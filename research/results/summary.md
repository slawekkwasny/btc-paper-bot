# Research results

Data: Coinbase BTC-USD 5-minute candles, 2026-07-31T08:25:00Z -> 2026-10-29T08:25:00Z (25920 bars).
Windows: 24 h, one starting every hour; train = windows ending by 2026-09-29T08:25:00Z
(1393 windows), test = windows starting after it (697 windows), full = all
2113 windows (including the ones straddling the split). Same engine and fee model as `bot.py`
(0.1 % per side, fills at the next bar's open, forced close at the last bar's close).

**Hit-rate** = share of windows that end with more than 10,000 USD. ~2113 overlapping windows are only
~90 independent days, so a hit-rate carries roughly +/- 10 percentage points of uncertainty: differences smaller
than that are noise.

| strategy | params | train hit % | test hit % | full hit % | median P&L % | 5th pct % | P(trades>=5) % | mean trades | guard % | corr w/ market |
|---|---|---|---|---|---|---|---|---|---|---|
| buy-and-hold (B0) | all in at open, out at close | 47.7 | 44.0 | 46.5 | -0.089 | -2.450 | 0.0 | 1.0 | 0.0 | +1.00 |
| random entries (B1, mean of 30 seeds) | p=0.04/bar, hold 24 bars | 16.4 | 11.3 | 14.7 | -1.064 | -2.935 | 85.2 | 5.7 | 0.0 | +0.72 |
| shipped: placeholder: buy a 3-bar dip, sell after 12 bars | lookback=3, hold=12 | 6.2 | 0.3 | 4.2 | -3.486 | -5.661 | 100.0 | 18.3 | 0.0 | +0.92 |

Random entries (B1) hit-rate range across seeds (5th-95th percentile): train 15.3-17.2 %,
test 9.8-12.8 %, full 14.0-15.4 %.
Buy-and-hold columns other than the hit-rate and P&L describe one round trip per window by construction.
One parameter set over all windows takes 1.3 s (pure Python, one core).

Why random entries score far below 50 %: with zero fees the same random strategy wins 51-55 % of windows
(checked on every third window, 5 seeds); with 0.1 % per side its ~5.7 round trips cost ~1.1 % of capital per day,
which a random 24 h path rarely repays. Any strategy here has to beat that fee drag, not a coin flip.

## Candidates (top 3 per family by train hit-rate; test shown, never used for ranking)

| strategy | params | train hit % | test hit % | full hit % | median P&L % | 5th pct % | P(trades>=5) % | mean trades | guard % | corr w/ market |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 #1 (train rank) | H=48, ema_n=24, k=1.0, min_edge=0.003, s=3, vol_n=72 | 27.3 | 30.6 | 28.1 | +0.000 | -1.203 | 1.0 | 1.4 | 0.0 | +0.45 |
| S1 #2 (train rank) | H=48, ema_n=24, k=1.0, min_edge=0.003, s=4, vol_n=72 | 27.3 | 33.0 | 28.9 | +0.000 | -1.167 | 1.0 | 1.3 | 0.0 | +0.44 |
| S1 #3 (train rank) | H=48, ema_n=24, k=1.0, min_edge=0.003, s=None, vol_n=72 | 27.3 | 33.0 | 28.9 | +0.000 | -1.167 | 1.0 | 1.3 | 0.0 | +0.44 |
| S2 #1 (train rank) | T=5, g=0.0018, t=0.0051 | 62.2 | 59.3 | 61.2 | +0.093 | -1.803 | 66.7 | 5.6 | 0.0 | +0.56 |
| S2 #2 (train rank) | T=5, g=0.0018, t=0.006 | 62.1 | 59.8 | 61.4 | +0.100 | -1.813 | 64.6 | 5.2 | 0.0 | +0.57 |
| S2 #3 (train rank) | T=5, g=0.002, t=0.0051 | 61.9 | 61.1 | 61.6 | +0.095 | -1.746 | 63.0 | 5.3 | 0.0 | +0.54 |
| S3 #1 (train rank) | H=96, L=18, trail=0.015 | 32.7 | 28.8 | 31.4 | -0.520 | -2.589 | 0.0 | 2.6 | 0.0 | +0.90 |
| S3 #2 (train rank) | H=96, L=24, trail=0.015 | 32.6 | 28.7 | 31.3 | -0.539 | -2.641 | 0.0 | 2.4 | 0.0 | +0.89 |
| S3 #3 (train rank) | H=96, L=18, trail=0.018 | 32.4 | 28.3 | 31.0 | -0.550 | -2.792 | 0.0 | 2.6 | 0.0 | +0.89 |

Parameter sets run: S1 278, S2 124, S3 89 (full per-set metrics in the CSVs next to this file).

## Selection (PLAN.md 4.3)

- S1 #1 (train rank) (H=48, ema_n=24, k=1.0, min_edge=0.003, s=3, vol_n=72): train 27.3 %, test 30.6 % (gap +3.3 pp) -> eligible
- S1 #2 (train rank) (H=48, ema_n=24, k=1.0, min_edge=0.003, s=4, vol_n=72): train 27.3 %, test 33.0 % (gap +5.7 pp) -> discarded (gap > 5 pp)
- S1 #3 (train rank) (H=48, ema_n=24, k=1.0, min_edge=0.003, s=None, vol_n=72): train 27.3 %, test 33.0 % (gap +5.7 pp) -> discarded (gap > 5 pp)
- S2 #1 (train rank) (T=5, g=0.0018, t=0.0051): train 62.2 %, test 59.3 % (gap -3.0 pp) -> eligible
- S2 #2 (train rank) (T=5, g=0.0018, t=0.006): train 62.1 %, test 59.8 % (gap -2.3 pp) -> eligible
- S2 #3 (train rank) (T=5, g=0.002, t=0.0051): train 61.9 %, test 61.1 % (gap -0.8 pp) -> eligible
- S3 #1 (train rank) (H=96, L=18, trail=0.015): train 32.7 %, test 28.8 % (gap -3.9 pp) -> eligible
- S3 #2 (train rank) (H=96, L=24, trail=0.015): train 32.6 %, test 28.7 % (gap -3.9 pp) -> eligible
- S3 #3 (train rank) (H=96, L=18, trail=0.018): train 32.4 %, test 28.3 % (gap -4.1 pp) -> eligible

**Selected: S2 #1 (train rank), T=5, g=0.0018, t=0.0051.** Train hit-rate 62.2 %, test 59.3 %, edge over random entries (full) +46.5 pp, over buy-and-hold +14.7 pp. Its P(trades >= 5) is 67 % without the pacing guard; Phase 4 adds the guard.
