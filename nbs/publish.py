import re
import subprocess, shutil, tempfile
from pathlib import Path
from . import assemble
from .models import parse_frontmatter_strict, canonicalize_url, validate_blog_output
from .config import ROOT, run_dir

_TLDR_MARKER = re.compile(r"(?im)^\s*(?:#+\s*TL;DR|\*\*\s*TL;DR\s*\*\*)\s*$")
_RELREF = re.compile(r'relref\s+"/posts/([^"]+?)\.md"')

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
    return sorted(posts) + [f"content/news/{date}.md", f"content/usecase/{date}.md", "data/published.csv"]

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
    return errs
