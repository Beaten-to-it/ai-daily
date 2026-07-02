# P2c — Promote & Publish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote a day's `runs/<date>/staging/` output into `content/`, verify it builds, append the ledger, and record it in one local git commit — atomically, idempotently, and with no push.

**Architecture:** New orchestrator `nbs/publish.py` reads the P2b `generation.json` contract, applies two publish gates (evidence-floor AND ok≥1), runs a strengthened completeness check, copies staging→content, verifies a throwaway Hugo build (rendered files + subpath hrefs), rebuilds the ledger for the date, and makes a single local commit — with a date-scoped rollback on any pre-commit failure. Small fixes land in existing modules (`assemble.floor_ok`, `assemble.build_news_index`, `models` strict front-matter parser, `ledger` date-rebuild).

**Tech Stack:** Python 3 (stdlib only — no new deps), Hugo 0.163.3 extended, git, pytest.

## Global Constraints

- `python3` only (no bare `python`); pip needs `--break-system-packages` (not needed here — stdlib only).
- **stdlib only** — no PyYAML or other new dependency (§ project rule).
- P2c writes to `content/{posts,news,usecase}/` and `data/published.csv`; it **does NOT push** (deploy = manual/P3).
- Hugo `baseURL = "https://beaten-to-it.github.io/ai-daily/"` (subpath `/ai-daily/`) — internal links MUST use `{{< relref "/posts/<slug>.md" >}}`, never root-relative `/posts/...`.
- FLOOR_N = 3 (evidence floor; not a cap).
- Build/verify commands are never wrapped in a pipe (exit code must survive — `set -o pipefail` if a pipe is unavoidable).
- Every commit message ends with the Co-Authored-By + Claude-Session trailer used across this repo.
- TDD: failing test first, minimal impl, commit per task.

**Contract consumed (P2b → P2c), from spec §6b:**
- `runs/<date>/generation.json` = `{date, status, results[], published_count, floor_failed, usecase_error}`.
- `results[]` item (GenerationResult.to_dict): `{event_key, title, url, source, source_type, evidence_level(confirmed|short|exclude), status(ok|failed|excluded), post_path, slug, rank, rationale, error}`.
- `runs/<date>/staging/posts/<slug>.md` (status ok items; slug = `<date>-<event_key>`), `staging/news/<date>.md` (floor pass), `staging/usecase/<date>.md` (floor pass + usecase ok).
- Blog front matter keys: `title, date, tags, source_url, source_lang, source_type, evidence_level, event_key`.

---

### Task 1: Strict front-matter parser (unquote scalars + tags-as-list)

**Files:**
- Modify: `nbs/models.py` (add `parse_frontmatter_strict`, `_unquote` after `parse_frontmatter`, ~line 95)
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: existing `parse_frontmatter(md) -> dict` (block extraction + line split).
- Produces: `parse_frontmatter_strict(md) -> dict` — scalar values unquoted; a `key: [a, b]` value becomes a `list[str]`; `key: []` becomes `[]`.

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
# nbs/models.py — add after parse_frontmatter (~line 95)
def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s

def parse_frontmatter_strict(md) -> dict:
    # like parse_frontmatter but unquotes scalars and parses `key: [a, b]` as a list.
    # ponytail: intentionally NOT full YAML (stdlib-only rule); covers our own emitted
    # front matter. The unanchored `---` split inherited from parse_frontmatter stays a
    # documented defer-safe minor (a `---` inside a value mis-splits; our posts don't).
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
Expected: PASS (all model tests green)

- [ ] **Step 5: Commit**

```bash
git add nbs/models.py tests/test_models.py
git commit -m "feat(p2c): strict front-matter parser (unquote + tags list)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 2: `extract_tldr` — ledger summary from blog body (robust, never empty)

**Files:**
- Create: `nbs/publish.py` (new module; add `import re` + `extract_tldr`)
- Test: `tests/test_publish.py` (new)

**Interfaces:**
- Produces: `extract_tldr(md, limit=500) -> str` — the TL;DR bullets (matches `## TL;DR` or `**TL;DR**`), else the first non-empty body paragraph. Non-empty whenever the body is non-empty.

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

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_publish.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/publish.py tests/test_publish.py
git commit -m "feat(p2c): extract_tldr — robust ledger summary (marker or first paragraph)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 3: Realign `floor_ok` to evidence count (§4 SSOT)

**Files:**
- Modify: `nbs/assemble.py:8-9` (`floor_ok`)
- Test: `tests/test_assemble.py`

**Interfaces:**
- Produces: `floor_ok(results) -> bool` — True iff `count(r.evidence_level in {"confirmed","short"}) >= FLOOR_N`. (Was: `len(publishable) >= FLOOR_N`.)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assemble.py (append)
from nbs.models import GenerationResult as _G
def _rev(k, evidence, status):
    return _G(event_key=k, title=k, url="u", source="S", source_type="article",
              evidence_level=evidence, status=status, post_path=None, slug=k, rank=1, rationale="r")

