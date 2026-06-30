# P1 — 사이트 골격 + 배포 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hugo(PaperMod) 정적 사이트를 새 GitHub repo `ai-daily`에 만들고 GitHub Actions로 GitHub Pages에 자동 배포해, 손으로 쓴 샘플 글이 `https://beaten-to-it.github.io/ai-daily/`에 실제로 뜨는 walking skeleton을 만든다.

**Architecture:** Hugo extended로 로컬 빌드, PaperMod 테마는 git submodule(로컬 go 없음). content는 `posts`(Blog)·`news`(News 인덱스)·`usecase` 3 섹션 + `tags` 분류. push → `.github/workflows/pages.yml`가 Hugo 빌드 후 Pages artifact 배포.

**Tech Stack:** Hugo extended, PaperMod, GitHub Actions(Pages), git submodule, bash 스모크 체크.

## Global Constraints

- GitHub owner: `Beaten-to-it` · repo: `ai-daily` · 기본 브랜치: `main`
- baseURL(슬래시 필수): `https://beaten-to-it.github.io/ai-daily/`
- Hugo: **extended**. 버전은 Task 0에서 GitHub 최신 release로 확정·설치하고, 그 **확정된 버전값을 Task 6 워크플로 `HUGO_VERSION`에 동일하게** 박는다(로컬·CI 동기화).
- 테마: PaperMod, **git submodule** (`themes/PaperMod`) — 로컬에 go 없음
- 언어: `ko`
- content 섹션: `posts`(Blog) · `news`(News 일일 인덱스) · `usecase`(AI UseCase) / 분류(taxonomy): `tags`
- **내부 링크는 항상 `{{< relref >}}`** (절대경로 하드코딩 금지 — subpath baseURL에서 깨짐)
- **메뉴 url은 leading slash 없이** (`news/` 형태 — project subpath에서 루트로 새는 것 방지)
- 샘플 콘텐츠 날짜는 **과거 고정(2026-06-30)** (future-dated 제외 회피)
- **시크릿 위생(§10):** 토큰·쿠키·키 절대 커밋 금지. `.gitignore`에 `*token*.json`, `client_secret*.json`, `secrets/`, `*.cookies`, `.env` 포함. (P1엔 시크릿 없음 — baseline만.)
- 작업 디렉터리: `/home/beaten/project/NBs` (이미 `docs/` 존재 — `--force`로 scaffold)
- 커밋 단위: 태스크별 1커밋

---

### Task 0: 로컬 툴체인(Hugo extended, no-sudo) + git preflight

**Files:** (환경 셋업)

**Interfaces:**
- Produces: `hugo` extended CLI(`~/.local/bin`), 확정 버전 문자열, git repo(`main`) + user.name/email

- [ ] **Step 1: git 자격 preflight (없으면 설정)**

```bash
git config --get user.name  || git config --global user.name  "Beaten-to-it"
git config --get user.email || git config --global user.email "kimhyo75@gmail.com"
git config --get user.name; git config --get user.email
```
Expected: name·email 둘 다 비어있지 않음

- [ ] **Step 2: Hugo extended 최신판 설치(sudo 불필요, tarball→~/.local/bin)**

```bash
set -euo pipefail
mkdir -p ~/.local/bin
# 최신 extended 버전 추출 — 실패(rate-limit/빈값)면 즉시 중단(grep -P 미사용)
HV=$(curl -fsSL https://api.github.com/repos/gohugoio/hugo/releases/latest \
      | grep -m1 '"tag_name"' | sed -E 's/.*"v([^"]+)".*/\1/')
test -n "$HV" || { echo "ERROR: Hugo 버전 추출 실패(rate-limit?). 최신 extended 버전을 수동 지정 후 재시도"; exit 1; }
echo "Hugo version = $HV"   # ← 이 값을 Task 6 HUGO_VERSION에 사용
curl -fsSL "https://github.com/gohugoio/hugo/releases/download/v${HV}/hugo_extended_${HV}_linux-amd64.tar.gz" -o /tmp/hugo.tgz
tar -xzf /tmp/hugo.tgz -C ~/.local/bin hugo
grep -q 'HOME/.local/bin' ~/.bashrc || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
export PATH="$HOME/.local/bin:$PATH"
```

