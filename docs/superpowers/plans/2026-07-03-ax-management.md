# AX 경영 (3번째 1급 산출물) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** News·UseCase와 평행한 3번째 1급 일간 산출물 "AX 경영"(경영자 톤 synthesis)을 추가하고, 그날 항목에 앵커된 것만 발행하는 결정적 grounding 게이트를 건다.

**Architecture:** UseCase 파이프라인을 그대로 복제 — `prompts/ax.md` + `assemble.build_ax`(build_usecase 복제 + grounding 게이트) → `stage`가 `staging/ax/<date>.md` 생성 → `publish`가 `content/ax/<date>.md` optional 승격 → PaperMod가 `/ax/` 자동 렌더 → `email`이 3번째 섹션. 신규 발명 0, 검증 파이프라인 재사용.

**Tech Stack:** Python 3(stdlib `re`), Hugo(PaperMod), claude -p(`--tools ""`), pytest.

## Global Constraints

- **SSOT** = 스펙 `docs/superpowers/specs/2026-07-01-nbs-news-blog-design.md` §16 "AX 경영" + 부록A AX 리뷰. 충돌 시 SSOT.
- **python3** 사용. **테스트 파이프 금지**(`pytest`/`hugo`를 `| tail`로 감싸지 말 것 — hookify 차단, exit code 은폐 [[2026-07-01-pipe-hides-build-failure]]). 직접 실행 또는 `set -o pipefail`.
- **import 사이클 금지:** `publish → assemble`(publish가 assemble 임포트)이므로 **`assemble`은 `publish`/`email`을 모듈레벨 임포트 금지**. `build_ax`의 게이트는 `publish._RELREF`를 **함수레벨 임포트**로 재사용(호출시점엔 전부 로드됨 → 사이클 없음, 단일 소스 유지).
- **grounding 게이트 = 결정적**(스펙 §16): 본문에서 **angle-form `{{< relref "/posts/<slug>.md" >}}`만** slug 추출 → (a) 교집합≥1 (b) 추출 slug 전부 publishable ∈ (c) 비-angle ref/relref shortcode 잔존 시 거부. **email `_RELREF_FULL`/`_ANY_REF_SHORTCODE`와 동일 형태**(gate-pass ⟹ email·Hugo-safe). 위반 = `ValueError`(§5 격리 → `ax_error`).
- **게이트는 필요조건이지 충분조건 아님** — fig-leaf(장식 링크 1개+일반론)는 프롬프트 계약 + 사람 eyeball이 담당.
- **UseCase 평행**: 기존 스테이지 최소 수정, 모든 usecase 터치포인트를 ax로 복제(assemble/stage/publish/email/hugo.toml). 재사용: `assemble.publishable`, `_blog_snippet`, `_strip_fences`, `parse_frontmatter`.
- **커밋**: 태스크당 1커밋. 메시지 끝 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` / `Claude-Session: https://claude.ai/code/session_0146UERyE93fmWzCxWuLH1g6`. **브랜치**: `ax-management`(체크아웃됨, spec `094da8e` 위).

## File Structure

- **Create** `prompts/ax.md` — 경영자 톤 프롬프트(항목 relref 링크 강제 + grounding 규칙).
- **Create** `tests/test_ax.py` — build_ax 게이트 + stage/publish/email ax 배선 테스트(네트워크 0).
- **Modify** `nbs/assemble.py` — `_summary_lines` 추출 + `AX_PROMPT` + `build_ax_prompt` + `build_ax`(게이트).
- **Modify** `nbs/stage.py` — `run` 시그니처 `ax=None`, staging 하위 `ax`, ax 격리 블록, `generation.json` `ax_error`.
- **Modify** `nbs/publish.py` — `date_writeset`/`promote`/`build_verify`/`_degraded`에 ax.
- **Modify** `hugo.toml` — `[[menu.main]]` AX 경영 + `params.mainSections`에 `"ax"`.
- **Modify** `nbs/email.py` — `read_content` 3튜플(+ax), `run_email` 본문 3섹션.
- **Modify** `tests/test_email.py` — `read_content` 3튜플 테스트 갱신.

---

### Task 1: prompts/ax.md + assemble.build_ax + 결정적 grounding 게이트

**Files:**
- Create: `prompts/ax.md`
- Modify: `nbs/assemble.py`
- Test: `tests/test_ax.py`

