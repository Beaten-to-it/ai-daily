---
title: '내가 Google DeepMind를 떠난 이유 — 한 정렬 연구자의 군사 AI 계약 기록'
date: 2026-07-17
tags: [AI, AI안전, 거버넌스, GoogleDeepMind, 군사AI]
source_url: https://news.hada.io/topic?id=31496
source_lang: en
source_type: article
evidence_level: confirmed
event_key: deepmind-researcher-resigns-weapons
---

Google DeepMind의 정렬(alignment) 연구 과학자였던 Alexander Matt Turner(온라인에서 TurnTrout으로 알려진 인물)가, Google이 미 국방부와 "모든 합법적 용도"를 허용하는 AI 계약을 조용히 체결하자 회사를 떠났다고 공개적으로 밝혔다. 그는 자율살상무기와 대규모 감시를 **구속력 있게** 금지하지 않은 그 계약에 양심상 남을 수 없었다고 설명하면서, 자신이 떠나기까지 몇 달간 무엇을 시도했는지를 상세한 기록으로 남겼다. 아래 내용은 모두 Turner 본인의 서술이며, 그가 지목한 인물·계약 조항에 대한 주장은 그의 관점임을 전제로 읽는 것이 맞다.

## TL;DR
- Turner는 Google이 미 국방부에 "모든 합법적 정부 목적"으로 AI를 제공하고 자율무기·국내 대규모 감시 금지에 법적 구속력이 없는 계약을 체결하자 퇴사했다고 밝혔다.
- 그는 퇴사 전 250명 서명, Anthropic 지지 법정 의견서 참여, 인간 통제·비표적 프로파일링 금지를 담은 25쪽짜리 거버넌스 프레임워크 작성까지 시도했으나 고위 정책 담당자의 평가를 받지 못했다고 주장한다.
- 그의 결론은 "개인의 윤리적 약속에 기대는 대신, 사전 제한·독립 검토·투명성을 갖춘 낮은 신뢰(low-trust) 거버넌스가 필요하다"는 것이다.

## 무슨 일이 있었나 (Turner의 기록)

**문제의식의 출발 — DHS·ICE 공급망.** Turner는 2026년 1월 DHS 요원들이 최소 2명을 살해한 사건을 계기로 Google과 이민 단속 기관의 관계를 조사했다고 한다. DHS의 2025 AI Use Case Inventory가 생성형 AI 공급자 중 하나로 Google을 기재했고, Google이 ITC Federal 같은 제3자를 통해 ICE에 클라우드를 판매한다는 점, 2025년 10월 ICE 활동 경고 앱을 스토어에서 내린 점, 학생 시위자 계정을 사전 통지 없이 ICE에 넘긴 점 등을 문제 삼았다. 그가 강조한 핵심은 "특별한 서비스를 줬느냐"가 아니라 "ICE에 서비스를 제공했다는 사실 자체"였다.

**미 국방부의 Anthropic 압박.** 2026년 2월 25일 미 국방부가 Anthropic에 기존의 자율무기·감시 제한을 없애고 Claude를 "모든 합법적 용도"로 제공하라고 요구했고, 거부 시 2억 달러 계약 취소·공급망 위험 업체 지정·Defense Production Act 강제를 위협했다고 Turner는 전한다. 그는 "합법적 용도"라는 기준의 허점을 두 가지로 봤다. 정부가 스스로 합법이라 판단하면 독립 전문가가 전쟁범죄 소지를 지적한 행위도 통과될 수 있고, 기존 감시법이 AI를 전제로 만들어지지 않아 대규모 프로파일링도 합법 범주에 들 수 있다는 것이다. 이후 Lin 판사가 공급망 위험 지정을 "전형적인 불법 수정헌법 제1조 보복"으로 판단했다고 그는 덧붙인다.

**침묵한 조력자들.** Turner는 UNESCO에서 열린 IASEAI 행사에서 Yoshua Bengio, Stuart Russell 등에게 공개 대응을 요청했으나, Bengio는 성명을 내지 않았고 Stuart는 회원 투표를 약속했지만 설문은 끝내 열리지 않았다고 기록한다(그는 투표 참여를 위해 낸 75달러 회원비를 환불받았다). 추상적 금지선에는 300명 넘게 서명했던 석학들이 정작 실제 기업·정부 충돌이 벌어지자 낮은 비용의 도움(예: Google 의사결정자와의 비공개 소개)조차 거절했다는 것이 그의 실망 지점이다.

**Google 내부에서의 시도.** 그는 내부 채널에서 "모든 합법적 용도"를 거부하자고 촉구해 한 메시지에 125개 넘는 지지 반응을 받았고, 하루이틀 만에 약 250명의 서명을 모아 Chief Scientist인 Jeff Dean에게 전달했다고 한다. Anthropic의 소송에 붙는 AI 전문가 법정 의견서에도 서명했고 DeepMind 서명자 18명 중 8명을 자신이 모집했다고 밝힌다. Jeff Dean은 그 의견서에 공개 서명한 유일한 C급 경영진이었지만, Google 자체는 참여하지 않았고 Microsoft가 대신 의견서를 냈다고 한다.

**25쪽짜리 프레임워크.** Turner는 휴가를 써서 계약 문구와 감독 구조를 담은 25쪽 문서를 작성해 군사·감시법 전문가 검토를 받았다고 한다. 두 가지 기준이 핵심이다. ① 각 교전에서 적절한 인간 통제 없이 AI가 표적을 선택·공격하지 못하게 하는 **무력 사용의 인간 통제**(방어·군수·연구개발은 제외), ② 이미 특정된 조사 대상이 아닌 개인 정보로 대량 데이터를 변환하지 못하게 하는 **비표적 AI 프로파일링 금지**. 여기에 Chief Scientist가 임명·감독하는 7인 Defense AI Review Body, 최대 10일 검토 시한, 권고 무시 사례를 연례 투명성 보고서에 남기는 장치, 2018년 원칙처럼 조용히 폐기되지 못하게 하는 해산 요건까지 설계했다고 한다. 그러나 Demis Hassabis가 검토를 지시했음에도 고위 정책 담당자들에게서 평가를 받지 못했다는 것이 그의 불만이다.

