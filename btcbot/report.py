"""Plain-text report: window and source, every trade, totals, buy-and-hold, guard status."""
from datetime import datetime, timezone

# Share of historical 24 h windows the shipped strategy ended in profit (research/evaluate.py); set in Phase 4.
BACKTEST_HIT_RATE = 58.5
BACKTEST_TEST_HIT_RATE = 57.2
BACKTEST_BH_HIT_RATE = 46.5
BACKTEST_WINDOWS = 2113


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hhmm(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%m-%d %H:%M")


def render(result, meta, start, end, strategy, cash=10_000.0):
    params = ", ".join(f"{k}={v}" for k, v in strategy.params.items())
    lines = [
        "BTC paper-trading bot: last 24 h replay",
        f"window     {iso(start)} -> {iso(end)} (UTC)",
        f"data       {meta['source']}, {meta['bars_in_window']} x 5-min bars in window "
        f"(+{meta['warmup_bars']} warm-up, {meta['gaps_filled']} gaps filled)",
    ]
    if meta.get("note"):
        lines.append(f"note       {meta['note']}")
    lines += [
        f"strategy   {strategy.name} ({params})",
        f"start      {cash:,.2f} USD, fee 0.1 % per side, long only",
        "",
        f"{'#':>2}  {'buy (UTC)':11}  {'buy price':>10}  {'sell (UTC)':11}  {'sell price':>10}  {'size BTC':>10}  "
        f"{'fees USD':>8}  {'P&L USD':>9}  {'P&L %':>7}  exit",
    ]
    for n, t in enumerate(result.trades, 1):
        lines.append(f"{n:>2}  {hhmm(t.buy_time):11}  {t.buy_price:>10,.2f}  {hhmm(t.sell_time):11}  "
                     f"{t.sell_price:>10,.2f}  {t.qty_btc:>10.6f}  {t.fees_usd:>8.2f}  {t.pnl_usd:>+9.2f}  "
                     f"{t.pnl_pct:>+6.3f}%  {t.exit_reason}")
    if not result.trades:
        lines.append("    (no trades)")
    fees = sum(t.fees_usd for t in result.trades)
    wins = sum(1 for t in result.trades if t.pnl_usd > 0)
    lines += [
        "",
        f"trades          {len(result.trades)} round trips ({wins} winners), fees paid {fees:,.2f} USD",
        f"final balance   {result.final_cash:,.2f} USD, 0 BTC",
        f"profit          {result.pnl_usd:+,.2f} USD ({result.pnl_pct:+.3f} %)",
        f"buy-and-hold    {result.bh_pnl_usd:+,.2f} USD ({result.bh_pnl_pct:+.3f} %) net of fees; "
        f"price moved {result.price_change_pct:+.3f} %",
        f"5-trade guard   {'fired' if result.guard_fired else 'not fired'}",
        f"verdict         {'PROFITABLE' if result.pnl_usd > 0 else 'NOT PROFITABLE'}, "
        f"{'>= 5 trades' if len(result.trades) >= 5 else 'FEWER THAN 5 TRADES'}, flat at end",
    ]
    if BACKTEST_HIT_RATE is None:
        lines.append("backtest        hit-rate over historical 24 h windows: not measured yet (see README)")
    else:
        lines.append(f"backtest        hit-rate over {BACKTEST_WINDOWS} historical 24 h windows: "
                     f"{BACKTEST_HIT_RATE:.1f} % in profit (last-30-day test split {BACKTEST_TEST_HIT_RATE:.1f} %, "
                     f"buy-and-hold {BACKTEST_BH_HIT_RATE:.1f} %; see README)")
    return "\n".join(lines)
