#!/usr/bin/env python3
"""
Task 3 (SPP + dynamic I-RRIP): extract ChampSim stats, print/save tables, and generate plots.

Compares, on every trace:  baseline | spp | irrip | sppirrip
  baseline  no prefetcher, baseline replacement
  spp       SPP at L1D, baseline replacement
  irrip     no prefetcher, dynamic I-RRIP at L2C
  sppirrip  SPP at L1D + prefetch-aware dynamic I-RRIP at L2C

Expects logs named  <log-dir>/<config>_<trace>.log   (default: output_logs/spp_Trace1.log, ...)

Outputs
  plots/t3_<metric>.png      one grouped-bar plot per metric (traces + a geomean/mean group)
  plots/t3_<table>.tex       booktabs tables, ready for \\input{...}
  plots/t3_results.csv       every extracted/derived value
  console                    the same tables in plain text

Definitions
  speedup      IPC / IPC of baseline (same trace)
  coverage     (baseline load misses - load misses) / baseline load misses, at the given cache level.
               For irrip (no prefetcher) this is the miss reduction due to replacement alone.
  accuracy     ChampSim's "ACCURACY" line of the cache (useful / prefetches issued to the lower level);
               N/A for configurations without a prefetcher.
  aggregate    geometric mean over traces for IPC, speedup and MPKI; arithmetic mean for accuracy and coverage.
"""

import argparse
import csv
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CONFIGS = ["baseline", "spp", "irrip", "sppirrip"]
TRACES = ["Trace1", "Trace2", "Trace3"]

LABELS = {"baseline": "Baseline", "spp": "SPP", "irrip": "Dyn. I-RRIP", "sppirrip": "SPP + Dyn. I-RRIP"}
COLORS = {"baseline": "red", "spp": "green", "irrip": "orange", "sppirrip": "purple"}

# key -> (axis/column label, number format, aggregate kind)
METRICS = {
    "ipc":            ("IPC",                         "%.4f", "geo"),
    "speedup":        ("Speedup over baseline",       "%.4f", "geo"),
    "vs_spp":         ("IPC vs. SPP",                 "%.4f", "geo"),
    "vs_irrip":       ("IPC vs. Dyn. I-RRIP",         "%.4f", "geo"),
    "l1d_mpki":       ("L1D load MPKI",               "%.3f", "geo"),
    "l2c_mpki":       ("L2C load MPKI",               "%.3f", "geo"),
    "l2c_instr_mpki": ("L2C instruction-load MPKI",   "%.3f", "geo"),
    "l2c_data_mpki":  ("L2C data-load MPKI",          "%.3f", "geo"),
    "l1d_acc":        ("L1D prefetch accuracy (%)",   "%.2f", "arith"),
    "l2c_acc":        ("L2C prefetch accuracy (%)",   "%.2f", "arith"),
    "l1d_cov":        ("L1D load coverage (%)",       "%.2f", "arith"),
    "l2c_cov":        ("L2C load coverage (%)",       "%.2f", "arith"),
}

# metrics that get a plot (one file each)
PLOT_KEYS = ["ipc", "speedup", "l1d_acc", "l2c_acc", "l1d_cov", "l2c_cov",
             "l1d_mpki", "l2c_mpki", "l2c_instr_mpki", "l2c_data_mpki"]

# tables: name, caption, columns
TABLES = [
    ("perf", "IPC and speedup for the four configurations.",
     ["ipc", "speedup", "vs_spp", "vs_irrip"]),
    ("mpki", "Load MPKI at L1D and L2C (total, instruction and data).",
     ["l1d_mpki", "l2c_mpki", "l2c_instr_mpki", "l2c_data_mpki"]),
    ("pf", "Prefetch accuracy and load coverage at L1D and L2C (percent).",
     ["l1d_acc", "l2c_acc", "l1d_cov", "l2c_cov"]),
]


def fnum(s):
    """float(s), or None for -nan / nan / inf / missing."""
    try:
        v = float(s)
        return None if (math.isnan(v) or math.isinf(v)) else v
    except (TypeError, ValueError):
        return None


def ratio(a, b):
    return a / b if (a is not None and b not in (None, 0)) else None


