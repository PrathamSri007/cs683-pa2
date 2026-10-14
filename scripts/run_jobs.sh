#!/usr/bin/env bash
# usage: <job lines> | scripts/run_jobs.sh
# Each stdin line is   [VAR=value ...] <config> <trace> <tag>   and becomes one scripts/run_sim.sh call,
# JOBS at a time (default 4). Lines whose output file results/raw/<tag>__<trace>.txt already exists and is
# non-empty are skipped (restartable); FORCE=1 re-runs them. OUT_DIR is honoured as in run_sim.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT_DIR=${OUT_DIR:-results/raw}
while read -r line; do
  [ -n "$line" ] || continue
  set -- $line; while [[ "$1" == *=* ]]; do shift; done        # skip VAR=value words
  tr=$2; tag=$3
  if [ -s "$OUT_DIR/${tag}__${tr}.txt" ] && [ "${FORCE:-0}" != 1 ]; then echo "skip $tag $tr (exists)" >&2; continue; fi
  echo "$line"
done | xargs -r -P "${JOBS:-4}" -L 1 bash -c 'envs=(); while [[ "$1" == *=* ]]; do envs+=("$1"); shift; done; env "${envs[@]}" scripts/run_sim.sh "$@"' _