**조용히 체결된 계약.** 2026년 4월 27일 보도로 계약 사실이 알려졌고, Turner는 이를 밤 11시 45분 Signal 그룹에서 알게 됐다고 한다. 그가 전하는 계약의 핵심 문구는 — 미 국방부가 Google AI를 "모든 합법적 정부 목적"에 사용할 수 있고, 정부 요청 시 Google이 안전 설정·필터 조정을 지원해야 하며, 국내 대규모 감시나 인간 감독 없는 자율무기에 "쓰여서는 안 된다(should not)"는 문구는 있지만 Google에는 합법적 정부 운용을 거부할 권리가 없다는 것. Turner는 "should not"이 구속력 있는 금지가 아니라 형식적 대응일 뿐이라고 본다.

**"바뀌지 않았다"는 원칙.** Demis Hassabis는 세계가 더 위험해졌으니 정부와 협력해야 하며 "이익이 피해를 크게 능가하는지 신중히 판단한다"는 근본 원칙은 그대로라고 밝혔다고 한다. Turner의 반박은 "상황을 본 뒤 판단한다"는 것은 압력 속에서 지킬 사전 약속이 아니므로 원칙이라 부를 수 없다는 것이다. 그는 2025년 2월 개정된 Google AI 원칙이 무기·감시에 관한 구체적 금지 조항을 제거했다는 점을 들어, "금지를 없앴으면서 원칙은 그대로"라는 두 입장은 동시에 참일 수 없다고 지적한다. 참고로 대조군으로 언급되는 Anthropic은 같은 압력 아래 기존 금지선을 유지했다는 것이 그의 서술이다.

## 왜 중요한가

이 글의 진짜 주장은 특정 계약의 옳고 그름이 아니라 **거버넌스의 구조**다. Turner의 결론 — "사회는 윤리적 개인이 끝까지 버틸 것이라고 의존할 수 없다" — 는 AI 안전 논쟁의 흔한 전제(좋은 사람이 의사결정 테이블에 앉아 있으면 안전하다)를 정면으로 반박한다. 개인 역시 지분·동료 관계·회사와 결합된 자아상 같은 유인에 노출되므로, 결정적 순간에 원칙을 지키려면 개인의 선의가 아니라 **사전 제한·독립 검토·투명성**이 제도로 박혀 있어야 한다는 논리다. Google DeepMind가 무기 사용 금지 약속과 반독립 거버넌스를 전제로 인수됐음에도 그 구조가 약화된 사례, 그리고 2018년 원칙 때문에 100억 달러 JEDI 입찰에서 철수했던 회사가 이번엔 물러서지 않은 대비는, 명문화되지 않은 약속이 얼마나 쉽게 증발하는지를 보여준다.

또 하나 눈여겨볼 것은 **배치 후 투명성의 부재**다. "모든 합법적 용도" 계약에서는 공급자조차 자사 모델이 실제로 어디에 쓰이는지 알 수 없어 "이익이 피해를 능가하는지"를 평가할 수 없다는 지적, 그리고 정렬 안전 논증이 사고 과정(chain-of-thought) 감시에 의존하는데 기밀 군사 환경은 그 감시를 수행할 조건이 갖춰지지 않을 수 있다는 우려는, AI 안전과 조달 정책이 만나는 지점의 구체적 공백을 짚는다.

## 어떻게 써먹나

거버넌스·컴플라이언스를 설계하는 사람이라면 이 글을 **"낮은 신뢰 시스템 설계"의 케이스 스터디**로 읽을 만하다. 핵심은 "좋은 사람이 결정권을 쥐면 된다"가 아니라, 압력이 들어와도 우회하려면 마찰과 공개 비용을 치르게 만드는 구조 — 사전에 그은 명시적 금지선, 이해상충 회피가 박힌 독립 검토체, 무시 사례를 자동으로 기록·공개하는 투명성 장치, 조용한 폐기를 막는 해산 요건 — 다. 조직의 안전 약속이 "should"로만 쓰여 있는지 "must/거부권"으로 쓰여 있는지, 약속을 어겼을 때 자동으로 남는 흔적이 있는지를 점검하는 렌즈로 활용할 수 있다. (기록하되 통제는 개인 선의에 맡기지 않는다는 원칙은, 소프트웨어 배포에서 "머지=완료가 아니라 검증·게이트 통과=완료"인 것과 같은 계열의 사고다.)

## 출처

- 원문 요약: [내가 Google DeepMind를 떠난 이유 — GeekNews](https://news.hada.io/topic?id=31496) (원 출처: turntrout.com, Alexander Matt Turner)

---

Two notes on what I did and didn't do:

- **Attribution:** every serious allegation (contract terms, named people like Jeff Dean / Hassabis / Pichai, IASEAI's inaction) is framed as *Turner's account/claim*, not asserted fact — the confirmed event is that he published his reasons, not that each claim is independently verified.
- **I deliberately excluded the Hacker News comments** (~half the SOURCE), including the contested Emil Michael / All-In podcast account of Dario, which the source itself flags as unreliable. I also ignored the embedded links and "함께 보면 좋은 글" list.

One caveat you should decide on: I couldn't verify the repo's `source_lang` convention for hada.io items (no file access in this session), so I chose `en` on the reasoning that the primary artifact is Turner's English essay. If your other hada.io posts use `ko`, change that one field.
