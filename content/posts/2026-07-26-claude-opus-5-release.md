---
title: 'Claude Opus 5, Artificial Analysis 지능 리더보드 1위 — 그런데 ''1위''가 예전만큼 안 중요해진 이유'
date: 2026-07-26
tags: [Claude, Opus5, 벤치마크, LLM, ArtificialAnalysis]
source_url: https://news.hada.io/topic?id=31807
source_lang: ko
source_type: article
evidence_level: confirmed
event_key: claude-opus-5-release
---

Artificial Analysis가 평가한 170개 모델 중 **Claude Opus 5**가 종합 지능 지표 1위에 올랐다. 다만 이 소식을 전한 GeekNews 스레드에서 더 흥미로운 부분은 순위 자체가 아니라, "단일 지능 점수 1위"라는 개념이 실무에서 점점 무의미해지고 있다는 커뮤니티의 반응이다.

## TL;DR
- Claude Opus 5(Adaptive Reasoning·Max Effort)가 Intelligence Index v4.1 **61점으로 170개 모델 중 1위**. Xhigh 구성과 Fable 5(Max, Opus 4.8 fallback)가 각 60점, GPT-5.6 Sol(max)이 59점으로 뒤를 이었다.
- Index는 에이전트·코딩·과학 추론·지식 신뢰성·장문맥 등 **9개 평가를 하나로 합친 종합 점수**이고, 추론 모델의 확장 사고 시간까지 성능에 반영한다.
- 속도(Mercury 2 901.6 tok/s)·지연(Gemini 2.5 Flash-Lite 0.34초)·문맥 창(Llama 4 Scout 10M)·**작업당 비용**은 완전히 다른 축이라, "1위 모델"이 곧 "당신이 써야 할 모델"은 아니다.

## 무슨 일인가

Artificial Analysis의 **Intelligence Index v4.1** 리더보드에서 Claude Opus 5의 `Adaptive Reasoning, Max Effort` 구성이 61점으로 평가 대상 170개 모델 중 1위를 기록했다. 상위 5개는 다음과 같다.

| 순위 | 모델(구성) | 점수 |
|---|---|---|
| 1 | Claude Opus 5 (Adaptive Reasoning, Max Effort) | 61 |
| 2 | Claude Opus 5 (Adaptive Reasoning, Xhigh Effort) | 60 |
| 2 | Claude Fable 5 (Adaptive Reasoning, Max Effort, Opus 4.8 Fallback) | 60 |
| 4 | GPT-5.6 Sol (max) | 59 |
| 4 | Claude Opus 5 (Adaptive Reasoning, High Effort) | 59 |

주목할 점은 **같은 Opus 5도 추론 노력(effort) 설정에 따라 61→60→59점으로 갈린다**는 것이다. Max 구성은 126개 추론 모델 중에서도 1위지만, 그건 답변 전에 확장 사고(extended thinking)를 최대로 돌린 결과다.

