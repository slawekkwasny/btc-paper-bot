"""Candle feeds (Coinbase, Kraken, Binance), normalisation and validation.

Everything is UTC unix seconds. A bar is identified by its open time; it is closed once open_time + BAR <= now.
"""
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections import namedtuple

Candle = namedtuple("Candle", "open_time open high low close volume")

BAR = 300  # 5-minute candles
DAY = 86400
WARMUP = DAY  # history fetched before the window for indicators; never traded
WINDOW_BARS = DAY // BAR  # 288
MAX_GAP_SHARE = 0.02

USER_AGENT = "btc-paper-bot/0.1 (paper trading take-home)"
TIMEOUT = 10
RETRIES = 3
MIN_INTERVAL = 0.25

COINBASE_URL = ("https://api.coinbase.com/api/v3/brokerage/market/products/BTC-USD/candles"
                "?start={start}&end={end}&granularity=FIVE_MINUTE&limit=350")
COINBASE_PAGE = 300  # bars per request (the API allows 350)
KRAKEN_URL = "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=5&since={since}"
BINANCE_HOSTS = ("https://api.binance.com", "https://data-api.binance.vision")
BINANCE_PATH = "/api/v3/klines?symbol=BTCUSDT&interval=5m&startTime={start}&endTime={end}&limit=1000"


class DataError(Exception):
    """The feed returned nothing usable for the requested window."""


def window_bounds(now):
    """The 24 h window ending at the open time of the still-running bar."""
    end = int(now) - int(now) % BAR
    return end - DAY, end


_last_call = [0.0]
SYSTEM_CA = "/etc/ssl/cert.pem"  # macOS system bundle


def ssl_context():
    """Verified TLS. python.org builds on macOS ship without CA certs until "Install Certificates" is run;
    fall back to the system bundle in that case instead of failing (verification stays on)."""
    ctx = ssl.create_default_context()
    if not ctx.cert_store_stats()["x509_ca"] and os.path.exists(SYSTEM_CA):
        ctx.load_verify_locations(SYSTEM_CA)
    return ctx


_ctx = []


def get_json(url):
    """GET a JSON document with a User-Agent, timeout, retries with backoff and >= 0.25 s between calls."""
    err = None
    for attempt in range(RETRIES):
        wait = _last_call[0] + MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            if not _ctx:
                _ctx.append(ssl_context())
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ctx[0]) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            err = e
            if e.code in (400, 403, 404, 451):  # not transient: don't retry
                break
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            err = e
        if attempt < RETRIES - 1:
            time.sleep(0.5 * 2 ** attempt)
    raise DataError(f"{url.split('?')[0]}: {err}")


# --- parsers: API payload -> list[Candle] (unsorted, may contain the open bar) ---

def parse_coinbase(payload):
    return [Candle(int(c["start"]), float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]),
                   float(c["volume"])) for c in payload["candles"]]


def parse_kraken(payload):
    if payload.get("error"):
        raise DataError(f"kraken: {payload['error']}")
    rows = next(v for k, v in payload["result"].items() if k != "last")
    return [Candle(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[6])) for r in rows]


def parse_binance(payload):
    return [Candle(int(r[0]) // 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]))
            for r in payload]


# --- fetchers: [start, end) -> list[Candle] ---

def fetch_coinbase(start, end):
    out = []
    for t in range(start, end, COINBASE_PAGE * BAR):
        t_end = min(t + COINBASE_PAGE * BAR, end) - BAR  # Coinbase's end is inclusive
        out += parse_coinbase(get_json(COINBASE_URL.format(start=t, end=t_end)))
    return out


def fetch_kraken(start, end):
    # Kraken only serves the latest 720 bars (60 h); `since` cannot reach further back.
    rows = parse_kraken(get_json(KRAKEN_URL.format(since=start - BAR)))
    if rows and min(c.open_time for c in rows) > start:
        raise DataError("kraken only serves the latest 720 bars (60 h); this window starts earlier")
    return rows


def fetch_binance(start, end):
    err = None
    for host in BINANCE_HOSTS:
        try:
            out, t = [], start
            while t < end:
                page = parse_binance(get_json(host + BINANCE_PATH.format(start=t * 1000, end=(end - 1) * 1000)))
                if not page:
                    break
                out += page
                t = page[-1].open_time + BAR
            return out
        except DataError as e:  # api.binance.com returns 451 from US IPs: try the mirror
            err = e
    raise err


FETCHERS = {"coinbase": fetch_coinbase, "kraken": fetch_kraken, "binance": fetch_binance}


def normalise(candles, end):
    """Sort ascending, dedupe on open time, drop the still-open bar and anything after it."""
    by_time = {c.open_time: c for c in candles if c.open_time < end}
    return [by_time[t] for t in sorted(by_time)]


def fill_gaps(candles):
    """Forward-fill missing 5-minute slots with flat zero-volume bars. Returns (bars, filled_open_times)."""
    out, filled = [], []
    for c in candles:
        while out and c.open_time - out[-1].open_time > BAR:
            p = out[-1].close
            out.append(Candle(out[-1].open_time + BAR, p, p, p, p, 0.0))
            filled.append(out[-1].open_time)
        out.append(c)
    return out, filled


def validate(candles, start, end, now):
    """Check the window is complete and closed; forward-fill small gaps. Returns (bars, meta)."""
    if not candles:
        raise DataError("no candles returned")
    if candles[-1].open_time != end - BAR:
        raise DataError(f"last bar opens at {candles[-1].open_time}, expected {end - BAR}: feed is behind")
    if candles[-1].open_time + BAR > now:
        raise DataError("last bar is not closed yet")
    if candles[0].open_time > start:
        raise DataError(f"feed starts at {candles[0].open_time}, after the window start {start}")
    present = sum(1 for c in candles if start <= c.open_time < end)
    missing = WINDOW_BARS - present
    if missing > MAX_GAP_SHARE * WINDOW_BARS:
        raise DataError(f"{missing} of {WINDOW_BARS} bars missing in the window (max {MAX_GAP_SHARE:.0%})")
    bars, filled = fill_gaps(candles)
    window_filled = [t for t in filled if t >= start]
    return bars, {"bars_in_window": WINDOW_BARS, "gaps_filled": len(window_filled),
                  "warmup_bars": sum(1 for b in bars if b.open_time < start)}


def fetch_candles(start, end, source="auto", now=None, log=print):
    """Fetch [start - WARMUP, end) from one source, or from coinbase -> kraken -> binance with source="auto"."""
    now = time.time() if now is None else now
    names = list(FETCHERS) if source == "auto" else [source]
    errors = []
    for name in names:
        try:
            raw = [c for c in normalise(FETCHERS[name](start - WARMUP, end), end) if c.open_time >= start - WARMUP]
            bars, meta = validate(raw, start, end, now)
        except (DataError, KeyError, IndexError, TypeError, ValueError, StopIteration) as e:
            errors.append(f"{name}: {e}")
            log(f"data: {name} failed: {e}")
            continue
        if meta["gaps_filled"]:
            print(f"warning: {meta['gaps_filled']} missing bars forward-filled", file=sys.stderr)
        meta["source"] = name
        if name == "binance":
            meta["note"] = "Binance quotes BTC/USDT, not BTC/USD"
        return bars, meta
    raise DataError("all sources failed: " + "; ".join(errors))
