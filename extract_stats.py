#!/usr/bin/env python3

import re
from pathlib import Path


WARMUP = 25_000_000
SIMULATION = 25_000_000

CONFIGS = ["baseline", "ipstride", "spp"]
TRACES = ["Trace1", "Trace2", "Trace3"]


def extract_metrics(filename):
    text = Path(filename).read_text(errors="replace")

    metrics = {}

    # ------------------------------------------------------------
    # IPC
    # ------------------------------------------------------------
    m = re.search(
        r"CPU\s+0\s+cumulative IPC:\s+([\d.eE+-]+)",
        text
    )
    if m:
        metrics["ipc"] = float(m.group(1))
    else:
        metrics["ipc"] = None

    # ------------------------------------------------------------
    # L1D LOAD statistics
    #
    # Example:
    # L1D LOAD ACCESS: 4276668 HIT: 4009718 MISS: 266950
    #     ... MPKI: 10.678
    # ------------------------------------------------------------
    m = re.search(
        r"L1D LOAD\s+ACCESS:\s+(\d+)"
        r"\s+HIT:\s+(\d+)"
        r"\s+MISS:\s+(\d+)"
        r".*?MPKI:\s+([\d.eE+-]+)",
        text
    )

    if m:
        metrics["l1d_load_access"] = int(m.group(1))
        metrics["l1d_load_hit"] = int(m.group(2))
        metrics["l1d_load_miss"] = int(m.group(3))
        metrics["l1d_mpki"] = float(m.group(4))
    else:
        metrics["l1d_load_access"] = None
        metrics["l1d_load_hit"] = None
        metrics["l1d_load_miss"] = None
        metrics["l1d_mpki"] = None

    # ------------------------------------------------------------
    # L1D prefetch accuracy
    #
    # Example:
    # L1D USEFUL LOAD PREFETCHES: 1780
    # PREFETCH ISSUED TO LOWER LEVEL: 2497
    # ACCURACY: 71.2855
    # ------------------------------------------------------------
    m = re.search(
        r"L1D USEFUL LOAD PREFETCHES:.*?"
        r"ACCURACY:\s+([-\w.]+)",
        text
    )

    if m:
        value = m.group(1)

        if value.lower() in ["-nan", "nan", "inf", "-inf"]:
            metrics["l1d_prefetch_accuracy"] = None
        else:
            metrics["l1d_prefetch_accuracy"] = float(value)
    else:
        metrics["l1d_prefetch_accuracy"] = None

    return metrics


# ================================================================
# Read all logs
# ================================================================

results = {}

for config in CONFIGS:
    for trace in TRACES:

        filename = f"output_logs/{config}_{trace}.log"

        if not Path(filename).exists():
            print(f"WARNING: {filename} not found")
            continue

        results[(config, trace)] = extract_metrics(filename)


# ================================================================
# Calculate L1D coverage
# ================================================================

for trace in TRACES:

    baseline = results.get(("baseline", trace))

    if baseline is None:
        continue

    baseline_misses = baseline["l1d_load_miss"]

    for config in CONFIGS:

        result = results.get((config, trace))

        if result is None:
            continue

        if config == "baseline":
            # By definition, baseline has zero coverage
            result["l1d_coverage"] = 0.0

        elif (
            baseline_misses is not None
            and result["l1d_load_miss"] is not None
            and baseline_misses != 0
        ):
            result["l1d_coverage"] = (
                (baseline_misses - result["l1d_load_miss"])
                / baseline_misses
            )

        else:
            result["l1d_coverage"] = None


# ================================================================
# Print results
# ================================================================

print()
print("=" * 95)
print(
    f"{'Configuration':<12}"
    f"{'Trace':<10}"
    f"{'IPC':>10}"
    f"{'L1D MPKI':>12}"
    f"{'L1D Pref Acc (%)':>16}"
    f"{'L1D Coverage (%)':>16}"
)
print("=" * 95)

for trace in TRACES:
    for config in CONFIGS:
        result = results.get((config, trace))

        if result is None:
            continue

        def fmt(value, digits=4):
            if value is None:
                return "N/A"
            return f"{value:.{digits}f}"

        print(
            f"{config:<12}"
            f"{trace:<10}"
            f"{fmt(result['ipc'], 4):>10}"
            f"{fmt(result['l1d_mpki'], 4):>12}"
            f"{fmt(result['l1d_prefetch_accuracy'], 4):>16}"
            f"{fmt(None if result['l1d_coverage'] is None else result['l1d_coverage'] * 100, 4):>16}"
        )

print("=" * 95)