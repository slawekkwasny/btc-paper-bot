"""The shipped strategy: a tranche grid that buys dips below a 3-hour average and sells each tranche on a small bounce.

When it buys: when the 5-minute close is G (0.18 %) below its 36-bar (3-hour) exponential moving average, it buys a
tranche of 20 % of the starting cash. If the price keeps falling, it buys another tranche every further G below the
last buy, up to MAX_LOTS (5) tranches. No new tranches in the last 3 hours of the window.
When it sells: each tranche is sold on its own as soon as the close is TARGET (0.51 %) above that tranche's buy price,
which clears the 0.2 % round-trip fee. Whatever is still open at the end of the 24 hours is sold at the last close.
Why: at 15-minute-to-hours horizons BTC tends to overshoot and partly snap back (short-horizon reversal). Small,
frequent targets make many small wins; the cost is rare bigger losses on days that trend down all day, when the
tranches are still open at the forced close. Parameters were chosen on the first 60 days of 5-minute history and
checked on the last 30 (research/results/summary.md).

Pacing guard (the >= 5-trade rule): from bar 264 (22 h into the window), if closed trades + open tranches < 5, it buys
one small guard tranche (5 % of the starting cash) per bar until 5 trades are certain; a guard tranche sells at the
EMA, at the target, or after 6 bars, and whatever is left closes at the end. Guard tranches are small on purpose: they
exist only to satisfy the rule and cost little in fees. The engine's no-entry zone (last 6 bars) still applies.
`guard_fired` records whether the guard was needed (research/results/summary.md reports how often, and its cost).
"""

G = 0.0018  # dip below the EMA anchor (first tranche) and between tranches
TARGET = 0.0051  # take-profit per tranche, from its own buy price
MAX_LOTS = 5
EMA_N = 36  # bars (3 hours)
TRANCHE = 0.2  # share of starting cash per tranche
LAST_ENTRY = 36  # no normal tranches when this many bars or fewer are left

MIN_TRADES = 5
GUARD_FROM, GUARD_HOLD = 264, 6  # bar where the guard may start; max bars a guard tranche is held
GUARD_SIZE = 0.05  # share of starting cash per guard tranche
BAR = 300


class Strategy:
    name = "tranche grid (dip below 3 h EMA, 20 % tranches, per-tranche take-profit)"

    def __init__(self, g=G, t=TARGET, T=MAX_LOTS, guard=True, ema_n=EMA_N, tranche=TRANCHE, last_entry=LAST_ENTRY,
                 guard_size=GUARD_SIZE):
        self.params = {"g": g, "t": t, "T": T}
        self.g, self.t, self.T, self.guard = g, t, T, guard
        self.share, self.last_entry = tranche, last_entry
        self.guard_size = guard_size
        self.alpha = 2 / (ema_n + 1)
        self.ema = self.tranche = None
        self.seen = 0
        self.guard_fired = False

    def on_bar(self, bars, lots, ctx):
        for j in range(self.seen, len(bars)):  # incremental EMA over every bar seen so far (warm-up included)
            c = bars[j].close
            self.ema = c if self.ema is None else self.ema + self.alpha * (c - self.ema)
        self.seen = len(bars)
        if self.tranche is None:
            self.tranche = self.share * ctx.cash
            self.guard_tranche = self.guard_size * ctx.cash
        close, i = bars[-1].close, ctx.bar_index
        count = ctx.trades_closed + len(lots)
        guard_from = ctx.window_start + (GUARD_FROM + 1) * BAR  # guard tranches fill at bar 265 or later
        orders, held = [], []
        for lot in lots:
            if close >= lot.buy_price * (1 + self.t):
                orders.append(("sell", lot.lot_id, "target"))
            elif lot.buy_time >= guard_from and (close >= self.ema or lot.bars_held >= GUARD_HOLD):
                orders.append(("sell", lot.lot_id, "guard"))
            else:
                held.append(lot)
        if not ctx.entries_allowed:
            return orders

        if self.guard and count < MIN_TRADES and i >= GUARD_FROM:
            self.guard_fired = True
            need = MIN_TRADES - count
            orders.append(("buy", min(self.guard_tranche, ctx.cash / need)))
            return orders

        if ctx.bars_left <= self.last_entry or len(held) >= self.T or ctx.cash < self.tranche:
            return orders
        if held:
            trigger = close <= max(held, key=lambda lot: lot.lot_id).buy_price * (1 - self.g)
        else:
            trigger = close <= self.ema * (1 - self.g)
        if trigger:
            orders.append(("buy", self.tranche))
        return orders
