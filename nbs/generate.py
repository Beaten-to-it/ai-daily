import hashlib, re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from . import codex_cli
from .config import run_dir
from .models import (validate_blog_output, parse_frontmatter, split_frontmatter,
                     GenerationResult)

ROOT = Path(__file__).resolve().parent.parent
BLOG_PROMPT = ROOT / "prompts" / "blog.md"
ARTICLE_SCHEMA = ROOT / "schemas" / "article.schema.json"
DERIVED_SCHEMA = ROOT / "schemas" / "derived.schema.json"
_DELIMS = ("<<<SOURCE_BEGIN>>>", "<<<SOURCE_END>>>")
_ARTICLE_HEADINGS = ("## 무엇이 있었나", "## 왜 중요한가", "## 확인 범위", "## 출처")
GEN_TIMEOUT = 900   # ponytail: a failed item may consume this twice because retries=1

def _sanitize_source(text):
    # neutralize delimiter tokens so untrusted source can't escape the data fence (§10)
    for tok in _DELIMS:
        text = text.replace(tok, "[delimiter removed]")
    return text

def build_blog_prompt(item, fetched, date):
    # §10: <<SOURCE>> (untrusted fetched.text) must be substituted LAST. Trusted-placeholder
    # replacements run over the WHOLE string, so if SOURCE went in first, untrusted text
    # containing literal placeholder tokens (e.g. "<URL>") would get rewritten with trusted
    # values from inside the source fence -- a template-injection gap.
    tmpl = BLOG_PROMPT.read_text(encoding="utf-8")
    source_published_at = item.get("published_at") or "unknown"
    filled = (tmpl.replace("<DATE>", date)
                  .replace("<EVENT_KEY>", item.get("event_key",""))
                  .replace("<SOURCE_TYPE>", item.get("source_type",""))
                  .replace("<EVIDENCE_LEVEL>", fetched.evidence_level)
                  .replace("<SOURCE_NAME>", item.get("source", ""))
                  .replace("<SOURCE_PUBLISHED_AT>", source_published_at)
                  .replace("<URL>", item.get("url","")))
    return filled.replace("<<SOURCE>>", _sanitize_source(fetched.text))

def run_codex_markdown(text, date, operation, timeout=GEN_TIMEOUT):
    digest = hashlib.sha256(operation.encode("utf-8")).hexdigest()[:16]
    obj = codex_cli.run_json(
        text, ARTICLE_SCHEMA, run_dir(date) / "codex-work" / f"article-{digest}", timeout
    )
    markdown = obj.get("markdown")
    if not isinstance(markdown, str):
        raise ValueError("article output missing markdown")
    return markdown


def run_codex_derived(text, date, operation, timeout=GEN_TIMEOUT):
    if operation not in {"executive", "guide"}:
        raise ValueError(f"unknown derived operation: {operation}")
    obj = codex_cli.run_json(
        text, DERIVED_SCHEMA, run_dir(date) / "codex-work" / operation, timeout
    )
    if not isinstance(obj.get("publish"), bool) or not isinstance(obj.get("markdown"), str):
        raise ValueError("derived output is invalid")
    return obj

def _sanitize_title(md):
    # A model can emit a title our lenient parse_frontmatter accepts but Hugo's
    # strict YAML rejects -- e.g. an inner straight quote (`title: "A"는 B` = a complete "A"
    # scalar + trailing garbage, real 2026-07-03 build break), a bare `:`, or a `#`
    # (comment). title is the only free-text front-matter field (others are enums/URL/list/
    # date we control), so re-emit its value as a single-quoted YAML scalar: only `'` needs
    # doubling, and a literal `"` is harmless inside single quotes. Matches an optionally
    # indented keys with optional space before the colon (parse_frontmatter accepts those)
    # are normalized to column zero because Hugo rejects mixed top-level indentation.
    # Block scalars are rejected because
    # their payload could look like trusted front-matter keys to our line parser. Unwrapping
    # a single-quoted scalar un-doubles `''`, so the fix is idempotent on its own output.
    # `tags` is the other free-text field; switch to a real YAML dump if it ever needs
    # multiline YAML. No-op without a complete first-line front matter block.
    parts = split_frontmatter(md)
    if parts is None:
        return md
    def _repl(m):
        indent, raw = m.group(1), m.group(2).strip()
        if re.fullmatch(r"[>|][0-9+-]*", raw):
            raise ValueError("block scalar title is not allowed")
        if len(raw) >= 2 and raw[0] == raw[-1] == "'":
            raw = raw[1:-1].replace("''", "'")    # unwrap + un-escape a single-quoted scalar
        elif len(raw) >= 2 and raw[0] == raw[-1] == '"':
            raw = raw[1:-1]                        # unwrap a double-quoted scalar (backslash-escapes: accepted ceiling)
        return f"{indent}title: '" + raw.replace("'", "''") + "'"
    fm = re.sub(r"(?m)^([ \t]*)title[ \t]*:(.*)$", _repl, parts[0])
    fm = re.sub(r"(?m)^[ \t]+(?=[A-Za-z_][A-Za-z0-9_-]*[ \t]*:)", "", fm)
    return "---\n" + fm + "\n---\n" + parts[1]