**Interfaces:**
- Consumes: `assemble.publishable(results)`, `assemble._blog_snippet`, `generate.run_claude_notools`, `generate._strip_fences`, `models.parse_frontmatter`, `publish._RELREF`(함수레벨).
- Produces: `assemble.AX_PROMPT`, `assemble._summary_lines(results) -> str`, `assemble.build_ax_prompt(results, date) -> str`, `assemble.build_ax(results, date, *, run=None) -> str | None`.
- `build_ax` 반환: 검증·게이트 통과한 md / `publishable` 없으면 `None` / 형식·게이트 위반 시 `ValueError`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ax.py
import re
import pytest
from nbs import assemble
from nbs.models import GenerationResult


def _res(slug, title="T", status="ok"):
    return GenerationResult(event_key=slug.split("2026-07-03-")[-1], title=title, url="http://x",
                            source="s", source_type="article", evidence_level="confirmed",
                            status=status, post_path=f"content/posts/{slug}.md", slug=slug, rank=1)


def _fm(body):  # valid front matter + given body
    return f"---\ntitle: AI 경영 브리핑 2026-07-03\ndate: 2026-07-03\ntags: [ax]\n---\n\n{body}\n"


def test_build_ax_none_when_no_publishable():
    assert assemble.build_ax([_res("2026-07-03-a", status="failed")], "2026-07-03", run=lambda p: "x") is None


def test_build_ax_ok_with_anchored_relref():
    results = [_res("2026-07-03-a"), _res("2026-07-03-b")]
    body = '오픈AI 지분 소식은 조직에 X를 시사 [자세히]({{< relref "/posts/2026-07-03-a.md" >}}).'
    md = assemble.build_ax(results, "2026-07-03", run=lambda p: _fm(body))
    assert md.startswith("---") and "relref" in md


def test_build_ax_rejects_zero_anchor():  # (a)
    results = [_res("2026-07-03-a")]
    with pytest.raises(ValueError):
        assemble.build_ax(results, "2026-07-03", run=lambda p: _fm("일반론만 있고 항목 링크가 없다."))


def test_build_ax_rejects_hallucinated_slug():  # (b)
    results = [_res("2026-07-03-a")]
    body = '[x]({{< relref "/posts/2026-07-03-a.md" >}}) [y]({{< relref "/posts/2026-07-03-ZZZ.md" >}})'
    with pytest.raises(ValueError):
        assemble.build_ax(results, "2026-07-03", run=lambda p: _fm(body))


def test_build_ax_rejects_non_angle_shortcode():  # (c) — email would fail on {{% %}}
    results = [_res("2026-07-03-a")]
    body = '[x]({{< relref "/posts/2026-07-03-a.md" >}}) 그리고 {{% relref "/posts/2026-07-03-a.md" %}}'
    with pytest.raises(ValueError):
        assemble.build_ax(results, "2026-07-03", run=lambda p: _fm(body))


def test_build_ax_rejects_missing_front_matter():
    with pytest.raises(ValueError):
        assemble.build_ax([_res("2026-07-03-a")], "2026-07-03",
                          run=lambda p: '본문만 {{< relref "/posts/2026-07-03-a.md" >}}')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ax.py -q`
Expected: FAIL — `AttributeError: module 'nbs.assemble' has no attribute 'build_ax'`.

- [ ] **Step 3: Create the prompt**

Create `prompts/ax.md`:

```
너는 경영자·임원을 위한 "AX 경영" 브리핑을 쓴다. 아래는 오늘 발행된 블로그의 제목+요약이다.
이 소식들이 **조직 운영을 어떻게 바꾸는가**를 경영 관점에서 짚는다: 시간 재투자·업무 폐지·판단권한 위임·역할 승급·이익 분배.

## 철칙 (반드시 지켜라)
- **모든 경영 주장은 아래 목록의 특정 항목에 근거**해야 한다. 항목과 무관한 일반론(evergreen 원칙 나열)을 쓰지 마라.
- 각 포인트에는 근거 항목으로 가는 링크를 **정확히 이 형태로** 단다: `[제목 일부]({{< relref "/posts/<slug>.md" >}})` — `<slug>`는 아래 `/posts/<slug>/`의 slug. **다른 shortcode 형태(`{{% %}}` 등) 금지.**
- 목록에 없는 사실을 지어내지 마라. 근거는 아래 요약뿐.
- **짧아도 된다.** 경영 각도가 실하게 붙는 1~3개만. 억지로 채우지 마라. 경영 각도가 약한 날은 그렇게 밝히고 해당되는 항목만 짧게.

## 출력 (front matter + 본문)
---
title: AI 경영 브리핑 <DATE>
date: <DATE>
tags: [ax]
---
<본문: 각 포인트를 "무슨 소식 → 조직에서 무엇을 바꿔라" 순으로. 각 포인트에 relref 링크 필수>