- [ ] **Step 3: extended 확인 + 버전 기록**

Run: `hugo version`
Expected: 출력에 `extended` 포함. (이 버전 = Task 6에 박을 값)

- [ ] **Step 4: git repo 초기화 + 초기 커밋**

```bash
cd /home/beaten/project/NBs
git init -b main
git add -A
git commit -m "chore: init repo with design docs"
git rev-parse --abbrev-ref HEAD
```
Expected: 마지막 줄 `main`, 커밋 성공

---

### Task 1: Hugo 사이트 scaffold + 설정 (빌드는 테마 설치 후)

**Files:**
- Create: `hugo.toml`
- Create: `archetypes/default.md` (hugo 생성)

**Interfaces:**
- Produces: baseURL/언어/taxonomy/menu/outputs 설정된 config (테마 빌드는 Task 2)

- [ ] **Step 1: scaffold (기존 디렉터리 위에)**

```bash
cd /home/beaten/project/NBs
hugo new site . --force
```

- [ ] **Step 2: `hugo.toml` 작성 (생성된 내용 덮어쓰기)**

```toml
baseURL = "https://beaten-to-it.github.io/ai-daily/"
languageCode = "ko"
defaultContentLanguage = "ko"
title = "AI Daily"
theme = "PaperMod"

[taxonomies]
  tag = "tags"

[outputs]
  home = ["HTML", "RSS"]

[params]
  env = "production"
  defaultTheme = "auto"
  ShowReadingTime = true
  ShowShareButtons = false
  ShowPostNavLinks = true
  ShowCodeCopyButtons = true
  ShowToc = true
  mainSections = ["news", "posts", "usecase"]

[menu]
  [[menu.main]]
    name = "News"
    url = "news/"
    weight = 1
  [[menu.main]]
    name = "Blog"
    url = "posts/"
    weight = 2
  [[menu.main]]
    name = "AI UseCase"
    url = "usecase/"
    weight = 3
  [[menu.main]]
    name = "Tags"
    url = "tags/"
    weight = 4
```

- [ ] **Step 3: config TOML 유효성만 확인 (테마 없어 빌드는 아직 안 함)**

Run: `python3 -c "import tomllib; tomllib.load(open('hugo.toml','rb')); print('toml ok')"`
Expected: `toml ok`

- [ ] **Step 4: 커밋**

```bash
git add hugo.toml archetypes
git commit -m "feat: hugo site scaffold and config"
```

---

### Task 2: PaperMod 테마(submodule) 연결 + 첫 빌드

**Files:**
- Create: `themes/PaperMod` (submodule), `.gitmodules`

**Interfaces:**
- Consumes: `hugo.toml`의 `theme = "PaperMod"`
- Produces: 테마 적용된 성공 빌드

- [ ] **Step 1: 테마 submodule 추가**

```bash
cd /home/beaten/project/NBs
git submodule add --depth=1 https://github.com/adityatelange/hugo-PaperMod.git themes/PaperMod
```

- [ ] **Step 2: 첫 빌드 (실패를 숨기지 않게 rc 보존)**

```bash
hugo --quiet --baseURL "https://beaten-to-it.github.io/ai-daily/" >/tmp/hugo.log 2>&1; rc=$?
tail -5 /tmp/hugo.log; echo "exit=$rc"
```
Expected: `exit=0`, `public/index.html` 생성

- [ ] **Step 3: 테마 마크업 확인**

Run: `test -f public/index.html && grep -ci "post-entry\|menu\|main" public/index.html`
Expected: 1 이상

- [ ] **Step 4: 커밋**

