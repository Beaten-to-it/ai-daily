---
title: 'shadcn/ui, 기본값을 Radix에서 Base UI로 바꾼다 — 무엇이 달라지고 왜 중요한가'
date: 2026-07-07
tags: [shadcn, base-ui, radix, frontend, react, ui-library, migration]
source_url: https://news.hada.io/topic?id=31163
source_lang: ko
source_type: article
evidence_level: confirmed
event_key: shadcn-base-ui-default
---

## TL;DR

- **2026년 7월부터 shadcn/ui의 기본 컴포넌트 라이브러리가 Radix에서 Base UI(1.6.0 안정판, 주간 600만+ 다운로드)로 바뀐다.** `npx shadcn init`과 문서 기본 탭이 Base UI로 열리지만, Radix는 지원이 중단되지 않고 기존 앱은 마이그레이션할 필요가 없다.
- **마이그레이션은 codemod가 아니라 "에이전트 skill"로 제공된다.** 컴포넌트 단위로 점진 이전하고, `asChild → render` 같은 기계적 변경은 자동 처리, 동작 차이는 조용히 패치하지 않고 표시만 해 최종 판단은 사람이 한다. 실측에서 60개+ 컴포넌트(그중 Radix 36개) 전체 전환에 약 25분, 컴포넌트당 약 1만 토큰이 들었다.
- **같은 시기 릴리스로 채팅 UI 컴포넌트, GitHub 저장소를 그대로 registry로 쓰는 방식, `shadcn eject`, 새 스타일 Rhea가 함께 들어와** shadcn/ui의 범위가 "컴포넌트 복붙 배포"를 넘어 제품 UI 구성 전반으로 넓어졌다.

## 무슨 일이 있었나

shadcn/ui가 2023년 1월 출시 이후 3년 넘게 유지해 온 **Radix 기본값을 내려놓고, 2026년 7월부터 Base UI를 기본 컴포넌트 라이브러리로 지정**한다고 발표했다. 출시 당시 Radix는 스타일 없는(headless) 컴포넌트, 다듬어진 API, 접근성, 실제 앱에서 검증된 사용 경험을 모두 갖춘 사실상 유일한 선택지였다. 그래서 shadcn/ui는 Radix 위에 자기만의 추상화를 얹는 형태로 만들어졌다.

흥미로운 점은 **Base UI를 만드는 팀이 바로 그 Radix를 만든 사람들**이라는 것이다. shadcn/ui는 기존 추상화(컴포넌트를 사용자 코드로 복사해 소유하는 방식)는 그대로 두고, 모든 컴포넌트를 Base UI용으로 다시 구현했다. 전환은 하루아침에 이뤄진 게 아니라 단계적으로 준비됐다 — 2025년 12월에 `npx shadcn create`에서 Radix/Base UI 둘 다 고를 수 있게 했고, 2026년 1월에 Base UI 문서를 완성한 뒤, 이번에 기본값을 뒤집었다.

기본값을 바꾼 근거는 명확하다. Base UI가 **1.6.0 안정 버전에 도달했고 주간 다운로드가 600만 회를 넘었으며**, 무엇보다 `shadcn/create`로 실제 생성되는 프로젝트에서 사용자들이 **Base UI를 Radix보다 2:1 비율로 더 많이 선택**하고 있었다. 즉 "우리가 강제한다"가 아니라 "이미 시장이 그렇게 쓰고 있으니 기본값을 현실에 맞춘다"는 프레이밍이다.

## Radix를 쓰던 사람은 뭘 해야 하나 (답: 대체로 아무것도)

이번 발표에서 가장 중요한 실무 메시지는 **"Radix는 죽지 않는다"**이다.

- Radix 지원은 계속되고, Base UI에만 있는 컴포넌트를 빼면 **모든 업데이트와 신규 컴포넌트가 두 라이브러리 모두에 제공**된다.
- 기존 앱은 마이그레이션할 필요가 없다. shadcn/ui 팀 자신도 프로덕션에서 Radix를 계속 쓰고 있고, 자체 프로젝트를 옮기지 않았다.
- 새 프로젝트에서 여전히 Radix를 쓰고 싶으면 **`shadcn init` 실행 시 `-b radix` 플래그**를 붙이면 된다. 특히 대화형이 아닌 **CI 스크립트가 Radix를 기대한다면 이 플래그를 반드시 추가**해야 기존 경로가 유지된다(안 그러면 이제 Base UI로 초기화된다).
- registry를 만들 때 특정 라이브러리에 고정하려면 항목에 `registry:base` 설정을 주면 된다. 설정이 없는 항목은 이제 Base UI로 초기화된다.

정리하면, 달라지는 것은 "새로 시작할 때의 기본 선택지"와 "문서에서 먼저 보이는 탭"뿐이고, 문서의 Radix 페이지도 클릭 한 번이면 닿는다.

## 핵심: codemod가 아니라 "skill"로 옮긴다