def test_floor_counts_evidence_not_generation_success():
    # 3 confirmed evidence, but only 1 generated ok -> floor passes on evidence
    res = [_rev("a","confirmed","ok"), _rev("b","confirmed","failed"), _rev("c","confirmed","failed")]
    assert assemble.floor_ok(res) is True

def test_floor_fails_when_evidence_below_n():
    # 2 usable + 1 excluded evidence -> floor fails (mass source failure)
    res = [_rev("a","confirmed","ok"), _rev("b","short","ok"), _rev("c","exclude","excluded")]
    assert assemble.floor_ok(res) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_assemble.py::test_floor_counts_evidence_not_generation_success -v`
Expected: FAIL — old `floor_ok` counts publishable (status ok) = 1 < 3 → returns False, test wants True.

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
Expected: PASS. (Existing `test_floor_blocks_below_n` still holds: its `_r` items default `evidence_level="confirmed"`, so 2<3 False, 3>=3 True. `test_stage_*` still pass: `_fake_fetch`/`_gen_respecting_exclude` produce confirmed evidence, so a 3-item day still passes floor and a 2-item day still fails.)

- [ ] **Step 5: Commit**

```bash
git add nbs/assemble.py tests/test_assemble.py
git commit -m "fix(p2c): floor_ok counts evidence (confirmed+short), per spec §4 SSOT

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 4: News index uses Hugo `relref` (subpath-safe links)

**Files:**
- Modify: `nbs/assemble.py:21-23` (link line in `build_news_index`)
- Test: `tests/test_assemble.py`

**Interfaces:**
- Produces: `build_news_index(results, date) -> str` unchanged signature; each item link is now `[{title}]({{< relref "/posts/{slug}.md" >}}) — {hook}`.

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
# nbs/assemble.py — in build_news_index, replace the link append line
        for r in rs:
            hook = (r.rationale or "").strip() or r.title
            link = '{{< relref "/posts/%s.md" >}}' % r.slug   # subpath-safe (baseURL=/ai-daily/)
            lines.append(f"- [{r.title}]({link}) — {hook}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assemble.py -v`
Expected: PASS. (Update `test_news_index_only_ok_with_hook_and_category` if it asserted the old `/posts/<slug>/` form — the slug substring `2026-07-01-a` still appears inside the relref path, so its existing assertion `"2026-07-01-a" in md` still holds.)

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
- Modify: `nbs/ledger.py` (add `rewrite_date`; add `import os, tempfile`)
- Test: `tests/test_ledger.py`

**Interfaces:**
- Consumes: `LEDGER_HEADER`, `_p(path)`.
- Produces: `rewrite_date(date, rows, path=None) -> None` — reads the ledger, drops rows whose `date` == `date`, appends `rows`, writes via temp file + `os.replace` (atomic). Other dates' rows preserved and ordered first.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ledger.py (append)
from nbs.ledger import rewrite_date, append_rows
import csv as _csv

def _read(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(_csv.DictReader(f))

def test_rewrite_date_replaces_only_that_date(tmp_path):
    p = tmp_path / "led.csv"
    append_rows([{"event_key":"old","date":"2026-06-30","title":"O"}], path=p)
    append_rows([{"event_key":"stale","date":"2026-07-01","title":"S"}], path=p)
    rewrite_date("2026-07-01", [{"event_key":"fresh","date":"2026-07-01","title":"F"}], path=p)
    rows = _read(p)
    keys = {r["event_key"] for r in rows}
    assert keys == {"old", "fresh"}          # 2026-06-30 kept, 2026-07-01 replaced
    assert sum(1 for r in rows if r["date"] == "2026-07-01") == 1

def test_rewrite_date_is_idempotent(tmp_path):
    p = tmp_path / "led.csv"
    row = [{"event_key":"a","date":"2026-07-01","title":"A"}]
    rewrite_date("2026-07-01", row, path=p)
    rewrite_date("2026-07-01", row, path=p)
    assert len(_read(p)) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ledger.py::test_rewrite_date_replaces_only_that_date -v`
Expected: FAIL — `ImportError: cannot import name 'rewrite_date'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/ledger.py — add near top: import os, tempfile   (csv already imported)
def rewrite_date(date, rows, path=None):
    # idempotent per date: drop existing rows for `date`, append `rows`, atomic replace.
    # Keeps other dates intact so content/ and ledger never desync on rerun.
    p = _p(path)
    kept = []
    if p.exists():
        with p.open(newline="", encoding="utf-8") as f:
            kept = [r for r in csv.DictReader(f) if r.get("date") != date]
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".csv")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=LEDGER_HEADER)
            w.writeheader()
            for r in kept + list(rows):
                w.writerow({k: r.get(k, "") for k in LEDGER_HEADER})
        os.replace(tmp, p)
    except Exception:
        os.path.exists(tmp) and os.remove(tmp)
        raise
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
- Modify: `nbs/publish.py` (add `decide(gen) -> (str, str)`)
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: generation.json dict (`results[]` with `evidence_level`, `status`), `assemble.FLOOR_N`.
- Produces: `decide(gen) -> (decision, reason)` where `decision ∈ {"publish","held"}`. `held` when evidence < FLOOR_N (source failure) or ok_count == 0 (generation collapse); reason is a short human string.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_publish.py (append)
from nbs.publish import decide

