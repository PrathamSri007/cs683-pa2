#!/bin/bash

set -e

# Build the three ChampSim configurations
# ./build_champsim.sh baseline
# ./build_champsim.sh ipstride
# ./build_champsim.sh spp
./build_champsim.sh spp+dyn_irrip

# Binaries
BASELINE="./bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline"
IPSTRIDE="./bin/hashed_perceptron-no-ip_stride-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-ip_stride"
SPP="./bin/hashed_perceptron-no-spp-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-spp"
SPP_IRRIP="./bin/hashed_perceptron-no-spp-no-no-no-no-no-lru-lru-lru-dyn_irrip-lru-lru-lru-lru-1core-spp+dyn_irrip"
IRRIP="bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-dyn_irrip-lru-lru-lru-lru-1core-dyn_irrip"

# Run all 9 simulations in parallel
# $BASELINE -warmup_instructions 25000000 -simulation_instructions 25000000 -traces traces/Trace1.gz > output_logs/baseline_Trace1.log 2>&1 &
# $BASELINE -warmup_instructions 25000000 -simulation_instructions 25000000 -traces traces/Trace2.gz > output_logs/baseline_Trace2.log 2>&1 &
# $BASELINE -warmup_instructions 25000000 -simulation_instructions 25000000 -traces traces/Trace3.gz > output_logs/baseline_Trace3.log 2>&1 &

# $IPSTRIDE -warmup_instructions 25000000 -simulation_instructions 25000000 -traces traces/Trace1.gz > output_logs/ipstride_Trace1.log 2>&1 &
# $IPSTRIDE -warmup_instructions 25000000 -simulation_instructions 25000000 -traces traces/Trace2.gz > output_logs/ipstride_Trace2.log 2>&1 &
# $IPSTRIDE -warmup_instructions 25000000 -simulation_instructions 25000000 -traces traces/Trace3.gz > output_logs/ipstride_Trace3.log 2>&1 &

# $SPP -warmup_instructions 25000000 -simulation_instructions 25000000 -traces traces/Trace1.gz > output_logs/spp_Trace1.log 2>&1 &
# $SPP -warmup_instructions 25000000 -simulation_instructions 25000000 -traces traces/Trace2.gz > output_logs/spp_Trace2.log 2>&1 &
# $SPP -warmup_instructions 25000000 -simulation_instructions 25000000 -traces traces/Trace3.gz > output_logs/spp_Trace3.log 2>&1 &

$IRRIP -warmup_instructions 25000000 -simulation_instructions 25000000 -traces traces/Trace1.gz > output_logs/irrip_Trace1.log 2>&1 &
$IRRIP -warmup_instructions 25000000 -simulation_instructions 25000000 -traces traces/Trace2.gz > output_logs/irrip_Trace2.log 2>&1 &
$IRRIP -warmup_instructions 25000000 -simulation_instructions 25000000 -traces traces/Trace3.gz > output_logs/irrip_Trace3.log 2>&1 &

$SPP_IRRIP -warmup_instructions 25000000 -simulation_instructions 25000000 -traces traces/Trace1.gz > output_logs/sppirrip_Trace1.log 2>&1 &
$SPP_IRRIP -warmup_instructions 25000000 -simulation_instructions 25000000 -traces traces/Trace2.gz > output_logs/sppirrip_Trace2.log 2>&1 &
$SPP_IRRIP -warmup_instructions 25000000 -simulation_instructions 25000000 -traces traces/Trace3.gz > output_logs/sppirrip_Trace3.log 2>&1 &

# Wait for all 9 simulations to finish
wait

echo "All 9 simulations completed."
python3 extract_stats.py
