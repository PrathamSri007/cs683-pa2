#!/usr/bin/env python3
"""Grouped bar chart (x = trace, one bar per config) from results/summary.csv, in the style of the PDF's examples.

usage: python3 scripts/make_plots.py --metric speedup --tags rrip irrip_c2d3p2e1w0 --out plots/t2_speedup.png --geomean
"""
import argparse, csv, os, sys, math
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ap = argparse.ArgumentParser()
ap.add_argument("--csv", default="results/summary.csv")
ap.add_argument("--metric", required=True)
ap.add_argument("--tags", nargs="+", required=True)
ap.add_argument("--labels", nargs="+")
ap.add_argument("--out", required=True)
ap.add_argument("--title", default="")
ap.add_argument("--ylabel", default=None)
ap.add_argument("--hline", type=float, default=None)
ap.add_argument("--ymin", type=float, default=None)
ap.add_argument("--ymax", type=float, default=None)
ap.add_argument("--drop-ties", action="store_true")
ap.add_argument("--geomean", action="store_true", help="Add a group for geometric mean across traces")
a = ap.parse_args()

rows = list(csv.DictReader(open(a.csv)))
traces = sorted({r["trace"] for r in rows})
val = {(r["tag"], r["trace"]): (float(r[a.metric]) if r.get(a.metric) not in (None, "") else None) for r in rows}
labels = a.labels or a.tags

if a.drop_ties:                      
    raw = {(r["tag"], r["trace"]): tuple(sorted((k, v) for k, v in r.items() if k not in ("tag", "trace"))) for r in rows}
    groups = defaultdict(list)
    for tg in {t for t, _ in raw}:
        if all((tg, t) in raw for t in traces):
            groups[tuple(raw[(tg, t)] for t in traces)].append(tg)
    tied = {tg for g in groups.values() if len(g) > 1 for tg in g}
    pairs = [(tg, lb) for tg, lb in zip(a.tags, labels) if tg not in tied]
    for tg in a.tags:
        if tg in tied: print("tie: left out %s" % tg, file=sys.stderr)
    a.tags, labels = [p[0] for p in pairs], [p[1] for p in pairs]
    if not a.tags: sys.exit("no tags left after removing ties")

def get_geomean(xs):
    valid = [x for x in xs if x is not None and x > 0]
    return math.exp(sum(math.log(x) for x in valid) / len(valid)) if valid else None

plot_traces = traces + (["Geomean"] if a.geomean else [])
palette = ["#e8837f", "#6f87c0", "#8fc7a0", "#c9a45c", "#9c7fbf", "#6bb7c9", "#b0b0b0",
           "#d98cb3", "#b5cf6b", "#8c6d31", "#17becf", "#ad494a", "#7b4173", "#637939"]
many = len(a.tags) > 6                

fig, ax = plt.subplots(figsize=(min(15, max(7.5, 1.0 + 0.45 * len(a.tags) * len(plot_traces))), 4.5 + (0.8 if many else 0)))
w = 0.8 / len(a.tags)

for i, (tg, lb) in enumerate(zip(a.tags, labels)):
    xs = [j + (i - (len(a.tags) - 1) / 2) * w for j in range(len(plot_traces))]
    ys = [val.get((tg, t)) for t in traces]
    if a.geomean:
        ys.append(get_geomean(ys))
    
    ys0 = [y or 0 for y in ys]
    bars = ax.bar(xs, ys0, w, label=lb, color=palette[i % len(palette)], edgecolor="#555", linewidth=0.5)
    for b, y in zip(bars, ys):
        if y is not None:
            ax.annotate(f"{y:.3g}", (b.get_x() + b.get_width() / 2, y), ha="center", va="bottom",
                        fontsize=5.5 if many else 7, rotation=90 if many else 0)

if a.hline is not None:
    ax.axhline(a.hline, color="red", linestyle="--", linewidth=1, label="Baseline")

ax.set_xticks(range(len(plot_traces)))
ax.set_xticklabels([t.replace("trace", "Trace ") for t in plot_traces])
ax.set_ylabel(a.ylabel or a.metric); ax.set_title(a.title)
if a.ymin is not None or a.ymax is not None: ax.set_ylim(a.ymin, a.ymax)
elif many: ax.margins(y=0.15)
ax.legend(fontsize=8, ncol=2 if len(a.tags) > 4 else 1); ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
fig.savefig(a.out, dpi=160)
print("wrote", a.out)