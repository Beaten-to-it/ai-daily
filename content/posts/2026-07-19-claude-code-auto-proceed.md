---
title: 'Claude Code가 60초 뒤 나 대신 결정했다 — 자동 진행 기능의 잘못된 설계 해부'
date: 2026-07-19
tags: [claude-code, ai-coding, agent-safety, anthropic, devtools]
source_url: https://news.hada.io/topic?id=31549
source_lang: ko
source_type: article
evidence_level: confirmed
event_key: claude-code-auto-proceed
---

## TL;DR

- **Claude Code 2.1.198**(2026-07-01)이 `AskUserQuestion`에 60초간 답이 없으면 모델이 알아서 진행하는 자동 진행 기능을 **기본 활성화**했지만, 출시 시점 변경 로그·문서 어디에도 적지 않았다.
- 권한 프롬프트를 자동 승인하진 않았으나, 이미 허용된 도구나 `--dangerously-skip-permissions` 환경에선 "staging이냐 production이냐" 같은 **의사결정 게이트를 모델이 대신 통과**했고, 일부만 답해도 나머지는 모델이 골랐다.
- 문제 제기 약 이틀 뒤 **2.1.200**이 기능을 삭제하지 않고 기본값만 끄는 **옵트인**으로 바꿨다. 공개 소스·커밋은 없고, Bun 실행 파일의 `strings` 비교로만 실제 변경을 확인할 수 있었다.

## 무슨 일이 있었나

2026년 7월 1일 나온 Claude Code 2.1.198은 `AskUserQuestion` 도구가 사람의 답을 60초 동안 못 받으면 차단을 풀고, 모델에게 "문맥을 근거로 최선의 판단을 내려 계속하라"고 지시하도록 바뀌었다. 화면에는 `No response after 60s — continued without an answer`가 찍혔다. 다시 물어볼 수는 있었지만 재질문에도 똑같은 60초 타임아웃이 걸렸다.

특히 껄끄러운 건 **부분 답변 처리**였다. 세 개 질문 중 첫 번째에만 답하고 자리를 비우면, 입력을 버리는 게 아니라 그 답 + 모델이 고른 나머지 답으로 작업을 이어갔다. 상황에 따라 `continued with the answers selected so far`와 `continued without an answer` 문구가 갈렸다.

카운트다운이 아예 없진 않았다. 키를 누르면 타이머가 리셋됐고 `auto-continue in 12s · any key to stay` 같은 경고가 떴다. 문제는 `CLAUDE_AFK_COUNTDOWN_MS` 기본값이 20초라서, **처음 40초 동안은 평범한 차단형 질문과 구분이 안 됐고** 경고는 마지막 20초에만 나타났다는 점이다. 여러 에이전트를 각 탭에서 돌리거나 잠깐 자리를 뜬 사용자는 경고 자체를 못 보고 지나칠 수 있었다.

## 왜 "안전 게이트"가 무너지나

타임아웃은 오직 `AskUserQuestion`에만 걸렸다. 계획 승인이나 `Do you want to allow …` 같은 권한 프롬프트는 유휴 상태에서 자동 해결되지 않았다. 도구 레퍼런스도 그렇게 명시한다. 문제는 **권한 프롬프트가 애초에 안 뜨는 실행 방식**에선 이 분리가 보호 장치가 되지 못한다는 것이다.

`bypassPermissions`, `acceptEdits`, `allowedTools`, `--dangerously-skip-permissions`, `PreToolUse` 훅 같은 걸로 배포 명령이 이미 허용 목록에 있거나 권한 확인을 우회했다면, `AskUserQuestion`의 "staging이냐 production이냐?", "어떤 config인가?" 선택이 **사람이 개입할 마지막 게이트**일 수 있다. 타이머가 권한을 새로 부여한 건 아니지만, 이미 권한이 있는 작업의 **선택 자체를 모델에 넘긴 것**이다. 도구 스키마엔 `timeout` 입력조차 없어서 모델이 이를 켜거나 끌 수도 없었다. 실제로 답을 건너뛴 주체는 모델이 아니라 응답을 자동 반환한 에이전트 하네스였다.