def _gen(results, date="2026-07-01"):
    return {"date": date, "status": "ok", "results": results}
def _res(ek, evidence, status):
    return {"event_key": ek, "evidence_level": evidence, "status": status,
            "slug": f"2026-07-01-{ek}", "url": f"https://x/{ek}", "post_path": f"posts/2026-07-01-{ek}.md"}

def test_decide_publish_when_evidence_and_ok():
    g = _gen([_res("a","confirmed","ok"), _res("b","confirmed","ok"), _res("c","short","ok")])
    assert decide(g)[0] == "publish"

def test_decide_held_when_evidence_below_floor():
    g = _gen([_res("a","confirmed","ok"), _res("b","exclude","excluded"), _res("c","exclude","excluded")])
    assert decide(g)[0] == "held"

def test_decide_held_when_all_generation_failed():
    # evidence fine (3 confirmed) but 0 ok -> empty-day guard
    g = _gen([_res("a","confirmed","failed"), _res("b","confirmed","failed"), _res("c","confirmed","failed")])
    d, reason = decide(g)
    assert d == "held" and "generation" in reason.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_publish.py::test_decide_publish_when_evidence_and_ok -v`
Expected: FAIL — `cannot import name 'decide'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/publish.py — add
from . import assemble

def _ok(gen):        return [r for r in gen.get("results", []) if r.get("status") == "ok"]
def _evidence(gen):  return [r for r in gen.get("results", []) if r.get("evidence_level") in ("confirmed", "short")]

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

### Task 7: Strengthened completeness check

**Files:**
- Modify: `nbs/publish.py` (add `check_completeness(gen, staging) -> list[str]`)
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: generation dict, `staging` = `Path` to `runs/<date>/staging`, `models.parse_frontmatter_strict`, `models.canonicalize_url`, `re`.
- Produces: `check_completeness(gen, staging) -> list[str]` — list of error strings (empty = pass). Verifies, for each ok result: exactly one `staging/posts/<slug>.md`; `post_path == f"posts/{slug}.md"`; front matter `event_key`==result event_key, `source_url`==result url, `date`==gen date, `evidence_level`==result evidence_level; `tags` non-empty list; slug/event_key/canonical_url unique across ok results; and the news index links exactly the set of ok slugs.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_publish.py (append)
from pathlib import Path
from nbs.publish import check_completeness

def _write_post(staging, slug, ek, url, date="2026-07-01", ev="confirmed", tags="[ai]"):
    (staging/"posts").mkdir(parents=True, exist_ok=True)
    (staging/"posts"/f"{slug}.md").write_text(
        f"---\ntitle: T\ndate: {date}\ntags: {tags}\nsource_url: {url}\n"
        f"source_lang: en\nsource_type: article\nevidence_level: {ev}\nevent_key: {ek}\n---\n## TL;DR\n- x\n본문\n",
        encoding="utf-8")

def _write_news(staging, slugs, date="2026-07-01"):
    (staging/"news").mkdir(parents=True, exist_ok=True)
    links = "\n".join('- [T]({{< relref "/posts/%s.md" >}}) — h' % s for s in slugs)
    (staging/"news"/f"{date}.md").write_text(f"---\ntitle: N\n---\n{links}\n", encoding="utf-8")

def _okres(ek):
    s=f"2026-07-01-{ek}"
    return {"event_key":ek,"evidence_level":"confirmed","status":"ok","slug":s,
            "url":f"https://x/{ek}","post_path":f"posts/{s}.md"}

def test_completeness_passes_on_matching_set(tmp_path):
    staging = tmp_path/"staging"
    gen = {"date":"2026-07-01","results":[_okres("a"), _okres("b")]}
    for r in gen["results"]:
        _write_post(staging, r["slug"], r["event_key"], r["url"])
    _write_news(staging, [r["slug"] for r in gen["results"]])
    assert check_completeness(gen, staging) == []

