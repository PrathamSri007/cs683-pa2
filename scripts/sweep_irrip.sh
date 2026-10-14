#!/usr/bin/env bash
# c[i]: code lines are inserted at rrpv i
# d[i]: data lines are inserted at rrpv i
# p[i]: data lines are promoted to rrpv i
# e[0/1]: if 1, evict data lines preferably
# w[0/1]: if 0, ignore writeback rrpv change
set -euo pipefail
cd "$(dirname "$0")/.."

VARIANTS="c2d3p3e1w0 c2d3p3e1w1 c2d3p2e1w0 c1d3p3e1w1 c1d3p3e1w0 c0d3p3e1w0 c0d3p2e1w0 c1d3p2e1w1 c0d3p2e0w0 c2d2p2e0w0 c0d2p3e0w1 c0d2p3e1w1 c2d2p0e1w0 c0d2p0e1w0"

for tr in trace1 trace2 trace3; do
  for v in $VARIANTS; do
    # Regex updated to make 'w' compulsory
    [[ "$v" =~ ^c([0-3])d([0-3])p([0-3])e([01])w([01])$ ]] || { echo "bad variant $v" >&2; exit 1; }
    
    # BASH_REMATCH indexes: 
    # [1]=c, [2]=d, [3]=p, [4]=e, [5]=w
    echo "IRRIP_INS_INSTR=${BASH_REMATCH[1]} IRRIP_INS_DATA=${BASH_REMATCH[2]} IRRIP_PRO_DATA=${BASH_REMATCH[3]} DATA_EVICT=${BASH_REMATCH[4]} IRRIP_WB_PROMOTE=${BASH_REMATCH[5]} irrip $tr irrip_$v"
  done
done | scripts/run_jobs.sh