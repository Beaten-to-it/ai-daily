#!/usr/bin/env bash
# P2a 통합 스모크: 실제 collect -> select 1회. 깨지면 비0 종료.
set -euo pipefail
DATE="${1:?usage: p2a_smoke.sh YYYY-MM-DD}"
python3 -m nbs.collect --date "$DATE"
N=$(python3 -c "import json;print(len(json.load(open(f'runs/$DATE/candidates.json'))))")
echo "candidates: $N"
[ "$N" -gt 0 ] || { echo "FAIL: 0 candidates — nbs/sources.py 피드 점검"; exit 1; }
python3 -m nbs.select --date "$DATE"
python3 - "$DATE" <<'PY'
import json,sys
from nbs.models import validate_selection
o=json.load(open(f"runs/{sys.argv[1]}/selection.json"))
assert validate_selection(o)==[], "schema invalid"
assert o["selected_count"]==len(o["items"])
print("selected:",o["selected_count"],"| skipped:",o["skipped_count"])
print("SMOKE OK")
PY
