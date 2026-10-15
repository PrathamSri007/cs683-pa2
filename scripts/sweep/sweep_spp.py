import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import random
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DEFAULTS = dict(
    TRACKERS=24, IP_BITS=8, MAX_PERIOD=12,
    THR_BASE=1, THR_SLOPE=1, SAT_HEADROOM=0, CONF_DEC=0, STRIDE_MAX=0,
    DIST1=2, DEG1=3, DISTN=2, DEGN=3,
    THROTTLE=1, AGGR_START=0, AGGR_MAX=8, ACC_HI=60, ACC_LO=40, EPOCH=16, THR_SRC=0,
    MSHR_FRAC8=4,
)

GRID = dict(
    TRACKERS=[24, 48],
    IP_BITS=[8],
    MAX_PERIOD=[8, 12, 14, 16, 18, 20],
    THR_BASE=[1, 2, 3],
    THR_SLOPE=[0, 1],
    SAT_HEADROOM=[0, 3],
    CONF_DEC=[0, 1, 3],
    STRIDE_MAX=[0, 32],
    DIST1=[0, 1, 2, 4],
    DEG1=[1, 2, 3, 4],
    DISTN=[0, 1, 2, 4],
    DEGN=[1, 2, 3, 4],
    THROTTLE=[0, 1],
    AGGR_START=[0, 2],
    AGGR_MAX=[4, 8, 16],
    ACC_HI=[50, 60, 70],
    ACC_LO=[20, 30, 40],
    EPOCH=[16, 32],
    THR_SRC=[0, 1],
    MSHR_FRAC8=[4, 6],
)

PARAM_ORDER = list(DEFAULTS.keys())


def canon(p):
    """Collapse parameters that cannot affect behaviour so equivalent configs dedupe."""
    q = dict(p)
    if q["MAX_PERIOD"] == 1:
        for k in ("DISTN", "DEGN", "THR_SLOPE"):
            q[k] = DEFAULTS[k]
    if q["CONF_DEC"] == 0:
        q["SAT_HEADROOM"] = DEFAULTS["SAT_HEADROOM"]
    if not q["THROTTLE"]:
        for k in ("AGGR_MAX", "ACC_HI", "ACC_LO", "EPOCH", "THR_SRC"):
            q[k] = DEFAULTS[k]
    return q


def valid(q):
    if q["THROTTLE"]:
        if q["ACC_LO"] >= q["ACC_HI"]:
            return False
        if q["AGGR_START"] > q["AGGR_MAX"]:
            return False
    return True


def combo_id(q):
    s = json.dumps({k: q[k] for k in PARAM_ORDER}, sort_keys=True)
    return hashlib.sha1(s.encode()).hexdigest()[:8]


def gen_oat():
    seen, out, meta = set(), [], {}
    base = canon(DEFAULTS)
    cid = combo_id(base)
    seen.add(cid); out.append(base); meta[cid] = ["default"]
    for k, vals in GRID.items():
        for v in vals:
            q = dict(DEFAULTS); q[k] = v
            q = canon(q)
            if not valid(q):
                continue
            cid = combo_id(q)
            if cid in seen:
                meta[cid].append(f"{k}={v}")
                continue
            seen.add(cid); out.append(q); meta[cid] = [f"{k}={v}"]
    return out, meta


def gen_random(n, seed):
    rng = random.Random(seed)
    seen, out = set(), []
    attempts = 0
    while len(out) < n and attempts < n * 200:
        attempts += 1
        q = canon({k: rng.choice(v) for k, v in GRID.items()})
        if not valid(q):
            continue
        cid = combo_id(q)
        if cid in seen:
            continue
        seen.add(cid); out.append(q)
    return out, {}


def gen_full(limit=5_000_000):
    raw = 1
    for v in GRID.values():
        raw *= len(v)
    if raw > limit:
        sys.exit(f"Raw grid has {raw:,} points (> {limit:,}). Narrow it with --grid FILE.json "
                 f"(a JSON object mapping parameter -> list of values), or use --mode random / oat.")
    seen, out = set(), []
    keys = list(GRID.keys())
    for vals in itertools.product(*[GRID[k] for k in keys]):
        q = canon(dict(zip(keys, vals)))
        if not valid(q):
            continue
        cid = combo_id(q)
        if cid in seen:
            continue
        seen.add(cid); out.append(q)
    return out, {}


