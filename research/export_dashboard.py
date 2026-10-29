"""Write the CSV files behind the results dashboard to research/results/dashboard/.

    python3 research/export_dashboard.py [--end 2026-10-29T08:40:00Z]

day.csv      one row per window bar: close, bot equity and buy-and-hold equity (marked at the close, before the exit
             fee; the last row is the final balance after it)
trades.csv   the trades of that window, exactly as bot.py prints them
hitrates.csv hit-rates by strategy (train / test / full), read from the research CSVs
replays.csv  bot.py --end replays saved in runs/
windows.csv  per-window results of the shipped strategy (copy of shipped_windows.csv)
"""
import argparse
import csv
import glob
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import parse_utc  # noqa: E402
from btcbot.data import fetch_candles, window_bounds  # noqa: E402
from btcbot.engine import simulate  # noqa: E402
from btcbot.report import iso  # noqa: E402
from btcbot.strategy import Strategy  # noqa: E402
from research.evaluate import RESULTS, family_rows, read_csv  # noqa: E402

OUT = os.path.join(RESULTS, "dashboard")


class Recorder(Strategy):
    """The shipped strategy, also recording mark-to-market equity at each decision (it does not change decisions)."""

    def __init__(self):
        super().__init__()
        self.equity = {}

    def on_bar(self, bars, lots, ctx):
        self.equity[bars[-1].open_time] = ctx.cash + sum(lot.qty_btc for lot in lots) * bars[-1].close
        return super().on_bar(bars, lots, ctx)


def write(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"{name}: {len(rows)} rows")


def day(end_iso):
    start, end = window_bounds(parse_utc(end_iso))
    bars, meta, start, end = fetch_candles(start, end, "coinbase", end)
    rec = Recorder()
    r = simulate(bars, start, end, rec)
    window = [b for b in bars if start <= b.open_time < end]
    qty_bh = 0.999 * 10_000 / window[0].open
    rows = []
    for b in window[:-1]:
        rows.append([iso(b.open_time + 300), b.close, round(rec.equity[b.open_time], 2), round(qty_bh * b.close, 2)])
    rows.append([iso(end), window[-1].close, round(r.final_cash, 2), round(10_000 + r.bh_pnl_usd, 2)])
    write("day.csv", ["time", "close", "bot_equity", "bh_equity"], rows)
    write("trades.csv", ["trade", "buy_time", "buy_price", "sell_time", "sell_price", "size_btc", "fees_usd",
                         "pnl_usd", "pnl_pct", "exit"],
          [[n, iso(t.buy_time), t.buy_price, iso(t.sell_time), t.sell_price, round(t.qty_btc, 6),
            round(t.fees_usd, 2), round(t.pnl_usd, 2), round(t.pnl_pct, 3), t.exit_reason]
           for n, t in enumerate(sorted(r.trades, key=lambda t: t.buy_time), 1)])
    print(f"window {iso(start)} -> {iso(end)}: {len(r.trades)} trades, P&L {r.pnl_usd:+.2f} USD")


def hitrates():
    rows = []
    base = {name: m for name, _, m in read_csv(os.path.join(RESULTS, "baselines.csv"))}
    rand = [m for name, _, m in read_csv(os.path.join(RESULTS, "baselines.csv")) if name == "random"]
    mean = {sp: sum(m[sp]["hit"] for m in rand) / len(rand) for sp in ("train", "test", "full")}
    rows.append(["Random entries", "baseline", *(round(mean[sp], 1) for sp in ("train", "test", "full"))])
    m = base["buy_and_hold"]
    rows.append(["Buy-and-hold", "baseline", *(round(m[sp]["hit"], 1) for sp in ("train", "test", "full"))])
    for family, label in (("S1", "S1 dip reversion"), ("S3", "S3 momentum"), ("S2", "S2 tranche grid")):
        m = family_rows(family)[0][2]
        rows.append([label, "candidate", *(round(m[sp]["hit"], 1) for sp in ("train", "test", "full"))])
    m = base["shipped"]
    rows.append(["Shipped (S2 + guard)", "shipped", *(round(m[sp]["hit"], 1) for sp in ("train", "test", "full"))])
    write("hitrates.csv", ["strategy", "kind", "train_hit", "test_hit", "full_hit"], rows)


def replays():
    rows = []
    for path in sorted(glob.glob(os.path.join(ROOT, "runs", "*.txt"))):
        text = open(path).read()
        if "clean-clone" in path:
            continue
        end = re.search(r"-> (\S+) \(UTC\)", text).group(1)
        trades = int(re.search(r"^trades\s+(\d+)", text, re.M).group(1))
        pnl = float(re.search(r"^profit .*\(([-+\d.]+) %\)", text, re.M).group(1))
        bh = float(re.search(r"^buy-and-hold .*\(([-+\d.]+) %\)", text, re.M).group(1))
        guard = "fired" if re.search(r"^5-trade guard\s+fired", text, re.M) else "not fired"
        rows.append([end, trades, pnl, bh, guard])
    write("replays.csv", ["window_end", "trades", "pnl_pct", "bh_pnl_pct", "guard"], sorted(rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default="2026-10-29T08:40:00Z")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    day(args.end)
    hitrates()
    replays()
    shutil.copy(os.path.join(RESULTS, "shipped_windows.csv"), os.path.join(OUT, "windows.csv"))
    print("windows.csv: copied")


if __name__ == "__main__":
    main()
