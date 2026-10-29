# BTC paper-trading bot (take-home)

One command replays the last 24 hours of BTC-USD 5-minute candles from Coinbase's public API, trades them with the
strategy below, and prints every trade and the totals.

## Run it

Prerequisites: macOS with `python3` (3.9 or newer). No packages, no API keys. On a clean Mac the first `python3` call
offers to install the Xcode Command Line Tools, which include Python 3.9; a python.org or Homebrew Python works too.

    git clone https://github.com/slawekkwasny/btc-paper-bot.git && cd btc-paper-bot && python3 bot.py

Options: `--end 2026-10-28T12:00:00Z` replays the 24 h ending at a past time; `--source kraken|binance` forces a
fallback feed (Binance quotes BTC/USDT, not BTC/USD); `--verbose` prints every decision and fill.
Tests: `python3 -m unittest discover tests`.

## The strategy (in a few sentences)

**When it buys:** when the 5-minute close is 0.18 % below its 3-hour exponential moving average, it buys a tranche of
20 % of the starting cash. If the price keeps falling it buys another tranche every further 0.18 % below the last buy,
up to 5 tranches. No new tranches in the last 3 hours of the window.
**When it sells:** each tranche is sold on its own as soon as the close is 0.51 % above that tranche's buy price,
which clears the 0.2 % round-trip fee. Whatever is still open at the end of the 24 hours is sold at the last close.
**Why:** at horizons of 15 minutes to a few hours BTC tends to overshoot and partly snap back (short-horizon
reversal). Small, frequent targets give many small wins; the price of that is a rare bigger loss on a day that trends
down all day, when tranches are still open at the forced close.
**The >= 5-trade rule:** if fewer than 5 trades are closed or open at 22 h into the window, a pacing guard buys small
5 % tranches (one per 5-minute bar) until 5 round trips are certain, and sells each at the moving average, at the
target, or after 30 minutes. It fired in 33 % of historical windows and cost 0.03 percentage points on average there.

Every decision uses only candles that have closed; orders fill at the next candle's open (tested in
`tests/test_no_lookahead.py`). Fees are 0.1 % on every buy and every sell.

## Can this be guaranteed? No. Here is the evidence

Five full-size round trips cost at least 1 % of capital in fees, and 24 hours of BTC is mostly noise, so no strategy
is profitable on every day. The useful question is how often a strategy ends a random 24 h window with more than
10,000 USD. I measured that on 90 days of Coinbase 5-minute candles (2026-07-31 to 2026-10-29): 2,113 windows of
24 h, one starting every hour, run through the same engine and strategy code as `bot.py`. Parameters were chosen on
windows inside the first 60 days (train) and then checked on windows inside the last 30 days (test), which were never
used for choosing anything.

| strategy | params | train hit-rate | test hit-rate | median P&L (all) | 5th pct P&L (all) | P(trades >= 5) | guard rate |
|---|---|---|---|---|---|---|---|
| buy-and-hold | all in at open, out at close | 47.7 % | 44.0 % | -0.09 % | -2.45 % | n/a | n/a |
| random entries (30 seeds) | p = 0.04 per bar, hold 2 h | 16.4 % (15.3-17.2) | 11.3 % (9.8-12.8) | -1.06 % | -2.94 % | 85 % | n/a |
| S1 dip reversion, best | ema 24, k 1.0, H 48 | 27.3 % | 30.6 % | 0.00 % | -1.20 % | 1 % | n/a |
| S3 breakout momentum, best | L 18, trail 1.5 %, H 96 | 32.7 % | 28.8 % | -0.52 % | -2.59 % | 0 % | n/a |
| S2 tranche grid, selected (guard off) | g 0.18 %, t 0.51 %, 5 lots | 62.2 % | 59.3 % | +0.09 % | -1.80 % | 67 % | n/a |
| **shipped: S2 + pacing guard** | same | **59.2 %** | **57.2 %** | +0.08 % | -1.80 % | **100 %** | 33 % |

The 2,113 windows overlap, so they hold only about 90 independent days: every hit-rate here carries roughly
+/- 10 percentage points of uncertainty, and differences smaller than that are noise. Read the shipped line as "about
6 days in 10 end in profit", against about 4.5 in 10 for buy-and-hold and 1.5 in 10 for random trading with the same
fees. Full tables, every parameter set and the selection log: [research/results/summary.md](research/results/summary.md).

