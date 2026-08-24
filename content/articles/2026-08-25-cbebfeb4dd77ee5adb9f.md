---
title: '코딩 에이전트 세션 옮기는 오픈소스 도구 ‘session-migrate’ 공개'
date: 2026-08-25
tags: [AI, 코딩 에이전트, 오픈소스, 개발 도구]
source_url: https://github.com/xhluca/session-migrate
source_name: github.com
source_published_at: 2026-08-24T20:44:24+00:00
source_lang: en
source_type: article
evidence_level: confirmed
event_key: cbebfeb4dd77ee5adb9f
---

## 무엇이 있었나

코딩 에이전트의 작업 세션을 서로 다른 도구로 이전할 수 있는 오픈소스 프로젝트 ‘session-migrate’가 공개됐다. 지원 대상으로는 Claude Code, Codex CLI, Pi, OpenCode, GitHub Copilot CLI, Antigravity CLI, Cursor Agent, Mistral Vibe가 제시됐다. 같은 형식으로 다시 옮기는 경우까지 포함해 총 64개 경로를 지원한다는 설명이다.

이 도구는 원본 세션을 검증된 이벤트 타임라인으로 변환한 뒤, 대상 도구가 인식하고 재개할 수 있는 새로운 네이티브 세션으로 작성한다. 사용자와 어시스턴트의 메시지는 순서대로 보존하지만 도구 호출, 이미지, 요약 정보 등은 양쪽 형식의 지원 범위에 따라 일부만 이전될 수 있다. 인증 정보와 실행 정책, 훅, MCP 설정, 비공개 또는 서명된 추론 기록은 옮기지 않는다. 원본 세션도 수정하지 않는다.

현재 설치 및 실행 환경은 Python 3.11 이상과 리눅스로 한정돼 있다. Cursor 지원은 특정 리눅스 빌드에 고정된 실험 기능이며, 대화의 사용자·어시스턴트 텍스트만 이전한다.

## 왜 중요한가

개발자가 작업 도중 코딩 에이전트를 바꾸려면 기존 대화와 문제 해결 맥락을 새 도구에 다시 전달해야 했다. session-migrate는 이 과정을 재개 가능한 세션 단위로 처리해, 도구를 비교하거나 상황에 따라 다른 에이전트로 전환할 때 발생하는 반복 작업을 줄일 가능성이 있다.

특정 업체의 코딩 도구에 작업 이력이 묶이는 문제를 완화한다는 점도 의미가 있다. 다만 모든 실행 상태를 그대로 복제하거나 여러 도구 사이에서 실시간으로 동기화하는 방식은 아니다. 대상 도구에서는 새 식별자를 가진 독립 세션이 만들어지며, 인증과 프로젝트 정책 같은 실행 환경은 별도로 준비해야 한다.

## 확인 범위

GitHub 저장소의 README에 제시된 지원 도구, 이전 방식, 보존·제외 항목, 설치 환경을 확인했다. 저장소 설명에 따르면 Antigravity와 Cursor 어댑터는 공식 연동 기능이 아닌 독자 구현이며 특정 버전에 고정돼 있다. 각 이전 경로의 실제 호환성과 장기적인 안정성, 운영체제 지원 확대 여부는 이번 자료만으로 확인할 수 없다.

## 출처

- [github.com](https://github.com/xhluca/session-migrate)
