# ai-daily — 작업 핸드오프 (세션 재개용)

> 마지막 갱신: 2026-07-03 저녁. **main==origin `4e8c80c`, 206 passed.** 오늘 한 것: **P3b(이메일) merged·pushed** + **첫 실 발행 2026-07-03(뉴스 14글 라이브)** + **AX 경영 섹션 신설·라이브** + buildFuture·AX타임아웃 fix. **다음 재개점 = P3c(스케줄러) brainstorm.** 남은 즉시항목: ①**메일 실발송** — 사람이 `scripts/reauth_google.py`로 gmail.send 토큰 발급(브라우저, client_secret을 `~/.config/ai-daily/`에) 후 `python3 -m nbs.email --date <d>`. ~~②generate.py title-YAML sanitize~~ **✅ DONE** (branch `fix/generate-title-yaml-sanitize`, `_sanitize_title` at `_strip_fences` seam=blog/usecase/ax 공통, Hugo 0.163.3 RED→GREEN 실증, advisor+Codex xhigh 2R, 214 passed). 상세 = 아래 §2.8 오늘 실황.

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
| P2b | 전문 fetch(grounding 게이트) + 항목당 한글 Blog 생성 + News/UseCase 조립 → `staging/` | ✅ **DONE (merged, 80 tests)**. 적대리뷰 2R(Codex+Opus) 통과. 상세 §2.5 |
| P2c | 원자적 스테이징→`content/` 승격·완결성 검사·로컬 발행(빌드+커밋)·ledger append | ✅ **DONE·머지** (main, 117 tests, 적대리뷰 2R). §2.6 |
| P3a | 오케스트레이터: collect→select→stage→publish→**push**→Actions배포. 날단위 멱등·crash-safe·no-email | ✅ **DONE·merged·pushed** (main==origin `ea8e29e`, 149 passed, 적대리뷰 2R + code-review 라운드). §2.7 |
| P3b | 이메일 발송(Gmail, News+UseCase, push 성공 후, idempotent) | ✅ **DONE·merged·pushed**. ⚠️ **실 Gmail 발송만 미검증** — reauth 토큰(사람) 후 발송. `nbs/email.py`+`scripts/reauth_google.py`+orchestrate seam. 스펙 §15 + plan. |
| **AX 경영** | News·UseCase 평행 3번째 1급 산출물(경영자 톤 daily synthesis) | ✅ **DONE·merged·pushed·라이브** `/ax/2026-07-03/`. `prompts/ax.md`+`assemble.build_ax`(결정적 grounding 게이트)+stage/publish/hugo(menu+mainSections)/email 3섹션. 스펙 §16 + plan. |
| P3c | 스케줄러(systemd timer)·preflight·catchup·Reddit Chrome 무인기동 | 🔵 **다음 재개점** (brainstorm부터) |
| P3d | 관측성/알림(run.json 소비, 실패·누락·인증만료·floor미달 이메일, 일일 메트릭) | 대기 (P3b 후) |

## 2.5 P2b 완료 기록 (DONE — 참고용)

**머지:** branch `p2b-fetch-generate-assemble` → main. `python3 -m pytest -q` = **80 passed**.
**plan:** `docs/superpowers/plans/2026-07-01-p2b-fetch-generate-assemble.md` (9-task TDD).

**구현:** `nbs/fetch.py`(체인 http→jina→curl + classify_evidence + `_visible_text` 추출 + scheme 가드), `nbs/generate.py`(claude -p `--tools ""`, delimiter sanitize, `_strip_fences` 펜스+서두제거, generate_all 병렬/timeout/retry/격리), `nbs/assemble.py`(news+floor+usecase+검증), `nbs/stage.py`(→`runs/<date>/staging/`+`generation.json`, event_key reject-and-isolate, P2b→P2c 계약). `prompts/blog.md`,`prompts/usecase.md`. select.py도 `--tools ""`(§10).

**최종 실 E2E 증거 (Claude Code env, 2026-07-02, 4항목 실URL 스모크):** `python3 -m nbs.stage --date 2026-07-02` → **published=4, floor_failed=False, usecase_error=None**, posts×4 + news + usecase 스테이징. eyeball 품질 확인(usecase=일반사용자 톤, grounded, 서두/인젝션 흔적 0).

