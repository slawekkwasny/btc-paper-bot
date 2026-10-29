"""Download the last 90 days of BTC-USD 5-minute candles from Coinbase into data/btcusd_5m.csv.

    python3 research/download_history.py [--days 90]

Resumes: if the CSV exists, only the missing head and tail ranges are fetched. Prints bar count and gaps.
"""
import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from btcbot.data import BAR, DAY, Candle, fetch_coinbase, normalise, window_bounds  # noqa: E402
from btcbot.report import iso  # noqa: E402

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "btcusd_5m.csv")
FIELDS = Candle._fields


def load(path=PATH):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [Candle(int(r["open_time"]), *(float(r[k]) for k in FIELDS[1:])) for r in csv.DictReader(f)]


def save(bars, path=PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        w.writerows(bars)
    os.replace(tmp, path)


def gaps(bars):
    return [(a.open_time + BAR, b.open_time) for a, b in zip(bars, bars[1:]) if b.open_time - a.open_time > BAR]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    args = ap.parse_args()
    _, end = window_bounds(time.time())
    start = end - args.days * DAY
    have = [b for b in load() if b.open_time >= start]
    ranges = [(start, end)] if not have else [(start, have[0].open_time), (have[-1].open_time + BAR, end)]
    new = []
    for a, b in ranges:
        if b > a:
            print(f"fetching {iso(a)} -> {iso(b)} ({(b - a) // BAR} bars)")
            new += fetch_coinbase(a, b)
    bars = normalise(have + new, end)
    save(bars)
    missing = sum((b - a) // BAR for a, b in gaps(bars))
    print(f"{len(bars)} bars, {iso(bars[0].open_time)} -> {iso(bars[-1].open_time + BAR)}, "
          f"{len(gaps(bars))} gaps ({missing} missing bars) -> {os.path.relpath(PATH)}")
    for a, b in gaps(bars)[:10]:
        print(f"  gap {iso(a)} -> {iso(b)}")


if __name__ == "__main__":
    main()
