import re
import subprocess, shutil, tempfile, argparse, json, os
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit
from . import assemble
from . import config
from . import ledger as ledger_mod
from .models import (parse_frontmatter_strict, canonicalize_url,
                     validate_blog_output, split_frontmatter)
from .config import ROOT, run_dir

_TLDR_MARKER = re.compile(r"(?im)^\s*(?:#+\s*TL;DR|\*\*\s*TL;DR\s*\*\*)\s*$")
_RELREF = re.compile(r'relref\s+"/articles/([^"]+?)\.md"')
# slug flows from generation.json into fs paths AND git pathspecs. P2b bounds event_key to
# this charset, but P2c must not TRUST its input across the contract: a corrupt/hand-edited
# slug like "../_index" would escape content/articles/ (promote writes it, rollback mis-handles
# the non-normalized path). Reject at the completeness gate, before any write. (§10 boundary.)
# fullmatch (not match): `$` matches before a trailing newline, so `re.match` would accept
# "evil\n"; fullmatch requires the WHOLE string to be in-charset.
_SLUG_RE = re.compile(r"[a-z0-9-]{1,120}")
# date is ALSO a path component (runs/<date>, content/daily/<date>.md, staging/<date>). A
# corrupt generation.json "date":"../_index" would path-traverse exactly like a bad slug.
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_HUGO_TIMEOUT = 300

def _body(md):
    parts = split_frontmatter(md)
    return parts[1] if parts else md

def extract_tldr(md, limit=500):
    body = _body(md)
    m = _TLDR_MARKER.search(body)
    if m:
        seg = body[m.end():]
        nxt = re.search(r"(?m)^\s*#+\s", seg)          # stop at next heading
        seg = seg[:nxt.start()] if nxt else seg
        text = " ".join(l.strip().lstrip("-*").strip()
                        for l in seg.splitlines() if l.strip())
        if text:
            return text[:limit]
    for para in re.split(r"\n\s*\n", body):            # fallback: first non-empty paragraph
        t = " ".join(para.split()).strip()
        if t:
            return t[:limit]
    return ""

def _ok(gen):       return [r for r in gen.get("results", []) if r.get("status") == "ok"]
def _evidence(gen): return [r for r in gen.get("results", []) if r.get("evidence_level") in ("confirmed", "short")]

def decide(gen):
    count = len(_ok(gen))
    if count == 0:
        return "held", "generation produced 0 publishable articles (empty-day guard)"
    if count < 10:
        return "publish", f"warning: low article volume ({count} < 10)"
    return "publish", "ok"

def check_completeness(gen, staging):
    errs = []; ok = _ok(gen); date = gen.get("date")
    slugs, eks, canons = [], [], []
    for r in ok:
        slug = r.get("slug", "")
        if not _SLUG_RE.fullmatch(slug):    # reject-and-isolate: unsafe slug never touches fs/git
            errs.append(f"unsafe slug rejected: {slug!r}"); continue
        if slug != f"{date}-{r.get('event_key','')}":   # §"date-scoped": slug must be THIS day's
            errs.append(f"{slug}: slug not date-scoped (expected {date}-{r.get('event_key','')})"); continue
        slugs.append(slug); eks.append(r.get("event_key")); canons.append(canonicalize_url(r.get("url", "")))
        if r.get("post_path") != f"articles/{slug}.md":
            errs.append(f"{slug}: post_path != articles/{slug}.md (got {r.get('post_path')})")
        p = staging / "articles" / f"{slug}.md"
        if not p.exists():
            errs.append(f"{slug}: staging post file missing"); continue
        md = p.read_text(encoding="utf-8")
        verrs = validate_blog_output(md)                    # body non-empty + required keys + schema
        if verrs:
            errs.append(f"{slug}: invalid blog ({'; '.join(verrs[:3])})")
        if not md[md.find('---', md.find('---')+3)+3:].strip():
            errs.append(f"{slug}: empty body")
        fm = parse_frontmatter_strict(md)
        if fm.get("event_key") != r.get("event_key"):
            errs.append(f"{slug}: front matter event_key {fm.get('event_key')} != {r.get('event_key')}")
        if fm.get("source_url") != r.get("url"):
            errs.append(f"{slug}: front matter source_url != result url")
        if fm.get("date") != date:
            errs.append(f"{slug}: front matter date {fm.get('date')} != {date}")
        if fm.get("source_name") != r.get("source"):
            errs.append(f"{slug}: front matter source_name mismatch")
        if fm.get("source_type") != r.get("source_type"):
            errs.append(f"{slug}: front matter source_type mismatch")
        if fm.get("evidence_level") != r.get("evidence_level"):
            errs.append(f"{slug}: front matter evidence_level mismatch")
        tags = fm.get("tags")
        if not isinstance(tags, list) or not tags:
            errs.append(f"{slug}: tags must be a non-empty list")
    for label, vals in (("slug", slugs), ("event_key", eks), ("canonical_url", canons)):
        if len(set(vals)) != len(vals):
            errs.append(f"duplicate {label} across ok results")
    daily = staging / "daily" / f"{date}.md"
    linked = set(_RELREF.findall(daily.read_text(encoding="utf-8"))) if daily.exists() else set()
    if linked != set(slugs):
        errs.append(f"daily links {sorted(linked)} != ok slugs {sorted(slugs)}")
    return errs

