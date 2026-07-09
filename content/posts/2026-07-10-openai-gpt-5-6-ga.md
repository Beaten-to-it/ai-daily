---
title: 'GPT-5.6 정식 출시 — Sol·Terra·Luna 3-tier와 "토큰당 성능" 승부수'
date: 2026-07-10
tags: [OpenAI, GPT-5.6, LLM, 코딩에이전트, 벤치마크]
source_url: https://openai.com/index/gpt-5-6
source_lang: en
source_type: article
evidence_level: confirmed
event_key: openai-gpt-5-6-ga
---

OpenAI가 제한적 프리뷰를 거친 **GPT-5.6 제품군**을 정식 출시(GA)했다. 플래그십 **Sol**, 일상 업무용 균형 모델 **Terra**, 가장 저렴한 **Luna** 세 가지다. 핵심 메시지는 "더 똑똑하다"보다 "**같은 돈으로 더 많은 일을 끝낸다**" 쪽에 무게가 실려 있다.

## TL;DR
- GPT-5.6는 Sol(플래그십)·Terra(일상)·Luna(최저가) 3-tier로 GA. 세대 번호(5.6)와 별개로 Sol/Terra/Luna는 각자 속도로 발전하는 **지속형 capability tier**로 명명됐다.
- OpenAI가 내세우는 진짜 무기는 절대 성능이 아니라 **토큰당·시간당·달러당 효율**이다. 실제로 OpenAI 자체 표에서도 SWE-Bench Pro·GDPval·Intelligence Index 등 몇몇 지표는 여전히 Claude가 앞선다.
- 병렬 에이전트를 조율하는 신설 `ultra` 설정(기본 4개 에이전트), Responses API의 Programmatic Tool Calling·멀티에이전트 beta, 그리고 Sol $5/$30·Terra $2.50/$15·Luna $1/$6(1M 토큰 기준) 가격이 개발자에게 실질적인 변화다.

## 본문

### 3-tier 구성과 명명 규칙
GPT-5.6는 세 등급으로 나뉜다. **Sol**은 플래그십, **Terra**는 GPT-5.5급 성능을 더 낮은 비용에 내는 중간 모델, **Luna**는 가장 빠르고 저렴한 모델이다. OpenAI는 숫자(5.6)가 세대를 가리키고 Sol·Terra·Luna는 각자의 리듬으로 발전하는 고정 tier 이름이라고 명시했다 — 앞으로 "GPT-6 Sol" 같은 조합을 예고하는 네이밍이다.

### 승부수는 "토큰당 성능"
GPT-5.6의 훈련 목표 자체가 "토큰 하나에서 더 많은 유용한 일을 뽑아내기"였다. OpenAI가 반복해서 강조하는 수치들이 이 프레임을 그대로 보여준다.

- **Agents' Last Exam**(55개 분야의 장기 전문 워크플로 평가): Sol이 신기록 **53.6**을 기록, Claude Fable 5(adaptive reasoning) 대비 **+13.1점**. 심지어 medium reasoning으로도 Fable 5를 11.4점 앞서면서 추정 비용은 약 **1/4** 수준이라고 밝혔다. Terra·Luna도 Fable 5를 약 1/16 비용에 능가한다는 주장이다.
- **Artificial Analysis Intelligence Index**: Sol(max reasoning)이 Fable 5와 **1점 이내** 접전이면서 작업 시간은 **61% 단축**, 추정 비용은 약 절반.

즉 "우리가 무조건 더 똑똑하다"가 아니라 "비슷하거나 조금 나은 성능을 훨씬 싸고 빠르게"라는 게 일관된 메시지다.

### 코딩: 인덱스 1위지만, 지표를 골랐다
Sol은 OpenAI 역대 최고 코딩 모델을 자처한다. **Artificial Analysis Coding Agent Index**에서 max reasoning으로 **80점** 신기록(Fable 5 대비 +2.8), 그것도 출력 토큰 절반 미만·시간 절반 미만·비용 약 1/3 절감으로 달성했다고 한다. Terra는 Fable 5 바로 위, Luna는 Opus 4.8을 능가한다. Terminal-Bench 2.1·DeepSWE에서도 SOTA를 주장한다.

