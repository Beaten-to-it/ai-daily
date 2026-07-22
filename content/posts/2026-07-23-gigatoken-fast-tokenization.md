---
title: 'Gigatoken — HuggingFace보다 ~1000배 빠른, GB/s급 토크나이저'
date: 2026-07-23
tags: [tokenizer, tokenization, nlp, llm, rust, simd]
source_url: https://github.com/marcelroed/gigatoken/
source_lang: en
source_type: article
evidence_level: confirmed
event_key: gigatoken-fast-tokenization
---

Marcel Rød이 공개한 **Gigatoken**은 "언어모델 토크나이징을 GB/s 속도로"를 내건 Rust 기반 토크나이저다. `pip install gigatoken` 한 줄로 설치되고, HuggingFace `tokenizers`나 `tiktoken`을 쓰던 코드에 거의 그대로 끼워 넣을 수 있는 드롭인 대체재를 표방한다. 저장소 기준 별 1k개, MIT 라이선스, 구성은 Rust 66.2% / Python 33.3%다.

## TL;DR

- HuggingFace `tokenizers` 대비 최대 **~1000배**(GPT-2 기준 EPYC에서 989×, M4 Max에서 1,268×) 빠른 토크나이징을 내세운다. 단, 이 최고 배수는 Gigatoken 자체 API를 쓸 때이고 호환 모드는 그보다 낮다.
- 비교 대상인 HF `tokenizers`와 `tiktoken`은 **이미 멀티스레드 Rust 구현**이다. 즉 이건 "Rust가 Python을 이겼다"가 아니라 "Rust가 기존 Rust를 이겼다"는 이야기다.
- 속도의 핵심은 보통 정규식 엔진에 맡기던 **프리토크나이제이션을 SIMD로 직접 구현**하고, 분기(branch)를 줄이고, 프리토큰 매핑을 캐시 계층에 맞춰 공격적으로 캐싱한 데 있다.

## 무엇인가

Gigatoken은 BPE(Byte-Pair Encoding) 계열 토크나이저를 CPU에서 극한까지 최적화한 라이브러리다. 폭넓은 CPU 하드웨어(현대 x86, ARM)를 지원하고, 흔히 쓰이는 거의 모든 토크나이저를 커버한다고 밝힌다.

쓰는 방식은 두 가지다.

**호환 모드(가장 쉬움)** — 기존 HF/tiktoken 토크나이저 객체를 감싸서 쓴다.

```python
import gigatoken as gt

# HuggingFace 토크나이저를 감싸는 최소 변경
tokenizer = gt.Tokenizer(hf_tokenizer).as_hf()
tokens = tokenizer.encode_batch(["This is a test string", "And here is another"])

# 또는 tiktoken
tokenizer = gt.Tokenizer(tiktokenizer).as_tiktoken()
```

이 모드는 HF `tokenizers`와 출력이 **정확히 일치**하도록 상당한 공을 들였다고 한다. 다만 그 일치를 맞추는 데 성능 비용이 붙어서, 전반적으로 훨씬 빠르긴 해도 뒤에 나오는 ~1000배까지는 못 간다.

**Gigatoken API(가장 빠름)** — Rust 구현이 데이터를 직접 읽게 하고 오버헤드를 최대한 걷어낸다.

```python
tokenizer = gt.Tokenizer("Qwen/Qwen3-8B")  # HF 모델 이름을 그대로 받는다
file_source = gt.TextFileSource(["owt_train.txt"], separator=b"<|endoftext|>")
tokens = tokenizer.encode_files(file_source)
```

이 경로는 Rust가 파일을 직접 읽어 최대 병렬성을 끌어내는 대신, Python 자료구조를 API로 넘길 때 생기는 읽기 오버헤드는 여전히 감수해야 한다.

## 벤치마크는 얼마나 빠른가

측정 데이터셋은 `owt_train.txt`(openwebtext, 11.9 GB)다. 저자는 이 셋을 고른 이유로 "CommonCrawl 문서에서 텍스트를 추출한 뒤의 형태와 대략 비슷하기 때문"이라고 밝힌다. 대표적인 수치는 다음과 같다(gigatoken은 **GB/s**, 비교군은 **MB/s** 단위임에 주의).

- **AMD EPYC 9565 72코어 ×2소켓(144코어)** — GPT-2: gigatoken 24.53 GB/s vs HF 24.8 MB/s = **989×**, tiktoken 36.0 MB/s 대비 681×. Qwen 3는 22.16 GB/s(648×), Llama 3 계열 22.15 GB/s(457×).
- **Apple M4 Max(16코어)** — GPT-2: gigatoken 8.79 GB/s vs HF 6.9 MB/s = **1,268×**.
- **AMD Ryzen 7 9800X3D(16코어)** — GPT-2: gigatoken 6.27 GB/s vs HF 59.0 MB/s = **106×**.

여기서 두 가지를 짚어야 정직한 그림이 된다.

첫째, 배수는 토크나이저마다 크게 다르다. GPT-2·Phi-4·OLMo·Qwen 같은 BPE 계열은 수백~1000배까지 벌어지지만, **SentencePiece 기반**(Gemma, Mistral 7B v0.3, CodeLlama, TinyLlama/Phi-3 등)은 EPYC에서도 대략 7×~14× 수준에 그친다. 저자 본인이 "SentencePiece 계열은 Gigatoken에서 잘 최적화돼 있지 않다"고 명시한다. 따라서 "무조건 1000배"가 아니라 "BPE 계열에서 최고 1000배"로 읽는 게 맞다.

