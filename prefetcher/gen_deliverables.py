#!/usr/bin/env python3

import re
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

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
# Calculate L1D coverage & Speedup
# ================================================================

for trace in TRACES:
    baseline = results.get(("baseline", trace))
    ipstride = results.get(("ipstride", trace))

    if baseline is None:
        continue

    baseline_misses = baseline["l1d_load_miss"]
    baseline_ipc = baseline["ipc"]
    
    if ipstride:
        ipstride_ipc = ipstride["ipc"]

    for config in CONFIGS:
        result = results.get((config, trace))
        if result is None:
            continue

        if config == "baseline":
            result["l1d_coverage"] = 0.0
        elif (
            baseline_misses is not None
            and result["l1d_load_miss"] is not None
            and baseline_misses != 0
        ):
            result["l1d_coverage"] = (baseline_misses - result["l1d_load_miss"]) / baseline_misses
        else:
            result["l1d_coverage"] = None
            
        result["baseline_speedup"] = result["ipc"] / baseline_ipc if baseline_ipc else None
        if ipstride and ipstride_ipc:
            result["ipstride_speedup"] = result["ipc"] / ipstride_ipc


# ================================================================
# Print results
# ================================================================

print()
print("=" * 95)
print(
    f"{'Configuration':<12}"
    f"{'Trace':<10}"
    f"{'IPC':>8}"
    f"{'Speedup':>10}"
    f"{'L1D MPKI':>12}"
    f"{'L1D Pref Acc (%)':>20}"
    f"{'L1D Coverage (%)':>20}"
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
            f"{fmt(result['baseline_speedup'], 4):>10}"
            f"{fmt(result['l1d_mpki'], 4):>12}"
            f"{fmt(result['l1d_prefetch_accuracy'], 4):>16}"
            f"{fmt(None if result['l1d_coverage'] is None else result['l1d_coverage'] * 100, 4):>16}"
        )
print("=" * 95)


# ================================================================
# Generate Plots
# ================================================================

def get_metric_list(config, metric_key, scale=1.0):
    vals = []
    for t in TRACES:
        res = results.get((config, t))
        if res and res.get(metric_key) is not None:
            vals.append(res[metric_key] * scale)
        else:
            vals.append(0)  # Default/fallback
    return vals

x = np.arange(len(TRACES))
width = 0.25

# 1. Speedup Plot
fig, ax = plt.subplots(figsize=(8, 5))
sp_ip = get_metric_list("ipstride", "baseline_speedup")
sp_spp = get_metric_list("spp", "baseline_speedup")

rects1 = ax.bar(x - width/2, sp_ip, width, label='IP-stride', color='blue', edgecolor='grey')
rects2 = ax.bar(x + width/2, sp_spp, width, label='SPP', color='green', edgecolor='grey')
ax.axhline(1.0, color='red', linestyle='--', label='Baseline')

ax.bar_label(rects1, padding=3, fmt='%.4f', fontsize=9)
ax.bar_label(rects2, padding=3, fmt='%.4f', fontsize=9)

ax.set_ylabel('Speedup')
ax.set_title('Speedup of L1D Prefetchers over Baseline(no prefetching)')
ax.set_xticks(x)
ax.set_xticklabels(TRACES)
if sp_ip and sp_spp:
    ax.set_ylim(bottom=min(min(sp_ip), min(sp_spp)) * 0.95, top=max(max(sp_ip), max(sp_spp)) * 1.05)
ax.legend()
plt.tight_layout()
plt.savefig('plots/plot_speedup.png')
plt.close()

# 2. MPKI Plot
fig, ax = plt.subplots(figsize=(8, 5))
mpki_base = get_metric_list("baseline", "l1d_mpki")
mpki_ip = get_metric_list("ipstride", "l1d_mpki")
mpki_spp = get_metric_list("spp", "l1d_mpki")

rects1 = ax.bar(x - width, mpki_base, width, label='Baseline', color='red', edgecolor='grey')
rects2 = ax.bar(x, mpki_ip, width, label='IP-stride', color='blue', edgecolor='grey')
rects3 = ax.bar(x + width, mpki_spp, width, label='SPP', color='green', edgecolor='grey')

ax.bar_label(rects1, padding=3, fmt='%.2f', fontsize=9)
ax.bar_label(rects2, padding=3, fmt='%.2f', fontsize=9)
ax.bar_label(rects3, padding=3, fmt='%.2f', fontsize=9)

ax.set_ylabel('L1D MPKI')
ax.set_xlabel('Traces')
ax.set_xticks(x)
ax.set_xticklabels(TRACES)
if mpki_spp:
    ax.set_ylim(bottom=min(mpki_spp) * 0.8, top=max(max(mpki_base), max(mpki_ip), max(mpki_spp)) * 1.05)
ax.legend()
plt.tight_layout()
plt.savefig('plots/plot_mpki.png')
plt.close()

# 3. Accuracy Plot
fig, ax = plt.subplots(figsize=(8, 5))
acc_ip = get_metric_list("ipstride", "l1d_prefetch_accuracy")
acc_spp = get_metric_list("spp", "l1d_prefetch_accuracy")

rects1 = ax.bar(x - width/2, acc_ip, width, label='IP-stride', color='blue', edgecolor='grey')
rects2 = ax.bar(x + width/2, acc_spp, width, label='SPP', color='green', edgecolor='grey')

ax.bar_label(rects1, padding=3, fmt='%.1f', fontsize=9)
ax.bar_label(rects2, padding=3, fmt='%.1f', fontsize=9)

ax.set_ylabel('L1D Prefetch Accuracy (%)')
ax.set_xticks(x)
ax.set_xticklabels(TRACES)
if acc_ip and acc_spp:
    ax.set_ylim(bottom=min(min(acc_ip), min(acc_spp)) * 0.9, top=max(max(acc_ip), max(acc_spp)) * 1.05)
ax.legend()
plt.tight_layout()
plt.savefig('plots/plot_accuracy.png')
plt.close()

# 4. Coverage Plot
fig, ax = plt.subplots(figsize=(8, 5))
cov_ip = get_metric_list("ipstride", "l1d_coverage", scale=100.0)
cov_spp = get_metric_list("spp", "l1d_coverage", scale=100.0)

rects1 = ax.bar(x - width/2, cov_ip, width, label='IP-stride', color='blue', edgecolor='grey')
rects2 = ax.bar(x + width/2, cov_spp, width, label='SPP', color='green', edgecolor='grey')

ax.bar_label(rects1, padding=3, fmt='%.1f', fontsize=9)
ax.bar_label(rects2, padding=3, fmt='%.1f', fontsize=9)

ax.set_ylabel('L1D Prefetch Coverage (%)')
ax.set_xticks(x)
ax.set_xticklabels(TRACES)
if cov_ip and cov_spp:
    ax.set_ylim(bottom=min(min(cov_ip), min(cov_spp)) * 0.9, top=max(max(cov_ip), max(cov_spp)) * 1.05)
ax.legend()
plt.tight_layout()
plt.savefig('plots/plot_coverage.png')
plt.close()

print("\nPlots generated and saved as PNGs:")
print("- plot_speedup.png")
print("- plot_mpki.png")
print("- plot_accuracy.png")
print("- plot_coverage.png")