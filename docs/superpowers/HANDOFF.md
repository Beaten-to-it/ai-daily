# ai-daily — 작업 핸드오프 (세션 재개용)

> 마지막 갱신: 2026-07-01 (P2b **구현완료·미머지** — 최종리뷰+머지 대기). `/clear` 후 새 세션은 이 문서(특히 §2.5) + 스펙 + P2b plan을 읽고 이어간다.

## 1. 프로젝트 한 줄
`newsNblog`의 **대체재**. 매일 AI 뉴스를 **News 인덱스(짧게) → 각 항목 Blog 상세글(외국어 원문의 한글 최대 상세 해설) + AI UseCase(일반 사용자용)** 로 자동 발행. 검증되면 기존 newsNblog 폐기.

- 라이브: https://beaten-to-it.github.io/ai-daily/
- repo: https://github.com/Beaten-to-it/ai-daily (main)
- 작업 디렉터리: `/home/beaten/project/NBs`

## 2. 진행 상태
| Phase | 내용 | 상태 |
|---|---|---|
| P1 | Hugo(PaperMod) 사이트 골격 + GitHub Actions Pages 배포 | ✅ DONE (라이브, 샘플글) |
| P2a | 수집(RSS+X+Reddit) → claude -p 내용 중복판정·선별 → `selection.json` | ✅ DONE (merged, 20 tests) |
| P2b | 전문 fetch(grounding 게이트) + 항목당 한글 Blog 생성 + News/UseCase 조립 → `staging/` | 🟡 **구현완료·미머지** (branch `p2b-fetch-generate-assemble`, 70 tests green). 최종리뷰+머지 미완 — §2.5 |
| P2c | 원자적 스테이징→`content/` 승격·완결성 검사·로컬 발행(빌드+커밋)·ledger append | 대기 (P2b 머지 후) |
| P3 | 자동화(스케줄러·preflight·catchup) + 이메일(idempotent) + 관측성/알림 + Reddit용 Chrome 기동 | 대기 |

## 2.5 P2b 재개 상태 (미머지 — **여기부터 시작**)

**브랜치:** `p2b-fetch-generate-assemble` (main 미머지). HEAD `100135a`. `python3 -m pytest -q` = **70 passed**.
**plan:** `docs/superpowers/plans/2026-07-01-p2b-fetch-generate-assemble.md` (9-task TDD, advisor+Codex 2R 통과). 진행 ledger: `.superpowers/sdd/progress.md` (gitignore).

**구현 완료 (9/9 task, 태스크별 리뷰 통과):** `nbs/fetch.py`(체인+classify_evidence), `nbs/generate.py`(claude -p `--tools ""`, delimiter sanitize, generate_all 병렬/timeout/retry/격리), `nbs/assemble.py`(news+floor+usecase), `nbs/stage.py`(→`runs/<date>/staging/`+`generation.json`, P2b→P2c 계약). `prompts/blog.md`,`prompts/usecase.md`. select.py도 `--tools ""` 하드닝(§10).

**실 E2E 증거:** 1차 실행(Claude Code env)=22 fetch + **진짜 한글 블로그 8편** + news 조립 성공(파이프라인 실증). 구현중 실버그 4개 잡아 고침(commit 0adff5e 캡션dedup, 3c98a46 dup-frontmatter+`--tools ""`발견[`--allowedTools ""`는 툴 안막힘!], d77e02c 프롬프트 template-injection+select하딩, 100135a usecase실패격리).

