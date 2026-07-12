#!/usr/bin/env bash
# P2c real smoke: regenerate staging (so news uses relref), then promote into content/
# WITHOUT committing, then show the manifest. Leaves a dirty tree for inspection;
# clean up with the date-scoped commands printed at the end.
set -euo pipefail
DATE="${1:?usage: p2c_smoke.sh <date>}"
export PATH="$HOME/.local/bin:$PATH"
python3 -m nbs.stage --date "$DATE"                 # fresh staging (relref links)
python3 -m nbs.publish --date "$DATE" --no-commit
echo "--- publish.json ---"; cat "runs/$DATE/publish.json"
echo "--- content added ---"; ls -1 content/posts/ | grep "$DATE" || true
ls -1 "content/news/$DATE.md" "content/usecase/$DATE.md" 2>/dev/null || true
echo "--- cleanup (date-scoped; restores tracked, removes new untracked) ---"
echo "git restore --staged --worktree -- content/posts/$DATE-*.md content/news/$DATE.md content/usecase/$DATE.md content/ax/$DATE.md data/published.csv 2>/dev/null; git clean -f -- content/posts/$DATE-*.md content/news/$DATE.md content/usecase/$DATE.md content/ax/$DATE.md data/published.csv"
