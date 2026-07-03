# NBs — AI 데일리 News + Blog 설계안

- 날짜: 2026-07-01
- 상태: 승인됨 (Codex 적대 리뷰 1라운드 반영, 사용자 재확인 대기)
- 위치: `/home/beaten/project/NBs`
- 성격: 기존 `newsNblog`(github.com/Beaten-to-it/newsNblog)의 **대체재**. 검증되면 기존 폐기.
- 출처 아이디어: 기존 newsNblog의 개념/아키텍처만 참고. **코드는 가져오지 않음.**

---

## 1. 목적 / 해결할 문제

기존 newsNblog "AI Morning Radar"는 매일 AI 뉴스 브리핑을 자동 생성·발행했으나 3가지 문제:

1. **같은 뉴스 반복** — 한 브리핑(9개 섹션) 안에서 같은 항목이 여러 섹션에 중복. (예: 2026-06-30 브리핑에서 *vLLM Micro-Agent*가 섹션 2·5·7, *Copilot fast mode*가 2·3·7에 중복.)
2. **못 읽음** — WebSearch 스니펫만으로 작성해 글이 얕고, 외국어 원문·페이월·죽은 링크로 실제 내용 접근 불가.
3. **가독성** — 9개 섹션, 빽빽한 문단, "5분 읽기" 밀도 붕괴.

## 2. 핵심 모델

**News = 짧은 인덱스 피드 → 각 항목이 Blog 상세글로 링크. Blog = 외국어 원문에 대한 최대한 자세한 한글 해설(상세 재서술+맥락+분석).**

```
[수집] → [중복제거+선별] → [원문 fetch (게이트)] → [항목당 Blog 1편] → [News 인덱스 + UseCase 조립]
       → [스테이징 완결성 검사] → [원자적 발행: 빌드+push] → [발행 성공 후 이메일] → [로그/알림]
```

3대 문제 구조적 해결:

| 문제 | 해결 |
|---|---|
| 반복 | 항목이 News에 **1번만** 등장 → Blog 1편 링크. 섹션 중복 원천 제거. 날짜 간은 내용 기반 ledger 판정 |
| 못 읽음 | **fetch 게이트**: 1차 출처 확보 실패 시 발행 보류/제외. 확보한 내용에 근거한 한글 해설 → 외국어도 읽힘 |
| 가독성 | News=짧은 스캔 피드, 깊이는 Blog가 흡수. 한 항목 = 한 페이지 = 한 URL |

## 3. 산출물 (3종)

### 3.1 Blog 글 — `content/posts/YYYY-MM-DD-<slug>.md`
외국어 원문에 대한 **최대한 자세한 한글 해설**(사용자 선택) — 원문 내용을 충실·상세히 다루되 우리 문장으로 재서술+분석(기계적 1:1 전재 아님 — §11 법적 정책).
- 구성: 제목 / TL;DR 3줄 / **본문(원문 핵심을 우리말로 요약·설명+우리 분석)** / 왜 중요한가 / (해당 시) 이걸 어떻게 써먹나 / 출처 링크
- front matter: `title, date, tags, source_url, source_lang, source_type(article|sns|paper|repo|video), evidence_level(confirmed|short|unverified), event_key`
- 톤: 개발자·창업자
- **짧은 확인 항목**: 1차 출처가 짧은 글/영상/동적 페이지뿐이면(전문 본문 없음) 풀 Blog 대신 **짧은 확인 포맷**(핵심 1~3문단 + 출처)로 발행 → 중요한데 전문이 없다고 누락되는 일 방지.

### 3.2 News 인덱스 — `content/news/YYYY-MM-DD.md` + 홈
그날 항목들을 **1~2줄 훅 + "자세히 →" 링크**로 나열. 카테고리로 가볍게 묶어 항목이 많아도 스캔 가능. **이메일 본문도 이걸 재사용.**

### 3.3 AI UseCase 스트림 — `content/usecase/` (또는 `usecase` 태그)
매일 그날 뉴스에서 *일반 사용자가 따라갈 실사용 흐름*을 별도로 뽑음. 사이트 상단 고정 섹션 + News 인덱스 + 이메일 포함.
- 톤: **일반 사용자용**(전문용어 줄이고 "이걸로 ~할 수 있다" 구체적으로) — 비엔지니어도 AI 활용 흐름 따라가기.

## 4. 소스 & fetch 스파인 (계층적 grounding)

| 소스 | 수집 도구 |
|---|---|
| 웹 article / 공식 블로그 / 미디어 | WebFetch + `insane-search`(차단 시, **페이월 우회는 안 함** §11) |
| X/Twitter, Reddit, GitHub | `agent-reach` |
| Threads | `insane-search`(명시 지원) — 로그인 인증 저장 필요 |
| GeekNews / Hacker News / RSS / arXiv | RSS + `agent-reach` / WebFetch |

소스 우선순위(기존 선호 유지): AI 에이전트 > AI 코딩 도구 > 주요 모델 업데이트 > 오픈소스 LLM > 스타트업/제품/투자 > 멀티모달 > 논문/벤치마크 > 기업용/생산성 > 한국 개발자 반응 > 규제/정책(큰 건만).

**게이트 규칙 (트러스트 경계 — 게으름 금지):**
- 1차 출처를 **실제로 확보**한 항목만 발행. 확보 실패 → 보류/제외.
- **source_type별 최소 근거 기준**(evidence_level): 전문 본문 확보=`confirmed`(풀 Blog) / 짧은 1차 출처만=`short`(짧은 확인 포맷) / 미확인=발행 안 함.
- **최소 발행 기준**: N은 *대량 장애 감지용 floor*(상한 아님). 그날 confirmed+short 항목이 N개 미만이면(소스 대량 장애 의심) **그날 전체 발행 보류**하고 실패 알림. N을 채우려고 top story를 강등/누락하지 않음 — 중요 항목은 short로라도 항상 포함.
- 글은 확보한 내용에 **근거해서만** 작성·인용. 루머는 `unverified`로 분리, 풀 Blog 안 씀. 환각 금지.

## 5. 생성 방식 — 항목당 격리 + 실행 한도

큰 LLM 호출 1번이 News+모든 글을 생성하던 기존 방식 폐기(스니펫 의존·교차오염·얕음 원인).
- **선별 1회** → 채택 항목 확정(구조화 리스트, URL·event_key 포함).
- **항목마다 `claude -p` 1회** → 1차 출처 + 단독 호출로 Blog 1편. 항목 간 격리 → 품질↑, 근거↑, 반복 0.
- **실행 한도(견고성):** 항목 수에 고정 상한은 없으나 — **병렬 한도, 항목당 timeout, 1회 retry, 일일 wall-clock/예산 상한**을 둔다. 한 항목 실패는 격리(다른 항목 진행). 예산 초과 시 우선순위 낮은 항목은 `short` 포맷으로 강등.
- News 인덱스·UseCase는 **최종 성공한 항목만**으로 조립(부분 실패가 인덱스에 깨진 링크로 새지 않게).

## 6. 중복 제거 (내용 기반)

3단 판정:
1. **URL/canonical 1차 필터** — 동일 링크 싸게 제거.
2. **event_key 매칭** — 사건/엔티티 단위 키(제목 변형에 강함)로 최근 항목과 대조.
3. **내용 판정** — 최근 N일 ledger의 `compact summary`를 LLM이 읽고 판단 + `confidence`:
   - **순수 재보도(새 정보 0)** → skip
   - **변화·개선·후속(새 디테일/벤치마크/가격/반응/버전)** → **채택**, 이전 글 링크하며 이어감(델타 중심)
   - **신규** → 채택
   - **저신뢰(애매)** → **keep 쪽으로 편향** + 로그 플래그 (과잉 skip 방지)

> 사용자 명시: 스토리 A가 조금씩 변하며 다음날·그 다음날 다시 나오는 건 **환영**. 진화 스토리는 죽이지 않음. skip은 *새 정보가 전혀 없는 순수 재보도*에만.

- ledger `data/published.csv`: `canonical_key, event_key, date, title, url, source, post_path, summary, entities, tags, confidence`
- LLM 입력은 **rolling window(최근 N일) + compact summary**만 사용(비대화 방지). 전체는 archive로 보존.
- 임베딩/벡터DB·event cluster·quarantine 큐 사용 안 함 (YAGNI). `// ponytail: 최근창+event_key LLM 판정. 규모 커지면 임베딩/클러스터 도입`

## 7. 실행 호스트 — 로컬 생성 + Actions 배포

- 로컬 PC에서 **구독 OAuth**로 생성·`git push`(추가 토큰 비용 0) → push가 GitHub Actions 트리거 → Pages 배포.
- 스케줄: **WSL systemd timer 우선**(가능 시). Windows 예약작업→WSL 진입은 fallback(절전 깨움 보완).
- **preflight 체크**(네트워크·인증·distro·PATH·git 자격) 통과해야 run 시작. 절전/네트워크 미준비 등 특정일 실패 방지.
- **누락 실행 catchup + 실패 알림**: 그날 미발행이면 catchup 재시도, 계속 실패 시 이메일 알림(조용한 며칠 미발행 방지).
- Threads/SNS 로그인: 사용자가 1회 로그인 → 인증(쿠키/토큰) **레포 밖 보안 위치에 저장** → 무인 실행 재사용. 만료 감지 시 알림.

