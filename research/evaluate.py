"""Rolling 24 h window evaluation on the same engine and strategy classes as the live bot.

    python3 research/evaluate.py baselines        # B0 buy-and-hold, B1 random entries (30 seeds), placeholder
    python3 research/evaluate.py grid S1          # coarse grid on train, fine grid around the top 10 -> CSVs

Windows start every hour from series_start + 24 h (warm-up) to series_end - 24 h. Train = windows that end on or
before series_start + 60 d; test = windows that start at or after it (the ~23 windows straddling the split are left
out so no test hour is ever inside a train window). ~2,000 overlapping windows are ~90 independent days: a hit-rate
carries roughly +/- 10 percentage points of uncertainty.
"""
import csv
import json
import math
import os
import sys
import time
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from btcbot.data import BAR, DAY, WARMUP, fill_gaps  # noqa: E402
from btcbot.engine import simulate  # noqa: E402
from btcbot.report import iso  # noqa: E402
from btcbot.strategy import Strategy as Shipped  # noqa: E402
from research import strategies  # noqa: E402
from research.download_history import load  # noqa: E402

RESULTS = os.path.join(ROOT, "research", "results")
STEP = 3600
TRAIN_DAYS = 60
SPLITS = ("train", "test", "full")


def registry():
    reg = {"shipped": Shipped, "placeholder": Shipped, "random": strategies.RandomEntry}
    reg.update({n: getattr(strategies, n) for n in dir(strategies) if n[:1] == "S" and n[1:2].isdigit()})
    return reg


# --- data and windows (loaded once per worker process) ---
_series = {}


def series():
    if not _series:
        bars, _ = fill_gaps(load())
        t0, t_end = bars[0].open_time, bars[-1].open_time + BAR
        split = t0 + TRAIN_DAYS * DAY
        windows = []
        for ws in range(t0 + WARMUP, t_end - DAY + 1, STEP):
            we = ws + DAY
            tag = "train" if we <= split else "test" if ws >= split else None
            windows.append((ws, (ws - WARMUP - t0) // BAR, (we - t0) // BAR, tag))
        _series.update(bars=bars, windows=windows, t0=t0, t_end=t_end, split=split)
    return _series


def run_windows(name, params):
    """Simulate one parameter set on every window. Returns one record per window."""
    s, cls = series(), registry()[name]
    out = []
    for ws, lo, hi, tag in s["windows"]:
        r = simulate(s["bars"][lo:hi], ws, ws + DAY, cls(**params))
        out.append({"start": ws, "split": tag, "pnl_pct": r.pnl_pct, "n_trades": len(r.trades),
                    "guard_fired": r.guard_fired, "bh_pnl_pct": r.bh_pnl_pct,
                    "price_change_pct": r.price_change_pct, "max_drawdown_pct": r.meta["max_drawdown_pct"]})
    return out


# --- metrics ---

def pct(xs, q):
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo = math.floor(k)
    return xs[lo] + (xs[min(lo + 1, len(xs) - 1)] - xs[lo]) * (k - lo)


def corr(xs, ys):
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx, syy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else 0.0


def metrics(recs, key="pnl_pct"):
    pnl = [r[key] for r in recs]
    return {"n": len(recs), "hit": 100 * sum(p > 0 for p in pnl) / len(pnl),
            "p_min_trades": 100 * sum(r["n_trades"] >= 5 for r in recs) / len(recs),
            "mean": sum(pnl) / len(pnl), "median": pct(pnl, 0.5), "p5": pct(pnl, 0.05), "min": min(pnl),
            "trades": sum(r["n_trades"] for r in recs) / len(recs),
            "guard": 100 * sum(r["guard_fired"] for r in recs) / len(recs),
            "corr": corr(pnl, [r["price_change_pct"] for r in recs]),
            "maxdd": sum(r["max_drawdown_pct"] for r in recs) / len(recs)}


def split_metrics(recs, key="pnl_pct"):
    return {sp: metrics([r for r in recs if sp == "full" or r["split"] == sp], key) for sp in SPLITS}


def evaluate(task):
    name, params = task
    return name, params, split_metrics(run_windows(name, params))


def evaluate_many(tasks, processes=None):
    with Pool(processes) as pool:
        return pool.map(evaluate, tasks)


# --- output ---
COLS = ("hit", "p_min_trades", "mean", "median", "p5", "min", "trades", "guard", "corr", "maxdd")


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "params"] + [f"{sp}_{c}" for sp in SPLITS for c in ("n",) + COLS])
        for name, params, m in rows:
            w.writerow([name, json.dumps(params, sort_keys=True)] +
                       [round(m[sp][c], 4) for sp in SPLITS for c in ("n",) + COLS])