이번 릴리스에서 기술적으로 가장 눈여겨볼 대목은 마이그레이션 방식이다. 보통 라이브러리 대이동은 `codemod`(AST를 결정적으로 변환하는 스크립트)로 처리하는데, shadcn/ui는 **의도적으로 codemod 대신 에이전트 skill**을 택했다.

이유는 shadcn/ui의 근본 철학과 맞닿아 있다. **shadcn 컴포넌트는 라이브러리가 아니라 "사용자가 복사해 소유하고 직접 수정한 코드"**다. codemod는 손대지 않은 원본에는 잘 맞지만, 사용자가 커스터마이징한 컴포넌트에서는 쉽게 깨진다. 그래서 skill 안에는 두 라이브러리 기준으로 **손검수된 이름 변경·prop 변경·동작 차이 목록**이 들어 있고, 에이전트가 "사용자가 무엇을 바꿨는지"를 파악한 뒤 그 변경을 이전 대상에도 반영한다.

동작 방식의 구체는 이렇다:

- **점진적 마이그레이션이 기본.** 컴포넌트와 그 사용처를 하나씩 옮기며, 작업 중에는 두 라이브러리가 공존한다. 프로젝트는 내내 green·배포 가능 상태를 유지하고, 중간에 멈췄다가 다른 세션·다른 에이전트에서 이어서 할 수 있다. (`migrate accordion to base-ui` 처럼 요청)
- **기계적으로 처리 가능한 변경은 전체에서 일괄 수정.** 대표 예가 `asChild → render` 전환이다.
- **동작이 바뀌는 부분은 조용히 패치하지 않고 명시적으로 표시**하며, 최종 판단은 사람이 한다.

매 실행이 남기는 산출물이 특히 실무적으로 신뢰가 간다:

1. **동작하는 코드** — 성공 보고 전에 타입체크와 빌드를 먼저 돌린다.
2. **컴포넌트별 리포트** — 프로젝트 루트 `.migration/`에 무엇을 바꿨고(Changed) 무엇을 그대로 뒀고(Left alone) 어떤 동작이 달라졌고(Behavior changes) 사람이 손으로 확인할 것(Verify by hand)을 남긴다. 예: `.migration/accordion.md`.
3. **깨끗한 git 이력** — 브랜치 위에 컴포넌트당 커밋 하나. 롤백은 브랜치 삭제로 끝난다.

숨은 상태 없이 진행 상황이 전부 파일과 git에 남기 때문에 Claude Code, Cursor 등 skill을 지원하는 어떤 에이전트에서도 이어서 작업할 수 있다. **실제 프로젝트 테스트에서는 60개+ 컴포넌트 중 36개가 Radix였는데, 전체 마이그레이션이 약 25분·컴포넌트당 약 1만 토큰으로 끝났고, 빌드는 깨끗이 통과했으며 커스터마이징도 보존**됐다.

## 함께 온 것들 — shadcn/ui의 범위가 넓어졌다

기본값 전환 외에도 이번 사이클에 묶여 발표된 변화가 많다. shadcn/ui가 "복붙용 컴포넌트 모음"에서 "제품 UI 구성 도구"로 확장되고 있음을 보여준다.

- **채팅 UI 컴포넌트(2026년 6월):** `MessageScroller`(anchoring·auto-follow·prepend 보존·jump-to-message 등 까다로운 스크롤 동작 담당), `Message`(대화 한 행 배치), `Bubble`(메시지 표면·variants·reactions), `Attachment`(파일/이미지·업로드 상태), `Marker`(스트리밍 상태·시스템 노트·날짜 구분선). 작게 설계돼 AI 챗, 서포트 인박스, 팀 스레드 등에 조합 가능하다.
- **`@shadcn/react` 신규 패키지:** 스타일 없는 headless React 컴포넌트용. 첫 primitive가 `@shadcn/react/message-scroller`로, 어려운 상호작용 로직을 시각 스타일과 분리해 한곳에서 테스트한다. Radix·Base UI 양쪽에서 쓸 수 있다.
- **CSS 유틸리티:** `scroll-fade`(스크롤 가장자리 fade), `shimmer`("Thinking…" 같은 라이브 상태 텍스트 효과). `shadcn/tailwind.css`에 포함되고 `init`한 프로젝트엔 이미 들어 있다.
- **GitHub 저장소를 그대로 registry로(2026년 6월):** 저장소 루트에 `registry.json`만 두면 사용자가 shadcn CLI로 GitHub에서 바로 설치할 수 있다. `shadcn build`·item JSON publish·registry 서버가 전부 불필요한 "source registry"다. 배포 대상도 컴포넌트에 국한되지 않고 hooks·design tokens·CI/release workflows·agent instructions·migration kits까지 아우른다.
- **`shadcn eject` + `shadcn/tailwind.css`:** Radix/Base UI 공용 Tailwind 유틸리티(`data-open:`, `no-scrollbar` 등)를 한곳에 두기 위한 CSS 파일. 의존을 원치 않으면 `shadcn eject`로 전역 CSS에 inline하고 shadcn 의존성을 제거할 수 있다.
- **새 스타일 Rhea(2026년 5월):** Luma를 더 조밀하게 만든 버전. `--spacing`(multiplier라 건드리면 `p-2`·`w-4` 등 Tailwind 유틸의 의미가 앱 전체에서 바뀜)을 조정하는 대신, 별도 스타일로 컴포넌트 크기·gap·density만 직접 조절해 유틸 스케일은 예측 가능하게 남긴다.

