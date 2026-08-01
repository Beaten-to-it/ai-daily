#!/usr/bin/env bash
# 빌드 산출물 완결성 스모크 체크. 깨지면 비0 종료.
set -euo pipefail
BASE="https://beaten-to-it.github.io/ai-daily/"
rm -rf public
hugo --quiet --baseURL "$BASE"

req=(
  "public/index.html"
  "public/index.xml"                                  # daily-only 홈 RSS
  "public/daily/index.html"
  "public/articles/index.html"
  "public/executive/index.html"
  "public/guides/index.html"
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
if grep -Eq '<link>[^<]*/(posts|news|ax|usecase|articles|executive|guides)/' public/index.xml; then
  echo "home RSS contains a non-daily section"
  exit 1
fi
echo "SMOKE OK"
