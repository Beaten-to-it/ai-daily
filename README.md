# AI Daily

Windows에서 Codex로 수집·선별·작성·검증하고 Hugo로 발행하는 한국어 AI 뉴스 프로젝트입니다.

- 유의미한 개별 기사 목표는 30편 이상이며 상한은 없습니다.
- 10편 이상은 정상 발행, 1~9편은 부족 경고와 함께 발행, 0편은 게시·이메일을 중단합니다.
- 원문 본문은 재게시하지 않고 출처 링크와 자체 요약·해설만 제공합니다.
- 홈페이지, 기본 RSS, 기본 이메일에는 `daily` 종합 리포트만 노출합니다.

## 콘텐츠 구조

- `content/daily/` — 일일 종합 리포트
- `content/articles/` — 개별 한국어 기사
- `content/executive/` — 경영·AX 브리핑
- `content/guides/` — 실제 활용 가치가 있을 때만 만드는 가이드
- `content/news/`, `content/posts/`, `content/ax/`, `content/usecase/` — URL 보존을 위한 기존 발행물

## 로컬 검증

필수 환경은 Python 3.13+, 로그인된 Codex CLI, Git, Hugo Extended 0.163.3+입니다. 테마는 Git submodule입니다.

```powershell
git submodule update --init --recursive
python -m pytest -q
hugo --gc --minify --buildFuture
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_scheduler.ps1 -WhatIf
```

Hugo나 초기화된 PaperMod가 없으면 준비 체크포인트도 실패 폐쇄형으로 중단되며 게시·커밋·푸시·이메일은 실행되지 않습니다.

## Windows 실행

```powershell
# 06시 준비와 같은 읽기·쓰기 제한 섀도 실행
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_daily.ps1 -Mode Prepare -Shadow

# 준비된 오늘 체크포인트를 게시하고, 없으면 자정 넘김 복구에 한해 어제 것을 사용
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_daily.ps1 -Mode Publish
```

설치·섀도·진단·활성화·롤백 절차는 [Windows 운영 가이드](docs/operations/windows-publisher.md)를 따릅니다. 게시 푸시는 로컬 `main` 브랜치에서만 허용됩니다.

GitHub Pages는 `main` push 후 `.github/workflows/pages.yml`의 Hugo 빌드와 스모크 게이트를 통과한 경우에만 배포됩니다.
