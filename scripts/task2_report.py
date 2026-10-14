#!/usr/bin/env python3
"""Task 2 (2A I-RRIP, 2B Dynamic I-RRIP): tables and plots for summary_src/task2_summary.tex."""
import argparse, csv, math, os, re
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TRACES = ["trace1", "trace2", "trace3"]

# ---- configuration names: change these two lines if the choice of "chosen" configurations changes ----
CHOSEN_IRRIP = "irrip_c2d3p2e1w0"   # static I-RRIP used as "the" I-RRIP
DYN_DEFAULT = "dyn_irrip_th25"      # default dynamic I-RRIP (threshold 25%, 128 leaders based on LEADER_LOG2=7, epoch 1024)

IRRIP_RE = re.compile(r"irrip_c[0-3]d[0-3]p[0-3]e[01]w[01]")

# ---- Separated Refinements ----
HINT_MODS = [("dyn_irrip_hyst5", "Hint formula + hysteresis 5%")]
MISS_SHARE = [("dyn_irrip_miss50", "Miss share mode (threshold 50%)")]
SET_DUEL = [("dyn_irrip_duel", "Set dueling (PSEL)"), ("dyn_irrip_duelw2", "Set dueling (Code x2)")]

MPKI = ["l2c_load_mpki", "l2c_instr_mpki", "l2c_data_mpki"]
MPKI_NAMES = ["L2C load MPKI", "L2 instruction load MPKI", "L2 data load MPKI"]

COLS = {"ipc": "IPC", "speedup": "Speedup", "speedup_rrip": "vs RRIP", "l2c_total_mpki": "L2C total MPKI",
        "l2c_load_mpki": "L2C load MPKI", "l2c_instr_mpki": "L2 instr. MPKI", "l2c_data_mpki": "L2 data MPKI",
        "l1i_load_mpki": "L1I MPKI", "l2c_trans_mpki": "L2 page-walk MPKI", "dyn_switches": "switches",
        "l2c_instr_evict_data": "Instr. evicts data", "l2c_data_evict_instr": "Data evicts instr.",
        "dyn_pct_irrip": "I-RRIP epochs (\\%)", "dyn_ratio_min": "ratio min (\\%)", "dyn_ratio_avg": "ratio avg (\\%)",
        "dyn_ratio_max": "ratio max (\\%)"}
DIGITS = {"ipc": 4, "speedup": 4, "speedup_rrip": 4, "l2c_instr_evict_data": 0, "l2c_data_evict_instr": 0,
          "dyn_pct_irrip": 1, "dyn_ratio_min": 1, "dyn_ratio_avg": 1, "dyn_ratio_max": 1, "dyn_switches": 0}
PALETTE = ["#8fc7a0", "#c9a45c", "#9c7fbf", "#6bb7c9", "#d98cb3", "#e0b0a0", "#a0a0d8",
           "#b5cf6b", "#8c6d31", "#17becf", "#bcbd22", "#ad494a", "#7b4173", "#637939"]
FIXED = {"baseline": "#d0d0d0", "rrip": "#7f7f7f", CHOSEN_IRRIP: "#e8837f", DYN_DEFAULT: "#6f87c0"}   

TIES = {"dropped": set(), "alias": {}}     

def num(v):
    try:
        x = float(v)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None

def load(path):
    data, raw = {}, {}
    for r in csv.DictReader(open(path)):
        data[(r["tag"], r["trace"])] = {k: num(v) for k, v in r.items() if k not in ("tag", "trace")}
        raw[(r["tag"], r["trace"])] = tuple(sorted((k, v) for k, v in r.items() if k not in ("tag", "trace")))
    for (tag, tr), r in data.items():                       
        b = data.get(("rrip", tr))
        r["speedup_rrip"] = r["ipc"] / b["ipc"] if b and b.get("ipc") and r.get("ipc") else None
    return data, raw

def find_ties(raw):
    sig = {}
    for tag in {t for t, _ in raw}:
        if all((tag, tr) in raw for tr in TRACES):
            sig[tag] = tuple(raw[(tag, tr)] for tr in TRACES)
    groups = defaultdict(list)
    for tag, s in sig.items():
        groups[s].append(tag)
    return [sorted(g) for g in groups.values() if len(g) > 1]