def _git(args, timeout=None):
    # publish runs only LOCAL git ops (commit/add/status/cat-file/ls-tree/show/rev-parse) — these
    # fail fast, they never hang, so no timeout (a synthetic timeout rc would masquerade as a real
    # git answer). GIT_TERMINAL_PROMPT=0 so a credential prompt on commit fails fast, never hangs.
    # env per call (not snapshotted at import) so runtime GIT_CONFIG_*/env overrides are honored.
    try:
        return subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, returncode=124, stdout="", stderr="git timed out")

def date_writeset(gen):
    date = gen["date"]
    articles = {p.relative_to(ROOT).as_posix() for p in (ROOT/"content"/"articles").glob(f"{date}-*.md")}
    # Include HEAD-tracked same-date articles so a deleted-but-tracked stale file
    # remains in scope even though the filesystem glob cannot see it.
    lf = _git(["ls-files", "--", f"content/articles/{date}-*.md"])
    if lf.returncode != 0:            # fail CLOSED: an incomplete write-set would skip rollback/add
        raise RuntimeError(f"ls-files failed (rc={lf.returncode}); cannot compute write-set")
    articles |= set(lf.stdout.split())
    articles |= {f"content/articles/{r['slug']}.md" for r in _ok(gen)}
    return sorted(articles) + [f"content/daily/{date}.md", f"content/guides/{date}.md",
                            f"content/executive/{date}.md", "data/published.csv"]

def preflight_clean(paths):
    r = _git(["status", "--porcelain", "--"] + paths)
    if r.returncode != 0:            # fail CLOSED: a git error/timeout (rc=124) must NOT read as
        return [f"git status failed (rc={r.returncode})"]   # "clean" -> publish.run aborts, no promote
    return [ln[3:].strip() for ln in r.stdout.splitlines() if ln[3:].strip()]

def promote(gen, staging):
    date = gen["date"]; touched = []
    ok_files = {f"{r['slug']}.md" for r in _ok(gen)}
    for p in (ROOT/"content"/"articles").glob(f"{date}-*.md"):     # delete stale same-date articles
        if p.name not in ok_files:
            touched.append(p.relative_to(ROOT).as_posix()); p.unlink()
    def _cp(src, dst):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst); touched.append(dst.relative_to(ROOT).as_posix())
    for r in _ok(gen):
        _cp(staging/"articles"/f"{r['slug']}.md", ROOT/"content"/"articles"/f"{r['slug']}.md")
    _cp(staging/"daily"/f"{date}.md", ROOT/"content"/"daily"/f"{date}.md")
    guide = staging/"guides"/f"{date}.md"
    target_guide = ROOT/"content"/"guides"/f"{date}.md"
    if guide.exists():
        _cp(guide, target_guide)
    elif target_guide.exists():
        touched.append(target_guide.relative_to(ROOT).as_posix()); target_guide.unlink()
    executive = staging/"executive"/f"{date}.md"
    target_executive = ROOT/"content"/"executive"/f"{date}.md"
    if executive.exists():
        _cp(executive, target_executive)
    elif target_executive.exists():
        touched.append(target_executive.relative_to(ROOT).as_posix()); target_executive.unlink()
    return touched

def rollback(paths):
    for rel in paths:
        # ls-tree cleanly separates the three cases cat-file conflates (cat-file returns rc 128 for
        # BOTH a missing path AND a corrupt repo): rc 0 + non-empty stdout = tracked, rc 0 + empty =
        # CONFIRMED absent, rc != 0 = git error. Only unlink on a positively-confirmed absence — a
        # git error (or timeout) must NEVER delete a possibly-tracked worktree file (data loss).
        r = _git(["ls-tree", "HEAD", "--", rel])
        if r.returncode == 0 and r.stdout.strip():         # tracked in HEAD -> restore
            _git(["restore", "--staged", "--worktree", "--source=HEAD", "--", rel])
        elif r.returncode == 0:                            # confirmed absent -> unstage + remove
            _git(["reset", "-q", "--", rel])
            p = ROOT / rel
            if p.exists(): p.unlink()
        else:                                              # git error -> fail CLOSED: unstage only, keep file
            _git(["reset", "-q", "--", rel])