def test_completeness_flags_missing_post_file(tmp_path):
    staging = tmp_path/"staging"
    gen = {"date":"2026-07-01","results":[_okres("a"), _okres("b")]}
    _write_post(staging, "2026-07-01-a", "a", "https://x/a")   # b missing
    _write_news(staging, ["2026-07-01-a","2026-07-01-b"])
    errs = check_completeness(gen, staging)
    assert any("2026-07-01-b" in e for e in errs)

def test_completeness_flags_frontmatter_mismatch(tmp_path):
    staging = tmp_path/"staging"
    gen = {"date":"2026-07-01","results":[_okres("a"), _okres("b"), _okres("c")]}
    _write_post(staging, "2026-07-01-a", "WRONG", "https://x/a")   # event_key mismatch
    _write_post(staging, "2026-07-01-b", "b", "https://x/b")
    _write_post(staging, "2026-07-01-c", "c", "https://x/c")
    _write_news(staging, ["2026-07-01-a","2026-07-01-b","2026-07-01-c"])
    assert any("event_key" in e for e in check_completeness(gen, staging))

def test_completeness_flags_news_link_mismatch(tmp_path):
    staging = tmp_path/"staging"
    gen = {"date":"2026-07-01","results":[_okres("a"), _okres("b")]}
    for r in gen["results"]:
        _write_post(staging, r["slug"], r["event_key"], r["url"])
    _write_news(staging, ["2026-07-01-a"])   # missing b link
    assert any("news" in e.lower() for e in check_completeness(gen, staging))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_publish.py::test_completeness_passes_on_matching_set -v`
Expected: FAIL — `cannot import name 'check_completeness'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/publish.py — add
from .models import parse_frontmatter_strict, canonicalize_url

_RELREF = re.compile(r'relref\s+"/posts/([^"]+?)\.md"')

def check_completeness(gen, staging):
    errs = []
    ok = _ok(gen)
    date = gen.get("date")
    slugs, eks, canons = [], [], []
    for r in ok:
        slug = r.get("slug", "")
        slugs.append(slug); eks.append(r.get("event_key")); canons.append(canonicalize_url(r.get("url", "")))
        if r.get("post_path") != f"posts/{slug}.md":
            errs.append(f"{slug}: post_path != posts/{slug}.md (got {r.get('post_path')})")
        p = staging / "posts" / f"{slug}.md"
        if not p.exists():
            errs.append(f"{slug}: staging post file missing"); continue
        fm = parse_frontmatter_strict(p.read_text(encoding="utf-8"))
        if fm.get("event_key") != r.get("event_key"):
            errs.append(f"{slug}: front matter event_key {fm.get('event_key')} != {r.get('event_key')}")
        if fm.get("source_url") != r.get("url"):
            errs.append(f"{slug}: front matter source_url != result url")
        if fm.get("date") != date:
            errs.append(f"{slug}: front matter date {fm.get('date')} != {date}")
        if fm.get("evidence_level") != r.get("evidence_level"):
            errs.append(f"{slug}: front matter evidence_level mismatch")
        if not fm.get("tags"):
            errs.append(f"{slug}: empty tags")
    for label, vals in (("slug", slugs), ("event_key", eks), ("canonical_url", canons)):
        if len(set(vals)) != len(vals):
            errs.append(f"duplicate {label} across ok results")
    news = staging / "news" / f"{date}.md"
    linked = set(_RELREF.findall(news.read_text(encoding="utf-8"))) if news.exists() else set()
    if linked != set(slugs):
        errs.append(f"news links {sorted(linked)} != ok slugs {sorted(slugs)}")
    return errs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_publish.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/publish.py tests/test_publish.py
git commit -m "feat(p2c): strengthened completeness check (1:1, front matter, unique, news==ok)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 8: Promotion with write-set preflight and date-scoped rollback

**Files:**
- Modify: `nbs/publish.py` (add `_git`, `writeset_paths`, `preflight_clean`, `promote`, `rollback`)
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: `config.ROOT`, `config.run_dir`, `subprocess`, `shutil`, `pathlib`.
- Produces:
  - `writeset_paths(gen) -> list[str]` — repo-relative dest paths this run will touch (posts per ok slug, `news/<date>.md`, `usecase/<date>.md`, `data/published.csv`).
  - `preflight_clean(paths) -> list[str]` — returns any write-set paths that are git-dirty (uncommitted); empty = clean.
  - `promote(gen, staging) -> list[str]` — copies staging posts/news/usecase into `content/`; returns the list of content paths created/overwritten (usecase copied only if the staging file exists).
  - `rollback(created)` — restores content working tree: `git checkout --` tracked paths, delete untracked created files.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_publish.py (append)
import subprocess
from nbs import publish, config

def _git(args, cwd):
    return subprocess.run(["git"]+args, cwd=cwd, capture_output=True, text=True)

