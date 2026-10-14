#!/usr/bin/env python3
"""Make a LaTeX (booktabs) table for Summary.pdf from results/summary.csv.

usage: python3 scripts/csv_to_latex.py --tags baseline ipstride spp --cols ipc speedup l1d_load_mpki l1d_pf_acc l1d_coverage \
           --caption "Task 1B results" --label tab:t1 > results/table_task1.tex
       python3 scripts/csv_to_latex.py --tags baseline rrip irrip_c2d3p2e1w0 --cols ipc speedup l2c_load_mpki l2c_instr_mpki l2c_data_mpki --drop-ties --geomean
"""
import argparse, csv, sys, math
from collections import defaultdict

HEAD = {"ipc": "IPC", "speedup": "Speedup", "l1d_load_mpki": "L1D MPKI", "l1d_pf_acc": "L1D acc. (\\%)", "l1d_coverage": "L1D cov. (\\%)",
        "l2c_load_mpki": "L2C load MPKI", "l2c_data_mpki": "L2 data MPKI", "l2c_instr_mpki": "L2 instr. MPKI", "l2c_total_mpki": "L2C total MPKI",
        "llc_load_mpki": "LLC MPKI", "l1i_load_mpki": "L1I MPKI", "l2c_pf_acc": "L2 acc. (\\%)"}

ap = argparse.ArgumentParser()
ap.add_argument("--csv", default="results/summary.csv")
ap.add_argument("--tags", nargs="+", required=True)
ap.add_argument("--cols", nargs="+", required=True)
ap.add_argument("--caption", default="")
ap.add_argument("--label", default="tab:results")
ap.add_argument("--digits", type=int, default=4)
ap.add_argument("--drop-ties", action="store_true")
ap.add_argument("--geomean", action="store_true", help="Add a row for geometric mean across traces")
a = ap.parse_args()

rows = {(r["tag"], r["trace"]): r for r in csv.DictReader(open(a.csv))}
traces = sorted({t for _, t in rows})

if a.drop_ties:                       
    groups = defaultdict(list)
    for tg in {t for t, _ in rows}:
        if all((tg, t) in rows for t in traces):
            groups[tuple(tuple(sorted((k, v) for k, v in rows[(tg, t)].items() if k not in ("tag", "trace"))) for t in traces)].append(tg)
    tied = {tg for g in groups.values() if len(g) > 1 for tg in g}
    for tg in a.tags:
        if tg in tied: print("tie: left out %s" % tg, file=sys.stderr)
    a.tags = [tg for tg in a.tags if tg not in tied]

esc = lambda s: s.replace("_", "\\_").replace("+", "{+}")
def cell(v):
    try: return f"{float(v):.{a.digits}f}"
    except Exception: return "--"

def get_geomean(xs):
    valid = []
    for x in xs:
        if x is not None:
            try:
                v = float(x)
                if v > 0: valid.append(v)
            except ValueError:
                pass
    return math.exp(sum(math.log(x) for x in valid) / len(valid)) if valid else None

print("\\begin{table}[H]\\centering\\small")
print("\\begin{tabular}{ll" + "r" * len(a.cols) + "}\\toprule")
print("Trace & Config & " + " & ".join(HEAD.get(c, esc(c)) for c in a.cols) + " \\\\ \\midrule")

for i, t in enumerate(traces):
    for tg in a.tags:
        r = rows.get((tg, t))
        print(f"{t.replace('trace', 'Trace ')} & {esc(tg)} & " + " & ".join(cell(r.get(c)) if r else "--" for c in a.cols) + " \\\\")
    if i < len(traces) - 1 or a.geomean: print("\\midrule")

if a.geomean:
    for tg in a.tags:
        gm_cells = []
        for c in a.cols:
            xs = [rows.get((tg, t), {}).get(c) for t in traces]
            gm = get_geomean(xs)
            gm_cells.append(f"{gm:.{a.digits}f}" if gm is not None else "--")
        print(f"Geomean & {esc(tg)} & " + " & ".join(gm_cells) + " \\\\")

print("\\bottomrule\\end{tabular}")
print(f"\\caption{{{a.caption}}}\\label{{{a.label}}}\\end{{table}}")