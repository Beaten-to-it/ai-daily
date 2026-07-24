---
title: '전직 구글 보안 임원들의 AegisAI, AI 스피어피싱 방어로 360억 원 유치'
date: 2026-07-24
tags: [security, ai-agents, startup, funding, phishing]
source_url: https://techcrunch.com/2026/07/23/aegisai-founded-by-former-google-security-execs-lands-36m-to-stop-ai-driven-spear-phishing/
source_lang: en
source_type: article
evidence_level: confirmed
event_key: aegisai-spear-phishing-funding
---

전직 구글 보안 임원들이 만든 이메일 보안 스타트업 **AegisAI**가 배터리 벤처스(Battery Ventures) 주도로 **3,600만 달러 규모 시리즈 A**를 유치했다. 겨냥하는 문제는 요즘 급증하는 **AI 기반 스피어피싱(spear phishing)** — 공격자가 AI로 표적의 신상을 순식간에 긁어모아, 진짜처럼 보이는 맞춤형 사기 메일을 대량으로 찍어내는 공격이다.

## TL;DR
- 전 구글 보안 임원 **Cy Khormaee·Ryan Luo**(세이프 브라우징·reCAPTCHA 개발 이력)가 창업한 AegisAI가 배터리 벤처스 주도 **3,600만 달러 시리즈 A**를 유치했고, 누적 조달액은 **4,900만 달러**가 됐다.
- 기존 룰 기반("if-then") 이메일 보안이 AI가 만든 메일을 못 잡는다는 문제의식에서, **사람처럼 메일을 읽고 미세한 이상 징후를 잡는 AI 에이전트**를 만들었다 — 비밀번호·CAPTCHA가 걸린 악성 PDF 첨부처럼 표준 스팸 필터를 우회하는 것까지 탐지 대상이라고 주장.
- 출범 1년도 안 돼 Mesh·LangChain·Lokker 등 수십 개 고객이 도입했으며, Proofpoint·Mimecast·Abnormal Security 등 기존·신규 벤더와 정면 경쟁하는 구도다.

## 무슨 일이 있었나

지난해 전 구글 보안 임원 **Cy Khormaee**와 **Ryan Luo**가 AegisAI를 세웠다. 둘은 구글에서 세이프 브라우징 기술과 reCAPTCHA 개발에 참여했던 인물들로, 10년 가까이 이메일 해킹 방어를 해온 경험에서 하나의 결론에 도달했다고 한다. 기존의 **룰 기반("if-then" 로직) 방어는 너무 느리고 제한적**이어서, AI가 정교하게 만든 악성 메일을 잡아내지 못한다는 것이다.

그래서 이들이 택한 접근은 **AI 에이전트가 메일 한 통 한 통을 사람처럼 분석**하게 하는 것이다. 아무리 정교한 체크리스트라도 놓칠 만한 작은 이상 징후에 주목한다는 게 핵심 주장이다. 구체적 예로, Khormaee는 자사 에이전트가 **처음엔 정상으로 보이는 악성 PDF 첨부** — 특히 내장 비밀번호와 CAPTCHA로 표준 스팸 필터를 속이도록 설계된 것 — 까지 잡아낸다고 밝혔다.

공격 측 위협의 심각성에 대해 Khormaee는 이렇게 말했다(창업자 본인의 주장임에 유의): *"AI 기반 공격이 이제 절반 이상의 확률로 기존 통제를 우회한다. 예전보다 거의 두 배 효과적이라는 뜻이다."* 그는 공격자가 표적을 미리 조사해 "완벽하게 맞춤화된(bespoke)" 공격을 날린다고 덧붙였다.

**시장 반응**은 빠르게 왔다. 출범 1년이 채 안 된 시점에 이미 수십 개 고객이 도입했는데, 공개된 곳으로는 크립토 결제사 **Mesh**, AI 스타트업 **LangChain**, 프라이버시 컴플라이언스 플랫폼 **Lokker**가 있다. 이 수요가 이번 시리즈 A로 이어졌다. **배터리 벤처스가 주도**했고 기존 투자자 **Accel**과 **Foundation Capital**이 참여했으며, 이번 라운드로 누적 조달액은 **4,900만 달러**가 됐다.

