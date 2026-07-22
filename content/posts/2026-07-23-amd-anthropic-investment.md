---
title: 'AMD, 앤트로픽에 최대 50억 달러 투자 — MI450 2기가와트 배치로 컴퓨트 확보전 참전'
date: 2026-07-23
tags: [AMD, Anthropic, AI인프라, GPU, Claude]
source_url: https://www.theverge.com/ai-artificial-intelligence/969285/amd-anthropic-ai-infrastructure-deal
source_lang: en
source_type: article
evidence_level: confirmed
event_key: amd-anthropic-investment
---

## TL;DR

- AMD가 앤트로픽에 **최대 50억 달러**를 투자하고, 앤트로픽은 그 대가로 AMD의 Instinct MI450 GPU를 **최대 2기가와트** 규모로 배치한다(첫 1GW는 2027년 상반기).
- 단순 투자가 아니라 **하드웨어 조달 + 다년 엔지니어링 협업**이 묶인 딜이다 — AMD는 사내 소프트웨어·엔지니어링·제품 개발 전반에 Claude를 쓴다.
- 앤트로픽의 컴퓨트 소싱 다변화(SpaceX·TeraWulf·Google·Broadcom·Amazon에 이어 AMD)가 한층 뚜렷해졌다 — 엔비디아 단일 의존을 피하려는 움직임.

## 무슨 일이 있었나

7월 22일(수) 발표에 따르면, AMD가 앤트로픽에 최대 50억 달러를 투자하기로 했다. 핵심은 돈만 오가는 지분 투자가 아니라 컴퓨팅 파워 확장이 조건으로 엮여 있다는 점이다. 이번 파트너십으로 앤트로픽은 AMD의 신형 **Helios 랙 스케일 시스템**을 활용해 **Instinct MI450 AI GPU를 최대 2기가와트**까지 배치한다. The Wall Street Journal이 먼저 보도한 내용이라고 The Verge는 전한다.

배치 일정은 단계적이다. 두 회사는 **첫 1기가와트를 2027년 상반기에** 올린다는 계획이며, 이는 앤트로픽이 최근 맺은 데이터센터 계약들(SpaceX, TeraWulf) 위에 쌓아 올리는 그림이다. 앤트로픽은 이미 Google, Broadcom, Amazon과도 AI 인프라 계약을 체결한 상태이고, 원문은 Meta와도 합의에 이를 수 있다는 **소문(rumor)**이 있다고 언급한다 — 확정 사실이 아니라 미확인 관측이라는 점은 짚어두자.

또 하나 눈에 띄는 축은 **다년 엔지니어링 협업**이다. AMD는 자사 소프트웨어 개발·엔지니어링·제품 개발 전반에 앤트로픽의 Claude를 도입한다. 즉 앤트로픽은 칩(하드웨어)을 사고, AMD는 그 위에서 돌아갈 모델을 자사 개발 워크플로에 사서 쓰는, 서로를 고객으로 삼는 구조다.

앤트로픽 공동창업자이자 최고컴퓨트책임자(chief compute officer)인 Tom Brown은 보도자료에서 이렇게 말했다. "AMD와 스택 전반에 걸쳐 협력함으로써, 우리는 필요한 (컴퓨트) 용량을 확보하고 이를 Claude의 학습과 서빙에 맞게 최적화하고 있다."

## 왜 중요한가

**컴퓨트가 곧 모델 회사의 생명선이 됐다.** 이 딜의 본질은 투자 뉴스가 아니라 용량 확보(capacity securing) 뉴스다. 프론티어 모델을 학습·서빙하려면 GPU를 얼마나 확보하느냐가 곧 로드맵의 상한을 결정한다. 앤트로픽이 SpaceX·TeraWulf·Google·Broadcom·Amazon에 이어 AMD까지 끌어들이는 이유는, 단일 공급자(사실상 엔비디아)에 묶이면 가격·물량·일정 협상력을 전부 내주기 때문이다. 참고로 The Verge의 별도 보도에 따르면 앤트로픽은 일론 머스크의 데이터센터 접근에 연 150억 달러를 쓰고 있다고 알려졌는데(이번 발표 본문이 아닌 관련 보도), 이 수치 하나만 봐도 컴퓨트 조달이 이 회사의 최대 비용 축임을 짐작할 수 있다.

**AMD에게는 '엔비디아 대안'이라는 레퍼런스가 필요했다.** AI 가속기 시장은 사실상 엔비디아 독점에 가깝고, AMD의 승부처는 "MI450이 실제 프론티어 학습·서빙 워크로드를 감당한다"는 증명이다. 앤트로픽 같은 최상위 랩이 2GW 규모로 MI450 + Helios를 채택한다는 건 그 자체로 강력한 검증 신호다. 투자금을 태워서라도 톱티어 고객을 확보하려는 전략인 셈이다.

**개발자·창업자 관점에서의 함의.** 모델 회사들이 공급자를 다변화하고 자체 데이터센터 딜을 직접 체결한다는 건, 향후 추론 단가와 가용 용량이 이 인프라 경쟁의 결과에 따라 출렁일 수 있다는 뜻이다. 특정 벤더 하드웨어에 락인된 모델 성능·가격에만 의존해 제품을 설계하면, 공급 구도가 바뀔 때 원가 구조가 흔들릴 수 있다. 또한 AMD가 자사 엔지니어링에 Claude를 전면 도입하는 대목은, 칩 설계·검증 같은 고난도 하드웨어 개발 영역에서도 코딩 에이전트가 실무 도구로 채택되고 있다는 방증이다.

## 출처

- The Verge, "AMD commits up to $5 billion to Anthropic" (Emma Roth, 2026-07-22): https://www.theverge.com/ai-artificial-intelligence/969285/amd-anthropic-ai-infrastructure-deal
