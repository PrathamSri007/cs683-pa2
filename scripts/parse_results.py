#!/usr/bin/env python3
"""Turn ChampSim output files (results/raw/<tag>__<trace>.txt) into results/summary.csv and a table.

usage: python3 scripts/parse_results.py [--raw results/raw] [--out results/summary.csv] [--baseline baseline]
Derived columns (relative to the --baseline tag on the SAME trace):
  speedup      = IPC / IPC_baseline
  l1d_coverage = (L1D load misses_baseline - L1D load misses) / L1D load misses_baseline   (percent)
"""
import argparse, csv, glob, math, os, re, sys

NUM = r"(-?[\d.eE+-]+|-?nan|-?inf)"

def f(x):
    try:
        v = float(x)
        return None if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return None

def first(pattern, text, flags=re.M):
    m = re.search(pattern, text, flags)
    return m.groups() if m else None

def parse(path):
    t = open(path, errors="replace").read()
    r = {}
    g = first(r"^CPU 0 cumulative IPC: " + NUM + r" instructions: (\d+) cycles: (\d+)", t)
    r["ipc"] = f(g[0]) if g else None
    r["cycles"] = int(g[2]) if g else None
    for lvl in ("L1D", "L1I", "L2C", "LLC"):
        g = first(r"^%s LOAD\s+ACCESS:\s+(\d+)\s+HIT:\s+(\d+)\s+MISS:\s+(\d+).*MPKI:\s+%s" % (lvl, NUM), t)
        k = lvl.lower()
        r[k + "_load_access"], r[k + "_load_miss"], r[k + "_load_mpki"] = (
            (int(g[0]), int(g[2]), f(g[3])) if g else (None, None, None))
    g = first(r"^L2C DATA LOAD MPKI:\s+" + NUM, t);        r["l2c_data_mpki"] = f(g[0]) if g else None
    g = first(r"^L2C INSTRUCTION LOAD MPKI:\s+" + NUM, t); r["l2c_instr_mpki"] = f(g[0]) if g else None
    g = first(r"^L2C TOTAL .*MPKI:\s+" + NUM, t);          r["l2c_total_mpki"] = f(g[0]) if g else None
    # page-walk reads at the L2 (ITLB + DTLB walks); not part of the L2C LOAD / INSTRUCTION LOAD MPKI
    g = first(r"^L2C LOAD TRANSLATION .*MPKI:\s+" + NUM, t); r["l2c_trans_mpki"] = f(g[0]) if g else None
    for lvl in ("L1D", "L2C"):
        k = lvl.lower()
        g = first(r"^%s USEFUL LOAD PREFETCHES:\s+(\d+)\s+PREFETCH ISSUED TO LOWER LEVEL:\s+(\d+)\s+ACCURACY:\s+%s" % (lvl, NUM), t)
        r[k + "_pf_useful"], r[k + "_pf_lower"], r[k + "_pf_acc"] = (int(g[0]), int(g[1]), f(g[2])) if g else (None, None, None)
        g = first(r"^%s TIMELY PREFETCHES:\s+(\d+)\s+LATE PREFETCHES:\s+(\d+)" % lvl, t)
        r[k + "_pf_late"] = int(g[1]) if g else None
        g = first(r"^%s PREFETCH\s+REQUESTED:\s+(\d+)\s+ISSUED:\s+(\d+)" % lvl, t)
        r[k + "_pf_issued"] = int(g[1]) if g else None
    # L2C eviction mix (region of interest; reset at the end of warm-up): evidence for the Task 2 rationale
    for key, label in (("l2c_instr_evict_data", "Instructions Evicting Data"), ("l2c_data_evict_instr", "Data Evicting Instructions"),
                       ("l2c_instr_evict_instr", "Instructions Evicting Instructions"), ("l2c_data_evict_data", "Data Evicting Data")):
        g = first(r"^L2C %s (\d+)" % label, t)
        r[key] = int(g[0]) if g else None
    # Dynamic I-RRIP decision statistics (printed by dyn_irrip.l2c_repl at exit, ROI only)
    g = first(r"^DYN_IRRIP ROI epochs: (\d+) in I-RRIP mode: (\d+) pct_irrip: " + NUM, t)
    r["dyn_epochs"], r["dyn_pct_irrip"] = (int(g[0]), f(g[2])) if g else (None, None)
    g = first(r"^DYN_IRRIP ROI ratio\(%\) min: " + NUM + " avg: " + NUM + " max: " + NUM, t)
    r["dyn_ratio_min"], r["dyn_ratio_avg"], r["dyn_ratio_max"] = (f(g[0]), f(g[1]), f(g[2])) if g else (None, None, None)
    g = first(r"^DYN_IRRIP ROI switches: (\d+)", t);       r["dyn_switches"] = int(g[0]) if g else None
    # set-dueling variant only: misses (all / code) of the SRRIP and the I-RRIP leader group
    for grp, key in (("SRRIP", "srrip"), ("I-RRIP", "irrip")):
        g = first(r"^DYN_IRRIP ROI %s leader misses: (\d+) code: (\d+)" % grp, t)
        r["dyn_lmiss_" + key], r["dyn_lmiss_code_" + key] = (int(g[0]), int(g[1])) if g else (None, None)
    return r

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="results/raw")
    ap.add_argument("--out", default="results/summary.csv")
    ap.add_argument("--baseline", default="baseline")
    a = ap.parse_args()

    rows = []
    for p in sorted(glob.glob(os.path.join(a.raw, "*__*.txt"))):
        tag, trace = os.path.basename(p)[:-4].split("__", 1)
        r = parse(p); r["tag"] = tag; r["trace"] = trace
        rows.append(r)
    if not rows:
        sys.exit("no result files found in " + a.raw)

    base = {r["trace"]: r for r in rows if r["tag"] == a.baseline}
    for r in rows:
        b = base.get(r["trace"])
        r["speedup"] = r["ipc"] / b["ipc"] if b and b["ipc"] and r["ipc"] else None
        if b and b["l1d_load_miss"] and r["l1d_load_miss"] is not None:
            r["l1d_coverage"] = 100.0 * (b["l1d_load_miss"] - r["l1d_load_miss"]) / b["l1d_load_miss"]
        else:
            r["l1d_coverage"] = None

    cols = ["tag", "trace", "ipc", "speedup", "cycles",
            "l1d_load_mpki", "l1d_load_miss", "l1d_pf_acc", "l1d_pf_useful", "l1d_pf_lower", "l1d_pf_late", "l1d_pf_issued", "l1d_coverage",
            "l2c_load_mpki", "l2c_data_mpki", "l2c_instr_mpki", "l2c_total_mpki", "l2c_trans_mpki", "l2c_pf_acc", "l1i_load_mpki", "llc_load_mpki",
            "l2c_instr_evict_data", "l2c_data_evict_instr", "l2c_instr_evict_instr", "l2c_data_evict_data",
            "dyn_epochs", "dyn_pct_irrip", "dyn_ratio_min", "dyn_ratio_avg", "dyn_ratio_max", "dyn_switches",
            "dyn_lmiss_srrip", "dyn_lmiss_code_srrip", "dyn_lmiss_irrip", "dyn_lmiss_code_irrip"]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)

    def fmt(v, d=4):
        return "-" if v is None else (f"{v:.{d}f}" if isinstance(v, float) else str(v))
    show = ["tag", "trace", "ipc", "speedup", "l1d_load_mpki", "l1d_pf_acc", "l1d_coverage", "l2c_load_mpki", "l2c_data_mpki", "l2c_instr_mpki"]
    print("| " + " | ".join(show) + " |"); print("|" + "---|" * len(show))
    for r in rows:
        print("| " + " | ".join(fmt(r.get(c)) if c not in ("tag", "trace") else r[c] for c in show) + " |")
    # geometric-mean speedup per tag
    tags = sorted({r["tag"] for r in rows})
    print("\nGeomean speedup over", a.baseline, "(only tags with all traces):")
    for tg in tags:
        sp = [r["speedup"] for r in rows if r["tag"] == tg and r["speedup"]]
        if len(sp) == len(base) and sp:
            print(f"  {tg:28s} {math.exp(sum(map(math.log, sp)) / len(sp)):.4f}")
    print("\nwrote", a.out)

if __name__ == "__main__":
    main()
