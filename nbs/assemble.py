FLOOR_N = 3
_CAT = {"article":"뉴스/블로그", "paper":"논문", "sns":"소셜",
        "video":"영상", "repo":"오픈소스"}

def publishable(results):
    return [r for r in results if r.status == "ok"]

def floor_ok(results):
    return len(publishable(results)) >= FLOOR_N

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
            lines.append(f"- [{r.title}](/posts/{r.slug}/) — {hook}")
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

def build_usecase_prompt(results, date):
    lines = []
    for r in publishable(results):
        snip = _blog_snippet(getattr(r, "_md", "") or "")
        lines.append(f"- {r.title} ({r.source}) -> /posts/{r.slug}/\n  {snip}")
    return (USECASE_PROMPT.read_text(encoding="utf-8")
            .replace("<<SUMMARIES>>", "\n".join(lines)).replace("<DATE>", date))

def build_usecase(results, date, *, run=None):
    if not publishable(results):
        return None
    if run is None:
        from .generate import run_claude_notools as run
    raw = run(build_usecase_prompt(results, date)).strip()
    if not raw.startswith("---"):
        raise ValueError("usecase output missing front matter")
    return raw + "\n"