def _hugo_build(outdir, content_dir=None):
    # no pipe: exit code must survive. A staging contentDir makes shadow validation read-only.
    args = ["hugo", "--quiet", "-d", outdir]
    if content_dir is not None:
        args.extend(["--contentDir", str(content_dir)])
    try:
        return subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=_HUGO_TIMEOUT).returncode
    except subprocess.TimeoutExpired:
        return 124

def _rss_item_targets(feed):
    root = ET.fromstring(feed)
    targets = []
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1] != "item":
            continue
        for child in item:
            if child.tag.rsplit("}", 1)[-1] in {"link", "guid"} and child.text:
                targets.append(child.text.strip())
    return targets

def build_verify(gen, content_dir=None):
    date = gen["date"]; errs = []
    with tempfile.TemporaryDirectory() as td:
        build_rc = (_hugo_build(td, content_dir=content_dir)
                    if content_dir is not None else _hugo_build(td))
        if build_rc != 0:
            return ["hugo build failed (exit != 0)"]
        out = Path(td)
        content_root = Path(content_dir) if content_dir is not None else ROOT / "content"
        base_path = urlsplit(config.SITE_BASEURL).path.rstrip("/")
        daily_html = out / "daily" / date / "index.html"
        if not daily_html.exists():
            errs.append(f"daily page not rendered: daily/{date}/index.html")
        html = daily_html.read_text(encoding="utf-8", errors="replace") if daily_html.exists() else ""
        for r in _ok(gen):
            slug = r["slug"]
            if not (out/"articles"/slug/"index.html").exists():
                errs.append(f"article not rendered: articles/{slug}/index.html")
            if f"{base_path}/articles/{slug}/" not in html:
                errs.append(f"daily missing subpath href for {slug}")
        feed_path = out / "index.xml"
        feed = feed_path.read_text(encoding="utf-8", errors="replace") if feed_path.exists() else ""
        try:
            targets = _rss_item_targets(feed) if feed_path.exists() else []
        except ET.ParseError:
            targets = []
            errs.append("home RSS is malformed XML")
        target_text = "\n".join(targets)
        if f"{base_path}/daily/{date}/" not in target_text:
            errs.append("home RSS missing daily edition")
        if re.search(re.escape(base_path) + r"/(?:articles|executive|guides|posts|news|ax|usecase)/", target_text):
            errs.append("home RSS contains non-daily content")
        if (content_root/"guides"/f"{date}.md").exists() and not (out/"guides"/date/"index.html").exists():
            errs.append(f"guide page not rendered: guides/{date}/index.html")
        if (content_root/"executive"/f"{date}.md").exists() and not (out/"executive"/date/"index.html").exists():
            errs.append(f"executive page not rendered: executive/{date}/index.html")
    return errs

def ledger_rows(gen):
    rows = []
    for r in _ok(gen):
        md = (ROOT/"content"/"articles"/f"{r['slug']}.md").read_text(encoding="utf-8")
        summary = extract_tldr(md)
        if not summary:
            raise ValueError(f"empty ledger summary for {r['slug']} (protects §6 dedup)")
        tags = parse_frontmatter_strict(md).get("tags") or []
        rows.append({
            "canonical_key": canonicalize_url(r.get("url", "")),
            "event_key": r.get("event_key", ""), "date": gen["date"],
            "title": r.get("title", ""), "url": r.get("url", ""), "source": r.get("source", ""),
            "post_path": r.get("post_path", ""), "summary": summary,
            "entities": "", "tags": ",".join(tags) if isinstance(tags, list) else str(tags),
            "confidence": "",
        })
    return rows

