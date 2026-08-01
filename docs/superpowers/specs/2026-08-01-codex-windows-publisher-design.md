# Codex Windows AI Daily Publisher Design

## 목적

WSL의 `/home/beaten/project/NBs`에서 Claude CLI로 실행되던 AI Daily 발행 체계를 Windows Codex 환경으로 재구성한다. 기존 Hugo 사이트, Git 이력, 발행 기사와 중복 방지 원장은 보존하되 Linux·Claude·브라우저 브리지에 묶인 실행 계층은 이식하지 않는다.

완료 상태는 다음과 같다.

- Windows에서 수집, 선별, 작성, 검증, 게시 준비를 수행한다.
- 오전 7시 이전에 준비를 끝내고 오전 7시부터 검증된 결과만 게시한다.
- 정상적인 날에는 유의미한 개별 기사 30편 이상을 목표로 하며 상한은 두지 않는다.
- 10~29편은 정상 발행, 1~9편은 경고와 함께 발행, 0편은 발행하지 않는다.
- 일반 종합 리포트, 개별 기사, 경영 브리핑, 활용 가이드가 서로 다른 콘텐츠 영역과 피드에 놓인다.
- 국내외 원문을 수집하지만 발행물에는 원문 본문을 복제하지 않고 출처 링크만 제공한다.

## 확인된 기존 문제

### 발행 중단

- WSL의 Claude CLI 인증이 풀려 2026-07-28 이후 선별 단계가 매일 실패했다.
- 실패 로그가 표준 오류의 일부만 남겨 실제 인증 원인이 빈 메시지처럼 보였다.

### 수집원 부족

- 실제 후보는 RSS 9개, X 검색어 4개, Reddit 2개 서브레딧에 한정됐다.
- X CLI는 현재 검색 요청에서 오류가 나며, Reddit 수집은 NVM의 Node와 Chrome Browser Bridge에 의존한다.
- systemd 환경에는 필요한 Node 경로가 없어 Reddit 수집이 실행될 수 없었다.
- SNS가 0건이어도 전체 실행은 정상처럼 계속돼 운영자가 수집 장애를 알아보기 어려웠다.

### 기사 수 누락

- 선별 프롬프트에 목표 기사 수나 최소 품질 계약이 없었다.
- 코드에는 `MAX_SELECTED = 20` 상한이 있어 30편 목표를 구조적으로 달성할 수 없었다.
- 모델이 반환하지 않은 후보는 제외 사유 없이 사라졌고 `skipped_count`에도 포함되지 않았다.

### 콘텐츠 혼합

- Hugo `mainSections`가 `ax`, `news`, `posts`, `usecase`를 모두 포함해 홈페이지에서 네 유형을 섞었다.
- 이메일도 같은 날짜의 뉴스, 활용 가이드, AX 경영 브리핑을 한 본문으로 합쳤다.
- 이는 우발적인 표시 오류가 아니라 기존 구현의 명시적 동작이다.

### Windows 비호환

- `fcntl`, Bash 설치 스크립트, `chmod 600`, Linux 프로세스 그룹, `~/.git-credentials`, systemd가 핵심 경로에 포함돼 있다.
- 2026-08-01 Windows 기준선 테스트는 `ModuleNotFoundError: No module named 'fcntl'` 때문에 테스트 수집 단계에서 중단됐다.

## 선택한 접근

기존 발행 자산 보존과 파이프라인 재구축을 결합한다.

보존 대상:

- Git 이력과 GitHub Pages 원격 저장소
- Hugo와 PaperMod 테마
- 기존 `/news/`, `/posts/`, `/ax/`, `/usecase/` URL 및 콘텐츠
- `data/published.csv`의 중복 방지 이력
- 단계별 격리, 스테이징, 날짜 단위 롤백, Git 원자성, 이메일 멱등성, SSRF 방어

교체 대상:

- Claude CLI 호출
- X 비공식 CLI와 Chrome Browser Bridge 기반 Reddit 수집
- systemd와 Bash 예약 설치
- Linux 전용 잠금, 프로세스, 권한 및 Git 자격증명 확인
- 콘텐츠 유형을 한 화면과 이메일에 합치는 조립 규칙

## 전체 구조

```text
Windows Task Scheduler
  -> deterministic collectors
  -> candidates.json + source_health.json
  -> normalize, canonicalize, deduplicate
  -> isolated codex exec selection
  -> selection.json (선택 items + 전 후보 decisions)
  -> deterministic evidence fetch
  -> isolated codex exec article generation
  -> staging/articles + staging/daily + staging/executive + staging/guides
  -> deterministic validation + Hugo build
  -> atomic Git commit/push
  -> default daily email
```

