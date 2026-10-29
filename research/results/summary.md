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
| shipped: tranche grid (dip below 3 h EMA, 20 % tranches, per-tranche take-profit) | g=0.0018, t=0.0051, T=5 | 59.2 | 57.2 | 58.5 | +0.079 | -1.803 | 100.0 | 6.5 | 33.3 | +0.55 |

Random entries (B1) hit-rate range across seeds (5th-95th percentile): train 15.3-17.2 %,
test 9.8-12.8 %, full 14.0-15.4 %.
Buy-and-hold columns other than the hit-rate and P&L describe one round trip per window by construction.
One parameter set over all windows takes 2.2 s (pure Python, one core).

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

## Shipped strategy with the >= 5-trade pacing guard

| strategy | params | train hit % | test hit % | full hit % | median P&L % | 5th pct % | P(trades>=5) % | mean trades | guard % | corr w/ market |
|---|---|---|---|---|---|---|---|---|---|---|
| shipped: tranche grid (dip below 3 h EMA, 20 % tranches, per-tranche take-profit) | g=0.0018, t=0.0051, T=5, guard on | 59.2 | 57.2 | 58.5 | +0.079 | -1.803 | 100.0 | 6.5 | 33.3 | +0.55 |
| same, guard off (= S2 selected) | g=0.0018, t=0.0051, T=5 | 62.2 | 59.3 | 61.2 | +0.093 | -1.803 | 66.7 | 5.6 | 0.0 | +0.56 |

- The guard fired in 33.3 % of windows (train 36.7 %, test 27.3 %). On those windows it changed P&L by -0.027 percentage points on average; it turned 57 winning windows into losers and 0 losers into winners.
- P(trades >= 5) with the guard: 100.0 % (without: 66.7 %).
- Known failure mode, trend-down days: on the 201 windows where buy-and-hold lost more than 2 %, the shipped strategy ended in profit in 3.5 % of them (median P&L -1.72 %).
- Per-window results: shipped_windows.csv.

How the guard was chosen (train split only, same strategy parameters): PLAN.md's guard lowered the dip threshold by
0.75x every 12 bars from bar 192 and then forced full 20 % tranches from bar 264. That cost 8 pp of train hit-rate
(62.2 % -> 54.2 %) because late full-size tranches and their fees flip small winning days. Measured train hit-rates:

| guard tranche size | with threshold decay from bar 192 | forced tranches from bar 264 only |
|---|---|---|
| 20 % | 54.2 % | 52.8 % |
| 10 % | 57.0 % | 56.6 % |
| 5 % | 58.4 % | **59.2 % (shipped)** |
| 2 % | 59.7 % | 60.6 % |

All variants give P(trades >= 5) = 100 % on train. Smaller is cheaper because the guard's job is only to complete the
round trips the rule asks for; 5 % was chosen over 2 % (+1.4 pp, inside the noise) so the guard trades remain real
positions rather than token ones, and the threshold decay was dropped (no gain, one fewer moving part).