def apply_tie_policy(raw, mode):
    TIES["dropped"], TIES["alias"] = set(), {}
    groups = find_ties(raw)
    for g in groups:
        print("  tie: " + " = ".join(g))
        if mode == "off":
            continue
        if mode == "auto" and DYN_DEFAULT in g:             
            TIES["alias"].update({t: DYN_DEFAULT for t in g if t != DYN_DEFAULT})
            print("       kept once as %s (same default run, other names are aliases)" % DYN_DEFAULT)
        else:
            TIES["dropped"].update(g)
            print("       left out of all tables and plots")
    if not groups:
        print("  no tied tags found")

def present(data, tags):
    keep, seen = [], set()
    for t, l in tags:
        t = TIES["alias"].get(t, t)
        if t in TIES["dropped"]:
            continue
        if not all((t, tr) in data for tr in TRACES):
            print("  (no complete results for %s: left out)" % t)
            continue
        if t not in seen:
            seen.add(t)
            keep.append((t, l))
    return keep

def geomean(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs and all(x and x > 0 for x in xs) else None

def esc(s):
    return s.replace("_", "\\_").replace("%", "\\%")

def table(data, tags, cols, path, caption, label, geo=("speedup", "speedup_rrip", "ipc", "l2c_load_mpki", "l2c_instr_mpki", "l2c_data_mpki", "l2c_total_mpki")):
    if not tags: return
    with open(path, "w") as fh:
        fh.write("\\begin{table}[H]\\centering\\small\n\\ifdefined\\fitbx\\else\\newsavebox{\\fitbx}\\fi\n\\sbox{\\fitbx}{\\begin{tabular}{ll" + "r" * len(cols) + "}\\toprule\n")
        fh.write("Trace & Configuration & " + " & ".join(COLS.get(c, esc(c)) for c in cols) + " \\\\ \\midrule\n")
        rows = TRACES + ["geomean"]
        for i, tr in enumerate(rows):
            for tag, lab in tags:
                cells = []
                for c in cols:
                    if tr == "geomean":
                        v = geomean([data[(tag, t)].get(c) for t in TRACES]) if c in geo else None
                    else:
                        v = data[(tag, tr)].get(c)
                    cells.append("--" if v is None else "%.*f" % (DIGITS.get(c, 3), v))
                name = "Geomean" if tr == "geomean" else tr.replace("trace", "Trace ")
                fh.write("%s & %s & %s \\\\\n" % (name, esc(lab), " & ".join(cells)))
            if i < len(rows) - 1: fh.write("\\midrule\n")
        fh.write("\\bottomrule\n\\end{tabular}}\n\\ifdim\\wd\\fitbx>\\linewidth\\resizebox{\\linewidth}{!}{\\usebox{\\fitbx}}\\else\\usebox{\\fitbx}\\fi\n\\caption{%s}\\label{%s}\n\\end{table}\n" % (caption, label))
    print("wrote", path)

def bars(data, tags, metric, path, title, ylabel, hline=None, with_geo=False, hline_label="Baseline (LRU)"):
    if not tags: return
    xs_names = TRACES + (["geomean"] if with_geo else [])
    many = len(tags) > 6                                      
    fig, ax = plt.subplots(figsize=(min(15, max(7.5, 1.0 + 0.45 * len(tags) * len(xs_names))), 4.5 + (0.8 if many else 0)))
    w = 0.8 / len(tags)
    for i, (tag, lab) in enumerate(tags):
        ys = [data[(tag, t)].get(metric) for t in TRACES]
        if with_geo: ys.append(geomean(ys))
        xs = [j + (i - (len(tags) - 1) / 2) * w for j in range(len(xs_names))]
        ys0 = [y or 0 for y in ys]
        bs = ax.bar(xs, ys0, w, label=lab, color=FIXED.get(tag, PALETTE[sum(1 for t, _ in tags[:i] if t not in FIXED) % len(PALETTE)]), edgecolor="#555", linewidth=0.5)
        for b, y in zip(bs, ys):
            if y is not None:
                ax.annotate(("%.3f" if metric.startswith("speedup") else "%.3g") % y, (b.get_x() + b.get_width() / 2, y),
                            ha="center", va="bottom", fontsize=5.5 if many else 6.5, rotation=90 if many else 0)
    if hline is not None:
        ax.axhline(hline, color="red", linestyle="--", linewidth=1, label=hline_label)
        lo = min(data[(t, tr)].get(metric) or hline for t, _ in tags for tr in TRACES)
        hi = max(data[(t, tr)].get(metric) or hline for t, _ in tags for tr in TRACES)
        pad = max(0.01, (max(hi, hline) - min(lo, hline)) * (0.45 if many else 0.25))
        ax.set_ylim(min(lo, hline) - pad, max(hi, hline) + pad)   
    elif many: ax.margins(y=0.15)
    ax.set_xticks(range(len(xs_names)))
    ax.set_xticklabels([n.replace("trace", "Trace ").replace("geomean", "Geomean") for n in xs_names])
    ax.set_ylabel(ylabel); ax.set_title(title); ax.grid(axis="y", alpha=0.3)
    ax.legend(fontsize=7, ncol=2 if len(tags) > 4 else 1)
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)
    print("wrote", path)