## How I got here, and what didn't work

- **Started from the judging rule.** The rerun is judged on the *sign* of one 24 h result, not on the expected
  return. That favours a high hit-rate (many small wins, rare larger losses) over strategies with a few big wins. The
  background reading for the plan (PLAN.md §10) pointed to short-term reversal in BTC at 15-minute to multi-hour
  horizons, which is also the horizon that produces 5-15 trades a day; the harness, not the literature, decided.
- **Built the measuring tool first** (`research/evaluate.py`): rolling windows, a train/test split, and two baselines.
  The random baseline was the first surprise: with zero fees random entries win 51-55 % of days, with 0.1 % per side
  only ~15 %. The fee drag of ~1.1 % per day is the real opponent, not a coin flip.
- **S1, dip reversion with a single all-in lot** (my favourite going in): best 27 % train hit-rate. Requiring the dip
  to be large enough to pay the fees leaves it with ~1.3 trades a day, so most days it barely trades. The stop-loss
  variants (3 and 4 sigma) almost never triggered and changed nothing on train.
- **S3, breakout momentum** (the control): best 33 %, and its P&L moves with the market (correlation +0.9), i.e. it
  is mostly a delayed buy-and-hold with extra fees. Dropped.
- **S2, the tranche grid**: 62 % train, 59 % test. Its best point first landed on the edge of the grid, so I extended
  the grid below it (train only); the top is a flat plateau (61-62 % for dips of 0.15-0.24 % and targets of
  0.40-0.60 %), which is what you want: the result does not hinge on one lucky number.
- **The pacing guard as first planned** (lower the dip threshold from 16 h, then force full 20 % tranches from 22 h)
  cost 8 points of hit-rate, because late full-size tranches and their fees flip small winning days into small losing
  ones. Smaller forced tranches are cheaper (train: 20 % -> 52.8 %, 10 % -> 56.6 %, 5 % -> 59.2 %, 2 % -> 60.6 %)
  and the threshold decay added nothing, so the shipped guard uses 5 % tranches only. I stopped at 5 % rather than 2 %
  (+1.4 points, inside the noise) so the guard trades stay real positions rather than token ones.

## Known failure mode

Days that trend down without bouncing. The tranches keep buying the way down, never reach their target, and the forced
close at the end of the window realises the loss. On the 201 historical windows where buy-and-hold lost more than 2 %,
the shipped strategy ended in profit in only 3.5 % of them (median -1.72 %), though it lost less than buy-and-hold
on 195 of the 201. My own run below is one of those days.

## My runs

    $ python3 bot.py        # run at 2026-10-29T08:41:42Z, macOS 26.6.2, Python 3.12.0
    BTC paper-trading bot: last 24 h replay
    window     2026-10-28T08:40:00Z -> 2026-10-29T08:40:00Z (UTC)
    data       coinbase, 288 x 5-min bars in window (+288 warm-up, 0 gaps filled)
    strategy   tranche grid (dip below 3 h EMA, 20 % tranches, per-tranche take-profit) (g=0.0018, t=0.0051, T=5)
    start      10,000.00 USD, fee 0.1 % per side, long only

     #  buy (UTC)     buy price  sell (UTC)   sell price    size BTC  fees USD    P&L USD    P&L %  exit
     1  10-28 13:50   80,307.47  10-28 17:55   80,758.53    0.024879      4.01      +7.21  +0.361%  target
     2  10-28 12:35   80,598.24  10-28 18:45   81,093.75    0.024790      4.01      +8.27  +0.414%  target
     3  10-28 12:15   80,808.61  10-28 19:35   81,246.69    0.024725      4.01      +6.82  +0.341%  target
     4  10-28 12:05   81,086.76  10-28 20:00   81,502.09    0.024640      4.01      +6.23  +0.311%  target
     5  10-29 01:00   81,000.00  10-29 08:40   79,919.00    0.024667      3.97     -30.64  -1.532%  eod
     6  10-29 01:10   80,852.12  10-29 08:40   79,919.00    0.024712      3.97     -27.03  -1.352%  eod
     7  10-29 01:35   80,598.90  10-29 08:40   79,919.00    0.024789      3.98     -20.84  -1.042%  eod
     8  10-29 01:45   80,442.89  10-29 08:40   79,919.00    0.024837      3.98     -17.00  -0.850%  eod
     9  10-29 01:50   79,977.96  10-29 08:40   79,919.00    0.024982      4.00      -5.47  -0.273%  eod

    trades          9 round trips (4 winners), fees paid 35.95 USD
    final balance   9,927.56 USD, 0 BTC
    profit          -72.44 USD (-0.724 %)
    buy-and-hold    -219.47 USD (-2.195 %) net of fees; price moved -1.999 %
    5-trade guard   not fired
    verdict         NOT PROFITABLE, >= 5 trades, flat at end
    backtest        hit-rate over 2113 historical 24 h windows: 58.5 % in profit (last-30-day test split 57.2 %, buy-and-hold 46.5 %; see README)

