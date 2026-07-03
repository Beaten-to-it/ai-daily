import re
FLOOR_N = 3
_CAT = {"article":"뉴스/블로그", "paper":"논문", "sns":"소셜",
        "video":"영상", "repo":"오픈소스"}

def publishable(results):
    return [r for r in results if r.status == "ok"]

def floor_ok(results):
    # §4: floor is a mass-source-failure detector on EVIDENCE (confirmed+short), not a
    # generation-success count and not a cap. P2c additionally requires ok>=1 to publish.
    return sum(1 for r in results if r.evidence_level in ("confirmed", "short")) >= FLOOR_N

def build_news_index(results, date):
    items = sorted(publishable(results), key=lambda r: r.rank)
    lines = ["---", f"title: AI 데일리 {date}", f"date: {date}", "---", "",
             f"# AI 데일리 — {date}", ""]
    by_cat = {}
    for r in items:                       # preserves rank order within each category
        by_cat.setdefault(_CAT.get(r.source_type, "기타"), []).append(r)
    for cat, rs in by_cat.items():
        lines.append(f"## {cat}")
        lines.append("")
        for r in rs:
            hook = (r.rationale or "").strip() or r.title
            link = '{{< relref "/posts/%s.md" >}}' % r.slug   # subpath-safe (baseURL=/ai-daily/)
            lines.append(f"- [{r.title}]({link}) — {hook}")
        lines.append("")
    return "\n".join(lines) + "\n"

from pathlib import Path
USECASE_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "usecase.md"

def _blog_snippet(md, limit=300):
    if not md:
        return ""
    end = md.find("---", md.find("---") + 3)
    body = md[end+3:] if end != -1 else md
    return " ".join(body.split())[:limit]

def _summary_lines(results):
    lines = []
    for r in publishable(results):
        snip = _blog_snippet(getattr(r, "_md", "") or "")
        lines.append(f"- {r.title} ({r.source}) -> /posts/{r.slug}/\n  {snip}")
    return "\n".join(lines)

def build_usecase_prompt(results, date):
    return (USECASE_PROMPT.read_text(encoding="utf-8")
            .replace("<<SUMMARIES>>", _summary_lines(results)).replace("<DATE>", date))

def build_usecase(results, date, *, run=None):
    if not publishable(results):
        return None
    if run is None:
        from .generate import run_claude_notools as run
    from .generate import _strip_fences
    from .models import parse_frontmatter
    md = _strip_fences(run(build_usecase_prompt(results, date)))  # same fence-strip as render_blog
    end = md.find("---", md.find("---") + 3)
    if not md.startswith("---") or end == -1:
        raise ValueError("usecase output missing/unterminated front matter")
    missing = {"title", "date", "tags"} - set(parse_frontmatter(md))
    if missing:
        raise ValueError(f"usecase front matter missing: {sorted(missing)}")
    if not md[end+3:].strip():
        raise ValueError("usecase output has empty body")
    return md

AX_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "ax.md"
# AX synthesizes over the whole day's summaries — heavier than a single blog/usecase, so it
# needs a longer claude -p budget than GEN_TIMEOUT(300s), which it empirically overruns
# (300s timed out; 900s succeeded). Without this the daily stage would ax_error every day.
AX_TIMEOUT = 900

# any ref/relref shortcode ({{< ref >}}, {{% relref %}}, ...) — used to reject NON-angle forms
# so a gate-pass AX body is also email-safe (email rewrites ONLY the angle form).
_ANY_REF_SHORTCODE = re.compile(r"\{\{[<%]\s*/?\s*(?:rel)?ref\b")

def build_ax_prompt(results, date):
    return (AX_PROMPT.read_text(encoding="utf-8")
            .replace("<<SUMMARIES>>", _summary_lines(results)).replace("<DATE>", date))

def build_ax(results, date, *, run=None):
    if not publishable(results):
        return None
    if run is None:
        from . import generate as _gen
        run = lambda p: _gen.run_claude_notools(p, timeout=AX_TIMEOUT)   # AX-specific long budget
    from .generate import _strip_fences
    from .models import parse_frontmatter
    from . import publish   # function-level: avoids assemble<->publish import cycle; reuse _RELREF
    md = _strip_fences(run(build_ax_prompt(results, date)))
    end = md.find("---", md.find("---") + 3)
    if not md.startswith("---") or end == -1:
        raise ValueError("ax output missing/unterminated front matter")
    missing = {"title", "date", "tags"} - set(parse_frontmatter(md))
    if missing:
        raise ValueError(f"ax front matter missing: {sorted(missing)}")
    body = md[end + 3:]
    if not body.strip():
        raise ValueError("ax output has empty body")
    # --- deterministic grounding gate (spec §16 (a)/(b)/(c)) ---
    angle = re.compile(r"\{\{<\s*" + publish._RELREF.pattern + r"\s*>\}\}")  # == email._RELREF_FULL form
    linked = set(angle.findall(body))
    if _ANY_REF_SHORTCODE.search(angle.sub("", body)):        # (c) non-angle ref/relref remains
        raise ValueError("ax: non-angle ref/relref shortcode remains (email would fail)")
    if not linked:                                            # (a) no post anchor
        raise ValueError("ax: no post-anchor relref — ungrounded")
    ok_slugs = {r.slug for r in publishable(results)}
    if not linked <= ok_slugs:                                # (b) hallucinated slug
        raise ValueError(f"ax: relref to non-publishable slug: {sorted(linked - ok_slugs)}")
    return md
