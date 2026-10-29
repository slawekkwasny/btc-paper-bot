import unittest

from btcbot.data import DAY
from btcbot.engine import simulate
from btcbot.strategy import Strategy
from tests.helpers import START, flat, series


class TestShippedStrategy(unittest.TestCase):
    def test_guard_reaches_five_trades_on_a_dead_market(self):
        s = Strategy()
        r = simulate(flat(576), START, START + DAY, s)
        self.assertTrue(r.guard_fired)
        self.assertEqual(len(r.trades), 5)
        self.assertTrue(all(t.buy_time >= START + 265 * 300 for t in r.trades))
        self.assertTrue(all(t.qty_btc * t.buy_price < 0.051 * 10_000 for t in r.trades))  # small guard tranches

    def test_guard_off_means_no_trades_on_a_dead_market(self):
        r = simulate(flat(576), START, START + DAY, Strategy(guard=False))
        self.assertEqual(r.trades, [])
        self.assertFalse(r.guard_fired)

    def test_tranches_and_targets_on_a_wiggly_market(self):
        r = simulate(series(576), START, START + DAY, Strategy())
        self.assertGreaterEqual(len(r.trades), 5)
        for t in r.trades:
            if t.exit_reason == "target":
                self.assertGreaterEqual(t.sell_price, t.buy_price * 1.0051 * 0.999)

    def test_deterministic(self):
        a = simulate(series(576), START, START + DAY, Strategy())
        b = simulate(series(576), START, START + DAY, Strategy())
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
