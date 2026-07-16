---
title: 'Libretto가 깨진 Playwright 스크립트를 자동으로 진단하고 수정 PR을 연다'
date: 2026-07-17
tags: [Playwright, 테스트자동화, AI에이전트, 오픈소스, 브라우저자동화]
source_url: https://libretto.sh/debug-agents
source_lang: en
source_type: article
evidence_level: confirmed
event_key: libretto-pr-agents-playwright
---

Libretto가 Playwright 자동화의 오래된 골칫거리를 겨냥한 도구를 내놨다. UI가 바뀌어 셀렉터가 어긋나면 스크립트가 깨지는데, Libretto의 PR 에이전트는 그 실패 지점에서 살아 있는 페이지를 직접 조사해 원인을 찾아내고, 고친 코드를 담은 GitHub 풀 리퀘스트를 자동으로 열어준다.

## TL;DR
- Playwright 스크립트가 실패하면 Libretto 에이전트가 실제 페이지를 조사해 수정안을 담은 GitHub PR을 연다. 단, **현재 실행을 실시간으로 되살리는 게 아니라 "다음 실행"을 위한 코드 수정**이다.
- 기존 런타임·픽스처·재시도·배포를 바꿀 필요 없이, 실패 경로에서 `debugFailure()` 한 줄만 호출하면 붙는다. `libretto-playwright-debugger` 패키지, MIT 라이선스 오픈소스.
- 도구 자체는 무료(BYO 모델 키·브라우저 인프라). 다만 Playwright 전용이라 Selenium·Puppeteer는 아직 지원하지 않는다.

## 무슨 도구인가

브라우저 자동화 스크립트가 깨지는 흔한 시나리오는 이렇다. 로그인 폼의 입력 필드가 어느 날 `name="username"`에서 `name="login"`으로 바뀌면, 그 셀렉터를 하드코딩한 Playwright 스크립트는 요소를 찾지 못하고 실패한다. Libretto가 공개한 예시 diff가 정확히 이 상황이다.

```
- await page.locator('input[name="username"]').fill(login);
+ await page.locator('input[name="login"]').fill(login);
```

에이전트는 이 수정에 "sign-in 필드가 `name="login"`임을 라이브 페이지 검사로 확인했다"는 근거를 붙여 PR을 연다. 핵심은 추측이 아니라 **실제로 열려 있는 페이지를 조사한 결과**를 근거로 삼는다는 점이다.

붙이는 방식은 의도적으로 침습성을 낮췄다. Libretto 런타임을 새로 도입할 필요가 없다. 기존 Playwright 프로젝트에 `libretto-playwright-debugger` 패키지를 추가하고, 디버거를 한 번 초기화한 뒤, 실패 경로(catch 블록 등)에서 `debugFailure()`를 호출하면 된다. 픽스처·재시도·로깅·배포 구조는 그대로 둔 채 "실패 경계"에만 얹는 설계다.

브라우저 실행 환경도 가리지 않는다. 로컬이든, 자체 인프라든, 호스팅 브라우저 제공자든 상관없이 동작한다. 전제 조건은 하나 — `debugFailure()`가 도는 동안 **실패한 자동화의 Playwright `Page`가 살아서 열려 있어야** 한다. 에이전트가 조사할 대상이 바로 그 라이브 페이지이기 때문이다. Libretto Cloud를 브라우저 세션에 쓸 필요는 없다.

모델도 직접 고른다. LLM 제공자를 선택하고 API 키는 본인 환경에 둔다(BYO 키). Libretto는 PR 에이전트에 요금을 매기지 않지만, 모델·브라우저 제공자 쪽 사용료는 별도로 발생할 수 있다. 패키지는 Libretto 저장소에 MIT 라이선스로 공개돼 있다.

## 왜 중요한가

