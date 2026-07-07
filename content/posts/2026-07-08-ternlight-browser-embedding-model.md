---
title: 'Ternlight — 브라우저에서 통째로 도는 7MB 임베딩 모델'
date: 2026-07-08
tags: [임베딩, WASM, 온디바이스, 시맨틱검색, 오픈소스]
source_url: https://news.hada.io/topic?id=31218
source_lang: ko
source_type: article
evidence_level: confirmed
event_key: ternlight-browser-embedding-model
---

## TL;DR

- **엔진+가중치 7MB(mini는 5MB), CPU 전용**으로 브라우저 안에서 텍스트 임베딩과 유사도 검색을 끝낸다. 서버·API 호출이 아예 없다.
- `npm install @ternlight/base` 후 `embed`/`similar`를 가져오면 **3줄 수준**으로 시맨틱 검색이 붙는다. 임베딩당 약 5ms, 384차원 벡터, 코사인 유사도로 관련성을 판단한다.
- MiniLM에서 문장 인코더를 증류하고 **ternary(3진) 양자화 인식 학습**을 얹은 뒤 추론 엔진을 Rust→WASM SIMD로 직접 구현했다. **MIT 라이선스**, 데모는 React 문서 2,000개를 전부 기기 내에서 검색한다.

## 무엇인가

Ternlight는 임베딩 모델을 서버가 아니라 사용자의 브라우저 탭 안에서 돌리는 라이브러리다. LLM이 아니라 **임베딩 모델**이라는 점이 핵심이다. 텍스트를 넣으면 384차원 벡터가 나오고, 두 벡터의 코사인 유사도로 "이 두 문장이 얼마나 비슷한 의미인가"를 잰다. 제작자가 든 예시가 직관적이다 — `"reset my password"`와 `"I forgot my password"`가 약 **0.88**로 붙는다. 단어가 하나도 겹치지 않아도 의미가 가까우면 높게 나온다는 뜻이고, 이게 키워드 매칭(Fuse.js·`LIKE`)과 시맨틱 검색을 가르는 지점이다.

패키지는 두 티어다.

- **`@ternlight/base`** — 엔진+가중치 합쳐 7MB, 임베딩당 약 5ms, 상대적으로 품질이 더 좋은 임베딩.
- **`@ternlight/mini`** — 전송 기준 5MB, 임베딩당 약 2.5ms. HN 논의에 따르면 mini는 내부적으로 384가 아니라 **256차원 벡터**로 계산해 공간을 줄이고, 마지막에 호환성을 위해 384로 투영한다. 크기는 1/3 줄지만 정보 손실은 선형이 아니라서 체감 손실은 1/3보다 작다는 관찰이 붙었다.

둘 다 Node와 브라우저용으로 번들링돼 있어, 서버에서 배치 색인을 돌리고 브라우저에서 실시간 질의를 처리하는 식으로 나눠 쓸 수 있다.

## 어떻게 만들었나

이건 거대 모델을 그냥 웹으로 옮긴 게 아니다. 제작자는 취미 프로젝트로 "브라우저에서 쓸 만한 모델"을 목표로 잡고 세 가지를 직접 했다.

1. **증류(distillation)** — MiniLM에서 더 작은 문장 인코더를 뽑아냈다. 성능-크기 균형이 좋기로 알려진 MiniLM-L6 계열을 출발점으로 삼았다(단, HN에서는 "같은 급 중 특별히 좋아서 골랐는지는 제시된 지표만으로 판단하기 어렵다"는 지적이 있었다 — 공개된 벤치가 SciFact NDCG@10 하나뿐).
2. **ternary 양자화 인식 학습(QAT)** — 가중치를 3진으로 눌러 7MB까지 줄였다. 이름 "Tern(three)"이 여기서 온 것으로 보인다.
3. **추론 엔진 직접 작성** — Rust로 짜서 WASM SIMD로 배포했다. 브라우저에서 CPU만으로 밀리초 단위 임베딩이 나오는 게 이 엔진 덕이다.

