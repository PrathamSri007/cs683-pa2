# CS683 - Programming Assignment 2
## Group: CacheMeIfYouCan

### Project Structure

```text
cs683-pa2/
├── LICENSE                       # Project license
├── Makefile                      # Build rules for compiling the simulator
├── README.md                     # Project documentation and usage guide
├── .gitignore                    # Ignore generated/temporary build artifacts
├── build_champsim.sh             # Generates simulator binaries for selected configs
├── champsim_sim_run.sh           # Convenience wrapper for simulation runs
├── bin/                          # Built simulator binaries for different policy configs
│   ├── baseline                  # Default baseline binary
│   ├── irrip                    # IRRIP binary
│   ├── rrip                     # RRIP binary
│   ├── dyn_irrip                # Dynamic IRRIP binary
│   └── hashed_perceptron-...    # Configuration-specific compiled binaries
├── branch/                       # Branch predictor logic and config artifacts
│   ├── branch_predictor.cc      # Branch predictor implementation
│   └── hashed_perceptron.bpred  # Predictor config/model file
├── inc/                          # Core simulator header files and data-structure definitions
│   ├── block.h                  # Cache block metadata definitions
│   ├── cache.h                  # Cache subsystem headers
│   ├── champsim.h               # Shared simulator definitions
│   ├── dram_controller.h        # DRAM controller interface
│   ├── instruction.h            # Instruction representation
│   ├── memory_class.h           # Memory model definitions
│   ├── ooo_cpu.h                # Out-of-order CPU definitions
│   ├── set.h                    # Set/associativity utilities
│   └── uncore.h                 # Uncore and system-level definitions
├── obj/                          # Intermediate build outputs and object files
│   ├── branch/                  # Branch object files
│   ├── prefetcher/              # Prefetcher object files
│   ├── replacement/             # Replacement-policy object files
│   └── src/                     # Core simulator object files
├── plots/                        # Generated performance plots and charts
│   ├── plot_accuracy.png         # Accuracy comparison plots
│   ├── plot_coverage.png         # Coverage comparison plots
│   ├── plot_mpki.png             # MPKI plots
│   ├── plot_speedup.png          # Speedup plots
│   └── task2/                   # Task-2 plotting outputs
├── prefetcher/                   # Prefetcher implementations and config variants
│   ├── dtlb_prefetcher.cc       # DTLB prefetcher
│   ├── itlb_prefetcher.cc       # ITLB prefetcher
│   ├── l1d_prefetcher.cc        # L1D prefetcher
│   ├── l1i_prefetcher.cc        # L1I prefetcher
│   ├── l2c_prefetcher.cc        # L2C prefetcher
│   ├── llc_prefetcher.cc        # LLC prefetcher
│   ├── stlb_prefetcher.cc       # STLB prefetcher
│   ├── spp.l1d_pref             # SPP prefetcher config
│   └── *.l1d_pref               # Other prefetcher config variants
├── replacement/                  # Replacement-policy implementations and configs
│   ├── base_replacement.cc      # Base replacement logic
│   ├── l1d_replacement.cc       # L1D replacement policy
│   ├── l2c_replacement.cc       # L2 replacement policy
│   ├── llc_replacement.cc       # LLC replacement policy
│   ├── dyn_irrip.l2c_repl      # Dynamic IRRIP policy config
│   ├── irrip.l2c_repl          # IRRIP policy config
│   ├── rrip.l2c_repl           # RRIP policy config
│   ├── lru.*.repl               # LRU policy configs
│   └── *.repl                   # Additional replacement-policy configs
├── results/                      # Simulation result files and reports
│   ├── README.md                # Results directory documentation
│   ├── raw/                     # Raw output files from experiments
│   ├── output_logs/             # Simulation logs and traces of execution
│   ├── summary.csv              # Aggregated result summary
│   └── task2/                   # Task-2 result artifacts
├── scripts/                      # Automation and analysis scripts
│   ├── README.md                # Script usage notes
│   ├── csv_to_latex.py          # CSV-to-LaTeX conversion helper
│   ├── extract_stats.py         # Extracts key metrics from simulation output
│   ├── gen_deliverables.py      # Deliverable generation utility
│   ├── make_plots.py            # Plot generation from CSV data
│   ├── parse_results.py         # Parses experiment outputs
│   ├── run_jobs.sh              # Executes simulation jobs
│   ├── run_matrix.sh            # Runs a sweep/matrix of configs
│   ├── run_sim.sh               # Runs a single simulation job
│   ├── task2_report.py          # Task-2 analysis/report script
│   └── sweep/                   # Sweep configuration files
├── src/                          # Main C++ implementation of the simulator
│   ├── block.cc                 # Block functionality implementation
│   ├── cache.cc                 # Cache implementation
│   ├── dram_controller.cc       # DRAM controller implementation
│   ├── main.cc                  # Simulator entry point
│   ├── ooo_cpu.cc               # Out-of-order CPU implementation
│   ├── page_table_walker.cc     # Page-walker logic
│   ├── uncore.cc                # Uncore subsystem implementation
│   └── ...                      # Remaining simulator source files
├── traces/                       # Input benchmark traces for simulation
│   ├── Trace1.gz                # Trace set 1
│   ├── Trace2.gz                # Trace set 2
│   ├── Trace3.gz                # Trace set 3
└── ...
```

