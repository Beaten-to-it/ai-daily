---
title: 'Bun을 사람 대신 AI로 Rust에 통째 이식하다 — 11일, 6,778커밋, 16만 5천 달러의 실측 기록'
date: 2026-07-10
tags: [Bun, Rust, Zig, AI코딩, 에이전틱엔지니어링, 런타임]
source_url: https://news.hada.io/topic?id=31263
source_lang: ko
source_type: article
evidence_level: confirmed
event_key: bun-rust-rewrite
---

Zig로 시작해 월 2,200만 다운로드까지 큰 JavaScript 런타임 Bun이, 53만 줄이 넘는 코드베이스를 사람이 아니라 수십 개의 Claude Code 워크플로우로 Rust에 통째로 옮겼다. 그리고 그 과정과 비용, 함정을 이례적으로 투명하게 공개했다. "AI가 대형 재작성을 실제로 해냈다"는 첫 번째 본격 사례이자, 동시에 그 비용과 전제조건까지 드러난 기록이라 곱씹을 지점이 많다.

## TL;DR

- Bun은 535,496줄(주석 제외)의 Zig 코드를 **약 50개의 Claude Code 동적 워크플로우 + 최대 64개 병렬 인스턴스**로 **11일 만에** Rust에 기계적으로 이식했고, 6개 플랫폼 CI에서 테스트 100% 통과에 도달했다.
- 그 결과인 Bun v1.4.0(첫 Rust 버전, 현재 canary)은 v1.3.14에서 재현되던 **버그 128개를 수정**하고, instrumentable 메모리 누수를 전부 없앴으며, Linux·Windows 바이너리를 **약 20% 축소**하고 HTTP 처리량 등에서 **최대 4.8%** 성능이 올랐다.
- 다만 이건 **출시 전 모델(Claude Fable 5)**로, **API 기준 약 16만 5천 달러**를 쓴, **Anthropic이 소유한**(2025년 12월 인수) 프로젝트라는 전제를 함께 봐야 한다 — "누구나 Rust로 다시 쓰면 된다"로 일반화하기엔 조건이 특수하다.

## 무슨 일이 있었나

Bun은 원래 esbuild의 트랜스파일러를 Go에서 Zig로 라인 단위 포팅하며 출발한 프로젝트다. 초기엔 한 사람이 1년간 Zig로 트랜스파일러·번들러·패키지 매니저·테스트 러너·Node.js 호환 API까지 넓은 범위를 구현했다. 지금은 Claude Code와 OpenCode가 런타임으로 쓰고 Vercel·Railway·DigitalOcean이 1st-party 지원을 붙일 만큼 커졌다.

문제는 안정성이었다. Bun은 GC 기반 JavaScript 엔진(JavaScriptCore)과 수동 메모리 관리를 동시에 다뤄야 했는데, 이 조합이 반복적인 메모리 버그의 근원이었다. v1.3.14에서 고친 버그 샘플만 봐도 `node:zlib`의 async write 중 reset 호출로 인한 use-after-free, `node:http2` 재진입 콜백이 hashmap rehash를 유발해 스트림 포인터가 무효화되는 문제, `valueOf()`/`toString()` 콜백이 ArrayBuffer를 detach시키는 문제, CSS 파서의 double-free, `MessagePort` 동시 접근 race condition 등이 줄줄이 나온다. 팀은 이미 Zig 컴파일러에 ASAN을 패치하고, Fuzzilli로 24/7 퍼징하고, e2e 누수 테스트를 돌리는 등 방어 장치를 겹겹이 두고 있었다. 그래도 계속 샜다.

핵심 진단은 "Zig가 나쁘다"가 아니라, **GC 값과 수동 관리 메모리의 lifetime을 정확히 다루는 일 자체가 안정성 문제의 큰 원천**이라는 것이었다. Zig의 cleanup은 각 call site에 `defer`/`errdefer`를 명시하는 방식이라 누락·중복 해제가 나기 쉽다. 반면 Rust의 안전한 코드에서는 use-after-free, double-free, error path의 누락된 free가 **컴파일 오류**가 된다. C++도 후보였지만 여전히 스타일 가이드와 코드 리뷰에 의존하고 ASAN이 있어도 손상·누수가 난다는 이유로 밀렸다.

### 왜 "한 번에, 기계적으로"였나

53만 줄을 전통적으로 재작성하면 작은 팀이 1년쯤 걸릴 일이다. 하지만 그동안 버그·보안·기능 개발을 멈출 수 없었다. 그래서 사용자 동작 변경을 최소화하는 **기계적 전체 포팅**이 가장 위험이 낮은 선택으로 채택됐다. 결정적 자산은 **테스트 스위트가 TypeScript로 작성돼 런타임 구현 언어와 무관**했다는 점이다 — 구현 언어를 통째로 바꿔도 검증 기준은 그대로 살아있었다. Rust 코드는 "Zig를 transpile한 것처럼" 보이게 쓰고, v1.4 이후 점진적으로 `unsafe`를 줄여 idiomatic Rust로 리팩터링하는 방향을 잡았다.

### 어떻게 굴렸나 — 워크플로우와 적대적 리뷰