def _init_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(publish, "ROOT", tmp_path, raising=False)
    _git(["init","-q"], tmp_path); _git(["config","user.email","t@t"], tmp_path); _git(["config","user.name","t"], tmp_path)
    (tmp_path/"content"/"posts").mkdir(parents=True); (tmp_path/"content"/"news").mkdir(); (tmp_path/"content"/"usecase").mkdir()
    (tmp_path/"data").mkdir()
    (tmp_path/"content"/".keep").write_text("x"); _git(["add","-A"], tmp_path); _git(["commit","-qm","init"], tmp_path)
    return tmp_path

def _gen2(date="2026-07-01"):
    return {"date":date, "results":[_okres("a"), _okres("b")]}

def test_promote_copies_staging_to_content(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); staging=tmp_path/"staging"
    gen=_gen2()
    for r in gen["results"]: _write_post(staging, r["slug"], r["event_key"], r["url"])
    _write_news(staging, [r["slug"] for r in gen["results"]])
    (staging/"usecase").mkdir(); (staging/"usecase"/"2026-07-01.md").write_text("---\ntitle: U\n---\nu\n", encoding="utf-8")
    created = publish.promote(gen, staging)
    assert (root/"content"/"posts"/"2026-07-01-a.md").exists()
    assert (root/"content"/"news"/"2026-07-01.md").exists()
    assert (root/"content"/"usecase"/"2026-07-01.md").exists()
    assert any("2026-07-01-a.md" in c for c in created)

