# ai-daily — 작업 핸드오프 (세션 재개용)

> 마지막 갱신: 2026-07-01. `/clear` 후 새 세션은 이 문서 + 스펙 + 다음 plan을 읽고 이어간다.

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
| **P2b** | **전문 fetch(grounding 게이트, insane-search 폴백) + 항목당 한글 Blog 생성 + News/UseCase 조립** | ⏭ **다음** |
| P2c | 원자적 스테이징·완결성 검사·로컬 발행(빌드+커밋) | 대기 |
| P3 | 자동화(스케줄러·preflight·catchup) + 이메일(idempotent) + 관측성/알림 + Reddit용 Chrome 기동 | 대기 |

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

## 6. 데이터 계약 (P2b가 그대로 소비)
- `runs/<date>/selection.json` 루트: `{date, items[], selected_count, skipped_count, generated_with}` (gitignore 스크래치).
- SelectionItem: `{event_key, title(한글), url(후보에 존재·검증됨), source, source_type, evidence_type, dedup(new|followup|skip), prior_post_path, rank, rationale}`. source/source_type은 **LLM 편집 분류**(URL로 grounding, 의도적으로 candidate에서 안 덮어씀).
- ledger `data/published.csv` 헤더: `canonical_key,event_key,date,title,url,source,post_path,summary,entities,tags,confidence` (커밋 대상, 아직 비어있음 — P2b/c가 발행 후 append하며 post_path 채움).
- 코드: `nbs/models.py`(Candidate/SelectionItem/canonicalize_url/validate_*), `nbs/collect.py`, `nbs/select.py`, `nbs/ledger.py`, `nbs/sources.py`, `prompts/select.md`.

## 7. 재개 실행 절차 (P2b 시작)
1. `cd /home/beaten/project/NBs && export PATH="$HOME/.local/bin:$PATH"`
2. `python3 -m pytest -q` → 20 passed 확인(그린 베이스라인).
3. 스펙 §2~§12 + 이 문서 §4~§6 읽기.
4. **P2b writing-plans** → 각 단계 **advisor + Codex 적대 리뷰**(2R 캡, 글로벌 룰=게이트) → 사용자 "구현해" → subagent-driven 실행(브랜치 `p2b-...` → 리뷰 → 머지).

### P2b 설계 시드 (미확정, plan에서 확정)
- fetch: article=WebFetch→insane-search(페이월/차단/JS 폴백)→실패 시 `evidence:short` 또는 제외. paper=arXiv abstract. sns=twitter/opencli 스레드. video=yt-dlp 자막.
- 생성: `selection.json` 항목마다 **claude -p 1회**(격리) → 원문 근거 한글 Blog md(front matter: title/date/tags/source_url/source_lang/source_type/evidence_level/event_key) → `content/posts/`.
- 실행 한도: 병렬 캡·항목당 timeout·retry·실패격리. **최소발행 floor**(그날 confirmed+short < N이면 전체 보류+알림).
- 프롬프트 인젝션 방어: 원문=신뢰못할 데이터(구분자), 스키마 검증, 시크릿 접근 분리, 원문 근거로 도구호출 금지.
- **무출력 날 처리**: select/생성이 0건이면 그날 발행 skip(P2c/P3가 처리).

## 8. 알려진 함정 / 미해결
- `select`는 LLM 스키마/멤버십 실패 시 그날 **abort(무출력)** — 다운스트림이 감내해야(재시도는 P3).
- Reddit은 Chrome 꺼지면 가드 스킵(현재 그러함). X 원문 트윗은 저신호 많아 LLM이 자주 필터(정상).
- 워크플로 룰: 산출물마다 **advisor + Codex 각 단계 리뷰**(글로벌 CLAUDE.md 게이트). subagent-driven, 브랜치→머지, 커밋 태스크별.
