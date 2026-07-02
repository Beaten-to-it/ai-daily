# P2c — Promote & Publish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote a day's `runs/<date>/staging/` output into `content/`, verify it builds, rebuild the ledger for that date, and record it in one local git commit — atomically, idempotently, date-scoped, and with no push.

**Architecture:** New orchestrator `nbs/publish.py` reads the P2b `generation.json` contract, applies two publish gates (evidence-floor AND ok≥1), runs a strengthened completeness check **on staging before touching content/**, copies staging→content (deleting stale same-date content), verifies a throwaway Hugo build (rendered post/news/usecase files + subpath hrefs), rebuilds the ledger for the date, and makes a single local commit of exactly the date write-set — with a git-restore-based rollback on any pre-commit failure. Small fixes land in existing modules (`assemble.floor_ok`, `assemble.build_news_index`, `models` strict parser, `ledger` date-rebuild, `prompts/blog.md`).

**Tech Stack:** Python 3 (stdlib only — no new deps), Hugo 0.163.3 extended, git ≥2.23 (`git restore`), pytest.

## Global Constraints

- `python3` only (no bare `python`). **stdlib only** — no PyYAML / new dependency.
- P2c writes `content/{posts,news,usecase}/` + `data/published.csv`; it **does NOT push** (deploy = manual/P3).
- Hugo `baseURL=https://beaten-to-it.github.io/ai-daily/` (subpath `/ai-daily/`) — internal links MUST be `{{< relref "/posts/<slug>.md" >}}`, never root-relative `/posts/...`.
- FLOOR_N = 3 (evidence floor; not a cap).
- **Date-scoped** everything: preflight/promote/rollback/commit operate on exactly `content/posts/<date>-*.md` (glob) + `content/news/<date>.md` + `content/usecase/<date>.md` + `data/published.csv`. A rerun that drops an item must delete its stale same-date post.
- Build/verify commands never wrapped in a pipe (exit code must survive).
- Every commit message ends with the Co-Authored-By + Claude-Session trailer.
- TDD: failing test first, minimal impl, commit per task.

**Contract consumed (P2b → P2c), spec §6b:**
- `runs/<date>/generation.json` = `{date, status, results[], published_count, floor_failed, usecase_error}`.
- `results[]` (GenerationResult.to_dict): `{event_key, title, url, source, source_type, evidence_level(confirmed|short|exclude), status(ok|failed|excluded), post_path, slug, rank, rationale, error}`.
- `runs/<date>/staging/posts/<slug>.md` (ok items; slug=`<date>-<event_key>`), `staging/news/<date>.md`, `staging/usecase/<date>.md` (may be absent when `usecase_error` set — degraded day).
- Blog front matter keys: `title, date, tags, source_url, source_lang, source_type, evidence_level, event_key`.

---

### Task 1: Strict front-matter parser (unquote scalars + tags-as-list)

**Files:**
- Modify: `nbs/models.py` (add `_unquote`, `parse_frontmatter_strict` after `parse_frontmatter`, ~line 95)
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `parse_frontmatter(md) -> dict`.
- Produces: `parse_frontmatter_strict(md) -> dict` — scalars unquoted; `key: [a, b]` → `list[str]`; `key: []` → `[]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py (append)
from nbs.models import parse_frontmatter_strict

def test_parse_frontmatter_strict_unquotes_and_lists():
    md = ('---\ntitle: "Claude: 5"\nsource_url: \'https://x/a\'\n'
          'tags: [ai, "model release"]\nempty: []\n---\nbody\n')
    fm = parse_frontmatter_strict(md)
    assert fm["title"] == "Claude: 5"
    assert fm["source_url"] == "https://x/a"
    assert fm["tags"] == ["ai", "model release"]
    assert fm["empty"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_models.py::test_parse_frontmatter_strict_unquotes_and_lists -v`
Expected: FAIL — `ImportError: cannot import name 'parse_frontmatter_strict'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/models.py — after parse_frontmatter (~line 95)
def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s

def parse_frontmatter_strict(md) -> dict:
    # like parse_frontmatter but unquotes scalars and parses `key: [a, b]` as a list.
    # ponytail: NOT full YAML (stdlib-only rule); covers our own emitted front matter.
    # Inherits parse_frontmatter's unanchored-`---` split (documented defer-safe minor;
    # our posts never put `---` inside a value).
    out = {}
    for k, v in parse_frontmatter(md).items():
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            out[k] = [_unquote(x) for x in inner.split(",") if x.strip()] if inner else []
        else:
            out[k] = _unquote(v)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/models.py tests/test_models.py
git commit -m "feat(p2c): strict front-matter parser (unquote + tags list)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 2: `extract_tldr` + steer the prompt toward `## TL;DR`

**Files:**
- Create: `nbs/publish.py` (`import re`, `extract_tldr`)
- Modify: `prompts/blog.md:7` (require a `## TL;DR` 3-bullet block for confirmed posts)
- Test: `tests/test_publish.py` (new)

**Interfaces:**
- Produces: `extract_tldr(md, limit=500) -> str` — TL;DR bullets (matches `## TL;DR` or `**TL;DR**`), else first non-empty body paragraph. Non-empty whenever the body is non-empty.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_publish.py (new)
from nbs.publish import extract_tldr
_FM = "---\ntitle: T\n---\n"

def test_extract_tldr_from_heading():
    md = _FM + "리드 문장.\n\n## TL;DR\n- 첫째 요점\n- 둘째 요점\n\n## 본문\n내용\n"
    out = extract_tldr(md)
    assert "첫째 요점" in out and "둘째 요점" in out and "본문" not in out and "리드 문장" not in out

def test_extract_tldr_from_bold_marker():
    md = _FM + "**TL;DR**\n- 요점 A\n- 요점 B\n\n본문\n"
    assert "요점 A" in extract_tldr(md)

def test_extract_tldr_fallback_first_paragraph():
    md = _FM + "첫 문단이 요약을 대신한다.\n\n둘째 문단.\n"
    out = extract_tldr(md)
    assert out.startswith("첫 문단") and "둘째 문단" not in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_publish.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nbs.publish'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/publish.py (new)
import re

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
```

- [ ] **Step 4: Steer the prompt (keep parser tolerant; this only improves the common case)**

In `prompts/blog.md`, the confirmed-Blog rule (line ~7) already lists "TL;DR 3줄". Make the marker explicit so extraction is reliable — change that clause to require a literal heading:

```
- evidence_level=confirmed → 풀 Blog: 제목 / **`## TL;DR` 헤딩 아래 정확히 3개 불릿** / 본문(원문 핵심 상세 + 우리 분석) / 왜 중요한가 / (해당 시) 어떻게 써먹나 / 출처 링크.
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_publish.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add nbs/publish.py prompts/blog.md tests/test_publish.py
git commit -m "feat(p2c): extract_tldr (marker or first paragraph) + prompt steers ## TL;DR

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 3: Realign `floor_ok` to evidence count (§4 SSOT)

**Files:**
- Modify: `nbs/assemble.py:8-9` (`floor_ok`)
- Test: `tests/test_assemble.py`

**Interfaces:**
- Produces: `floor_ok(results) -> bool` — True iff `count(r.evidence_level in {"confirmed","short"}) >= FLOOR_N`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assemble.py (append)
from nbs.models import GenerationResult as _G
def _rev(k, evidence, status):
    return _G(event_key=k, title=k, url="u", source="S", source_type="article",
              evidence_level=evidence, status=status, post_path=None, slug=k, rank=1, rationale="r")

def test_floor_counts_evidence_not_generation_success():
    res = [_rev("a","confirmed","ok"), _rev("b","confirmed","failed"), _rev("c","confirmed","failed")]
    assert assemble.floor_ok(res) is True

def test_floor_fails_when_evidence_below_n():
    res = [_rev("a","confirmed","ok"), _rev("b","short","ok"), _rev("c","exclude","excluded")]
    assert assemble.floor_ok(res) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_assemble.py::test_floor_counts_evidence_not_generation_success -v`
Expected: FAIL — old `floor_ok` counts publishable (1<3) → False.

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/assemble.py — replace floor_ok
def floor_ok(results):
    # §4: floor is a mass-source-failure detector on EVIDENCE (confirmed+short), not a
    # generation-success count and not a cap. P2c additionally requires ok>=1 to publish.
    return sum(1 for r in results if r.evidence_level in ("confirmed", "short")) >= FLOOR_N
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assemble.py tests/test_stage.py -v`
Expected: PASS. (`test_floor_blocks_below_n` still holds — its `_r` items default `evidence_level="confirmed"`: 2<3 False, 3≥3 True. `test_stage_*` still pass — fixtures produce confirmed evidence.)

- [ ] **Step 5: Commit**

```bash
git add nbs/assemble.py tests/test_assemble.py
git commit -m "fix(p2c): floor_ok counts evidence (confirmed+short) per spec §4 SSOT

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 4: News index uses Hugo `relref` (subpath-safe links)

**Files:**
- Modify: `nbs/assemble.py:21-23` (link line in `build_news_index`)
- Test: `tests/test_assemble.py`

**Interfaces:** `build_news_index(results, date) -> str` unchanged signature; item link now `[{title}]({{< relref "/posts/{slug}.md" >}}) — {hook}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assemble.py (append)
def test_news_index_uses_relref_not_root_relative():
    md = assemble.build_news_index([_r("a", rank=1), _r("c", rank=2), _r("d", rank=3)], "2026-07-01")
    assert '{{< relref "/posts/2026-07-01-a.md" >}}' in md
    assert "](/posts/" not in md   # no root-relative link (404s under /ai-daily/)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_assemble.py::test_news_index_uses_relref_not_root_relative -v`
Expected: FAIL — current output has `](/posts/2026-07-01-a/)`.

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/assemble.py — in build_news_index, replace the link append
        for r in rs:
            hook = (r.rationale or "").strip() or r.title
            link = '{{< relref "/posts/%s.md" >}}' % r.slug   # subpath-safe (baseURL=/ai-daily/)
            lines.append(f"- [{r.title}]({link}) — {hook}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assemble.py -v`
Expected: PASS. (If `test_news_index_only_ok_with_hook_and_category` asserted old `/posts/<slug>/`, the slug substring still appears inside the relref path so `"2026-07-01-a" in md` still holds.)

- [ ] **Step 5: Commit**

```bash
git add nbs/assemble.py tests/test_assemble.py
git commit -m "fix(p2c): news index links via Hugo relref (root-relative 404s under /ai-daily/)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 5: Ledger date-scoped rebuild (idempotent, atomic)

**Files:**
- Modify: `nbs/ledger.py` (add `import os, tempfile`; `rewrite_date`)
- Test: `tests/test_ledger.py`

**Interfaces:** `rewrite_date(date, rows, path=None) -> None` — drop rows whose `date`==`date`, append `rows`, write via temp + `os.replace`. Other dates preserved (first). **Callers MUST pass an explicit `path` in tests** (default is the real `LEDGER_PATH`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ledger.py (append)
from nbs.ledger import rewrite_date, append_rows
import csv as _csv
def _read(p):
    with open(p, newline="", encoding="utf-8") as f: return list(_csv.DictReader(f))

def test_rewrite_date_replaces_only_that_date(tmp_path):
    p = tmp_path / "led.csv"
    append_rows([{"event_key":"old","date":"2026-06-30","title":"O"}], path=p)
    append_rows([{"event_key":"stale","date":"2026-07-01","title":"S"}], path=p)
    rewrite_date("2026-07-01", [{"event_key":"fresh","date":"2026-07-01","title":"F"}], path=p)
    keys = {r["event_key"] for r in _read(p)}
    assert keys == {"old", "fresh"}

def test_rewrite_date_is_idempotent(tmp_path):
    p = tmp_path / "led.csv"; row = [{"event_key":"a","date":"2026-07-01","title":"A"}]
    rewrite_date("2026-07-01", row, path=p); rewrite_date("2026-07-01", row, path=p)
    assert len(_read(p)) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ledger.py::test_rewrite_date_replaces_only_that_date -v`
Expected: FAIL — `ImportError: cannot import name 'rewrite_date'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/ledger.py — add: import os, tempfile   (csv already imported)
def rewrite_date(date, rows, path=None):
    # idempotent per date: drop existing rows for `date`, append `rows`, atomic replace.
    p = _p(path)
    kept = []
    if p.exists():
        with p.open(newline="", encoding="utf-8") as f:
            kept = [r for r in csv.DictReader(f) if r.get("date") != date]
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".csv")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=LEDGER_HEADER); w.writeheader()
            for r in kept + list(rows):
                w.writerow({k: r.get(k, "") for k in LEDGER_HEADER})
        os.replace(tmp, p)
    except Exception:
        os.path.exists(tmp) and os.remove(tmp); raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_ledger.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/ledger.py tests/test_ledger.py
git commit -m "feat(p2c): ledger.rewrite_date — idempotent date-scoped atomic rebuild

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 6: Publish gate — evidence-floor AND ok≥1

**Files:**
- Modify: `nbs/publish.py` (`from . import assemble`; `_ok`, `_evidence`, `decide`)
- Test: `tests/test_publish.py`

**Interfaces:** `decide(gen) -> (decision, reason)`, `decision ∈ {"publish","held"}`. `held` when evidence < FLOOR_N (source failure) or ok_count == 0 (generation collapse).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_publish.py (append)
from nbs.publish import decide
def _gen(results, date="2026-07-01"): return {"date": date, "status": "ok", "results": results}
def _res(ek, evidence, status):
    s=f"2026-07-01-{ek}"
    return {"event_key": ek, "evidence_level": evidence, "status": status, "slug": s,
            "url": f"https://x/{ek}", "post_path": f"posts/{s}.md", "title": "T", "source": "S"}

def test_decide_publish_when_evidence_and_ok():
    assert decide(_gen([_res("a","confirmed","ok"), _res("b","confirmed","ok"), _res("c","short","ok")]))[0] == "publish"

def test_decide_held_when_evidence_below_floor():
    assert decide(_gen([_res("a","confirmed","ok"), _res("b","exclude","excluded"), _res("c","exclude","excluded")]))[0] == "held"

def test_decide_held_when_all_generation_failed():
    d, reason = decide(_gen([_res("a","confirmed","failed"), _res("b","confirmed","failed"), _res("c","confirmed","failed")]))
    assert d == "held" and "generation" in reason.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_publish.py::test_decide_publish_when_evidence_and_ok -v`
Expected: FAIL — `cannot import name 'decide'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/publish.py — add
from . import assemble

def _ok(gen):       return [r for r in gen.get("results", []) if r.get("status") == "ok"]
def _evidence(gen): return [r for r in gen.get("results", []) if r.get("evidence_level") in ("confirmed", "short")]

def decide(gen):
    if len(_evidence(gen)) < assemble.FLOOR_N:
        return "held", f"evidence floor not met ({len(_evidence(gen))} < {assemble.FLOOR_N}) — suspected mass source failure"
    if len(_ok(gen)) == 0:
        return "held", "generation produced 0 publishable posts (empty-day guard)"
    return "publish", "ok"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_publish.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/publish.py tests/test_publish.py
git commit -m "feat(p2c): publish gate — evidence-floor AND ok>=1 (empty-day guard)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 7: Strengthened completeness check (run on STAGING, before promote)

**Files:**
- Modify: `nbs/publish.py` (`check_completeness`)
- Test: `tests/test_publish.py`

**Interfaces:** `check_completeness(gen, staging: Path) -> list[str]` (empty=pass). Per ok result: exactly one `staging/posts/<slug>.md`; `post_path==f"posts/{slug}.md"`; front matter `event_key`/`source_url`(=url)/`date`(=gen date)/`evidence_level` match; **`tags` is a non-empty list**; **body non-empty** (`validate_blog_output` passes); slug/event_key/canonical_url unique; news links == ok slug set. Runs on staging so a missing file is caught **before** any copy.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_publish.py (append)
from pathlib import Path
from nbs.publish import check_completeness

def _write_post(staging, slug, ek, url, date="2026-07-01", ev="confirmed", tags="[ai]", body="## TL;DR\n- x\n본문\n"):
    (staging/"posts").mkdir(parents=True, exist_ok=True)
    (staging/"posts"/f"{slug}.md").write_text(
        f"---\ntitle: T\ndate: {date}\ntags: {tags}\nsource_url: {url}\n"
        f"source_lang: en\nsource_type: article\nevidence_level: {ev}\nevent_key: {ek}\n---\n{body}",
        encoding="utf-8")

def _write_news(staging, slugs, date="2026-07-01"):
    (staging/"news").mkdir(parents=True, exist_ok=True)
    links = "\n".join('- [T]({{< relref "/posts/%s.md" >}}) — h' % s for s in slugs)
    (staging/"news"/f"{date}.md").write_text(f"---\ntitle: N\n---\n{links}\n", encoding="utf-8")

def _okres(ek):
    s=f"2026-07-01-{ek}"
    return {"event_key":ek,"evidence_level":"confirmed","status":"ok","slug":s,
            "url":f"https://x/{ek}","post_path":f"posts/{s}.md","title":"T","source":"S"}

def test_completeness_passes_on_matching_set(tmp_path):
    staging=tmp_path/"staging"; gen={"date":"2026-07-01","results":[_okres("a"),_okres("b")]}
    for r in gen["results"]: _write_post(staging, r["slug"], r["event_key"], r["url"])
    _write_news(staging, [r["slug"] for r in gen["results"]])
    assert check_completeness(gen, staging) == []

def test_completeness_flags_missing_post_file(tmp_path):
    staging=tmp_path/"staging"; gen={"date":"2026-07-01","results":[_okres("a"),_okres("b")]}
    _write_post(staging,"2026-07-01-a","a","https://x/a"); _write_news(staging,["2026-07-01-a","2026-07-01-b"])
    assert any("2026-07-01-b" in e for e in check_completeness(gen, staging))

def test_completeness_flags_frontmatter_mismatch(tmp_path):
    staging=tmp_path/"staging"; gen={"date":"2026-07-01","results":[_okres("a"),_okres("b"),_okres("c")]}
    _write_post(staging,"2026-07-01-a","WRONG","https://x/a")
    _write_post(staging,"2026-07-01-b","b","https://x/b"); _write_post(staging,"2026-07-01-c","c","https://x/c")
    _write_news(staging,["2026-07-01-a","2026-07-01-b","2026-07-01-c"])
    assert any("event_key" in e for e in check_completeness(gen, staging))

def test_completeness_flags_scalar_or_empty_tags(tmp_path):
    staging=tmp_path/"staging"; gen={"date":"2026-07-01","results":[_okres("a"),_okres("b"),_okres("c")]}
    _write_post(staging,"2026-07-01-a","a","https://x/a", tags="ai")     # scalar, not a list
    _write_post(staging,"2026-07-01-b","b","https://x/b", tags="[]")     # empty list
    _write_post(staging,"2026-07-01-c","c","https://x/c")
    _write_news(staging,["2026-07-01-a","2026-07-01-b","2026-07-01-c"])
    errs = check_completeness(gen, staging)
    assert any("2026-07-01-a" in e and "tags" in e for e in errs)
    assert any("2026-07-01-b" in e and "tags" in e for e in errs)

def test_completeness_flags_empty_body(tmp_path):
    staging=tmp_path/"staging"; gen={"date":"2026-07-01","results":[_okres("a"),_okres("b"),_okres("c")]}
    _write_post(staging,"2026-07-01-a","a","https://x/a", body="")       # empty body
    _write_post(staging,"2026-07-01-b","b","https://x/b"); _write_post(staging,"2026-07-01-c","c","https://x/c")
    _write_news(staging,["2026-07-01-a","2026-07-01-b","2026-07-01-c"])
    assert any("2026-07-01-a" in e and "body" in e.lower() for e in check_completeness(gen, staging))

def test_completeness_flags_news_link_mismatch(tmp_path):
    staging=tmp_path/"staging"; gen={"date":"2026-07-01","results":[_okres("a"),_okres("b")]}
    for r in gen["results"]: _write_post(staging, r["slug"], r["event_key"], r["url"])
    _write_news(staging,["2026-07-01-a"])
    assert any("news" in e.lower() for e in check_completeness(gen, staging))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_publish.py::test_completeness_passes_on_matching_set -v`
Expected: FAIL — `cannot import name 'check_completeness'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/publish.py — add
from .models import parse_frontmatter_strict, canonicalize_url, validate_blog_output
_RELREF = re.compile(r'relref\s+"/posts/([^"]+?)\.md"')

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
```

Note: `validate_blog_output` already requires `evidence_level in {confirmed,short}` and non-empty body; the explicit body check is belt-and-suspenders for a corrupted staged file.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_publish.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/publish.py tests/test_publish.py
git commit -m "feat(p2c): completeness check (1:1, front matter, tags-list, body, unique, news==ok)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 8: Date-scoped write-set, preflight, promote (with stale delete), rollback

**Files:**
- Modify: `nbs/publish.py` (`subprocess`, `shutil`, `from .config import ROOT, run_dir`; `_git`, `_head_has`, `date_writeset`, `preflight_clean`, `promote`, `rollback`)
- Test: `tests/test_publish.py`

**Interfaces:**
- `date_writeset(gen) -> list[str]` — repo-relative, date-scoped: **existing** `content/posts/<date>-*.md` (glob) ∪ target ok post paths, `content/news/<date>.md`, `content/usecase/<date>.md`, `data/published.csv`. (Includes stale same-date posts so preflight/rollback/commit see deletions.)
- `_head_has(rel) -> bool` — path exists in `HEAD`.
- `preflight_clean(paths) -> list[str]` — write-set paths that are git-dirty (empty=clean).
- `promote(gen, staging) -> list[str]` — delete stale `content/posts/<date>-*.md` not in ok slugs; copy staging posts/news/(usecase if present) into `content/`; return touched repo-rel paths (created/modified/deleted).
- `rollback(paths)` — for each: if in HEAD → `git restore --staged --worktree --source=HEAD -- path`; else unstage + delete file.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_publish.py (append)
import subprocess
from nbs import publish, config

def _git_in(args, cwd): return subprocess.run(["git"]+args, cwd=str(cwd), capture_output=True, text=True)

def _init_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(publish, "ROOT", tmp_path)
    monkeypatch.setattr(publish, "run_dir", lambda date: tmp_path/"runs"/date)
    _git_in(["init","-q"], tmp_path); _git_in(["config","user.email","t@t"], tmp_path); _git_in(["config","user.name","t"], tmp_path)
    for d in ("posts","news","usecase"): (tmp_path/"content"/d).mkdir(parents=True)
    (tmp_path/"data").mkdir()
    (tmp_path/"content"/".keep").write_text("x")
    _git_in(["add","-A"], tmp_path); _git_in(["commit","-qm","init"], tmp_path)
    return tmp_path

def _gen2(date="2026-07-01"): return {"date":date, "results":[_okres("a"), _okres("b")]}

def _stage_posts(root, gen):
    staging=root/"runs"/gen["date"]/"staging"
    for r in gen["results"]: _write_post(staging, r["slug"], r["event_key"], r["url"], date=gen["date"])
    _write_news(staging, [r["slug"] for r in gen["results"]], date=gen["date"])
    (staging/"usecase").mkdir(parents=True, exist_ok=True)
    (staging/"usecase"/f"{gen['date']}.md").write_text("---\ntitle: U\n---\nu\n", encoding="utf-8")
    return staging

def test_promote_copies_and_deletes_stale(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    # a stale same-date post from a previous run, committed
    (root/"content"/"posts"/"2026-07-01-old.md").write_text("---\ntitle: O\n---\nx\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm","stale"], root)
    gen=_gen2(); staging=_stage_posts(root, gen)
    touched = publish.promote(gen, staging)
    assert (root/"content"/"posts"/"2026-07-01-a.md").exists()
    assert not (root/"content"/"posts"/"2026-07-01-old.md").exists()   # stale deleted
    assert (root/"content"/"news"/"2026-07-01.md").exists() and (root/"content"/"usecase"/"2026-07-01.md").exists()

def test_preflight_detects_dirty_writeset(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    (root/"data"/"published.csv").write_text("dirty\n", encoding="utf-8")
    assert "data/published.csv" in publish.preflight_clean(["data/published.csv"])

def test_rollback_restores_and_deletes(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    (root/"content"/"posts"/"2026-07-01-old.md").write_text("orig\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm","base"], root)
    # simulate a partial promote: overwrite tracked + create untracked, stage them
    (root/"content"/"posts"/"2026-07-01-old.md").write_text("CHANGED\n", encoding="utf-8")
    (root/"content"/"posts"/"2026-07-01-new.md").write_text("NEW\n", encoding="utf-8")
    _git_in(["add","-A"], root)
    publish.rollback(["content/posts/2026-07-01-old.md", "content/posts/2026-07-01-new.md"])
    assert (root/"content"/"posts"/"2026-07-01-old.md").read_text() == "orig\n"   # restored to HEAD
    assert not (root/"content"/"posts"/"2026-07-01-new.md").exists()              # untracked removed
    assert _git_in(["status","--porcelain"], root).stdout.strip() == ""           # index clean
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_publish.py::test_promote_copies_and_deletes_stale -v`
Expected: FAIL — `module 'nbs.publish' has no attribute 'promote'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/publish.py — add
import subprocess, shutil
from pathlib import Path
from .config import ROOT, run_dir

def _git(args): return subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True)
def _head_has(rel): return _git(["cat-file", "-e", f"HEAD:{rel}"]).returncode == 0

def date_writeset(gen):
    date = gen["date"]
    posts = {str(p.relative_to(ROOT)) for p in (ROOT/"content"/"posts").glob(f"{date}-*.md")}
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
    if uc.exists():
        _cp(uc, ROOT/"content"/"usecase"/f"{date}.md")
    return touched

def rollback(paths):
    for rel in paths:
        if _head_has(rel):
            _git(["restore", "--staged", "--worktree", "--source=HEAD", "--", rel])
        else:
            _git(["reset", "-q", "--", rel])          # unstage if staged (no-op otherwise)
            p = ROOT / rel
            if p.exists(): p.unlink()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_publish.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/publish.py tests/test_publish.py
git commit -m "feat(p2c): date-scoped write-set + preflight + promote(stale-delete) + git-restore rollback

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 9: Hugo build-verify (post/news/usecase rendered + subpath hrefs)

**Files:**
- Modify: `nbs/publish.py` (`tempfile`; `_hugo_build`, `build_verify`)
- Test: `tests/test_publish.py`

**Interfaces:** `build_verify(gen) -> list[str]` (empty=pass). Runs `hugo --quiet -d <tmp>` (no pipe), asserts exit 0, then: each ok post → `<tmp>/posts/<slug>/index.html`; day news → `<tmp>/news/<date>/index.html` with a `/ai-daily/posts/<slug>/` href per ok slug; **if `content/usecase/<date>.md` exists → `<tmp>/usecase/<date>/index.html`**. `_hugo_build(outdir)->int` is the seam tests stub.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_publish.py (append)
def _render(outdir, date, slugs, usecase=False):
    for s in slugs:
        (Path(outdir)/"posts"/s).mkdir(parents=True); (Path(outdir)/"posts"/s/"index.html").write_text("x")
    (Path(outdir)/"news"/date).mkdir(parents=True)
    (Path(outdir)/"news"/date/"index.html").write_text("".join(f'<a href="/ai-daily/posts/{s}/">x</a>' for s in slugs))
    if usecase:
        (Path(outdir)/"usecase"/date).mkdir(parents=True); (Path(outdir)/"usecase"/date/"index.html").write_text("u")
    return 0

def test_build_verify_flags_missing_rendered_post(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a"]))  # b missing
    assert any("2026-07-01-b" in e for e in publish.build_verify(gen))

def test_build_verify_flags_missing_usecase_when_present(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    (root/"content"/"usecase"/"2026-07-01.md").write_text("---\ntitle: U\n---\nu\n", encoding="utf-8")
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a","2026-07-01-b"], usecase=False))
    assert any("usecase" in e.lower() for e in publish.build_verify(gen))

def test_build_verify_passes_when_all_rendered(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    (root/"content"/"usecase"/"2026-07-01.md").write_text("---\ntitle: U\n---\nu\n", encoding="utf-8")
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a","2026-07-01-b"], usecase=True))
    assert publish.build_verify(gen) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_publish.py::test_build_verify_passes_when_all_rendered -v`
Expected: FAIL — `module 'nbs.publish' has no attribute 'build_verify'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/publish.py — add
import tempfile

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_publish.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/publish.py tests/test_publish.py
git commit -m "feat(p2c): hugo build-verify (post/news/usecase rendered + subpath hrefs)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 10: Build ledger rows (fail on empty summary)

**Files:**
- Modify: `nbs/publish.py` (`ledger_rows`)
- Test: `tests/test_publish.py`

**Interfaces:** `ledger_rows(gen) -> list[dict]` — one dict per ok result keyed by `LEDGER_HEADER`: `canonical_key=canonicalize_url(url)`, `event_key/date/title/url/source/post_path` from result, `summary=extract_tldr(post md)` (raise `ValueError` if empty), `tags=",".join(front-matter tags list)`, `entities=""`, `confidence=""`. Reads promoted `content/posts/<slug>.md`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_publish.py (append)
import pytest
def test_ledger_rows_fields(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    (root/"content"/"posts"/"2026-07-01-a.md").write_text(
        "---\ntitle: A\ndate: 2026-07-01\ntags: [ai, model]\nsource_url: https://x/a\n"
        "source_lang: en\nsource_type: article\nevidence_level: confirmed\nevent_key: a\n---\n## TL;DR\n- 요약 문장\n본문\n", encoding="utf-8")
    (root/"content"/"posts"/"2026-07-01-b.md").write_text(
        "---\ntitle: B\ndate: 2026-07-01\ntags: [x]\nsource_url: https://x/b\n"
        "source_lang: en\nsource_type: article\nevidence_level: confirmed\nevent_key: b\n---\n첫 문단.\n", encoding="utf-8")
    gen["results"][0]["title"]="A"; gen["results"][0]["source"]="OpenAI"
    rows = publish.ledger_rows(gen)
    ra = next(r for r in rows if r["event_key"]=="a")
    assert ra["canonical_key"]=="https://x/a" and "요약 문장" in ra["summary"] and ra["tags"]=="ai,model"
    assert ra["post_path"]=="posts/2026-07-01-a.md"
    assert next(r for r in rows if r["event_key"]=="b")["summary"].startswith("첫 문단")

def test_ledger_rows_raises_on_empty_summary(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen={"date":"2026-07-01","results":[_okres("a")]}
    (root/"content"/"posts"/"2026-07-01-a.md").write_text("---\ntitle: A\n---\n\n", encoding="utf-8")  # empty body
    with pytest.raises(ValueError):
        publish.ledger_rows(gen)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_publish.py::test_ledger_rows_fields -v`
Expected: FAIL — `module 'nbs.publish' has no attribute 'ledger_rows'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/publish.py — add
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_publish.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/publish.py tests/test_publish.py
git commit -m "feat(p2c): ledger_rows — canonical_key + TL;DR summary (fail if empty) + tags

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 11: Orchestration — `run()` (completeness→promote→verify→ledger→commit) + manifest

**Files:**
- Modify: `nbs/publish.py` (`argparse`, `json`, `from . import ledger as ledger_mod`; `_write_manifest`, `_degraded`, `_commit_msg`, `run`, `main`, `__main__`)
- Test: `tests/test_publish.py`

**Interfaces:** `run(date, *, do_commit=True) -> dict` (the manifest, also written to `runs/<date>/publish.json`). Order: load gen → `decide` (held→manifest, no writes) → git identity + write-set-clean + **index-clean** preflight (fail→manifest) → **`check_completeness(staging)` before any copy** (fail→manifest, nothing to roll back) → `try:` promote → build_verify → `rewrite_date(path=ROOT/data/published.csv)` → `git add -A -- <date_writeset>` → verify staged names ⊆ write-set → `git diff --cached --quiet` ? no-op success : commit → sha; `except:` rollback(date_writeset) + failed manifest. Manifest: `{date, status(published|held|failed), reason, promoted[], degraded{...}, commit_sha, error}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_publish.py (append)
import json
def _stage_full(root, gen):
    d=root/"runs"/gen["date"]; _stage_posts(root, gen)
    (d/"generation.json").write_text(json.dumps(gen), encoding="utf-8"); return d

def test_run_held_when_evidence_low(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    gen={"date":"2026-07-01","results":[_res("a","confirmed","ok"), _res("b","exclude","excluded"), _res("c","exclude","excluded")]}
    _stage_full(root, gen)
    m=publish.run("2026-07-01")
    assert m["status"]=="held" and not (root/"content"/"news"/"2026-07-01.md").exists()
    assert (root/"runs"/"2026-07-01"/"publish.json").exists()

def test_run_publishes_and_writes_ledger_and_manifest(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a","2026-07-01-b","2026-07-01-c"], usecase=True))
    gen={"date":"2026-07-01","results":[_okres("a"),_okres("b"),_okres("c")]}
    _stage_full(root, gen)
    m=publish.run("2026-07-01")
    assert m["status"]=="published" and m["commit_sha"]
    assert (root/"content"/"news"/"2026-07-01.md").exists()
    led=(root/"data"/"published.csv").read_text(encoding="utf-8")
    assert "2026-07-01-a" in led and led.count("2026-07-01-a")==1
    # idempotent rerun -> still published, still one row
    m2=publish.run("2026-07-01")
    assert m2["status"]=="published"
    assert (root/"data"/"published.csv").read_text(encoding="utf-8").count("2026-07-01-a")==1

def test_run_degraded_publishes_without_usecase(tmp_path, monkeypatch):
    # §15: usecase optional — usecase_error set, no staging usecase file -> still publishes
    root=_init_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a","2026-07-01-b","2026-07-01-c"], usecase=False))
    gen={"date":"2026-07-01","results":[_okres("a"),_okres("b"),_okres("c")], "usecase_error":"boom"}
    d=root/"runs"/gen["date"]; staging=d/"staging"
    for r in gen["results"]: _write_post(staging, r["slug"], r["event_key"], r["url"])
    _write_news(staging, [r["slug"] for r in gen["results"]])       # NO usecase file
    (d/"generation.json").write_text(json.dumps(gen), encoding="utf-8")
    m=publish.run("2026-07-01")
    assert m["status"]=="published" and m["degraded"].get("usecase")
    assert not (root/"content"/"usecase"/"2026-07-01.md").exists()
    assert (root/"content"/"news"/"2026-07-01.md").exists()

def test_run_rolls_back_on_build_failure(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(publish, "_hugo_build", lambda o: 1)         # build fails
    gen={"date":"2026-07-01","results":[_okres("a"),_okres("b"),_okres("c")]}
    _stage_full(root, gen)
    m=publish.run("2026-07-01")
    assert m["status"]=="failed"
    assert not (root/"content"/"posts"/"2026-07-01-a.md").exists()   # rolled back
    assert _git_in(["status","--porcelain"], root).stdout.strip()==""  # clean tree/ledger
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_publish.py::test_run_held_when_evidence_low -v`
Expected: FAIL — `module 'nbs.publish' has no attribute 'run'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/publish.py — add
import argparse, json
from . import ledger as ledger_mod

def _write_manifest(date, payload):
    (run_dir(date)/"publish.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

def _degraded(gen):
    ok, ev = len(_ok(gen)), len(_evidence(gen)); d = {}
    if gen.get("usecase_error"): d["usecase"] = gen["usecase_error"]
    if ok < ev or ok < assemble.FLOOR_N: d["generation_failed_count"] = ev - ok
    return d

def _commit_msg(date, gen):
    return (f"publish(ai-daily): {date} — {len(_ok(gen))} posts"
            "\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
            "\nClaude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4")

def _fail(date, gen, reason, error=None):
    return _write_manifest(date, {"date": date, "status": "failed", "reason": reason,
                                  "promoted": [], "degraded": _degraded(gen), "commit_sha": None, "error": error or reason})

def run(date, *, do_commit=True):
    d = run_dir(date)
    gen = json.loads((d/"generation.json").read_text(encoding="utf-8"))
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
            if _git(["add", "-A", "--"] + ws).returncode != 0:
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
```

Note: rollback receives the full `ws` (date write-set incl. `data/published.csv`), so a build/commit failure restores content **and** ledger to HEAD — no desync, next run's preflight stays clean.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_publish.py -v`
Expected: PASS (held, published, idempotent rerun, degraded-no-usecase, rollback-on-build-failure)

- [ ] **Step 5: Commit**

```bash
git add nbs/publish.py tests/test_publish.py
git commit -m "feat(p2c): publish orchestration — completeness->promote->verify->ledger->commit + manifest

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 12: Full-suite regression + real publish smoke + docs

**Files:**
- Create: `scripts/p2c_smoke.sh`
- Modify: `docs/superpowers/HANDOFF.md` (P2c status)
- Test: full `pytest`

- [ ] **Step 1: Full-suite regression**

Run: `python3 -m pytest -q`
Expected: PASS (P2b 80 + new P2c tests). Confirm no P2b test still assumes old `floor_ok` (publishable) or root-relative news links — Tasks 3/4 updated them.

- [ ] **Step 2: Write the real smoke script** (regenerate staging first — post-Task-4 staging must use relref; a `--no-commit` dry run)

```bash
# scripts/p2c_smoke.sh
#!/usr/bin/env bash
# P2c real smoke: regenerate staging (so news uses relref), then promote into content/
# WITHOUT committing, then show the manifest. Leaves a dirty tree for inspection;
# clean up with the date-scoped commands printed at the end.
set -euo pipefail
DATE="${1:?usage: p2c_smoke.sh <date>}"
export PATH="$HOME/.local/bin:$PATH"
python3 -m nbs.stage --date "$DATE"                 # fresh staging (relref links)
python3 -m nbs.publish --date "$DATE" --no-commit
echo "--- publish.json ---"; cat "runs/$DATE/publish.json"
echo "--- content added ---"; ls -1 content/posts/ | grep "$DATE" || true
ls -1 "content/news/$DATE.md" "content/usecase/$DATE.md" 2>/dev/null || true
echo "--- cleanup (date-scoped) ---"
echo "git checkout -- content/news/$DATE.md 2>/dev/null; git clean -f -- content/posts/$DATE-*.md content/news/$DATE.md content/usecase/$DATE.md data/published.csv; git checkout -- data/published.csv 2>/dev/null || true"
```

- [ ] **Step 3: Run the real smoke (Claude Code env — `claude -p` needs it; regenerating staging calls it)**

```bash
export PATH="$HOME/.local/bin:$PATH"
chmod +x scripts/p2c_smoke.sh
bash scripts/p2c_smoke.sh 2026-07-02
```
Expected: `publish.json` `status=published`, `content/posts/2026-07-02-*.md` present, `content/news/2026-07-02.md` present, `data/published.csv` has the day's rows with non-empty summaries. Then run the printed cleanup so the working tree is clean before commit.

- [ ] **Step 4: Update HANDOFF** — set P2c row to DONE-pending-merge, note real-smoke evidence, list deferred minors (unanchored `---` in `parse_frontmatter`, entities/confidence empty).

- [ ] **Step 5: Commit**

```bash
git add scripts/p2c_smoke.sh docs/superpowers/HANDOFF.md
git commit -m "test(p2c): real publish smoke (regen staging + dry promote) + HANDOFF update

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

## Notes / deferred (carry to review)

- `parse_frontmatter` unanchored `---` split stays a documented defer-safe minor; `parse_frontmatter_strict` inherits it (our posts never put `---` in a value).
- `entities` / `confidence` ledger fields intentionally empty (YAGNI; `ledger_digest` ignores them).
- Real smoke covers article-only days (matches P2b coverage note). paper/sns/video promotion via unit tests only.
- Push / live deploy / email / unattended schedule = P3 (out of scope).
- Rollback assumes git ≥2.23 (`git restore`). Atomicity guarantee: on any promote/verify/commit failure, `rollback(date_writeset)` restores content **and** `data/published.csv` to HEAD (tracked → `git restore --source=HEAD`; untracked-new → delete), leaving a clean tree for the next run's preflight.
