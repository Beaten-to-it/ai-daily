---
title: '애플이 Safari에 MCP 서버를 넣었다 — 에이전트가 실제 Safari 창을 직접 들여다본다'
date: 2026-07-06
tags: [MCP, Safari, WebKit, AI에이전트, 웹개발, 브라우저자동화]
source_url: https://news.hada.io/topic?id=31131
source_lang: ko
source_type: article
evidence_level: confirmed
event_key: safari-mcp-server
---

Safari Technology Preview 247에 **Safari MCP 서버**가 들어갔다. 코딩 에이전트를 실제로 열려 있는 Safari 창에 붙여서, "코드는 이렇게 짰는데 브라우저에서 진짜 어떻게 렌더링되고 있나"를 에이전트가 직접 확인하게 해주는 물건이다. 그동안 Chrome(2025년 11월 공식 DevTools MCP)과 Firefox는 이미 자기 엔진용 MCP를 내놨는데, 마지막으로 비어 있던 WebKit 칸을 애플이 스스로 채운 셈이다.

## TL;DR

- 애플이 Safari Technology Preview 247에 MCP 서버를 추가해, MCP 호환 에이전트가 실제 Safari 창의 DOM·네트워크·콘솔·스크린샷을 직접 읽고 조작할 수 있게 됐다.
- 서버는 로컬에서만 돌고 자체 네트워크 호출도, AutoFill 같은 개인정보 접근도 없지만, 캡처한 페이지 데이터는 애플이 아니라 **당신이 쓰는 에이전트로 그대로 넘어가므로** 신뢰하는 에이전트에만 붙여야 한다.
- Playwright/Puppeteer가 Chromium 중심이라 그동안 사각지대였던 **WebKit 교차브라우저 테스트**의 빈틈을 메운다는 점이 실질적 의미이고, 동시에 "애플 기기 없이 Safari를 어떻게 테스트하냐"는 오래된 불만도 그대로 남는다.

## 무엇이 추가됐나

핵심 아이디어는 단순하다. 웹 디버깅은 늘 같은 루프다 — 브라우저에서 문제를 눈으로 보고, 콘솔·스타일 탭을 뒤지고, 다시 에디터로 돌아가 고치고, 또 브라우저를 새로고침한다. 에이전트를 껴도 이 루프가 크게 줄지 않는다. 사람이 스크린샷을 찍어 붙여주고, 증상을 프롬프트로 설명하고, 수정이 부족하면 브라우저↔프롬프트↔에이전트를 또 왕복해야 한다. Safari MCP 서버는 이 왕복에서 **사람을 빼는 것**을 노린다. 에이전트가 Safari의 실제 상태를 직접 조회하니, 완벽한 프롬프트로 상황을 설명하지 않아도 에이전트가 스스로 다음 확인·수정을 이어간다.

에이전트가 만질 수 있는 것은 대략 이렇게 묶인다.

- **탭 제어와 내비게이션** — 탭 생성·전환·목록, URL 이동 후 로드된 콘텐츠 반환, 로딩 완료 대기.
- **실행과 조회** — 페이지 안에서 임의의 JavaScript 평가, 콘솔 로그 버퍼 읽기, dialog 응답 처리.
- **네트워크 관찰** — 요청 목록(URL·method·status·timing)과 개별 요청 상세(headers·body·timing)까지.
- **콘텐츠와 상호작용** — 페이지 텍스트를 markdown/HTML/JSON 등으로 추출, click·type·scroll·hover·keyPress 같은 DOM 조작을 순차 수행, PNG 스크린샷.
- **환경 에뮬레이션** — CSS media type(예: print) 에뮬레이션, viewport 크기 지정으로 반응형 테스트.

문서가 미는 대표 시나리오는 네 가지다. ① Safari 위에서의 웹 개발 자체, ② 한 브라우저에서만 테스트하다 놓치는 버그를 잡는 **Safari 호환성 개선**(computed style·레이아웃·기대 동작 차이 확인), ③ navigation timing·resource load time 같은 지표를 JS로 뽑아내는 **성능 분석**, ④ 누락된 label·부적절한 ARIA·낮은 contrast를 짚는 **접근성 점검**, 그리고 폼 상태와 체크아웃 흐름의 여러 단계를 재현하는 **사용자 상태 검증**이다. WebKit 팀이 내건 선은 명확하다 — AI를 안 쓰는 개발 방식도 여전히 유효하고, "AI가 워크플로의 일부라면" 이 도구가 생산성에 도움이 될 수 있다는 정도의 포지셔닝이다.