# ------------------------------------------------------------------------------------------
# Extraction
# ------------------------------------------------------------------------------------------
def extract_metrics(path):
    text = Path(path).read_text(errors="replace")
    i = text.find("Region of Interest Statistics")
    roi = text[i:] if i >= 0 else text
    m = {}

    mm = re.search(r"CPU\s+0\s+cumulative IPC:\s+(\S+)", roi)
    m["ipc"] = fnum(mm.group(1)) if mm else None

    for cache, key in (("L1D", "l1d"), ("L2C", "l2c")):
        mm = re.search(rf"{cache} LOAD\s+ACCESS:\s+(\d+)\s+HIT:\s+(\d+)\s+MISS:\s+(\d+).*?MPKI:\s+(\S+)", roi)
        m[f"{key}_load_miss"] = int(mm.group(3)) if mm else None
        m[f"{key}_mpki"] = fnum(mm.group(4)) if mm else None

        mm = re.search(rf"{cache} USEFUL LOAD PREFETCHES:.*?ACCURACY:\s+(\S+)", roi)
        m[f"{key}_acc"] = fnum(mm.group(1)) if mm else None   # -nan (no prefetcher) -> None

    mm = re.search(r"L2C INSTRUCTION LOAD MPKI:\s+(\S+)", roi)
    m["l2c_instr_mpki"] = fnum(mm.group(1)) if mm else None
    mm = re.search(r"L2C DATA LOAD MPKI:\s+(\S+)", roi)
    m["l2c_data_mpki"] = fnum(mm.group(1)) if mm else None
    return m


def load_results(log_dir, traces):
    results = {}
    for cfg in CONFIGS:
        for t in traces:
            p = Path(log_dir) / f"{cfg}_{t}.log"
            if not p.exists():
                print(f"WARNING: {p} not found")
                continue
            results[(cfg, t)] = extract_metrics(p)
    return results


def derive(results, traces):
    for t in traces:
        base = results.get(("baseline", t))
        spp = results.get(("spp", t))
        irrip = results.get(("irrip", t))
        for cfg in CONFIGS:
            r = results.get((cfg, t))
            if r is None:
                continue
            r["speedup"] = ratio(r["ipc"], base["ipc"]) if base else None
            r["vs_spp"] = ratio(r["ipc"], spp["ipc"]) if spp else None
            r["vs_irrip"] = ratio(r["ipc"], irrip["ipc"]) if irrip else None
            for lvl in ("l1d", "l2c"):
                bm = base.get(f"{lvl}_load_miss") if base else None
                mi = r.get(f"{lvl}_load_miss")
                r[f"{lvl}_cov"] = 100.0 * (bm - mi) / bm if (bm and mi is not None) else None


def aggregate(vals, kind):
    """Aggregate over traces. Returns None if any trace is missing / N/A."""
    if not vals or any(v is None for v in vals):
        return None
    if kind == "geo":
        if any(v <= 0 for v in vals):
            return None
        return math.exp(sum(math.log(v) for v in vals) / len(vals))
    return sum(vals) / len(vals)


def series(results, cfg, key, traces):
    """Per-trace values followed by the aggregate."""
    vals = [results.get((cfg, t), {}).get(key) for t in traces]
    return vals + [aggregate(vals, METRICS[key][2])]


# ------------------------------------------------------------------------------------------
# Plots
# ------------------------------------------------------------------------------------------
def plot_metric(results, key, traces, plot_dir, zoom_speedup=True):
    label, fmt, agg = METRICS[key]
    groups = list(traces) + ["Geomean" if agg == "geo" else "Mean"]
    x = np.arange(len(groups))
    n = len(CONFIGS)
    width = 0.8 / n

    fig, ax = plt.subplots(figsize=(10, 5.2))
    all_vals = []
    for i, cfg in enumerate(CONFIGS):
        vals = series(results, cfg, key, traces)
        all_vals += [v for v in vals if v is not None]
        heights = [0.0 if v is None else v for v in vals]
        rects = ax.bar(x + (i - (n - 1) / 2) * width, heights, width, label=LABELS[cfg],
                       color=COLORS[cfg], edgecolor="grey")
        ax.bar_label(rects, labels=["N/A" if v is None else fmt % v for v in vals],
                     padding=2, fontsize=7, rotation=90)

    ax.set_ylabel(label)
    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.margins(y=0.18)
    # speedups differ in the 3rd-4th digit, so start the axis near 1.0 (the baseline bars are exactly 1.0);
    # this exaggerates the differences visually, the bar labels give the exact numbers
    if key == "speedup" and zoom_speedup and all_vals:
        lo, hi = min(all_vals + [1.0]), max(all_vals + [1.0])
        span = max(hi - lo, 0.004)
        ax.set_ylim(lo - 0.6 * span, hi + 0.9 * span)
        ax.axhline(1.0, color="red", linestyle="--", linewidth=1)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=n, frameon=False, fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)

    out = Path(plot_dir) / f"t3_{key}.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


