# ai-daily

매일 아침 AI 뉴스 — 짧은 **News 인덱스** → 각 항목의 한글 상세 **Blog** + **AI UseCase**.
Hugo(PaperMod) 정적 사이트 → GitHub Pages: https://beaten-to-it.github.io/ai-daily/

## 로컬 빌드

필요: Hugo **extended** 0.163.3+ (`hugo version` 출력에 `extended` 포함).

```bash
# 새로 클론할 때 (테마는 submodule)
git clone --recurse-submodules <repo-url>

# 이미 클론했다면 submodule 초기화
git submodule update --init --recursive

# 빌드 + 완결성 스모크 체크 → "SMOKE OK"
./scripts/smoke_build.sh

# 로컬 미리보기
hugo server
```

## 배포

`main`에 push → `.github/workflows/pages.yml`가 빌드 + smoke 게이트 후 GitHub Pages 배포.
최초 1회 설정: GitHub → Settings → Pages → Build and deployment → Source: **GitHub Actions**.

## 구조

- `content/news/` — 일일 News 인덱스
- `content/posts/` — Blog 상세글
- `content/usecase/` — AI UseCase
- `scripts/smoke_build.sh` — 빌드 완결성 체크 (로컬·CI 공용)
- 설계: `docs/superpowers/specs/` · 구현 계획: `docs/superpowers/plans/`