def _write_manifest(date, payload):
    (run_dir(date)/"publish.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

def _degraded(gen):
    ok, ev = len(_ok(gen)), len(_evidence(gen)); d = {}
    if gen.get("guide_error"): d["guide"] = gen["guide_error"]
    if gen.get("executive_error"): d["executive"] = gen["executive_error"]
    if ok < ev: d["generation_failed_count"] = ev - ok
    if 0 < ok < 10: d["article_volume"] = "warning"
    if gen.get("source_health_warnings"): d["source_health"] = gen["source_health_warnings"]
    return d

def _commit_msg(date, gen):
    return (f"publish(ai-daily): {date} — {len(_ok(gen))} articles"
            "\n\nGenerated-By: Codex")

def _fail(date, gen, reason, error=None):
    return _write_manifest(date, {"date": date, "status": "failed", "reason": reason,
                                  "volume_status": assemble.volume_status(len(_ok(gen))),
                                  "promoted": [], "degraded": _degraded(gen), "commit_sha": None, "error": error or reason})

def run(date, *, do_commit=True):
    # validate the date arg BEFORE run_dir(date) (used for manifest path) can traverse.
    if not _DATE_RE.fullmatch(date or ""):
        return {"date": date, "status": "failed", "reason": "invalid date",
                "promoted": [], "degraded": {}, "commit_sha": None, "error": "date must be YYYY-MM-DD"}
    d = run_dir(date)
    gen = json.loads((d/"generation.json").read_text(encoding="utf-8"))
    # gen["date"] flows into fs paths everywhere (date_writeset/promote/build_verify); pin it to
    # the validated arg so a corrupt generation.json date cannot escape the date scope.
    if gen.get("date") != date:
        return _fail(date, gen, "generation.json date mismatch", f"{gen.get('date')!r} != {date!r}")
    staging = d/"staging"
    decision, reason = decide(gen)
    if decision == "held":
        return _write_manifest(date, {"date": date, "status": "held", "reason": reason,
                                      "volume_status": "empty", "promoted": [],
                                      "degraded": _degraded(gen), "commit_sha": None, "error": None})
    branch = _git(["symbolic-ref", "--quiet", "--short", "HEAD"])
    if branch.returncode != 0 or branch.stdout.strip() != "main":
        return _fail(date, gen, "publishing requires the local main branch")
    if not (_git(["config","user.email"]).stdout.strip() and _git(["config","user.name"]).stdout.strip()):
        return _fail(date, gen, "git identity not configured")
    ws = date_writeset(gen)
    dirty = preflight_clean(ws)
    if dirty:
        return _fail(date, gen, f"write-set dirty: {dirty}")
    if _git(["diff", "--cached", "--quiet"]).returncode != 0:
        return _fail(date, gen, "git index not clean (staged changes present)")
    cerrs = check_completeness(gen, staging)         # BEFORE promote — nothing to roll back
    if cerrs:
        return _fail(date, gen, "completeness", "; ".join(cerrs[:8]))
    touched = []
    try:
        touched = promote(gen, staging)
        berrs = build_verify(gen)
        if berrs:
            raise RuntimeError("; ".join(berrs[:8]))
        ledger_mod.rewrite_date(date, ledger_rows(gen), path=ROOT/"data"/"published.csv")
        commit_sha = None
        if do_commit:
            # R2-#1: `git add -- <pathspec>` fails (rc 128) on a ws path that neither exists
            # nor is in HEAD (e.g. a guide on a degraded day). Add only real paths; keep full
            # `ws` for the staged-subset check and rollback. The HEAD-tracked subset comes from ONE
            # CHECKED ls-tree — fail closed if it errors, so a git failure can't silently drop a
            # staged DELETION of a tracked file (which would leave a stale page in HEAD/origin).
            lt = _git(["ls-tree", "-r", "--name-only", "HEAD", "--"] + ws)
            if lt.returncode != 0:
                raise RuntimeError(f"ls-tree failed (rc={lt.returncode}); cannot determine tracked set")
            tracked = set(lt.stdout.split())
            add_paths = [p for p in ws if (ROOT/p).exists() or p in tracked]
            if _git(["add", "-A", "--"] + add_paths).returncode != 0:
                raise RuntimeError("git add failed")
            staged = [l for l in _git(["diff","--cached","--name-only"]).stdout.splitlines() if l.strip()]
            if any(s not in ws for s in staged):
                raise RuntimeError(f"unexpected staged paths: {[s for s in staged if s not in ws]}")
            if _git(["diff","--cached","--quiet"]).returncode == 0:
                commit_sha = _git(["rev-parse","HEAD"]).stdout.strip()   # nothing changed = idempotent no-op
            else:
                c = _git(["commit","-m", _commit_msg(date, gen)])
                if c.returncode != 0:
                    raise RuntimeError(f"git commit failed: {c.stderr[:200]}")
                commit_sha = _git(["rev-parse","HEAD"]).stdout.strip()
        return _write_manifest(date, {"date": date, "status": "published", "reason": reason,
                                      "volume_status": assemble.volume_status(len(_ok(gen))),
                                      "promoted": touched, "degraded": _degraded(gen),
                                      "commit_sha": commit_sha, "error": None})
    except Exception as e:
        rollback(ws)                                  # date-scoped: restores content + ledger
        return _fail(date, gen, "promote/verify/commit", str(e)[:200])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--date", required=True)
    ap.add_argument("--no-commit", action="store_true"); a = ap.parse_args()
    m = run(a.date, do_commit=not a.no_commit)
    print(f"[{m['status']}] {a.date} promoted={len(m['promoted'])} degraded={m['degraded']} reason={m['reason']}")

if __name__ == "__main__":
    main()
