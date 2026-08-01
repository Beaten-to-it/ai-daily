# Codex Windows AI Daily Publisher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 AI Daily의 사이트·이력·발행 안전장치를 보존하면서 Windows에서 Codex로 수집, 선별, 작성, 검증, 오전 7시 게시 준비를 수행하는 파이프라인을 구축한다.

**Architecture:** 기존 `collect -> select -> stage -> publish -> push -> email` 경계를 유지한다. Python이 수집, 상태 전이, 검증과 외부 변경을 소유하고 Codex CLI는 격리된 읽기 전용 작업 디렉터리에서 구조화된 편집 판단과 한국어 원고만 생성한다.

**Tech Stack:** Python 3.13, pytest, requests, feedparser, Codex CLI 0.144.1+, Hugo Extended, Git, PowerShell, Windows Task Scheduler, Gmail API.

## Global Constraints

- 작업 플랫폼은 Windows 네이티브이며 WSL 절대 경로, Bash, systemd, `fcntl`, Linux 프로세스 그룹 또는 브라우저 브리지를 런타임에 요구하지 않는다.
- 기존 Git 이력, Hugo/PaperMod, 기존 콘텐츠 URL과 `data/published.csv`를 보존한다.
- 일반 기사 목표는 30편 이상이며 개수 상한은 두지 않는다. 10~29편은 정상, 1~9편은 경고 발행, 0편은 발행 중단이다.
- 종합 리포트, 개별 기사, 경영 브리핑, 활용 가이드는 각각 `daily`, `articles`, `executive`, `guides`에 저장한다.
- 홈페이지, 기본 RSS와 기본 이메일에는 `daily`만 노출한다.
- 발행문은 한국어이며 원문 본문을 복제하지 않고 확인된 원출처 링크만 제공한다.
- Codex 출력의 URL, 출처, 유형은 수집 후보가 제공한 값을 변경할 수 없다.
- 실제 커밋, 푸시, 이메일 발송, Task Scheduler 등록, WSL timer 중지는 사용자의 별도 승인 전에는 실행하지 않는다.
- 구현 중 커밋 단계는 승인 전까지 체크하지 않고 로컬 diff로 유지한다.

---

## File Map

### Create

- `nbs/locking.py`: Windows와 POSIX에서 동일하게 사용하는 비차단 파일 잠금.
- `nbs/codex_cli.py`: 격리된 `codex exec` 구조화 출력 호출 한 곳.
- `schemas/selection.schema.json`: 모든 후보의 선택·제외 결정을 강제하는 출력 스키마.
- `schemas/article.schema.json`: 개별 기사 Markdown을 감싼 출력 스키마.
- `schemas/derived.schema.json`: 경영 브리핑·가이드의 게시 여부와 Markdown 스키마.
- `tests/test_locking.py`: 교차 플랫폼 잠금 검증.
- `tests/test_codex_cli.py`: Codex 명령, 격리, 오류 보존 검증.
- `tests/test_source_health.py`: 수집원 상태와 장애 집계 검증.
- `tests/test_content_routes.py`: 새 콘텐츠 경로와 홈페이지 분리 검증.
- `tests/test_end_to_end.py`: 네트워크와 외부 변경 없는 전체 파이프라인 검증.
- `scripts/run_daily.ps1`: Task Scheduler가 호출할 Windows 진입점.
- `scripts/install_scheduler.ps1`: 실행 파일과 절대 경로를 검증하고 예약 작업 정의를 생성하는 설치 스크립트.
- `docs/operations/windows-publisher.md`: 자격증명, 섀도 실행, 전환과 롤백 절차.

### Modify

- `nbs/models.py`: 후보 provenance, 후보 ID, 수집원 상태, 완전한 선별 결정 모델.
- `nbs/sources.py`: 검증된 RSS, Bluesky 계정, X 검색어, Reddit 목록, GitHub 저장소, 웹 검색어.
- `nbs/collect.py`: 공식 API 수집, 경로별 상태 기록, 후보 원출처 보존.
- `nbs/select.py`: Claude 제거, Codex 구조화 선별, 무상한 선별, 전 후보 결정 검증.
- `nbs/generate.py`: Claude 제거, Codex 기사 생성, 원출처 불변성 및 원문 비복제 검증.
- `nbs/assemble.py`: `daily`, `executive`, `guides` 조립과 `1/9/10/30` 발행량 정책.
- `nbs/stage.py`: 새 스테이징 경로, 선택적 파생 콘텐츠, 체크포인트 재사용.
- `nbs/publish.py`: 새 날짜 쓰기 집합, 검증, 승격과 롤백.
- `nbs/email.py`: 기본 이메일을 `daily` 한 종류로 제한하고 Windows 외부 설정 경로 사용.
- `nbs/orchestrate.py`: 교차 플랫폼 잠금, `prepare`와 `publish` 재개 단계, 섀도 모드.
- `nbs/schedule.py`: Chrome·Browser Bridge 제거, Windows 전제 없는 실행 전 검증.
- `hugo.toml`: 홈페이지를 `daily`로 한정하고 새 메뉴 구성.
- `prompts/select.md`: 모든 후보 결정과 의미 기준.
- `prompts/blog.md`: 한국어 기사 구조와 원문 비복제 규칙.
- `prompts/ax.md`: `executive` 전용 파생 콘텐츠.
- `prompts/usecase.md`: 게시하지 않을 수 있는 `guides` 결정.
- 기존 `tests/test_*.py`: 경로, Codex 호출, 발행량과 Windows 계약에 맞게 갱신.
- `README.md`: Windows 실행과 섀도 검증 진입점.
- `.gitignore`: 로컬 도구와 Windows 실행 산출물 제외.