def fmt_params(params):
    return ", ".join(f"{k}={v}" for k, v in params.items()) or "-"


def table(rows):
    """Markdown table: one row per (label, params, metrics)."""
    head = ("| strategy | params | train hit % | test hit % | full hit % | median P&L % | 5th pct % | "
            "P(trades>=5) % | mean trades | guard % | corr w/ market |")
    lines = [head, "|" + "---|" * (head.count("|") - 1)]
    for label, params, m in rows:
        f = m["full"]
        lines.append(f"| {label} | {params} | {m['train']['hit']:.1f} | {m['test']['hit']:.1f} | {f['hit']:.1f} | "
                     f"{f['median']:+.3f} | {f['p5']:+.3f} | {f['p_min_trades']:.1f} | {f['trades']:.1f} | "
                     f"{f['guard']:.1f} | {f['corr']:+.2f} |")
    return "\n".join(lines)


def baselines(seeds=30):
    """B0 buy-and-hold, B1 random entries over `seeds` seeds, and the shipped strategy."""
    s = series()
    t = time.time()
    shipped_recs = run_windows("shipped", {})
    one = time.time() - t
    b1 = evaluate_many([("random", {"seed": k}) for k in range(seeds)])
    b0 = split_metrics(shipped_recs, key="bh_pnl_pct")
    for sp in SPLITS:  # buy-and-hold is 1 round trip per window by construction
        b0[sp].update(p_min_trades=0.0, trades=1.0, corr=1.0)
    rows = [("buy-and-hold (B0)", "all in at open, out at close", b0)]
    b1_hits = {sp: [m[sp]["hit"] for _, _, m in b1] for sp in SPLITS}
    b1_mean = {sp: {c: sum(m[sp][c] for _, _, m in b1) / len(b1) for c in ("n",) + COLS} for sp in SPLITS}
    rows.append((f"random entries (B1, mean of {seeds} seeds)", "p=0.04/bar, hold 24 bars", b1_mean))
    shipped = Shipped()
    rows.append((f"shipped: {shipped.name}", fmt_params(shipped.params), split_metrics(shipped_recs)))
    write_csv(os.path.join(RESULTS, "baselines.csv"), [("random", p, m) for _, p, m in b1] +
              [("buy_and_hold", {}, b0), ("shipped", shipped.params, rows[-1][2])])
    n = {sp: sum(1 for w in s["windows"] if sp == "full" or w[3] == sp) for sp in SPLITS}
    b1_range = {sp: (pct(b1_hits[sp], 0.05), pct(b1_hits[sp], 0.95)) for sp in SPLITS}
    return {"rows": rows, "n": n, "b1_range": b1_range, "seconds_per_set": one}


def summary_md(info, extra_rows=(), notes=""):
    s = series()
    rows = info["rows"] + list(extra_rows)
    b1r = info["b1_range"]
    return f"""# Research results

Data: Coinbase BTC-USD 5-minute candles, {iso(s['t0'])} -> {iso(s['t_end'])} ({len(s['bars'])} bars).
Windows: 24 h, one starting every hour; train = windows ending by {iso(s['split'])}
({info['n']['train']} windows), test = windows starting after it ({info['n']['test']} windows), full = all
{info['n']['full']} windows (including the ones straddling the split). Same engine and fee model as `bot.py`
(0.1 % per side, fills at the next bar's open, forced close at the last bar's close).

**Hit-rate** = share of windows that end with more than 10,000 USD. ~{info['n']['full']} overlapping windows are only
~90 independent days, so a hit-rate carries roughly +/- 10 percentage points of uncertainty: differences smaller
than that are noise.

{table(rows)}

Random entries (B1) hit-rate range across seeds (5th-95th percentile): train {b1r['train'][0]:.1f}-{b1r['train'][1]:.1f} %,
test {b1r['test'][0]:.1f}-{b1r['test'][1]:.1f} %, full {b1r['full'][0]:.1f}-{b1r['full'][1]:.1f} %.
Buy-and-hold columns other than the hit-rate and P&L describe one round trip per window by construction.
One parameter set over all windows takes {info['seconds_per_set']:.1f} s (pure Python, one core).
{notes}"""


