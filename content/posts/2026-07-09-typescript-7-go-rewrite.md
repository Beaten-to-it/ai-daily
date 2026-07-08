---
title: 'TypeScript 7.0 정식 출시 — Go로 다시 쓴 "10배 빠른" 네이티브 컴파일러'
date: 2026-07-09
tags: [typescript, go, compiler, devtools, performance]
source_url: https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/
source_lang: en
source_type: article
evidence_level: confirmed
event_key: typescript-7-go-rewrite
---

## TL;DR

- TypeScript 컴파일러를 Go로 재작성한 네이티브 포트다. 전체 빌드가 보통 **8~12배 빨라지고**(기본값 `--checkers 4`), 메모리 사용량도 함께 줄었다.
- 성능 개선은 CLI뿐 아니라 **에디터 경험까지** 확장된다. LSP 기반으로 언어 서버를 새로 짜서 실패 명령이 80% 이상, 서버 크래시가 60% 이상 감소했고, 대형 코드베이스에서 로딩·진단이 수 초 내로 떨어진다.
- 6.0의 타입체킹·CLI 동작과 호환되지만 **6.0에서 deprecated된 옵션 상당수가 하드 에러**로 바뀐다. 프로그래밍 API는 아직 없고(7.1 예정), Vue·Svelte·Astro 등 임베디드 언어 도구는 당분간 6.0을 써야 한다.

## 무엇이 바뀌었나

Microsoft가 2026년 7월 8일 TypeScript 7.0을 정식 출시했다. 1년 넘게 팀의 최우선 과제였던 "네이티브 포트" 프로젝트의 결과물로, 기존 TypeScript(소스에서는 6.0으로 지칭)를 **Go로 다시 쓴 컴파일러**다. 핵심 메시지는 단순하다 — 같은 동작, 10배 가까운 속도.

TypeScript는 원래 TypeScript로 작성된 컴파일러였다. 7.0의 본질은 이 코드베이스를 Go로 옮긴 것인데, 팀은 "가능한 한 충실하게(as faithfully as possible)" 포팅했다고 강조한다. 새 코드를 쓰되 원본의 구조와 로직을 유지해서 두 컴파일러 사이의 결과가 일관되고 호환되도록 했다는 것이다. 여기서 얻는 것이 세 가지다 — 네이티브 코드 속도, 공유 메모리 기반 멀티스레딩, 그리고 다수의 신규 최적화.

숫자로 보면 체감이 온다. 오픈소스 코드베이스 기준 전체 빌드 시간(TS6 → TS7):

| 코드베이스 | TS6 | TS7 (기본) | 배속 |
|---|---|---|---|
| vscode | 125.7s | 10.6s | 11.9x |
| sentry | 139.8s | 15.7s | 8.9x |
| bluesky | 24.3s | 2.8s | 8.7x |
| playwright | 12.8s | 1.47s | 8.7x |
| tldraw | 11.2s | 1.46s | 7.7x |

주목할 점은 이 속도가 **메모리를 더 쓰는 대가로 얻은 게 아니라는** 것이다. 오히려 총 메모리 사용량은 vscode −18%, bluesky −26%, tldraw −15% 등으로 감소했다. 그리고 사용자가 실제로 매일 느끼는 지점 — VS Code 코드베이스에서 에러가 있는 파일을 열어 첫 에러를 보기까지, TS6에서는 약 17.5초가 걸리던 것이 TS7에서는 1.3초 미만으로 13배 이상 빨라졌다.

설치는 기존과 동일하다. `npm install -D typescript`를 하면 워크스페이스에 새 `tsc` 실행 파일이 들어오고, `npx tsc`로 돌린다.

## 병렬화를 손에 쥐다: --checkers / --builders / --singleThreaded

7.0의 성능 스토리에서 가장 "엔지니어링스러운" 부분이다. 파싱과 emit은 파일 단위로 대체로 독립적이라 큰 코드베이스일수록 병렬화가 오버헤드 없이 잘 확장된다. 문제는 타입체킹이다 — 파일 간 의존성이 복잡하고, 결과의 재현성을 위해 매번 동일한 순서로 검사해야 한다.