def _strip_fences(raw):
    m = re.search(r"```(?:markdown)?\s*(---[\s\S]*)```", raw)
    body = m.group(1) if m else raw
    # models often narrate before the doc ("선택 확정: ...\n\n---\ntitle:..."); drop any
    # prose preamble before the first front-matter opener line so the doc starts at ---.
    fm = re.search(r"(?m)^---\s*$", body)
    if fm:
        body = body[fm.start():]
    # sanitize the title here (the one seam every LLM doc -- blog/usecase/ax -- shares) so a
    # Hugo-breaking title can't reach content/ from any generation path. See _sanitize_title.
    return _sanitize_title(body.strip() + "\n")

def _duplicate_frontmatter_keys(md):
    # parse_frontmatter is dict-based (last key wins); a duplicate key (fake+real) still
    # passes the event_key/source_url check below via the surviving value, but both keys
    # remain in the returned md string -- a downstream YAML consumer could resolve the
    # duplicate differently than we did. Reject outright instead of picking one (§10).
    parts = split_frontmatter(md)
    if parts is None:
        return []
    keys = [ln.split(":", 1)[0].strip() for ln in parts[0].splitlines() if ":" in ln]
    seen, dupes = set(), []
    for k in keys:
        (dupes.append(k) if k in seen else seen.add(k))
    return dupes

def _copies_long_source_span(body, source, window=120):
    body = " ".join((body or "").split()).casefold()
    source = " ".join((source or "").split()).casefold()
    if len(body) < window or len(source) < window:
        return False
    # A copied span of at least 150 normalized characters contains one sampled 120-char window.
    return any(body[start:start + window] in source
               for start in range(0, len(body) - window + 1, 30))

def render_blog(item, fetched, date, timeout=GEN_TIMEOUT):
    md = _strip_fences(run_codex_markdown(
        build_blog_prompt(item, fetched, date), date, f"article:{item.get('event_key', '')}", timeout
    ))
    errs = validate_blog_output(md)
    if errs:
        raise ValueError("blog schema invalid: " + "; ".join(errs[:6]))
    dupes = _duplicate_frontmatter_keys(md)
    if dupes:
        raise ValueError(f"front matter has duplicate keys: {sorted(set(dupes))}")
    fm = parse_frontmatter(md)
    if fm.get("event_key") != item.get("event_key"):
        raise ValueError(f"event_key mismatch: {fm.get('event_key')} != {item.get('event_key')}")
    if fm.get("source_url") != item.get("url"):
        raise ValueError(f"source_url mismatch: {fm.get('source_url')} != {item.get('url')}")
    if fm.get("source_name") != item.get("source"):
        raise ValueError(f"source_name mismatch: {fm.get('source_name')} != {item.get('source')}")
    source_published_at = item.get("published_at") or "unknown"
    if fm.get("source_published_at") != source_published_at:
        raise ValueError(
            f"source_published_at mismatch: {fm.get('source_published_at')} != {source_published_at}"
        )
    expected = {
        "date": date,
        "source_type": item.get("source_type"),
        "evidence_level": fetched.evidence_level,
    }
    for key, value in expected.items():
        if fm.get(key) != value:
            raise ValueError(f"{key} mismatch: {fm.get(key)} != {value}")
    body = split_frontmatter(md)[1]
    missing = [heading for heading in _ARTICLE_HEADINGS if heading not in body]
    if missing:
        raise ValueError(f"article body missing sections: {missing}")
    if item.get("url") not in body:
        raise ValueError("article body missing source link")
    if _copies_long_source_span(body, fetched.text):
        raise ValueError("article body copies a long source span")
    return md

def _gen_one(item, fetched, date, render, timeout, retries):
    slug = f"{date}-{item.get('event_key','')}"
    base = dict(event_key=item.get("event_key",""), title=item.get("title",""),
                url=item.get("url",""), source=item.get("source",""),
                source_type=item.get("source_type",""),
                evidence_level=fetched.evidence_level, slug=slug,
                rank=item.get("rank",999), rationale=item.get("rationale",""))
    if fetched.evidence_level == "exclude":
        return GenerationResult(status="excluded", post_path=None, error="unverified", **base)
    last = None
    for _ in range(retries + 1):
        try:
            md = render(item, fetched, date, timeout=timeout)
            r = GenerationResult(status="ok", post_path=f"articles/{slug}.md", **base)
            r._md = md            # carried for staging; not serialized by to_dict()
            return r
        except Exception as e:
            last = str(e)[:200]
    return GenerationResult(status="failed", post_path=None, error=last, **base)

def _mapped(ek, fetched_map):
    # an unhashable event_key (corrupt selection.json: `"event_key": []`) can't be a map key -> not
    # generatable; `in` would raise TypeError, so guard it (stage already skipped adding such keys).
    try:
        return ek in fetched_map
    except TypeError:
        return False

def generate_all(items, fetched_map, date, *, max_workers=4, timeout=GEN_TIMEOUT, retries=1, render=None):
    render = render or render_blog
    todo = [it for it in items if _mapped(it.get("event_key"), fetched_map)]
    out = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_gen_one, it, fetched_map[it["event_key"]], date,
                          render, timeout, retries): it for it in todo}
        for f in as_completed(futs):
            out.append(f.result())
    out.sort(key=lambda r: r.rank)
    return out
