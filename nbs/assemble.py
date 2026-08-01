import re
from pathlib import Path


TARGET_ARTICLES = 30
_CAT = {
    "article": "뉴스/블로그",
    "paper": "논문",
    "sns": "소셜",
    "video": "영상",
    "repo": "오픈소스",
}


def publishable(results):
    return [result for result in results if result.status == "ok"]


def volume_status(count):
    if count == 0:
        return "empty"
    if count < 10:
        return "warning"
    return "normal"


def _safe_daily_text(value, limit=300):
    text = " ".join(str(value or "").split())
    text = re.sub(r"\{\{[<%].*?[>%]\}\}", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    return re.sub(r"[\\\[\](){}<>]", "", text).strip()[:limit]


def build_daily(results, date):
    items = sorted(publishable(results), key=lambda result: result.rank)
    lines = [
        "---",
        f"title: AI 데일리 {date}",
        f"date: {date}",
        "---",
        "",
        f"# AI 데일리 — {date}",
        "",
    ]
    by_category = {}
    for result in items:
        by_category.setdefault(_CAT.get(result.source_type, "기타"), []).append(result)
    for category, grouped in by_category.items():
        lines.extend((f"## {category}", ""))
        for result in grouped:
            from .models import parse_frontmatter_strict

            generated_title = parse_frontmatter_strict(
                getattr(result, "_md", "") or ""
            ).get("title")
            title = _safe_daily_text(generated_title or result.title)
            hook = _safe_daily_text(result.rationale) or title
            link = '{{< relref "/articles/%s.md" >}}' % result.slug
            lines.append(f"- [{title}]({link}) — {hook}")
        lines.append("")
    return "\n".join(lines) + "\n"


ROOT = Path(__file__).resolve().parent.parent
GUIDE_PROMPT = ROOT / "prompts" / "usecase.md"
EXECUTIVE_PROMPT = ROOT / "prompts" / "ax.md"
EXECUTIVE_TIMEOUT = 900


def _blog_snippet(markdown, limit=300):
    if not markdown:
        return ""
    from .models import split_frontmatter

    parts = split_frontmatter(markdown)
    body = parts[1] if parts else markdown
    return " ".join(body.split())[:limit]


def _summary_lines(results):
    from .generate import _sanitize_source

    lines = []
    for result in publishable(results):
        snippet = _blog_snippet(getattr(result, "_md", "") or "")
        lines.append(
            f"- {result.title} ({result.source}) -> /articles/{result.slug}/\n  {snippet}"
        )
    return _sanitize_source("\n".join(lines))


def build_guide_prompt(results, date):
    template = GUIDE_PROMPT.read_text(encoding="utf-8").replace("<DATE>", date)
    return template.replace("<<SUMMARIES>>", _summary_lines(results))


def _validate_derived(raw, kind):
    from .generate import _strip_fences
    from .models import parse_frontmatter, split_frontmatter

    markdown = _strip_fences(raw)
    parts = split_frontmatter(markdown)
    if parts is None:
        raise ValueError(f"{kind} output missing/unterminated front matter")
    keys = set(parse_frontmatter(markdown))
    allowed = {"title", "date", "tags"}
    missing = allowed - keys
    if missing:
        raise ValueError(f"{kind} front matter missing: {sorted(missing)}")
    unknown = keys - allowed
    if unknown:
        raise ValueError(f"{kind} front matter unknown: {sorted(unknown)}")
    if not parts[1].strip():
        raise ValueError(f"{kind} output has empty body")
    return markdown


def build_guide(results, date, *, run=None):
    if not publishable(results):
        return None
    prompt = build_guide_prompt(results, date)
    if run is None:
        from .generate import run_codex_derived

        generated = run_codex_derived(prompt, date, "guide")
        if not generated["publish"]:
            return None
        raw = generated["markdown"]
    else:
        raw = run(prompt)
    markdown = _validate_derived(raw, "guide")
    return _validate_article_refs(markdown, results, "guide")


_ANY_REF_SHORTCODE = re.compile(r"\{\{[<%]\s*/?\s*(?:rel)?ref\b")
_ARTICLE_RELREF = re.compile(r'relref\s+"/articles/([^"]+?)\.md"')


def _validate_article_refs(markdown, results, kind, require=False):
    from .models import split_frontmatter

    body = split_frontmatter(markdown)[1]
    angle = re.compile(r"\{\{<\s*" + _ARTICLE_RELREF.pattern + r"\s*>\}\}")
    linked = set(angle.findall(body))
    if _ANY_REF_SHORTCODE.search(angle.sub("", body)):
        raise ValueError(f"{kind}: non-angle ref/relref shortcode remains")
    if require and not linked:
        raise ValueError(f"{kind}: no article-anchor relref")
    allowed = {result.slug for result in publishable(results)}
    if not linked <= allowed:
        raise ValueError(
            f"{kind}: relref to non-publishable slug: {sorted(linked - allowed)}"
        )
    return markdown


def build_executive_prompt(results, date):
    template = EXECUTIVE_PROMPT.read_text(encoding="utf-8").replace("<DATE>", date)
    return template.replace("<<SUMMARIES>>", _summary_lines(results))


def build_executive(results, date, *, run=None):
    if not publishable(results):
        return None
    prompt = build_executive_prompt(results, date)
    if run is None:
        from .generate import run_codex_derived

        generated = run_codex_derived(
            prompt, date, "executive", timeout=EXECUTIVE_TIMEOUT
        )
        if not generated["publish"]:
            return None
        raw = generated["markdown"]
    else:
        raw = run(prompt)
    markdown = _validate_derived(raw, "executive")
    return _validate_article_refs(markdown, results, "executive", require=True)