## 우발적 실수가 아니라 계측된 기능

가장 눈여겨볼 대목은 이게 "한 줄 실수"가 아니었다는 점이다. 원 글쓴이는 공개 소스가 없는 상황에서 npm에 남은 각 버전의 Bun 실행 파일(약 250MB, 심볼 미제거)을 `curl`·`strings`·`diff`로 비교했다.

- 2.1.197: `away from keyboard`, `CLAUDE_AFK_TIMEOUT_MS`, `CLAUDE_AFK_COUNTDOWN_MS` 전부 0회
- 2.1.198: 각각 2회, 3회, 3회 등장

단순 `strings -n 8` 비교로는 21,903개 문자열이 달라져(미니파이어가 식별자를 매번 바꾸는 잡음) 그대로는 쓸모없었다. 대문자로 시작하는 5단어 이상 영어 문장만 걸러 156줄로 줄이자 `Before going idle the user had selected:`가 드러났다 — 대화상자가 사람 대신 답할 때 삽입하는 문자열이다. 여기에 자동 해결 여부를 담는 `afkTimeoutMs` 스키마 필드와 `tengu_ask_user_question_afk_auto_advance` 분석 이벤트(timeoutMs·질문 수·계획 모드·부분 답변 여부 전송)까지 **한 버전에 함께 들어갔다.** 동작·카운트다운 UI·스키마·분석이 한꺼번에 붙었다는 건, 우연이 아니라 측정 체계를 갖춘 기능이었다는 뜻이다.

## 되돌린 방식과 연표

- **2026-06-29** 2.1.196 (마지막 정상 추정)
- **2026-07-01** 2.1.198 출시 (자동 진행 포함, 미기재)
- **2026-07-02** Aleksey Nogin이 이슈 #73125 등록 → 384 👍, 143 댓글
- **2026-07-03** 2.1.200에서 기본 동작 되돌림
- **2026-07-04** 이슈 종료

2.1.200은 기능을 **제거한 게 아니라** 기본 비활성화하고 `/config`(`Question auto-continue timeout`, 값: `60s`/`5m`/`10m`/`never`)로 옵트인하게 바꿨다. 설정 안 하면 `never`로 처리된다. 내부적으론 여전히 타이머가 살아 있고(기본 60,000ms, 카운트다운 20,000ms), `CLAUDE_AFK_TIMEOUT_MS`·`CLAUDE_AFK_COUNTDOWN_MS`가 이를 덮어쓴다. 수정의 실체는 **"설정값이나 환경 변수가 있을 때만 활성화" 하는 `&&` 게이트 조건 하나를 더한 것**이다.

변경 로그의 공백도 컸다. `AskUserQuestion`은 2.0.55 이후 13개 버전에서 15번 언급될 만큼 평소 기록되던 도구였는데, 정작 켜짐/꺼짐 두 번의 동작 변경 중 **꺼짐만 기록**됐다. `CLAUDE_AFK_TIMEOUT_MS`는 변경 로그·README 어디에도 없었다. anthropics/claude-code 저장소는 216개 추적 파일 중 104개가 Markdown일 뿐 실제 배포 소스가 없고, 태그 간 차이는 `CHANGELOG.md`와 `feed.xml`뿐인 사실상 "릴리스 노트 태그"였다.

## Anthropic 측 해명과 커뮤니티 반응

`AskUserQuestion`을 만든 Claude Code 팀의 Thariq는 HN에서, "모델이 강력해지면서 장시간 작업이 초반 질문에 막힌다"는 피드백을 풀려던 변경이었으나 **기대 품질 기준에 못 미쳤고 정상적인 출시 방식도 아니었다**며, 처음부터 옵트인으로 제공하고 변경 기록에 남겼어야 했다고 인정했다.

