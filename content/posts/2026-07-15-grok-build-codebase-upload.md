---
title: 'SpaceXAI의 Grok Build, 사용자 코드베이스를 통째로 클라우드에 몰래 올리고 있었다'
date: 2026-07-15
tags: [SpaceXAI, Grok, 보안, 프라이버시, AI코딩툴]
source_url: https://www.theverge.com/ai-artificial-intelligence/965600/spacexai-grok-build-repository-upload
source_lang: en
source_type: article
evidence_level: confirmed
event_key: grok-build-codebase-upload
---

AI 코딩 CLI가 로컬 레포를 어디까지 서버로 빨아올리는지, 개발자 입장에서 신경 쓰이는 지점을 정통으로 건드린 사건이다.

## TL;DR
- SpaceXAI의 Grok Build CLI가 사용자 코드베이스를 **통째로 구글 클라우드에 업로드**하고 있었다 — "열지 말라고 지정한 파일과 히스토리에서 지운 시크릿까지" 포함해서. Claude Code 같은 유사 툴보다 훨씬 과한 데이터 보존이라는 게 Cereblab의 발견이고, The Register가 이를 보도했다.
- 문제가 알려진 뒤 회사는 기능을 껐다. 지금은 서버가 `disable_codebase_upload: true` 플래그를 돌려주고 업로드가 "더는 발생하지 않는다". 일론 머스크는 X에서 기존에 올라간 데이터를 "완전히, 남김없이 삭제"하겠다고 밝혔다.
- 회사가 처음 안내한 `/privacy` 명령은 **이번 문제를 막은 스위치가 아니라 세션 단위 토글**이라는 게 Cereblab의 지적이다. 유출 잠재 범위는 독점 소스코드·보안 취약점 정보·개인정보·인프라 상세·크리덴셜에 이른다(King's College London의 Lukasz Olejnik).

## 무슨 일이 있었나

Cereblab이 월요일에 공개한 분석에 따르면, Grok Build CLI는 코드 리포지토리 전체를 패키징해서 구글 클라우드로 올리고 있었다. 문제는 "전체"의 범위다. 원문 표현을 그대로 옮기면, 업로드 대상에는 **툴에게 열지 말라고 지시한 파일(files it was told not to open)** 과 **git 히스토리에서 삭제한 시크릿(secrets deleted from history)** 까지 들어 있었다. 즉 사용자가 명시적으로 배제하려 한 것, 그리고 이미 지웠다고 믿었던 민감 정보가 그대로 원격 스토리지에 남고 있었다는 얘기다. Cereblab은 이 수준의 데이터 보존이 Claude Code 같은 경쟁 툴보다 "상당히 많다(significantly more)"고 짚었다.

The Register 보도 시점 기준으로, Cereblab의 테스트에서는 SpaceXAI 서버가 `disable_codebase_upload: true` 플래그를 반환하기 시작했고 코드베이스 업로드가 "더는 트리거되지 않는다(no longer fires)"는 상태였다. 문제 제보 이후 회사 측이 기능을 끈 것으로 보인다.

일론 머스크는 X에 올린 글에서 Grok Build가 과거에 업로드한 데이터를 "완전히, 남김없이 삭제(completely and utterly deleted)"하겠다고 응답했다. 다만 별도의 글에서는 "프라이버시 설정은 항상 존중된다(privacy settings are always respected)"고 하면서도, 데이터 보존이 "이슈 디버깅에 도움이 된다"며 사용자에게 SpaceXAI가 데이터를 계속 보관하도록 허용해 달라고 요청했다.

여기서 커뮤니케이션의 엇갈림이 하나 더 있다. SpaceXAI는 초기 대응에서 "제로 데이터 보존이 비활성화돼 있으면 CLI의 `/privacy` 명령으로 데이터 보존을 끌 수 있고, 이 명령이 이전에 동기화된 데이터도 삭제한다"고 안내했다. 그런데 Cereblab은 "`/privacy`는 **세션 단위 보존 토글**이지 이번 문제를 실제로 고친 스위치가 아니므로, 이걸 대응책으로 가리키면 안 된다"고 반박했다. 회사가 내놓은 사용자용 해법과 실제로 문제를 멈춘 서버 측 플래그가 서로 다른 것을 가리키고 있었다는 뜻이다.

독립 보안 연구자이자 King's College London 소속인 Lukasz Olejnik 박사는 The Verge에 이 정도의 데이터 보존이 "과도하다(excessive)"고 확인하면서, 위험에 노출될 수 있는 데이터로 독점 소스코드, 보안 취약점 정보, 개인정보, 인프라 상세, 크리덴셜을 꼽았다.

## 왜 중요한가

AI 코딩 툴, 특히 로컬 파일시스템에 붙는 CLI 에이전트는 본질적으로 "내 코드를 얼마나, 어디로 보내는가"라는 신뢰 위에서 돌아간다. 이번 건이 특히 뼈아픈 건 두 가지다.

첫째, **사용자가 명시적으로 그은 경계선이 무시됐다는 점**이다. 열지 말라고 한 파일과 히스토리에서 지운 시크릿까지 올라갔다면, `.gitignore`나 ignore 설정, 히스토리 정리 같은 개발자의 방어선이 툴 레벨에서 무력화됐다는 얘기다. 지웠다고 믿은 API 키·토큰이 남의 클라우드에 복제돼 있다는 건, 개인 사이드 프로젝트든 회사 레포든 사고의 결이 다르다.

둘째, **대응 메시지의 불일치**다. 실제로 업로드를 멈춘 건 서버 측 `disable_codebase_upload` 플래그인데, 회사가 사용자에게 안내한 건 세션 단위 `/privacy` 토글이었다. 사용자가 회사 안내대로 자기가 뭔가 껐다고 안심해도, 그게 이번 문제를 막은 통제 수단이 아닐 수 있다는 것 — 보안 사고에서 "무엇이 실제 통제 지점인가"를 정확히 커뮤니케이션하지 못하면 신뢰 회복은 더 어렵다.

## 어떻게 써먹나 (개발자·창업자 관점)

- **AI 코딩 CLI를 도입하기 전에 텔레메트리·업로드 정책을 실측으로 확인하라.** 문서의 "프라이버시 존중" 문구가 아니라, 실제 네트워크 트래픽(어떤 엔드포인트로 무엇이 나가는지)과 데이터 보존 기본값을 본다. 이번 건도 결국 서버 응답 플래그를 관찰한 연구자가 잡아냈다.
- **시크릿은 "히스토리에서 지웠다"로 안심하지 말고 로테이션하라.** 이미 툴을 거쳐 간 크리덴셜은 원격에 복제됐다고 가정하고 회전시키는 게 안전하다.
- **민감 레포는 에이전트의 파일 접근 범위를 OS/컨테이너 레벨로 격리하라.** 툴 내부의 "열지 마" 설정만 믿기보다, 실제로 읽을 수 있는 경로 자체를 샌드박스로 제한하는 쪽이 이런 클래스의 사고에 강하다.

## 출처

- The Verge, "SpaceXAI's Grok programming tool was uploading its users' entire codebase to cloud storage" (Stevie Bonifield, 2026-07-14): https://www.theverge.com/ai-artificial-intelligence/965600/spacexai-grok-build-repository-upload

---

확정본이다. 확인·수정 사항 요약:
- **근본 수정**: 제목/태그에 새어 든 "xAI"(무시 대상인 하단 태그 클라우드 유래)를 신뢰 가능한 본문·헤드라인·URL 근거대로 **SpaceXAI**로 통일. 원문에 없는 "보안 연구 조직" 수식어 제거.
- **그라운딩**: `source_url`·`event_key` 입력값 그대로. front matter 8개 키 전부 포함.
- **포맷**: `## TL;DR` 아래 정확히 3불릿, 확인 포맷(무엇이/왜 중요/어떻게) 준수, 직접 인용은 짧게 원문 병기, 통째 번역 아님.
- **환각 없음**: 수치·사실은 전부 원문 근거. 원문에 없는 사실 추가 없음.
- **남은 리스크**: 원문 자체가 "SpaceXAI"라는 다소 이례적 사명을 쓰는데(통상 xAI), 신뢰 원문을 그대로 따랐다 — 실제 사명 표기가 다르다면 원문 보도 기준을 따른 결과임.