## 8. 배포 — 새 repo + Hugo (원자적)

- 새 GitHub repo, GitHub Pages 배포(Source: GitHub Actions). 검증 후 기존 newsNblog 폐기.
- 사이트 빌더 손수 안 만듦 → **Hugo**(단일 바이너리, 태그/RSS/아카이브/페이지네이션 기본, 빌드 빠름, 깔끔한 테마). 가독성 1순위 불만 → 깔끔한 테마.
- **원자적 발행:** run마다 staging 디렉터리에 전체 생성 → **완결성 검사**(모든 News 링크가 실제 존재하는 post를 가리키는지) 통과해야 → 단일 commit으로 published. 부분 상태 금지. **run_id 기록 → 재실행 idempotent.**

## 9. 이메일

- Gmail API로 **News 인덱스 + UseCase** 발송. **발행(push) 성공 후에만** 발송(깨진 링크 메일 방지).
- **sent ledger + run_id**로 중복 발송 차단(재실행해도 같은 날 1회).
- 수신자 기본 `kimhyo75@gmail.com`. 추가 주소는 구현 시 확정.
- 폭 ~640px, 모바일 단일 컬럼, 카드형, 텍스트 fallback 동반.

## 10. 보안 가드레일

- **grounding 게이트**(§4).
- **프롬프트 인젝션 방어**: fetch한 원문은 **신뢰 못 할 데이터**로만 취급 — 명확한 구분자로 감싸 LLM에 전달, 지시로 해석 금지. 출력은 스키마 검증. **생성 프로세스는 시크릿/자격 접근 불가**(분리). **원문 내용을 근거로 새 도구 호출·외부 액션·링크 추종을 하지 않음**(데이터 → 텍스트 생성만).
- **시크릿 위생(강화):** 키·토큰·쿠키는 **레포 밖**에 `chmod 600`로 저장, `.gitignore`(`*token*.json`, `client_secret*.json`, `secrets/`, 쿠키), **push 전 secret 스캔**, **로그 마스킹**(토큰/쿠키 로그 금지), 토큰 회전 절차 문서화. `// ponytail: 파일권한+gitignore+스캔. 필요시 OS 키체인`

## 11. 법적 / 약관 정책 (저작권)

사용자 선택: **최대한 자세히**(번역에 가깝게). 깊이는 최대로 가되 리스크는 아래로 관리:

- **깊이 = 최대, 형태 = 재서술.** 원문 내용을 빠짐없이 상세히 다루되 **우리 문장으로 상세 해설 + 분석**(기계적 1:1 복붙 번역 아님) + 출처·원문 링크 명시. 직접 인용은 식별 가능하게 짧게.
- **라이선스 인지 차등:** 공식 발표·오픈소스·논문·CC/퍼미시브·공개 도메인은 **준-번역까지** 풀어도 됨. 상업 매체는 상세하되 재서술 중심.
- **페이월·로그인 강제 우회로 본문 수집 금지.** `insane-search`는 접근 가능한 공개 콘텐츠 읽기·검증용으로만.
- **안전판:** 권리자/매체 요청 시 즉시 삭제(takedown 대응) 절차 둠.
- **잔여 리스크(사용자 명시 수용):** 통째에 가까운 상세 해설은 분쟁 소지 잔존. 사용자가 깊이를 우선해 수용함.

## 12. 관측성

- run log + 단계별(fetch/generate/publish/email) 상태 기록.
- 실패·누락·인증 만료·최소 발행 미달 시 **이메일 알림**.
- 일일 메트릭(수집/채택/발행/skip 수, 실패율) 기록.
- 실패 시 **run_id별 아티팩트 보존**(staging·로그·원인 분류) → 재처리 가능.

## 13. 범위 밖 (YAGNI, v0 제외)

좋아요/댓글 · DB · 추천 알고리즘 · 관리자 페이지 · 사용자 계정 · 임베딩/벡터DB · Slack 알림(이메일로 대체) · quarantine 큐.

## 14. 성공 기준

- [ ] 한 호(일자) 안 같은 항목 중복 노출 0건.
- [ ] 날짜 간: 순수 재보도 skip / 진화 스토리는 이어짐(링크).
- [ ] 발행된 모든 글이 확보된 1차 출처에 근거(출처 링크 유효), 페이월 우회 0.
- [ ] News 스캔 짧고, Blog는 외국어도 한글로 읽힘.
- [ ] AI UseCase 매일 일반 사용자용으로 충분.
- [ ] 발행 원자성: News 링크 깨짐 0, 이메일은 발행 성공 후 1회.
- [ ] 무인 실행 성공 + 실패 시 알림 도달(조용한 미발행 0).

## 15. 미결 / 구현 시 확정

**확정 (P2b, 2026-07-01):**
- 최소 발행 floor **N=3** (대량장애 감지용, 상한 아님·튜너블). 항목당 timeout **180s**, 병렬 **4**, retry **1회**. claude -p는 OAuth(호출별 비용0)라 예산이 아닌 wall-clock·레이트가 한도.
- AI UseCase 산출 = **별도 claude -p 1회**, 그날 생성된 Blog 요약 기반 **하루 1~3편** 큐레이션(추가 fetch 없음, 일반 사용자 톤).
- Hugo 테마 = PaperMod (P1). repo = ai-daily (P1).

**확정 (P2c, 2026-07-02 — 설계 적대리뷰 advisor+Codex 2R 반영):**
- **범위 = 로컬 commit까지.** staging→content 승격 · 완결성 검사 · Hugo 빌드검증(렌더 산출물) · ledger 재작성 · **단일 git commit(로컬)**. **push/라이브 배포는 수동 또는 P3** — P2c는 push 안 함.
- **발행 게이트 (둘 다 통과해야 승격):**
  1. **evidence-floor (§4 SSOT)** = `results`의 `evidence_level∈{confirmed,short}` 개수 ≥ N(=3). 미달 → 대량 소스장애 의심 → **그날 전체 보류 + 알림**. (`assemble.floor_ok`를 evidence 기준으로 정렬 — P2b `publishable` 기준은 §4와 배치했음. P2b·P2c 공통.)
  2. **ok≥1** = `status==ok` 개수 ≥ 1. 0이면(증거는 있으나 생성 전멸) **보류 + 알림** — 빈 인덱스 발행 금지(evidence-floor만으론 이 케이스 못 막음). 통과 시 **ok 항목만** 발행(§5), ok 개수가 N 미만이어도 발행(floor는 상한 아님).
- **완결성 검사 (강화):** 각 ok result ↔ 정확히 1개 `staging/posts/<slug>.md`; `post_path==posts/<slug>.md`; 글 front matter의 `event_key/source_url/date/evidence_level`가 result와 일치; `tags` 비지 않음; slug·event_key·canonical_url 유일; news 링크 집합 == ok slug 집합. 하나라도 불일치 → 발행 중단(all-zero·경합·부분생성 차단).
- **UseCase = optional(degraded 발행):** 게이트 통과 시 news+posts 발행; usecase 실패(`usecase_error` set)면 usecase 없이 발행 + **degraded 기록/알림**(§5 "발행 가능한 것만" + P2b가 usecase를 이미 격리). 완결성은 usecase 파일을 필수로 요구하지 않음.
- **내부 링크 = Hugo `relref` shortcode** (P1 샘플·`scripts/smoke_build.sh`와 일치). `build_news_index`의 `](/posts/<slug>/)`는 baseURL subpath(`/ai-daily/`)에서 404 → `{{< relref "/posts/<slug>.md" >}}`로 수정. (P2b 잔존 버그, P2c에서 수정.)
- **원자적 발행(§8) = 게이트 통과 → content/ 복사 → 빌드검증 → ledger 재작성 → 단일 commit.** pre-commit 어느 단계든 실패 시 **날짜스코프 롤백**: 이 run이 만든 content 파일(**untracked 포함 삭제**) + tracked 덮어쓴 것 `git checkout` + index 클린 확인. (또는 temp 경로 후 `os.replace`.) `git checkout -- content/`만으론 untracked orphan·ledger 미복구.
- **ledger = 날짜단위 재구축(멱등):** append-only 금지. 전체 읽어 이 date 행 제거 후 현재 발행분 재작성 → temp+atomic replace, content와 같은 commit. 재생성으로 내용 바뀌어도 content·ledger desync 0. (재실행 = 동일 결과.)
- **ledger 필드**: `summary`=**`extract_tldr(md)`** — 실제 모델 출력은 `## TL;DR`·`**TL;DR**` 혼재(편차)라 하드검증으로 거부하지 않고 **관대 파싱**: 두 마커 중 아무거나 뒤의 불릿/줄을 취하고, 없으면 **본문 첫 문단 폴백**. body는 `validate_blog_output`가 non-empty 보장 → summary는 항상 non-empty(다음날 §6 dedup 보호). 프롬프트는 `## TL;DR` 3줄로 유도(강제 아님). `canonical_key`=`canonicalize_url(url)`(P2a §6 dedup 키와 동일), `tags`=Blog front matter(엄격 파서), 나머지=generation.json, `entities`/`confidence`=빈값(defer).
- **빌드검증 = throwaway `hugo` 빌드 + 렌더 검증**(exit 코드만으론 불충분): 승격된 각 post/news/usecase의 `public/.../index.html` 존재 + news→post href가 `/ai-daily/posts/<slug>/` subpath 포함(smoke_build.sh 패턴). 파이프로 감싸지 않음.
- **관측성(§12) = `runs/<date>/publish.json`**: `{date, status(published|held|failed), reason, promoted[], degraded(usecase 등), commit_sha, error}`. 보류·실패도 기록(재처리 판단용).
- **git preflight**: identity 확인; **write-set 경로(`content/posts/<date>*`, `content/news/<date>.md`, `content/usecase/<date>*`, `data/published.csv`)가 clean해야 시작 — dirty면 abort**(롤백의 `git checkout`이 사용자 미커밋 변경 파괴 방지, R2-P1). 내용 동일 재실행의 "nothing to commit"은 성공 처리.
- **front matter 읽기(게이트·ledger)는 엄격 파서**(R2-P2): quoted scalar 정규화 + `tags`를 리스트로 파싱(`[]`·빈 리스트=빈값 취급). 현 `parse_frontmatter`(naive line-splitter, dict last-key-wins)를 그대로 게이트에 쓰지 않음. stdlib만(YAML 의존 회피) — 제약 파서 수 줄.
- **degraded 확장**(R2-P3): `ok_count < evidence_count`(일부 생성 실패) 또는 `ok_count < FLOOR_N`이면 `publish.json.degraded.generation_failed_count` 기록 + 알림(부분 생성장애가 조용히 발행되지 않게).
- 모듈: 신규 `nbs/publish.py`(오케스트레이션). `ledger.py`에 날짜단위 재작성 헬퍼 추가. 수정 `assemble.build_news_index`(relref)·`floor_ok`(evidence)·`validate_blog_output`(TL;DR). 재사용 `models.py`(canonicalize_url/parse_frontmatter/엄격파서)/`config.py`.

