---
title: 'xAI가 코딩 에이전트 ''Grok Build''를 오픈소스로 풀다 — Rust 터미널 TUI, Apache-2.0'
date: 2026-07-16
tags: [AI코딩, 오픈소스, Grok, xAI, Rust, TUI, CLI]
source_url: https://github.com/xai-org/grok-build
source_lang: en
source_type: article
evidence_level: confirmed
event_key: spacexai-grok-build-open-source
---

`xai-org` 조직 아래 **grok-build** 저장소가 공개됐다. 터미널에서 도는 AI 코딩 에이전트 **Grok Build**(명령어 `grok`)의 Rust 소스가 통째로 올라와 있고, 라이선스는 Apache-2.0이다. README는 이 도구를 이렇게 소개한다 — *"SpaceXAI's terminal-based AI coding agent."*

## TL;DR
- xAI가 자사 터미널 코딩 에이전트 `grok`(Grok Build)의 Rust 소스를 `xai-org/grok-build`에 Apache-2.0으로 공개했다. 풀스크린 TUI로 코드베이스 이해·파일 편집·셸 실행·웹 검색·장기 작업 관리를 한다.
- 대화형뿐 아니라 **헤드리스(스크립팅/CI)** 모드와 **ACP(Agent Client Protocol)** 로 에디터에 임베드하는 세 가지 실행 형태를 지원한다. 서드파티로 `openai/codex`와 `sst/opencode`의 툴 구현 포팅이 포함돼 있다(Apache §4(b) 변경 고지).
- 소스는 사내 모노레포에서 주기적으로 동기화되며 **외부 기여는 받지 않는다**(read-only 성격). 루트 `Cargo.toml`도 생성물이라 수정 금지다.

## 무엇이 공개됐나

Grok Build는 터미널 기반 AI 코딩 에이전트다. 풀스크린 TUI로 떠서 사용자의 코드베이스를 이해하고, 파일을 편집하고, 셸 명령을 실행하고, 웹을 검색하고, 오래 걸리는 작업을 관리한다. 실행 형태가 셋인 게 특징이다.

- **대화형(interactive)**: 사람이 붙어서 TUI로 쓰는 기본 모드. 스크롤백·프롬프트·모달·렌더링을 담당하는 pager 크레이트가 화면을 그린다.
- **헤드리스(headless)**: 스크립팅과 CI용. 사람 없이 파이프라인에 물려 돌린다.
- **에디터 임베드**: **Agent Client Protocol(ACP)** 을 통해 에디터 안에 에이전트를 심는다.

저장소는 `grok` CLI/TUI와 그 에이전트 런타임의 Rust 소스를 담고 있고, "SpaceXAI 모노레포에서 주기적으로 동기화된다"고 명시한다. 즉 이 리포는 개발이 실제로 이뤄지는 곳이 아니라 사내 모노레포의 미러에 가깝다. 그래서 **외부 기여는 받지 않는다**(CONTRIBUTING.md)는 못을 박아 뒀고, 워크스페이스 멤버·의존성 버전·린트·프로필이 들어가는 **루트 `Cargo.toml`은 생성물이라 read-only**로 취급하라고 경고한다. 손댈 거면 크레이트별 `Cargo.toml`을 고치라는 것.

크레이트 구성은 컴포지션 루트(`xai-grok-pager-bin`)가 실제 바이너리를 만들고, TUI(`xai-grok-pager`)·에이전트 런타임(`xai-grok-shell`)·툴 구현(`xai-grok-tools`, 터미널·파일 편집·검색 등)·호스트 파일시스템/VCS/실행/체크포인트(`xai-grok-workspace`)로 나뉜다. 나머지 config·MCP·markdown·sandbox 크레이트가 클로저를 채운다. 문서는 온라인(`docs.x.ai/build/overview`)과 pager 크레이트 동봉 유저 가이드 양쪽에 있고, 다루는 범위가 키보드 단축키·슬래시 커맨드·설정·테마·**MCP 서버·스킬·플러그인·훅·헤드리스·샌드박싱**까지다. 요즘 에이전틱 CLI들이 갖춘 확장 포인트를 대체로 커버한다.