# ----------------------------------------------------------------------------------------------
# Storage estimate (bits). Assumptions are explicit: see ADDR_BITS and the stride-width rule below.
# ----------------------------------------------------------------------------------------------
ADDR_BITS = 58  # full cache-line address stored per tracker, as simulated (64-bit addr, 64B lines)


def clog2(x):
    return max(1, math.ceil(math.log2(x))) if x > 1 else 1


def storage_bits(p, addr_bits=ADDR_BITS):
    n, tag, mp = p["TRACKERS"], p["IP_BITS"], p["MAX_PERIOD"]
    thr = [p["THR_BASE"] + p["THR_SLOPE"] * (k - 1) for k in range(1, mp + 1)]
    sat = min(255, max(thr) + p["SAT_HEADROOM"])
    conf_bits = clog2(sat + 1)
    stride_bits = clog2(2 * p["STRIDE_MAX"] + 1) if p["STRIDE_MAX"] > 0 else 8  # 8 = assumed if unfiltered
    lru_bits = clog2(n)
    entry = tag + addr_bits + mp * stride_bits + mp * conf_bits + lru_bits
    throttle = (2 * 16 + clog2(p["AGGR_MAX"] + 1)) if p["THROTTLE"] else 0
    return n * entry + throttle


# ----------------------------------------------------------------------------------------------
# Log parsing
# ----------------------------------------------------------------------------------------------
def fnum(s):
    try:
        v = float(s)
        return None if (math.isnan(v) or math.isinf(v)) else v
    except (TypeError, ValueError):
        return None


def parse_log(path):
    text = Path(path).read_text(errors="replace")
    idx = text.find("Region of Interest Statistics")
    roi = text[idx:] if idx >= 0 else text
    m = {}

    def grab(pat, names, src=roi):
        mm = re.search(pat, src)
        for i, n in enumerate(names):
            m[n] = fnum(mm.group(i + 1)) if mm else None

    grab(r"CPU\s+0\s+cumulative IPC:\s+(\S+)", ["ipc"])
    for name, key in (("L1D LOAD", "l1d_load"), ("L1D TOTAL", "l1d_total"),
                      ("L2C TOTAL", "l2c_total"), ("LLC TOTAL", "llc_total"), ("LLC LOAD", "llc_load")):
        grab(rf"{name}\s+ACCESS:\s+(\d+)\s+HIT:\s+(\d+)\s+MISS:\s+(\d+).*?MPKI:\s+(\S+)",
             [f"{key}_access", f"{key}_hit", f"{key}_miss", f"{key}_mpki"])
    grab(r"L2C DATA LOAD MPKI:\s+(\S+)", ["l2c_data_load_mpki"])

    for C in ("L1D", "L2C", "LLC"):
        c = C.lower()
        grab(rf"{C} PREFETCH\s+REQUESTED:\s+(\d+)\s+ISSUED:\s+(\d+)\s+USEFUL:\s+(\d+)\s+USELESS:\s+(\d+)",
             [f"{c}_pf_requested", f"{c}_pf_issued", f"{c}_pf_useful", f"{c}_pf_useless"])
        grab(rf"{C} USEFUL LOAD PREFETCHES:\s+(\d+)\s+PREFETCH ISSUED TO LOWER LEVEL:\s+(\d+)\s+ACCURACY:\s+(\S+)",
             [f"{c}_useful_load", f"{c}_pf_lower", f"{c}_acc_pct"])
        grab(rf"{C} TIMELY PREFETCHES:\s+(\d+)\s+LATE PREFETCHES:\s+(\d+)\s+DROPPED PREFETCHES:\s+(\d+)",
             [f"{c}_timely", f"{c}_late", f"{c}_dropped"])
        grab(rf"{C} PREFETCHES SAME FILL-ORIGIN LEVEL:\s+(\d+)\s+DIFFERENT FILL-ORIGIN LEVEL:\s+(\d+)",
             [f"{c}_fill_same", f"{c}_fill_lower"])
        grab(rf"{C} PREFETCH\s+ACCESS:\s+(\d+)\s+HIT:\s+(\d+)\s+MISS:\s+(\d+)",
             [f"{c}_pfacc", f"{c}_pfacc_hit", f"{c}_pfacc_miss"])

    # SPP-side counters (printed by l1d_prefetcher_final_stats; NOT reset at warmup end)
    per = {}
    for mm in re.finditer(r"Prefetches triggered by period (\d+) to L1: (\d+) \| to L2: (\d+) \| total: (\d+)"
                          r" \| Useful: (\d+) \| Useless: (\d+)", text):
        per[int(mm.group(1))] = tuple(int(mm.group(i)) for i in range(4, 7))
    tot_all = sum(v[0] for v in per.values())
    tot_p1 = per.get(1, (0, 0, 0))[0]
    useful_n = sum(v[1] for p, v in per.items() if p >= 2)
    dead_n = sum(v[2] for p, v in per.items() if p >= 2)
    m["spp_share_p1_pct"] = 100.0 * tot_p1 / tot_all if tot_all else None
    m["spp_share_p2plus_pct"] = 100.0 * (tot_all - tot_p1) / tot_all if tot_all else None
    m["spp_p2plus_ptt_acc_pct"] = 100.0 * useful_n / (useful_n + dead_n) if (useful_n + dead_n) else None

    ep = {int(a): int(b) for a, b in re.findall(r"Epochs at aggression (\d+):\s+(\d+)", text)}
    n_ep = sum(ep.values())
    m["thr_epochs"] = n_ep if n_ep else None
    m["thr_mean_aggr"] = sum(k * v for k, v in ep.items()) / n_ep if n_ep else None
    return m


