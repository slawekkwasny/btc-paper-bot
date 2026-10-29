import unittest

from btcbot.data import BAR, DAY
from btcbot.engine import simulate
from tests.helpers import START, flat, series


class Scripted:
    """Buys/sells on given window bar indices."""

    def __init__(self, buys=(), sells=(), usd=1_000.0):
        self.buys, self.sells, self.usd = set(buys), set(sells), usd

    def on_bar(self, bars, lots, ctx):
        orders = [("sell", lot.lot_id, "signal") for lot in lots if ctx.bar_index in self.sells]
        if ctx.bar_index in self.buys:
            orders.append(("buy", self.usd))
        return orders


class TestFees(unittest.TestCase):
    def test_fee_math(self):
        r = simulate(flat(576), START, START + DAY, Scripted(buys=[0], sells=[1]))
        t = r.trades[0]
        self.assertAlmostEqual(t.qty_btc, 0.01998, places=10)
        self.assertAlmostEqual(t.buy_fee, 1.0)
        self.assertAlmostEqual(t.sell_fee, 0.999)
        self.assertAlmostEqual(r.final_cash, 9_998.001, places=6)
        self.assertAlmostEqual(t.pnl_usd, -1.999, places=6)
        self.assertEqual(t.exit_reason, "signal")

    def test_cash_after_buy(self):
        seen = []

        class Probe(Scripted):
            def on_bar(self, bars, lots, ctx):
                seen.append(ctx.cash)
                return super().on_bar(bars, lots, ctx)

        simulate(flat(576), START, START + DAY, Probe(buys=[0]))
        self.assertAlmostEqual(seen[1], 9_000.0)

    def test_buy_and_hold_net_of_fees(self):
        r = simulate(flat(576), START, START + DAY, Scripted())
        self.assertAlmostEqual(r.bh_pnl_usd, 10_000 * 0.999 * 0.999 - 10_000)
        self.assertAlmostEqual(r.price_change_pct, 0.0)


class TestRules(unittest.TestCase):
    def test_forced_flat(self):
        r = simulate(series(576), START, START + DAY, Scripted(buys=[10]))
        self.assertEqual(len(r.trades), 1)
        self.assertEqual(r.trades[0].exit_reason, "eod")
        self.assertEqual(r.trades[0].sell_time, START + DAY)  # close of the last window bar

    def test_no_entry_zone(self):
        # window bars 0..287; bar 281 has 6 bars left -> refused; bar 280 has 7 -> allowed
        r = simulate(flat(576), START, START + DAY, Scripted(buys=[281, 284]))
        self.assertEqual(r.trades, [])
        self.assertEqual(r.meta["refused_orders"], 2)
        r = simulate(flat(576), START, START + DAY, Scripted(buys=[280]))
        self.assertEqual(len(r.trades), 1)

    def test_refuses_overspend_and_unknown_lot(self):
        class Bad:
            def on_bar(self, bars, lots, ctx):
                return [("buy", 20_000.0), ("sell", 99, "x")] if ctx.bar_index == 0 else []

        r = simulate(flat(576), START, START + DAY, Bad())
        self.assertEqual(r.trades, [])
        self.assertEqual(r.meta["refused_orders"], 2)
        self.assertAlmostEqual(r.final_cash, 10_000.0)

    def test_warmup_never_traded(self):
        r = simulate(series(576), START, START + DAY, Scripted(buys=range(288)))
        self.assertTrue(all(t.buy_time >= START for t in r.trades))
        self.assertEqual(r.meta["window_bars"], 288)


if __name__ == "__main__":
    unittest.main()