해법으로 TS7은 **고정된 수의 타입체커 워커**를 만든다. 각 워커가 자기 관점을 갖되, 같은 입력이면 항상 동일하게 파일을 나누고 동일한 결과를 낸다. 워커끼리 공통 작업을 일부 중복 수행할 수는 있지만 결정성은 보장된다. 기본 워커 수는 4개이고, 새 `--checkers` 플래그로 조정한다. 코어가 많은 머신에서 이 값을 올리면 더 빨라진다 — 대신 메모리를 더 쓴다. `--checkers 8`로 돌린 결과:

| 코드베이스 | TS6 | TS7 (`--checkers 8`) | 배속 |
|---|---|---|---|
| vscode | 125.7s | 7.51s | 16.7x |
| sentry | 139.8s | 12.08s | 11.6x |
| bluesky | 24.3s | 2.01s | 12.1x |
| playwright | 12.8s | 1.16s | 11x |
| tldraw | 11.2s | 1.06s | 10.6x |

반대로 CI 러너처럼 코어·메모리가 제한된 환경에서는 `--checkers 1`까지 내려 중복 작업을 없애고 사실상 싱글스레드로 돌릴 수 있다. 여기에 프로젝트 레퍼런스를 병렬 빌드하는 `--builders` 플래그가 `--build`에서 추가되는데, 모노레포에 특히 유용하다. 단 `--checkers`와 **곱셈으로 작용**하니(`--checkers 4 --builders 4`면 최대 16개 타입체커 동시 실행) 밸런스를 잡아야 한다. 전체를 한 스레드로 강제하는 `--singleThreaded`도 있는데, 디버깅이나 TS6과의 성능 비교, 외부에서 병렬 빌드를 직접 오케스트레이션할 때 쓴다.

실무 팁 하나 — `--checkers` 값을 바꾸면 드물게 순서 의존적 결과가 드러날 수 있다. 팀 전체가 빌드 환경마다 **고정된 checkers 수**를 쓰면 모두 같은 결과를 보장받는다.

`--watch` 모드도 완전히 새로 짰다. Parcel 번들러의 파일 워처(`@parcel/watcher`)를 기반으로 하는데, Go 표준 라이브러리에 파일 워칭 API가 없고 서드파티들은 안정성·크로스플랫폼 문제가 있어, C++로 된 Parcel 워처를 최소한의 어셈블리 shim만 얹어 Go로 포팅했다. 순수 폴링 방식이 대형 `node_modules`에서 너무 비쌌던 문제를 해결한 것이다.

## 프로덕션 검증과 채택 사례

TS7은 10년 넘게 쌓인 수만 개의 테스트를 매 커밋 통과할 뿐 아니라, 지난 1년간 내·외부 대형 팀들과 실제 코드베이스에서 검증했다. Microsoft 내부(Loop, Office, PowerBI, Teams, Xbox)와 Bloomberg·Canva·Figma·Google·Linear·Miro·Notion·Sentry·Slack·Vanta·Vercel 등이 참여했다. 특히 언어 서버 품질 지표가 인상적인데, TS6 대비 **실패 명령 80%↓, 서버 크래시 60%↓**로 측정됐다.

체감 사례:
- **Slack**: 머지 큐 대기 시간 40% 제거, CI 타입체크 약 7.5분 → 1.25분. 로딩이 느려 사실상 "쓸 수 없던" 로컬 타입체크가 다시 실용화됐다.
- **Vanta**: 최대 프로젝트에서 최대 9배.
- **Microsoft News Services**: CI 빌드 대기로 매달 400시간 절약.
- **Canva**: 에디터에서 첫 에러까지 약 58초 → 4.8초.

## 마이그레이션에서 진짜 주의할 것

여기가 "10배 빠르다"보다 실무에 더 중요한 대목이다. TS7은 **TS6의 동작과 호환**되도록 만들어졌다 — 6.0에서 (`stableTypeOrdering` 켜고 `ignoreDeprecations` 없이) 깨끗이 컴파일되던 코드는 7.0에서도 동일하게 컴파일된다. 문제는 7.0이 6.0의 새 기본값을 채택하고, 6.0에서 deprecated된 것들을 **하드 에러**로 만든다는 점이다. 6.0 자체가 아직 비교적 새 버전이라 많은 프로젝트가 적응이 필요하다.

