---
title: '전직 CEO·CTO들이 OpenAI·Anthropic에 ''기술 실무자''로 앉았다 — YC 창업자 105명 추적'
date: 2026-07-18
tags: [YC, OpenAI, Anthropic, 창업, 커리어, AI]
source_url: https://news.hada.io/topic?id=31527
source_lang: ko
source_type: article
evidence_level: confirmed
event_key: yc-founders-at-openai-anthropic
---

## TL;DR

- 한 추적 사이트(joinedanthropic.com)가 인수·폐업 이후 경로를 좇아 **YC 창업자 최소 105명**이 OpenAI 또는 Anthropic에서 일했다고 집계했다(2026-07-14 기준, 공개 표엔 20명 노출).
- 진짜 눈에 띄는 건 숫자가 아니라 **직급의 방향**이다 — 과거 CEO·CTO였던 이들의 현재 최다 역할은 **Member of Technical Staff(MoTS), 63명·60%**. 리더에서 개별 기여자(IC)로 내려앉았다.
- 그러나 이 105명은 **YC 창업자 전체(대략 1만~1.3만 명)의 약 1%**이고, "OpenAI·Anthropic에 간 사람"만 골라 뽑은 **선택 편향** 표본이라 "YC가 이 회사들을 채운다"는 식의 결론은 데이터가 뒷받침하지 못한다.

## 무슨 데이터인가

`joinedanthropic.com`이라는 사이트가 YC 창업자들이 자기 스타트업을 인수당하거나 접은 뒤 어디로 갔는지를 추적해, 그중 OpenAI·Anthropic으로 흘러간 사람을 모았다. 2026년 7월 14일 기준 **105개의 고유 창업자 경로**를 집계했고, 공개 표에는 이 가운데 20명만 이름이 걸려 있다.

직무 분포는 이렇게 나뉜다(합계 105명):

- Member of Technical Staff: **63명 · 60%**
- 기타/비공개: 11명 · 10%
- 연구·안전: 10명 · 10%
- 시장 진출·파트너십: 8명 · 8%
- 리더십: 7명 · 7%
- 데이터·제품·디자인: 6명 · 6%

핵심은 첫 줄이다. 한때 자기 회사의 CEO·CTO였던 사람들이 지금은 대부분 리더 직함이 아니라 **기술 실무직(MoTS)** 에 앉아 있다. 사이트도, 원문을 나른 Hacker News 토론도 여기서 같은 지점을 짚는다 — "대형 조직에서 핵심 리더였던 사람들이 어떻게 이렇게 많이 개별 기여자로 옮겨갔는가"가 이 데이터에서 실제로 흥미로운 유일한 각도라는 것.

## 이름이 걸린 사례

표에 노출된 20명 중 몇을 옮기면:

**OpenAI 쪽** — Sam Altman(Loopt S05 창업 → OpenAI CEO), Emmett Shear(Twitch/Justin.tv W07 → 2023년 한 주말 OpenAI를 이끌었고 현재는 전 구성원), Michael Petrov(Couple W12 → GPT-3 API·응용 AI 기술 주도), Alex Karpenko(Midnox W12 → Research Engineer, o1·GPT-4V 핵심 기여), Christopher Berner(Carsabi W12 → Distinguished Engineer, 로보틱스·차세대 소비자 하드웨어), Sridatta Thatipamala(Flotype W11 → 검색 평가·RAG·에이전트 AI).

**Anthropic 쪽** — Tom Brown(Grouper W12 → 공동 창업자 겸 Chief Compute Officer), Tom Blomfield(GoCardless S11·Monzo Bank → Tom Brown의 컴퓨트 팀), Igor Kofman(HackPad W12 → Claude Code 기술 리드·MoTS), Chris Lloyd(Minefold W12 → Claude Code의 TUI 렌더링), Brian Krausz(GazeHawk S10 → Claude API·SDK·플랫폼 제품 엔지니어).

즉 GPT-3 API·o1·GPT-4V·Claude Code·Claude API/SDK·검색 평가/RAG 같은 실제 핵심 제품 라인에 이 창업자들이 손을 대고 있다. 데이터가 확인해 주는 건 딱 여기까지다.

## 숫자를 곧이곧대로 믿지 마라 (우리 분석)

원문 아래 Hacker News 토론이 스스로 이 통계를 해체한다. 그 논지를 그대로 옮기면:

- **표본이 극단적으로 작다.** YC 디렉터리 기준 창업자는 대략 1만~1.3만 명, 최근엔 기수당 약 150명씩 연 4회 뽑는다. 105명은 전체의 **약 1%**이고, 그중 약 1%(Altman의 OpenAI 창업 하나)가 상징성을 다 가져간다.
- **선택 편향이 설계에 박혀 있다.** 한 댓글이 정확히 짚었다 — `SELECT * FROM yc_founders WHERE employer IN ('OpenAI','Anthropic')`. 목적지를 먼저 고정하고 거기 간 사람만 세면, "YC 창업자가 이 회사들로 몰린다"가 아니라 "이 회사들에 YC 출신이 100명 있다"만 말할 수 있다. Google·Facebook에 간 YC 창업자가 더 많을 수도 있는데 비교군이 없다.
- **배치 분포는 이중 집계를 품는다.** 2024년 14명, 2020년 13명, 2012년 11명이 두드러지지만, YC 스타트업을 두 번 창업한 사람은 두 배치 연도에 모두 잡힌다. 그래서 배치별 합계는 고유 창업자 수와 직접 일치하지 않는다.

그래서 이 자료는 "YC가 프런티어 랩을 채운다"는 헤드라인용 서사로 읽으면 과장이다. 대신 두 가지 작은 사실만 남는다: (1) Altman이 YC 대표였으니 면접 밖에서 검증된 YC 인재를 데려오는 건 자연스럽고, (2) 리더였던 사람들이 IC로 내려앉을 만큼 이 두 회사가 지금 인재를 빨아들이고 있다.

## 왜 중요한가

숫자 자체보다, **커리어 계층의 재정렬** 신호라서 중요하다. "창업 → 실패/인수 → 프런티어 랩의 기술 실무직"이 하나의 실제 경로로 굳어지고 있다. 자기 회사에서 CEO였던 사람이 MoTS 직함을 기꺼이 받는다는 건, 지금 시장이 '직함'보다 '어떤 모델·어떤 코드에 손을 대느냐'를 더 값지게 친다는 뜻이다. 동시에 이 데이터는 좋은 반례 교보재이기도 하다 — 목적지를 고정한 채 표본을 뽑으면 1%짜리 사실도 트렌드처럼 보인다는, 데이터 읽는 사람이라면 늘 경계해야 할 함정을 그대로 보여준다.

## 어떻게 써먹나

- **창업자·구직자라면:** "실패한 스타트업 → 프런티어 랩 IC"가 실재하는 경로임을 참고하되, 원문 댓글의 냉정한 반론도 같이 새겨라 — 취업이 목표라면 창업은 가장 효율적인 길이 아니고, 시드를 넘지 못하면 이후 구직은 인맥에 크게 의존하게 된다는 지적이 함께 달렸다.
- **채용·전략 담당이라면:** 상대의 과거 '직함'이 아니라 지금 어떤 시스템을 만지는지를 본다. 리더 출신이 IC로 오는 흐름을 어떻게 받아들일지(직급·보상·기대치)를 미리 설계해 둘 만하다.
- **데이터를 다룬다면:** 이 사이트를 "선택 편향 + 이중 집계 + 비교군 부재"의 살아있는 사례로 북마크해 두라.

## 출처

- GeekNews: https://news.hada.io/topic?id=31527