A losing day, and an example of the failure mode above: BTC fell 2 % over the window; four tranches bought around
noon hit their targets, five bought overnight were still open at the close. Every run is kept in full in
[runs/](runs/).

The seven 24 h windows before it, replayed with `--end` (same code, same hour; full output in `runs/replay-*.txt`;
these are evidence, nothing was tuned on them):

| window ends (UTC) | trades | bot P&L | buy-and-hold | guard |
|---|---|---|---|---|
| 2026-10-22 08:40 | 8 | -262.43 USD (-2.62 %) | -1.72 % | not fired |
| 2026-10-23 08:40 | 7 | +26.19 USD (+0.26 %) | -0.25 % | not fired |
| 2026-10-24 08:40 | 8 | -51.32 USD (-0.51 %) | -1.65 % | not fired |
| 2026-10-25 08:40 | 5 | +17.75 USD (+0.18 %) | -0.50 % | not fired |
| 2026-10-26 08:40 | 7 | +27.16 USD (+0.27 %) | -0.41 % | not fired |
| 2026-10-27 08:40 | 10 | +18.69 USD (+0.19 %) | -0.83 % | not fired |
| 2026-10-28 08:40 | 5 | +10.43 USD (+0.10 %) | +2.15 % | fired |

Five of seven in profit, with small wins and two larger losses: the shape the hit-rate table predicts.

## Clean-clone test

    $ cd /tmp && rm -rf btc-paper-bot && gh repo clone slawekkwasny/btc-paper-bot && cd btc-paper-bot && /usr/bin/python3 bot.py
    # 2026-10-29T08:42:39Z, commit 74fa21b (75234d2 before the author e-mail was corrected), macOS 26.6.2, Apple's /usr/bin/python3 = Python 3.9.6, nothing installed
    BTC paper-trading bot: last 24 h replay
    window     2026-10-28T08:40:00Z -> 2026-10-29T08:40:00Z (UTC)
    ...
    backtest        hit-rate over 2113 historical 24 h windows: 58.5 % in profit (last-30-day test split 57.2 %, buy-and-hold 46.5 %; see README)

Exit code 0, same output as the run above. Note for python.org builds of Python on macOS: they ship without CA
certificates until "Install Certificates.command" is run, which made every HTTPS request fail; the bot falls back to
the system bundle `/etc/ssl/cert.pem` with verification still on, so this needs no action.

## AI tools used

Claude (claude.ai) for the research and the work plan ([PLAN.md](PLAN.md)) and the rules file
([CLAUDE.md](CLAUDE.md)); Claude Code (Claude Opus 5.5) for the implementation, following the plan phase by phase.
Every number in this README and in `research/results/` comes from running the code; the commit history shows the
order things were done in. Hands-on time: see [TIMELOG.md](TIMELOG.md).

## Repo layout

    bot.py                  entry point: python3 bot.py [--end ISO-8601] [--source ...] [--verbose]
    btcbot/data.py          Coinbase fetcher (paged) + Kraken/Binance fallbacks, validation, gap handling
    btcbot/engine.py        paper-trading engine: fills at next open, fees, forced close, buy-and-hold
    btcbot/strategy.py      the shipped strategy and its pacing guard (the only copy of its logic)
    btcbot/report.py        the printed report
    research/               history download, candidate strategies S1-S3, evaluation harness, results/
    tests/                  unittest suite (fees, forced close, no-entry zone, no look-ahead, parsers, guard)
    runs/                   full output of every run quoted here
    docs/brief.md           the original brief

## Loom

<link to be added>