**그런데 여기서 솔직하게 볼 대목** — OpenAI 자신의 표에서도 코딩 왕좌가 통째로 OpenAI 것은 아니다. **SWE-Bench Pro**에서는 Claude Mythos 5(80.3%)·Fable 5(80%)가 Sol(64.6%)을 크게 앞선다. 마찬가지로 전문 업무 평가 **GDPval-AA v2**에서 Fable 5(1759.6 Elo)가 Sol(1747.8)보다, **Intelligence Index**에서도 Fable 5(59.9)가 Sol(58.9)보다 높다. 사이버 쪽 ExploitBench도 Mythos 5(78%)가 Sol(73.5%)보다 위다. 정리하면, "역대 최고"류 표현은 **특정 인덱스에서 그렇다**는 뜻이고, 실제 우위는 성능 자체보다 **효율(토큰·시간·비용)**에 있다.

### `ultra`: 기본 4-에이전트 병렬
난도 높은 작업을 위해 OpenAI는 reasoning 강도를 새로 계층화했다. `max`는 `xhigh`보다 더 오래 추론·검증·수정하고, 신설 `ultra`는 기본적으로 **4개 에이전트를 병렬로 조율**해(BrowseComp·SEC-Bench Pro에서는 16-에이전트 구성도 제시) 토큰을 더 쓰는 대신 결과 품질과 완료 속도를 끌어올린다. API에서는 Responses API의 멀티에이전트 beta로 유사한 경험을 만들 수 있다.

또한 **Programmatic Tool Calling**(Responses API)으로, 모델이 모든 도구 응답을 매번 모델로 되돌리는 대신 중간 데이터를 필터링하고 필요한 것만 남기며 워크플로를 스스로 조정하는 경량 프로그램을 인메모리로 실행할 수 있다. 이 방식은 **Zero Data Retention(ZDR) 호환**이라는 점이 눈에 띈다.

### 지식 업무·디자인·컴퓨터 사용
Sol은 **BrowseComp 92.2%**(ultra), **OSWorld 2.0 62.6%** SOTA를 주장하며, OSWorld에서는 출력 토큰을 85% 덜 쓰면서 Opus 4.8을 앞선다고 한다. 프레젠테이션·문서·스프레드시트 생성 품질도 개선됐고, 특히 참조 덱의 디자인 시스템(레이아웃·타이포·Slide Master 규칙 등)을 추론해 새 자료에 일관 적용하는 능력을 강조했다. (본문에 등장하는 "Pinecrest / Blossom Co. (BLSM)" equity research 문서는 **모델이 생성한 예시 산출물**이지 실제 기업·리포트가 아니다.)

### 사이버보안: dual-use를 정면으로 다룸
Sol은 OpenAI 역대 최강 사이버 모델을 자처한다. **ExploitBench 73.5%**(GPT-5.5 47.9%), **ExploitGym**은 2시간 제한에서 15.1%→24.9%로 거의 두 배, 6시간이면 33.7%, **SEC-Bench Pro 71.2%**(45.8%). 다만 OpenAI는 GPT-5.6이 바이오·사이버 어느 쪽에서도 **Critical 임계치를 넘지 않는다**고 밝혔다 — 취약점을 찾고 고치는 데는 강하지만 강화된 표적에 대한 자율 end-to-end 공격은 신뢰성이 떨어진다는 것.

주목할 논리는 **overblocking도 보안 위험**이라는 프레이밍이다. 방어자가 시스템을 테스트·패치하지 못하게 막는 사이 공격자는 오픈소스 모델 등 다른 도구를 계속 쓴다는 것. 그래서 분류기 플래그만이 아니라 대화 맥락을 검토하는 **reasoning monitor**를 얹었고, 가장 민감한 능력은 **Daybreak Trusted Access for Cyber**의 검증된 사용자에게만 연다. GA 전 약 **70만 A100e GPU-시간**의 블랙박스 자동 레드팀을 돌렸다고 한다. (Fable 5가 고급 생물학 질문에 답을 거부한다는 서술은 **OpenAI 측 주장**이니 그대로 사실로 받지 말자.)