## 입력 (오늘 블로그 요약)
<<SUMMARIES>>
```

- [ ] **Step 4: Implement build_ax in `nbs/assemble.py`**

Add `import re` to the imports at the top of `nbs/assemble.py` if not already present. Then refactor `build_usecase_prompt` to share a helper and add the AX functions. Replace the existing `build_usecase_prompt`:

```python
def _summary_lines(results):
    lines = []
    for r in publishable(results):
        snip = _blog_snippet(getattr(r, "_md", "") or "")
        lines.append(f"- {r.title} ({r.source}) -> /posts/{r.slug}/\n  {snip}")
    return "\n".join(lines)

def build_usecase_prompt(results, date):
    return (USECASE_PROMPT.read_text(encoding="utf-8")
            .replace("<<SUMMARIES>>", _summary_lines(results)).replace("<DATE>", date))
```

Then add (near `USECASE_PROMPT` add the constant; place the functions after `build_usecase`):

```python
AX_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "ax.md"

def build_ax_prompt(results, date):
    return (AX_PROMPT.read_text(encoding="utf-8")
            .replace("<<SUMMARIES>>", _summary_lines(results)).replace("<DATE>", date))

# angle-form relref ({{< relref "/posts/<slug>.md" >}}) — SAME form email._RELREF_FULL rewrites.
# publish._RELREF is imported at call time (function-level) to avoid an assemble<->publish
# import cycle while keeping the relref token a single source.
_ANY_REF_SHORTCODE = re.compile(r"\{\{[<%]\s*/?\s*(?:rel)?ref\b")

def build_ax(results, date, *, run=None):
    if not publishable(results):
        return None
    if run is None:
        from .generate import run_claude_notools as run
    from .generate import _strip_fences
    from .models import parse_frontmatter
    from . import publish   # function-level: avoids import cycle; reuse _RELREF (single source)
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
    angle = re.compile(r"\{\{<\s*" + publish._RELREF.pattern + r"\s*>\}\}")
    linked = set(angle.findall(body))
    if _ANY_REF_SHORTCODE.search(angle.sub("", body)):        # (c) non-angle ref/relref remains
        raise ValueError("ax: non-angle ref/relref shortcode remains (email would fail)")
    if not linked:                                            # (a) no post anchor
        raise ValueError("ax: no post-anchor relref — ungrounded")
    ok_slugs = {r.slug for r in publishable(results)}
    if not linked <= ok_slugs:                               # (b) hallucinated slug
        raise ValueError(f"ax: relref to non-publishable slug: {sorted(linked - ok_slugs)}")
    return md
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_ax.py -q`
Expected: PASS (6 tests).

- [ ] **Step 6: Verify usecase refactor didn't regress**

Run: `python3 -m pytest -q -k "usecase or assemble"`
Expected: PASS (existing usecase/assemble tests still green — `_summary_lines` extraction is output-identical).

- [ ] **Step 7: Commit**

```bash
git add prompts/ax.md nbs/assemble.py tests/test_ax.py
git commit -m "feat(ax): prompts/ax.md + assemble.build_ax with deterministic grounding gate"
```

---

### Task 2: stage.py — ax 스테이지 배선 (§5 격리)

**Files:**
- Modify: `nbs/stage.py`
- Test: `tests/test_ax.py`

**Interfaces:**
- Consumes: `assemble.build_ax`.
- Produces: `stage.run(date, *, fetch=None, generate=None, usecase=None, ax=None)`; `staging/ax/<date>.md`; `generation.json` gains `ax_error`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_ax.py
import json as _json
from nbs import stage as stage_mod

def _seed_selection(tmp_path, date, monkeypatch):
    from nbs import config
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(stage_mod, "run_dir", lambda d: tmp_path / "runs" / d)
    d = tmp_path / "runs" / date; d.mkdir(parents=True)
    (d / "selection.json").write_text(_json.dumps({"items": [
        {"event_key": "a", "url": "http://x", "source_type": "article", "title": "T"}]}), encoding="utf-8")
    return d

def test_stage_ax_isolated_failure_records_ax_error(tmp_path, monkeypatch):
    d = _seed_selection(tmp_path, "2026-07-03", monkeypatch)
    def fake_fetch(it):
        from nbs.models import FetchResult
        return FetchResult(event_key=it["event_key"], url=it["url"], source_type="article",
                           text="body", evidence_level="confirmed", via="t", fetch_ok=True)
    def fake_generate(items, fetched, date):
        from nbs.models import GenerationResult
        r = GenerationResult(event_key="a", title="T", url="http://x", source="s", source_type="article",
                             evidence_level="confirmed", status="ok",
                             post_path="content/posts/2026-07-03-a.md", slug="2026-07-03-a", rank=1)
        r._md = "---\nx: 1\n---\nbody"
        return [r, r, r]  # >=FLOOR_N publishable so floor passes
    def boom_ax(results, date): raise RuntimeError("ax boom")
    payload = stage_mod.run("2026-07-03", fetch=fake_fetch, generate=fake_generate,
                            usecase=lambda r, dt: None, ax=boom_ax)
    assert payload["ax_error"] == "ax boom"[:200]
    assert payload["status"] == "ok"                       # ax failure did NOT abort
    assert not (d / "staging" / "ax" / "2026-07-03.md").exists()

def test_stage_writes_ax_when_ok(tmp_path, monkeypatch):
    d = _seed_selection(tmp_path, "2026-07-03", monkeypatch)
    def fake_fetch(it):
        from nbs.models import FetchResult
        return FetchResult(event_key=it["event_key"], url=it["url"], source_type="article",
                           text="body", evidence_level="confirmed", via="t", fetch_ok=True)
    def fake_generate(items, fetched, date):
        from nbs.models import GenerationResult
        r = GenerationResult(event_key="a", title="T", url="http://x", source="s", source_type="article",
                             evidence_level="confirmed", status="ok",
                             post_path="content/posts/2026-07-03-a.md", slug="2026-07-03-a", rank=1)
        r._md = "---\nx: 1\n---\nbody"
        return [r, r, r]
    stage_mod.run("2026-07-03", fetch=fake_fetch, generate=fake_generate,
                  usecase=lambda r, dt: None, ax=lambda r, dt: "AX-MD")
    assert (d / "staging" / "ax" / "2026-07-03.md").read_text() == "AX-MD"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ax.py -k stage -q`