**확정 (P3a, 2026-07-02 — Orchestrator + Push & Deploy):**
> P3 = 4개 독립 서브프로젝트로 분해(각자 spec→plan→구현): **P3a 오케스트레이터+push**(백본) → P3b 이메일 → P3c 스케줄러+preflight+catchup+Reddit Chrome → P3d 관측성/알림. P3a는 §7 "로컬 생성 + Actions 배포"의 실행 드라이버 + §8 push를 구현한다.
- **범위 = 하루치 파이프라인 단일 명령 + push까지.** collect→select→stage→publish(P2c, 로컬 commit)→**`git push origin main`**→Actions→Pages 배포. 이메일·스케줄러·알림·Chrome은 후속 서브(범위 밖).
- **아키텍처 = 서브프로세스 체이닝.** 신규 `nbs/orchestrate.py`가 각 스테이지를 `python3 -m nbs.{collect,select,stage,publish} --date <date>`로 호출, **exit코드 + 스테이지 아티팩트 JSON**으로 상태 판정. 기존 스테이지 코드 **수정 0**(격리·재사용). `orchestrate.run(date, *, force=False, no_push=False) -> dict`(run.json) + `main()`/`__main__`: `--date`(기본 **오늘 KST**, config.KST), `--force`, `--no-push`(publish에 `--no-commit`은 전달 안 함 — publish는 항상 커밋, no_push는 push만 스킵해 드라이런/스모크용).
- **동시실행 락 (R1+R2 반영):** orchestrate 진입 즉시 **fd 기반 `flock`** 획득 — 프로세스 사망 시 커널이 자동 해제(crash-safe). 이미 실행 중이면 즉시 종료(exit=busy). pidfile로 대체 시 반드시 **live-PID 검증 + stale 정리**(안 하면 crash 후 영구 busy, R2). ~15분 파이프라인 + 일일 timer(P3c) 겹침 시 git index 경합·이중 push 방지. 락은 orchestrate 소유(스케줄러가 P3c여도 여기서 건다).
- **날단위 멱등 가드 (R1+R2 반영 — git-authoritative, scratch 소실 견딤):** `--force`면 무조건 ③ 전체 파이프라인. 아니면 **`git cat-file -e HEAD:content/news/<date>.md`**(=그날이 로컬 HEAD에 발행됨)를 **1차 기준**으로 분기:
  - **head_has_news == 참** (로컬 발행 완료된 날 → 재생성 금지):
    - `publish.json.pushed==true` → **① skip** (`status=skipped`, exit 0, 이미 배포됨).
    - 아니면(pushed false/미확인/`publish.json` 없음) → **② push-only** — 스테이지 전부 스킵, `git push origin main`만 재시도(이미 최신이면 무해 no-op). 성공→published, 실패→push 상태분기(아래).
  - **head_has_news == 거짓** → **③ 전체 파이프라인**.
  - 근거(R2 BLOCK 수정): `head_has_news`가 "로컬 발행됨"의 **git 권위 신호**로 scratch `runs/` 소실에도 유효하다. 이걸 1차로 두어야 publish.json이 없는 scratch-wiped 날이 ③으로 새어 **비결정 `claude -p` 재생성→발산 에디션**이 되는 걸 막는다. `publish.json.pushed`는 ①skip vs ②re-push **최적화만** 담당(없으면 안전하게 ②로 no-op 재push). `--force`가 유일한 강제 전체 재발행 경로.
- **파이프라인 실패 의미(순서 고정, fail-fast) — 스테이지별 성공 기준 명시 (R1 반영):** 각 스테이지는 **exit0 AND 해당 아티팩트의 의미**로 판정(일반 `status==ok` 규칙 금지 — stage는 floor-fail일 때도 `status:ok`를 반환하고 held 판정은 publish가 함):
  - collect: rc0 & `candidates.json` 존재 → 진행(빈 리스트도 진행). rc≠0 → 중단·failed.
  - select: rc0 & `selection.json` 존재 → 진행(`selected_count==0`도 진행). abort=rc≠0(예외) → 중단·failed.
  - stage: rc0 & `generation.json.status∈{ok,skip-empty}` → 진행. rc≠0/JSON 없음/파싱실패 → 중단·failed.
  - publish: **결과는 `publish.json.status`로 읽는다**(publish 서브프로세스는 held/failed여도 exit0). published→push; held/failed→**push 안 함**, 최종 held/failed.
  - 공통: rc0인데 아티팩트 없음/손상 → **failed**(부분 산출·killed 서브프로세스 방어).
- **Push + 배포 마커 (R1 반영 — non-ff 구분):** published일 때만 `git push origin main`(자격 `~/.git-credentials`, 무인). **불변식: `origin/main`은 이 드라이버만 write**(다른 커밋 유입 없음 가정). push 성공 후 검증(`git rev-parse origin/main == HEAD`) → `publish.json`에 `pushed=true`+`deployed_sha` **원자적 기록**(temp+replace, orchestrate 소유; publish.py 무수정). push 실패 분기(**stderr 파싱 금지 — locale/provider 문구에 취약, R2**): `git ls-remote origin refs/heads/main`로 원격 SHA 조회 → 원격 SHA가 로컬 HEAD의 **조상이 아니면**(origin 발산) `push_rejected`로 **크게 실패**(단순 재시도로 안 풀림 — run.json 구분 기록, P3d 알림 대상). ls-remote 자체 실패(네트워크)면 `push_pending`(일시 — 다음 실행/catchup가 ②로 재push). **push 실패는 로컬 commit 롤백 안 함**(commit 성공, 재push만 필요).
- **run.json 매니페스트(§12 관측성) — run 신원 추가 (R1 반영):** `runs/<date>/run.json` = `{date, run_id, started_at, status, stages:{collect,select,stage,publish,push:{status,reason}}, reason, force}`. `status∈{published, skipped, held, failed, push_pending, push_rejected}`. `run_id`=timestamp기반, `started_at`=`datetime.now(KST)` ISO(비결정 무관 — 워크플로 스크립트 아님). P3d가 읽음. **exit코드:** published/skipped=**0**; held/failed/push_rejected=**비0-치명**(catchup 무의미, 알림); `push_pending`=**비0-재시도가능**(catchup가 ②로 재push). **P3a는 이메일/알림 직접 안 보냄**(관심사 분리 — P3b/P3d).
- **테스트:** `tests/test_orchestrate.py` — 스테이지 러너를 seam(주입 가능 runner/monkeypatch)으로 stub해 실 `claude -p`/`hugo` 없이: 정상 published→push, held→no-push, 스테이지 rc≠0→중단, 이미-발행 스킵, `--force` 재실행, push rc≠0→pushed=false. 실 스모크(Claude env) 1회는 `--no-push` 드라이런(또는 테스트 remote)으로 collect→publish 체인 확인.
- **범위 밖(후속 서브 명시):** Gmail 발송(P3b) · systemd timer·preflight 체크·catchup 재시도·Reddit Chrome 무인기동(P3c) · 실패/누락/인증만료 이메일 알림·일일 메트릭(P3d).