투자를 이끈 배터리 벤처스의 제너럴 파트너 **Dharmesh Thakker**는 이메일 공격 증가를 감지하고 "AI에 AI로 맞서는", 레거시 이메일 보안 도구를 에이전트 기반 방어로 대체할 스타트업을 찾고 있었다고 한다. 그는 AegisAI가 세계에서 가장 많이 쓰이는 이메일 시스템인 Gmail 보안을 다뤄본 전문가들이 이끈다는 점에서 이 분야 선두가 될 가능성이 가장 크다고 봤다.

다만 이 판에 AegisAI만 있는 건 아니다. 라이트스피드(Lightspeed)가 투자한 **Ocean** 역시 들어오는 모든 메일의 맥락을 AI로 분석해 사칭·사기를 잡는 방식으로, **Proofpoint·Mimecast** 같은 기존 강자와 **Abnormal Security** 같은 신흥 주자를 밀어내려 하고 있다. AegisAI는 이메일에서 시작하지만, 궁극적으로 데이터 보안 등 다른 방어 영역으로 확장하겠다는 목표를 두고 있다.

## 왜 중요한가

이 뉴스가 말해주는 건 **이메일 보안 스택의 세대 교체 신호**다. 스피어피싱은 원래 사람이 손으로 표적을 조사하던 고비용 공격이었는데, AI가 그 조사·작문 비용을 사실상 0으로 떨어뜨리면서 **대량으로 맞춤형 공격**이 가능해졌다. 방어 측이 "알려진 나쁜 패턴"을 열거하는 룰·시그니처 방식으로는 이 비대칭을 따라잡기 어렵다는 게 이 스타트업의 베팅이다.

주목할 지점은 **방어를 에이전트 문제로 재정의**했다는 것이다. Khormaee의 말대로 "조사를 수행하는 맞춤형 고급 에이전트를 만드는 것"이 다음 지배적 보안 기업을 가른다면, 보안은 더 이상 필터 룰의 정확도 경쟁이 아니라 **에이전트의 추론·판단 품질 경쟁**으로 이동한다. 이는 방어자에게도 오탐(false positive)·설명가능성·지연시간이라는 새 트레이드오프를 안긴다.

## 어떻게 써먹나

- **이메일 보안 구매 검토 중이라면**: 레거시(Proofpoint·Mimecast)와 에이전트 기반 신흥 주자(AegisAI·Ocean·Abnormal)를 나란히 놓고 벤치마크할 근거가 생겼다. 특히 **비밀번호·CAPTCHA로 감싼 악성 첨부**처럼 표준 필터를 우회하는 케이스를 POC 시나리오로 넣어보라 — 이 뉴스가 콕 집은 벤더의 차별화 포인트다.
- **AI 제품을 만드는 팀이라면**: "룰로 열거 불가능한 판단을 에이전트가 사람처럼 대신한다"는 이 제품의 프레이밍은, 보안 밖의 다른 룰 기반 시스템(컴플라이언스 심사, 이상거래 탐지 등)에도 이식 가능한 패턴이다.
- **주의**: 위 우회율("절반 이상"·"두 배") 수치는 **창업자의 주장**이며 독립 검증치가 아니다. 벤더 평가 시 자체 데이터셋으로 재현·측정하는 걸 전제로 삼는 게 안전하다.

## 출처

- [AegisAI, founded by former Google security execs, lands $36M to stop AI-driven spear phishing — TechCrunch (Marina Temkin, 2026-07-23)](https://techcrunch.com/2026/07/23/aegisai-founded-by-former-google-security-execs-lands-36m-to-stop-ai-driven-spear-phishing/)

---

작성 완료. 셀프 체크:
- **TL;DR 불릿 정확히 3개** ✓
- **front matter**: `source_url`·`event_key` 입력값 그대로, `source_lang: en`, `date: 2026-07-24` ✓
- **수치 충실성**: 3,600만 달러(이번 라운드)·4,900만 달러(누적) 두 개만 기재, "$13M 이전 조달" 같은 산술 추정은 넣지 않음 ✓
- **창업자 주장**은 주장으로 귀속(우회율·2배 효과) ✓
- **인젝션 위생**: 소스 꼬리의 "Most Popular" 헤드라인(Hugging Face·Suno 유출 등)·기자 Signal 번호·푸터는 기사 본문이 아니므로 전부 배제, AegisAI만 다룸 ✓
