import re
from . import assemble
from .models import parse_frontmatter_strict, canonicalize_url, validate_blog_output

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
