---
title: 'OpenAI 음성 모드가 ChatGPT 데스크톱 앱에 상륙 — 말로 에이전트를 부린다'
date: 2026-07-25
tags: [AI, OpenAI, ChatGPT, 음성, 에이전트, Codex]
source_url: https://techcrunch.com/2026/07/24/openais-new-voice-mode-makes-it-to-the-chatgpt-desktop-app/
source_lang: en
source_type: article
evidence_level: confirmed
event_key: openai-voice-desktop
---

OpenAI가 7월 24일(현지시간) ChatGPT 데스크톱 앱을 업데이트해 **ChatGPT Voice**를 추가했다. 이제 데스크톱 앱에 말을 걸어 AI 에이전트를 조종하고 컴퓨터에서 실제 작업을 수행하게 만들 수 있다.

## TL;DR
- OpenAI가 ChatGPT 데스크톱 앱에 음성 모드(ChatGPT Voice)를 넣어, 음성만으로 ChatGPT Work·Codex의 에이전트를 지시하고 컴퓨터 작업을 실행할 수 있게 했다.
- 이번 달 공개한 새 음성 모델군 ChatGPT-Live(트윗상 표기는 GPT-Live) 기반으로, 듣기·말하기·작업 조율을 동시에 처리한다. 오늘부터 전 세계에 순차 배포된다.
- 스마트폰 버전이 '대화 품질'에 초점을 뒀다면, 이번 데스크톱 업데이트는 여러 단계를 포함한 복잡한 명령을 받아 '행동'까지 한다는 게 핵심 차이다.

## 무슨 일이 있었나

OpenAI는 목요일 데스크톱 앱 업데이트로 ChatGPT Voice 지원을 추가했다고 밝혔다. 사용자는 앱에 말을 걸어 AI 에이전트를 통제하고 자기 컴퓨터에서 작업을 처리시킬 수 있다.

기술적 토대는 OpenAI가 이번 달 초 내놓은 새 음성 모델 계열 **ChatGPT-Live**다(OpenAI 공식 트윗에서는 이를 **GPT-Live**로 부른다). OpenAI 설명에 따르면 ChatGPT Voice는 **ChatGPT Work**와 **Codex** 양쪽에서 동작하고, '컴퓨터 사용(computer use)' 스킬을 끌어와 웹사이트와 앱을 직접 찾아볼 수도 있다. macOS에서는 **Appshots**를 통해 앱이 화면에 표시된 내용(대체 텍스트 포함)에 접근하도록 허용할 수 있다.

주목할 대목은 스마트폰 버전과의 성격 차이다. 처음 나온 스마트폰용 ChatGPT Voice는 더 매끄러운 대화, 개선된 끼어들기(interruption) 처리를 내세웠지만 **스마트폰에서 실제로 행동을 대신 하도록 설계되지는 않았다.** 반면 이번 데스크톱 업데이트는 더 유능하다. 여러 단계로 이뤄진 복잡한 명령을 받아치고, ChatGPT가 사용자 입력이 필요할 때 되물어 응답을 받는 식으로 작업을 이어간다.

OpenAI가 공개한 데모 영상에서는 한 개발자가 "새 스레드를 만들고, 풀 리퀘스트를 열고, 버그의 근본 원인을 찾아라"를 **하나의 명령**으로 지시하는 장면을 보여줬다. 또한 사용자는 iOS 앱에서 원격 접속(remote access)을 통해 Codex 안의 ChatGPT Voice를 쓸 수 있다고 회사는 덧붙였다. 배포는 오늘부터 전 세계로 순차 진행된다.

한편 경쟁사 Anthropic도 Claude의 음성 모드를 업데이트해, Opus·Sonnet·Haiku 모델을 끌어와 Gmail·캘린더·Slack·Notion·Canva 같은 앱에서 작업을 완료할 수 있게 했다.

## 왜 중요한가

음성 인터페이스가 '대화 상대'에서 '작업 실행기'로 넘어가는 전환점이다. 지금까지 음성 AI의 승부처는 얼마나 자연스럽게 말하고 끼어들기를 처리하느냐였는데, 이번 데스크톱 버전은 대놓고 **행동(action-taking)**을 전면에 세웠다. 데모의 "스레드 생성 → PR 생성 → 버그 원인 추적"을 한 문장으로 처리하는 장면은, 음성이 단순 받아쓰기가 아니라 **여러 에이전트를 오케스트레이션하는 지휘봉**으로 쓰인다는 신호다.

또 하나는 이게 개발자 워크플로에 직접 꽂힌다는 점이다. ChatGPT Work와 Codex를 음성으로 몰 수 있다는 건, IDE·터미널에서 손으로 치던 반복 조율 작업을 말로 대체할 여지가 생겼다는 뜻이다. macOS Appshots로 화면 컨텍스트(대체 텍스트 포함)를 읽어들이는 것도 "지금 내 화면에 대해" 지시하는 시나리오를 열어준다.

경쟁 구도 측면에서도, OpenAI의 데스크톱 음성 행동화와 Anthropic Claude 음성 모드의 앱 연동 강화가 같은 날 묶여 보도됐다는 건 우연이 아니다. **'말로 부리는 에이전트'가 차기 격전지**임을 두 진영이 동시에 확인해준 셈이다.

## 어떻게 써먹나

- **Codex/ChatGPT Work 조종을 음성으로**: 브랜치 만들고 PR 열고 버그 원인 추적 같은 다단계 작업을 한 번의 음성 명령으로 위임하는 흐름을 시험해볼 수 있다. 손을 키보드에서 떼고도 에이전트 여러 개를 동시에 굴리는 게 요지다.
- **macOS라면 Appshots 활용**: 앱이 화면 내용(대체 텍스트 포함)을 읽게 허용하면, "지금 보이는 이 에러에 대해" 식으로 화면 컨텍스트를 전제한 지시가 가능하다. 단 화면 접근 권한을 주는 것이므로 어디까지 열지 판단이 필요하다.
- **iOS 원격 접속으로 이동 중 Codex 지시**: iOS 앱에서 원격 접속을 통해 Codex 안 ChatGPT Voice를 쓸 수 있으니, 데스크톱에 걸어둔 작업을 밖에서 음성으로 이어붙이는 워크플로를 구상해볼 만하다.

## 출처

- [OpenAI's new voice mode makes it to the ChatGPT desktop app — TechCrunch (2026-07-24)](https://techcrunch.com/2026/07/24/openais-new-voice-mode-makes-it-to-the-chatgpt-desktop-app/)