Python 오케스트레이터가 상태 전이와 외부 변경을 소유한다. Codex는 후보의 편집 판단과 한국어 원고 작성만 담당한다. Codex가 Git, 이메일, 예약 작업 또는 발행 경로를 직접 변경하지 않는다.

## Codex 실행 경계

`codex exec`는 저장된 ChatGPT 인증을 사용한다. 각 호출은 다음 조건을 만족한다.

- `--ephemeral`
- `--sandbox read-only`
- `--ignore-user-config`
- `--ignore-rules`
- `--skip-git-repo-check`
- 날짜별 `runs/<date>/codex-work/` 격리 디렉터리에서 실행
- `--output-schema`와 `--output-last-message`로 구조화된 최종 결과 저장
- 프롬프트와 후보 데이터는 표준 입력으로 전달

Codex는 저장소나 사용자 홈을 작업 디렉터리로 받지 않는다. 수집된 본문은 신뢰할 수 없는 데이터로 명시하며, 결과는 스키마, 후보 URL 멤버십, 필드 일치 검증을 모두 통과해야 한다.

## 후보와 출처 계약

각 후보는 최소한 다음 값을 가진다.

- `source`: 실제 발행자
- `source_type`: `article`, `sns`, `paper`, `repo`, `video` 중 하나
- `lane`: `official`, `media`, `social`, `research`, `developer`, `web` 중 하나
- `discovered_via`: RSS 피드, API, 검색어 또는 계정 식별자
- `url`: 독자에게 제공할 원출처 URL
- `canonical_url`: 추적 매개변수를 제거한 중복 판단 URL
- `published_at`, `title`, `snippet`, `raw_id`

선별 모델은 `source`, `source_type`, `lane`, `url`을 변경하지 못한다. 모델은 후보 식별자, `select|skip`, 중복 상태, 순위, 이유 코드와 짧은 근거만 반환한다. 로컬 코드는 모든 후보가 정확히 한 번 결정됐는지 검증하고 누락된 후보가 있으면 선별 단계를 실패시킨다.

## 수집 전략

매 실행은 다음 경로를 모두 시도한다.

- 공식 출처: AI 기업, 연구기관, 정부, 규제기관의 RSS·Atom·공식 API
- 전문 매체: 기술·AI·산업·비즈니스 매체의 공개 피드
- SNS·커뮤니티: X 공식 API, Bluesky 공개 API, Reddit 공식 API, Hacker News 공개 API
- 개발·연구: GitHub 공개 API·릴리스 피드, arXiv 및 공개 학술 피드
- 웹 발견: 공개 검색 API 또는 Codex의 격리된 보조 발견 결과

자격증명이 필요한 X와 Reddit은 자격증명이 없을 때 조용히 0건을 반환하지 않고 `unconfigured` 상태를 기록한다. 비공식 브라우저 자동화나 사용자의 로그인 세션을 기본 수집 경로로 사용하지 않는다.

SNS와 웹 검색은 발견 경로다. 공식 발표나 원자료가 존재하면 `url`은 원자료를 가리킨다. SNS 게시물 자체가 최초 발표인 경우에만 그 게시물을 원출처로 쓴다. 웹 발견 후보도 실제 URL을 다시 가져와 증거 수준을 판정하기 전에는 기사 생성에 들어가지 않는다.

`source_health.json`은 경로별 상태, 후보 수, 경과 시간, 오류 요약을 기록한다. 한 경로의 실패는 나머지 수집을 막지 않지만, SNS 전체 0건이나 모든 공식 출처 실패는 실행 결과에 경고로 남는다.

## 선별과 발행량

선별 기준은 최신성, 영향도, 근거 품질, 신규성, 한국 독자 관련성이다. 단순 홍보, 근거 없는 주장, 동일 사건의 반복 보도, 최근 발행물과 실질적으로 같은 내용은 제외한다.

- 목표: 유의미한 개별 기사 30편 이상
- 상한: 없음
- 10~29편: 정상 발행
- 1~9편: 발행하고 부족 경고 기록
- 0편: 게시와 이메일 중단

30편을 채우기 위해 품질 기준을 낮추지 않는다. 기사 수에는 종합 리포트, 경영 브리핑, 활용 가이드를 포함하지 않는다.

## 콘텐츠 구조

새 발행물은 다음 경로를 사용한다.

- `content/daily/<date>.md`: 일반 AI 종합 리포트
- `content/articles/<date>-<event-key>.md`: 개별 한국어 기사
- `content/executive/<date>.md`: 경영·AX 브리핑
- `content/guides/<date>.md`: 실제 활용 가치가 있을 때만 생성하는 가이드

기존 콘텐츠는 이동하지 않아 기존 링크를 보존한다. 중복 방지 원장은 기존 `/posts/`와 새 `/articles/` 경로를 모두 이해한다.

