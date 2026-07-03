import re
import subprocess, shutil, tempfile, argparse, json
from pathlib import Path
from . import assemble
from . import ledger as ledger_mod
from .models import parse_frontmatter_strict, canonicalize_url, validate_blog_output
from .config import ROOT, run_dir

_TLDR_MARKER = re.compile(r"(?im)^\s*(?:#+\s*TL;DR|\*\*\s*TL;DR\s*\*\*)\s*$")
_RELREF = re.compile(r'relref\s+"/posts/([^"]+?)\.md"')
# slug flows from generation.json into fs paths AND git pathspecs. P2b bounds event_key to
# this charset, but P2c must not TRUST its input across the contract: a corrupt/hand-edited
# slug like "../_index" would escape content/posts/ (promote writes it, rollback mis-handles
# the non-normalized path). Reject at the completeness gate, before any write. (§10 boundary.)
# fullmatch (not match): `$` matches before a trailing newline, so `re.match` would accept
# "evil\n"; fullmatch requires the WHOLE string to be in-charset.
_SLUG_RE = re.compile(r"[a-z0-9-]{1,120}")
# date is ALSO a path component (runs/<date>, content/news/<date>.md, staging/<date>). A
# corrupt generation.json "date":"../_index" would path-traverse exactly like a bad slug.
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

def _body(md):
    end = md.find("---", md.find("---") + 3)   # skip front matter
    return md[end + 3:] if end != -1 else md

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
    if len(_evidence(gen)) < assemble.FLOOR_N:
        return "held", f"evidence floor not met ({len(_evidence(gen))} < {assemble.FLOOR_N}) — suspected mass source failure"
    if len(_ok(gen)) == 0:
        return "held", "generation produced 0 publishable posts (empty-day guard)"
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
        if r.get("post_path") != f"posts/{slug}.md":
            errs.append(f"{slug}: post_path != posts/{slug}.md (got {r.get('post_path')})")
        p = staging / "posts" / f"{slug}.md"
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
        if fm.get("evidence_level") != r.get("evidence_level"):
            errs.append(f"{slug}: front matter evidence_level mismatch")
        tags = fm.get("tags")
        if not isinstance(tags, list) or not tags:
            errs.append(f"{slug}: tags must be a non-empty list")
    for label, vals in (("slug", slugs), ("event_key", eks), ("canonical_url", canons)):
        if len(set(vals)) != len(vals):
            errs.append(f"duplicate {label} across ok results")
    news = staging / "news" / f"{date}.md"
    linked = set(_RELREF.findall(news.read_text(encoding="utf-8"))) if news.exists() else set()
    if linked != set(slugs):
        errs.append(f"news links {sorted(linked)} != ok slugs {sorted(slugs)}")
    return errs

def _git(args): return subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True)
def _head_has(rel): return _git(["cat-file", "-e", f"HEAD:{rel}"]).returncode == 0

def date_writeset(gen):
    date = gen["date"]
    posts = {str(p.relative_to(ROOT)) for p in (ROOT/"content"/"posts").glob(f"{date}-*.md")}
    # R2-#3: union with HEAD-tracked same-date posts so a worktree-deleted-but-tracked
    # stale post is still in scope (glob only sees files present on disk).
    posts |= set(_git(["ls-files", "--", f"content/posts/{date}-*.md"]).stdout.split())
    posts |= {f"content/posts/{r['slug']}.md" for r in _ok(gen)}
    return sorted(posts) + [f"content/news/{date}.md", f"content/usecase/{date}.md",
                            f"content/ax/{date}.md", "data/published.csv"]

def preflight_clean(paths):
    out = _git(["status", "--porcelain", "--"] + paths).stdout
    return [ln[3:].strip() for ln in out.splitlines() if ln[3:].strip()]