```bash
git add .gitmodules themes/PaperMod
git commit -m "feat: add PaperMod theme as submodule"
```

---

### Task 3: content 모델 — 3 섹션 + 샘플(과거 날짜 + relref)

**Files:**
- Create: `content/_index.md`
- Create: `content/posts/2026-06-30-sample.md`
- Create: `content/news/2026-06-30.md`
- Create: `content/usecase/2026-06-30-sample.md`

**Interfaces:**
- Consumes: mainSections/menu
- Produces: posts/news/usecase 렌더 + News→Blog relref 링크

- [ ] **Step 1: 홈 `content/_index.md`**

```markdown
---
title: "AI Daily"
---

매일 아침, 읽을 수 있는 AI 뉴스 한 통. 짧은 News 인덱스 → 각 항목의 한글 상세 Blog.
```

- [ ] **Step 2: 샘플 Blog `content/posts/2026-06-30-sample.md`**

```markdown
---
title: "샘플 — Blog 상세글 렌더 확인"
date: 2026-06-30T08:00:00+09:00
tags: ["sample", "ai-coding"]
source_url: "https://example.com/original"
source_lang: "en"
source_type: "article"
evidence_level: "confirmed"
event_key: "sample-event"
---

## TL;DR
- 이 글은 Blog 상세 페이지 렌더 확인용 샘플이다.

## 본문
P1은 발행 골격만 검증한다. 실제 콘텐츠 생성은 P2.

## 출처
[원문](https://example.com/original)
```

- [ ] **Step 3: 샘플 News `content/news/2026-06-30.md` (relref 링크)**

```markdown
---
title: "2026-06-30 News"
date: 2026-06-30T08:00:00+09:00
tags: ["news"]
---

오늘의 항목:

- **샘플 항목** — Blog 상세글로 가는 링크 확인. [자세히 →]({{< relref "/posts/2026-06-30-sample.md" >}})
```

- [ ] **Step 4: 샘플 UseCase `content/usecase/2026-06-30-sample.md`**

```markdown
---
title: "샘플 — AI UseCase"
date: 2026-06-30T08:00:00+09:00
tags: ["usecase"]
---

일반 사용자용 실사용 흐름 샘플. 예: "이걸로 매일 아침 AI 뉴스를 한글로 받아볼 수 있다."
```

- [ ] **Step 5: 빌드 후 세 섹션 + relref href 확인**

```bash
hugo --quiet --baseURL "https://beaten-to-it.github.io/ai-daily/" >/tmp/hugo.log 2>&1; rc=$?
echo "exit=$rc"
ls public/posts/2026-06-30-sample/index.html public/news/2026-06-30/index.html public/usecase/2026-06-30-sample/index.html
grep -o '/ai-daily/posts/2026-06-30-sample/' public/news/2026-06-30/index.html | head -1
```
Expected: `exit=0`, 세 파일 존재, 마지막 줄 `/ai-daily/posts/2026-06-30-sample/` (relref가 subpath 포함해 정확히 생성)

- [ ] **Step 6: 커밋**

```bash
git add content
git commit -m "feat: content model (posts/news/usecase) with sample content"
```

---

### Task 4: 시크릿 위생 baseline `.gitignore`

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: `.gitignore` 작성**

```gitignore
# Hugo build output
/public/
/resources/_gen/
.hugo_build.lock

# Secrets — NEVER commit (§10)
*token*.json
client_secret*.json
secrets/
*.cookies
.env
.env.*
```

- [ ] **Step 2: 무시 동작 확인**

```bash
touch google_token.json
git add -A --dry-run 2>&1 | grep -q "google_token.json" && echo "LEAK" || echo "ignored-ok"
rm google_token.json
```
Expected: `ignored-ok`

- [ ] **Step 3: 커밋**

```bash
git add .gitignore
git commit -m "chore: gitignore build output and secret patterns"
```

---

### Task 5: 스모크 체크 스크립트

