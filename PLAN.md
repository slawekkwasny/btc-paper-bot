# PLAN.md — how this take-home gets built

Companion to CLAUDE.md (the rules) and docs/brief.md (the brief). Five phases; each ends with real output, passing
tests and commits. Paste the prompts in §1 into Claude Code one at a time and review the checkpoints before moving on.

## 0. The idea in one paragraph

A strategy that is profitable on *every* 24-hour window of BTC, with ≥ 5 round trips at 0.2 % round-trip cost, does
not exist; the honest deliverable is a bot whose strategy is profitable on as large a share of historical 24-hour
windows as possible, plus the evidence. So the project is built around an evaluation harness: ~90 days of 5-minute
candles, a 24-hour window starting every hour (~2,000 windows, but only ~90 independent days), parameters picked on
the first 60 days and verified on the last 30, and a random-entry baseline that shows what chance looks like. The
judges' criterion is the *sign* of one rerun, not the expected return, which favours high-hit-rate mean reversion
(many small wins, rare larger losses on trend days) over momentum (few big wins). Published work finds reversal in
BTC at 15-minute to multi-hour horizons (§10), which is exactly the horizon that yields 5–15 trades a day. The README
says all of this plainly, with the measured hit-rate and where the strategy fails.

## 1. Driving Claude Code

Setup (human, ~10 min):

1. `mkdir btc-paper-bot && cd btc-paper-bot && git init`
2. Copy `CLAUDE.md`, `PLAN.md` and the brief (as `docs/brief.md`) into it.
   `git add -A && git commit -m "Add brief, project rules and work plan"`
3. Create a public GitHub repo and push: `gh repo create btc-paper-bot --public --source=. --push`
   (or create it in the web UI and `git remote add origin … && git push -u origin main`).
4. `python3 --version` (need ≥ 3.10; `brew install python` if missing), then run `claude` in the folder.

Prompts — paste one per phase, wait for the stop-and-summarise, check the checkpoint, then paste the next:

**Phase 1**
> Read CLAUDE.md and PLAN.md in full. Do Phase 1 only (PLAN.md §2): scaffold the layout; implement btcbot/data.py
> with the Coinbase fetcher (paged, ≤ 300 bars per request), the Kraken and Binance fallbacks and validation;
> btcbot/engine.py with the fee model, lots, forced close and buy-and-hold; a placeholder strategy; the tests
> listed in §2.4; and bot.py that fetches the last 24 h and prints the report. Run the tests and `python3 bot.py`
> for real and show me the full output. Commit in the small steps listed in §2.5. Stop after Phase 1 and
> summarise what you verified and what you assumed.

**Phase 2**
> Do Phase 2 (PLAN.md §3): research/download_history.py for 90 days of 5-minute bars into data/btcusd_5m.csv
> (gitignored), and research/evaluate.py with rolling 24 h windows that reuse btcbot.engine, the train/test split,
> the summary metrics and the two baselines. Run it on the placeholder strategy and on both baselines and show me
> the summary table. Commit. Stop and summarise.

**Phase 3**
> Do Phase 3 (PLAN.md §4): implement S1, S2 and S3 in research/strategies.py with the exact interface of
> btcbot/strategy.py; run the parameter grids coarse-then-fine on the train split only; verify the top 3 of each
> family on the test split; write research/results/summary.md with the full table including the baselines and the
> losers. Apply the selection rule in §4.3 and recommend one strategy with one parameter set. Never tune on
> windows after the train end date. Commit after each family. Stop and show me the table.

**Phase 4**
> Do Phase 4 (PLAN.md §5): move the selected strategy and parameters into btcbot/strategy.py, add the ≥ 5-trade
> pacing guard, re-run evaluate.py on the shipped strategy (train, test, full) and record how often the guard
> fires; finalise the output format; add --end, --source and --verbose. Run `python3 bot.py` for real and show me
> the output. Commit. Stop.

**Phase 5**
> Do Phase 5 (PLAN.md §6 and §7): write README.md from the template with real numbers; run the clean-clone test
> from /tmp and paste the result; add the hands-on time log and the AI-tools section. Commit. Then list anything
> in docs/brief.md that we have not satisfied, if anything.

Checkpoints you check at each stop:

- Phase 1: printed window bounds are right (end = now floored to 5 min, start = end − 24 h, 288 bars); source
  used is Coinbase; tests pass; fee math matches CLAUDE.md rule 4; the report lists every field from the brief.
