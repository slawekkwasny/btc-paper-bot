#!/usr/bin/env python3
"""Replay the last 24 h of BTC-USD 5-minute candles with the shipped strategy and print every trade.

    python3 bot.py                              # the 24 h before now
    python3 bot.py --end 2026-10-28T12:00:00Z   # replay a past window
    python3 bot.py --source kraken              # force a feed (coinbase | kraken | binance)
"""
import argparse
import sys
import time
from datetime import datetime, timezone

from btcbot.data import DataError, fetch_candles, window_bounds
from btcbot.engine import simulate
from btcbot.report import iso, render
from btcbot.strategy import Strategy


def parse_utc(s):
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))  # Python 3.9's fromisoformat has no "Z"
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--end", help="replay the 24 h ending at this ISO-8601 UTC time (default: now)")
    ap.add_argument("--source", default="auto", choices=["auto", "coinbase", "kraken", "binance"])
    ap.add_argument("--verbose", action="store_true", help="print per-bar decisions and fills")
    args = ap.parse_args(argv)

    now = parse_utc(args.end) if args.end else time.time()
    start, end = window_bounds(now)
    try:
        bars, meta, start, end = fetch_candles(start, end, args.source, now)  # may shift back one bar
    except DataError as e:
        print(f"error: could not fetch candles for {iso(start)} -> {iso(end)}: {e}", file=sys.stderr)
        return 1
    strategy = Strategy()
    result = simulate(bars, start, end, strategy, log=print if args.verbose else None)
    print(render(result, meta, start, end, strategy))
    return 0


if __name__ == "__main__":
    sys.exit(main())