**Files:**
- Create: `scripts/smoke_build.sh`

**Interfaces:**
- Consumes: Task 1–3 산출
- Produces: 빌드 완결성 runnable 체크(로컬/CI 공용)

- [ ] **Step 1: `scripts/smoke_build.sh` 작성**

```bash
#!/usr/bin/env bash
# 빌드 산출물 완결성 스모크 체크. 깨지면 비0 종료.
set -euo pipefail
BASE="https://beaten-to-it.github.io/ai-daily/"
rm -rf public
hugo --quiet --baseURL "$BASE"

req=(
  "public/index.html"
  "public/index.xml"                                  # 홈 RSS
  "public/posts/2026-06-30-sample/index.html"
  "public/news/2026-06-30/index.html"
  "public/usecase/2026-06-30-sample/index.html"
  "public/tags/index.html"
)
for f in "${req[@]}"; do
  [[ -f "$f" ]] || { echo "MISSING: $f"; exit 1; }
done
# News→Blog 링크가 subpath 포함해 정확한지(relref 검증)
grep -q '/ai-daily/posts/2026-06-30-sample/' public/news/2026-06-30/index.html \
  || { echo "news relref href wrong"; exit 1; }
echo "SMOKE OK"
```

- [ ] **Step 2: 실행 권한 + 실행**

```bash
chmod +x scripts/smoke_build.sh
./scripts/smoke_build.sh
```
Expected: 마지막 줄 `SMOKE OK`, 종료코드 0

- [ ] **Step 3: 커밋**

```bash
git add scripts/smoke_build.sh
git commit -m "test: add build smoke check"
```

---

### Task 6: GitHub Actions Pages 워크플로

**Files:**
- Create: `.github/workflows/pages.yml`

**Interfaces:**
- Consumes: submodule 테마, `HUGO_VERSION`(=Task 0 확정 버전), base_url
- Produces: push 시 Hugo 빌드 → Pages 배포 (공식 패턴)

- [ ] **Step 1: `.github/workflows/pages.yml` 작성 (`HUGO_VERSION`은 Task 0 Step 3에서 확인한 버전으로)**

```yaml
name: Deploy Hugo site to Pages
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: false
defaults:
  run:
    shell: bash
jobs:
  build:
    runs-on: ubuntu-latest
    env:
      HUGO_VERSION: "0.148.2"   # ← Task 0 Step 3에서 확인한 실제 버전으로 교체(로컬과 동일)
    steps:
      - name: Install Hugo CLI (extended)
        run: |
          curl -sSLO "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-amd64.deb"
          sudo dpkg -i "hugo_extended_${HUGO_VERSION}_linux-amd64.deb"
      - uses: actions/checkout@v4
        with:
          submodules: recursive
          fetch-depth: 0
      - id: pages
        uses: actions/configure-pages@v5
      - name: Build
        run: hugo --minify --baseURL "${{ steps.pages.outputs.base_url }}/"
      - uses: actions/upload-pages-artifact@v3
        with:
          path: ./public
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: YAML 유효성 확인**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/pages.yml')); print('yaml ok')"`
Expected: `yaml ok`

- [ ] **Step 3: 커밋**

```bash
git add .github/workflows/pages.yml
git commit -m "ci: GitHub Actions Hugo Pages deploy"
```

---

### Task 7: repo 생성 → Pages 활성화 → push → 라이브 검증 (순서 중요)

**Files:** (원격 배포)

**Interfaces:**
- Consumes: 전체 P1 산출
- Produces: `https://beaten-to-it.github.io/ai-daily/` 라이브, 샘플 노출

> 외부 부작용 단계. gh 인증/repo 생성/push는 사용자 승인하에 진행. Pages Source를 **push 전에** 설정해야 첫 워크플로가 정상 배포된다.

- [ ] **Step 1: gh 가용성 + 권한 확인**

