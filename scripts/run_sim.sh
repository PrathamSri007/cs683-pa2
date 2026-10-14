#!/usr/bin/env bash
# usage: scripts/run_sim.sh <config> <trace> [tag]
#   <config> = what you gave ./build_champsim.sh   (baseline, ipstride, spp, rrip, irrip, dyn_irrip, ...)
#   <trace>  = trace1 | trace2 | trace3
#   [tag]    = label used in the output file name (default: config). Use it for sweeps.
# The trace is always passed as  traces/Trace<N>.gz  (relative to the repo root: the convention of the committed
# logs, created by scripts/prep_traces.sh). Do not change it: the path seeds the simulator's random page placement.
# env:  OUT_DIR (default results/raw)  WARMUP / SIM (default 25M / 25M)
#       any experiment knob, e.g.  DYN_IRRIP_THRESH_PCT=35 scripts/run_sim.sh dyn_irrip trace1 dyn_irrip_th35
set -euo pipefail
cd "$(dirname "$0")/.."
CFG=$1; TR=$2; TAG=${3:-$CFG}
SUF=$CFG; [ "$CFG" = ipstride ] && SUF=ip_stride        # build_champsim.sh names the ipstride binary "...-1core-ip_stride"
BIN=$(ls bin/*-1core-"$SUF" 2>/dev/null | head -n1 || true)
[ -n "$BIN" ] || { echo "no binary for '$CFG' in bin/ - build it first" >&2; exit 1; }
T="traces/Trace${TR#trace}.gz"
[ -e "$T" ] || { echo "no $T - run scripts/prep_traces.sh" >&2; exit 1; }
OUT_DIR=${OUT_DIR:-results/raw}; mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/${TAG}__${TR}.txt"
echo "[$(date +%T)] start $TAG $TR"
"$BIN" -warmup_instructions "${WARMUP:-25000000}" -simulation_instructions "${SIM:-25000000}" -traces "$T" > "$OUT" 2>&1
echo "[$(date +%T)] done  $TAG $TR  $(grep 'CPU 0 cumulative IPC' "$OUT" | awk '{print "IPC="$5}')"
