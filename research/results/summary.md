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