**⚠️ 머지 전 남은 것 (순서대로):**
1. **[BLOCK] `build_usecase`에 `_strip_fences` 없음** (advisor 최종리뷰 지적). `render_blog`는 `_strip_fences(run_claude_notools(...))` 하는데 `build_usecase`는 `raw.strip()` 후 `startswith("---")`만 체크 → LLM이 ```` ```markdown ```` 펜스/서두 붙이면 usecase 매번 실패(§5격리로 크래시는 안 나지만 usecase 산출물 = 조용히 안 나옴). 수정: `build_usecase`도 `_strip_fences` 재사용 + 펜스 씌운 usecase 출력 테스트 추가. **머지 게이트.**
2. **깨끗한 생성 스모크 (Claude Code env에서!)**: `claude -p`는 **`codex exec` 밑에서 실패**한다(2026-07-01 Codex 스모크: 4/4 `claude -p failed:` — 인증/nesting). 그러니 생성 스모크는 Claude Code 환경에서 돌린다. 빠른 확인용 4항목 스모크셋: `runs/2026-07-02/selection.json`(article 4개, 실URL). `python3 -m nbs.stage --date 2026-07-02` → generation.json status=ok + posts≥1 + usecase 파일 생성 확인. (스모크는 [[smoke-tests-via-codex]]에 예외 기록됨: claude -p 호출 스모크는 Codex 불가.)
3. **최종 whole-branch 적대리뷰 마저**: advisor ✅완료(위 #1 지적). **Codex 최종리뷰 미완**, opus whole-branch reviewer 미완. 패키지: `.superpowers/sdd/review-a99e961..100135a.diff`. deferred Minor 트리아지: parse_frontmatter unanchored `---`(fail-safe), fetched.text size cap 없음, `_strip_fences` greedy, stage rerun시 `fetched/` 미삭제.
4. **머지**: finishing-a-development-branch → main 머지 + push. HANDOFF/memory 갱신(P2b DONE, 다음=P2c).

**커버리지 주의:** 실스모크는 article-only. paper/sns/video fetch는 단위테스트만(reddit=Chrome off). PR/handoff에 명시.

## 3. 문서 위치
- 스펙(SSOT): `docs/superpowers/specs/2026-07-01-nbs-news-blog-design.md`
- 계획: `docs/superpowers/plans/2026-07-01-p1-site-foundation.md`, `...-p2a-collect-select.md` (P2b/c/P3는 미작성)
- 이 핸드오프: `docs/superpowers/HANDOFF.md`

## 4. 확정된 핵심 결정 (스펙 §)
- 발행: 공개 GitHub Pages(ai-daily). **로컬 생성 + `git push`→Actions 배포** (구독 OAuth, 추가비용 0). 무인 스케줄은 P3.
- **모든 News 항목 → 각각 Blog.** 항목 수 고정 상한 없음(단 **fetch 게이트**: 원문 못 가져오면 발행 보류/제외) + 소스별 25 캡.
- Blog 깊이: **최대한 자세히**(사용자 선택). 단 형태는 **재서술+분석**(통째 번역 아님), **페이월 우회 금지**, takedown 대응. 라이선스 관대 소스(공식/오픈소스/논문/CC)는 준-번역까지.
- 중복: URL canonical 1차 + claude -p 내용 판정. skip은 *새 정보 0 순수 재보도*만. **진화·후속 스토리는 keep**(이어감). 애매하면 keep.
- AI UseCase = 1급 산출물, **일반 사용자 톤**. News/Blog는 개발자·창업자 톤.
- 이메일 유지(News 인덱스+UseCase). 수신자 기본 kimhyo75@gmail.com.
- 소스: RSS 코어(공식블로그·GeekNews·HN·arXiv·Verge·TechCrunch) + X + Reddit. Threads/GitHub 후속.

## 5. 환경 사실 (재개 시 그대로 사용)
- **`python3`** 사용 (bare `python` PATH 없음). pip는 `--break-system-packages` 필요(Debian 3.14).
- Hugo **0.163.3 extended** 설치됨(`~/.local/bin`, ~/.bashrc PATH). CI `HUGO_VERSION="0.163.3"`.
- 테마 PaperMod = git submodule `themes/PaperMod`.
- GitHub 인증: `~/.git-credentials`에 토큰(계정 **Beaten-to-it**, full scope). push/API 그대로 됨. gh CLI 미설치.
- **twitter** CLI(pipx, `~/.local/bin/twitter`): 인증됨(@beaten2it). `twitter search "<q>" --type latest -n N --json` → `{"ok":true,"data":[...]}` **봉투**(주의: `-c`는 배열).
- **opencli**(reddit): **Chrome + OpenCLI Browser-Bridge 확장 상시 필요**(없으면 `BROWSER_CONNECT`). 무인 시 Chrome 기동은 P3. 사용자 어제 reddit 로그인 세션 있음.
- `yt-dlp` 설치됨(video/insane-search 백엔드). `agent-reach`(라우터), `insane-search`(스킬, **P2b fetch 폴백**: Jina/curl_cffi/Playwright).
- claude -p: **stdin으로 프롬프트 전달**(`subprocess.run(["claude","-p"], input=text)`) — argv 길이 회피. 검증됨.

## 6. 데이터 계약

### 6a. P2a → P2b (`selection.json`)
- `runs/<date>/selection.json` 루트: `{date, items[], selected_count, skipped_count, generated_with}` (gitignore 스크래치).
- SelectionItem: `{event_key, title(한글), url(후보에 존재·검증됨), source, source_type, evidence_type, dedup(new|followup|skip), prior_post_path, rank, rationale}`. source/source_type은 **LLM 편집 분류**(URL로 grounding, 의도적으로 candidate에서 안 덮어씀).
- 코드: `nbs/models.py`(Candidate/SelectionItem/canonicalize_url/validate_*), `nbs/collect.py`, `nbs/select.py`, `nbs/ledger.py`, `nbs/sources.py`, `prompts/select.md`.

### 6b. P2b → P2c (staging, 아직 `content/` 아님) — **P2c가 소비할 계약**
- P2b(`nbs/stage.py`)는 `selection.json`을 읽어 **실제 fetch → claude -p 생성 → 스테이징**까지만 하고, **`content/`에는 아무것도 쓰지 않는다.** 승격은 P2c 책임.
- 산출물 위치(둘 다 `runs/<date>/` 아래, gitignore 스크래치 — 커밋 대상 아님):
  - `runs/<date>/staging/posts/<slug>.md` — 상태 `ok`인 항목만. front matter: title/date/tags/source_url/source_lang/source_type/evidence_level/event_key.
  - `runs/<date>/staging/news/<date>.md` — News 인덱스(카테고리별 그룹, 항목당 훅). **floor 통과 시에만** 생성.
  - `runs/<date>/staging/usecase/<date>.md` — AI UseCase(일반 사용자 톤). floor 통과 + publishable 존재 시에만 생성.
  - `runs/<date>/generation.json` — `{date, status, results[], published_count, floor_failed}`. `results[]`는 `GenerationResult.to_dict()`: `{event_key,title,url,source,source_type,evidence_level,status(ok|failed|excluded),post_path,slug,rank,rationale,error}`.
- **floor**: `nbs/assemble.py FLOOR_N=3` — publishable(status=="ok") 개수가 3 미만이면 `floor_failed=true`이고 news/usecase 파일은 **생성되지 않음**(posts는 ok인 것만 그대로 스테이징됨). P2c는 `floor_failed`를 보고 그날 전체를 보류할지 posts만 갈지 정책 결정 필요(스펙 §5).
- P2c가 해야 할 일(스펙 §2 파이프라인의 나머지): staging → `content/posts/`·`content/news/`·`content/usecase/` **원자적 승격** + **완결성 검사**(개수·front matter 일치 재검증) + Hugo 빌드 + `git commit`(+push) + `data/published.csv` **ledger append**(post_path 채움, canonical_key/event_key/date/title/url/source/summary/entities/tags/confidence).
- 코드: `nbs/stage.py`(orchestration), `nbs/fetch.py`(evidence gate: confirmed/short/exclude), `nbs/generate.py`(claude -p 격리 호출 + 스키마 검증), `nbs/assemble.py`(floor/news/usecase), `nbs/models.py`(GenerationResult/FetchResult), `prompts/blog.md`, `prompts/usecase.md`.
- ledger `data/published.csv` 헤더: `canonical_key,event_key,date,title,url,source,post_path,summary,entities,tags,confidence` (커밋 대상, 아직 비어있음 — **P2c**가 발행 후 append).

## 7. 재개 실행 절차 (P2c 시작)
1. `cd /home/beaten/project/NBs && export PATH="$HOME/.local/bin:$PATH"`
2. `python3 -m pytest -q` → 69 passed 확인(그린 베이스라인).
3. 스펙 §2, §5, §12(완결성/발행) + 이 문서 §4~§6 읽기.
4. **P2c writing-plans** → 각 단계 **advisor + Codex 적대 리뷰**(2R 캡, 글로벌 룰=게이트) → 사용자 "구현해" → subagent-driven 실행(브랜치 `p2c-...` → 리뷰 → 머지).
5. `scripts/p2a_smoke.sh <date> && scripts/p2b_smoke.sh <date>`로 `runs/<date>/staging/` + `generation.json` 재생성 후, P2c는 그걸 입력으로 승격 로직을 짠다.

### P2c 설계 시드 (미확정, plan에서 확정)
- 승격: `staging/posts|news|usecase/*` → `content/posts|news|usecase/*` 원자적 복사(임시 디렉터리 + rename, 부분 실패 방지).
- 완결성 게이트: 승격 직전 `generation.json.results`의 `ok` 개수 == 승격될 post 파일 개수 재검증(재수정·경합 방지, P2b가 이미 하는 recount-before-membership 패턴 재사용).
- `floor_failed=true`일 때 정책: posts만 승격하고 news/usecase는 skip? 그날 전체 보류? — 스펙 §5 "부분 실패시 발행 가능한 것만" 원칙과 상충 없는지 확인 필요(미확정).
- 커밋 메시지 포맷·ledger append 시점(빌드 성공 후 vs 승격 직후)은 plan에서 확정.

## 8. 알려진 함정 / 미해결
- `select`는 LLM 스키마/멤버십 실패 시 그날 **abort(무출력)** — 다운스트림이 감내해야(재시도는 P3).
- Reddit은 Chrome 꺼지면 가드 스킵(현재 그러함; task-9 REAL 스모크는 22건 전부 `source_type=article`이라 reddit/sns 경로는 이번엔 미노출 — 다음에 sns 항목 섞인 날 재확인 필요). X 원문 트윗은 저신호 많아 LLM이 자주 필터(정상).
- 워크플로 룰: 산출물마다 **advisor + Codex 각 단계 리뷰**(글로벌 CLAUDE.md 게이트). subagent-driven, 브랜치→머지, 커밋 태스크별.
- **경험적으로 고정된 사실 (재발 방지, 다음 세션이 재검증할 필요 없음):**
  - `claude -p` **도구 완전 차단 플래그는 `--tools ""`** (브리프 원안이던 `--allowedTools ""`는 **차단 안 됨** — Read가 `/etc/hostname`에 대해 permission_denials 없이 실행됨. `--tools ""`는 세션 init에서 `tools: []`, `tool_use` 이벤트 0건까지 확인됨). 코드: `nbs/generate.py:28-34`.
  - `yt-dlp`는 **ffmpeg 미설치 환경**에서 `--convert-subs srt`가 no-op이라 **`.vtt`를 그대로 남긴다**(`.srt` glob이 비면 `.vtt`로 폴백 필요). 코드: `nbs/fetch.py:150-169`.