def derive(m, base):
    d = dict(m)

    def ratio(a, b, scale=1.0):
        return scale * a / b if (a is not None and b not in (None, 0)) else None

    d["l1d_acc_issued_pct"] = ratio(m.get("l1d_pf_useful"), m.get("l1d_pf_issued"), 100)
    d["l1d_late_pct"] = ratio(m.get("l1d_late"), (m.get("l1d_timely") or 0) + (m.get("l1d_late") or 0), 100)
    d["l1d_pf_l1hit_pct"] = ratio(m.get("l1d_pfacc_hit"), m.get("l1d_pfacc"), 100)
    d["l1d_useless_pct"] = ratio(m.get("l1d_pf_useless"),
                                 (m.get("l1d_pf_useful") or 0) + (m.get("l1d_pf_useless") or 0), 100)
    if base:
        d["speedup"] = ratio(m.get("ipc"), base.get("ipc"))
        bm, lm = base.get("l1d_load_miss"), m.get("l1d_load_miss")
        d["coverage_pct"] = 100.0 * (bm - lm) / bm if (bm and lm is not None) else None
        # extra traffic below L1 caused by prefetching, relative to baseline L1D load misses
        d["l1d_pf_to_lower_per_base_miss"] = ratio(m.get("l1d_pf_lower"), bm)
    return d


METRIC_COLS = [
    "ipc", "speedup", "l1d_load_mpki", "l1d_total_mpki", "l2c_total_mpki", "l2c_data_load_mpki", "llc_total_mpki",
    "coverage_pct",
    "l1d_pf_requested", "l1d_pf_issued", "l1d_pf_lower", "l1d_pf_useful", "l1d_pf_useless",
    "l1d_acc_pct", "l1d_acc_issued_pct", "l1d_useless_pct", "l1d_timely", "l1d_late", "l1d_late_pct", "l1d_dropped",
    "l1d_fill_same", "l1d_fill_lower", "l1d_pf_l1hit_pct", "l1d_pf_to_lower_per_base_miss",
    "l2c_pf_issued", "l2c_pf_lower", "l2c_pf_useful", "l2c_pf_useless", "l2c_acc_pct", "l2c_timely", "l2c_late",
    "llc_pf_lower", "llc_pf_useful", "llc_acc_pct", "llc_pfacc_miss",
    "spp_share_p1_pct", "spp_share_p2plus_pct", "spp_p2plus_ptt_acc_pct", "thr_epochs", "thr_mean_aggr",
]


# ----------------------------------------------------------------------------------------------
# Running simulations
# ----------------------------------------------------------------------------------------------
def log_done(path, marker):
    p = Path(path)
    if not p.exists():
        return False
    try:
        return marker in p.read_text(errors="replace")
    except OSError:
        return False