def sweep_tags(data, prefix, label_fmt):
    found = sorted({t for t, _ in data if re.fullmatch(re.escape(prefix) + r"\d+", t)}, key=lambda t: int(t[len(prefix):]))
    out = []
    for t in found:
        lab = label_fmt % int(t[len(prefix):])
        if t == DYN_DEFAULT or TIES["alias"].get(t) == DYN_DEFAULT:     
            lab += " (default)"
        out.append((t, lab))
    return out

def irrip_variants(data):
    def score(tag):
        r = [data[(tag, t)]["l2c_instr_mpki"] / data[("baseline", t)]["l2c_instr_mpki"] for t in TRACES]
        return geomean(r)
    tags = sorted({t for t, _ in data if IRRIP_RE.fullmatch(t) and all((t, tr) in data for tr in TRACES)})
    if all(("baseline", tr) in data for tr in TRACES):
        tags.sort(key=lambda t: score(t) or 9e9)
    return [(t, t[len("irrip_"):] + (" (chosen)" if t == CHOSEN_IRRIP else "")) for t in tags]

def plots_for(d, tags, prefix, P, name, with_geo=True, speedup_tags=None):
    bars(d, speedup_tags or tags, "speedup", P + "/%s_speedup.png" % prefix, name + ": speedup over baseline (LRU)", "Speedup", hline=1.0, with_geo=with_geo)
    bars(d, tags, "ipc", P + "/%s_ipc.png" % prefix, name + ": IPC", "IPC", with_geo=with_geo)
    for m, nm in zip(MPKI, MPKI_NAMES):
        bars(d, tags, m, P + "/%s_%s.png" % (prefix, m), name + ": " + nm, "MPKI", with_geo=with_geo)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="results/summary.csv")
    ap.add_argument("--tables", default="results/task2")
    ap.add_argument("--plots", default="plots/task2")
    ap.add_argument("--ties", choices=["auto", "drop", "off"], default="auto")
    a = ap.parse_args()
    os.makedirs(a.tables, exist_ok=True); os.makedirs(a.plots, exist_ok=True)
    d, raw = load(a.csv)
    apply_tie_policy(raw, a.ties)
    T, P = a.tables, a.plots
    REF = [("baseline", "Baseline (LRU)"), ("rrip", "SRRIP")]
    CH = [(CHOSEN_IRRIP, "I-RRIP (chosen: %s)" % CHOSEN_IRRIP[len("irrip_"):])]

    # ---------------- Task 2A ----------------
    main2a = present(d, REF + CH)
    table(d, main2a, ["ipc", "speedup", "speedup_rrip"] + MPKI, T + "/t2a_main.tex",
          "Task 2A: IPC, speedup (over the LRU baseline and over SRRIP) and L2 load MPKI (L2C, instruction, data).", "tab:t2a_main")
    plots_for(d, main2a, "t2a", P, "Task 2A: Main")

    abl_var = present(d, irrip_variants(d))                  
    abl = present(d, REF) + abl_var
    table(d, abl, ["ipc", "speedup", "speedup_rrip"] + MPKI + ["l2c_trans_mpki", "l2c_instr_evict_data", "l2c_data_evict_instr"], T + "/t2a_all_tests.tex",
          "All static I-RRIP variants ordered by L2 instruction load MPKI reduction.", "tab:t2a_all_tests")
    plots_for(d, abl, "t2a_all_tests", P, "Static I-RRIP variants", speedup_tags=[x for x in abl if x[0] != "baseline"])
    bars(d, [x for x in abl if x[0] != "baseline"], "speedup_rrip", P + "/t2a_all_tests_speedup_rrip.png", "Static I-RRIP variants: speedup over SRRIP",
         "Speedup over SRRIP", hline=1.0, with_geo=True, hline_label="SRRIP")

    # ---------------- Task 2B ----------------
    main2b_tags = present(d, REF + CH + [(DYN_DEFAULT, "Dynamic I-RRIP (default)")])
    table(d, main2b_tags, ["ipc", "speedup", "speedup_rrip"] + MPKI, T + "/t2b_main.tex",
          "Task 2B: Dynamic I-RRIP (default parameters) against SRRIP and Static I-RRIP.", "tab:t2b_main")
    plots_for(d, main2b_tags, "t2b", P, "Task 2B: Main")

    dyn = present(d, [(DYN_DEFAULT, "Dynamic I-RRIP (default)")])
    table(d, dyn, ["dyn_pct_irrip", "dyn_switches", "dyn_ratio_min", "dyn_ratio_avg", "dyn_ratio_max"], T + "/t2b_ratio.tex",
          "Task 2B: instruction-share ratio parameters.", "tab:t2b_ratio", geo=())

    # Sweeps
    for prefix, fmt, name, key in (("dyn_irrip_th", "threshold %d%%", "threshold", "thresh"),
                                   ("dyn_irrip_ldr", "%d leader sets", "leader-set count", "leaders"),
                                   ("dyn_irrip_ep", "epoch %d", "epoch length", "epoch")):
        sw = present(d, sweep_tags(d, prefix, fmt))
        if sw:
            ref = present(d, [("rrip", "SRRIP")] + CH)
            table(d, ref + sw, ["ipc", "speedup", "speedup_rrip"] + MPKI + ["dyn_pct_irrip", "dyn_ratio_avg"], T + "/t2b_%s.tex" % key,
                  "Task 2B sensitivity to the %s (SRRIP and I-RRIP shown for reference)." % name, "tab:t2b_%s" % key)
            plots_for(d, ref + sw, "t2b_%s" % key, P, "Dynamic I-RRIP: %s sensitivity" % name)

    # ---------------- Refinements & Variants ----------------
    hint_tags = present(d, [(DYN_DEFAULT, "Hint (Default)")] + HINT_MODS)
    if len(hint_tags) > 1:
        table(d, main2b_tags + present(d, HINT_MODS), ["ipc", "speedup", "speedup_rrip"] + MPKI + ["dyn_pct_irrip", "dyn_switches"], T + "/t2b_hint_mods.tex",
              "Task 2B: Refinement strictly modifying the hint formula condition (Hysteresis).", "tab:t2b_hint")
        plots_for(d, main2b_tags + present(d, HINT_MODS), "t2b_hint_mods", P, "Dynamic I-RRIP: Hint Formula Mods")

    share_tags = present(d, [(DYN_DEFAULT, "Hint (Default)")] + MISS_SHARE)
    if len(share_tags) > 1:
        table(d, main2b_tags + present(d, MISS_SHARE), ["ipc", "speedup", "speedup_rrip"] + MPKI + ["dyn_pct_irrip", "dyn_switches"], T + "/t2b_miss_share.tex",
              "Task 2B: Alternative Miss-share mode compared against default hint.", "tab:t2b_share")
        plots_for(d, main2b_tags + present(d, MISS_SHARE), "t2b_miss_share", P, "Dynamic I-RRIP: Miss Share Mode")

    duel_tags = present(d, [(DYN_DEFAULT, "Hint (Default)")] + SET_DUEL)
    if len(duel_tags) > 1:
        table(d, main2b_tags + present(d, SET_DUEL), ["ipc", "speedup", "speedup_rrip"] + MPKI + ["dyn_pct_irrip", "dyn_switches"], T + "/t2b_set_duel.tex",
              "Task 2B: True Set Dueling logic compared to the default hint formula.", "tab:t2b_duel")
        plots_for(d, main2b_tags + present(d, SET_DUEL), "t2b_set_duel", P, "Dynamic I-RRIP: Set Dueling")

    # ---------------- Overall Comparative Summary ----------------
    overall = present(d, REF + CH + [(DYN_DEFAULT, "Dynamic (Default)")] + HINT_MODS + MISS_SHARE + SET_DUEL)
    if len(overall) > len(REF + CH):
        table(d, overall, ["ipc", "speedup", "speedup_rrip"] + MPKI, T + "/t2b_overall.tex",
              "Task 2B: Overall comparison of Baseline, SRRIP, Static I-RRIP, Dynamic I-RRIP (Default) and all refined configurations.", "tab:t2b_overall")
        plots_for(d, overall, "t2b_overall", P, "Dynamic I-RRIP: Overall Comparison")

if __name__ == "__main__":
    main()