def promote(gen, staging):
    date = gen["date"]; touched = []
    ok_files = {f"{r['slug']}.md" for r in _ok(gen)}
    for p in (ROOT/"content"/"posts").glob(f"{date}-*.md"):     # delete stale same-date posts
        if p.name not in ok_files:
            touched.append(str(p.relative_to(ROOT))); p.unlink()
    def _cp(src, dst):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst); touched.append(str(dst.relative_to(ROOT)))
    for r in _ok(gen):
        _cp(staging/"posts"/f"{r['slug']}.md", ROOT/"content"/"posts"/f"{r['slug']}.md")
    _cp(staging/"news"/f"{date}.md", ROOT/"content"/"news"/f"{date}.md")
    uc = staging/"usecase"/f"{date}.md"
    target_uc = ROOT/"content"/"usecase"/f"{date}.md"
    if uc.exists():
        _cp(uc, target_uc)
    elif target_uc.exists():                        # R2-#2: degraded rerun — drop stale usecase
        touched.append(str(target_uc.relative_to(ROOT))); target_uc.unlink()
    ax = staging/"ax"/f"{date}.md"
    target_ax = ROOT/"content"/"ax"/f"{date}.md"
    if ax.exists():
        _cp(ax, target_ax)
    elif target_ax.exists():                        # degraded/rerun — drop stale ax
        touched.append(str(target_ax.relative_to(ROOT))); target_ax.unlink()
    return touched

def rollback(paths):
    for rel in paths:
        if _head_has(rel):
            _git(["restore", "--staged", "--worktree", "--source=HEAD", "--", rel])
        else:
            _git(["reset", "-q", "--", rel])          # unstage if staged (no-op otherwise)
            p = ROOT / rel
            if p.exists(): p.unlink()

def _hugo_build(outdir):
    # no pipe: exit code must survive. Uses hugo.toml baseURL (=/ai-daily/).
    return subprocess.run(["hugo", "--quiet", "-d", outdir], cwd=str(ROOT),
                          capture_output=True, text=True).returncode

def build_verify(gen):
    date = gen["date"]; errs = []
    with tempfile.TemporaryDirectory() as td:
        if _hugo_build(td) != 0:
            return ["hugo build failed (exit != 0)"]
        out = Path(td)
        news_html = out / "news" / date / "index.html"
        if not news_html.exists():
            errs.append(f"news page not rendered: news/{date}/index.html")
        html = news_html.read_text(encoding="utf-8", errors="replace") if news_html.exists() else ""
        for r in _ok(gen):
            slug = r["slug"]
            if not (out/"posts"/slug/"index.html").exists():
                errs.append(f"post not rendered: posts/{slug}/index.html")
            if f"/ai-daily/posts/{slug}/" not in html:
                errs.append(f"news missing subpath href for {slug}")
        if (ROOT/"content"/"usecase"/f"{date}.md").exists() and not (out/"usecase"/date/"index.html").exists():
            errs.append(f"usecase page not rendered: usecase/{date}/index.html")
        if (ROOT/"content"/"ax"/f"{date}.md").exists() and not (out/"ax"/date/"index.html").exists():
            errs.append(f"ax page not rendered: ax/{date}/index.html")
    return errs

def ledger_rows(gen):
    rows = []
    for r in _ok(gen):
        md = (ROOT/"content"/"posts"/f"{r['slug']}.md").read_text(encoding="utf-8")
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
    if gen.get("usecase_error"): d["usecase"] = gen["usecase_error"]
    if gen.get("ax_error"): d["ax"] = gen["ax_error"]
    if ok < ev or ok < assemble.FLOOR_N: d["generation_failed_count"] = ev - ok
    return d

def _commit_msg(date, gen):
    return (f"publish(ai-daily): {date} — {len(_ok(gen))} posts"
            "\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
            "\nClaude-Session: https://claude.ai/code/session_01VPUtXZyTzXtKwJfkZG3e5H")

def _fail(date, gen, reason, error=None):
    return _write_manifest(date, {"date": date, "status": "failed", "reason": reason,
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
                                      "promoted": [], "degraded": _degraded(gen), "commit_sha": None, "error": None})
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
            # nor is in HEAD (e.g. usecase on a degraded day). Add only real paths; keep full
            # `ws` for the staged-subset check and rollback.
            add_paths = [p for p in ws if (ROOT/p).exists() or _head_has(p)]
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
        return _write_manifest(date, {"date": date, "status": "published", "reason": "ok",
                                      "promoted": touched, "degraded": _degraded(gen), "commit_sha": commit_sha, "error": None})
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
