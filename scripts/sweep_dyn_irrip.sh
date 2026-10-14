#!/usr/bin/env bash
# Task 2B sensitivity studies: ONE dyn_irrip binary, parameters selected through env vars (no rebuilds).
# usage: scripts/sweep_dyn_irrip.sh                  threshold sweep (THRESHOLDS, default "5 15 25 35 45 55" %), x 3 traces
#        THRESHOLDS="10 20 30 40 50" scripts/sweep_dyn_irrip.sh    choose values that straddle the observed ratios
#        SWEEP=leaders scripts/sweep_dyn_irrip.sh    leader-set count 128/64/32/16/8 (DYN_IRRIP_LEADER_LOG2 = 3..7)
#        SWEEP=epoch scripts/sweep_dyn_irrip.sh      decision epoch 256/1024/4096 leader events
#        SWEEP=variants scripts/sweep_dyn_irrip.sh   refined decision logic (see dyn_irrip.l2c_repl header):
#            dyn_irrip_hyst5    PDF formula, threshold 25% with a +-5% hysteresis band
#            dyn_irrip_miss50   miss-share formula Im/Tm, threshold 50%
#            dyn_irrip_duel     true set dueling (SRRIP + I-RRIP leaders, PSEL on misses), code miss weight 1
#            dyn_irrip_duelw2   true set dueling, a code miss weighs 2
# Tags: dyn_irrip_th<T>, dyn_irrip_ldr<N>, dyn_irrip_ep<E>, see above. Restartable (existing outputs are skipped; FORCE=1 reruns).
set -euo pipefail
cd "$(dirname "$0")/.."
SWEEP=${SWEEP:-thresh}; CFG=${CFG:-dyn_irrip}
THRESHOLDS=${THRESHOLDS:-"5 10 15 25 35 45 55"}
for tr in trace1 trace2 trace3; do
  case "$SWEEP" in
    thresh)  for th in $THRESHOLDS; do echo "DYN_IRRIP_THRESH_PCT=$th $CFG $tr ${CFG}_th$th"; done ;;
    leaders) for lg in 3 4 5 6 7; do echo "DYN_IRRIP_LEADER_LOG2=$lg $CFG $tr ${CFG}_ldr$((1024 >> lg))"; done ;;
    epoch)   for ep in 256 1024 2048 4096 6144; do echo "DYN_IRRIP_EPOCH=$ep $CFG $tr ${CFG}_ep$ep"; done ;;
    variants)
      echo "DYN_IRRIP_HYST_PCT=5 $CFG $tr ${CFG}_hyst5"
      echo "DYN_IRRIP_MODE=1 DYN_IRRIP_THRESH_PCT=50 $CFG $tr ${CFG}_miss50"
      echo "DYN_IRRIP_MODE=2 $CFG $tr ${CFG}_duel"
      echo "DYN_IRRIP_MODE=2 DYN_IRRIP_CODE_WEIGHT=2 $CFG $tr ${CFG}_duelw2" ;;
    *) echo "unknown SWEEP=$SWEEP" >&2; exit 1 ;;
  esac
done | scripts/run_jobs.sh