**최종 적대리뷰 2R (게이트 통과):** advisor + Codex(xhigh) round-1·2 + Opus whole-branch. 확정 findings 전부 fix (커밋 c59cc8e→12d966a):
- event_key(LLM출력)를 fetched/slug/post 경로로 그대로 씀 → path traversal/크래시. **reject-and-isolate** (`^[a-z0-9-]{1,100}$` 불일치=excluded, 경로쓰기 스킵; slugify 금지=충돌 덮어쓰기 회피). §5 격리 fetch 루프까지 확장.
- **§10 LFI**: fetcher가 `file://`/`ftp://` 등 로컬 읽음(실증). `fetch_item` dispatch에서 http(s)만 + `_http_get`/`_curl_impersonate`가 **redirect 최종 scheme** 재검증.
- fetch gate(`_visible_len`)와 return(`_visible_text`) 불일치 → 통일(`_visible_len=len(_visible_text)`, style 스트립). raw HTML 대신 visible text + 40K cap.
- usecase: `_strip_fences` 재사용(펜스+서두) + 최소검증(terminated fm + title/date/tags + 본문 비지않음).
- gen `timeout=180→300`(상세 한글블로그 실측 216s). no-retry-on-timeout는 spec("timeout+1retry")과 배치라 revert.

**deferred (defer-safe, P2c 정리 대상):** ① 미앵커 `---` 분할이 parse_frontmatter/validate_blog_output/build_usecase 종료체크 3곳 공통 — fm 값에 `---`면 오분할(저확률·§5격리). 중앙 수정 권장. ② `_visible_text` 단일라인 붕괴(품질만). ③ stage rerun시 `fetched/` 미삭제(디버그 스크래치, 무해). ④ **floor 의미 = §6b 결정 필요**.

**커버리지 주의:** 실스모크는 article-only. paper/sns/video fetch는 단위테스트만(reddit=Chrome off).

## 2.6 P2c 완료기록 (구현완료·머지대기 — **여기부터**)