```bash
gh --version | head -1
gh auth status 2>&1 | head -3
```
Expected: gh 설치+인증 → Step 2a / 아니면 → Step 2b

- [ ] **Step 2a: repo 생성만 (push 안 함)**

```bash
cd /home/beaten/project/NBs
gh repo create Beaten-to-it/ai-daily --public
git remote add origin https://github.com/Beaten-to-it/ai-daily.git
gh api repos/Beaten-to-it/ai-daily --jq '.permissions.admin'   # true 여야 Pages API 가능
```
Expected: 마지막 줄 `true`

- [ ] **Step 2b: 수동 repo 생성 (gh 불가)**

GitHub 웹에서 `Beaten-to-it/ai-daily`(Public, 빈 repo) 생성 후:
```bash
git remote add origin https://github.com/Beaten-to-it/ai-daily.git
```
> push 인증 필요 시 사용자에게 `! gh auth login`(또는 PAT) 요청. Pages API(Step 3)를 쓰려면 repo admin 권한 + 토큰 `repo`+`workflow` scope 필요(없으면 Step 3은 웹 수동으로).

- [ ] **Step 3: Pages Source = GitHub Actions 활성화 (push 전)**

gh 가능: `gh api -X POST repos/Beaten-to-it/ai-daily/pages -f build_type=workflow`
(이미 활성화면 409 → 무시. admin 권한/`repo`+`workflow` scope 필요)
또는 수동: GitHub → Settings → Pages → Source: **GitHub Actions**

- [ ] **Step 4: push (워크플로 트리거)**

```bash
git push -u origin main
gh run watch 2>/dev/null || echo "Actions 탭에서 진행 확인"
```

- [ ] **Step 5: 라이브 검증 (배포 완료 후)**

```bash
sleep 90
curl -s -o /dev/null -w "%{http_code}\n" https://beaten-to-it.github.io/ai-daily/
curl -s https://beaten-to-it.github.io/ai-daily/posts/2026-06-30-sample/ | grep -c "샘플"
```
Expected: 첫 줄 `200`, 둘째 줄 `1` 이상 (지연 시 1–2분 후 재시도)

- [ ] **Step 6: 완료 보고 (5필드)**

근본원인/변경/재발방지/검증(명령+출력)/남은 리스크 형식으로 P1 완료 보고.

---

## Self-Review

**Spec 커버리지(P1 범위):** §8 새 repo+Hugo+단일 push 배포 ✓ · §3 content 모델(posts/news/usecase) ✓ · §10 시크릿 baseline ✓ · 가독성(PaperMod) ✓. 수집/생성/dedup/이메일/스케줄러/grounding은 P2·P3 — 의도된 분리.

**Placeholder 스캔:** 모든 step에 실제 config/명령/기대출력. `HUGO_VERSION`만 Task 0에서 동적 확정 후 Task 6에 전달(파생 상수, TBD 아님).

**타입/이름 일관성:** repo `ai-daily`, baseURL, 섹션 `posts/news/usecase`, 테마 `PaperMod`, 샘플 날짜 `2026-06-30`, relref href `/ai-daily/posts/2026-06-30-sample/` 전 태스크 동일. front matter 키는 스펙 §3.1과 일치.

**Codex 적대 리뷰 반영 (캡 2라운드, 수렴):**
- R1 10건 전부 반영 — 테마 선설치 순서(T1/T2), pipe rc 보존, 메뉴 leading-slash 제거, relref 내부링크, 샘플 과거날짜, sudo-free tarball 설치, git user.email, Pages Source push 전 활성화·admin 권한 확인, JSON output 제거.
- R2: 7 OK / 3 부분(smoke의 `/ai-daily/` 하드코딩은 고정 배포타깃 검증이라 의도). 신규 BLOCKER 1건(Task0 버전추출 취약) → `set -euo pipefail`+`curl -fsSL`+빈값 가드+sed로 수정. 2b에 admin/scope 노트 추가. **수렴 — 리뷰 종료.**
