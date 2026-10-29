"""The shipped strategy.

PLACEHOLDER (Phase 1): exercises the engine end to end; it has no edge. Phase 4 replaces it with the strategy and
parameters selected on the train split of historical windows (research/results/summary.md).

Interface used by btcbot.engine.simulate:
    on_bar(bars, lots, ctx) -> list of ("buy", usd_amount) | ("sell", lot_id, reason)
"""


class Strategy:
    name = "placeholder: buy a 3-bar dip, sell after 12 bars"

    def __init__(self, lookback=3, hold=12):
        self.lookback, self.hold = lookback, hold
        self.params = {"lookback": lookback, "hold": hold}
        self.guard_fired = False

    def on_bar(self, bars, lots, ctx):
        if lots:
            return [("sell", lot.lot_id, "time") for lot in lots if lot.bars_held >= self.hold]
        if ctx.entries_allowed and bars[-1].close < bars[-1 - self.lookback].close:
            return [("buy", ctx.cash)]
        return []
