#!/usr/bin/env bash
# Re-runs the UNCHANGED Phase 4 frozen test set on the UNCHANGED Phase 4 engine (commit 48bf73e) and compares it
# row by row with the result recorded in Phase 4. Writes only to benchmarks/results/phase5/.
set -euo pipefail
cd "$(dirname "$0")/../.."
P4=${P4_DIR:-/tmp/granth_phase4_engine}
[ -d "$P4" ] || git worktree add -q "$P4" 48bf73e2346374a1a0081c0c95e6aa021bc6ab2a
PY=${PY:-.venv/bin/python}
PYTHONPATH="$P4" $PY "$P4/benchmarks/run_phase3.py" --engine-root "$P4" \
  --questions "$P4/benchmarks/phase4/frozen_test.json" --out benchmarks/results/phase5/phase4_baseline_rerun.json >/dev/null || true
$PY - "$P4" <<'P'
import json, sys, hashlib
p4 = sys.argv[1]
a = json.load(open(p4 + "/benchmarks/results/phase4_frozen_run1.json"))
b = json.load(open("benchmarks/results/phase5/phase4_baseline_rerun.json"))
key = lambda x: ([(r["id"], r["outcome"], r["status"], r["trust"], r["answer"]) for r in x["failures"]], x["by_category"], x["metrics"])
print("engine:", b["engine_version"])
print("frozen_test.json sha256:", hashlib.sha256(open(p4 + "/benchmarks/phase4/frozen_test.json", "rb").read()).hexdigest())
print("recorded overall:", a["overall"])
print("rerun overall:   ", b["overall"])
print("failures, per-category and metrics identical:", key(a) == key(b))
P
