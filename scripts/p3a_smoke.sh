#!/usr/bin/env bash
# P3a real smoke: run the full pipeline for a date WITHOUT committing or pushing (--no-commit
# implies --no-push), then show run.json. Needs Claude Code env (collect/select/stage call
# claude -p). Promotes into content/ but makes NO commit, so the tree is only DIRTY (never a
# stray commit that a later real run would push) — clean up with the P2c smoke's date-scoped
# git restore/clean commands. (--no-push alone still COMMITS, which restore/clean cannot undo.)
set -euo pipefail
DATE="${1:?usage: p3a_smoke.sh <date>}"
export PATH="$HOME/.local/bin:$PATH"
python3 -m nbs.orchestrate --date "$DATE" --no-commit
echo "--- run.json ---"; cat "runs/$DATE/run.json" 2>/dev/null || echo "(no run.json — see the [status] line above, e.g. a refused no-commit preview)"
echo "--- publish.json ---"; cat "runs/$DATE/publish.json" 2>/dev/null || true
