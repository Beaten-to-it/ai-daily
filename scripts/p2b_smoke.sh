#!/usr/bin/env bash
# P2b 통합 스모크: 실제 fetch -> generate -> stage. 깨지면 비0 종료.
# 전제: runs/<DATE>/selection.json 존재 (p2a_smoke.sh 선행).
set -euo pipefail
DATE="${1:?usage: p2b_smoke.sh YYYY-MM-DD}"
[ -f "runs/$DATE/selection.json" ] || { echo "FAIL: runs/$DATE/selection.json 없음 (p2a 먼저)"; exit 1; }
python3 -m nbs.stage --date "$DATE"
python3 - "$DATE" <<'PY'
import json,sys
from pathlib import Path
d=Path("runs")/sys.argv[1]
g=json.load(open(d/"generation.json"))
print("status:",g["status"],"| published:",g["published_count"],"| floor_failed:",g["floor_failed"])
for r in g.get("results",[]):
    assert r["status"] in ("ok","failed","excluded"), r
    if r["status"]=="ok":
        assert (d/"staging"/"posts"/f"{r['slug']}.md").exists(), f"missing post {r['slug']}"
print("SMOKE OK")
PY