Expected: FAIL — `run() got an unexpected keyword argument 'ax'`.

- [ ] **Step 3: Implement**

In `nbs/stage.py`, change the `run` signature and defaults:

```python
def run(date, *, fetch=None, generate=None, usecase=None, ax=None):
    fetch = fetch or fetch_mod.fetch_item
    generate = generate or gen_mod.generate_all
    usecase = usecase or asm.build_usecase
    ax = ax or asm.build_ax
```

In the empty-items early-return payload, add `ax_error`:

```python
        payload = {"date": date, "status": "skip-empty", "results": [],
                   "published_count": 0, "floor_failed": False, "usecase_error": None, "ax_error": None}
```

Add `"ax"` to the staging subdir loop:

```python
    for sub in ("posts", "news", "usecase", "ax"):
        (staging/sub).mkdir(parents=True, exist_ok=True)
```

Inside the `if not floor_failed:` block, after the usecase try/except, add the ax block:

```python
        ax_error = None
        try:
            # §5 isolation: an ax claude -p failure (bad output/timeout/gate reject) must not
            # abort the run. Gate rejection (ungrounded) is a normal "no AX page today" outcome.
            ax_md = ax(results, date)
            if ax_md:
                (staging/"ax"/f"{date}.md").write_text(ax_md, encoding="utf-8")
        except Exception as e:
            ax_error = str(e)[:200]
```

Move `ax_error = None` initialization to before the `if not floor_failed:` block (parallel to `usecase_error = None`), so it exists when floor fails. Change:

```python
    floor_failed = not asm.floor_ok(results)
    usecase_error = None
    ax_error = None
    if not floor_failed:
        (staging/"news"/f"{date}.md").write_text(asm.build_news_index(results, date), encoding="utf-8")
        try:
            uc = usecase(results, date)
            if uc:
                (staging/"usecase"/f"{date}.md").write_text(uc, encoding="utf-8")
        except Exception as e:
            usecase_error = str(e)[:200]
        try:
            ax_md = ax(results, date)
            if ax_md:
                (staging/"ax"/f"{date}.md").write_text(ax_md, encoding="utf-8")
        except Exception as e:
            ax_error = str(e)[:200]
```

Add `ax_error` to the main payload:

```python
    payload = {"date": date, "status": "ok",
               "results": [r.to_dict() for r in results],
               "published_count": len(asm.publishable(results)),
               "floor_failed": floor_failed, "usecase_error": usecase_error, "ax_error": ax_error}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_ax.py -k stage -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add nbs/stage.py tests/test_ax.py
git commit -m "feat(ax): stage ax generation (§5 isolated, ax_error in generation.json)"
```

---

### Task 3: publish.py — ax optional 승격 + writeset + build_verify + degraded

**Files:**
- Modify: `nbs/publish.py`
- Test: `tests/test_ax.py`

**Interfaces:**
- Produces: `date_writeset` includes `content/ax/<date>.md`; `promote` copies/stale-drops ax; `build_verify` checks ax page; `_degraded` includes `ax`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_ax.py
from nbs import publish as publish_mod