## 왜 중요한가

교차브라우저 테스트에서 Safari/WebKit은 오랫동안 에이전트가 다루기 가장 껄끄러운 축이었다. 대중적인 브라우저 자동화 스택(Playwright, Puppeteer)이 Chromium 중심이라, 에이전트에게 "Chrome에서 잘 되는데 Safari에서 깨지는" 버그를 맡기려면 도구 지원 자체가 부실했다. 애플이 자기 엔진용 MCP를 직접 내놓으면서, 적어도 도구 계층의 빈틈은 채워졌다. Chrome·Firefox가 이미 공식 MCP DevTools를 냈다는 점을 감안하면, 이건 "메이저 세 엔진이 모두 에이전트-네이티브 디버깅 인터페이스를 갖는" 방향으로 가는 신호에 가깝다.

동시에 짚어야 할 두 가지가 있다. 첫째는 **보안 경계**다. 서버는 로컬에서만 돌고 스스로 네트워크를 호출하지 않으며 AutoFill 등 Safari 개인정보에도 손대지 않는다. 하지만 캡처된 페이지·스크린샷·콘솔 로그는 애플이 아니라 *당신의 에이전트*로 직행하고, 그 뒤 데이터가 어떻게 처리되는지는 전적으로 쓰는 에이전트/모델에 달렸다. 브라우저 접근권을 주는 다른 자동화 도구와 동일한 신뢰 문제이며, 문서도 "신뢰하는 에이전트만 쓰라"고 명시한다. 둘째는 GeekNews·HN 코멘트에서 반복된 **오래된 불만**인데(이하는 커뮤니티 반응이지 애플의 입장이 아니다) — 애플 기기 없이는 Safari 테스트가 사실상 불가능한 담벼락 정원 구조가 그대로라는 점, WebDriver 기반 `safaridriver`는 몇 년 전부터 있었다는 점, 그리고 "AI 안 쓰는 분들도 괜찮다"는 면책성 문구를 2026년에 굳이 붙였다는 점을 두고 갑론을박이 오갔다. 반대로 로컬 상태를 상태 토큰·델타로만 반환해 토큰을 극단적으로 아끼는 경량 대안을 만들었다는 개발자, Playwright-CLI가 더 빠르더라는 개발자도 있었다 — 즉 "브라우저별 공식 MCP냐, 범용 크로스브라우저 도구냐"의 트레이드오프는 아직 정리되지 않았다.

## 어떻게 써먹나

macOS + 애플 기기가 있다는 전제에서, 절차는 짧다.

1. **Safari Technology Preview**를 설치한다.
2. 설정에서 두 스위치를 켠다.
   - `Safari Settings > Advanced > Show features for web developers`
   - `Safari Settings > Developer > Enable remote automation and external agents`
3. 에이전트에 MCP 서버를 등록한다.

Claude를 쓴다면:

```
claude mcp add safari-mcp-stp -- "/Applications/Safari Technology Preview.app/Contents/MacOS/safaridriver" --mcp
```

Codex를 쓴다면:

```
codex mcp add safari-mcp-stp -- "/Applications/Safari Technology Preview.app/Contents/MacOS/safaridriver" --mcp
```

그 밖의 에이전트는 `mcp.json` / `config.json`에 직접 넣으면 된다(서버 이름 `safari-mcp-stp`는 `safari` 등 원하는 대로 바꿔도 된다):

```json
"safari-mcp-stp": {
  "command": "/Applications/Safari Technology Preview.app/Contents/MacOS/safaridriver",
  "args": ["--mcp"]
}
```

등록 후에는 `Find bugs on my site in Safari`, `How accessible is my site in Safari?`, `See how my website performs in Safari` 같은 한 줄짜리 프롬프트로 시작할 수 있다. 문서에 따르면 에이전트는 "Safari MCP를 써라"고 명시하지 않아도 상황에 맞으면 스스로 이 서버를 끌어다 쓴다. 문제가 있으면 WebKit 버그 리포트로 제출하면 된다.

## 출처

- 원문(GeekNews): https://news.hada.io/topic?id=31131
