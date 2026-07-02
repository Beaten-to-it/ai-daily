#!/usr/bin/env bash
# P3b dry-run smoke: compose the email for a published day WITHOUT sending.
# Usage: bash scripts/p3b_smoke.sh 2026-07-03
set -euo pipefail
DATE="${1:?usage: p3b_smoke.sh YYYY-MM-DD}"
cd "$(dirname "$0")/.."
echo "== git gate =="
python3 -c "from nbs import email; print('published:', email.published('$DATE'))"
echo "== dry-run compose =="
python3 -m nbs.email --date "$DATE" --dry-run