def test_writeset_includes_ax():
    gen = {"date": "2026-07-03", "results": []}
    import nbs.publish as P
    # date_writeset globs content/ + git; assert the ax path is in the fixed tail
    ws = P.date_writeset(gen)
    assert "content/ax/2026-07-03.md" in ws

def test_degraded_includes_ax_error():
    from nbs import publish as P
    gen = {"date": "2026-07-03", "results": [], "ax_error": "ax boom"}
    assert P._degraded(gen).get("ax") == "ax boom"

def test_promote_copies_ax_optional(tmp_path, monkeypatch):
    from nbs import publish as P
    monkeypatch.setattr(P, "ROOT", tmp_path)
    (tmp_path / "content" / "posts").mkdir(parents=True)
    (tmp_path / "content" / "news").mkdir(parents=True)
    staging = tmp_path / "staging"
    for sub in ("posts", "news", "ax"):
        (staging / sub).mkdir(parents=True)
    (staging / "news" / "2026-07-03.md").write_text("news")
    (staging / "ax" / "2026-07-03.md").write_text("axmd")
    gen = {"date": "2026-07-03", "results": []}
    touched = P.promote(gen, staging)
    assert (tmp_path / "content" / "ax" / "2026-07-03.md").read_text() == "axmd"
    assert "content/ax/2026-07-03.md" in touched

