#!/usr/bin/env bash
# usage: scripts/run_matrix.sh <config> [<config> ...]      runs each config on trace1..3, JOBS at a time
# Skips (config,trace) pairs that already have an output file in OUT_DIR (default results/raw); FORCE=1 re-runs everything.
set -euo pipefail
cd "$(dirname "$0")/.."
JOBS=${JOBS:-4}
for cfg in "$@"; do
  for tr in trace1 trace2 trace3; do
    if [ -s "${OUT_DIR:-results/raw}/${cfg}__${tr}.txt" ] && [ "${FORCE:-0}" != 1 ]; then continue; fi
    echo "$cfg $tr"
  done
done | xargs -r -P "$JOBS" -L 1 scripts/run_sim.sh