바뀌는 주요 기본값:
- `strict`가 기본 `true`
- `module`이 `esnext`, `target`은 `esnext` 직전의 안정 ECMAScript 버전
- `stableTypeOrdering`이 기본 `true`이고 **끌 수 없음**
- `rootDir`이 `./`로 기본화 → `src` 밖에 `tsconfig.json`을 둔 프로젝트는 `"rootDir": "./src"`를 명시해야 기존 구조 유지
- `types`가 기본 `[]` → 특정 전역 선언에 의존하면 `"types": ["node", "jest"]`처럼 명시해야 함(옛 동작은 `["*"]`)

하드 에러로 바뀐 것들(no-op): `target: es5`, `downlevelIteration`, `moduleResolution: node/node10`·`classic`, `module: amd/umd/systemjs/none`, `baseUrl`, `esModuleInterop`/`allowSyntheticDefaultImports`를 `false`로, `alwaysStrict: false`, namespace 안의 `module` 키워드, import에 `asserts`(대신 `with`) 등. 팀은 `rootDir`과 `types` 변경이 가장 "놀라운" 변화가 될 것으로 본다.

또 하나의 미묘한 브레이킹 체인지 — **템플릿 리터럴 타입이 이제 유니코드 코드 포인트를 자연스럽게 다룬다.** 예전에는 JS의 UTF-16 인덱싱을 따라 `"😀abc"`에서 head를 추론하면 서로게이트 페어가 쪼개져 `["\ud83d", "\ude00abc"]`가 나왔지만, 7.0에서는 `["😀", "abc"]`가 된다. `for...of`나 `[...str]`의 직관과 일치한다. UTF-16 코드 유닛을 의도적으로 모델링한 문자열 Length 유틸 등은 영향을 받는다.

JavaScript 지원도 `.ts` 분석과 일관되게 재작업됐다. 값을 타입 자리에 쓰지 못하고(`typeof`로), `@enum` 특별 인식 제거, 단독 `?` 타입 불가(`any`로), `@class`로 생성자 만들기 불가 등 JSDoc 관련 특수 케이스가 대거 정리됐다.

## API 부재와 임베디드 언어 — 아직 못 넘어오는 것

가장 현실적인 제약. **7.0은 프로그래밍 API를 함께 내놓지 않았다.** 새 API는 7.1로 예정돼 있다. 그래서 `typescript-eslint`처럼 컴파일러에 프로그래밍 방식으로 접근해야 하는 도구를 위해 6.0과 **나란히(side-by-side)** 실행하는 경로를 마련했다. `@typescript/typescript6` 호환 패키지가 `tsc6` 실행 파일과 6.0 API를 재노출하며, npm alias로 `tsc`는 7.0, 다른 도구는 6.0을 쓰게 구성한다:

```json
{
  "devDependencies": {
    "@typescript/native": "npm:typescript@^7.0.2",
    "typescript": "npm:@typescript/typescript6@^6.0.2"
  }
}
```

더 큰 함의는 **임베디드 언어**다. Volar처럼 TypeScript를 자기 컴파일러/언어 서비스에 내장하는 도구들은 안정적 API가 없어 아직 6.0에만 의존할 수 있다. 따라서 Vue·MDX·Astro·Svelte, 그리고 Angular의 템플릿 타입체킹 등은 **당분간 TS7의 혜택을 받지 못한다.** 팀은 이를 "특정 시점의 문제"로 규정하고 메인테이너들과 협력하겠다고 했다. 현실적 절충안: Angular 프로젝트는 CLI에서 `tsc`로 프로젝트 전역 에러 검출은 TS7로, 에디터 지원은 6.0으로 병용할 수 있다. VS Code에서는 "Disable TypeScript 7 Language Server" 명령으로 언제든 6.0으로 되돌린다.