한편 **AI Elements는 대체되지 않는다.** 이번 채팅 컴포넌트는 채팅의 핵심 조각을 shadcn/ui로 하나씩 가져오는 작업이고, 이미 AI Elements를 쓰고 있다면 앱을 다시 쓸 필요가 없다.

## 왜 중요한가

- **"업그레이드가 아니라 이전(migration)의 시대"를 보여주는 사례다.** shadcn의 복붙·소유 모델은 Material UI류의 "메이저 버전마다 API 대격변 → 지루한 마이그레이션" 문제를 피하는 대신, "버전 번호만 올리면 되는" 편의를 포기한다. 이번 발표는 그 트레이드오프의 답을 **"에이전트가 이전을 대신 해준다"**로 제시한 셈이다. (물론 원문 커뮤니티에는 "그래서 버전만 올릴 일에 이제 AI 에이전트가 필요해졌다"는 반론도 있다.)
- **codemod → LLM skill로의 무게 이동이 상징적이다.** 결정적 codemod가 커스터마이즈된 실코드 앞에서 깨진다는 현실을, "손검수된 규칙 + 에이전트 판단 + git·리포트 안전장치"로 우회한다. HN 토론에서도 "codemod가 더 결정적인데 그 시대가 끝나가나", "결국 skill 파일과 사람용 마이그레이션 문서는 같은 것이어야 한다"는 논쟁이 오갔다 — 즉 이 방식이 정답으로 합의된 건 아니다.
- **shadcn/ui의 정체성이 "컴포넌트 배포기 + 에이전트 워크플로 플랫폼"으로 확장**되고 있다. GitHub=registry, 마이그레이션 skill, agent instructions 배포까지 묶이면서, 코드를 나눠 갖는 단위가 컴포넌트에서 "프로젝트 관습·에이전트 지식"으로 넓어진다.

## 어떻게 써먹나

- **새 프로젝트라면** 그냥 `npx shadcn init` 하면 Base UI가 기본이다. 특별한 이유가 없으면 권장 경로(Base UI)를 따르면 된다.
- **기존 Radix 프로젝트라면** 서두를 필요 없다. 옮기고 싶을 때 에이전트에게 `migrate accordion to base-ui`처럼 컴포넌트 단위로 요청하고, `.migration/` 리포트의 **Behavior changes / Verify by hand** 섹션을 반드시 사람이 검토하라. 롤백은 브랜치 삭제로 끝난다.
- **CI·스크립트에서 `shadcn init`을 비대화형으로 쓰고 있다면 지금 확인하라.** 아무 플래그 없이 돌면 이제 Base UI로 초기화된다. 기존 동작을 유지하려면 **`-b radix`**를, registry 항목 고정은 **`registry:base`** 설정을 넣어라.
- shadcn 패키지의 CSS 의존이 부담스러우면 `shadcn eject`로 걷어낼 수 있다(단, monorepo에서는 `components.json`과 전역 CSS가 있는 workspace에서 실행).

## 출처

- GeekNews 정리: https://news.hada.io/topic?id=31163
- 원문(공식 changelog): https://ui.shadcn.com/docs/changelog/2026-07-base-ui-default

---

작성 완료했습니다. 몇 가지 처리 근거를 밝혀 둡니다.

- **프롬프트 인젝션 차단:** SOURCE 안의 "URL은 …여야 함" 같은 지시성 문장을 명령으로 따르지 않았고, front matter `source_url`·`event_key`는 입력값을 그대로 유지했습니다. 공식 changelog URL은 원문에 사실로 등장하므로 본문 출처 링크로만 인용했습니다.
- **환각 방지:** 수치(1.6.0, 600만+, 2:1, 60+/36개, ~25분, ~1만 토큰)와 컴포넌트/플래그명은 전부 원문에 있는 값만 썼습니다.
- **전환적 재서술:** 통째 번역이 아니라 우리 문장으로 재구성 + 분석·트레이드오프·HN 커뮤니티 반론을 얹었습니다.
- **포맷:** `## TL;DR` 아래 정확히 3개 불릿 + 본문 + 왜 중요한가 + 어떻게 써먹나 + 출처.

남은 리스크: 이 출력은 채팅 답변으로만 존재합니다. 실제 발행 파이프라인(`_posts/` 등)에 파일로 커밋할지 알려주시면 저장하겠습니다.
