"""Synthetic candle series for tests."""
import math

from btcbot.data import BAR, Candle

START = 1_790_000_000 - 1_790_000_000 % BAR


def series(n, start=START - 288 * BAR, base=50_000.0, seed=1):
    """n bars of a deterministic wiggly price path starting at `start`."""
    out, p = [], base
    for i in range(n):
        o = p
        p = base * (1 + 0.01 * math.sin(i / 7 + seed) + 0.004 * math.sin(i / 2.3 * seed))
        out.append(Candle(start + i * BAR, o, max(o, p) * 1.0005, min(o, p) * 0.9995, p, 1.0))
    return out


def flat(n, price=50_000.0, start=START - 288 * BAR):
    return [Candle(start + i * BAR, price, price, price, price, 1.0) for i in range(n)]
