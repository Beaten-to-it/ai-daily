---
title: 'Prime Intellect, 1,300억원 시리즈 A — "모든 기업이 자기 AI랩을 갖는다"'
date: 2026-07-09
tags: [AI, 강화학습, 펀딩, AI주권, 에이전트, 인프라]
source_url: https://techcrunch.com/2026/07/08/prime-intellect-raises-130m-series-a-to-help-enterprises-build-their-own-ai-agents/
source_lang: en
source_type: article
evidence_level: confirmed
event_key: prime-intellect-series-a
---

프런티어 랩에 종속되지 않고 **기업이 스스로 에이전트를 훈련**하도록 돕는 스타트업 Prime Intellect가 1억 3천만 달러(약 1,300억원) 시리즈 A를 유치했다. 밸류에이션은 10억 달러, 딱 유니콘 라인이다.

## TL;DR

- Prime Intellect가 Radical Ventures 주도로 **$130M 시리즈 A(밸류 $10억)**를 유치. Nvidia Ventures·Intel Capital·Dell Technologies Capital·Iconiq와 Perplexity·Box·Harvey·Cognition·Mercor 창업자들이 엔젤로 참여했다.
- 제품은 컴퓨트 + 강화학습(RL) 프레임워크 + 평가 도구를 묶은 **"풀스택" 에이전트 개발 마켓플레이스**. 모듈식이라 필요한 조각만 골라 쓰고 all-or-nothing 락인이 없다.
- 2024년 창업, 벌써 **연환산 매출(ARR) $1억** 규모. Ramp가 이 플랫폼으로 만든 스프레드시트 응답 에이전트가 "정확도에서 프런티어 모델을 이기면서 더 빠르고 비용은 일부만" 나왔다고 밝혔다.

## 무슨 일인가

Prime Intellect의 목표는 한 문장으로 요약된다: 조직이 **프런티어 AI 랩에 의존하지 않고 자기만의 에이전틱 시스템을 훈련**할 수 있게 하는 것. 불과 몇 년 전만 해도 비현실적이던 이 그림이 지금 가능해진 배경으로 회사는 강화학습(RL)의 부상을 든다. 성공한 작업 완료엔 보상을 주고 오류엔 페널티를 주며 반복적으로 모델을 다듬는 방식인데, 이 덕분에 기업이 특정 업무에 맞춰 모델을 조율해 "스스로의 AI랩"이 될 수 있다는 논리다.

문제는 닫힌 랩을 우회하는 게 원리상 가능해졌어도, 밑단 인프라가 너무 복잡해 대부분의 회사엔 이 조각들을 프로덕션 시스템으로 조립할 전문성이 없다는 점이다. Prime Intellect가 파고든 지점이 정확히 여기다. 회사는 **컴퓨트 접근 · RL 프레임워크 · 평가(evaluation) 도구**를 하나로 엮은 "풀스택"을 만들었고, 이걸 마켓플레이스처럼 운영한다. 고객은 all-or-nothing 시스템에 묶이지 않고 필요한 도구만 골라 쓴다.

투자를 주도한 Radical Ventures의 파트너 David Katz는 "여러 곳이 조각조각은 제공하지만, Prime Intellect는 톱티어 AI랩의 역량을 '원스톱'으로 제공하는 게 독특하다"며 "프런티어 수준을 감당 가능한 비용으로 돌아가게 엮어냈다"고 평했다.

성과는 매출로 나타난다. Ramp, Zapier, Flapping Airplanes 같은 고객이 호스팅 버전을 쓰며 비용을 지불하고 있고, 이 빠른 도입이 회사를 **연환산 매출 $1억** 규모로 밀어 올렸다. 대표 사례가 Ramp다. Ramp는 스프레드시트 안에서 답을 찾아주는 에이전트를 Prime Intellect로 구축했는데, 공동창업자 겸 공동 CEO Karim Atiyeh는 "결과물이 정확도에서 프런티어 모델을 이기면서, 더 빠른 속도로, 비용은 일부만 들여 돌아갔다"고 밝혔다.

## 왜 중요한가

성장을 미는 또 하나의 축은 **프런티어 랩 위에 쌓는 것 자체가 리스크**라는 기업들의 자각이다. 기사가 짚는 위험은 둘이다. 첫째, 사내 독점 정보를 OpenAI·Anthropic에 넘기면서 데이터 통제권을 잃는 것. 둘째, 의존하던 모델이 어느 날 갑자기 꺼지는 것 — 지난달 Anthropic이 Fable을 종료시킨 사례가 그대로 인용된다. Katz의 표현을 빌리면 "내가 지금 하는 일을 일반화해서 나를 대체하려 들 회사와 일하고 있는 건 아닌지"라는 불안이 "내 엔터프라이즈 인텔리전스를 내가 소유하자"는 움직임을 만들고 있다.

이건 개발자·창업자 입장에서 익숙한 딜레마의 자본 시장 버전이다. 프런티어 API는 빠르게 시작하게 해주지만, (1) 데이터 주권, (2) 공급자 종속과 갑작스러운 EOL, (3) 벤더가 당신의 도메인으로 상향 침투할 위험을 안긴다. Fable 종료는 "네 의존성은 사라질 수 있다"는 걸 추상론이 아니라 실제 사건으로 못박았다. Prime Intellect의 시리즈 A는 이 불안에 **"자기 스택을 소유하라"**는 답을 파는 인프라 레이어가 유니콘 밸류를 받을 만큼 실재하는 시장이 됐다는 신호다. CEO Vincent Weisser의 말이 포지셔닝을 압축한다 — "AI 모델을 훈련할 능력이 샌프란시스코 유리 타워 속 소수 너드에게만 있어선 안 된다. 모든 기업, 모든 국가가 가져야 한다." 'AI 주권(AI sovereignty)'이라는 태그가 붙는 이유다.

## 어떻게 써먹나

- **프런티어 API 위에 핵심 제품을 얹고 있는 팀**이라면, "모델이 내일 꺼지거나 가격이 바뀌면?"과 "내 독점 데이터가 벤더 학습에 흘러가나?"를 이번 기회에 명시적으로 리스크 항목으로 올려라. Fable 사례가 그 시나리오의 실제 전례다.
- 다만 RL로 특정 업무 모델을 직접 조율하는 건 여전히 컴퓨트·RL 파이프라인·평가 셋업이 필요하다. Prime Intellect의 세일즈 포인트는 이걸 "직접 조립하지 않아도 되게" 마켓플레이스로 모듈화했다는 것. **전면 자체 구축 vs. 이런 풀스택 플랫폼 임대**의 비교 축은 이제 "가능하냐"가 아니라 "우리 팀의 전문성·비용·통제권 트레이드오프에서 어디가 맞냐"로 옮겨갔다.
- 벤치마크 주장(정확도·속도·비용에서 프런티어 우위)은 **Ramp의 스프레드시트 응답이라는 좁고 반복적인 태스크**에서 나온 결과다. 자기 도메인에 적용하려면 같은 종류의 좁은 태스크에서 자체 eval로 재현되는지부터 확인하는 게 순서다.

## 출처

- Marina Temkin, "Prime Intellect raises $130M Series A to help enterprises build their own AI agents", TechCrunch, 2026-07-08 — https://techcrunch.com/2026/07/08/prime-intellect-raises-130m-series-a-to-help-enterprises-build-their-own-ai-agents/

---

자체 점검 완료: `## TL;DR` 불릿 정확히 3개 / front matter의 `source_url`·`event_key`·`date` 입력값 그대로 / 페이지 크롬·무관 헤드라인 미포함 / 수치는 전부 원문 근거.
