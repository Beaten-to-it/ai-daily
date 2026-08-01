# Windows Codex 게시자 운영 가이드

## 현재 확인 상태

2026-08-02 KST의 이 작업 폴더 `C:\projects\DailyReport` 기준입니다.

| 항목 | 확인 결과 |
|---|---|
| Python | 3.13.13 |
| Codex CLI | 0.144.1 |
| Codex 인증 | `Logged in using ChatGPT`, 종료 코드 0 |
| Git | 2.54.0.windows.1 |
| Windows PowerShell | 5.1.26100.8875 |
| Windows 시간대 | Korea Standard Time |
| Hugo | Extended 0.164.0 설치 완료 |
| `AI Daily *` 예약 작업 | 0개 |

Hugo Extended와 PaperMod 서브모듈을 준비했다. 아래 두 명령이 모두 성공해야 한다.

```powershell
Get-Command hugo -ErrorAction Stop
hugo version  # extended 포함, 0.163.3 이상
```

2026-08-02 전환에서는 사용자 지시로 3~5일 연속 섀도 운영만 생략한다. 이를 실제 전체 콘텐츠 Hugo 렌더, RSS 경로 검사, 수동 Prepare/Publish 검증으로 대체한다.

## 운영 전제

- 지원 셸은 예약 작업이 사용하는 Windows PowerShell 5.1 `powershell.exe`다. `run_daily.ps1`은 PowerShell 7의 native-command 오류 동작도 보정한다.
- 예약 시간과 날짜 계약은 KST다. 설치 스크립트는 다른 Windows 시간대에서 실패한다.
- 예약 작업은 현재 사용자 `Interactive` 토큰을 사용하므로 사용자가 로그오프한 동안 실행되지 않는다. 06시·07시·12시 실행 시 Windows 로그인 상태가 유지되어야 한다.
- Codex와 Git 자격증명은 현재 사용자 프로필에서 접근 가능해야 한다.
- Google OAuth 토큰과 이메일 원장은 `%LOCALAPPDATA%\ai-daily` 아래에 두며 저장소에 넣지 않는다.
- 기존 WSL timer는 Windows 전환 승인과 첫 게시 확인 전까지 변경하지 않는다.
- 준비 체크포인트는 `hugo.toml`, `layouts/`, `themes/`와 네 콘텐츠 섹션 인덱스가 Git 기준으로 깨끗하고 PaperMod가 고정 커밋으로 초기화됐을 때만 생성된다.
- 예약 작업은 설치 시 검증한 절대 Python 경로를 사용한다. 07시 Publish는 오늘 체크포인트를 우선하고, 자정 넘김 복구에 한해 어제 체크포인트까지 채택한다.
- 원격 게시 푸시는 로컬 `main` 브랜치에서만 허용한다.

## 사전 점검

```powershell
Set-Location C:\projects\DailyReport
python --version
codex --version
codex login status
git status --short
git submodule update --init --recursive
hugo version
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_scheduler.ps1 -WhatIf
```

`install_scheduler.ps1 -WhatIf`은 실행 경로, 시간, 재시도 설정을 출력할 뿐 예약 작업을 만들지 않는다. 의존성이 빠졌거나 Codex 로그인이 유효하지 않으면 실패한다.

## 섀도 실행

Hugo 준비와 리뷰된 작업 브랜치 커밋이 끝난 뒤 다음 명령을 사용한다.

```powershell
$date = Get-Date -Format yyyy-MM-dd
$before = git rev-parse HEAD
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_daily.ps1 -Mode Prepare -Date $date -Shadow
$exit = $LASTEXITCODE
Get-Content "runs\$date\run.json"
Get-Content "runs\$date\checkpoint.json"
git status --short
git rev-parse HEAD
"exit=$exit before=$before"
```

`run.json`에는 후보·선택·제외·발행 수, 수집원별 상태, 선택/제외 결정 수, 부족·소스 경고, 단계별 경과 시간, bounded Codex stderr, 생성 오류 요약, 준비 HEAD·입력 해시·게시/배포 SHA가 기록된다.

하루 합격 조건:

- 종료 코드 0, `status=prepared`, `validate=ok`, 체크포인트의 `hugo=ok`
- 모든 후보에 선택 또는 제외 결정이 정확히 하나 존재
- `daily`, `articles`, `executive`, `guides`가 서로 다른 staging 경로에 존재
- 홈 RSS에 `daily`만 있고 개별 기사·경영·가이드·기존 콘텐츠는 없음
- 0편이면 게시 보류 가능 상태, 1~9편이면 warning, 10편 이상이면 normal
- `git rev-parse HEAD`가 실행 전후 동일하고 날짜 콘텐츠·Git index 변경이 없음
- commit, push, email, 예약 등록이 모두 0건
- 준비가 07:00 전에 끝남

일반 운영에서는 이 조건을 3~5일 연속 충족해야 전환을 검토한다. 이번 전환은 사용자 지시로 이 기간만 생략한다. 목표 30편은 품질을 낮추는 하한이 아니며, 유의미한 기사가 부족하면 실제 수를 그대로 기록한다.

## 진단

