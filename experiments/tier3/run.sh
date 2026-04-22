#!/bin/bash
# Run the Tier 3 experiment — grounded vs degenerate on the same case suite.
#
# Reproducible in < 10 seconds with zero network cost and zero LLM spend. See
# experiments/tier3/README.md for scope, the rule-based stand-in's limits,
# and how to add a live-Envelop column.
#
# Usage:
#   cd experiments/tier3
#   ./run.sh
#
# Writes:
#   grounded/kelvin/report.json
#   degenerate/kelvin/report.json
#   results/table_3.md

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# Pin Kelvin to *this* worktree's source so the experiment uses the exact
# version being evaluated, not whatever happens to be installed in the venv.
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
PY="${PY:-python3}"

echo "=== Tier 3 experiment ==="
echo "Kelvin source: $REPO_ROOT/src"
echo

echo "[1/3] Grounded (rule-based stand-in)"
rm -rf grounded/kelvin
( cd grounded && "$PY" -m kelvin check )
echo

echo "[2/3] Degenerate (constant output)"
rm -rf degenerate/kelvin
( cd degenerate && "$PY" -m kelvin check )
echo

echo "[3/3] Build Table 3"
"$PY" build_table.py
echo
echo "Results written to results/table_3.md"
