import random
import unittest

from btcbot.data import DAY, Candle
from btcbot.engine import simulate
from btcbot.strategy import Strategy
from tests.helpers import START, series


class Recorder:
    """Wraps a strategy and records (max open_time seen, orders) at each decision."""

    def __init__(self, inner):
        self.inner, self.log = inner, []

    def on_bar(self, bars, lots, ctx):
        seen = max(b.open_time for b in bars[:])
        orders = self.inner.on_bar(bars, lots, ctx)
        self.log.append((ctx.bar_index, seen, bars[-1].close, tuple(orders)))
        return orders


class TestNoLookahead(unittest.TestCase):
    def test_strategy_sees_only_past_bars(self):
        bars = series(576)
        rec = Recorder(Strategy())
        r = simulate(bars, START, START + DAY, rec)
        self.assertGreater(len(r.trades), 0)
        times = [b.open_time for b in bars]
        for bar_index, seen, _, _ in rec.log:
            fill_time = times[288 + bar_index + 1]  # orders fill at the next bar's open
            self.assertLess(seen, fill_time)

    def test_history_view_blocks_future_index(self):
        class Peek:
            def on_bar(self, bars, lots, ctx):
                with self.assertRaises(IndexError):
                    bars[len(bars)]
                return []

        peek = Peek()
        peek.assertRaises = self.assertRaises
        simulate(series(576), START, START + DAY, peek)

    def test_future_garbage_does_not_change_past_decisions(self):
        bars = series(576)
        a = Recorder(Strategy())
        simulate(bars, START, START + DAY, a)
        rng = random.Random(7)
        for k in (300, 400, 500):
            garbage = bars[:k + 1] + [Candle(b.open_time, *(rng.uniform(1, 1e6) for _ in range(4)), 1.0)
                                      for b in bars[k + 1:]]
            b = Recorder(Strategy())
            simulate(garbage, START, START + DAY, b)
            upto = [x for x in a.log if 288 + x[0] <= k]
            self.assertEqual(upto, b.log[:len(upto)])


if __name__ == "__main__":
    unittest.main()