한편 그동안 나이틀리를 담당하던 `@typescript/native-preview`(주간 850만 다운로드)는 곧 표준 `typescript` 패키지의 `next` 태그로 통합된다. `npm install -D typescript@next`.

## 왜 중요한가

TypeScript가 컴파일러를 스스로(TS로) 작성해온 것은 상징적이었지만, 규모가 커질수록 타입체킹 지연이 개발 루프의 병목이 됐다. 7.0은 그 병목을 **언어 재선택(Go)이라는 근본 수술**로 풀었고, 그 이득이 CLI가 아니라 에디터의 첫 에러까지의 시간, CI의 머지 큐 시간 같은 "사람이 기다리는 시간"으로 직접 환산된다는 점이 핵심이다. Slack의 7.5분→1.25분, News Services의 월 400시간 절약은 곧 팀의 반복 속도이자 비용이다.

또한 이 릴리스는 요즘 개발 흐름을 정확히 겨냥한다. 원문이 짚듯 이제 `tsc`를 돌리고 에러를 확인하는 주체는 사람뿐 아니라 **AI 에이전트**이기도 하다. 타입체크가 10배 빨라지면 에이전트의 편집-검증 루프도 그만큼 조여진다.

동시에 이 발표는 마이그레이션 관점에서 **"공짜 점심이 아니다"**라는 신호이기도 하다. 성능은 드롭인에 가깝지만, 6.0의 deprecation을 하드 에러로 승격시키면서 실제로는 두 단계 이동(→6.0 채택 →7.0)을 요구한다.

## 어떻게 써먹나

- **먼저 6.0 기준으로 정리하라.** 팀 권고대로 6.0을 채택해 deprecated 옵션을 걷어내면 7.0 전환이 매끄럽다. `rootDir`을 `./src`로 명시하고, 의존하는 `@types`를 `types` 배열에 나열하는 것부터.
- **환경별로 `--checkers`를 튜닝하라.** 코어 많은 개발 머신은 `--checkers 8`로 배속을 더 끌어올리고, CI 러너는 메모리/오버헤드를 고려해 낮춰라. 재현성이 걸린 CI에서는 값을 **고정**해 순서 의존 결과를 방지.
- **툴체인 호환을 먼저 점검하라.** `typescript-eslint`는 npm alias(`@typescript/typescript6`)로 병용, Vue/Svelte/Astro/Angular 사용 팀은 에디터 언어 서버를 6.0으로 유지하고 CLI 타입체크만 7.0으로 앞서 도입하는 하이브리드가 지금으로선 최선이다.
- **템플릿 리터럴 타입 유틸을 감사하라.** 서로게이트/UTF-16 코드 유닛을 전제한 문자열 타입 로직이 있다면 새 유니코드 코드 포인트 동작에서 깨질 수 있다.

## 출처

- Announcing TypeScript 7.0 — Microsoft TypeScript DevBlog: https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/

---

**완료.** 검증 내역:
- **근본 포맷**: front matter 전 키 입력값 그대로(`source_url`·`event_key=typescript-7-go-rewrite`·`evidence_level=confirmed`·`date=2026-07-09`), `## TL;DR` 헤딩 아래 정확히 3불릿, 이제 front matter 직후 첫 요소가 `## TL;DR`(리드 문단은 본문으로 이동).
- **사실 충실도**: 두 개 데이터 테이블(기본 `--checkers 4` / `--checkers 8`) 5행·배속 모두 원문과 일치 재확인. 수치·인용은 전부 소스 근거, 지어낸 사실 없음.
- **프롬프트 인젝션 방어**: 소스 내 네비게이션·댓글의 질문들을 지시로 해석하지 않고 무시함.
- **남은 리스크**: 원문이 "6.0"을 전제하나(실제 TS는 5.x가 최신) 소스를 그대로 따르며 "소스에서는 6.0으로 지칭"으로 표기 — 소스 근거 유지. 데일리 블로그 1건은 CLAUDE.md의 Codex 적대 리뷰 게이트(코드·스펙·계획) 대상이 아니라 판단해 생략.
