import json
import os
import unittest

from btcbot.data import (BAR, DAY, WARMUP, Candle, DataError, fill_gaps, normalise, parse_binance, parse_coinbase,
                         parse_kraken, validate, window_bounds)

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
FIX_END = 1793262000  # the fixtures were captured with this window end


def load(name):
    with open(os.path.join(FIX, name)) as f:
        return json.load(f)


def bars(start, n, skip=()):
    return [Candle(start + i * BAR, 1.0, 1.0, 1.0, 1.0, 1.0) for i in range(n) if i not in skip]


class TestParsers(unittest.TestCase):
    def check(self, candles):
        self.assertTrue(candles)
        for c in candles:
            self.assertEqual(c.open_time % BAR, 0)
            self.assertLessEqual(c.low, min(c.open, c.close))
            self.assertGreaterEqual(c.high, max(c.open, c.close))
            self.assertGreater(c.close, 1000)

    def test_coinbase(self):
        raw = parse_coinbase(load("coinbase.json"))
        self.check(raw)
        self.assertGreater(raw[0].open_time, raw[-1].open_time)  # newest first from the API
        out = normalise(raw, FIX_END)
        self.assertEqual([c.open_time for c in out], sorted({c.open_time for c in out}))
        self.assertEqual(out[-1].open_time, FIX_END - BAR)  # the open bar at FIX_END is dropped

    def test_kraken(self):
        raw = parse_kraken(load("kraken.json"))
        self.check(raw)
        self.assertEqual(raw[-1].open_time, FIX_END)  # last row is the still-open bar
        self.assertEqual(normalise(raw, FIX_END)[-1].open_time, FIX_END - BAR)

    def test_binance(self):
        raw = parse_binance(load("binance.json"))
        self.check(raw)
        self.assertLess(raw[-1].open_time, FIX_END)

    def test_kraken_error_payload(self):
        with self.assertRaises(DataError):
            parse_kraken({"error": ["EGeneral:Invalid arguments"], "result": {}})

    def test_dedupe(self):
        c = bars(0, 3)
        self.assertEqual(normalise(c + c[::-1], 10 * BAR), c)


class TestWindow(unittest.TestCase):
    def test_bounds(self):
        now = 1793262102  # 1 min 42 s into a bar
        start, end = window_bounds(now)
        self.assertEqual(end, 1793262000)
        self.assertEqual(end - start, DAY)
        self.assertEqual((end - start) // BAR, 288)

    def test_bounds_on_boundary(self):
        self.assertEqual(window_bounds(1793262000)[1], 1793262000)


class TestValidate(unittest.TestCase):
    start, end = 1793262000 - DAY, 1793262000

    def test_complete(self):
        out, meta = validate(bars(self.start - WARMUP, 576), self.start, self.end, self.end + 5)
        self.assertEqual(len(out), 576)
        self.assertEqual(meta["bars_in_window"], 288)
        self.assertEqual(meta["gaps_filled"], 0)

    def test_small_gap_forward_filled(self):
        src = bars(self.start - WARMUP, 576, skip={400, 401})
        src[399] = src[399]._replace(close=2.0)
        out, meta = validate(src, self.start, self.end, self.end)
        self.assertEqual(len(out), 576)
        self.assertEqual(meta["gaps_filled"], 2)
        self.assertEqual(out[400].open_time, src[399].open_time + BAR)
        self.assertEqual((out[400].open, out[400].close, out[400].volume), (2.0, 2.0, 0.0))

    def test_too_many_gaps(self):
        with self.assertRaises(DataError):
            validate(bars(self.start - WARMUP, 576, skip=set(range(300, 310))), self.start, self.end, self.end)

    def test_missing_last_bar(self):
        with self.assertRaises(DataError):
            validate(bars(self.start - WARMUP, 575), self.start, self.end, self.end)

    def test_last_bar_not_closed(self):
        with self.assertRaises(DataError):
            validate(bars(self.start - WARMUP, 576), self.start, self.end, self.end - 60)

    def test_fill_gaps_none(self):
        self.assertEqual(fill_gaps(bars(0, 5)), (bars(0, 5), []))


if __name__ == "__main__":
    unittest.main()