```powershell
$date = Get-Date -Format yyyy-MM-dd
Get-Content "runs\$date\run.json"
Get-Content "runs\$date\source_health.json"
Get-Content "runs\$date\selection.json"
Get-Content "runs\$date\generation.json"
Get-Content "runs\$date\checkpoint.json" -ErrorAction SilentlyContinue
Get-Content "runs\$date\publish.json" -ErrorAction SilentlyContinue
Get-ScheduledTask -TaskName 'AI Daily *' -ErrorAction SilentlyContinue |
  Select-Object TaskName, State
```

주요 종료 코드:

- `0`: prepared, published, skipped
- `2`: failed, held, push pending/rejected
- `3`: 다른 실행이 잠금을 보유함
- `4`: 체크포인트가 아직 없거나 준비 후 입력/Git HEAD가 바뀜

게시 커밋 뒤 push만 실패한 경우 다음 `Publish` 재시도는 같은 `publish.json.commit_sha`와 현재 HEAD를 확인한 뒤 재생성 없이 push만 복구한다.

## 예약 작업 설치와 활성화

아래 변경은 별도 사용자 승인 후에만 수행한다.

```powershell
# 세 작업을 등록하지만 모두 disabled 상태로 둔다.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_scheduler.ps1 -Apply
Get-ScheduledTask -TaskName 'AI Daily *' | Select-Object TaskName, State
```

등록 계약:

- `AI Daily Prepare`: 매일 06:00
- `AI Daily Publish`: 매일 07:00, 실패 시 10분 간격 최대 12회 재시도
- `AI Daily Alert`: 매일 12:00

Task Scheduler가 실제 non-zero action exit를 재시작하는지는 아직 목표 호스트에서 관찰하지 않았다. 라이브 전환 승인 전에 별도 안전한 throwaway 작업 또는 첫 섀도 작업 기록으로 재시도 이벤트를 확인해야 한다.

일반적으로 3~5일 섀도와 최종 적대 리뷰가 통과한 뒤 활성화한다. 이번 전환은 사용자 지시로 섀도 기간만 면제하며, 실제 전체 렌더와 최종 적대 리뷰는 면제하지 않는다.

```powershell
Enable-ScheduledTask -TaskName 'AI Daily Prepare'
Enable-ScheduledTask -TaskName 'AI Daily Publish'
Enable-ScheduledTask -TaskName 'AI Daily Alert'
```

실제 `Publish` 실행은 검증된 날짜 파일을 커밋하고 `origin/main`에 push한 뒤 기본 `daily` 이메일을 보낸다. 수동 테스트 목적으로 실행하지 않는다.

## 전환과 롤백

전환 순서:

1. 실제 전체 Hugo/RSS 검증과 최신 Opus 5 적대 리뷰 `Critical=0`, `High=0` 확인
2. 사용자 승인 후 예약 작업 등록(disabled)
3. 작업 정의·계정·시간·재시도 설정 확인
4. 사용자 승인 후 세 작업 활성화
5. 첫 Windows 게시와 이메일 확인
6. 그 뒤에만 WSL timer 중지
7. WSL 저장소를 최소 일주일 읽기 전용 롤백 기준으로 보존

문제 발생 시 먼저 Windows 작업을 멈춘다.

```powershell
Disable-ScheduledTask -TaskName 'AI Daily Prepare'
Disable-ScheduledTask -TaskName 'AI Daily Publish'
Disable-ScheduledTask -TaskName 'AI Daily Alert'
```

- push 전 로컬 실패는 날짜 쓰기 집합 롤백이 Git HEAD와 index를 복원한다.
- 강제 종료로 날짜 쓰기 집합이 남으면 `git status --short -- "content/articles/$date-*" "content/daily/$date.md" "content/guides/$date.md" "content/executive/$date.md" data/published.csv`로 범위를 확인한 뒤, 추적 파일은 같은 경로에 `git restore --staged --worktree -- ...`를 적용하고 미추적 파일은 정확한 날짜 경로만 제거한다.
- 로컬 커밋 후 push 실패는 삭제·재생성하지 말고 같은 날짜 `Publish`로 push-only 복구한다.
- 이미 원격에 게시한 커밋을 되돌려야 하면 해당 SHA와 영향 날짜를 확인한 뒤 별도 승인으로 `git revert <sha>`와 push를 수행한다. `reset --hard`는 사용하지 않는다.
- Windows 전환 자체를 되돌릴 때는 Windows 작업을 disabled로 유지하고, 보존한 WSL 저장소 상태와 timer 정의를 확인한 뒤 별도 승인으로 WSL timer를 다시 활성화한다.
- 예약 작업을 완전히 삭제하는 `Unregister-ScheduledTask`도 별도 승인 없이 실행하지 않는다.

## 현재 열린 전환 게이트

- 실제 프로덕션 렌더링 검증
- Task Scheduler non-zero exit 재시도 실증
- `Interactive` 작업을 위해 06시~12시 로그인 상태 유지 확인
- 최신 전체 산출물에 대한 Claude Opus 5 `--effort xhigh` 리뷰
- 예약 등록, 활성화, WSL timer 중지, 첫 게시·이메일 결과 확인