**확정 (P3b, 2026-07-03 — Email 발송):** *(적대리뷰 반영: advisor R1 + Codex xhigh R1 40건 triage — accepted 다수, rejected는 근거 명시. 상세 부록 A.)*
> 사용자 결정: **newsNblog의 검증된 이메일 방식을 이식**(스펙 §7 "코드 안 가져옴"을 이 조각에 한해 명시 오버라이드). 이식 대상 = `send_email.py`(Gmail API + 저장 OAuth 토큰 auto-refresh + base64 raw send) + `render_briefing.py::render_html`(무의존 MD→HTML) + delivery-log 멱등 패턴. **이식 ≠ 복붙**: 아래 fidelity 결함(광역 scope 상속·HTML-only·href escape·markdown 순서)은 이식 시 반드시 수정.

- **범위 = 발행(push) 성공 후 그날 News 인덱스 + UseCase를 Gmail로 1회 발송.** 스케줄러·알림·catchup은 범위 밖(P3c/P3d).
- **모듈 = 신규 `nbs/email.py`.** 실행 `python3 -m nbs.email --date <YYYY-MM-DD> [--to a,b] [--dry-run] [--force] [--run-id ID]`(기본 오늘 = `datetime.now(config.KST).date()`). 기존 스테이지 코드 수정 0, **`orchestrate.py`만 최소 추가**(seam).
- **발송 게이트 = git-authoritative (advisor R2 — BLOCK 수정; Codex #9/#13/#36을 P3a 원칙에 맞춰 재해석).** ~~publish.json.pushed~~는 scratch(`runs/`)라 wipe 후 standalone 재발송을 false-negative로 막는다(P3a가 git-authoritative 가드로 피한 바로 그 함정). 따라서 email의 **발송 결정·본문 구성 모두 scratch 아닌 git 상태**로: 게이트 = `git cat-file -e origin/main:content/news/<date>.md`(=그날이 origin 배포됨. origin/main은 P3a 드라이버만 write). 통과 시에만 발송, 아니면 미발송(깨진 링크 방지). run_id만 scratch에서(추적 label, 없으면 `"manual"`).
  - **usecase 포함 = 동일 commit의 committed 존재로 판정(Codex #37 dissolve):** `git cat-file -e origin/main:content/usecase/<date>.md` 있으면 포함, 없으면 news-only. publish가 degraded 재실행 시 stale usecase를 이미 삭제하므로 **committed 존재 자체가 진실** — `publish.json.degraded` 읽기 불필요.
  - **본문도 게이트와 동일 ref에서 읽음(Codex R2 BLOCK2 수정):** `git show origin/main:content/news/<date>.md`(usecase 동일). 게이트·본문이 **같은 commit**이라 HEAD/워킹트리가 origin/main과 어긋난 순간에도 일관(온디스크 read 시 mismatch 갭 제거).
- **결합(seam) — standalone + orchestrate 체이닝:** orchestrate가 push 확인 직후 `python3 -m nbs.email --date --run-id <run_id>`를 서브프로세스 1회 호출. **`published`(이번 push)뿐 아니라 `skipped`(이미 push된 날)에도 호출** — 1차 run이 push 성공·email만 실패 시 재run은 skipped가 되므로, published에만 걸면 영구 미발송. ledger 멱등이 중복을 막아 skipped마다 호출해도 안전. **이메일 rc는 run 상태에 영향 없음**(발행은 이미 성공 — §9). email 실패로 published/skipped→강등 금지. `--no-push` 드라이런은 origin에 안 올라가므로 email의 git 게이트가 자연히 실패→미발송(옵션 이름 아닌 origin 상태로 판정 — Codex #13).
- **관측 권위 분리 (Codex #12):** **ledger가 "발송됨"의 유일 권위**(orchestrate가 email subprocess 후 죽어도 유효). email은 결과 JSON(status/reason/message_ids)을 stdout으로 반환 → orchestrate가 `run.json.stages.email:{status,reason}`에 **best-effort** 반영(관측용). email 실패는 `stages.email.status="failed"`로 기록(P3d 알림 대상 — §12).
- **전송 = Gmail API + 저장 OAuth 사용자 토큰(refresh_token), auto-refresh + write-back.**
- **⚠️ 시크릿 = 최소권한 + 레포 밖 + 원자성 (advisor R1·Codex #1/#3/#4/#5/#31/#32/#34 — CRITICAL, §10 정합):**
  - newsNblog 토큰 재사용 **금지** — 실측 scope가 `gmail.send` 외 `readonly/modify·drive·calendar·documents·spreadsheets·contacts`까지 광범(계정 탈취급). ai-daily는 **공개** 레포라 유출=치명.
  - **① 신규 최소권한 토큰**: scope=`["https://www.googleapis.com/auth/gmail.send"]` **단일**. reauth 이식본은 `existing_scopes()` **제거**, `SCOPES=[gmail.send]` 하드코딩(기존 광역 scope 상속 금지). client_secret은 newsNblog 것 재사용 가능(토큰만 신규).
  - **② 레포 밖 저장**: 토큰·client_secret·ledger 전부 `~/.config/ai-daily/`(dir chmod 700, 파일 chmod 600). 레포 내 `secrets/`는 gitignore backstop일 뿐 **기본 경로 아님**. 경로 해석: `$AI_DAILY_GOOGLE_TOKEN`→`~/.config/ai-daily/google_token.json`, `$AI_DAILY_GOOGLE_CLIENT_SECRET`→`~/.config/ai-daily/client_secret.json`(**레포 root glob 제거**).
  - **③ 권한 강제**: 토큰 write 후 `os.chmod(0o600)`, read 시 group/world-readable이면 실패. refresh write-back은 **temp+`os.replace`+chmod**(원자성, 중단 시 토큰 손상 방지).
  - 발급 = `scripts/reauth_google.py`(이식·수정, **사람이 브라우저 로그인** — [[ai-stages-human-does-privileged-click]]). revoke(`invalid_grant`/`RefreshError`)는 email이 reason `token_invalid`로 exit≠0(Codex #35) + 동일 reauth 재실행.
- **본문 = News 인덱스 + UseCase 합본.**
  - 입력 = `git show origin/main:content/news/<date>.md`(필수) + usecase(**위 게이트 규칙으로 일원화** — origin/main에 usecase 존재 시 포함, 없으면 news-only). **`publish.json` 안 읽음**(scratch 비권위 — git 게이트 단일 권위, Codex R2 BLOCK1 수정).
  - **전처리(NBs 신규, 기존 헬퍼 재사용)**: ①front matter 제거·title 추출은 **`models.parse_frontmatter_strict` 재사용**(YAML edge·`---` 본문충돌·quoting 이미 처리, Codex #14/#15). 콘텐츠는 YAML front matter only(assemble가 그렇게 생성 — 테스트로 고정, Codex #16). ②relref 치환은 **`publish._RELREF` import 재사용**(패턴 중복 금지, Codex #17) → `https://<baseURL>/posts/<slug>/`. slug은 상류에서 `^[a-z0-9-]{1,100}$`(P2c `_SLUG_RE`) 보장이라 URL-escape 불필요(Codex #18 완화). **전처리 후 `{{< relref`/`{{% relref`/`{{< ref`가 남으면 exit≠0**(깨진 링크 발송 방지, Codex #19).
  - **렌더 = `render_html` 이식하되 보안 수정**: (a) 카드 폭 `max-width:640px`(§9 정합, Codex #2). (b) **href escape 이중화**(Codex #20/#21): scheme 검사는 `html.unescape`→control 제거→`urllib.parse.urlsplit` 기준, 허용은 **절대 http/https/mailto만**(scheme-less→`#`, Codex #22), href 삽입 시 `html.escape(url, quote=True)`. (c) **web_url 버튼도 동일 validator 통과**(Codex #23). (d) **code span 먼저 토큰화** 후 link/bold(코드 안 링크 렌더 방지, Codex #26). (e) raw HTML은 항상 escape(원문 인젝션 방어 — 원문→텍스트만, §10). `LINK_RE`의 괄호포함 URL 조기종단은 알려진 한계로 명시+테스트(우리 링크는 괄호 없음, Codex #25).
  - **본문 = `multipart/alternative`(text+html, Codex #27/advisor R1)** — newsNblog `_build_message`의 html-only는 §9 텍스트 fallback 누락이라 수정. text part = 전처리 마크다운 + 말미 웹URL.
  - **헤더 안전(Codex #28/#29/#30)**: `From`=인증 발신자 설정. `email.message.EmailMessage`/header API로 subject·수신자의 **CR/LF 제거**(헤더 인젝션 방어 — title은 외부 콘텐츠 경유 가능). `--to`는 `parseaddr` 검증+CRLF 차단+dedupe.
  - Subject = news front-matter `title`(폴백 `f"[AI Daily] {date}"`). 수신자 기본 `["kimhyo75@gmail.com"]`(config 상수). "웹에서 보기" 버튼 → `.../news/<date>/`.
- **멱등성(§9 "같은 날 1회") — 레포 밖 durable ledger (Codex #31/#32):** ledger `~/.config/ai-daily/email_delivery_log.csv`(**레포 밖** — recipients/subject PII의 공개레포 유출·`git add -A` 오염 원천 차단; `$AI_DAILY_EMAIL_LOG` override). `already_sent(date)` 행 존재→skip. **게이트=날짜 1회**(기본 수신자 1명). `--force`만 강제 재발송(force행에 reason 기록; 별도 `--confirm`은 과함 — Codex #8 부분반려). 발송 후 `(date,run_id,recipients,subject,ids,status)` append. run_id는 orchestrate `--run-id`>run.json>`"manual"`.
- **config 단일화(Codex #38/#39):** `SITE_BASEURL`을 `config.py` 상수로(하드코딩 산재 금지; hugo.toml baseURL과 일치). 날짜 기본 = `datetime.now(config.KST).date()`.
- **구현 세부 = plan로 위임(advisor R2 — 스펙은 결정/불변식만):** 아래는 mechanic이라 writing-plans에서 확정 — ① 토큰 write-back 원자성(temp+`os.replace`+chmod, Codex #34) ② code-span 선토큰화(Codex #26) ③ `Message-ID` 헤더 자체부여 + gmail_id 병기(Codex #33) ④ **per-`(date,recipient)` 게이트·부분실패 재발송은 `--to`가 다수일 때만**(기본 1명엔 날짜게이트로 충분 — YAGNI) ⑤ 멱등 임계구역 lockfile(자동경로는 orchestrate flock이 이미 직렬화; 단일 로컬PC 수동vs자동 경합은 근0 — 필요시 plan에서 `O_EXCL`).
- **의존성 추가(requirements.txt):** `google-auth`, `google-auth-oauthlib`, `google-api-python-client`. 렌더·전처리·멱등은 stdlib만.
- **테스트(네트워크 0, Codex #40 확장):** `tests/test_email.py` — front-matter strip·title edge(strict parser) / relref→절대URL(`_RELREF` 재사용 벡터) / relref 잔존→exit≠0 / subject 폴백·CRLF 제거 / `--to` 검증·dedupe·CRLF / `already_sent` 날짜게이트 / dry-run / **git 게이트**(fake git repo: origin/main에 news 있음→발송, 없음(scratch wipe 포함)→미발송) / usecase git-존재로 포함·미존재로 news-only / **href escape 우회 벡터**(`javascript:`,entity,scheme-less,`"`탈출) / web_url validator / **MIME=multipart 2파트** / **카드 max-width:640px** / **토큰 경로 레포 밖·scope=gmail.send 단일** 검증 / news 없음→exit≠0. `tests/test_orchestrate.py` 추가 — published→email 1회·rc≠0이어도 status 불변, skipped→email 호출(복구), 미발행(dry-run/held/failed)→email 미발송(git 게이트), stages.email best-effort 기록. email 러너는 주입 seam으로 stub. 실 Gmail send는 `--dry-run` 스모크 + (선택)Claude env 1회 실발송.
- **exit코드:** 발송성공/이미발송(`already_sent`)/미발행(git 게이트 실패=보낼 것 없음, reason `not_published`)=**0**(benign); `token_invalid`·send실패·(게이트는 통과했는데 committed news 파일 읽기 실패=희귀 불변식 위반)=**비0**. orchestrate가 이 rc를 **non-fatal**로 소비(run status 불변).

**확정 (P3c, 2026-07-03 — 스케줄러 + preflight + catchup + Reddit Chrome):**
> P3 서브 4개 중 3번째. P3a(orchestrate) 위에 **무인 스케줄 계층**을 얹는다. 기존 newsNblog Windows 발행작업(`newsNblog_Daily_Catchup`+`_OnWake` = `wscript daily_catchup_hidden.vbs`, 매일 21:03 + wake)은 **disable됨**(2026-07-03, 사용자 요청 — 삭제 아님·되돌리기 `Enable-ScheduledTask`) → **ai-daily 타이머가 유일 발행자**(이중 발행·중복 이메일 제거).

- **범위 = 무인 일일 발행(systemd 타이머 + preflight + catchup) + Reddit Chrome 무인기동 + 최소 quiet-day 알림.** 풍부한 관측·실패분류·인증만료 전용 알림·메트릭 = P3d(범위 밖).
- **환경 사실(확인 2026-07-03):** WSL2에 **systemd=init 활성**(PID1=systemd, `is-system-running`=running, wsl.conf `[boot] systemd=true`) → systemd **user** 타이머 가용. **WSLg 디스플레이 `:0`+`wayland-0`** + `google-chrome` 설치 → headful Chrome 무인기동 실현가능. 시스템 TZ = **KST(Asia/Seoul, +0900)**, systemd **259**.
- **가정 + 잔여리스크 (사용자 확정 2026-07-03):** **WSL 상시 기동**(VSCode-server 등이 잡음)을 전제로 systemd user 타이머 채택. wsl.conf `[boot]`은 "WSL 뜰 때 systemd 켜라"일 뿐 **WSL 자체를 부팅 시 자동시작 안 함** — WSL이 완전히 내려가면(Windows 재부팅 + 아무 세션 미개시) 타이머·quiet-day 알림 **모두 미발화**. 이는 §270 "로컬 PC 단일 장애점 = 비용0 선택의 수용 트레이드오프"에 해당. 필요 시 후속으로 **최소 Windows 트리거**(`wsl.exe -d <distro> true` on boot/logon)만 추가해 완화(스케줄 로직은 그대로 systemd). **참고: disable한 newsNblog Windows 작업은 `cmd /c daily_catchup.cmd`(Windows측 실행)라 WSL 기동과 무관 — 그 disable이 이 리스크를 만든 게 아님.**
- **스케줄 = systemd user 타이머 + 멱등 반복(bespoke catchup 엔진 없음).**
  - `ai-daily.timer`: **명시적 `OnCalendar` 라인 3개**(`*-*-* 07:00 Asia/Seoul`, `09:00`, `11:00` — systemd 259가 존/`Asia/Seoul` 접미 지원; 고정 wall-clock, 각 라인이 자체 `Persistent` catchup) + **`Persistent=true`**(놓친 발화 다음 기동 시 1회). `OnUnitActiveSec` 안 씀(활성시각 drift·Persistent와 상호작용 어색 — advisor). 각 발화 = `python3 -m nbs.schedule`. (TZ 무관: OnCalendar이 `Asia/Seoul` 명시 + 날짜연산은 고정 `config.KST` → 시스템 TZ가 UTC여도 발화·날짜 정확. 그래서 preflight에 TZ 체크 없음 — Codex R1 #4.)
  - **catchup은 창발**: 각 발화가 `orchestrate.run(오늘KST)`를 멱등 호출(P3a 가드 = HEAD에 발행됨→skip, commit-only→push재시도, 없음→full). 07시 실패→09시→11시 재시도; WSL이 오전 내내 꺼졌으면 Persistent + 다음 부팅 tick가 잡음. **미발행일 per-day 추적 코드 0.** 여러 날 backfill 안 함(3일 전 뉴스 재발행은 무가치 — 오늘치 발행이 옳음).
- **무인 드라이버 = 신규 `nbs/schedule.py`(얇음, 발행로직 0 — 기존 orchestrate/email 재사용).** 매 tick: **non-blocking flock 프로브**(orchestrate 락 이미 잡혀있으면 = run 진행중 → **Chrome 안 띄우고 즉시 exit busy**, Codex R1 #6) → `preflight()` 게이트 → `ensure_chrome()`(reddit, soft, **띄운 Chrome PID 기록**) → `orchestrate.run(오늘)` 위임 → (finally) **자기가 띄운 그 PID만 kill**(타 run/일상 Chrome 안 건드림) → 결과는 run.json/rc로 판정. **순서 근거: Chrome은 `orchestrate.run` 前에 띄워 유지**(orchestrate가 내부 서브프로세스로 collect를 돌리고 collect가 브리지에 접속하므로), run 종료 후 kill. `--check-alert` 모드는 발행 안 하고 quiet-day 판정만.
- **preflight 게이트 — 하드셋은 orchestrate가 스스로 못 다루는 것만 (Codex R1 #3: push_only 복구까지 오abort 방지):**
  - **하드 실패(이 tick abort, 부분쓰기 0, 다음 tick 재시도):** ①**write-set clean**(§172 재사용: `content/posts/<date>*`·`content/news/<date>.md`·`content/usecase/<date>*`·`content/ax/<date>*`·`data/published.csv` dirty면 abort — 롤백의 `git checkout`이 미커밋 변경 파괴하는 걸 막음, 유일하게 반드시 선제 차단해야 하는 것) ②git identity + 자격(`~/.git-credentials`) 존재(commit·push 전제, push_only 경로도 필요).
  - **soft(경고만, abort 안 함):** `hugo`·`nbs` deps·네트워크 — 이것들이 진짜 없으면 orchestrate가 해당 스테이지를 rc≠0로 **깨끗이 실패**(flock·롤백 crash-safe)시키고 다음 tick 재시도. **push_only/skip 경로는 hugo/deps 불필요**하므로 하드셋에서 빼야 그 catchup이 안 죽음. 디스플레이 env도 soft(없으면 reddit degrade). **TZ 체크 없음**(위: Asia/Seoul+config.KST라 무관).
  - 하드 실패는 조용히 종료; 지속되면 quiet-day 알림이 잡음.
- **Reddit Chrome 무인기동 = "될 때 얻고, 안 될 때 발행 안 잃는다"(Chrome 포함을 graceful-degrade 바닥 위에). 불변식: reddit이 뭘 하든 그날 발행 절대 안 막고 안 멈춘다.** (무인 flaky 5지점 대응:)
  - **① 디스플레이 env 명시 고정**: 서비스 `Environment=DISPLAY=:0`·`WAYLAND_DISPLAY=wayland-0`·`XDG_RUNTIME_DIR=/run/user/<uid>`(systemd user 세션이 인터랙티브 shell env 미상속).
  - **② 세션 만료 감지 → degrade + 기록**: preflight/ensure가 reddit 인증 프로브 → 풀렸으면 그 run은 **RSS+X로 degrade하고 run.json에 기록**(발행은 RSS+X로 성공하므로 quiet-day 알림 대상 아님 — reddit 전용 인증만료 알림은 P3d). 재로그인은 알림 받고 1회 수동. 조용한 다일 *미발행*은 없음(발행은 됨).
  - **③ 전용 자동화 프로필**(`--user-data-dir=~/.config/ai-daily/chrome-profile`) — 일상 브라우징 프로필과 분리(프로필 잠금 충돌 회피 + reddit 로그인 안정 격리). **1회 수동 = OpenCLI Browser-Bridge 확장 설치 + reddit 로그인 둘 다**(fresh `--user-data-dir`은 확장 0 → 로그인만으론 브리지 없어 reddit 죽음, advisor #3). 기동 시 `--load-extension=<브리지 확장 경로>` 필요할 수 있음(설치 방식은 plan에서 확인).
  - **④ 브리지 준비 게이트 = opencli 프로브(포트 아님)**: collect가 opencli↔확장으로 접속(직접 포트 아님 — `nbs/collect.py:65 fetch_reddit`가 `opencli reddit …` 호출, 미연결이면 출력에 `BROWSER_CONNECT`). readiness = Chrome 기동 후 값싼 `opencli` 프로브를 폴링해 **`BROWSER_CONNECT`가 안 나올 때까지**(상한 ~30s) 대기 후 진행. 계속 `BROWSER_CONNECT`면 degrade(RSS+X).
  - **⑤ bounded + 격리**: Chrome 기동/collect를 timeout으로 감싸고 넘으면 **Chrome kill + RSS+X degrade**(§5 격리 — run/flock 안 막음).
  - **Chrome 수명주기 vs flock (Codex R1 #6 — assumption 아닌 실제 가드)**: schedule.py가 flock **밖**에서 Chrome 기동(flock은 orchestrate 내부 소유)하되, ①**진입 시 non-blocking flock 프로브** — 이미 run 진행중이면 Chrome 안 띄우고 exit(launch-then-teardown-during-busy 원천 차단) ②teardown은 **자기가 띄운 PID만** kill(타 run/일상 Chrome 불가침). systemd `.service` 단일기동 + no-manual-run-in-window와 합쳐 수명주기 불변식이 실제로 성립.
  - **주의**: reddit-via-Chrome은 본질적으로 가장 불안정한 소스(라이브 GUI + 만료 세션). 보완의 목적 = 실패를 "조용히 죽음/멈춤"→"눈에 보이는 안전 degrade"로 바꾸는 것(신뢰성 보장 아님).
- **최소 quiet-day 알림 (Codex R1 #1/#2/#5 반영):** `ai-daily-alert.timer`(`OnCalendar` **12:00 Asia/Seoul** — 마지막 발행 tick 11:00이 정상 완료(~15분)된 뒤로 잡아 진행중 run과의 경합/오알림 최소화) → `python3 -m nbs.schedule --check-alert`:
  - **flock busy면 skip 아니라 bounded 대기 후 재확인**(#1 BLOCK — skip하면 그 run이 held/failed로 끝나도 그날 재판정이 없어 조용히 누락). flock 해제까지 짧게 대기(상한 예 5분) → 해제되면 재확인; 상한 넘도록 안 풀리면(=stuck run, 그 자체가 장애) 알림.
  - 판정 = **git-권위** "오늘 발행됨?"(`git cat-file -e origin/main:content/news/<date>.md`, orchestrate 가드와 동일 신호). 미발행이면 **알림메일 1회**(그날 1회 멱등 = 별도 alert-ledger `~/.config/ai-daily/`로 재알림 방지). 12:00은 마지막 스케줄 tick 이후라 이후 발행은 **수동 run뿐**(no-manual-run-in-window 가정으로 #2 false-alarm 커버).
  - **발송 = P3b gmail *프리미티브만* 재사용, `run_email` 금지(#5)**: `run_email()`은 origin에 오늘 news 없으면 `not_published`로 **미발송** — 정확히 quiet-day 조건이라 재사용하면 알림이 안 나감. 대신 email.py의 **토큰/creds 로드 + `build_message` + gmail send**만 재사용해 **별도 alert 본문**("오늘 미발행" + 날짜 + 마지막 `run.json` status/reason) + **별도 alert-ledger**로 보냄(gmail send 성공 후 기록 = `run_email` 패턴; send-후-기록-전 크래시는 수동 재시도 시 중복 가능·저위험, 자동경로는 flock 직렬화로 사실상 무해 — plan에서 필요시 `O_EXCL`). 이메일 실패해도 무한재시도 안 함(다음 날 다시 판정).
- **설치/배포 = repo 버전관리 유닛 + install 스크립트:** `deploy/systemd/ai-daily.service|.timer` + `ai-daily-alert.service|.timer`(repo) + `scripts/install_scheduler.sh` — 유닛을 `~/.config/systemd/user/`에 복사 → `systemctl --user daemon-reload && enable --now` → **`loginctl enable-linger $USER`**(로그인 세션 없이 부팅 시 user 타이머 실행 — WSL 무인 필수) → Chrome 자동화 프로필 디렉터리 안내. 유닛은 하드코딩 경로 대신 `%h`/`WorkingDirectory` 사용.
- **테스트(네트워크·Chrome 0):** `tests/test_schedule.py` — preflight **하드셋만 abort**(dirty write-set·git 자격없음 → 하드 abort) vs **soft는 abort 안 함**(hugo/deps/네트워크·디스플레이 없음 → 진행/degrade, 하드 abort 아님 — #3 회귀 방지) / flock busy 프로브 → Chrome 미기동·exit(#6) / quiet-day 판정(미발행→알림1회, 발행됨→무알림, 재호출 멱등=재알림X, flock busy→대기후판정 #1) / alert는 `run_email` 아닌 gmail 프리미티브 경로 사용(#5) / `orchestrate`·`email`·launcher 러너 **주입 seam**으로 stub(P3a/P3b 패턴 재사용) / `ensure_chrome`는 launcher·bridge 주입해 degrade 로직만 유닛(실 Chrome 없이). systemd 유닛 = `systemd-analyze --user verify`. **실 스모크(수동/Codex, Claude env)**: 실 Chrome+reddit 세션 1회 + 타이머 1발화 관측(무인 flaky부분 유닛 불가 — [[smoke-tests-via-codex]]).
- **exit코드:** 각 tick = orchestrate rc 전파(published/skipped=0, held/failed/push_rejected=비0); `--check-alert`=알림 보냄/안보냄 무관 0(관측용); preflight 하드실패=비0(이 tick abort).
- **범위 밖(P3d):** 실패 분류·reddit/인증만료 전용 알림·floor미달 알림·일일 메트릭·run.json 집계 대시보드.

**미결 (후속 단계):**
- News 카테고리 라벨 최종안.
- 이메일 추가 수신자(기본 `kimhyo75@gmail.com` 확정 — 추가분만 후속).
- 인증 저장 = **레포 밖 `~/.config/ai-daily/`로 P3b 확정**. ~~systemd timer 가용 여부 확인 (P3c)~~ **확인 완료(P3c): systemd user 타이머 + WSLg Chrome 가용.**

---

## 16. AX 경영 (3번째 1급 산출물)

**확정 (2026-07-03 — 사용자 요청):** News(개발자·창업자 톤)·UseCase(일반사용자 톤)와 평행한 **3번째 1급 일간 산출물 = AX 경영(경영자·임원 톤)**. AI 전환을 조직 운영 관점에서 재해석(시간 재투자·업무 폐지·판단권한 위임·역할 승급·이익 분배). 구조는 **UseCase 패턴을 그대로 복제**(신규 발명 0, 검증 파이프라인 재사용).

- **콘텐츠 = 하루 1페이지 synthesis**(항목 나열 아님). 그날 발행된 뉴스/블로그(publishable results의 title+source+slug+본문 snippet)를 입력받아 경영 관점 함의로 재구성: "이 소식이 조직을 어떻게 바꾸나 / 리더가 뭘 다르게 해야 하나".
- **⚠️ 콘텐츠 계약 = item-앵커 grounding (advisor R1 — BLOCK, §10 트러스트 경계):** 이 섹션의 최대 리스크는 "빈날 방지"가 아니라 **경영 신호 약한 날(흔한 경우)에 프롬프트가 그날 항목과 무관한 일반론(시간 재투자·역할 승급 같은 evergreen 원칙)을 지어내는 것**. `None` 가드는 publishable 개수만 보므로(오늘=14) 신호가 얕아도 풀페이지가 나온다 → 프롬프트로 강제:
  1. **모든 경영 주장은 그날의 구체적 항목에 앵커**(evergreen 원칙 나열 금지 — "오늘 X 소식 때문에 → 조직에서 Y를 바꿔라" 형태). 근거는 입력 요약뿐, 요약에 없으면 쓰지 마라.
  2. **짧아도 됨**을 명시 — 억지로 페이지 채우지 말고, 경영 각도가 실하게 붙는 1~3개만. 신호 약한 날은 "오늘은 조직 전환 관점 신호가 적다 + [해당되는 1~2개 항목]"로 짧게.
  3. 짧아도 되지만 **모든 포인트는 그날 항목 relref로 앵커**(위 결정적 게이트). 그날 groundable 경영 각도가 **전혀** 없으면 → 게이트가 `ValueError`로 거부 → §5 격리(`ax_error`) → **그날 AX 페이지 없음**(억지 일반론 발행보다 낫다). `build_ax`의 `None`은 UseCase와 동일하게 **publishable==0(빈날)** 담당, 게이트 실패는 `ValueError`→`ax_error`.
- **v1 상류 한계 (advisor R1 — 명시, 수정은 범위 밖):** AX는 `select`가 이미 개발자·창업자 관점으로 고른 publishable 블로그만 입력받는다 → **select의 편향을 상속**. 경영 관련 소식이 수집됐어도 블로그 컷을 못 넘으면 AX가 못 본다. 즉 v1 AX의 천장 = select가 표면화한 것. AX는 독립적으로 경영 콘텐츠를 사냥하지 않는다(전용 소스는 범위 밖).
- **톤/독자 = 경영자·임원.** 실행 지향(다음 분기에 뭘 바꾸나). 전문 코딩 용어 최소.
- **배선 (전부 UseCase 평행, 기존 스테이지 최소 수정):**
  - `prompts/ax.md` — 경영자 톤 프롬프트. UseCase와 동일 골격(규칙: 근거는 요약뿐·지어내지 마라 / 출력: front matter `title: AI 경영 브리핑 <DATE>`·`date`·`tags:[ax]` + 본문 / `<<SUMMARIES>>` 입력 치환).
  - `nbs/assemble.py` — `AX_PROMPT` 상수 + `build_ax(results, date, *, run=None)` = `build_usecase` 복제(claude -p `run_claude_notools`=`--tools ""`, `_strip_fences`, front matter `{title,date,tags}` 검증 + 비지않은 body, publishable 없으면 `None`). `<<SUMMARIES>>` 생성은 `build_usecase_prompt`의 라인빌더 재사용(중복 최소화 — 공통 헬퍼로 추출 또는 프롬프트경로 파라미터화).
  - **⚠️ 결정적 grounding 게이트 (Codex R1 — BLOCK 수정):** 프롬프트만으로는 계약이 *방향*일 뿐 강제가 아니다(build_usecase 검증은 front matter+빈body만 봐서 evergreen 일반론도 형식만 맞으면 통과). 따라서 `build_ax`에 **기계적 게이트**(**필요조건이지 충분조건 아님** — 아래 (c) 참고): 프롬프트가 각 경영 포인트를 그날 항목에 `{{< relref "/posts/<slug>.md" >}}`로 **링크**하도록 지시하고, `build_ax`는 본문에서 slug을 추출해 조건 요구 —
  - (a) **교집합 ≥1**(그날 항목에 실제 앵커; 0이면 순수 일반론 → 거부).
  - (b) **추출 slug 전부가 그날 publishable slug ∈**(할루시네이션 slug 링크가 Hugo 빌드를 깨는 것 방지 — news 완결성 `링크==ok-slug`와 동일 결정적 패턴).
  - **⚠️ (c) 형태 일관 (advisor R2 — MAJOR):** slug 추출은 **angle 형태만**(email `_RELREF_FULL` = `{{< relref "/posts/<slug>.md" >}}`) 인정하고, `publish._RELREF`(내부 토큰만 매칭 → `{{% relref %}}`도 통과)를 그대로 쓰지 마라. + 본문에 비-angle ref/relref shortcode(`{{% relref %}}`·`{{< ref >}}`)가 남으면 거부(email `_ANY_REF_SHORTCODE` parity). 이유: email `rewrite_relref`는 angle만 재작성하고 leftover `{{%`엔 **raise**하므로, 게이트가 permissive 토큰을 허용하면 AX가 렌더는 되고 **그날 이메일만 조용히 실패**한다(AX는 LLM 생성이라 유일하게 노출; news는 assemble이 angle만 emit). 게이트를 email과 **동일 angle 형태**로 맞춰 **gate-pass ⟹ email-safe ⟹ Hugo-safe** 일관.
  위반 시 `ValueError`로 거부(§5 격리 → `ax_error`, 그날 AX 페이지 없음 — 억지 일반론/깨진 빌드/이메일 실패보다 낫다). §4 트러스트 경계 정합. 부수효과: AX 페이지가 근거 항목으로 클릭연결(UX↑).
  - **한계 명시(advisor R2):** 이 게이트는 **degenerate(무앵커) 케이스만** 막는다. 90% 일반론 + 장식용 링크 1개인 fig-leaf 페이지는 형식상 통과한다 → 그건 **프롬프트 계약 + 사람 eyeball**이 담당(게이트만 믿지 마라).
  - `nbs/stage.py` — `run(date, *, fetch=None, generate=None, usecase=None, ax=None)`(**기존 `=None` 기본값 보존** — CLI `run(a.date)` 무인자 호출 안 깨지게, Codex R1), `ax`는 기본 `asm.build_ax` 주입. UseCase 블록 옆에 `staging/ax/<date>.md` 생성, **§5 격리**(ax claude -p 실패=timeout/bad output → abort 금지, `ax_error` 기록). `generation.json`에 `ax_error` 필드 추가(usecase_error 평행). staging 하위디렉터리 목록에 `ax` 추가.
  - `nbs/publish.py` — `date_writeset`에 `content/ax/<date>.md` 추가. `promote`에서 ax staging→content 승격(usecase와 동일 optional: 있으면 `_cp`, 없고 target 존재하면 stale drop). `build_verify`에 `ax/<date>/index.html` 렌더 확인(content ax 있을 때만). `_degraded`에 `ax`(=`gen["ax_error"]`) 추가.
  - `hugo.toml` — ① `[[menu.main]]` `name="AX 경영"` `url="ax/"` `weight=0`(**최상단**, News 앞). ② **`params.mainSections`에 `"ax"` 추가(Codex R1 — 필수 터치포인트):** 현재 `["news","posts","usecase"]`인데 PaperMod가 홈 목록·아카이브·prev/next를 이 값으로 필터하므로, 빠지면 AX가 메뉴엔 보여도 홈/아카이브/nav에서 UseCase와 평행하지 않게 됨. PaperMod가 `/ax/` 섹션 자동 렌더(커스텀 layout 불필요).
- **이메일 (P3b 확장):** `nbs/email.py` `read_content(date)`가 ax도 읽음(`git show origin/main:content/ax/<date>.md`, 없으면 `None` — usecase와 동일 optional). 본문 = News + UseCase + **AX 경영** 3섹션(각 preprocess). 게이트는 news 존재 불변(변경 없음). `read_content` 반환 형태 확장(현 `(news, usecase)` → `(news, usecase, ax)`); 관련 테스트 갱신. 저녁 reauth 후 발송분부터 적용.
- **오늘치(2026-07-03) 즉시 반영:** 구현 후 오늘 14 results로 `build_ax` 1회 실행 → `content/ax/2026-07-03.md` 생성. **⚠️ push 전 grounding eyeball(advisor R1/R2):** 오늘은 진단상 최악-신호일이자 사용자가 기능을 판단할 페이지. 게이트는 "링크 있음"만 답하므로 **eyeball은 산문 실질을 읽는다** — 각 경영 주장이 링크된 그날 항목에서 **실제로 도출**됐나, 아니면 링크가 장식이고 본문은 일반론(fig-leaf)인가. **fig-leaf/evergreen으로 읽히면 발행 보류 → 프롬프트 계약 재조정**("발행 성공"이 "grounded"를 대체하지 않는다; 게이트 통과도 fig-leaf를 대체하지 않는다). 통과 시에만 publish 재실행(ax 포함) → push. (실 `claude -p` 1회 — Claude env, [[2026-07-02-claude-p-fails-under-codex-exec]].)
- **테스트(네트워크 0):** `build_ax`(주입 run stub) — publishable 0 → `None` / front matter 누락 → ValueError / **grounding 게이트 각 조건별**: angle relref 0개(무앵커 일반론) → ValueError〔(a)〕 / valid slug + hallucinated(비-publishable) slug 섞임 → ValueError〔(b)〕 / `{{% relref %}}`·`{{< ref >}}` 잔존 → ValueError〔(c)〕 / **angle-form `{{< relref >}}` + 추출 slug 전부 publishable + ≥1** → 통과. · stage ax 격리(ax 실패 → ax_error 기록, 나머지 진행) · publish ax optional 승격+writeset+build_verify · email read_content ax 포함(fake git repo) · `params.mainSections`에 ax 포함(hugo.toml 검증). UseCase 테스트 평행.
- **범위 밖(defer):** AX 경영 전용 수집 소스(현 소스로 충분) · 과거 날짜 백필 · AX 경영 전용 커스텀 layout.

---

## 부록 A. Codex 적대 리뷰 반영 이력 (캡 2라운드)

- **R1 (2026-07-01):** 12개 결함 접수. 반영 — 계층적 grounding+최소발행기준(§4), 실행 한도·실패격리(§5), event_key·confidence·keep편향(§6), preflight·catchup·알림(§7), 원자적 발행·idempotency(§8), 이메일 idempotency(§9), 프롬프트 인젝션·시크릿 강화(§10), **저작권 정책 신설(§11)**, 관측성(§12). 보류(YAGNI) — 임베딩/event cluster/quarantine 큐/Slack(§13).
- **R2 (2026-07-01):** 신규 CRITICAL 없음. R1 결함 7개 OK / 5개 부분(대부분 미정값 §15). 추가 반영 — 최소발행 floor 명확화·top story 보호(§4), 원문 기반 도구호출 금지(§10), run_id 아티팩트 보존(§12). 나머지 부분(timeout·예산·인증저장 구체값)은 writing-plans에서 확정. 로컬 PC 단일 장애점은 비용0 선택의 수용 트레이드오프(catchup+알림으로 완화). **수렴 — 리뷰 종료.**
- **사용자 결정 (2026-07-01):** Codex가 CRITICAL로 본 저작권 리스크에 대해, 사용자가 "최대한 자세히(번역에 가깝게)"를 명시 선택. §11을 깊이=최대 / 형태=재서술 / 라이선스 차등 / 페이월 우회 금지 / takedown 안전판으로 갱신. 잔여 리스크는 사용자 명시 수용(미해결이 아니라 수용된 결정).

### P3b 이메일 스펙 리뷰 (2026-07-03)
- **advisor R1:** 4건 — ① 시크릿 레포내 저장이 §10(레포밖) 위반(공개레포=치명) ② 재사용 토큰 광역 scope=계정탈취 blast radius ③ 이식 `_build_message` html-only=§9 텍스트fallback 누락 ④ 프로세스: Codex 패킷에 newsNblog 코드 포함해야 fidelity 판정 가능. + 명료화(run_id 순서, --force 전파). 전부 반영.
- **Codex xhigh R1:** 40건(BLOCK 8·MAJOR 다수·MINOR). **반영(accepted):** 토큰 레포밖+gmail.send단일+chmod강제+원자적write-back(#1/3/4/5/34), ledger 레포밖+per-recipient게이트+O_EXCL임계구역(#6/7/31/32), href escape이중화+scheme검사강화+web_url validator+code선토큰화(#20/21/22/23/26), front matter·relref는 기존 `parse_frontmatter_strict`·`_RELREF` 재사용+relref잔존시 실패(#14/15/17/19), multipart/alternative(#27), From헤더+CRLF헤더인젝션방어+수신자검증(#28/29/30), 발송게이트=`publish.json.pushed`(#9/10/13/36), ledger=발송권위·run.json=관측(#12), usecase degraded규칙(#37), 640px(#2), SITE_BASEURL config단일화(#38), KST date(#39), 테스트확장(#40), Message-ID+gmail_id병기(#33), token_invalid reason(#35). **부분반려:** #8 `--force`에 별도 `--confirm` 요구 → 수동 명시 플래그라 과함(force행 reason 기록으로 갈음). **완화:** #18 slug URL-escape → 상류 `_SLUG_RE`가 charset보장이라 불필요(명시만). #25 LINK_RE 괄호URL → 알려진 한계 명시+테스트(우리 링크 괄호없음).
- **R2 (2026-07-03) — 수렴 게이트:** **advisor R2** = 1 BLOCK: R1 fold의 발송게이트 `publish.json.pushed`(scratch)가 P3a git-authoritative 원칙 위배(wipe 후 standalone 재발송 false-negative) → **게이트를 `git cat-file -e origin/main:content/news`로 교체**(fix=correctness+단순화). + 과over-build 지적 → per-recipient·lockfile·Message-ID·원자적write-back을 **plan로 위임**(스펙은 결정/불변식만). **Codex R2**(수렴 스코프) = 2 BLOCK(모두 fold가 만든 내부모순): ①usecase 포함이 git-존재 vs `publish.json.degraded` 이중정의 → git-존재로 일원화 ②게이트 ref(origin/main) vs 본문 read(온디스크) 불일치 → **본문도 `git show origin/main:...` 동일 ref**로. 셋 다 반영. **2R 캡 도달 — 리뷰 종료.**

### AX 경영(§16) 스펙 리뷰 (2026-07-03)
- **advisor R1:** BLOCK — optional/None 가드가 post-count만 봐서 약신호일에 항목무관 일반론 날조(§10 위배). + v1 상류 한계(select 편향 상속) 명시 + 오늘치 rollout grounding eyeball 게이트. **Codex R1:** MAJOR `params.mainSections`에 ax 누락(PaperMod 홈/아카이브/nav 필터), MAJOR `stage.run` `=None` 기본값 보존, **BLOCK** grounding 계약이 프롬프트만(강제 아님)→ **결정적 게이트**(본문 relref가 그날 slug에 앵커) 신설. 전부 반영.
- **R2 수렴:** **advisor R2** = MAJOR 게이트가 `publish._RELREF`(내부토큰) 쓰면 `{{% relref %}}`도 통과→그날 이메일만 조용히 실패(email은 angle만 재작성+leftover에 raise) → 게이트를 **angle-form(email `_RELREF_FULL`) 일관**으로 + 비-angle shortcode 거부(gate-pass⟹email·Hugo-safe). + 게이트는 필요조건이지 충분조건 아님(fig-leaf=프롬프트+eyeball 담당) 명시. **Codex R2** = 모순 1: 테스트 bullet이 게이트 (b)(c) 미반영("≥1→통과"로 축약) → 조건별 테스트로 정합. 반영. **2R 캡 도달 — 종료.**

### P3c 스케줄러(§15) 스펙 리뷰 (2026-07-03)
- **advisor R1:** 3건 — ①(치명 후보) systemd user 타이머는 WSL이 떠야 발화하는데 WSL2는 부팅 시 자동시작 안 함 → 무인 실패 가능. **검증 결과 정정**: disable한 newsNblog는 Windows측 `cmd`라 WSL 기동과 무관(내 disable이 원인 아님). **사용자 결정 = WSL 상시기동 전제로 systemd 유지**(잔여 SPOF는 §270 수용, 후속 최소 Windows starter로 완화 가능). ②`OnCalendar`가 시스템 TZ로 발화(UTC면 16시 KST)=buildFuture 쌍둥이 → `Asia/Seoul` 명시. ③전용 Chrome 프로필은 reddit 로그인만이 아니라 **Browser-Bridge 확장 설치도** 1회 필요(fresh `--user-data-dir`엔 확장 0). + 비블로킹(Chrome 수명 vs flock, explicit OnCalendar 라인). 전부 반영/정정.
- **Codex xhigh R1:** 1 BLOCK + 5 MAJOR. **①(BLOCK)** 11:30 알림이 flock busy면 skip→그 run이 held/failed로 끝나도 재판정 없어 조용한 누락 → **알림 12:00 이동 + busy면 bounded 대기 후 재확인(skip 아님)**. **②** 11:31 발행 false-alarm → 12:00(마지막 tick 이후)+no-manual-run 가정. **③** preflight가 hugo/deps로 push_only 복구까지 오abort → **하드셋=write-set clean+git identity/creds만, hugo/deps/net=soft**(orchestrate stage-rc가 처리). **④** TZ assert가 무의미 abort(Asia/Seoul+config.KST라 무관) → **TZ 체크 제거**. **⑤** `run_email`은 news 없으면 `not_published`로 미발송=quiet-day 조건과 상충 → **gmail send 프리미티브(`build_message`/`load_credentials`/`_gmail_send`)만 재사용, 별도 본문·ledger**. **⑥** busy 시 teardown이 타 run Chrome kill → **ensure_chrome 前 non-blocking flock 프로브(busy=Chrome 없이 exit)+self-PID만 kill**. 전부 반영.
- **Codex R2:** BLOCK/MAJOR 0 — fix 6건 전부 closed 확인(프리미티브 존재·narrowed preflight가 partial-write 안 만듦·flock 프로브 가능). minor: alert-ledger=send 성공 후 기록(크래시 중복은 저위험, 자동경로 flock 직렬화로 무해) → 스펙 명시. **2R 캡 도달 — 종료.**
