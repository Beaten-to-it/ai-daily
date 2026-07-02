#!/usr/bin/env bash
# P3a real smoke: run the full pipeline for a date WITHOUT pushing (--no-push), then show
# run.json. Needs Claude Code env (collect/select/stage call claude -p). Leaves a dirty tree;
# clean up with the date-scoped commands the P2c smoke prints (content/news|posts|usecase, ledger).
set -euo pipefail
DATE="${1:?usage: p3a_smoke.sh <date>}"
export PATH="$HOME/.local/bin:$PATH"
python3 -m nbs.orchestrate --date "$DATE" --no-push
echo "--- run.json ---"; cat "runs/$DATE/run.json"
echo "--- publish.json ---"; cat "runs/$DATE/publish.json" 2>/dev/null || true
