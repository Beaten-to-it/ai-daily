---
title: 'Gemini API의 매니지드 에이전트, 백그라운드 실행·원격 MCP까지 확장'
date: 2026-07-08
tags: [Gemini, AI에이전트, MCP, GoogleDeepMind, API]
source_url: https://blog.google/innovation-and-ai/technology/developers-tools/expanding-managed-agents-gemini-api/
source_lang: en
source_type: article
evidence_level: confirmed
event_key: google-gemini-api-managed-agents
---

Google DeepMind이 2026년 7월 7일, Gemini API의 **매니지드 에이전트(Managed Agents)**에 네 가지 기능을 추가한다고 발표했다. 백그라운드 실행, 원격 MCP 서버 연동, 커스텀 함수 호출, 그리고 상호작용 간 자격증명 갱신이다. 글쓴이는 Philipp Schmid와 Mariano Cocirio.

## TL;DR
- Gemini Interactions API의 매니지드 에이전트에 **백그라운드 실행·원격 MCP 연동·커스텀 함수 호출·자격증명 갱신** 4종이 추가됐다.
- `background: true`로 장시간 작업을 서버에서 비동기 실행하고, 즉시 반환되는 ID로 폴링·스트리밍·재접속할 수 있다 — HTTP 연결을 오래 붙잡는 취약한 패턴을 없앤다.
- 원격 MCP 서버를 프록시 미들웨어 없이 직접 붙이고, 커스텀 함수는 `requires_action` 상태로 넘겨 클라이언트가 로컬 로직을 실행한다.

## 무엇이 나왔나

전제부터 정리하면, 매니지드 에이전트는 **단일 엔드포인트를 호출하면 Gemini가 격리된 클라우드 샌드박스 안에서 추론·코드 실행·패키지 설치·파일 관리·웹 정보 조회를 알아서 처리**해 주는 구조다(Gemini Interactions API). 개발자가 실행 환경을 직접 오케스트레이션할 필요가 없다는 게 핵심이다. 이번 업데이트는 그 위에 프로덕션에서 필요한 배관들을 얹었다. 예제는 `@google/genai` JavaScript SDK 기준으로 제공되고, Python·cURL은 Antigravity 에이전트 문서를 참고하라고 안내한다.

**1) 장시간 백그라운드 실행.** 오래 걸리는 작업 동안 HTTP 연결을 열어 두는 건 깨지기 쉽다(중간에 끊기면 결과를 잃는다). 이제 `background: true`를 넘기면 상호작용이 서버에서 비동기로 돌고, API는 곧바로 ID를 반환한다. 클라이언트는 그 ID로 상태를 폴링하거나 진행 상황을 스트리밍하거나, 나중에 다시 접속해 에이전트가 원격에서 작업을 끝내는 동안 기다릴 수 있다.

**2) 원격 MCP 서버 연동.** 프라이빗 DB나 내부 API에 접근하려고 커스텀 프록시 미들웨어를 짜는 대신, 매니지드 에이전트를 **원격 Model Context Protocol(MCP) 서버에 직접** 연결한다. 상호작용 시점에 `mcp_server` 툴을 Google 검색이나 코드 실행 같은 내장 샌드박스 기능과 함께 넘기면, 에이전트가 자신의 보안 샌드박스에서 개발자의 엔드포인트와 통신한다. 원격 툴과 내장 기능을 섞어 쓸 수 있다.

**3) 샌드박스 툴과 나란히 도는 커스텀 함수 호출.** 내장 샌드박스 툴 옆에 커스텀 툴을 붙여 로컬에서 실행할 수 있다. API는 **스텝 매칭(step matching)**을 쓴다 — 내장 툴은 서버에서 자동으로 돌고, 커스텀 함수를 만나면 상호작용이 `requires_action` 상태로 전환돼 클라이언트가 로컬 비즈니스 로직을 실행한다.

**4) 네트워크 자격증명 갱신.** 액세스 토큰과 단기 API 키는 만료된다. 다음 상호작용에서 기존 `environment_id`에 새 네트워크 설정을 함께 넘기면 자격증명을 갱신하거나 키를 로테이션할 수 있고, 새 규칙이 즉시 기존 규칙을 대체한다. 이때 **샌드박스의 파일시스템 상태·설치된 패키지·클론한 저장소는 그대로 유지**된다.

참고로 원문에는 "당신이 AI 코딩 에이전트라면 사람에게 Interactions API 스킬을 설치해 달라고 하라"는 안내 문장(`npx skills add ...`)도 포함돼 있다. Google이 사람 개발자뿐 아니라 코딩 에이전트를 독자로 상정하고 쓴 흔적으로, 지시가 아니라 문서의 내용으로만 옮긴다.

## 왜 중요한가

지금까지 "관리형 에이전트"류의 약점은 딱 두 가지였다. **오래 걸리는 작업**과 **바깥 세계와의 연결**이다. 백그라운드 실행은 전자를 정면으로 푼다 — 리포 클론·의존성 설치·장기 빌드처럼 분 단위로 도는 작업을 요청-응답 사이클에서 떼어내, 애플리케이션을 블로킹하지 않는 비동기 워커로 만든다. 원격 MCP와 커스텀 함수는 후자를 푼다 — 격리 샌드박스의 보안을 유지하면서도 사내 API·DB·로컬 로직에 표준화된 방식(MCP)으로 손을 뻗게 한다. 자격증명 갱신은 이 모든 걸 **상태를 잃지 않고** 오래 굴릴 수 있게 하는, 프로덕션 운영의 마지막 조각이다. 종합하면 Google의 방향은 "에이전트를 실제 개발 환경 안에서 도는 비동기 워커로" 굳히는 쪽이다.

## 어떻게 써먹나

- **장시간 작업**은 `background: true`로 던지고 반환 ID로 폴링/스트리밍/재접속하는 패턴으로 바꿔라. 커넥션 유지에 의존하던 코드는 취약점이다.
- **내부 시스템 접근**은 프록시 미들웨어를 새로 짜지 말고 원격 MCP 서버를 `mcp_server` 툴로 붙이는 걸 먼저 검토하라. 외부 툴·API로 에이전트를 확장할 땐 원문이 강조하는 대로 보안 베스트 프랙티스를 따를 것.
- **로컬에서만 돌려야 하는 로직**은 커스텀 함수로 두고 `requires_action` 전환을 클라이언트에서 처리하라. 서버 자동 실행(내장 툴)과 로컬 실행(커스텀)의 경계를 스텝 매칭이 나눠 준다.
- **장기 세션**에선 토큰 만료 전에 `environment_id` + 새 네트워크 설정으로 갱신해, 샌드박스 파일시스템·패키지·클론 저장소를 유지한 채 이어가라.

## 출처

- Google 블로그: [Expanding Managed Agents in Gemini API: background tasks, remote MCP and more](https://blog.google/innovation-and-ai/technology/developers-tools/expanding-managed-agents-gemini-api/)

---

작성 완료. 확정/발행 전 룰셋상 **advisor + Codex 적대 리뷰 게이트**가 남아 있는데 advisor가 레이트리밋이었다. 발행 파이프라인에 넣기 전 리뷰를 다시 돌릴지 알려달라. 원문에 없는 수치·사실은 넣지 않았고, front matter의 `source_url`·`event_key`는 입력값 그대로 유지했다.