def test_build_verify_flags_missing_ax_page(tmp_path, monkeypatch):
    # implementer must not omit the build_verify ax check — mock hugo, render news but NOT ax
    from nbs import publish as P
    from pathlib import Path
    monkeypatch.setattr(P, "ROOT", tmp_path)
    (tmp_path / "content" / "ax").mkdir(parents=True)
    (tmp_path / "content" / "ax" / "2026-07-03.md").write_text("ax", encoding="utf-8")
    def fake_build(outdir):
        o = Path(outdir); (o / "news" / "2026-07-03").mkdir(parents=True)
        (o / "news" / "2026-07-03" / "index.html").write_text("<html></html>")
        return 0   # deliberately does NOT create ax/2026-07-03/index.html
    monkeypatch.setattr(P, "_hugo_build", fake_build)
    errs = P.build_verify({"date": "2026-07-03", "results": []})
    assert any("ax page not rendered" in e for e in errs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ax.py -k "writeset or degraded or promote or build_verify" -q`
Expected: FAIL — ax path not in writeset / `_degraded` has no `ax` / ax not copied / build_verify doesn't flag missing ax page.

- [ ] **Step 3: Implement**

In `nbs/publish.py`, `date_writeset` return line — add the ax path:

```python
    return sorted(posts) + [f"content/news/{date}.md", f"content/usecase/{date}.md",
                            f"content/ax/{date}.md", "data/published.csv"]
```

In `promote`, after the usecase block (the `uc = ... elif target_uc.exists(): ... unlink()`), add the parallel ax block:

```python
    ax = staging/"ax"/f"{date}.md"
    target_ax = ROOT/"content"/"ax"/f"{date}.md"
    if ax.exists():
        _cp(ax, target_ax)
    elif target_ax.exists():                        # degraded/rerun — drop stale ax
        touched.append(str(target_ax.relative_to(ROOT))); target_ax.unlink()
    return touched
```

(The `return touched` replaces the old one — move it to after the ax block.)

In `build_verify`, after the usecase check, add the ax check:

```python
        if (ROOT/"content"/"ax"/f"{date}.md").exists() and not (out/"ax"/date/"index.html").exists():
            errs.append(f"ax page not rendered: ax/{date}/index.html")
```

In `_degraded`, add the ax_error line:

```python
def _degraded(gen):
    ok, ev = len(_ok(gen)), len(_evidence(gen)); d = {}
    if gen.get("usecase_error"): d["usecase"] = gen["usecase_error"]
    if gen.get("ax_error"): d["ax"] = gen["ax_error"]
    if ok < ev or ok < assemble.FLOOR_N: d["generation_failed_count"] = ev - ok
    return d
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_ax.py -k "writeset or degraded or promote or build_verify" -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add nbs/publish.py tests/test_ax.py
git commit -m "feat(ax): publish ax optional promote + writeset + build_verify + degraded"
```

---

### Task 4: hugo.toml — 메뉴 + mainSections

**Files:**
- Modify: `hugo.toml`
- Test: `tests/test_ax.py`

**Interfaces:**
- Produces: `/ax/` in nav + `params.mainSections` (so PaperMod home/archive/nav include it).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_ax.py
from pathlib import Path as _P
from nbs import config as _cfg

def test_hugo_config_has_ax_section_and_menu():
    toml = (_P(_cfg.ROOT) / "hugo.toml").read_text(encoding="utf-8")
    assert '"ax"' in toml.split("mainSections")[1].split("]")[0]   # ax in mainSections
    assert 'url = "ax/"' in toml                                    # menu entry
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ax.py -k hugo -q`
Expected: FAIL — ax not in mainSections.

- [ ] **Step 3: Implement**

In `hugo.toml`, change `mainSections`:

```toml
  mainSections = ["ax", "news", "posts", "usecase"]
```

Add the menu entry (as the first `[[menu.main]]`, weight 0):

```toml
  [[menu.main]]
    name = "AX 경영"
    url = "ax/"
    weight = 0
```

- [ ] **Step 4: Run test + a real hugo build sanity**

Run: `python3 -m pytest tests/test_ax.py -k hugo -q`
Expected: PASS.

Run (no pipe): `hugo --minify --cleanDestinationDir --buildFuture --baseURL "https://beaten-to-it.github.io/ai-daily/"`
Expected: exit 0 (config valid; menu/mainSections parse).

- [ ] **Step 5: Commit**

```bash
git add hugo.toml tests/test_ax.py
git commit -m "feat(ax): hugo menu (AX 경영, weight 0) + mainSections ax"
```

---

### Task 5: email.py — read_content 3섹션 (AX 포함)

**Files:**
- Modify: `nbs/email.py`
- Test: `tests/test_email.py`

**Interfaces:**
- Produces: `read_content(date) -> tuple[str, str | None, str | None]` (news, usecase, ax). `run_email` body = News + UseCase + AX 3섹션.

- [ ] **Step 1: Update existing tests + add ax test in `tests/test_email.py`**

The two existing `read_content` tests unpack a 2-tuple — update them to 3-tuple, and add ax coverage. Replace `test_read_content_from_origin_main` and `test_read_content_news_only_when_no_usecase`:

```python
def test_read_content_from_origin_main(tmp_path, monkeypatch):
    from nbs import email as em, publish
    work = _init_repo_with_origin(tmp_path)
    monkeypatch.setattr(publish, "ROOT", work)
    _publish_day(work, "2026-07-03", usecase=True)
    (work / "content" / "news" / "2026-07-03.md").write_text("TAMPERED", encoding="utf-8")
    news, uc, ax = em.read_content("2026-07-03")
    assert "News" in news and "TAMPERED" not in news
    assert uc is not None and "UseCase" in uc
    assert ax is None   # _publish_day writes no ax

def test_read_content_news_only_when_no_usecase(tmp_path, monkeypatch):
    from nbs import email as em, publish
    work = _init_repo_with_origin(tmp_path)
    monkeypatch.setattr(publish, "ROOT", work)
    _publish_day(work, "2026-07-03", usecase=False)
    news, uc, ax = em.read_content("2026-07-03")
    assert uc is None and ax is None

def test_read_content_includes_ax(tmp_path, monkeypatch):
    from nbs import email as em, publish
    work = _init_repo_with_origin(tmp_path)
    monkeypatch.setattr(publish, "ROOT", work)
    _publish_day(work, "2026-07-03", usecase=True)
    (work / "content" / "ax").mkdir(parents=True)
    (work / "content" / "ax" / "2026-07-03.md").write_text("---\ntitle: AX\n---\n경영 본문\n", encoding="utf-8")
    _git(work, "add", "-A"); _git(work, "commit", "-m", "ax"); _git(work, "push", "origin", "HEAD:refs/heads/main")
    news, uc, ax = em.read_content("2026-07-03")
    assert ax is not None and "경영 본문" in ax
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_email.py -k read_content -q`
Expected: FAIL — `too many values to unpack` / `read_content` returns 2-tuple.

- [ ] **Step 3: Implement**

In `nbs/email.py`, change `read_content`:

```python
def read_content(date: str) -> tuple[str, str | None, str | None]:
    """Return (news_md, usecase_md_or_None, ax_md_or_None) — all read from origin/main (gate ref)."""
    news = _origin_show(f"content/news/{date}.md")
    if news is None:
        raise FileNotFoundError(f"origin/main has no content/news/{date}.md")
    usecase = _origin_show(f"content/usecase/{date}.md")   # None => omit section
    ax = _origin_show(f"content/ax/{date}.md")             # None => omit section
    return news, usecase, ax
```

In `run_email`, update the unpack and body assembly:

```python
    news_md, usecase_md, ax_md = read_content(date)
    subject = subject_for(news_md, date)
    web_url = f"{config.SITE_BASEURL.rstrip('/')}/news/{date}/"
    body_md = preprocess(news_md)
    if usecase_md is not None:
        body_md += "\n\n---\n\n" + preprocess(usecase_md)
    if ax_md is not None:
        body_md += "\n\n---\n\n" + preprocess(ax_md)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_email.py -q`
Expected: PASS (all email tests; read_content now 3-tuple).

- [ ] **Step 5: Full regression**

Run: `python3 -m pytest -q`
Expected: PASS (190 prior + new ax tests, all green).

- [ ] **Step 6: Commit**

```bash
git add nbs/email.py tests/test_email.py
git commit -m "feat(ax): email read_content 3-tuple + AX section in daily mail body"
```

---

### Task 6: 오늘치(2026-07-03) AX 경영 생성 + grounding eyeball + 발행

> 실행 태스크(1회 롤아웃). **재-stage 금지**(claude -p 재호출 = 비결정 → 이미 발행된 14개 포스트가 바뀔 위험). 대신 **기존 generation.json + 온디스크 포스트로 results 재구성**해 `build_ax`만 결정적으로 돌려 ax를 **추가**(기존 콘텐츠 무변경).

- [ ] **Step 1: 오늘 results 재구성 + build_ax (claude -p 1회, Claude env)**

Run (no pipe):

```bash
cd /home/beaten/project/NBs && export PATH="$HOME/.local/bin:$PATH"
python3 - <<'PY'
import json
from pathlib import Path
from nbs import assemble
from nbs.models import GenerationResult
date = "2026-07-03"
gen = json.loads(Path(f"runs/{date}/generation.json").read_text(encoding="utf-8"))
results = []
for d in gen["results"]:
    fields = {k: d[k] for k in ("event_key","title","url","source","source_type",
              "evidence_level","status","post_path","slug","rank","rationale","error") if k in d}
    r = GenerationResult(**fields)
    p = Path(f"content/posts/{r.slug}.md")
    r._md = p.read_text(encoding="utf-8") if p.exists() else ""   # for _blog_snippet
    results.append(r)
ax_md = assemble.build_ax(results, date)   # raises if ungrounded (gate) -> iterate prompt
Path(f"runs/{date}/staging/ax").mkdir(parents=True, exist_ok=True)
Path(f"runs/{date}/staging/ax/{date}.md").write_text(ax_md, encoding="utf-8")
gen["ax_error"] = None
Path(f"runs/{date}/generation.json").write_text(json.dumps(gen, ensure_ascii=False, indent=2), encoding="utf-8")
print("AX staged. chars:", len(ax_md))
PY
```

Expected: `AX staged. chars: <N>`. If `build_ax` raises (gate reject = ungrounded), the prompt needs a pass — do NOT force-publish.

- [ ] **Step 2: ⚠️ Grounding eyeball (spec §16 rollout gate — 필수)**

Run (no pipe): `cat runs/2026-07-03/staging/ax/2026-07-03.md`

Read the **prose substance**, not just link presence: is each management claim actually derived from its linked item (오픈AI 지분·삼성 칩·메타 클라우드·클플 등), or is the link ornamental and the body generic (fig-leaf)? If fig-leaf/evergreen → STOP, revise `prompts/ax.md`, regenerate. "게이트 통과"가 "grounded"를 대체하지 않는다.

- [ ] **Step 3a: Pre-publish drift guard (Codex R1 — BLOCK)**

`publish.promote` re-copies ALL of `staging/{posts,news,usecase}` → `content/`, not just ax. To guarantee "기존 콘텐츠 무변경", confirm the staging that will be re-promoted is byte-identical to what's already published, BEFORE publishing:

Run (no pipe):

```bash
cd /home/beaten/project/NBs
DRIFT=0
for f in $(ls runs/2026-07-03/staging/posts/*.md) runs/2026-07-03/staging/news/2026-07-03.md runs/2026-07-03/staging/usecase/2026-07-03.md; do
  rel="content/${f#runs/2026-07-03/staging/}"
  if ! diff -q "$f" "$rel" >/dev/null 2>&1; then echo "DRIFT: $f vs $rel"; DRIFT=1; fi
done
echo "DRIFT=$DRIFT (0=staging matches published content, safe to re-promote)"
```

Expected: `DRIFT=0`. If `DRIFT=1`, STOP — re-promoting would overwrite live content; investigate (do not publish/push).

- [ ] **Step 3b: Publish (ax 포함 승격 + 빌드검증 + 로컬 커밋)**

Run (no pipe):

```bash
cd /home/beaten/project/NBs && export PATH="$HOME/.local/bin:$PATH"
python3 -m nbs.publish --date 2026-07-03 > runs/2026-07-03/publish.log 2>&1
echo "PUBLISH_EXIT=$?"
python3 -c "import json;d=json.load(open('runs/2026-07-03/publish.json'));print('status:',d['status'],'promoted:',len(d['promoted']),'error:',d.get('error'))"
test -f content/ax/2026-07-03.md && echo "content/ax present" || echo "MISSING ax"
```

Expected: `status: published`, `content/ax/2026-07-03.md` present, exit 0.

- [ ] **Step 4: Verify commit scope, then push + verify live**

Run (no pipe) — confirm the publish commit touched ONLY the new ax page (+ possibly ledger), nothing else:

```bash
cd /home/beaten/project/NBs
echo "=== commit scope (must be only content/ax/2026-07-03.md, optionally data/published.csv) ==="
git show --stat --oneline HEAD
```

If `git show --stat HEAD` lists any `content/posts/*`, `content/news/*`, or `content/usecase/*` change, STOP — the re-promote altered live content; do NOT push. Otherwise push:

```bash
git push origin HEAD:refs/heads/main 2>&1
```

After Actions completes (~1-2 min), verify:

```bash
curl -s -o /dev/null -w "ax page HTTP %{http_code}\n" "https://beaten-to-it.github.io/ai-daily/ax/2026-07-03/"
curl -s -o /dev/null -w "home HTTP %{http_code}\n" "https://beaten-to-it.github.io/ai-daily/"
```

Expected: ax page HTTP 200, "AX 경영" menu visible in nav.

> Note: 이 롤아웃 커밋을 push하려면 `ax-management` 브랜치가 아니라 **머지 후 main**에서 해야 origin/main 배포가 맞다. Task 6는 **Task 1–5 머지 완료 후** 실행(finishing-a-development-branch → main 머지 → 그 위에서 Task 6). 브랜치에서 미리 실행 금지.

---

## Self-Review (작성자 체크)

- **Spec §16 coverage:** synthesis+optional=T1(build_ax None) · grounding 게이트 (a)(b)(c)=T1 · 프롬프트 item-앵커=prompts/ax.md · stage ax_error §5=T2 · publish writeset/promote/build_verify/_degraded=T3 · menu+mainSections=T4 · email 3섹션=T5 · 오늘치+eyeball=T6 · v1 한계(select 편향)=설계 명시(코드 무관). ✅
- **Placeholder scan:** 없음. 모든 스텝 실코드/실명령. ✅
- **Type consistency:** `build_ax(results,date,*,run=None)->str|None`, `read_content->3-tuple`, `stage.run(...,ax=None)`, `promote/date_writeset/build_verify/_degraded` ax 추가 — 태스크 간 일치. 게이트 angle 정규식 = `publish._RELREF.pattern` wrap(email `_RELREF_FULL`와 동형). ✅
- **Import cycle:** `build_ax`의 `from . import publish`는 함수레벨(호출시 로드완료) — assemble 모듈로드 시 publish 임포트 안 함. ✅

## 적대리뷰 이력 (2R 게이트 통과)
- **R1:** **advisor** 2 지적 → 실코드 검증으로 **둘 다 non-bug 확인**(stage `from .config import run_dir` bare name → monkeypatch 유효 / Task6 재구성 publishable=14·`_blog_snippet`이 front matter strip=prose). **Codex** 2 — BLOCK: Task6 "기존 콘텐츠 무변경"이 명령상 미보장(promote가 staging 전체 재승격) → **pre-publish drift guard(DRIFT=0) + post-commit scope check** 추가. MAJOR: `build_verify` ax 실패테스트 부재(구현자 누락해도 통과) → **mock `_hugo_build` ax 브랜치 테스트** 추가. ①~⑥(import cycle·angle 정규식 email 동형·run_dir·publish 평행·email 3튜플·Task6 결정성) 전부 sound 확인.
- **R2 수렴:** advisor=converged. **Codex="수렴: 신규 BLOCK/모순 없음"** + drift guard 라이브 실행 `DRIFT=0`(오늘 staging==발행 content 확인). **2R 캡 — 종료.**
- **실행 시 유의(자동 게이트가 못 잡는 것):** Task6 Step2 grounding **eyeball이 진짜 게이트**(구조검증 아닌 산문 실질 — 각 주장이 링크 항목서 도출됐나). 오늘=최악신호일·실명 발행. Task6 Step1은 실 `claude -p`(Claude env), `build_ax`가 게이트로 raise 가능=정상. 별개 미결: `generate.py` title-YAML sanitize(오늘 아침 실런서 발견, 다음 발행 재발 — 이 계획 범위 밖, 메모리 기록됨).