둘째, 비교 조건이 오히려 gigatoken에 불리하게 세팅돼 있다. gigatoken은 파일 전체를 **분할하지 않고 통째로** 인코딩하면서 분할 경계를 스스로 찾고 자동 병렬화까지 한다 — 즉 남들보다 더 많은 일을 한다. 반면 HF(`encode_batch_fast`)는 앞 100 MB만, tiktoken(`encode_ordinary_batch`)은 앞 1 GB만, 둘 다 `<|endoftext|>`로 미리 분할된 상태에서 측정했다. 두 비교군 모두 캐싱을 하지 않아 처리 속도가 구간 내내 거의 균일하기 때문에 이 비교가 공정하다는 게 저자의 설명이다.

체감 스케일로는, EPYC 기준 속도라면 흔히 "인터넷 전체"로 불리는 Common Crawl(130조 토큰)을 **약 6.5시간**에 토크나이징할 수 있다고 한다.

## 왜 이렇게 빠른가

저자는 FAQ에서 "특정 CPU/토크나이저 하나에 과최적화한 것 아니냐"는 질문에 "아니, 모든 조합에 과최적화했다"고 답한다. 결과가 현대 x86·ARM 전반, 그리고 개별 토크나이저 전반에서 일관적이라는 것이다. 핵심 기법은:

- **프리토크나이제이션의 SIMD 구현** — 보통 정규식 엔진에 외주 주던 이 단계를 SIMD로 직접 짜고 분기를 최소화했다.
- **프리토큰 매핑의 캐시 계층 최적화** — 이미 본 단어라면 인코딩 결과를 효율적으로 되찾는다. 이 도메인에서 캐싱은 캐시가 매우 빨리 커지고 프리토큰 분포가 심하게 롱테일이라 어려운 문제인데, 여기에 공을 들였다.
- **Python 상호작용 최소화 + 스레드 간 통신 회피**로 추가 이득을 얻었다.

CLI로 설치 없이 바로 검증·측정도 가능하다.

```bash
wget https://huggingface.co/datasets/stanford-cs336/owt-sample/resolve/main/owt_train.txt.gz
gunzip owt_train.txt.gz
uvx --with tokenizers gigatoken bench 'openai-community/gpt2' owt_train.txt \
  --validate --doc-separator "<|endoftext|>"
```

`--validate`는 실제로 HF 출력과 문서 단위로 일치하는지까지 확인한다(예시 로그: "validation OK: 20401 documents match"). macOS에서는 첫 실행 시 보안 스캔 때문에 느리게 나오니 두 번 돌려 재보라는 팁도 붙어 있다.

## 왜 중요한가

토크나이징은 LLM 데이터 파이프라인에서 조용히 병목이 되는 단계다. 수 TB~PB급 코퍼스를 다룰 때 토크나이징이 MB/s면 전처리에만 며칠~몇 주가 갈 수 있는데, GB/s로 올라가면 같은 작업이 시간 단위로 줄어든다. "CommonCrawl 전체를 6.5시간"이라는 수치가 과장처럼 들려도, 대규모 사전학습 데이터 준비를 반복하는 팀에게는 반복 주기와 컴퓨트 비용을 직접 깎는 이야기다.

특히 비교 기준이 이미 멀티스레드 Rust인 HF `tokenizers`라는 점이 핵심이다. "느린 Python을 Rust로 바꿔 빨라졌다"는 흔한 서사가 아니라, 잘 만든 Rust 구현조차 SIMD 프리토크나이제이션과 캐시 계층 설계로 두세 자릿수 배 더 짜낼 여지가 있었다는 뜻이다. 정규식 엔진에 외주하던 뜨거운 경로를 손으로 SIMD화한다는 접근은 다른 텍스트 처리 병목에도 시사하는 바가 있다.

## 어떻게 써먹나

- **가장 빠르게 확인**: 설치 없이 `uvx --with tokenizers gigatoken bench '<HF 모델명>' <데이터파일> --validate`로 내 토크나이저가 지원되는지, 얼마나 빨라지는지 바로 재본다. `uvx gigatoken bench --help`로 플래그를 볼 수 있다.
- **기존 코드 최소 변경**: 출력 호환이 중요하면 호환 모드(`.as_hf()` / `.as_tiktoken()`)로 감싸 드롭인한다. 최고 속도가 필요하고 파일을 직접 읽어도 되는 대규모 전처리라면 Gigatoken API(`encode_files` + `TextFileSource`)로 간다.
- **적용 전 확인할 제약**: 아직 파일 싱크(file sink)는 미구현, WordPiece 미지원, SentencePiece 계열은 최적화가 약함, Windows는 테스트가 적어 WSL 권장. 또 Python 반복 처리는 ABI3를 써서 버전별 CPython API보다 느린데, 저자는 버전별 특수화로 오버헤드-바운드 케이스에서 ~2배 개선을 예고했다.

참고로 코드베이스 대부분은 손으로 작성됐고(깃 히스토리로 확인 가능하다고 밝힘), 최종 단계에서 사용자용 API, 호환성 확대, AVX512/AVX2/NEON 간 SIMD 전략 포팅, 마지막 ~4배어치 분기 제거·캐시 튜닝, 리팩터링 등에만 AI를 보조로 썼다고 공개돼 있다.

## 출처

- Gigatoken (marcelroed/gigatoken): https://github.com/marcelroed/gigatoken/