저장소(github.com/soycaporal/ternlight)에는 기술 세부·MIT 라이선스·학습 파이프라인이 함께 공개돼 있다. 즉 가중치만 던진 게 아니라 재현 경로까지 열어둔 셈이다.

## 써먹는 법

가장 짧은 경로는 이렇다. 별도 모델 다운로드 단계나 서버 없이 npm 패키지 하나로 끝난다.

```
npm install @ternlight/base
```

```js
import { embed, similar } from '@ternlight/base';
similar('easy weeknight dinner ideas', recipes, { topK: 3 });
// → 순위 매겨진 매치 · 약 5ms · 네트워크 호출 0
```

`recipes` 배열을 넘기면 질의와 의미가 가까운 상위 3개를 정렬해 돌려준다. 데모(ternlight-demo.vercel.app)는 이 흐름으로 React 문서 2,000건을 전부 기기 안에서 검색한다. HN에서는 이미 django 문서 전체와 사내 지식베이스를 통째로 임베딩해 즉시 검색에 쓴 사례가 올라왔다.

현실적인 조합 아이디어도 나왔다.

- **정적 사이트 검색** — Astro 같은 메타프레임워크 플러그인으로 빌드 시 생성된 HTML을 파싱해 작은 임베딩 DB를 만들고, 프런트엔드에서 지연 로딩. `pagefind`의 시맨틱 버전에 가깝다.
- **하이브리드 검색** — 네이티브 SQLite의 FTS5/BM25(키워드)와 Ternlight의 의미 검색을 Reciprocal Rank Fusion으로 합치기.
- **서버 선(先)색인 → 프런트 전송** — 30초 걸리는 임베딩 생성은 서버에서 한 번만 돌리고, 완성된 벡터만 브라우저로 보내 추론은 클라이언트에서. FAQ/의도 매칭, 군집화, 데스크톱 앱 내장 검색에 적합하다.

## 왜 중요한가

임베딩을 브라우저로 완전히 끌어내리면 세 가지가 공짜가 된다. **비용**(임베딩 API 호출 0), **지연**(왕복 네트워크 제거, ~5ms), **프라이버시**(입력이 기기를 떠나지 않음). 특히 "제품 DB에서 싸고 빠른 검색", "로컬 앱의 오프라인 시맨틱 검색"처럼 API 의존이 부담스러웠던 자리를 정확히 겨냥한다. CPU 전용이라는 제약이 오히려 장점이라는 반응도 있었다 — GPU가 없는 평범한 사용자 기기 어디서나 돈다.

더 크게 보면, HTTP 범위 요청으로 정적 호스팅된 Parquet/SQLite를 검색하는 접근(portable-hnsw, absurder-sql 등)과 엮여 **대기업이 통제하지 않는 분산·정적 벡터 검색 생태계**의 빠진 조각이 될 수 있다는 기대가 붙었다.

다만 "confirmed"인 사실만큼 한계도 솔직히 봐야 한다. HN에는 i5-4570의 Firefox에서 홍보된 초당 400개가 아니라 **초당 35개**만 나왔다는 보고가 있었고(비-SIMD 경로로 떨어졌을 가능성 제기), 데모에서 `"how to use typescript with createContext"`를 검색하면 typescript 항목만 상위로 올라와 유사도 검색이 실패한 것처럼 보인다는 지적도 있었다. 초소형 증류 모델의 품질 한계와 실행 환경별 SIMD 편차는 도입 전 자기 데이터로 반드시 벤치해야 할 부분이다. 영어 외 언어 품질과 다른 초소형 임베딩 모델과의 비교 지표도 아직 공개가 얇다.

## 출처

- GeekNews: https://news.hada.io/topic?id=31218
- 데모: https://ternlight-demo.vercel.app
- 저장소(MIT): https://github.com/soycaporal/ternlight