# --- parameter grids: coarse on train, then a fine pass around the top 10; selection never reads test ---
import itertools  # noqa: E402


def product(**axes):
    return [dict(zip(axes, v)) for v in itertools.product(*axes.values())]


COARSE = {
    "S1": product(ema_n=[24, 36, 72], vol_n=[72], k=[1.0, 1.5, 2.0, 2.5], H=[12, 24, 48], s=[3, 4, None],
                  min_edge=[0.003]),
    "S2": product(g=[0.003, 0.005, 0.008], t=[0.004, 0.006, 0.009, 0.012], T=[3, 5]),
    "S3": product(L=[24, 48, 96], trail=[0.005, 0.010, 0.015], H=[48, 96]),
}


def neighbours(family, p):
    """The fine grid around one coarse winner."""
    if family == "S1":
        return product(ema_n=[p["ema_n"]], vol_n=[36, 72], k=sorted({max(0.5, p["k"] - 0.25), p["k"], p["k"] + 0.25}),
                       H=[p["H"]], s=[p["s"]], min_edge=[0, 0.003, 0.005])
    if family == "S2":
        return product(g=[round(p["g"] * f, 4) for f in (0.8, 1, 1.25)], t=[round(p["t"] * f, 4) for f in (0.85, 1, 1.15)],
                       T=[p["T"]])
    return product(L=[round(p["L"] * f) for f in (0.75, 1, 1.25)], trail=[round(p["trail"] * f, 4) for f in (0.8, 1, 1.2)],
                   H=[p["H"]])


def train_key(row):
    m = row[2]["train"]
    return (m["hit"], m["p5"])


def grid(family):
    t = time.time()
    coarse = evaluate_many([(family, p) for p in COARSE[family]])
    write_csv(os.path.join(RESULTS, f"{family}_coarse.csv"), coarse)
    top10 = sorted(coarse, key=train_key, reverse=True)[:10]
    seen = {json.dumps(p, sort_keys=True) for _, p, _ in coarse}
    fine_sets = []
    for _, p, _ in top10:
        for q in neighbours(family, p):
            if json.dumps(q, sort_keys=True) not in seen:
                seen.add(json.dumps(q, sort_keys=True))
                fine_sets.append(q)
    fine = evaluate_many([(family, p) for p in fine_sets])
    write_csv(os.path.join(RESULTS, f"{family}_fine.csv"), fine)
    ranked = sorted(coarse + fine, key=train_key, reverse=True)
    print(f"{family}: {len(coarse)} coarse + {len(fine)} fine sets in {time.time() - t:.0f} s; top 10 by train hit-rate:")
    for _, p, m in ranked[:10]:
        print(f"  train {m['train']['hit']:5.1f} %  p5 {m['train']['p5']:+.2f}  trades {m['train']['trades']:.1f}  {fmt_params(p)}")
    return ranked


FEE_NOTE = """
Why random entries score far below 50 %: with zero fees the same random strategy wins 51-55 % of windows
(checked on every third window, 5 seeds); with 0.1 % per side its ~5.7 round trips cost ~1.1 % of capital per day,
which a random 24 h path rarely repays. Any strategy here has to beat that fee drag, not a coin flip.
"""


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "baselines"
    if cmd == "baselines":
        info = baselines()
        md = summary_md(info, notes=FEE_NOTE)
        with open(os.path.join(RESULTS, "summary.md"), "w") as f:
            f.write(md)
        print(md)
    elif cmd == "grid":
        grid(sys.argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