Index v4.1 자체는 단일 시험이 아니라 9개 평가의 결합이다. 에이전트 실무(GDPval-AA v2), 도구 사용(𝜏³-Banking), 에이전트 코딩·터미널(Terminal-Bench v2.1), 코딩(SciCode), 추론·지식(Humanity's Last Exam), 과학 추론(GPQA Diamond), 물리(CritPt), 지식 정확도와 비환각률(AA-Omniscience), 장문맥 추론(AA-LCR)을 가중 합산한다. 즉 "지능 61점"은 하나의 능력이 아니라 **아홉 가지 능력의 평균을 한 숫자로 압축한 것**이다.

### 지능은 여러 축 중 하나일 뿐

리더보드가 보여주는 다른 축들을 보면 "1위 = 최선"이라는 등식이 왜 성립하지 않는지 분명해진다.

- **출력 속도:** Mercury 2가 901.6 tokens/s로 가장 빠르다. Gemini 3.5 Flash-Lite(435.1), HyperNova 60B(427.6)가 뒤를 잇는다. 지능 상위권 모델들은 이 축에서 상위권이 아니다.
- **첫 토큰 지연(TTFT):** Gemini 2.5 Flash-Lite(Non-reasoning)가 0.34초로 가장 짧다. 추론 모델은 답변 전 사고 시간이 지연에 포함되므로 구조적으로 불리하다.
- **문맥 창:** Llama 4 Scout가 10M 토큰, Grok 4.20이 2M 토큰. RAG처럼 대량 데이터에서 검색·추론하는 워크플로라면 지능 점수보다 이쪽이 결정적이다.
- **비용:** Artificial Analysis는 단순 토큰 단가가 아니라 입력·캐시 적중·캐시 쓰기·추론·답변 토큰을 모두 가중한 **"작업당 비용(cost per task)"**으로 비교한다. Anthropic은 캐시 쓰기를 별도 과금(5분/1시간 TTL 요율 상이)하고, Google Vertex는 시간당 저장 비용을 매기며, OpenAI·DeepSeek은 보통 캐시 적중 가격만 받는 등 제공업체마다 비용 구조가 달라 단순 단가 비교가 왜곡될 수 있다.

### 공개 가중치(open-weight) 진영

평가된 170개 중 94개가 공개 가중치 모델이다. 이 진영 1위는 **GLM-5.2(max) 51점**으로, MiniMax-M3와 DeepSeek V4 Pro(각 44점)가 뒤를 잇는다. 다만 전체 1위(61점)보다 10점 낮다 — 오픈 가중치가 프론티어 폐쇄 모델을 상당히 따라잡았지만 최상단과의 격차는 여전히 존재한다는 뜻이다.

### 커뮤니티 반응 — "순위표가 사실상 무의미해졌다"

여기서부터는 확정된 벤치마크 수치가 아니라 스레드에 달린 **Hacker News 의견들**이라, 사실이 아니라 관점으로 읽어야 한다. 요지는 이렇다.

- **단일 지표 순위는 최종 사용자의 모델 선택에 별 쓸모가 없어졌다는 지적.** 모델마다 분야별 강약이 달라 "UI 디자인엔 Fable, 백엔드 설계엔 Sol, 취약점 개발엔 Kimi K3" 식으로 작업별로 갈아탄다는 것. 이런 종합 순위는 "모델 회사의 과시용 숫자"에 가깝다는 냉소도 나온다.
- **비용 대비 성능 논쟁.** 한 댓글은 지능 대비 비용 행렬에서 GPT-5.6 Sol Max가 Opus 5보다 절반가량 저렴하면서 1~2% 차이의 점수를 낸다고 주장하며, Opus 5가 Fable 5 다음으로 비싼 모델이라는 점을 지적했다. 또 Max가 아닌 Medium 노력으로 낮추면 "코딩 작업의 95%에는 충분할 것"이라는 실무 의견도 있다.
- **반대편 옹호.** "벤치마크만 노린 모델이 아니라 직접 써보니 세대가 바뀐 수준의 도약"이라는 호평, "Opus 5는 4.8처럼 모든 걸 다시 설명하지 않아 좋다"는 반응도 공존한다.
- **안전 과잉 불만.** Opus 5가 넓은 권한을 이유로 배포 작업을 거부했는데 다른 모델들은 처리했다는 사례, Anthropic의 무음 하향 전환(silent downgrade)에 대한 불만 등도 제기됐다. (모두 검증되지 않은 개인 경험담이다.)

균형 잡힌 반박도 있었다. "완전히 무의미하다"는 표현은 과장이며, 링크를 실제로 열어보면 단일 지표만 있는 게 아니라 작업당 비용·환각 빈도 등 판단에 필요한 지표가 모두 제공된다는 것. 문제는 이를 **하나의 종합 점수로 합치는 순간 미묘한 차이가 사라지고 "과시용 순위"만 남는다**는 데 있다.

## 왜 중요한가

Opus 5의 1위 자체보다, 이 스레드가 드러낸 **"프론티어 모델 시장의 성숙"**이 더 중요한 신호다. 상위 5개 모델이 61~59점 안에 몰려 있다는 건, 이제 종합 지능만으로는 모델 간 유의미한 차이를 만들기 어려워졌다는 뜻이다. 같은 Opus 5조차 effort 설정에 따라 순위가 뒤바뀌는 상황에서, "어느 회사 모델이 1등이냐"는 질문은 갈수록 답하기 애매해진다.

개발자·창업자 입장에서 실질적 변수는 지능 2점 차이가 아니라 **작업당 비용, 지연, 문맥 창, 그리고 우리 스택에서의 실제 동작**이다. Artificial Analysis가 종합 점수 옆에 비용·속도 축을 나란히 두는 이유도 여기에 있다.

## 어떻게 써먹나

이 리더보드의 자체 결론이 곧 실무 지침이다 — **단일 지능 점수로 모델을 고르지 말라.**

- **작업 유형별로 필요한 축을 먼저 정한다.** RAG·대량 문서 처리라면 문맥 창(10M급), 대화형 UX라면 TTFT·출력 속도, 대량 배치 추론이라면 작업당 비용이 지능 점수보다 우선한다.
- **effort/reasoning 설정을 비용 레버로 다룬다.** Opus 5도 Max→High→Medium으로 내리면 점수는 소폭 빠지지만 비용은 크게 준다. "대부분의 실무 작업엔 Max가 과잉"이라는 커뮤니티 관점은 최소한 A/B로 검증해볼 가치가 있다.
- **종합 점수 대신 세부 평가를 본다.** 코딩이 목적이면 SciCode·Terminal-Bench, 지식 신뢰성이 중요하면 AA-Omniscience(정답 보상·환각 감점·거부 무감점) 축을 직접 확인하는 편이 종합 1위 배지보다 결정에 도움이 된다.

## 출처

- [Claude Opus 5, Artificial Analysis 지능 리더보드 1위 — GeekNews](https://news.hada.io/topic?id=31807)

---

작성 완료. 벤치마크 수치는 GeekNews 사실 보도 층에서만 확정으로 서술하고, HN 댓글의 비용·거부·검열 주장은 "커뮤니티 반응"으로 격리해 관점임을 명시했습니다. `source_lang: ko`(인용 페이지가 한국어), TL;DR 정확히 3불릿, 잘린 URL(`...intelligence-index-toke...`)은 재현하지 않고 `source_url`만 그대로 사용했습니다.
