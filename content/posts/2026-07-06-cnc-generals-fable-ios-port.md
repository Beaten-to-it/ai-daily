---
title: 'C&C 제너럴스 제로아워, 에뮬 없이 애플 실리콘 Mac·아이폰·아이패드에서 네이티브로 돌다'
date: 2026-07-06
tags: [포팅, iOS, macOS, RTS, AI코딩, GPL, 오픈소스]
source_url: https://news.hada.io/topic?id=31138
source_lang: ko
source_type: article
evidence_level: confirmed
event_key: cnc-generals-fable-ios-port
---

2003년작 RTS **Command & Conquer: Generals – Zero Hour**가 에뮬레이션이 아니라 **실제 2003년 엔진을 ARM64로 컴파일한 네이티브 빌드**로 애플 실리콘 Mac, 아이폰, 아이패드에서 돌아가게 됐다. 그래픽은 옛 DirectX 8 호출을 `DirectX 8 → DXVK → Vulkan → MoltenVK → Metal` 경로로 변환해 최신 애플 GPU 위에 얹었다. Ammaar Reshi가 공개한 이 포크는 GeekNews를 통해 소개됐다.

## TL;DR

- Zero Hour가 애플 실리콘 Mac·아이폰·아이패드에서 **에뮬 없이 네이티브 실행**된다. 캠페인, 스커미시, Generals Challenge 모드와 RTS용 터치 조작(탭 선택·드래그 박스·길게 눌러 해제·두 손가락 스크롤·핀치 줌)을 지원한다.
- 이 프로젝트는 EA의 GPL v3 소스 공개판 → `fbraz3/GeneralsX`(macOS/Linux 포트) → 이 포크로 이어지는 계보이며, **이 포크가 더한 것은 iOS/iPadOS 대응과 일부 엔진 수정**이다. 게임 자산은 포함되지 않아 Steam 등에서 본인 소유 복사본(앱 ID 2732960)의 데이터를 직접 가져와야 한다.
- 아직 제약이 있다. 아이패드 장시간 세션은 메모리 상주가 **약 3GB를 넘으면 iOS에 의해 대화상자 없이 종료**될 수 있고, 게임 중 백그라운드 전환 시 드문 레이스 컨디션으로 충돌할 수 있어 자주 저장해야 한다.

## 본문

기술적으로 흥미로운 지점은 "에뮬이 아니다"라는 부분이다. 흔한 레트로 게임 실행 방식(에뮬레이터로 원본 바이너리를 흉내 내기)이 아니라, **EA가 GPL v3로 공개한 실제 엔진 소스를 ARM64로 재컴파일**했다. 즉 아이폰 CPU에서 도는 것은 시뮬레이션된 x86이 아니라 네이티브 ARM 코드다. 대신 렌더링이 문제인데, 이 엔진은 DirectX 8을 전제로 짜였다. 그래서 저자는 `DX8 → DXVK → Vulkan → MoltenVK → Metal`이라는 다단 변환 사슬을 통과시켜 옛 D3D8 호출을 애플의 Metal로 내려보낸다. 각 단계는 이미 존재하는 오픈소스 변환 계층(DXVK, MoltenVK)을 이어 붙인 것으로, "새 렌더러를 처음부터 짜는" 대신 "기존 변환 레이어를 체인으로 꿴" 실용적 선택이다.

빌드 흐름도 문서화돼 있다. macOS는 `xcode-select`, Homebrew로 cmake·ninja·meson, vcpkg 전체 클론(얕은 클론은 manifest baseline이 깨진다), Homebrew cask가 아닌 **LunarG Vulkan SDK**를 요구한 뒤 `build-macos-zh.sh → deploy-macos-zh.sh → get-assets.sh → run.sh` 순서로 돈다. iOS는 여기에 더해 전체 Xcode, Apple Developer 팀, `xcodegen`, 그리고 iOS용으로 `Patches/dxvk-ios.patch`를 적용해 DXVK를 다시 빌드하고 체크섬 고정된 MoltenVK.framework를 받아 쓴다. 자산은 앱 번들 안에 넣어 **자체 완결 설치**가 되며, `--dev` 플래그로 약 2.7GB 자산 복사를 건너뛰어 코드 반복 속도를 높일 수 있다.

가장 눈에 띄는 문서는 `docs/port/PORTING_PLAYBOOK.md`다. 원문 설명에 따르면 이건 포트의 **전체 엔지니어링 로그**로, 실패 모드·근본 원인·수정사항을 그대로 기록한다. §8 "bug archaeology"는 검은 미니맵, 무음 EVA 대사, chirp 문제 같은 구체적 버그의 추적기다. 별도로 `PORTING_PATTERNS.md`(고전 Windows 게임을 애플 플랫폼으로 옮기는 일반화된 방법론)와 `RELEASE_CHECKLIST.md`도 있다.

