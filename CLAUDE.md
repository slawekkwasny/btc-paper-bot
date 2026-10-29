# CLAUDE.md — BTC paper-trading bot (take-home)

Read PLAN.md before starting any phase. This file holds the rules that never change.

## What we are building

A paper-trading bot that replays the last 24 hours of BTC/USD 5-minute candles, trades them long-only with one
strategy, and prints every trade plus the totals. Constraints come from the brief (docs/brief.md): start with
10,000 USD, 0.1 % fee on every buy and every sell, at least 5 round-trip trades, 0 BTC at the end, no look-ahead,
real data from a public feed with no API keys, one command, rerunnable on the latest 24 hours.

## Non-negotiable rules

1. `bot.py` and the `btcbot/` package use the Python standard library only (urllib, json, csv, math, datetime,
   dataclasses, argparse, unittest). No third-party imports there: the reviewer runs `python3 bot.py` on a clean Mac.
   Research scripts should also be stdlib-only; if numpy is unavoidable, list it in `research/requirements.txt`.
2. The live bot and the research harness run the **same** engine and the **same** strategy class. Never keep two
   copies of the strategy logic.
3. No look-ahead: a strategy decides on the close of bar t using bars ≤ t only; the engine fills at the open of
   bar t+1. The strategy object never receives bars after t. `tests/test_no_lookahead.py` must keep passing.
4. Fee model. Buy: spend X USD; fee = 0.001·X; BTC received = 0.999·X / price. Sell q BTC at price p:
   gross = q·p; fee = 0.001·gross; cash += 0.999·gross. Trade P&L = net sell proceeds − X. Report both fees.
5. Window: `end` = now floored to the 5-minute boundary (the open time of the still-running bar);
   `start = end − 24 h`. Only closed bars (open_time + 300 ≤ now) are used. Warm-up bars before `start` may be
   fetched for indicators but are never traded. All times are UTC unix seconds; print them as ISO-8601 UTC.
6. End flat: whatever is open at the last bar of the window is sold at that bar's close (fee applies),
   exit reason `eod`. The engine enforces this; a strategy cannot opt out.
7. Never fabricate output. Every number in README.md and research/results/ comes from a real run; paste real
   stdout with its UTC timestamp. If a network call fails, say so and stop. Never invent candles.
8. Never tune on today's window. Parameters are chosen on the train split of historical windows and checked on the
   test split (PLAN.md §4). The live run is evidence, not a tuning target.
9. Keep it small: no frameworks, no config systems, no classes for their own sake. Target < 800 lines for the
   whole `btcbot/` package.
10. Commit after every completed step with a message that says what changed and why. Never squash, never amend
    a pushed commit. The reviewer reads the history.

## Data sources (public, no keys)

- **Primary — Coinbase Advanced Trade public candles**
  `GET https://api.coinbase.com/api/v3/brokerage/market/products/BTC-USD/candles?start=<unix>&end=<unix>&granularity=FIVE_MINUTE&limit=350`
  Max 350 candles per request, so page in chunks of ≤ 300 bars (25 h). The response is newest-first; each candle
  has `start` (bar open time, unix seconds, as a string), `low`, `high`, `open`, `close`, `volume` as strings.
  Sort ascending, dedupe on `start`.
- **Fallback 1 — Kraken** `GET https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=5`
  → `result["XXBTZUSD"]` rows `[time, open, high, low, close, vwap, volume, count]`. Only the most recent 720 bars
  (60 h) exist, regardless of `since`. The last row is the still-open bar: drop any row with time ≥ `end`.
- **Fallback 2 — Binance** `GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&startTime=<ms>&endTime=<ms>&limit=1000`
  (alternate host `https://data-api.binance.vision`). Returns HTTP 451 from US IPs, hence last. Quote is USDT, not
  USD; say so in the README if it is ever used.
- Always send a `User-Agent` header, 10 s timeout, 3 retries with exponential backoff, ≥ 0.25 s between calls.
- Validate after fetching: exactly 288 bars inside the window (allow ≤ 2 % gaps, forward-fill them and print a
  warning); abort with a clear message if more are missing or if the last bar is not closed. Print the source used.
- Publishing lag: if only the newest closed bar is missing, wait 5 s and refetch the same source once; if it is still
  missing, shift the window back one bar, print a note, and keep the source. Other errors fall back to the next source.

## Repo layout

```
bot.py                  # entry point: python3 bot.py   (options: --end <ISO-8601 UTC>, --source, --verbose)
btcbot/
  data.py               # fetchers + normalisation to Candle(open_time, open, high, low, close, volume)
  engine.py             # paper-trading engine: lots, fees, forced close, Trade records, buy-and-hold
  strategy.py           # THE shipped strategy (+ the ≥5-trade pacing guard)
  report.py             # printing: every trade, totals, buy-and-hold, window + source info
research/
  download_history.py   # 90 days of 5-minute bars -> data/btcusd_5m.csv (gitignored)
  strategies.py         # candidate strategies S1–S3 (+S4), same interface as btcbot/strategy.py
  evaluate.py           # rolling 24 h windows, param grids, train/test split, baselines -> research/results/
  results/              # committed: summary.md + small CSVs
tests/                  # python3 -m unittest discover tests
docs/brief.md           # the original brief
README.md               # the deliverable README (template in PLAN.md §7)
PLAN.md                 # the work plan
```

## Output format (from the brief, exact)

Every trade: buy time and price, sell time and price, size (BTC), fees (USD), profit or loss (USD and %),
exit reason. Totals: number of trades, final balance, profit in USD and %, buy-and-hold over the same 24 hours
(net of the same fees) for comparison. Also print: data source used, window start and end (UTC), bar count,
and whether the ≥5-trade guard fired.

## Working style

- Run things for real and show the actual stdout.
- When PLAN.md is ambiguous, pick the simplest option, say so in the commit message, and move on.
- At the end of each phase: run `python3 -m unittest discover tests`, run `python3 bot.py` (or the harness),
  commit, then stop and summarise what was verified and what was assumed.
