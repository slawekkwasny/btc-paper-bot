"""Candidate strategies for the research harness. Same interface as btcbot/strategy.py:
on_bar(bars, lots, ctx) -> list of ("buy", usd) | ("sell", lot_id, reason).
"""
import math
import random
from collections import deque

from btcbot.strategy import Strategy


class RandomEntry:
    """Baseline B1: when flat, enter with probability p per bar; exit after `hold` bars. Seeded per window."""
    name = "random entries"

    def __init__(self, seed=0, p=0.04, hold=24):
        self.seed, self.p, self.hold = seed, p, hold
        self.params = {"seed": seed, "p": p, "hold": hold}
        self.rng = None

    def on_bar(self, bars, lots, ctx):
        if self.rng is None:
            self.rng = random.Random(self.seed * 1_000_003 + ctx.window_start)
        if lots:
            return [("sell", lot.lot_id, "time") for lot in lots if lot.bars_held >= self.hold]
        if ctx.entries_allowed and self.rng.random() < self.p:
            return [("buy", ctx.cash)]
        return []


# --- shared indicators: incremental, trailing only ---

class Indicators:
    """EMA of closes and the std of 5-minute log returns over `vol_n` bars, updated one bar at a time."""

    def __init__(self, ema_n, vol_n):
        self.alpha, self.vol_n = 2 / (ema_n + 1), vol_n
        self.ema = self.prev = None
        self.rets = deque()
        self.s = self.ss = 0.0

    def update(self, close):
        self.ema = close if self.ema is None else self.ema + self.alpha * (close - self.ema)
        if self.prev is not None:
            r = math.log(close / self.prev)
            self.rets.append(r)
            self.s += r
            self.ss += r * r
            if len(self.rets) > self.vol_n:
                old = self.rets.popleft()
                self.s -= old
                self.ss -= old * old
        self.prev = close

    def sigma_h(self):
        """1-hour volatility estimate: std of 5-minute log returns * sqrt(12); None until warm."""
        n = len(self.rets)
        if n < self.vol_n:
            return None
        return math.sqrt(max((self.ss - self.s * self.s / n) / (n - 1), 0.0) * 12)


class Base:
    """Feeds every bar the strategy has not seen yet (warm-up included) into `self.update(bar)`."""
    guard_fired = False

    def catch_up(self, bars):
        for j in range(getattr(self, "_seen", 0), len(bars)):
            self.update(bars[j])
        self._seen = len(bars)


class S1(Base):
    """Dip reversion, single lot: buy when the close is k one-hour sigmas below its EMA anchor (and that gap is
    worth at least min_edge); sell back at the anchor, after H bars, or at a stop s sigmas below it."""
    name = "S1 dip reversion"

    def __init__(self, ema_n=36, vol_n=72, k=1.5, H=24, s=None, min_edge=0.003):
        self.params = {"ema_n": ema_n, "vol_n": vol_n, "k": k, "H": H, "s": s, "min_edge": min_edge}
        self.k, self.H, self.s, self.min_edge = k, H, s, min_edge
        self.ind = Indicators(ema_n, vol_n)

    def update(self, bar):
        self.ind.update(bar.close)

    def on_bar(self, bars, lots, ctx):
        self.catch_up(bars)
        sig = self.ind.sigma_h()
        if sig is None:
            return []
        dev = bars[-1].close / self.ind.ema - 1
        if lots:
            lot = lots[0]
            if dev >= 0:
                return [("sell", lot.lot_id, "anchor")]
            if lot.bars_held >= self.H:
                return [("sell", lot.lot_id, "time")]
            if self.s is not None and dev <= -self.s * sig:
                return [("sell", lot.lot_id, "stop")]
            return []
        if ctx.entries_allowed and dev <= -self.k * sig and self.k * sig >= self.min_edge:
            return [("buy", ctx.cash)]
        return []


class S2(Strategy):
    """Tranche grid. The logic lives in btcbot/strategy.py (one copy, shared with the live bot); research runs it
    with the pacing guard off so the grid measures the strategy itself."""
    name = "S2 tranche grid"

    def __init__(self, g=0.005, t=0.006, T=5, guard=False):
        super().__init__(g=g, t=t, T=T, guard=guard)


class S3(Base):
    """Breakout momentum, single lot: buy when the close exceeds the highest high of the previous L bars; sell on a
    trailing stop `trail` below the highest close since entry, or after H bars."""
    name = "S3 breakout momentum"

    def __init__(self, L=48, trail=0.01, H=96):
        self.params = {"L": L, "trail": trail, "H": H}
        self.L, self.trail, self.H = L, trail, H
        self.highs = []
        self.peak = None

    def update(self, bar):
        self.highs.append(bar.high)

    def on_bar(self, bars, lots, ctx):
        self.catch_up(bars)
        close = bars[-1].close
        if lots:
            lot = lots[0]
            self.peak = max(self.peak or lot.buy_price, close)
            if close < self.peak * (1 - self.trail):
                return [("sell", lot.lot_id, "trail")]
            if lot.bars_held >= self.H:
                return [("sell", lot.lot_id, "time")]
            return []
        self.peak = None
        if len(self.highs) > self.L and ctx.entries_allowed and close > max(self.highs[-self.L - 1:-1]):
            return [("buy", ctx.cash)]
        return []