Claude와 약 3시간 논의해 Zig 패턴↔Rust 패턴 매핑을 `PORTING.md`로 직렬화하고, 모든 struct field의 lifetime을 분석해 `LIFETIMES.tsv`로 저장하는 사전 작업을 거쳤다. 그 위에서 약 50개 워크플로우가 11일간 돌며 포팅 가이드 작성 → 파일 변환 → 컴파일 오류 수정 → subcommand 복구 → 전체 테스트 통과 → 대규모 cleanup으로 이어졌다.

구조의 핵심은 **적대적 리뷰**다. 각 구현 Claude와 별도 context에 리뷰어 Claude를 두고, 리뷰어는 diff만 받은 채 "코드가 틀렸다고 가정하고" 버그를 찾도록 지시받았다. 기본 편성은 **구현자 1 + 적대적 리뷰어 2 이상 + fixer 1**. 리뷰어가 실제로 잡은 버그들은 전부 컴파일은 통과하되 동작이 틀린 것들이었다 — 예: `Box<uv::Pipe>`가 match arm 끝에서 drop돼 비동기 `uv_close`가 freed memory를 들고 있게 되는 use-after-free, 음수 file time에서 `trunc()`가 음수 nsec를 만드는 오류, `unwrap_or`가 인자를 eager 평가해 `color-mix()` 생략 케이스에서 panic하는 오류. 작성자와 리뷰어의 context를 분리한 이유도 사람 리뷰와 같다 — "merge하고 싶은" 구현자의 편향을 줄이려는 것이다.

실행 규모는 만만치 않았다. 전체 1,448개 `.zig` 파일을 옮기기 전 3개 파일로 절차를 검증했고, 초기엔 여러 Claude가 `git stash`/`git reset --hard`로 서로 충돌해서 "특정 파일 커밋 외의 git 명령 금지, `cargo` 같은 느린 명령 금지" 규칙을 추가해야 했다. 최종적으로 4개 shard × 4개 worktree, 각 shard에 16개 Claude가 붙어 peak에 **분당 약 1,300줄**을 썼다. 순환 의존성을 풀자 약 **16,000개 컴파일 오류**가 드러났고 crate별 병렬로 수정했다. "모든 crate를 컴파일되게 하자"를 함수 stub 생성으로 오해하는 false start, 긴 주석으로 workaround를 정당화하는 패턴("문단 길이 주석이 필요하면 코드가 틀린 것이다"라는 리뷰 규칙 추가) 같은 삽질도 정직하게 적혀 있다.

### 검증과 비용

첫 CI 실행 이틀 뒤 실패 파일이 972개에서 23개로 줄었고, 하루 반 뒤 Linux가 완전히 green이 됐다. 최종적으로 macOS x64/arm64, Linux x64/arm64, Windows x64/arm64 6개 플랫폼 전체가 통과했다. 테스트는 삭제·skip되지 않았고(사람이 실제 실행 여부를 수동 확인 후 merge), 플랫폼당 `expect()` 호출이 100만~138만 회에 달했다.

비용은 이 글에서 가장 정직한 부분이다. **May 3~14, 11일간 6,778커밋**(포트 브랜치의 merge 제외 커밋은 6,502개, 최종 landed diff는 +100만 줄 남짓). pre-merge에 **uncached input 59억 · output 6억 9천만 · cached input read 720억 토큰**을 썼고, **API 가격 기준 약 16만 5천 달러**다. 사람이 했다면 코드베이스 전체 context를 가진 엔지니어 3명이 약 1년 걸렸을 것으로 팀은 평가했다. 사용 모델은 **출시 전 Claude Fable 5**이며, Bun은 **2025년 12월 Anthropic에 인수**됐다는 disclosure가 붙어 있다.

### 결과물

- **버그 128개 수정**: 메모리 누수, crash, 잘못 색칠된 help text까지. Rust의 `Drop`이 scope 이탈 시 자동 호출되므로, `defer`를 call site마다 붙여야 했던 Zig의 누락·중복 cleanup footgun이 구조적으로 줄었다.
- **메모리 누수 평탄화**: 같은 60-module 프로젝트를 한 프로세스에서 2,000번 bundle하는 테스트에서 v1.3.14는 6,745MB까지 치솟았으나 v1.4.0은 609MB에서 수평을 유지했다.
- **바이너리 20% 축소**: Rust 전환 초기 변경만으로도 줄었고(Zig의 과한 `comptime`이 주원인), ICU unused data 제거와 identical code folding을 합쳐 Linux 88→70MB, Windows 94→76MB.
- **성능 2~4%대 향상**: `Bun.serve` 169.6k→177.7k req/s(+4.8%), `next build` 13.62→13.03s(+4.5%) 등. LLVM의 lifetime intrinsic과 cross-language LTO 덕이라고 설명한다.
- **19개 regression**(모두 수정): 대부분 "문법은 비슷한데 의미가 다른" 지점에서 나왔다 — `debug_assert!`가 release에서 통째로 제거돼 side effect가 사라진 케이스, `bytemuck::cast_slice`가 홀수 길이 slice에서 panic하는 케이스, Rust release가 bounds check를 유지해 포팅된 off-by-one이 out-of-bounds write 대신 panic으로 바뀐 케이스 등.