- Phase 2: ≈ 2,000 windows; random baseline hit-rate 40–50 %; buy-and-hold hit-rate ≈ 50 %; the harness runs
  one parameter set in a few seconds.
- Phase 3: the winner's train and test hit-rates are within ~5 percentage points; nothing is above ~80 % (if it
  is, suspect look-ahead or an optimistic fill); P(trades ≥ 5) ≈ 1 for the winner.
- Phase 4: `python3 bot.py` ends flat, shows every field, and states whether the guard fired.
- Phase 5: a fresh clone runs with one command; the README output is a real paste with a UTC timestamp.

## 2. Phase 1 — data, engine, tests (≈ 45 min hands-on)

### 2.1 `btcbot/data.py`

- `Candle = namedtuple("Candle", "open_time open high low close volume")`, open_time = unix seconds UTC,
  bar length `BAR = 300`.
- `window_bounds(now) -> (start, end)`: `end = now - now % BAR`, `start = end - 86400`.
- `fetch_candles(start, end, source="auto") -> list[Candle]` fetching `[start − WARMUP, end)` where
  `WARMUP = 24 h`. `source="auto"` tries coinbase → kraken → binance and prints which one succeeded and why the
  others failed. Each fetcher is one function; the shared HTTP helper does User-Agent, timeout, retries, pacing.
- Normalise, sort, dedupe, drop any bar with `open_time >= end`. Validate as in CLAUDE.md. Return the list plus
  a small dict of metadata (source, bars_in_window, gaps_filled).

### 2.2 `btcbot/engine.py`

- `Lot(lot_id, buy_time, buy_price, qty_btc, usd_spent, buy_fee, bars_held)`
- `Trade(buy_time, buy_price, sell_time, sell_price, qty_btc, fees_usd, pnl_usd, pnl_pct, exit_reason)`
- Orders a strategy may return: `("buy", usd_amount)` and `("sell", lot_id, reason)`. Several per bar allowed.
- Strategy interface (a plain class):
  `on_bar(bars: tuple[Candle, ...], lots: tuple[Lot, ...], ctx) -> list[order]`
  `ctx` carries `window_start, window_end, bar_index (0..287 inside the window), bars_left, trades_closed, cash,
  entries_allowed`.
- `simulate(bars, start, end, strategy, cash=10_000.0, fee=0.001, no_entry_bars=6) -> Result`:
  - iterate over all bars (warm-up included) but only act inside the window;
  - at bar i: first fill the orders decided at bar i − 1 at `bars[i].open`; then, if i is the last bar of the
    window, sell every lot at `bars[i].close` with reason `eod` and stop; otherwise call
    `strategy.on_bar(bars[:i+1], lots, ctx)` and queue the returned orders;
  - the engine refuses buys when `bars_left <= no_entry_bars` (`ctx.entries_allowed = False`), buys that exceed
    cash, and sells of unknown lot ids;
  - buy-and-hold: all cash at the first window bar's open, sold at the last bar's close, same fees; also keep the
    raw price change.
  - `Result(trades, final_cash, pnl_usd, pnl_pct, bh_pnl_usd, bh_pnl_pct, price_change_pct, guard_fired, meta)`.
- The strategy only ever sees `bars[:i+1]` as a tuple; it never gets the full list.

### 2.3 `bot.py` and `btcbot/report.py`

- `python3 bot.py` = fetch (last 24 h, auto source) → simulate → print report. Exit code 0 always, unless data
  fetch fails (then a one-line error and exit 1).
- `--end 2026-10-28T12:00:00Z` replays the 24 h ending at that time (for reproducing README output and the Loom).
  `--source coinbase|kraken|binance`. `--verbose` prints per-bar decisions.
- Report: header (window start/end UTC, source, bars, strategy name + parameters), one line per trade, totals
  block, buy-and-hold block, guard status, and one line: "backtest hit-rate over N historical 24 h windows: X %
  (see README)". That last number is a constant updated in Phase 4.

### 2.4 Tests (`python3 -m unittest discover tests`)