홈페이지와 기본 RSS는 `daily`만 표시한다. 종합 리포트는 짧은 요약과 개별 기사 링크를 제공한다. `executive`와 `guides`는 각각 별도 메뉴와 목록을 가진다. 일반 기업·산업 뉴스는 `articles`에 포함하지만 경영진을 위한 해석과 실행 제안은 `executive`에만 둔다.

기본 이메일은 `daily`만 읽고 경영 브리핑이나 가이드 본문을 합치지 않는다. 첫 구현에서는 경영 전용 이메일을 추가하지 않는다.

각 개별 기사는 한국어로 작성하며 다음을 포함한다.

- 무엇이 발표되거나 발생했는지
- 왜 중요한지
- 확인 가능한 범위와 불확실성
- 출처명, 출처 발행일, 원문 링크

원문 본문이나 긴 인용문은 재게시하지 않는다.

## 단계, 체크포인트와 외부 변경

각 단계는 날짜별 JSON 산출물을 원자적으로 기록한다. 재실행은 유효한 체크포인트를 재사용하고 실패 단계부터 계속한다.

- `collect`: 후보와 수집원 상태
- `select`: 모든 후보의 선택·제외 결정
- `stage`: 증거 수집, 개별 기사, 파생 콘텐츠
- `validate`: 경로, 링크, 중복, 메타데이터, Hugo 빌드
- `publish`: 검증된 날짜 쓰기 집합만 승격하고 커밋
- `push`: 원격 상태를 확인한 뒤 해당 커밋만 푸시
- `email`: 원격에 게시된 `daily`만 한 번 발송

기사 하나의 증거 수집이나 생성 실패는 해당 기사만 제외한다. 게시 전 검증 실패는 Git과 이메일 변경 없이 종료한다. 이메일은 원격 게시 성공 후에만 실행한다.

## Windows 예약 실행

Windows Task Scheduler를 핵심 예약 실행기로 사용한다. Codex 앱 예약 작업은 로컬 앱 실행 상태에 의존하므로 핵심 게시자가 아니라 운영 모니터 용도로만 고려한다.

- 06:00 KST: 준비 실행. 수집, 선별, 증거 수집, 작성, 조립, 검증까지 수행
- 07:00 KST: 게시 실행. 준비된 체크포인트를 다시 검증한 뒤 Git 게시와 이메일 실행
- 준비가 끝나지 않았으면 게시 실행은 변경 없이 재시도 가능 상태로 종료
- Task Scheduler는 10분 간격으로 제한된 횟수만 재시도
- 12:00 KST: 최종 미발행 경고 확인

예약 등록 스크립트는 PowerShell로 작성하고 현재 사용자, 절대 Windows 경로, 현재 Python과 Codex 실행 파일을 명시한다. 실제 작업 등록과 기존 WSL timer 중지는 별도 사용자 승인 후 수행한다.

## 테스트와 전환

필수 자동 검증:

- Windows 잠금과 동시 실행 차단
- 수집기별 파싱, 제한 시간, 실패 격리, 상태 기록
- 후보 URL 정규화와 사건 중복 제거
- 모든 후보 결정 완전성 및 후보 필드 불변성
- Codex 출력 스키마, URL 멤버십, 원문 비복제 규칙
- 기사 수 `0`, `1`, `9`, `10`, `30` 경계
- `daily`, `articles`, `executive`, `guides` 경로와 홈페이지 분리
- 기본 이메일에 `daily` 외 콘텐츠가 섞이지 않음
- 날짜 단위 롤백, Git divergence, 중복 이메일 방지
- Windows Task Scheduler 명령 생성과 준비·게시 재개

전환 전에 3~5일 연속 섀도 실행한다. 섀도 실행은 수집부터 Hugo 빌드까지 수행하지만 커밋, 푸시, 이메일을 실행하지 않는다. 각 날에 다음을 확인한다.

- 수집 경로별 상태와 후보 수가 보인다.
- 유의미한 기사 수와 제외 이유가 설명 가능하다.
- 생성된 페이지가 서로 다른 콘텐츠 영역에 놓인다.
- 준비가 오전 7시 이전에 끝난다.
- 실패 후 재실행이 같은 결과를 중복 생성하지 않는다.

섀도 실행 통과 후에만 Windows 게시 작업을 활성화하고 WSL timer를 중지한다. 전환 후 첫 일주일은 WSL 저장소를 읽기 전용 롤백 기준으로 보존한다.

## 범위 제외

- 새 CMS 또는 새 웹 프레임워크 도입
- 기존 콘텐츠 URL의 일괄 이동
- 비공식 로그인 세션이나 브라우저 확장 기반 SNS 수집
- 기사 수를 맞추기 위한 품질 기준 완화
- 경영 브리핑 별도 이메일 구독 시스템
- 사용자 승인 없는 Git 푸시, 실제 이메일, Task Scheduler 등록, WSL timer 중지