현재 Rust 코드의 약 4%가 `unsafe` 블록 안에 있고(약 13,000개 키워드), 그중 78%는 한 줄짜리로 대부분 C/C++ 라이브러리 호출이다. 팀은 JavaScriptCore·BoringSSL·SQLite 같은 C/C++ 의존성을 계속 쓰기 때문에 순수 Rust 프로젝트보다 `unsafe`가 항상 많을 것이라고 밝혔다. 이미 Prisma가 이 위에서 Prisma Compute 퍼블릭 베타를 냈고, Claude Code도 v2.1.181(6월 17일)부터 Rust 포트 Bun을 쓰며 Linux 시작이 10% 빨라졌다.

## 왜 중요한가

이건 "AI가 코드를 짠다"의 다음 단계, **AI가 대형 마이그레이션을 실행 주체로 해냈다**는 첫 본격 사례다. 그리고 그 성공을 떠받친 건 모델이 똑똑해서가 아니라 **검증 루프**였다. 구현 언어와 무관한 TypeScript 테스트 스위트, ASAN/Miri/LeakSanitizer/24-7 퍼징, 그리고 diff만 보고 "틀렸다고 가정하는" 적대적 리뷰어 2명 — LLM은 검증 가능한 보상이 있을 때 강하다는 명제의 대규모 실증이다. HN 토론에서도 "종합적인 테스트 하네스 설계가 진짜 일이 되고, 우리 역할은 코딩 에이전트 목동으로 바뀐다"는 관점이 반복해 나온다.

동시에, 순진하게 읽으면 곤란한 지점이 분명하다(아래는 원문 본문이 아니라 HN·Lobste.rs **토론에서 나온 의견**이다). ① 비용 비교가 미묘하다 — 16만 5천 달러는 "50명 × 11일 = 66만 달러"보다는 싸지만, 이 계산은 Anthropic 소유라 토큰 비용을 실질 0으로 볼 수도 있고, 반대로 출시 전 모델(Fable 5)이라 아무나 재현할 수 없다는 뜻이기도 하다. ② `unsafe` 블록이 "한 줄"이라는 건 안전 지표가 아니다 — 그 안에서 soundness가 깨지면 블록 밖 모든 코드가 영향을 받으며, 실제로 초기 병합에 unsoundness가 있어 Miri를 CI에 켜서 대응했다. ③ "Zig에서 벗어난 순진한 재작성만으로 개선됐다"는 해석도, 반대로 "재작성 자체가 주는 이점(같은 규모로 Zig→Zig를 했어도 개선됐을 것)"이라는 반론도 둘 다 제기됐다. 즉 **결과는 진짜지만, 전제가 특수하다**. "우리도 Rust로 다시 쓰자"의 근거로 이 사례를 그대로 끌어오는 건 과잉 일반화다.

## 어떻게 써먹나

Rust 재작성이 아니라 **방법론**이 이식 가능한 자산이다.

- **구현 언어와 분리된 테스트 스위트를 먼저 확보하라.** Bun이 통째 포팅을 감행할 수 있었던 유일한 이유는 검증 기준이 구현 언어에 매이지 않았기 때문이다. 대형 리팩터링·마이그레이션을 AI에 맡길 생각이라면, 착수 전에 "구현이 뭘로 바뀌든 살아남는" 동작 계약(behavioral contract)부터 만들어라. 이게 없으면 에이전트가 아무리 빨라도 방향을 검증할 수 없다.
- **적대적 리뷰를 구조로 강제하라.** 구현 에이전트와 리뷰 에이전트의 context를 분리하고, 리뷰어에게 "이 코드는 틀렸다"를 기본 가정으로 준다. "merge하고 싶은 편향"을 줄이는 이 분리는 사람 팀에서도 유효한 원리다. 컴파일은 통과하지만 의미가 틀린 버그를 잡는 데 특히 효과적이었다.
- **기계적 포팅 → 이후 점진적 정련**의 2단계로 쪼개라. "완벽한 idiomatic 코드를 한 번에"가 아니라 "동작 보존 우선, unsafe/추함은 나중에 줄인다"가 위험을 낮춘다. 증분 재작성이 오히려 임시 코드 부채를 키운다는 판단도 참고할 만하다.
- **삽질 방지 규칙을 워크플로우에 새겨라.** 병렬 에이전트의 `git` 충돌 금지, 느린 명령 금지, "문단 길이 주석이 필요하면 코드가 틀린 것"처럼, 관찰된 실패 패턴을 그때그때 규칙으로 고정하는 운영이 규모를 지탱했다.

한 줄 요약: **AI에게 대형 작업을 맡기는 능력은 모델이 아니라 검증 하네스에서 나온다.** 이건 이 블로그가 앞서 기록한 "이해 못 할 코드는 올리지 말고 안전장치를 구조로 강제하라"와 정확히 같은 결론이다.

## 출처

- GeekNews: https://news.hada.io/topic?id=31263
- 원문: "Bun을 Rust로 다시 작성하기" (bun.com 블로그)