- fee math: buy 1,000 USD at 50,000 → 0.01998 BTC, cash 9,000; sell it at 50,000 → cash 9,998.001; P&L −1.999.
- forced flat: a strategy that buys and never sells ends with 0 BTC and one `eod` trade.
- no-entry zone: a buy signalled inside the last 6 bars is refused.
- no look-ahead, two tests: (a) the strategy records the max open_time it saw at each decision; assert it is
  strictly less than the fill bar's open_time; (b) run a deterministic strategy on a series, then replace every bar
  after index k with random garbage and assert all decisions up to k are identical.
- data: parsing fixtures for the three API shapes (small JSON samples saved in tests/fixtures), the window maths,
  the still-open-bar drop, and the gap handling.

### 2.5 Commits

1. "Scaffold package layout and .gitignore" 2. "Add Coinbase candle fetcher with paging and validation"
3. "Add Kraken and Binance fallbacks" 4. "Add paper-trading engine with fee model and forced close"
5. "Add engine and fee tests, no-look-ahead tests" 6. "Add bot.py entry point and report printing"

## 3. Phase 2 — the evaluation harness (≈ 45 min hands-on)

### 3.1 `research/download_history.py`

90 days of 5-minute bars from Coinbase (paged, 300 bars per request, 0.25 s pacing ≈ 450 requests, a few minutes)
into `data/btcusd_5m.csv` with a resume: if the file exists, fetch only what is missing. Print bar count and gaps.

### 3.2 `research/evaluate.py`

- Load the CSV. Windows: start every 3600 s from `series_start + WARMUP` to `series_end − 86400`.
- For each window: `simulate(bars_slice, ws, ws + 86400, strategy_factory(params))` — the same engine as the bot.
- Per window record: start, pnl_pct, n_trades, guard_fired, bh_pnl_pct, price_change_pct, max_drawdown_pct.
- Split: train = windows starting before `series_start + 60 d`; test = the rest. Report train, test and full.
- Metrics per parameter set: hit_rate = share of windows with pnl_pct > 0; p_min_trades = share with
  n_trades ≥ 5; mean, median, 5th percentile and min of pnl_pct; mean trades; guard rate; correlation of pnl_pct
  with price_change_pct (how much the strategy is just long the market).
- Baselines: B0 buy-and-hold (hit-rate of net B&H > 0). B1 random entries: when flat, enter with probability
  0.04 per bar, exit after 24 bars; 30 seeds; report the mean and the 5–95 % range of the hit-rate across seeds.
  Edge = strategy hit-rate minus B1 mean.
- Output: `research/results/<strategy>_<grid>.csv` (one row per parameter set) and `summary.md` with a table.
- Note in summary.md: ~2,000 overlapping windows ≈ 90 independent days, so a hit-rate carries roughly ± 10
  percentage points of uncertainty. Differences smaller than that are noise.
- Speed: pure Python, ~2,000 windows × 288 bars ≈ 1–3 s per parameter set; grids of 100–300 sets are fine.

## 4. Phase 3 — candidates and selection (≈ 60 min hands-on)

### 4.1 Candidates (all on 5-minute bars; all parameters in bars)

Common indicator code (incremental, trailing only): `ema(n)`, `std of 5-min log returns over n bars`,
`sigma_h = std_5m * sqrt(12)` (1-hour volatility estimate), `dev = close / ema - 1`.

