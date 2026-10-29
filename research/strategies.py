"""Candidate strategies for the research harness. Same interface as btcbot/strategy.py:
on_bar(bars, lots, ctx) -> list of ("buy", usd) | ("sell", lot_id, reason).
"""
import random


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