# ------------------------------------------------------------------------------------------
# Tables
# ------------------------------------------------------------------------------------------
def esc(s):
    return s.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")


def table_rows(results, cols, traces):
    """Rows: (trace label, config, [formatted values]); last block is the aggregate over traces."""
    rows = []
    for t in list(traces) + ["agg"]:
        for cfg in CONFIGS:
            cells = []
            for k in cols:
                fmt = METRICS[k][1]
                vals = series(results, cfg, k, traces)
                v = vals[-1] if t == "agg" else results.get((cfg, t), {}).get(k)
                cells.append("N/A" if v is None else fmt % v)
            rows.append(("Mean" if t == "agg" else t, cfg, cells))
    return rows


def print_table(title, cols, rows):
    heads = [METRICS[k][0] for k in cols]
    w = max(14, max(len(h) for h in heads) + 1)
    line = "=" * (12 + 20 + w * len(cols))
    print(f"\n{title}")
    print(line)
    print(f"{'Trace':<12}{'Config':<20}" + "".join(f"{h:>{w}}" for h in heads))
    print(line)
    prev = None
    for t, cfg, cells in rows:
        if prev is not None and t != prev:
            print("-" * len(line))
        prev = t
        print(f"{t:<12}{LABELS[cfg]:<20}" + "".join(f"{c:>{w}}" for c in cells))
    print(line)


def write_latex(path, caption, label, cols, rows):
    heads = " & ".join(esc(METRICS[k][0]) for k in cols)
    lines = [r"\begin{table}[H]", r"\centering", r"\small", r"\setlength{\tabcolsep}{4pt}",
             r"\resizebox{\textwidth}{!}{%",
             r"\begin{tabular}{@{}ll" + "r" * len(cols) + r"@{}}", r"\toprule",
             r"\textbf{Trace} & \textbf{Configuration} & " + heads + r" \\", r"\midrule"]
    prev = None
    for t, cfg, cells in rows:
        if prev is not None and t != prev:
            lines.append(r"\midrule")
        shown = esc(t) if t != prev else ""
        prev = t
        lines.append(f"{shown} & {esc(LABELS[cfg])} & " + " & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}}",
              rf"\caption{{{caption}}}", rf"\label{{{label}}}", r"\end{table}"]
    Path(path).write_text("\n".join(lines) + "\n")


def write_csv(path, results, traces):
    keys = list(METRICS.keys())
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["config", "trace"] + keys)
        for cfg in CONFIGS:
            for t in traces:
                r = results.get((cfg, t))
                if r:
                    w.writerow([cfg, t] + ["" if r.get(k) is None else r.get(k) for k in keys])


# ------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log-dir", default="output_logs")
    ap.add_argument("--plot-dir", default="plots")
    ap.add_argument("--table-dir", default=None, help="default: same as --plot-dir")
    ap.add_argument("--traces", nargs="+", default=TRACES)
    ap.add_argument("--no-zoom", action="store_true", help="start the speedup axis at 0 instead of near 1.0")
    args = ap.parse_args()

    traces = args.traces
    plot_dir = Path(args.plot_dir)
    table_dir = Path(args.table_dir) if args.table_dir else plot_dir
    plot_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)

    results = load_results(args.log_dir, traces)
    if not results:
        raise SystemExit("no logs found")
    derive(results, traces)

    for name, caption, cols in TABLES:
        rows = table_rows(results, cols, traces)
        print_table(caption, cols, rows)
        write_latex(table_dir / f"t3_{name}.tex", caption, f"tab:t3-{name}", cols, rows)

    write_csv(plot_dir / "t3_results.csv", results, traces)

    print("\nPlots written:")
    for key in PLOT_KEYS:
        print("  ", plot_metric(results, key, traces, plot_dir, zoom_speedup=not args.no_zoom))
    print("\nTables written:", ", ".join(f"t3_{n}.tex" for n, _, _ in TABLES), "(in", table_dir, ")")
    print("CSV written:", plot_dir / "t3_results.csv")


if __name__ == "__main__":
    main()