**구현 완료 (2026-07-02, executing-plans 직접실행):** plan 12태스크 TDD 전부 그린. 신규 `nbs/publish.py`(decide/check_completeness/date_writeset/preflight_clean/promote/rollback/_hugo_build/build_verify/ledger_rows/run/main) + 수정 `models.parse_frontmatter_strict`, `assemble.floor_ok`(증거기준)·`build_news_index`(relref), `ledger.rewrite_date`, `prompts/blog.md`(## TL;DR). 커밋: 72c2eff→5b5142d(태스크당 1커밋).
- **검증:** `python3 -m pytest -q` = **111 passed**(P2b 80 + P2c 31). 
- **실스모크 (Claude env, 2026-07-02):** publish.run → `[published] promoted=6 degraded={}`, 실 hugo 빌드 통과(build_verify 무에러=렌더+subpath href 확인), content posts×4+news+usecase 승격, ledger 4행 전부 summary 비지않음(257~340자)+tags. 스모크 후 tree clean(git clean).
  - ⚠️ **스모크 접근 편차 (의도적, advisor 승인):** plan Task12는 `nbs.stage --date`로 staging 전체 재생성(=live fetch + claude -p 재호출)을 명시하나, 그건 비결정적(죽은 URL·LLM 출력변동→floor 결과가 바뀌어 P2c와 무관하게 스모크 실패 가능)이라, P2b가 이미 검증한 staging을 재사용하고 **news 인덱스만 결정적으로 재빌드**(`build_news_index`로 relref화, LLM 0)한 뒤 `publish --no-commit` 실행. 스모크의 고유가치(실 hugo + 실 git/fs promote + 실 ledger)는 그대로 커버. `scripts/p2c_smoke.sh`는 fresh-day용 full 파이프라인 형태로 커밋됨.
- **적대리뷰 2R 통과 (게이트 완료):** advisor✅ + Codex xhigh R1·R2. 확정 findings 전부 fix:
  - R1 **BLOCK** slug이 generation.json→fs/git 경로로 무검증 유입(traversal) → completeness 게이트에 `_SLUG_RE.fullmatch` reject(promote/rollback 전). R1 **MAJOR** `rewrite_date`가 옛 날짜 재실행 시 행 재정렬→spurious commit → `(date,event_key)` 정렬로 순서 불변. (자체발견: `match`+`$`가 `evil\n` 통과 → `fullmatch`.)
  - R2 **BLOCK** `gen["date"]`/date 인자도 경로성분 → `../_index` traversal → `_DATE_RE` 엄격검증 + `gen["date"]==arg` 핀. R2 **MAJOR** charset-safe 타 날짜 slug(예 `2026-06-30-sample`)가 date-scope 탈출 → completeness에서 `slug==f"{date}-{ek}"` 강제. (R2가 R1 fix 정확성 확인.)
  - 커밋 ac5bbce→b2c83c3. 회귀 부정검증 완료(정렬 fix 제거 시 옛날짜 재실행 테스트 실패 재현).
- **deferred 미해결 (defer-safe):** ① `parse_frontmatter`/`parse_frontmatter_strict` 미앵커 `---` 분할(값에 `---`면 오분할, 우리 포맷엔 없음). ② ledger `entities`/`confidence` 필드 빈값(YAGNI, ledger_digest 무시). ③ 실스모크는 article-only(P2b 커버리지와 동일; paper/sns/video 승격은 단위테스트만).
- **남은 것:** finishing-a-development-branch로 머지. push는 P3(수동/자동 배포).

<details><summary>(이전) 재개점 — 계획완료·구현대기 시점 기록</summary>

**상태:** brainstorm→스펙확정→writing-plans 끝. **구현 미착수**(사용자 "구현해" 트리거 대기 — 1순위 룰: 트리거 전 코드 금지).
**브랜치:** `p2c-promote-publish` (main 미머지, 현재 체크아웃됨). HEAD `b47ca18`. main 대비 앞선 커밋 = 스펙 §15 확정(4커밋) + P2c plan(3커밋)뿐, **코드 0**.
**plan(구현 청사진):** `docs/superpowers/plans/2026-07-02-p2c-promote-publish.md` — 12태스크 TDD. **적대리뷰 2R 통과**(스펙 §15: advisor+Codex 2R / plan: advisor+Codex 2R, R1 6BLOCK+7MAJOR→R2 3건 전부 반영). 바로 실행 가능 상태.
**스펙 확정 위치:** 스펙 §15 "확정 (P2c, 2026-07-02...)" 블록 + §6b 계약.

**P2c가 하는 일 (요약):** `runs/<date>/staging/` → `content/` 원자적 승격 + 완결성검사 + Hugo 빌드검증 + `data/published.csv` ledger 재구축 + **단일 로컬 commit(push 안 함 — 배포는 수동/P3)**.

**확정된 핵심 설계 결정 (구현 시 그대로):**
- **발행 게이트 2중**: evidence-floor(confirmed+short≥3, §4 소스장애감지) AND ok≥1(빈날 방지). `assemble.floor_ok`를 **evidence 기준으로 정렬**(현 publishable 기준 → 변경, P2b 테스트도 갱신).
- **내부 링크 = Hugo `{{< relref "/posts/<slug>.md" >}}`** (P2b `build_news_index`의 `/posts/` root-relative는 baseURL `/ai-daily/`서 404 → 수정 필요. Task 4).
- **date-scoped 원자성**: writeset= `content/posts/<date>-*.md` glob ∪ `git ls-files` ∪ ok타깃 + news/usecase/ledger. 순서=completeness(staging)→promote(스테일 삭제)→build-verify→ledger 재구축→`git add -A`(존재-or-HEAD만)→staged-subset 확인→`git diff --cached --quiet`(no-op 멱등) 아니면 commit. 실패 시 `rollback(ws)`=git restore(HEAD-tracked)+삭제(untracked), ledger 포함.
- **usecase optional**: 실패해도 news+posts 발행, `publish.json.degraded`에 기록. build-verify는 content usecase 있을 때만 렌더 확인.
- **ledger summary = `extract_tldr(md)`** (`## TL;DR`/`**TL;DR**` 관대파싱, 없으면 첫문단 폴백, 빈값이면 발행 실패). front matter는 **엄격 파서**(unquote+tags 리스트).
- **관측성 = `runs/<date>/publish.json`** manifest(status published|held|failed, reason, promoted[], degraded, commit_sha).
- **모듈**: 신규 `nbs/publish.py`. 수정 `assemble.floor_ok`/`build_news_index`, `models`(+parse_frontmatter_strict), `ledger`(+rewrite_date), `prompts/blog.md`(## TL;DR).

**재개 절차:** ①`cd /home/beaten/project/NBs && export PATH="$HOME/.local/bin:$PATH"` ②`git branch --show-current`=`p2c-promote-publish` 확인, `python3 -m pytest -q`=80 passed 베이스라인 ③plan 읽기 ④사용자 "구현해" → **subagent-driven-development**(태스크마다 fresh subagent + 2단계 리뷰, 태스크 12개 순서대로) 또는 executing-plans ⑤전 태스크 그린 후 실 스모크(Claude env, `bash scripts/p2c_smoke.sh 2026-07-02`) → 최종 whole-branch 리뷰 → 머지.
**주의:** 실 스모크는 `claude -p` 호출(staging 재생성) → **Claude Code env 필수**([[2026-07-02-claude-p-fails-under-codex-exec]]). 빌드/검증은 파이프로 감싸지 말 것([[2026-07-01-pipe-hides-build-failure]]).

</details>

## 2.7 P3a 완료기록 (구현완료·리뷰통과·머지대기 — **여기부터**)

**구현 완료 (2026-07-02, executing-plans 직접실행):** 신규 `nbs/orchestrate.py`(서브프로세스 체이닝 드라이버) + `tests/test_orchestrate.py`(25) + `scripts/p3a_smoke.sh`. 기존 스테이지 **수정 0**. 7태스크 TDD 커밋 b0c38d9→(T7). 전체 `pytest -q` = **142 passed**(P2c 117 + P3a 25).
- **하는 일:** 하루치 단일명령 `collect→select→stage→publish(P2c)→git push origin main→Actions→Pages 배포`. `python3 -m nbs.orchestrate --date <YYYY-MM-DD>`(기본 오늘 KST) `[--force] [--no-push]`.
- **확정 설계(스펙 §15 "확정 (P3a)"):** ①**날단위 멱등 가드**=`git cat-file HEAD:content/news/<date>.md`(git 권위, scratch 소실 견딤) 1차 → 있으면 `pushed==true`면 skip / 아니면 push-only 재시도(재생성 안 함=비결정 발산 방지), 없으면 full. `--force`만 강제 재발행. ②**crash-safe fd `flock`**(동시실행 방지). ③**스테이지별 성공기준**=exit0 AND 아티팩트 의미(stage는 floor-fail도 status:ok → publish 결과는 `publish.json.status`로 읽음; publish 서브프로세스는 held/failed여도 exit0). ④**push**=published일 때만, 성공검증(origin/main==HEAD) 후 publish.json에 `pushed`+`deployed_sha`. 실패는 `git ls-remote` 조상판정으로 `push_rejected`(발산·치명) vs `push_pending`(네트워크·재시도) — stderr 파싱 안 함. ⑤**run.json** `{date,run_id,started_at,status(published|skipped|held|failed|push_pending|push_rejected|busy),stages{},reason}` + exit코드. **이메일 안 보냄**(P3b/d).
- **적대리뷰 2R 통과 (게이트):** 스펙 advisor+Codex 2R / plan advisor+Codex 2R. 확정 findings 전부 fix — R1 **BLOCK** publish rc 미검사+stale publish.json→push(=`_stage_ok(publish)` 선검사), R1 MAJOR ×5(_push reason 유실·remote-equal 오분류·테스트 remote가 worktree 안·divergence 방향 미판별·publish-rc1 테스트 부재), R2 MAJOR(_push 3튜플 언팩·push-only reason·publish held/failed reason 전파). plan `docs/superpowers/plans/2026-07-02-p3a-orchestrate-publish.md`.
- **검증:** unit 25(실 git bare-remote로 push/classify/flock/멱등가드/publish-crash 가드 커버) + 전체 142 passed. **실체인 부분스모크:** `nbs.orchestrate`가 실 `nbs.collect` 서브프로세스를 구동해 candidates.json 28건 생성 확인(엔트리→lock→guard→runner→아티팩트 체인 실증). ⚠️ **편차(의도적):** 전체 라이브 생성(select+stage `claude -p` ~25분·비결정)은 orchestrate 통해 안 돌림 — P2c 실스모크 published가 publish 단 E2E를 이미 커버하고, 나머지 링크는 실 git 유닛으로 커버. 전체 라이브는 `bash scripts/p3a_smoke.sh <오늘>`(Claude env)로 필요시.
- **남은 것:** finishing-a-development-branch로 머지. 이후 **P3b 이메일 → P3c 스케줄러+preflight+catchup+Chrome → P3d 관측성/알림**(각자 brainstorm→spec→plan→2R→구현). push=이 P3a가 하지만 자동 트리거(스케줄)는 P3c.

## 2.8 오늘 실황 (2026-07-03) — P3b·첫발행·AX경영·수정들

**전부 merged·pushed. main==origin `4e8c80c`, 206 passed. 다음 재개점 = P3c brainstorm.**

- **P3b 이메일 (DONE):** `nbs/email.py`(git-authoritative 발송게이트 `git cat-file origin/main:content/news`, gmail.send 단일권한 토큰·시크릿 레포밖 `~/.config/ai-daily/`, multipart, href/헤더 인젝션 방어, 날짜게이트 ledger) + `scripts/reauth_google.py` + orchestrate seam(published/skipped시 non-fatal, `--no-push` 미호출). 이제 **AX 포함 3섹션**(News+UseCase+AX). ⚠️ **실 Gmail 발송 미검증** — 저녁에 사람이 reauth 토큰 발급(브라우저) 후.
- **첫 실 발행 2026-07-03 (라이브):** collect 138→select 16→stage 14ok/2타임아웃(격리)→publish→push. `/news/2026-07-03/` 등 라이브. **실 E2E가 유닛 못잡은 버그 2개 노출:**
  - **buildFuture(수정·`ca02542`):** KST 아침 실행 시 date=오늘(KST)이 UTC 빌드서버 기준 미래 → Hugo 기본 `buildFuture=false`가 오늘 글 제외(로컬 build_verify 실패+배포 누락). `hugo.toml buildFuture=true`. **P3c 스케줄러 필수 전제**(매 KST 아침 재발).
  - **✅ generate.py title-YAML (해결):** claude -p가 title에 straight `"` 넣어 생성(예 `title: "A"는 B`) → 우리 parser 통과하나 Hugo strict YAML 거부(build 실패). `_sanitize_title`를 **`_strip_fences` 공통 seam**(blog/usecase/ax 3경로 공유)에 접어 title 값을 single-quoted YAML scalar로 재방출. 들여쓰기/`title :`(공백)/block scalar(`>``|`)/single-quote apostrophe(`''` un-escape, 멱등) 처리. **Hugo 0.163.3 실파서 RED→GREEN 실증**(broken rc=1 → sanitized rc=0). advisor+Codex xhigh 2R(R1 1 BLOCK+2 MAJOR fix, R2 clean), 214 passed. branch `fix/generate-title-yaml-sanitize`.
    - **deferred(문서화된 ceiling):** ①`tags`도 free-text — 같은 break class, 미처리(다음에 tags 깨지면 real YAML dump로). ②title 내 literal `---` mis-split(parse_frontmatter/_dup_keys 공유 코드베이스 ceiling, fail-safe=격리 드롭). ③usecase/ax는 duplicate title 키 가드 없음(blog엔 `_duplicate_frontmatter_keys` 있음) — pre-existing, P3d 강건화 후보.
- **AX 경영 (신설·DONE·라이브):** News·UseCase 평행 3번째 1급 산출물(경영자 톤 daily synthesis). 스펙 §16 + plan `2026-07-03-ax-management.md`(각 2R×2). `prompts/ax.md`+`assemble.build_ax`(**결정적 grounding 게이트**: 본문 angle relref가 그날 항목 slug에 앵커≥1·전부 publishable·비-angle 거부=email `_RELREF_FULL` 동형→gate-pass⟹email-safe)+stage(ax_error §5격리)/publish(promote·writeset·build_verify·_degraded)/hugo(menu weight0+**mainSections에 ax**)/email 3섹션. 오늘치 `/ax/2026-07-03/` 라이브(grounding eyeball PASS: 3포인트 다 그날 항목서 도출).
  - **⚠️ AX 타임아웃(fix `4e8c80c`):** build_ax 합성이 무거워 기본 `GEN_TIMEOUT=300` 초과 → `AX_TIMEOUT=900`. 단 **미측정 상한**(900서도 flake 가능, §5로 페이지만 스킵). AX 3× 필요는 AX본질 아니라 env claude -p 레이턴시 편차 의심.
  - **교훈:** 새 stage 기본값(`ax=ax or asm.build_ax`)이 기존 test_stage를 실 claude -p로 만들어 suite 1.5s→333s. **전체 회귀 시간**으로 잡음. 새 주입점 추가 시 기존 테스트 스텁 갱신 필수.

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
  - ⚠️ **P2c 결정 필요 (스펙 §4 vs 코드 모순 — Opus 리뷰 지적):** 코드는 floor를 **생성성공(publishable, status=="ok")** 으로 세는데, 스펙 §4 SSOT는 **증거(confirmed+short) 개수**의 대량-수집실패 감지기로 정의(“상한 아님”). 즉 fetch는 다 됐는데(예: confirmed 5) 생성만 3개 실패하면 코드에선 publishable=2<3 → 그날 index 전체 보류(§4는 발행하라는 날). 코드가 더 보수적이라 defer-safe지만 SSOT와 배치 → **P2c 설계에서 (a) floor를 증거기준으로 바꾸거나 (b) 스펙 §4 문구를 코드에 맞춰 정합화** 중 택해 해소할 것.
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