def run_sim(binary, trace_path, log, warm, sim, params=None):
    env = os.environ.copy()
    if params:
        for k, v in params.items():
            env[f"SPP_{k}"] = str(v)
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    part = log.with_name(log.name + ".part")
    with open(part, "w") as fh:
        r = subprocess.run([binary, "-warmup_instructions", str(warm), "-simulation_instructions", str(sim),
                            "-traces", str(trace_path)], stdout=fh, stderr=subprocess.STDOUT, env=env)
    if r.returncode == 0:
        os.replace(part, log)
    return r.returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["oat", "random", "full"], default="oat")
    ap.add_argument("--n", type=int, default=100, help="configs for --mode random")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--grid", help="JSON file overriding GRID entries (param -> list of values)")
    ap.add_argument("--traces", nargs="+", default=["Trace1", "Trace2", "Trace3"])
    ap.add_argument("--trace-dir", default="traces")
    ap.add_argument("--out-dir", default="output_logs")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--warmup", type=int, default=25_000_000)
    ap.add_argument("--sim", type=int, default=25_000_000)
    ap.add_argument("--binary", default="./bin/hashed_perceptron-no-spp-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-spp")
    ap.add_argument("--baseline-bin", default="./bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline")
    ap.add_argument("--ipstride-bin", default="./bin/hashed_perceptron-no-ip_stride-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-ip_stride")
    ap.add_argument("--build", action="store_true", help="run ./build_champsim.sh spp first")
    ap.add_argument("--no-run", action="store_true", help="do not launch simulations, only aggregate")
    ap.add_argument("--max-jobs", type=int, default=400, help="refuse to launch more sims than this without --yes")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--csv-prefix", default="sweep")
    args = ap.parse_args()

    if args.grid:
        GRID.update(json.loads(Path(args.grid).read_text()))

    if args.mode == "oat":
        combos, meta = gen_oat()
    elif args.mode == "random":
        combos, meta = gen_random(args.n, args.seed)
    else:
        combos, meta = gen_full()

    out = Path(args.out_dir)
    sweep_dir = out / "sweep"
    jobs = []
    for q in combos:
        cid = combo_id(q)
        for t in args.traces:
            jobs.append((cid, q, t, sweep_dir / f"{cid}_{t}.log"))
    todo = [j for j in jobs if not log_done(j[3], "Prefetches triggered by period 1 ")]

    est_min = len(todo) * 3.0 / max(1, args.jobs)
    print(f"{len(combos)} unique configs x {len(args.traces)} traces = {len(jobs)} runs; "
          f"{len(todo)} still to run (~{est_min:.0f} min at ~3 min/run on {args.jobs} workers)")

    if args.build and not args.no_run:
        subprocess.run(["./build_champsim.sh", "spp"], check=True)

    if not args.no_run and todo:
        if len(todo) > args.max_jobs and not args.yes:
            sys.exit(f"{len(todo)} runs > --max-jobs {args.max_jobs}. Re-run with --yes, or narrow the grid / use --mode random.")
        if not Path(args.binary).exists():
            sys.exit(f"binary not found: {args.binary} (build the spp config first, or pass --build)")

        # reference runs (baseline, ip_stride) if their logs are missing
        refs = []
        for cfg, binp in (("baseline", args.baseline_bin), ("ipstride", args.ipstride_bin)):
            for t in args.traces:
                lg = out / f"{cfg}_{t}.log"
                if not log_done(lg, "Region of Interest Statistics") and Path(binp).exists():
                    refs.append((binp, f"{args.trace_dir}/{t}.gz", lg, None))

        t0 = time.time()
        with ThreadPoolExecutor(max_workers=args.jobs) as ex:
            futs = {}
            for binp, tp, lg, prm in refs:
                futs[ex.submit(run_sim, binp, tp, lg, args.warmup, args.sim, prm)] = str(lg)
            for cid, q, t, lg in todo:
                futs[ex.submit(run_sim, args.binary, f"{args.trace_dir}/{t}.gz", lg, args.warmup, args.sim, q)] = str(lg)
            done = 0
            for f in as_completed(futs):
                done += 1
                rc = f.result()
                flag = "" if rc == 0 else f"  (exit code {rc}!)"
                print(f"[{done}/{len(futs)}] {futs[f]} {time.time() - t0:.0f}s{flag}", flush=True)

    # ------------------------------------------------------------------ aggregate
    base = {}
    for t in args.traces:
        lg = out / f"baseline_{t}.log"
        base[t] = parse_log(lg) if lg.exists() else None
        if base[t] is None:
            print(f"WARNING: {lg} missing, speedup/coverage will be empty for {t}")

    rows = []
    # reference rows
    for cfg in ("baseline", "ipstride"):
        for t in args.traces:
            lg = out / f"{cfg}_{t}.log"
            if lg.exists():
                d = derive(parse_log(lg), base[t] if cfg != "baseline" else base[t])
                rows.append(dict(combo_id=cfg, trace=t, **{k: "" for k in PARAM_ORDER}, **d))
    for cid, q, t, lg in jobs:
        if not log_done(lg, "Prefetches triggered by period 1 "):
            continue
        d = derive(parse_log(lg), base[t])
        d["storage_bits_est"] = storage_bits(q)
        rows.append(dict(combo_id=cid, trace=t, **q, **d))

    fields = ["combo_id", "trace"] + PARAM_ORDER + ["storage_bits_est"] + METRIC_COLS
    with open(f"{args.csv_prefix}_results.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})
    print(f"wrote {args.csv_prefix}_results.csv ({len(rows)} rows)")

    # per-config summary across traces
    by = {}
    for r in rows:
        by.setdefault(r["combo_id"], []).append(r)

    def mean(xs):
        xs = [x for x in xs if isinstance(x, (int, float))]
        return sum(xs) / len(xs) if xs else None

    def gmean(xs):
        xs = [x for x in xs if isinstance(x, (int, float)) and x > 0]
        return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else None

    summ = []
    for cid, rs in by.items():
        s = dict(combo_id=cid, n_traces=len(rs))
        s["geomean_speedup"] = gmean([r.get("speedup") for r in rs])
        sp = [r.get("speedup") for r in rs if isinstance(r.get("speedup"), (int, float))]
        s["min_speedup"] = min(sp) if sp else None
        for k in ("l1d_load_mpki", "coverage_pct", "l1d_acc_pct", "l1d_late_pct", "l1d_pf_lower", "l1d_pf_useful"):
            s["mean_" + k] = mean([r.get(k) for r in rs])
        for k in PARAM_ORDER + ["storage_bits_est"]:
            s[k] = rs[0].get(k, "")
        summ.append(s)
    summ.sort(key=lambda s: -(s["geomean_speedup"] or 0))
    sfields = (["combo_id", "n_traces", "geomean_speedup", "min_speedup", "mean_l1d_load_mpki", "mean_coverage_pct",
                "mean_l1d_acc_pct", "mean_l1d_late_pct", "mean_l1d_pf_lower", "mean_l1d_pf_useful"]
               + PARAM_ORDER + ["storage_bits_est"])
    with open(f"{args.csv_prefix}_summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=sfields, extrasaction="ignore")
        w.writeheader()
        for s in summ:
            w.writerow({k: ("" if s.get(k) is None else s.get(k)) for k in sfields})
    print(f"wrote {args.csv_prefix}_summary.csv ({len(summ)} configs)")

    def f(x, d=4):
        return "N/A" if x in (None, "") else (f"{x:.{d}f}" if isinstance(x, float) else str(x))

    print("\nTop configs by geomean speedup over baseline (all requested traces):")
    print(f"{'id':<9}{'gm spd':>8}{'min spd':>9}{'ldMPKI':>8}{'cov%':>7}{'acc%':>7}{'late%':>7}{'pf->L2':>9}{'kbit':>7}  changed vs default")
    for s in summ[:args.top]:
        diff = [f"{k}={s[k]}" for k in PARAM_ORDER if s.get(k) not in ("", None) and s[k] != DEFAULTS[k]]
        kb = s["storage_bits_est"] / 1000 if s.get("storage_bits_est") not in ("", None) else None
        print(f"{s['combo_id']:<9}{f(s['geomean_speedup']):>8}{f(s['min_speedup']):>9}{f(s['mean_l1d_load_mpki'],3):>8}"
              f"{f(s['mean_coverage_pct'],2):>7}{f(s['mean_l1d_acc_pct'],1):>7}{f(s['mean_l1d_late_pct'],1):>7}"
              f"{f(s['mean_l1d_pf_lower'],0):>9}{f(kb,1):>7}  {' '.join(diff) or '(default)'}")

    if args.mode == "oat" and meta:
        sm = {s["combo_id"]: s for s in summ}
        print("\nOne-at-a-time sensitivity (geomean speedup; default config first):")
        for cid, tags in meta.items():
            if cid in sm:
                print(f"  {', '.join(tags):<28} {f(sm[cid]['geomean_speedup'])}   cov {f(sm[cid]['mean_coverage_pct'],2)}%   "
                      f"acc {f(sm[cid]['mean_l1d_acc_pct'],1)}%")


if __name__ == "__main__":
    main()