This project is built around the standard ChampSim simulator layout: `src/` and `inc/` contain the core implementation, `replacement/` and `prefetcher/` define policy strategies, and `scripts/` plus `results/` handle benchmarking and reporting.

The traces are git-ignored as instructed.

# ChampSim

ChampSim is a trace-based simulator for microarchitecture research.

Useful trace links:
- Traces (access requires an LDAP ID): https://drive.google.com/drive/folders/1zYchkn-M1auZp_l5wRkIzAcDYPkNtW3H?usp=sharing
- ChampSim wiki: https://champsim.github.io/ChampSim/master/index.html

## Clone the repository

```bash
git clone https://github.com/Shivraj1906/PA2-CS683-2026.git
```

## Compile

To compile ChampSim, specify which config you to want use, such as baseline, spp, ipstride, irrip or dyn_irrip etc.

For example, `./build_champsim.sh baseline` builds a single-core processor with a hashed perceptron branch predictor, no L1D data prefetcher and LRU replacement policy at all cache levels.

Your binary will have different name for different configs. Custom name help distinguish binaries for different configuration.

```bash
./build_champsim.sh ${config_name}

./build_champsim.sh baseline

--Complied Binary: hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline
```

## Run simulation

```bash
./bin/[BINARY] -warmup_instructions [N_WARM] -simulation_instructions [N_SIM] -traces [TRACE_DIR]/[TRACE]
./bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline -warmup_instructions 25000000 -simulation_instructions 25000000 -traces ../traces/trace1.champsimtrace.xz
```

Where:
- `${BINARY}`: ChampSim binary compiled by `build_champsim.sh baseline` (example, `hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline`)
- `${N_WARM}`: number of instructions for the warmup period (25 million)
- `${N_SIM}`: number of instructions for the detailed simulation (25 million)
- `${TRACE_DIR}`: directory containing the trace (for example, `../traces/`)
- `${TRACE}`: name of the trace (for example, `trace1.champsimtrace.xz`)

## Evaluate the simulation

ChampSim measures IPC (instructions per cycle) as its main performance metric. It also prints other useful metrics at the end of each simulation.

## Install GCC 7 on Ubuntu

```bash
sudo apt update
sudo add-apt-repository ppa:ubuntu-toolchain-r/test
vim /etc/apt/sources.list
```

Update the last line with:

```bash
deb [arch=amd64] http://archive.ubuntu.com/ubuntu focal main universe
```

Then run:

```bash
sudo add-apt-repository ppa:ubuntu-toolchain-r/test
sudo apt-get install gcc-7
sudo apt-get install g++-7
sudo update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-7 0
sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-7 0
```

If GCC and G++ are already present in `/usr/bin`, configure the alternatives using:

```bash
sudo update-alternatives --config g++
sudo update-alternatives --config gcc
```