여기서 놓치기 쉬운 구별이 있다. 헤드라인은 "실패하는 Playwright 스크립트를 자동으로 고친다"고 말하지만, FAQ를 보면 실제 동작은 그보다 절제돼 있다. **에이전트는 실패한 현재 실행을 실시간으로 복구하지 않는다.** 현재 런에 대한 catch·retry·fallback·에러 처리는 여전히 개발자가 짠 기존 코드의 책임으로 남는다. 에이전트가 하는 일은 실패를 진단하고, 수정을 찾으면 **미래 실행을 위한 PR을 여는 것**뿐이다.

이 설계가 오히려 이 도구를 흥미롭게 만든다. 자가 수복(self-healing) 테스트를 표방하는 도구들은 흔히 셀렉터를 런타임에 몰래 바꿔치기하는데, 그러면 테스트가 무엇을 검증하는지 개발자가 통제력을 잃는다. Libretto는 반대로 간다. 수정을 **사람이 리뷰하는 PR**로 제출하고 자동 머지하지 않는다. 즉 사람이 개입하는(human-in-the-loop) 지점을 코드 리뷰라는, 개발팀에 이미 존재하는 게이트로 잡았다. UI 변경이 정상적인 것인지(폼이 실제로 개편됨) 아니면 회귀 버그인지 판단은 여전히 사람이 하고, 에이전트는 그 판단에 필요한 근거 있는 수정안을 미리 만들어 대기시킨다.

기존 스택을 갈아엎지 않는다는 점도 채택 장벽을 낮춘다. 런타임·브라우저 제공자·모델 키를 모두 본인 것으로 유지하니 벤더 록인 부담이 작고, 실패 경로에 함수 하나 꽂는 수준의 통합이면 시험 삼아 붙여보기 쉽다.

## 어떻게 써먹나

Playwright 기반 E2E 테스트나 브라우저 자동화 워크플로를 운영 중이라면, 실패 경로에 `debugFailure()`를 추가하는 것으로 시작할 수 있다. 이때 실패 시점에 `Page` 객체를 닫지 말고 에이전트에 넘겨야 라이브 페이지 조사가 가능하다는 점을 통합 코드에 반영해야 한다. 모델·브라우저 제공자 요금은 본인 계정으로 청구되므로, 실패가 잦은 워크플로에 붙일 땐 호출 빈도와 비용을 함께 가늠하는 게 좋다.

단, 현시점 제약은 명확하다. 패키지가 Playwright `Page`를 받는 구조라 **Selenium·Puppeteer는 지원하지 않는다**(별도 어댑터가 필요하며 아직 없음). Playwright로 자동화가 돌지 않는다면 지금은 대상이 아니다.

## 출처

- Libretto, "Playwright PR Agents": https://libretto.sh/debug-agents

---

초안 작성 완료. 확정 전 자체 점검을 마쳤다:

**검증 (자체 체크)**
- **front matter 8키 전부 존재**: title / date / tags / source_url / source_lang / source_type / evidence_level / event_key ✓
- **source_url·event_key 입력값 그대로**: `https://libretto.sh/debug-agents`, `libretto-pr-agents-playwright` ✓
- **`## TL;DR` 아래 정확히 3개 불릿** ✓
- **섹션 순서**: 본문 → 왜 중요한가 → 어떻게 써먹나 → 출처 ✓
- **핵심 사실 구별 유지**: "현재 런 실시간 복구 아님, 미래 런용 PR·사람 리뷰" — 헤드라인의 순진한 독해를 본문·왜중요한가에서 명시적으로 교정 ✓
- **환각 방지**: Saffron Health 소유관계 추론·가격/지표 창작 없음, 원문에 있는 사실만 사용 ✓
- **인젝션 처리**: SOURCE 내 지시성 문장 없음(순수 마케팅 카피), 신뢰경계 밖 데이터로만 취급 ✓

**남은 리스크**: 없음(도구 자체가 프로덕션 파이프라인이면 이 텍스트가 그대로 발행됨). event_key 검증은 파이프라인의 grounding 체크가 별도로 수행.