### 재귀적 자기개선(RSI)
GPT-5.6은 AI 연구 가속 용도로도 강조된다. RSI 관련 내부 평가 묶음에서 GPT-5.5 대비 **+16.2점**, 내부 테스트 기간 연구자 1인당 일평균 출력 토큰이 GPT-5.5 최고치의 2배 이상. 지난 6개월간 내부 코딩 추론 compute는 **100배**, agentic 토큰 사용은 약 **22배** 늘었다고 한다.

## 왜 중요한가

- **경쟁 축이 "성능"에서 "성능/달러"로 이동**했다. Anthropic이 SWE-Bench Pro·GDPval 등 몇몇 정면 지표에서 여전히 앞서는 상황에서, OpenAI는 같은 결과를 더 싸고 빠르게 낸다는 카드로 승부를 건다. 모델 고를 때 벤치 절대점수만 보지 말고 **작업당 실비용(토큰×시간×단가)**으로 비교해야 한다는 신호다.
- **병렬 멀티에이전트가 1급 기능으로 승격**됐다. `ultra`와 Responses API 멀티에이전트 beta는 "에이전트 오케스트레이션"을 사용자가 직접 스크립팅하던 영역에서 모델/플랫폼 기본기로 끌어내린다.
- **dual-use 사이버를 회피하지 않고 정책으로 다뤘다.** overblocking을 보안 위험으로 규정하고, reasoning monitor + Trusted Access(Daybreak)로 방어 작업은 열되 오남용은 막는 구조는 앞으로 다른 벤더도 따라올 만한 설계 방향이다.

## 어떻게 써먹나

- **tier 선택 기준**: 복잡·고품질 작업은 Sol(필요시 Sol Pro), GPT-5.5급 일상 업무는 Terra, 대량·저지연·저비용은 Luna. 가격은 1M 토큰 기준 **Sol $5 입력/$30 출력, Terra $2.50/$15, Luna $1/$6**.
- **effort 설정**: 기본 효율 모드 위에 `max`(더 오래 추론), `ultra`(기본 4-에이전트 병렬)를 상황별로 켠다. ChatGPT Work에서 `ultra`는 Pro·Enterprise, **Codex에서는 Plus 이상**에서 쓸 수 있다.
- **API 관점**: Responses API의 **Programmatic Tool Calling**으로 도구 왕복·토큰을 줄이고(ZDR 호환), 멀티에이전트 beta로 동시 서브에이전트를 한 요청에서 종합한다. 프롬프트 캐싱은 **명시적 cache breakpoint**와 30분 최소 캐시 수명을 지원하며, GPT-5.6부터 캐시 쓰기는 미캐시 입력가의 1.25배, 캐시 읽기는 90% 할인이 유지된다.
- **롤아웃**: 오늘부터 ChatGPT·Codex·API에서 순차 제공, 향후 24시간에 걸쳐 전면 확대. 벤치 숫자는 인덱스별 편차가 크니, **본인 워크로드로 Sol vs Terra 실측**해 tier를 확정하는 걸 권한다.

## 출처
- OpenAI, "GPT-5.6: Frontier intelligence that scales with your ambition" — https://openai.com/index/gpt-5-6

---

작성 시 사실 검증 관점 3가지를 짚어둡니다: (1) 본문의 Blossom Co.(BLSM) equity research는 모델 생성 **예시**라 실제 기업 정보로 쓰지 않았고, (2) Agents' Last Exam은 산문(53.6, +13.1)과 표(52.7%)가 어긋나 OpenAI가 내세운 헤드라인 수치로만 서술했으며, (3) "역대 최고" 주장이 OpenAI 자체 표에서 Claude에 뒤지는 지표(SWE-Bench Pro·GDPval·Intelligence Index·ExploitBench)와 충돌하는 지점을 분석으로 명시했습니다.