**S1 — dip reversion, single lot (the favourite)**
- Entry (flat, entries allowed): `dev <= -k * sigma_h` and `k * sigma_h >= min_edge` (don't trade dead markets
  where the expected bounce can't cover 0.2 %).
- Exit: `dev >= 0` (back at the anchor) or `bars_held >= H` or `dev <= -s * sigma_h` (stop; `s = None` = no stop).
- Size: all cash.
- Grid: anchor `ema_n ∈ {24, 36, 72}`, vol window `{36, 72}`, `k ∈ {1.0, 1.5, 2.0, 2.5}`, `H ∈ {12, 24, 48}`,
  `s ∈ {3, 4, None}`, `min_edge ∈ {0, 0.003, 0.005}`. Coarse pass with `vol window = 72, min_edge = 0.003`,
  then refine around the best.

**S2 — tranche grid (high hit-rate, negative skew; the main alternative)**
- Anchor `ema(36)`. Tranche = 20 % of starting cash, max `T` lots.
- First buy when `dev <= -g`; each further lot when `close <= last_buy_price * (1 - g)`.
- Each lot sells when `close >= lot.buy_price * (1 + t)`. No new lots in the last 36 bars. Everything closes at eod.
- Grid: `g ∈ {0.003, 0.005, 0.008}`, `t ∈ {0.004, 0.006, 0.009, 0.012}`, `T ∈ {3, 5}`.

**S3 — breakout momentum, single lot (the control; expected to score lower)**
- Entry: `close > max(high over the last L bars)`. Exit: `close < peak_close_since_entry * (1 - trail)` or
  `bars_held >= H`.
- Grid: `L ∈ {24, 48, 96}`, `trail ∈ {0.005, 0.010, 0.015}`, `H ∈ {48, 96}`.

**S4 — regime switch (only if time remains)**
Efficiency ratio over 144 bars `ER = |close_t − close_{t−144}| / Σ|Δclose|`; `ER > θ` → S3 rules, else S1 rules;
`θ ∈ {0.25, 0.35}`. More parameters, so it must beat S1 on *test* by more than the noise to be chosen.

### 4.2 Procedure

Coarse grid on train → top 10 per family → fine grid around them on train → top 3 per family evaluated on test →
one full table with train / test / full metrics for everything that was run, including the losers. No parameter
is ever picked by looking at test or at today's live run.

### 4.3 Selection rule

1. Must have `p_min_trades ≥ 0.98` on all windows once the pacing guard is on (Phase 4), and always end flat.
2. Highest train hit-rate whose test hit-rate is within 5 percentage points of train. A bigger drop means
   overfitting: discard it.
3. Ties (within noise): fewer parameters, better 5th-percentile pnl, lower correlation with the market move.
4. Expect 55–70 % on test. Anything ≥ 85 % is a bug (look-ahead, optimistic fills, a leak from warm-up) until
   proven otherwise. A test hit-rate near the random baseline means the strategy has no edge; say so in the README
   and still ship the best one.

### 4.4 Commits

"Add candidate strategies S1–S3", "Add S1 grid results", "Add S2 grid results", "Add S3 grid results",
"Add results summary and strategy selection".

## 5. Phase 4 — ship the bot (≈ 30 min hands-on)

- `btcbot/strategy.py` = the winner with its parameters as module constants, docstring explaining when it buys,
  when it sells and why, in the words the README will reuse.
- Pacing guard (the ≥ 5-trade rule, transparent and counted): from bar 192 (16 h) on, if
  `trades_closed + open lots < 5`, multiply the entry threshold `k` (or `g`) by 0.75 every 12 bars; from bar 264
  (22 h), if still short, enter at the next flat bar with threshold 0 and exit at the anchor or after 6 bars.
  The engine's no-entry zone (last 6 bars) still applies. `Result.guard_fired` records it; evaluate.py reports the
  firing rate and its average cost. The README states both numbers.
- Re-run evaluate.py on the shipped strategy; update the hit-rate constant printed by bot.py; commit the results.
- `python3 bot.py` twice in a row must produce the same output (same bars, deterministic strategy, no randomness).

## 6. Phase 5 — README, clean-clone test, Loom (≈ 60 min hands-on, mostly the Loom)

- README from the template in §7, every number real.
- Clean-clone test, verbatim:
  `cd /tmp && rm -rf btc-paper-bot && git clone <repo-url> && cd btc-paper-bot && python3 bot.py`
  Paste the first and last lines of the output into the README with the date and `python3 --version`.
- Run `python3 bot.py` once per day until you send it, and keep every output in the README (`runs/` folder with
  the full stdout, dated). Three honest results beat one lucky one.
- Record the Loom from the script in §8. Share link set to "anyone with the link".
- Final commit: "Add README with run output and Loom link".

## 7. README template

```markdown
# BTC paper-trading bot (take-home)

One command replays the last 24 hours of BTC-USD 5-minute candles from Coinbase's public API, trades them with the
strategy below, and prints every trade and the totals.

## Run it
Prerequisites: Python 3.10+ (macOS: `xcode-select --install` or `brew install python`). No packages.
    git clone <url> && cd btc-paper-bot && python3 bot.py
Options: `--end 2026-10-28T12:00:00Z` replays a past window; `--source kraken|binance` forces a fallback feed.

## The strategy (in a few sentences)
When it buys: … When it sells: … Why: …  (copy the strategy docstring, then one sentence on the ≥5-trade guard)

## Can this be guaranteed? No — here is the evidence
… one paragraph: fees ≥ 1 % of notional over 5 full-size trades, 24 h of BTC is mostly noise, so the right question
is how often the strategy ends a random 24 h window in profit. Then the table from research/results/summary.md:
| strategy | params | train hit-rate | test hit-rate | median P&L | 5th pct | P(trades ≥ 5) | guard rate |
| buy-and-hold | — | … | … | | | | |
| random entries (30 seeds) | — | … ± … | … ± … | | | | |
| S1 … | | | | | | | |
… and the sentence about ± 10 pp uncertainty with ~90 independent days.

## How I got here, and what didn't work
Bullet list: what was tried, what the numbers said, why it was dropped (S3 momentum, the stop-loss variants, the
tighter take-profit, S4 if tried). Link research/results/summary.md.

## Known failure mode
Trend-down days: the forced eod close realises the loss. Hit-rate conditional on B&H < −2 %: … %.

## My runs
    $ python3 bot.py        # 2026-10-30 09:12 UTC, macOS 15, Python 3.12.x
    <full output>
(+ one block per additional day)

## Clean-clone test
    <command, date, first/last lines>

## AI tools used
Claude (claude.ai) for research and the plan (PLAN.md), Claude Code for implementation; every result in this README
comes from running the code. Hands-on time: … h … min (log in TIMELOG.md).

## Repo layout
…

## Loom
<link>
```

## 8. Loom script (5 minutes)

- 0:00 — Who I am, what the bot does, run `python3 bot.py` on screen while talking (it finishes in ~10 s).
- 0:40 — The core idea: BTC overshoots and snaps back at 15-minute-to-hours horizons; the bot buys a dip of k
  volatility units below a 3-hour anchor and sells when price is back at the anchor, or after H hours. Fees are
  0.2 % per round trip, so it only trades when the expected bounce covers that.
- 1:40 — Why a guarantee is impossible and what I measured instead: the rolling-window harness, train/test split,
  the random baseline. Show the summary table. Say the hit-rate and the ± 10 pp uncertainty out loud.
- 3:00 — How I got here: what I tried that didn't work (momentum, stops, tighter targets) and what the numbers said.
- 3:50 — Why it should keep working: it is the published reversal effect, three parameters, the same on train and
  test; and where it won't: trend-down days, which the forced close turns into losses.
- 4:30 — What I'd do with more time (limit-order fills, more history, a regime filter). Done.

## 9. Submission checklist (from the brief)

- [ ] Public repo link, full history, no squashing.
- [ ] Setup steps + one command tested from a fresh clone on a Mac, prerequisites named.
- [ ] README: strategy in a few sentences; how I got there and what didn't work; output of my run with date and
      time; AI tools used.
- [ ] 5-minute Loom: core idea, how I got to it, why it should keep working.
- [ ] Bot prints every trade (buy time/price, sell time/price, size, fees, P&L) and totals (trade count, final
      balance, profit USD and %, buy-and-hold).
- [ ] ≥ 5 trades, ends flat, 0.1 % fees both sides, long only, no look-ahead, real data, no keys, one command.
- [ ] If the measured hit-rate is near chance: the README says the task can't be done as set, with the evidence,
      and still ships the best strategy (the brief explicitly asks for this).

## 10. Background notes (for the README and the Loom)

- Reversal is the documented regularity at these horizons: a 2026 cross-market study finds significant directional
  mean reversion at 15-minute horizons in the large majority of Binance pairs (arXiv 2608.21888), and De Nicola
  (Ledger, 2021) finds negative first-order autocorrelation of BTC returns at 1-, 2- and 4-hour timeframes.
  That is why S1 is the favourite and why the anchor is hours, not minutes.
- Time-of-day effects exist in some samples (e.g. Quantpedia's 21:00–23:00 UTC finding) but Baur et al. (2019)
  find no persistent effects across time, so the bot does not depend on the clock.
- Fees: 0.1 % per side × 2 sides × ≥ 5 full-size trades ≥ 1 % of capital. The edge must clear that in 24 hours.

## 11. Time budget (hands-on, keep TIMELOG.md)

Phase 1 ≈ 45 min · Phase 2 ≈ 45 min · Phase 3 ≈ 60 min · Phase 4 ≈ 30 min · Phase 5 ≈ 60 min → ≈ 4 h.
Claude Code's running time is not hands-on time, but the brief asks which AI tools were used: say so plainly.