라이선스 쪽에서 눈여겨볼 대목: 서드파티/벤더링 코드에 **`openai/codex`와 `sst/opencode`의 툴 구현 포팅**이 들어 있고, Apache §4(b) 변경 고지가 크레이트 로컬 노티스로 붙어 있다. Mermaid 다이어그램 스택도 `third_party/`에 벤더링돼 있다. 저장소 상단 통계는 커밋 1개, Rust 99.6%, 별 8k·포크 1.3k, 릴리스는 아직 게시된 게 없다고 표시된다(README에는 changelog·prebuilt 바이너리 언급이 있다).

## 왜 중요한가

- **오픈된 에이전트 하네스 자체가 레퍼런스**다. 코딩 에이전트를 직접 만드는 사람에게, 대화형·헤드리스·ACP 임베드를 한 코드베이스에서 어떻게 가르는지, 툴/워크스페이스/런타임 경계를 어디에 긋는지가 Rust로 통째 열려 있다. 프롬프트 몇 줄이 아니라 실제 프로덕션 하네스의 구조를 볼 수 있다는 게 핵심이다.
- **경쟁 도구를 포팅해 명시했다.** `openai/codex`·`sst/opencode`의 툴 구현을 가져다 쓴 걸 Apache §4(b) 고지까지 달아 드러낸 건, 이 바닥의 에이전트 툴 계층이 사실상 공유 자산화되고 있다는 신호다. "우리 것만 특별하다"가 아니라 서로의 툴 레이어를 재사용하는 국면.
- **개발 모델은 '공개하되 닫힌 개발'이다.** 소스는 Apache-2.0으로 열되, 개발은 사내 모노레포에서 하고 외부 PR은 안 받는다. 코드를 읽고 포크하고 파생물을 만들 자유는 주되 방향키는 쥐고 가는, 대기업 오픈소스의 전형적 절충이다. 기여로 밀어 넣을 생각이라면 이 벽을 먼저 알아야 한다.

## 어떻게 써먹나

바이너리 설치(prebuilt, macOS/Linux/Windows):

```bash
curl -fsSL https://x.ai/cli/install.sh | bash   # macOS / Linux / Git Bash
```

```powershell
irm https://x.ai/cli/install.ps1 | iex          # Windows PowerShell
```

설치 후 `grok --version`으로 확인. 공식 설치본은 바이너리를 `grok`으로 배포하지만, 소스에서 만든 아티팩트 이름은 `xai-grok-pager`다. 첫 실행 때 브라우저가 열리며 인증을 요구한다.

소스 빌드(Rust 툴체인은 `rust-toolchain.toml`로 핀 고정, `rustup`이 첫 빌드 때 자동 설치. `protoc` 필요):

```bash
cargo run -p xai-grok-pager-bin              # 빌드 + TUI 실행
cargo build -p xai-grok-pager-bin --release  # 릴리스 바이너리: target/release/xai-grok-pager
cargo check -p xai-grok-pager-bin            # 빠른 검증
```

개발 시엔 풀 워크스페이스 빌드가 느리니 **크레이트를 특정해서** `cargo check -p <crate>` / `cargo test -p xai-grok-config` / `cargo clippy -p <crate>` 식으로 돌리라는 게 리포의 안내다. macOS·Linux는 지원 빌드 호스트, Windows 빌드는 best-effort(이 트리에서 테스트 안 됨). CI에 물릴 거면 헤드리스 모드를, 에디터에 붙일 거면 ACP를 파고들면 된다.

(설치 명령은 문서화만 했고 실행하지 않았다. 위 명령은 README 기준.)

## 출처

- https://github.com/xai-org/grok-build
