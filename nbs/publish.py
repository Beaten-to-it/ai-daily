import re
from . import assemble

_TLDR_MARKER = re.compile(r"(?im)^\s*(?:#+\s*TL;DR|\*\*\s*TL;DR\s*\*\*)\s*$")

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