---

### Task 1: Windows에서 테스트 가능한 실행 기반 만들기

**Files:**
- Create: `nbs/locking.py`
- Create: `tests/test_locking.py`
- Modify: `nbs/orchestrate.py`
- Modify: `nbs/schedule.py`
- Modify: `tests/test_orchestrate.py`
- Modify: `tests/test_schedule.py`

**Interfaces:**
- Produces: `exclusive_lock(path: Path) -> ContextManager[None]`
- Consumes: 기존 `config.ROOT`, `.orchestrate.lock`, `.schedule.lock`

- [x] **Step 1: Windows 잠금 실패 테스트 작성**

```python
def test_exclusive_lock_rejects_second_holder(tmp_path):
    path = tmp_path / "run.lock"
    with exclusive_lock(path):
        with pytest.raises(BusyLock):
            with exclusive_lock(path):
                pass
```

- [x] **Step 2: 기준선 실패 확인**

Run: `python -m pytest tests/test_locking.py tests/test_orchestrate.py::test_lock_is_exclusive -q`

Expected: `nbs.locking`이 없거나 Windows에서 기존 `fcntl` import가 실패한다.

- [x] **Step 3: 표준 라이브러리 잠금 구현**

```python
class BusyLock(RuntimeError):
    pass

@contextlib.contextmanager
def exclusive_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if path.stat().st_size == 0:
            handle.write(b"0")
            handle.flush()
        _lock_one_byte(handle)
        try:
            yield
        finally:
            _unlock_one_byte(handle)
```

`_lock_one_byte`는 Windows에서 `msvcrt.LK_NBLCK`, POSIX에서 `fcntl.LOCK_EX | LOCK_NB`를 사용한다. `orchestrate`와 `schedule`의 중복 잠금 코드를 이 함수로 교체한다.

- [x] **Step 4: Windows에서 테스트 수집과 잠금 테스트 통과 확인**

Run: `python -m pytest tests/test_locking.py tests/test_orchestrate.py tests/test_schedule.py -q`

Expected: 테스트 수집 오류가 사라지고 잠금 관련 테스트가 통과한다. Chrome 관련 기존 테스트는 Task 4에서 제거될 때까지 동작을 유지한다.

- [x] **Step 5: 전체 기준선 기록**

Run: `python -m pytest -q`

Expected: `fcntl`로 인한 collection error가 0건이다. 남는 실패는 후속 작업에 매핑해 계획 체크리스트에 기록한다.

- [ ] **Step 6: 승인 후에만 커밋**

```powershell
git add nbs/locking.py nbs/orchestrate.py nbs/schedule.py tests/test_locking.py tests/test_orchestrate.py tests/test_schedule.py
git commit -m "refactor: make publisher locking work on Windows"
```

---

### Task 2: Codex CLI 구조화 출력 어댑터 도입

> 구현·테스트·라이브 스모크를 완료했다. 사용자 승인 15분 창에서 `claude-opus-5`, `xhigh` 유효 리뷰가 완료됐고 `Critical=0`, `High=0`으로 게이트를 통과했다. 처분 원장은 `reviews/2026-08-01-task2-codex-exec.md`에 있다.

**Files:**
- Create: `nbs/codex_cli.py`
- Create: `schemas/selection.schema.json`
- Create: `schemas/article.schema.json`
- Create: `schemas/derived.schema.json`
- Create: `tests/test_codex_cli.py`
- Modify: `nbs/select.py`
- Modify: `nbs/generate.py`
- Modify: `nbs/assemble.py`
- Modify: `tests/test_select.py`
- Modify: `tests/test_generate.py`
- Modify: `tests/test_ax.py`

**Interfaces:**
- Produces: `run_json(prompt: str, schema: Path, work_dir: Path, timeout: int) -> dict`
- Produces: `CodexExecError` containing exit code, timeout state, and bounded stderr.
- Consumes: saved `codex login` authentication; no API key in the repository.