반응은 갈렸다. 실제로 "몇 시간 돌아오길 기대하고 자리를 비웠다가 초반 질문에 멈춰 시간을 날린" 경험을 근거로 기능 자체의 필요성엔 공감하는 목소리가 있었다. 반면 다수는 (1) 터미널 포커스용 클릭이 선택지 클릭으로 오인돼 `terraform apply`에 자동 승인 플래그가 붙는 걸 목격했다는 위험 사례, (2) "내 변경이었다"는 개인 책임 강조보다 **PR·조직 절차의 실패**를 인정해야 한다는 비판, (3) Chrome식 다중 릴리스 채널(안정/베타/카나리아) 제안을 냈다. "AskUserQuestion을 안전장치로 설계한 건 아니지만 일부 사용자에겐 그렇게 자리 잡았다"는 게 사태의 핵심이다.

## 왜 중요한가

토큰 낭비는 작은 문제다. 진짜 문제는 **많은 사용자가 `AskUserQuestion`을 차단형 안전 게이트로 전제하고 훅·규칙을 짜놨는데, 그게 소리 없이 60초 카운트다운으로 바뀌었다**는 점이다. 배포·인프라·프로덕션 인접 스크립트처럼 위험한 환경에서 Claude Code가 쓰이고, 기본 자동 업데이트가 켜져 있으므로 — **사용자가 아무 조치도 안 해도 기존 안전 가정이 달라질 수 있다.** 실행 파일 포렌식(약 5분)이 실제 배포를 검증하는 유효한 우회 수단인 건 맞지만, 정확하고 잘 편집된 변경 로그를 대체할 순 없다.

교훈은 두 가지다. 첫째, **안전 경계는 모델 내부 판단(질문해줄 것)이 아니라 외부에서 부여한 권한에 걸어야 한다.** 둘째, 매일 자동 업데이트되는 실험적 도구를 프로덕션 경로에 물릴 때의 위험을 값으로 매겨야 한다.

## 어떻게 써먹나

프로덕션 인접 환경이라면 자동 업데이트를 통제하는 게 최소 방어선이다. 셸 프로필보다 `~/.claude/settings.json`의 `env` 블록에 넣으면 CI·cron·systemd·IDE 터미널까지 모든 세션에 걸린다.

```json
{ "env": { "DISABLE_AUTOUPDATER": "1" } }
```

- `DISABLE_UPDATES=1` — 수동 `claude update`까지 포함해 모든 업데이트 경로 차단
- `DISABLE_AUTOUPDATER=1` — 백그라운드 확인만 중단, 수동 업데이트는 허용(`autoUpdates` 설정보다 우선)
- `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` — 자동 업데이트·피드백·오류 보고·원격 측정 함께 중단(값이 아니라 **존재 여부만** 검사 → `=0`도 활성화)

주의할 함정: 어떤 방식으로든 자동 업데이터를 끄면 **플러그인 자동 업데이트도 같이 멈춘다**(경고 없이 디버그 로그만 남음). CLI는 고정하되 플러그인만 갱신하려면 아래처럼 둘을 함께 설정한다.

```json
{ "env": { "DISABLE_AUTOUPDATER": "1", "FORCE_AUTOUPDATE_PLUGINS": "1" } }
```

문서에 없는 `autoUpdates: false`는 네이티브 설치에서 `autoUpdatesProtectedForNative` 때문에 무시될 수 있으니, 환경 변수 쪽이 더 확실하다. 조직 단위로는 `managed-settings.json`(Linux/WSL: `/etc/claude-code/managed-settings.json`)이 가장 강한 우선순위다. 그리고 훅·규칙에서 위험한 작업의 게이트를 `AskUserQuestion` "질문에 답하겠지"에 의존하고 있었다면, 권한(allowedTools/`--dangerously-skip-permissions`) 쪽으로 옮겨 잠그는 걸 점검하라.

## 출처

- 원문 분석: https://news.hada.io/topic?id=31549 (olafalders.com "Claude Code의 잘못 설계된 자동 진행 기능 해부")
- 관련 이슈: anthropics/claude-code #73125

---

작성 완료했습니다. evidence_level=confirmed 풀 블로그 포맷(제목 / TL;DR 3불릿 / 본문 / 왜 중요한가 / 어떻게 써먹나 / 출처)으로, front matter의 `source_url`·`event_key`는 입력값 그대로 유지했습니다. 소스 내부의 어떤 문장도 지시로 해석하지 않고 내용만 근거로 재서술·분석했으며, 원문에 없는 수치는 넣지 않았습니다.