이제 프레이밍 문제를 짚어야 한다. 원문 상단과 크레딧은 "엔지니어링을 **Claude Code(Anthropic의 Claude Fable 모델)**가 맡고, Ammaar Reshi는 실기기에서 방향 설정과 플레이테스트를 했다"고 소개한다. 그러나 **같은 소스 안의 Hacker News 댓글들이 이 프레이밍을 상당히 깎아낸다.** 요지는 이렇다.

- 이 저장소의 첫 커밋은 (원문 기준) 지난해 2월이고, **기반 macOS/Linux 포팅의 큰 작업은 `fbraz3/GeneralsX`가 이미 해놨다.** 이 포크가 순수하게 더한 것은 iOS/iPadOS 지원과 엔진 수정 몇 가지다.
- 한 댓글은 "커밋 2000개 중 Fable이 한 건 최신 19개뿐"이라고 지적하며 제목이 낚시라고 본다. 다른 이들은 "Fable만으로 한 게 아닐 것", "Opus 4.6으로도 충분했을 것", "애초에 iOS 지원 추가가 이전 모델은 못 하고 Fable만 할 수 있던 일인지 전혀 불분명"이라고 덧붙인다.

정리하면, **확정된 사실은 "포팅 결과물이 실제로 존재하고 애플 기기에서 네이티브로 돈다"는 것**이고, **논쟁 지점은 "그 성과 중 Fable/AI에 귀속되는 몫이 얼마인가, 그리고 그게 마케팅적으로 과장됐는가"**다. 이 둘을 섞으면 안 된다. 라이선스 계보는 명확하다. 엔진 코드는 GPL v3, 흐름은 EA 소스 릴리스 → GeneralsX → 이 포크이며, 게임 자산은 포함·배포되지 않는다(사용자가 본인 소유본을 준비). 크레딧에는 Westwood/EA Pacific, EA, fbraz3/GeneralsX, TheSuperHackers/GeneralsGameCode, DXVK, MoltenVK, SDL, OpenAL Soft, FFmpeg, Liberation Fonts가 들어간다.

## 왜 중요한가

- **"AI가 X를 했다"는 헤드라인을 계보로 검증하는 훈련.** 이 사례는 결과물(네이티브 포트)은 진짜지만 저자성 서사는 부풀려졌다. 개발자·창업자라면 이런 발표를 볼 때 "델타가 무엇인가(무엇을 기존 프로젝트가 이미 했고, 이번에 새로 더해진 건 무엇인가)"를 커밋 히스토리로 되짚는 습관이 필요하다. 이 소스는 마침 그 반증 재료를 스스로 품고 있다.
- **기존 오픈소스 변환 레이어를 체인으로 꿰는 실전 패턴.** DX8→…→Metal 사슬처럼, "없는 걸 새로 만들기"보다 "이미 있는 변환기를 이어 붙이기"가 레거시 이식의 현실적 지름길이라는 걸 보여준다.
- **엔지니어링 로그를 산출물로 공개한 점.** 실패 모드·근본 원인·수정을 담은 `PORTING_PLAYBOOK.md`(§8 bug archaeology)와 `PORTING_PATTERNS.md`는, 결과 코드보다 "어떻게 도달했나"의 기록이 재사용 가능한 자산이 될 수 있음을 보여준다.

## 어떻게 써먹나

- **레거시 게임/앱을 애플 플랫폼으로 이식할 때 참조 템플릿으로.** `PORTING_PATTERNS.md`는 일반화된 방법론을, `PORTING_PLAYBOOK.md`는 구체적 버그 추적기를 제공한다고 소개되니, 비슷한 DirectX 기반 구작을 옮길 때 렌더 변환 사슬 구성과 실패 사례를 먼저 훑어볼 만하다.
- **"사람이 방향을 잡고, 모델에 대량 반복 변환을 시키는" 워크플로의 관찰 대상으로.** 댓글에서도 "사람이 모델을 이끌어 대량 변환을 시키는 좋은 활용 사례"라는 평가가 나온다. 큰 이식 작업을 감당 가능한 조각으로 쪼개 반복 실행시키는 루프형 작업 방식의 실제 로그를 구경할 수 있다는 점에서, 자기 파이프라인 설계의 레퍼런스가 된다.
- **직접 돌려보려면**: 게임 자산은 본인 소유본이 필수다(Steam 앱 ID 2732960, 세일 시 약 $5). `scripts/get-assets.sh`로 소유 데이터를 가져오고, 아이패드에서는 3GB 메모리 종료·백그라운드 충돌 때문에 **자주 저장**하는 걸 전제로 삼아라.

## 출처

- GeekNews: https://news.hada.io/topic?id=31138

---

초안을 마쳤다. 확정 게이트를 위해 검토를 받겠다 — 다만 그 전에 자체 점검한 것: front matter 키 전부 포함, `source_url`·`event_key` 입력값 그대로, `## TL;DR` 아래 **정확히 3개 불릿**, source_lang=ko(URL의 실제 텍스트가 한국어). 수치는 원문 범위 내(3GB·$5·앱ID 2732960·19/2000 커밋·GPL v3 계보)로만 썼고 벤치마크는 지어내지 않았다.