- [x] **Step 1: 명령 격리 테스트 작성**

```python
def test_run_json_uses_isolated_read_only_exec(monkeypatch, tmp_path):
    seen = {}
    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["input"] = kwargs["input"]
        Path(args[args.index("--output-last-message") + 1]).write_text('{"ok":true}', encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert run_json("prompt", SCHEMA, tmp_path, 30) == {"ok": True}
    assert "--ephemeral" in seen["args"]
    assert seen["args"][seen["args"].index("--sandbox") + 1] == "read-only"
    assert "--ignore-user-config" in seen["args"]
    assert "--ignore-rules" in seen["args"]
    assert seen["args"][-1] == "-"
```

- [x] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_codex_cli.py -q`

Expected: `nbs.codex_cli`가 없어 실패한다.

- [x] **Step 3: 최소 어댑터 구현**

```python
def run_json(prompt: str, schema: Path, work_dir: Path, timeout: int) -> dict:
    output = work_dir / "last-message.json"
    args = [
        "codex", "exec", "--ephemeral", "--sandbox", "read-only",
        "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check",
        "--cd", str(work_dir), "--output-schema", str(schema.resolve()),
        "--output-last-message", str(output), "-",
    ]
    result = subprocess.run(args, input=prompt, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise CodexExecError(result.returncode, result.stderr[-2000:])
    return json.loads(output.read_text(encoding="utf-8"))
```

작업 디렉터리는 `runs/<date>/codex-work/<operation>/`만 사용한다. Codex가 생성한 파일을 신뢰하지 않고 `last-message.json`만 읽는다.

- [x] **Step 4: Claude 호출을 한 곳씩 교체**

`select.run_claude`, `generate.run_claude_notools`, AX와 usecase의 직접 호출을 제거하고 `run_json`으로 교체한다. 선택은 `selection.schema.json`, 개별 기사는 `article.schema.json`, 파생 콘텐츠는 `derived.schema.json`을 사용한다.

- [x] **Step 5: 단위 테스트 통과 확인**

Run: `python -m pytest tests/test_codex_cli.py tests/test_select.py tests/test_generate.py tests/test_ax.py -q`

Expected: 명령 배열에 `claude`, `--tools`, `--effort`가 없고 Codex 오류의 stderr가 실행 기록에 남는다.

- [x] **Step 6: 합성 데이터 라이브 스모크**

Run: `python -m nbs.codex_cli --self-test`

Expected: 저장된 ChatGPT 인증으로 `{"ok": true}` 스키마 결과를 받고 작업 디렉터리 밖에는 파일이 생기지 않는다.

- [ ] **Step 7: 승인 후에만 커밋**

```powershell
git add nbs/codex_cli.py nbs/select.py nbs/generate.py nbs/assemble.py schemas tests/test_codex_cli.py tests/test_select.py tests/test_generate.py tests/test_ax.py
git commit -m "feat: replace Claude generation with isolated Codex exec"
```

---

### Task 3: 후보 provenance와 전 후보 결정 완전성 적용

> 구현과 회귀 테스트를 완료했다. `claude-opus-5`, `xhigh` 유효 리뷰에서 `Critical=0`, `High=0`으로 통과했으며 처분 원장은 `reviews/2026-08-01-task3-provenance-decisions.md`에 있다.

**Files:**
- Modify: `nbs/models.py`
- Modify: `nbs/collect.py`
- Modify: `nbs/select.py`
- Modify: `nbs/ledger.py`
- Modify: `prompts/select.md`
- Modify: `schemas/selection.schema.json`
- Modify: `tests/test_models.py`
- Modify: `tests/test_collect.py`
- Modify: `tests/test_select.py`
- Modify: `tests/test_hardening.py`

**Interfaces:**
- Produces: `candidate_id(url: str) -> str`
- Produces: `Candidate.lane`, `Candidate.discovered_via`, immutable publisher/type/url fields.
- Produces: `selection.json` containing selected `items` and one `decisions` row per candidate.

- [x] **Step 1: 필드 불변성과 완전성 실패 테스트 작성**

```python
def test_selection_requires_exactly_one_decision_per_candidate():
    candidates = [candidate("https://a.example/x"), candidate("https://b.example/y")]
    model = {"date": "2026-08-01", "decisions": [decision(candidates[0], "select")]}
    assert validate_decision_coverage(model, candidates) == ["missing decision: " + candidates[1]["candidate_id"]]

def test_selected_source_fields_come_from_candidate_not_model():
    item = materialize_selected(candidate(source="OpenAI", source_type="article"), decision())
    assert item["source"] == "OpenAI"
    assert item["source_type"] == "article"
```

- [x] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_models.py tests/test_select.py -q`

Expected: 후보 ID, provenance 필드와 결정 완전성 함수가 없어 실패한다.

- [x] **Step 3: 안정적인 후보 ID와 모델 정의**

```python
def candidate_id(url: str) -> str:
    normalized = canonicalize_url(url).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:20]

@dataclass
class Candidate:
    source: str
    source_type: str
    title: str
    url: str
    canonical_url: str
    published_at: str | None
    snippet: str
    raw_id: str
    lane: str = "official"
    discovered_via: str = ""
```

- [x] **Step 4: 모든 후보에 결정 요구**

모델 출력은 `candidate_id`, `decision`, `dedup`, `prior_post_path`, `rank`, `reason_code`, `rationale`만 포함한다. `decision`은 `select|skip`, `reason_code`는 `selected|duplicate|stale|weak_evidence|low_significance|off_topic`으로 제한한다. 로컬 join이 후보의 제목, URL, 출처와 유형을 최종 `items`에 복사한다.

- [x] **Step 5: 고정 상한 제거와 집계 교정**

`MAX_SELECTED`와 truncate 로직을 삭제한다. `selected_count`는 `select` 결정 수, `skipped_count`는 전체 후보 수에서 선택 수를 뺀 값으로 로컬 계산한다. 모델이 선언한 카운트는 사용하지 않는다.

- [x] **Step 6: 회귀 테스트**

Run: `python -m pytest tests/test_models.py tests/test_collect.py tests/test_select.py tests/test_hardening.py -q`

Expected: 31개의 유의미한 결정을 잘라내지 않으며, 누락·중복 후보 ID와 변조된 provenance를 거부한다.

- [ ] **Step 7: 승인 후에만 커밋**

```powershell
git add nbs/models.py nbs/collect.py nbs/select.py nbs/ledger.py prompts/select.md schemas/selection.schema.json tests/test_models.py tests/test_collect.py tests/test_select.py tests/test_hardening.py
git commit -m "feat: make editorial decisions complete and provenance-safe"
```

---

### Task 4: RSS·SNS·개발·웹 수집 확대와 상태 기록

**Files:**
- Modify: `nbs/sources.py`
- Modify: `nbs/collect.py`
- Modify: `nbs/models.py`
- Modify: `nbs/fetch.py`
- Create: `tests/test_source_health.py`
- Modify: `tests/test_sources.py`
- Modify: `tests/test_collect.py`
- Modify: `tests/test_fetch.py`
- Modify: `tests/test_models.py`
- Modify: `tests/test_select.py`
- Modify: `tests/test_hardening.py`
- Modify: `nbs/schedule.py`
- Modify: `tests/test_schedule.py`

**Interfaces:**
- Produces: `collect(date) -> tuple[list[Candidate], list[SourceHealth]]`
- Produces: `runs/<date>/source_health.json`
- Consumes optional environment variables: `AI_DAILY_X_BEARER`, `AI_DAILY_REDDIT_CLIENT_ID`, `AI_DAILY_REDDIT_CLIENT_SECRET`, `AI_DAILY_GITHUB_TOKEN`.

- [x] **Step 1: 경로별 실패 격리 테스트 작성**

```python
def test_failed_social_lane_is_visible_but_does_not_drop_rss(monkeypatch):
    monkeypatch.delenv("AI_DAILY_X_BEARER", raising=False)
    candidates, health = collect_with([ok_rss_adapter(), x_adapter()])
    assert len(candidates) == 1
    assert health_by_name(health, "x").status == "unconfigured"
```

- [x] **Step 2: 수집원 상태 모델 구현**

```python
@dataclass
class SourceHealth:
    lane: str
    name: str
    status: str       # ok | empty | unconfigured | degraded | failed
    candidate_count: int
    elapsed_ms: int
    error: str = ""
```

오류 문자열은 500자로 제한하고 토큰이나 요청 헤더를 기록하지 않는다.

- [x] **Step 3: 초기 RSS 목록 확대**

기존 피드에 2026-08-01 실제 HTTP 200과 feed content type을 확인한 다음 피드를 추가한다.

```python
RSS_FEEDS += [
    {"name": "AWS ML", "url": "https://aws.amazon.com/blogs/machine-learning/feed/", "source_type": "article", "lane": "official"},
    {"name": "NVIDIA Developer", "url": "https://developer.nvidia.com/blog/feed/", "source_type": "article", "lane": "official"},
    {"name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml", "source_type": "article", "lane": "official"},
    {"name": "GitHub Changelog", "url": "https://github.blog/changelog/feed/", "source_type": "article", "lane": "developer"},
    {"name": "AI타임스", "url": "https://www.aitimes.com/rss/allArticle.xml", "source_type": "article", "lane": "media"},
]
```

404/410을 확인한 Anthropic, Microsoft AI, Meta RSS 추정 주소는 넣지 않는다.

- [x] **Step 4: 공식 공개 API 어댑터 구현**

- Hacker News: `https://hacker-news.firebaseio.com/v0/newstories.json`과 `/v0/item/<id>.json`
- Bluesky: `https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed`, 검증된 계정 `simonwillison.net`, `emollick.bsky.social`, `hardmaru.bsky.social`, `jeremyphoward.bsky.social`, `jackclark.bsky.social`
- GDELT DOC 2.0: `https://api.gdeltproject.org/api/v2/doc/doc`, `mode=artlist`, `format=json`, `timespan=1day`
- GitHub releases: `https://api.github.com/repos/<owner>/<repo>/releases`, 공개 요청은 무인증으로 시작하고 토큰이 있으면 rate limit만 높인다.

각 API는 공통 `requests.Session`, connect/read timeout, 응답 바이트 상한과 기존 public-host 검증을 사용한다.

- [x] **Step 5: 선택적 공식 인증 어댑터 구현**

- X: `GET https://api.x.com/2/tweets/search/recent`, `AI_DAILY_X_BEARER`가 없으면 `unconfigured`.
- Reddit: OAuth와 공식 `/r/<subreddit>/new` listing, client ID/secret이 없거나 접근이 거부되면 `unconfigured` 또는 `failed`.

비공식 `twitter` CLI, `opencli`, Chrome 실행·종료 코드를 삭제한다.

- [x] **Step 6: 원출처 승격 규칙 테스트**

SNS나 GDELT 항목이 공식 발표 URL을 포함하면 후보 `url`을 공식 URL로 만들고 `discovered_via`에 SNS/API URL을 남긴다. 공식 URL을 확인하지 못한 SNS 최초 발표만 SNS URL을 증거 URL로 유지한다.

- [x] **Step 7: 수집 회귀 테스트**

Run: `python -m pytest tests/test_sources.py tests/test_collect.py tests/test_source_health.py tests/test_schedule.py -q`

Expected: 모든 어댑터의 성공·empty·unconfigured·failed 상태가 기록되고 한 어댑터 실패가 다른 후보를 지우지 않는다.

- [x] **Step 8: 읽기 전용 라이브 수집 스모크**

Run: `python -m nbs.collect --date 2026-08-01`

Expected: `runs/2026-08-01/candidates.json`과 `source_health.json`이 생성되고 RSS, HN, Bluesky, GDELT 중 둘 이상의 경로가 `ok`다. 저장소 콘텐츠와 Git 상태는 바뀌지 않는다.

- [ ] **Step 9: 승인 후에만 커밋**

```powershell
git add nbs/sources.py nbs/collect.py nbs/models.py nbs/fetch.py nbs/schedule.py tests/test_sources.py tests/test_collect.py tests/test_source_health.py tests/test_fetch.py tests/test_models.py tests/test_select.py tests/test_hardening.py tests/test_schedule.py
git commit -m "feat: expand observable AI news collection"
```

---

### Task 5: 콘텐츠 경로와 파생 콘텐츠 분리

**Files:**
- Create: `tests/test_content_routes.py`
- Modify: `nbs/generate.py`
- Modify: `nbs/assemble.py`
- Modify: `nbs/stage.py`
- Modify: `prompts/blog.md`
- Modify: `prompts/ax.md`
- Modify: `prompts/usecase.md`
- Modify: `schemas/article.schema.json`
- Modify: `schemas/derived.schema.json`
- Modify: `hugo.toml`
- Modify: `tests/test_generate.py`
- Modify: `tests/test_assemble.py`
- Modify: `tests/test_stage.py`
- Modify: `tests/test_ax.py`

**Interfaces:**
- Produces: article `post_path="articles/<date>-<event-key>.md"`.
- Produces: `build_daily(results, date) -> str`.
- Produces: optional `build_executive` and `build_guide` returning `str | None`.

- [ ] **Step 1: 콘텐츠 혼합 방지 테스트 작성**

```python
def test_home_only_lists_daily():
    config = Path("hugo.toml").read_text(encoding="utf-8")
    assert 'mainSections = ["daily"]' in config

def test_stage_routes_are_disjoint(tmp_path):
    out = stage_with_three_articles(tmp_path)
    assert exists("staging/articles/2026-08-01-a.md")
    assert exists("staging/daily/2026-08-01.md")
    assert not exists("staging/posts/2026-08-01-a.md")
```

- [ ] **Step 2: 기사 출력 계약 변경**

`article.schema.json`은 `{"markdown": "..."}`만 허용한다. Markdown front matter는 `title`, `date`, `tags`, `source_url`, `source_name`, `source_published_at`, `source_lang`, `source_type`, `evidence_level`, `event_key`를 요구한다. `source_url`과 `event_key`는 로컬 후보와 정확히 일치해야 한다.

프롬프트는 원문 본문이나 긴 직접 인용을 금지하고 `무엇이 있었나`, `왜 중요한가`, `확인 범위`, `출처` 구조를 요구한다.

- [ ] **Step 3: 일일 리포트 경로 변경**

```python
article_link = '{{< relref "/articles/%s.md" >}}' % result.slug
```

`build_news_index`를 `build_daily`로 이름을 바꾸고 `content/daily/<date>.md`를 생성한다. 기존 `/news/`와 `/posts/` 콘텐츠는 이동하지 않는다.

- [ ] **Step 4: 경영과 가이드의 선택적 출력**

`derived.schema.json`은 `publish: boolean`, `markdown: string`을 요구한다. `publish=false`면 해당 파일을 생성하지 않는다. AX는 `executive`, usecase는 `guides`로 이름을 바꾸고 새 개별 기사 slug만 참조하도록 검증한다.

- [ ] **Step 5: Hugo 홈페이지와 메뉴 분리**

```toml
[params]
  mainSections = ["daily"]

[[menu.main]]
  name = "Daily"
  url = "daily/"
  weight = 1
```

그 뒤 `Articles`, `Executive`, `Guides`, `Tags` 메뉴를 독립 경로로 추가한다. 기존 경로 메뉴는 제거하되 기존 URL 콘텐츠는 보존한다.

- [ ] **Step 6: 기사 수 경계 정책 적용**

```python
def volume_status(count: int) -> str:
    if count == 0:
        return "empty"
    if count < 10:
        return "warning"
    return "normal"
```

30은 리포트의 목표 지표로만 기록하고 게시 차단 조건으로 사용하지 않는다.

- [ ] **Step 7: 콘텐츠 테스트**

Run: `python -m pytest tests/test_generate.py tests/test_assemble.py tests/test_stage.py tests/test_ax.py tests/test_content_routes.py -q`

Expected: `0/1/9/10/30` 경계가 승인된 정책과 일치하고 네 콘텐츠 유형의 경로가 겹치지 않는다.

- [ ] **Step 8: 승인 후에만 커밋**

```powershell
git add nbs/generate.py nbs/assemble.py nbs/stage.py prompts schemas hugo.toml tests/test_generate.py tests/test_assemble.py tests/test_stage.py tests/test_ax.py tests/test_content_routes.py
git commit -m "feat: separate daily articles executive and guides"
```

---

### Task 6: 게시, 롤백과 기본 이메일을 새 경로에 연결

**Files:**
- Modify: `nbs/publish.py`
- Modify: `nbs/email.py`
- Modify: `nbs/orchestrate.py`
- Modify: `tests/test_publish.py`
- Modify: `tests/test_email.py`
- Modify: `tests/test_orchestrate.py`

**Interfaces:**
- Produces: 날짜 쓰기 집합 `articles + daily + optional executive + optional guides + ledger`.
- Produces: `read_content(date) -> str` returning only the daily Markdown.

- [ ] **Step 1: 새 쓰기 집합과 이메일 분리 테스트 작성**

```python
def test_date_writeset_uses_new_routes():
    paths = date_writeset(generation_fixture())
    assert "content/daily/2026-08-01.md" in paths
    assert "content/executive/2026-08-01.md" in paths
    assert all("content/news/" not in path for path in paths)

def test_default_email_reads_daily_only(monkeypatch):
    monkeypatch.setattr(email, "_origin_show", lambda path: "DAILY" if path.startswith("content/daily/") else "EXEC")
    assert email.read_content("2026-08-01") == "DAILY"
```

- [ ] **Step 2: 승격·롤백 경로 교체**

`date_writeset`, `promote`, `build_verify`, `rollback`, `head_has_news`를 새 경로에 맞춘다. 기존 날짜의 `/posts/`와 `/news/`는 날짜 쓰기 집합에 포함하지 않아 재실행이 과거 콘텐츠를 건드리지 않게 한다.

- [ ] **Step 3: 발행 게이트 교체**

- `published_count == 0`: held, Git·이메일 변경 없음
- `1 <= published_count < 10`: published with warning
- `published_count >= 10`: published normal
- source health 경고는 manifest에 기록하지만 유일한 차단 사유로 사용하지 않음

- [ ] **Step 4: 기본 이메일 단일 콘텐츠화**

`published`와 `_origin_show`가 `content/daily/<date>.md`를 사용한다. `read_content`는 tuple 대신 daily 문자열만 반환하고 `run_email`은 executive와 guides를 합치지 않는다. 웹 URL은 `/daily/<date>/`다.

- [ ] **Step 5: Windows 설정 경로 적용**

`config_dir` 기본값을 `%LOCALAPPDATA%\ai-daily`로 두고 환경변수 override를 유지한다. POSIX 권한 검사는 POSIX에서만 시행하고 Windows에서는 설치 문서의 사용자 전용 ACL 검사를 사용한다. 토큰 파일은 저장소 밖에만 둔다.

- [ ] **Step 6: 회귀 테스트**

Run: `python -m pytest tests/test_publish.py tests/test_email.py tests/test_orchestrate.py tests/test_hardening.py -q`

Expected: 게시 전 실패는 날짜 쓰기 집합을 복원하고, 성공한 원격 daily가 없으면 이메일을 보내지 않으며, 재실행도 중복 발송하지 않는다.

- [ ] **Step 7: 승인 후에만 커밋**

```powershell
git add nbs/publish.py nbs/email.py nbs/orchestrate.py tests/test_publish.py tests/test_email.py tests/test_orchestrate.py tests/test_hardening.py
git commit -m "feat: publish and email the separated daily edition"
```

---

### Task 7: 준비·게시 체크포인트와 Windows Task Scheduler 진입점

**Files:**
- Modify: `nbs/orchestrate.py`
- Modify: `nbs/schedule.py`
- Create: `scripts/run_daily.ps1`
- Create: `scripts/install_scheduler.ps1`
- Modify: `tests/test_orchestrate.py`
- Modify: `tests/test_schedule.py`
- Create: `tests/test_windows_scripts.py`

**Interfaces:**
- Produces CLI: `python -m nbs.orchestrate --date YYYY-MM-DD --prepare-only --shadow`.
- Produces CLI: `python -m nbs.orchestrate --date YYYY-MM-DD --publish-only`.
- Produces exit status: `0=success`, `2=failed/held`, `3=busy`, `4=not-ready-retry`.

- [ ] **Step 1: 준비와 게시 재개 테스트 작성**

```python
def test_prepare_only_never_calls_publish_or_email(tmp_path, monkeypatch):
    manifest = run("2026-08-01", prepare_only=True, shadow=True)
    assert manifest["status"] == "prepared"
    assert manifest["stages"]["publish"]["status"] == "skipped"

def test_publish_only_requires_validated_checkpoint(tmp_path, monkeypatch):
    manifest = run("2026-08-01", publish_only=True)
    assert manifest["status"] == "not_ready"
```

- [ ] **Step 2: 오케스트레이터 상태 전이 구현**

`STAGES`를 `collect, select, stage, validate, publish`로 확장한다. `prepare_only`는 validate 뒤 종료하고 `publish_only`는 기존 체크포인트의 날짜, 입력 해시, Git HEAD와 검증 결과가 일치할 때만 publish부터 재개한다.

- [ ] **Step 3: PowerShell 실행 래퍼 작성**

```powershell
param(
  [ValidateSet('Prepare','Publish','Alert')][string]$Mode,
  [string]$Date = (Get-Date).ToString('yyyy-MM-dd'),
  [switch]$Shadow
)
$python = (Get-Command python -ErrorAction Stop).Source
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repo
try {
  if ($Mode -eq 'Prepare') {
    $arguments = @('-m', 'nbs.orchestrate', '--date', $Date, '--prepare-only')
    if ($Shadow) { $arguments += '--shadow' }
    & $python @arguments
  }
  elseif ($Mode -eq 'Publish') { & $python -m nbs.orchestrate --date $Date --publish-only }
  else { & $python -m nbs.schedule --date $Date --check-alert }
  exit $LASTEXITCODE
} finally { Pop-Location }
```

- [ ] **Step 4: 예약 작업 설치 스크립트 작성**

스크립트는 `python`, `codex`, `git`, `hugo` 절대 경로와 `codex login status`를 검사한 뒤 다음 작업 정의를 만든다.

- `AI Daily Prepare`: 매일 06:00 KST
- `AI Daily Publish`: 매일 07:00 KST, 실패 시 10분 간격 최대 12회 재시도
- `AI Daily Alert`: 매일 12:00 KST

`-WhatIf`가 기본이며 `-Apply`를 명시해야만 `Register-ScheduledTask`를 호출한다.

- [ ] **Step 5: 스크립트 정적·단위 테스트**

Run: `python -m pytest tests/test_orchestrate.py tests/test_schedule.py tests/test_windows_scripts.py -q`

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_scheduler.ps1 -WhatIf`

Expected: 세 작업의 절대 실행 경로와 시간이 출력되지만 Task Scheduler 상태는 바뀌지 않는다.

- [ ] **Step 6: 승인 후에만 커밋**

```powershell
git add nbs/orchestrate.py nbs/schedule.py scripts/run_daily.ps1 scripts/install_scheduler.ps1 tests/test_orchestrate.py tests/test_schedule.py tests/test_windows_scripts.py
git commit -m "feat: add resumable Windows scheduling entrypoints"
```

---

### Task 8: 전체 검증, 섀도 운영 문서와 전환 게이트

**Files:**
- Create: `docs/operations/windows-publisher.md`
- Create: `tests/test_end_to_end.py`
- Modify: `README.md`
- Modify: `.gitignore`
- Modify: 필요한 회귀 테스트 파일

**Interfaces:**
- Produces documented commands for setup, dry-run, shadow, diagnosis, publish approval, rollback.
- Produces a daily run manifest containing counts, source health, decisions, warning state, stage durations, Codex stderr summary, and Git identifiers.

- [ ] **Step 1: 운영 문서에 현재 의존성 상태 기록**

문서에는 Python 3.13.13, Codex CLI 0.144.1 및 ChatGPT 로그인 확인, Windows Hugo 미설치 상태를 기록한다. Hugo Extended 설치는 사용자 승인 후 수행하거나 사용자가 지정한 기존 바이너리 경로를 사용한다.

- [ ] **Step 2: 섀도 실행 명령과 합격 조건 작성**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_daily.ps1 -Mode Prepare -Shadow
Get-Content (Join-Path 'runs' ((Get-Date -Format yyyy-MM-dd) + '\run.json'))
git status --short
```

합격 조건은 3~5일 연속으로 수집 경로 상태가 기록되고, 모든 후보 결정이 완전하며, 콘텐츠가 분리되고, Hugo 검증이 통과하며, 커밋·푸시·이메일이 0건인 것이다.

- [ ] **Step 3: 전체 자동 테스트 실행**

Run: `python -m pytest -q`

Expected: 모든 테스트 통과.

- [ ] **Step 4: Hugo 빌드 실행**

Run: `hugo --gc --minify --buildFuture`

Expected: exit code 0이며 homepage가 daily만 열거하고 articles, executive, guides가 각각 독립 section으로 생성된다.

- [ ] **Step 5: 합성 end-to-end 실행**

Run: `python -m pytest tests/test_end_to_end.py -q`

Expected: 주입한 fixture 수집기와 Codex 응답으로 staging, validate와 manifest가 완성되고 Git tracked content, 원격, 이메일, 예약 작업은 바뀌지 않는다.

- [ ] **Step 6: 실제 하루 읽기·쓰기 제한 섀도 실행**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_daily.ps1 -Mode Prepare -Shadow`

Expected: `runs/<date>/`와 무시된 빌드 산출물만 생성되고 `git status --short`에는 의도한 구현 diff 외의 날짜 콘텐츠가 나타나지 않는다.

- [ ] **Step 7: 적대 리뷰 준비**

최신 트리 식별자, 지원 진입점, Windows 기본 구성, 신뢰 경계, 제외 범위, 테스트 결과와 열린 리스크를 한 묶음으로 기록한다. 사용자가 승인하면 Windows Claude Opus 5 `--effort xhigh` 전체 리뷰를 실행하고 `Critical=0`, `High=0`을 확인한다. 모델 불일치나 quota 실패는 무효 처리한다.

- [ ] **Step 8: 승인 후에만 커밋**

```powershell
git add README.md .gitignore docs/operations tests
git commit -m "docs: add Windows publisher operations and shadow gate"
```

- [ ] **Step 9: 별도 승인 후에만 운영 전환**

1. `scripts/install_scheduler.ps1 -Apply`로 Windows 예약 작업 등록.
2. 준비 작업을 수동 실행하고 07시 게시 작업의 dry-run 확인.
3. Windows 게시 작업 활성화.
4. WSL timer 중지.
5. 첫 실제 게시와 이메일을 확인.
6. 일주일 동안 WSL 저장소를 읽기 전용 롤백 기준으로 보존.

---

## Plan Self-Review

- Spec coverage: Windows 호환, Codex 격리, provenance, 수집 확대, 발행량, 콘텐츠 분리, 게시·이메일, 예약, 섀도 전환이 Task 1~8에 각각 매핑됐다.
- Placeholder scan: 미정 값이나 비어 있는 구현 지시가 없다.
- Type consistency: `Candidate`, `SourceHealth`, `run_json`, `selection.json`, 새 콘텐츠 경로가 모든 후속 작업에서 같은 이름을 사용한다.
- Scope: 새 CMS, 기존 URL 이동, 경영 전용 메일, 비공식 브라우저 수집을 제외해 한 저장소에서 순차 실행 가능한 범위로 제한했다.
- Authorization: 커밋, 푸시, 이메일, 예약 등록, WSL timer 변경은 모두 별도 승인 게이트 뒤에 있다.
