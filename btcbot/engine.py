"""Paper-trading engine shared by bot.py and the research harness.

Timing (no look-ahead): the strategy decides on the close of bar i, seeing bars[0..i] only; the engine fills those
orders at the open of bar i+1. On the last bar of the window every open lot is sold at its close (exit reason "eod").

Fees (0.1 % per side): a buy of X USD costs X and yields 0.999 * X / price BTC; a sell of q BTC at p yields
0.999 * q * p USD. Trade P&L = net sell proceeds - X.
"""
from collections import namedtuple
from collections.abc import Sequence
from dataclasses import dataclass

from btcbot.data import BAR

Lot = namedtuple("Lot", "lot_id buy_time buy_price qty_btc usd_spent buy_fee bars_held")
Trade = namedtuple("Trade", "buy_time buy_price sell_time sell_price qty_btc buy_fee sell_fee fees_usd "
                            "pnl_usd pnl_pct exit_reason")
Result = namedtuple("Result", "trades final_cash pnl_usd pnl_pct bh_pnl_usd bh_pnl_pct price_change_pct "
                              "guard_fired meta")


@dataclass
class Ctx:
    window_start: int
    window_end: int
    bar_index: int  # 0..287 inside the window
    bars_left: int  # window bars after this one
    trades_closed: int
    cash: float
    entries_allowed: bool


class History(Sequence):
    """Read-only view of bars[0..n-1]. Indexing past the current bar raises IndexError, so a strategy cannot see
    the future; it avoids copying the whole history into a new tuple on every bar."""

    def __init__(self, bars, n):
        self._bars, self._n = bars, n

    def __len__(self):
        return self._n

    def __getitem__(self, i):
        if isinstance(i, slice):
            return tuple(self._bars[j] for j in range(*i.indices(self._n)))
        if i < 0:
            i += self._n
        if not 0 <= i < self._n:
            raise IndexError("bar index out of range (no look-ahead)")
        return self._bars[i]


def buy_and_hold(first_open, last_close, cash, fee):
    """Net P&L (USD, %) of putting all cash in at the first open and selling at the last close, plus the raw move."""
    final = (1 - fee) * ((1 - fee) * cash / first_open) * last_close
    return final - cash, (final / cash - 1) * 100, (last_close / first_open - 1) * 100


def simulate(bars, start, end, strategy, cash=10_000.0, fee=0.001, no_entry_bars=6, log=None):
    """Replay bars (warm-up included) and trade only those with start <= open_time < end."""
    bars = tuple(bars)
    window = [i for i, b in enumerate(bars) if start <= b.open_time < end]
    if not window:
        raise ValueError("no bars inside the window")
    first, last = window[0], window[-1]
    start_cash = cash
    lots = {}  # lot_id -> (Lot, fill index)
    trades, pending = [], []
    next_id, refused = 0, 0

    def close_lot(lot_id, i, price, reason, at_close=False):
        nonlocal cash
        lot, _ = lots.pop(lot_id)
        gross = lot.qty_btc * price
        sell_fee = fee * gross
        cash += gross - sell_fee
        pnl = gross - sell_fee - lot.usd_spent
        sell_time = bars[i].open_time + (BAR if at_close else 0)  # fills happen at the bar's open or close
        trades.append(Trade(lot.buy_time, lot.buy_price, sell_time, price, lot.qty_btc, lot.buy_fee,
                            sell_fee, lot.buy_fee + sell_fee, pnl, pnl / lot.usd_spent * 100, reason))
        if log:
            log(f"  sell lot {lot_id} @ {price:.2f} ({reason}) pnl {pnl:+.2f}")

    for i in range(first, last + 1):
        bar = bars[i]
        # 1. fill the orders decided on the previous bar at this bar's open: sells first, then buys
        for order in sorted(pending, key=lambda o: o[0] != "sell"):
            if order[0] == "sell":
                if order[1] in lots:
                    close_lot(order[1], i, bar.open, order[2])
                else:
                    refused += 1
            elif order[0] == "buy":
                usd = order[1]
                if usd > cash + 1e-9 or usd <= 0:
                    refused += 1
                    continue
                usd = min(usd, cash)
                buy_fee = fee * usd
                cash -= usd
                lots[next_id] = (Lot(next_id, bar.open_time, bar.open, (usd - buy_fee) / bar.open, usd, buy_fee, 0), i)
                if log:
                    log(f"  buy lot {next_id} {usd:.2f} USD @ {bar.open:.2f}")
                next_id += 1
        pending = []
        # 2. last bar of the window: force everything flat at the close
        if i == last:
            for lot_id in list(lots):
                close_lot(lot_id, i, bar.close, "eod", at_close=True)
            break
        # 3. ask the strategy, which sees bars[0..i] only
        bars_left = last - i
        ctx = Ctx(start, end, i - first, bars_left, len(trades), cash, bars_left > no_entry_bars)
        open_lots = tuple(lot._replace(bars_held=i - fill_i) for lot, fill_i in lots.values())
        orders = strategy.on_bar(History(bars, i + 1), open_lots, ctx) or []
        for order in orders:
            if order[0] == "buy" and not ctx.entries_allowed:
                refused += 1
                if log:
                    log(f"  refused buy at bar {ctx.bar_index}: inside the last {no_entry_bars} bars")
            else:
                pending.append(order)
        if log and orders:
            log(f"bar {ctx.bar_index:3d} close {bar.close:.2f}: {orders}")

    pnl = cash - start_cash
    bh_usd, bh_pct, move = buy_and_hold(bars[first].open, bars[last].close, start_cash, fee)
    meta = {"window_bars": last - first + 1, "refused_orders": refused}
    return Result(trades, cash, pnl, pnl / start_cash * 100, bh_usd, bh_pct, move,
                  bool(getattr(strategy, "guard_fired", False)), meta)