def test_preflight_detects_dirty_writeset(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    (root/"data"/"published.csv").write_text("dirty\n", encoding="utf-8")   # untracked/dirty write-set path
    dirty = publish.preflight_clean(["data/published.csv"])
    assert "data/published.csv" in dirty
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_publish.py::test_promote_copies_staging_to_content -v`
Expected: FAIL — `module 'nbs.publish' has no attribute 'promote'`

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/publish.py — add
import subprocess, shutil
from pathlib import Path
from .config import ROOT, run_dir

def _git(args):
    return subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True)

def writeset_paths(gen):
    date = gen["date"]
    paths = [f"content/posts/{r['slug']}.md" for r in _ok(gen)]
    paths += [f"content/news/{date}.md", f"content/usecase/{date}.md", "data/published.csv"]
    return paths

def preflight_clean(paths):
    # returns write-set paths that are git-dirty (staged, modified, or untracked-with-content)
    r = _git(["status", "--porcelain", "--"] + paths)
    dirty = []
    for line in r.stdout.splitlines():
        p = line[3:].strip()
        if p:
            dirty.append(p)
    return dirty

def promote(gen, staging):
    date = gen["date"]
    created = []
    def _cp(src, dst):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        created.append(str(dst.relative_to(ROOT)))
    for r in _ok(gen):
        _cp(staging/"posts"/f"{r['slug']}.md", ROOT/"content"/"posts"/f"{r['slug']}.md")
    _cp(staging/"news"/f"{date}.md", ROOT/"content"/"news"/f"{date}.md")
    uc = staging/"usecase"/f"{date}.md"
    if uc.exists():
        _cp(uc, ROOT/"content"/"usecase"/f"{date}.md")
    return created

def rollback(created):
    # restore working tree: tracked paths back to HEAD, untracked created files removed.
    for rel in created:
        tracked = _git(["ls-files", "--error-unmatch", rel]).returncode == 0
        if tracked:
            _git(["checkout", "--", rel])
        else:
            (ROOT/rel).exists() and (ROOT/rel).unlink()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_publish.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/publish.py tests/test_publish.py
git commit -m "feat(p2c): promote + write-set preflight + date-scoped rollback

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 9: Hugo build-verify (rendered files + subpath hrefs)

**Files:**
- Modify: `nbs/publish.py` (add `build_verify(gen) -> list[str]`)
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: `ROOT`, `subprocess`, `tempfile`; content already promoted.
- Produces: `build_verify(gen) -> list[str]` — errors (empty = pass). Runs `hugo --quiet -d <tmp>` (no pipe), asserts exit 0, then asserts every ok post renders `<tmp>/posts/<slug>/index.html`, the day's `<tmp>/news/<date>/index.html` exists, and that news HTML contains a `/ai-daily/posts/<slug>/` href for each ok slug.

- [ ] **Step 1: Write the failing test** (uses monkeypatch to stub Hugo so tests need no live build)

```python
# tests/test_publish.py (append)
def test_build_verify_flags_missing_rendered_post(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    calls={}
    def fake_hugo(outdir):
        # render only post a + a news page linking only a -> b must be flagged
        (Path(outdir)/"posts"/"2026-07-01-a").mkdir(parents=True)
        (Path(outdir)/"posts"/"2026-07-01-a"/"index.html").write_text("x")
        (Path(outdir)/"news"/"2026-07-01").mkdir(parents=True)
        (Path(outdir)/"news"/"2026-07-01"/"index.html").write_text('<a href="/ai-daily/posts/2026-07-01-a/">a</a>')
        calls["ran"]=True; return 0
    monkeypatch.setattr(publish, "_hugo_build", fake_hugo)
    errs = publish.build_verify(gen)
    assert calls.get("ran") and any("2026-07-01-b" in e for e in errs)

def test_build_verify_passes_when_all_rendered(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    def fake_hugo(outdir):
        for s in ("2026-07-01-a","2026-07-01-b"):
            (Path(outdir)/"posts"/s).mkdir(parents=True); (Path(outdir)/"posts"/s/"index.html").write_text("x")
        (Path(outdir)/"news"/"2026-07-01").mkdir(parents=True)
        (Path(outdir)/"news"/"2026-07-01"/"index.html").write_text(
            '<a href="/ai-daily/posts/2026-07-01-a/">a</a><a href="/ai-daily/posts/2026-07-01-b/">b</a>')
        return 0
    monkeypatch.setattr(publish, "_hugo_build", fake_hugo)
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
    r = subprocess.run(["hugo", "--quiet", "-d", outdir], cwd=str(ROOT),
                       capture_output=True, text=True)
    return r.returncode

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
            if not (out / "posts" / slug / "index.html").exists():
                errs.append(f"post not rendered: posts/{slug}/index.html")
            if f"/ai-daily/posts/{slug}/" not in html:
                errs.append(f"news missing subpath href for {slug}")
    return errs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_publish.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nbs/publish.py tests/test_publish.py
git commit -m "feat(p2c): hugo build-verify (rendered post/news files + subpath hrefs)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 10: Build ledger rows (canonical_key, TL;DR summary, tags)

**Files:**
- Modify: `nbs/publish.py` (add `ledger_rows(gen) -> list[dict]`)
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: ok results, promoted `content/posts/<slug>.md`, `extract_tldr`, `parse_frontmatter_strict`, `canonicalize_url`, `ledger.LEDGER_HEADER`.
- Produces: `ledger_rows(gen) -> list[dict]` — one dict per ok result keyed by `LEDGER_HEADER`: `canonical_key=canonicalize_url(url)`, `event_key/date/title/url/source/post_path` from result, `summary=extract_tldr(post md)`, `tags=",".join(front-matter tags list)`, `entities=""`, `confidence=""`. Reads the promoted `content/posts/<slug>.md`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_publish.py (append)
def test_ledger_rows_fields(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    # promote posts into content first
    (root/"content"/"posts"/"2026-07-01-a.md").write_text(
        "---\ntitle: A\ndate: 2026-07-01\ntags: [ai, model]\nsource_url: https://x/a\n"
        "source_lang: en\nsource_type: article\nevidence_level: confirmed\nevent_key: a\n---\n## TL;DR\n- 요약 문장\n본문\n", encoding="utf-8")
    (root/"content"/"posts"/"2026-07-01-b.md").write_text(
        "---\ntitle: B\ndate: 2026-07-01\ntags: [x]\nsource_url: https://x/b\n"
        "source_lang: en\nsource_type: article\nevidence_level: confirmed\nevent_key: b\n---\n첫 문단.\n", encoding="utf-8")
    gen["results"][0]["title"]="A"; gen["results"][0]["source"]="OpenAI"
    rows = publish.ledger_rows(gen)
    ra = next(r for r in rows if r["event_key"]=="a")
    assert ra["canonical_key"] == "https://x/a"
    assert "요약 문장" in ra["summary"] and ra["tags"] == "ai,model"
    assert ra["post_path"] == "posts/2026-07-01-a.md"
    rb = next(r for r in rows if r["event_key"]=="b")
    assert rb["summary"].startswith("첫 문단")   # fallback path
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
        md = (ROOT / "content" / "posts" / f"{r['slug']}.md").read_text(encoding="utf-8")
        fm = parse_frontmatter_strict(md)
        tags = fm.get("tags") or []
        rows.append({
            "canonical_key": canonicalize_url(r.get("url", "")),
            "event_key": r.get("event_key", ""), "date": gen["date"],
            "title": r.get("title", ""), "url": r.get("url", ""), "source": r.get("source", ""),
            "post_path": r.get("post_path", ""), "summary": extract_tldr(md),
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
git commit -m "feat(p2c): ledger_rows — canonical_key + TL;DR summary + tags from promoted posts

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 11: Orchestration — `run()` + publish.json + git commit + degraded

**Files:**
- Modify: `nbs/publish.py` (add `run(date)`, `_write_manifest`, `main`, git identity preflight, `__main__`)
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: everything above; `ledger.rewrite_date`, `run_dir`, `assemble.FLOOR_N`.
- Produces:
  - `run(date, *, do_commit=True) -> dict` (the manifest) — orchestrates: load generation.json → `decide` → (held: write manifest `status=held`, no promotion) → git identity + write-set preflight → `promote` → `check_completeness`/`build_verify` (fail → `rollback` + manifest `status=failed`) → `rewrite_date` ledger → single git commit (`nothing to commit` = success) → manifest `status=published` with `commit_sha`, `promoted[]`, `degraded`.
  - manifest written to `runs/<date>/publish.json`: `{date, status(published|held|failed), reason, promoted[], degraded{usecase, generation_failed_count}, commit_sha, error}`.
  - `main()` — argparse `--date`, `--no-commit`; prints status line.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_publish.py (append)
import json

def _stage_full(tmp_path, gen):
    d = tmp_path/"runs"/gen["date"]; staging=d/"staging"
    for r in gen["results"]:
        _write_post(staging, r["slug"], r["event_key"], r["url"], date=gen["date"])
    _write_news(staging, [r["slug"] for r in gen["results"]], date=gen["date"])
    (staging/"usecase").mkdir(parents=True, exist_ok=True)
    (staging/"usecase"/f"{gen['date']}.md").write_text("---\ntitle: U\n---\nu\n", encoding="utf-8")
    (d/"generation.json").write_text(json.dumps(gen), encoding="utf-8")
    return d

def test_run_held_when_evidence_low(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(publish, "run_dir", lambda date: root/"runs"/date)
    gen={"date":"2026-07-01","results":[_res("a","confirmed","ok"), _res("b","exclude","excluded"), _res("c","exclude","excluded")]}
    _stage_full(root, gen)
    m = publish.run("2026-07-01")
    assert m["status"]=="held" and not (root/"content"/"news"/"2026-07-01.md").exists()

def test_run_publishes_and_writes_ledger_and_manifest(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(publish, "run_dir", lambda date: root/"runs"/date)
    monkeypatch.setattr(publish, "_hugo_build", lambda outdir: _fake_full_build(outdir, "2026-07-01", ["2026-07-01-a","2026-07-01-b","2026-07-01-c"]))
    gen={"date":"2026-07-01","results":[_okres("a"), _okres("b"), _okres("c")]}
    for r in gen["results"]: r["source"]="S"; r["title"]="T"
    _stage_full(root, gen)
    m = publish.run("2026-07-01")
    assert m["status"]=="published"
    assert (root/"content"/"news"/"2026-07-01.md").exists()
    led = (root/"data"/"published.csv").read_text(encoding="utf-8")
    assert "2026-07-01-a" in led
    # idempotent rerun: still one row set, still published
    m2 = publish.run("2026-07-01")
    assert m2["status"]=="published"
    assert led.count("2026-07-01-a") == (root/"data"/"published.csv").read_text(encoding="utf-8").count("2026-07-01-a")

def _fake_full_build(outdir, date, slugs):
    from pathlib import Path as _P
    hrefs=""
    for s in slugs:
        (_P(outdir)/"posts"/s).mkdir(parents=True); (_P(outdir)/"posts"/s/"index.html").write_text("x")
        hrefs+=f'<a href="/ai-daily/posts/{s}/">x</a>'
    (_P(outdir)/"news"/date).mkdir(parents=True); (_P(outdir)/"news"/date/"index.html").write_text(hrefs)
    return 0
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
    (run_dir(date) / "publish.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

def _degraded(gen):
    ok, ev = len(_ok(gen)), len(_evidence(gen))
    d = {}
    if gen.get("usecase_error"):
        d["usecase"] = gen["usecase_error"]
    if ok < ev or ok < assemble.FLOOR_N:
        d["generation_failed_count"] = ev - ok
    return d

def run(date, *, do_commit=True):
    d = run_dir(date)
    gen = json.loads((d / "generation.json").read_text(encoding="utf-8"))
    staging = d / "staging"
    decision, reason = decide(gen)
    if decision == "held":
        return _write_manifest(date, {"date": date, "status": "held", "reason": reason,
                                      "promoted": [], "degraded": _degraded(gen), "commit_sha": None, "error": None})
    # preflight: git identity + clean write-set
    if not (_git(["config", "user.email"]).stdout.strip() and _git(["config", "user.name"]).stdout.strip()):
        return _write_manifest(date, {"date": date, "status": "failed", "reason": "git identity not configured",
                                      "promoted": [], "degraded": _degraded(gen), "commit_sha": None, "error": "git identity"})
    dirty = preflight_clean(writeset_paths(gen))
    if dirty:
        return _write_manifest(date, {"date": date, "status": "failed", "reason": f"write-set dirty: {dirty}",
                                      "promoted": [], "degraded": _degraded(gen), "commit_sha": None, "error": "dirty write-set"})
    created = promote(gen, staging)
    errs = check_completeness(gen, staging) + build_verify(gen)
    if errs:
        rollback(created)
        return _write_manifest(date, {"date": date, "status": "failed", "reason": "completeness/build",
                                      "promoted": [], "degraded": _degraded(gen), "commit_sha": None, "error": "; ".join(errs[:8])})
    ledger_mod.rewrite_date(date, ledger_rows(gen))
    commit_sha = None
    if do_commit:
        _git(["add"] + writeset_paths(gen))
        c = _git(["commit", "-m", _commit_msg(date, gen)])
        if c.returncode != 0 and "nothing to commit" not in (c.stdout + c.stderr):
            rollback(created)
            return _write_manifest(date, {"date": date, "status": "failed", "reason": "git commit failed",
                                          "promoted": [], "degraded": _degraded(gen), "commit_sha": None, "error": c.stderr[:200]})
        commit_sha = _git(["rev-parse", "HEAD"]).stdout.strip()
    return _write_manifest(date, {"date": date, "status": "published", "reason": "ok",
                                  "promoted": created, "degraded": _degraded(gen), "commit_sha": commit_sha, "error": None})

def _commit_msg(date, gen):
    return (f"publish(ai-daily): {date} — {len(_ok(gen))} posts"
            + "\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
            + "\nClaude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--date", required=True)
    ap.add_argument("--no-commit", action="store_true"); a = ap.parse_args()
    m = run(a.date, do_commit=not a.no_commit)
    print(f"[{m['status']}] {a.date} promoted={len(m['promoted'])} degraded={m['degraded']} reason={m['reason']}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_publish.py -v`
Expected: PASS (held + published + idempotent-rerun cases)

- [ ] **Step 5: Commit**

```bash
git add nbs/publish.py tests/test_publish.py
git commit -m "feat(p2c): publish orchestration — gate->promote->verify->ledger->commit + manifest

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

### Task 12: Full-suite regression + real publish smoke + docs

**Files:**
- Create: `scripts/p2c_smoke.sh`
- Modify: `docs/superpowers/HANDOFF.md` (P2c status)
- Test: full `pytest`

**Interfaces:**
- Consumes: everything; a real `runs/<date>/staging/` + `generation.json` from a P2b run.

- [ ] **Step 1: Full-suite regression**

Run: `python3 -m pytest -q`
Expected: PASS (P2b 80 + new P2c tests). Fix any P2b test that assumed the old `floor_ok` (publishable) or root-relative news links — Tasks 3/4 already updated them; confirm none remain red.

- [ ] **Step 2: Write the real publish smoke script**

```bash
# scripts/p2c_smoke.sh
#!/usr/bin/env bash
# P2c real smoke: promote a prepared staging day into content/ WITHOUT committing.
# Requires an existing runs/<date>/generation.json + staging (from a P2b stage run).
set -euo pipefail
DATE="${1:?usage: p2c_smoke.sh <date>}"
export PATH="$HOME/.local/bin:$PATH"
python3 -m nbs.publish --date "$DATE" --no-commit
echo "--- publish.json ---"
cat "runs/$DATE/publish.json"
echo "--- content added ---"
ls -1 "content/posts/" | grep "$DATE" || true
ls -1 "content/news/$DATE.md" "content/usecase/$DATE.md" 2>/dev/null || true
```

- [ ] **Step 3: Run the real smoke (Claude Code env)**

Run (regenerate staging first if needed, then publish dry):
```bash
export PATH="$HOME/.local/bin:$PATH"
chmod +x scripts/p2c_smoke.sh
# staging for 2026-07-02 already exists from P2b; if not: python3 -m nbs.stage --date 2026-07-02
bash scripts/p2c_smoke.sh 2026-07-02
```
Expected: `publish.json` `status=published`, `content/posts/2026-07-02-*.md` present, `content/news/2026-07-02.md` present, ledger `data/published.csv` has the day's rows. Then discard the dry-run working-tree changes: `git checkout -- content/ data/published.csv && git clean -fd content/`.

- [ ] **Step 4: Update HANDOFF**

Set P2c row to DONE-pending-merge, note real-smoke evidence, and record any deferred minors (unanchored `---` in `parse_frontmatter`, entities/confidence empty).

- [ ] **Step 5: Commit**

```bash
git add scripts/p2c_smoke.sh docs/superpowers/HANDOFF.md
git commit -m "test(p2c): real publish smoke script + HANDOFF update

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WVpBkm4AB4juVWwn5saTr4"
```

---

## Notes / deferred (carry to review)

- `parse_frontmatter` unanchored `---` split stays a documented defer-safe minor; `parse_frontmatter_strict` inherits it (our emitted posts never put `---` in a value).
- `entities` / `confidence` ledger fields intentionally empty (YAGNI; `ledger_digest` ignores them).
- Real smoke covers article-only days (matches P2b coverage note). paper/sns/video promotion exercised by unit tests only.
- Push / live deploy / email / unattended schedule = P3 (out of scope).
