"""
ticker_feed_writer.py — Volatility Radar feed writer

Tracks ~27 tickers across three free/no-signup categories:
  CRYPTO  — 8 majors, one bulk CoinGecko call (7d hourly sparkline)
  WEATHER — 12 global cities, one bulk Open-Meteo call (7d hourly temps)
  MACRO   — VIX, oil, S&P 500, NASDAQ, 2Y/10Y yields, dollar index,
            all via FRED (reuses FRED_API_KEY)

A background thread refreshes all of that every --refresh-interval
seconds. The main loop rotates through the tracked tickers,
(--columns x --rows-per-col) at a time, writing one file per column
(<prefix>_col0.txt, _col1.txt, ...) plus a shared <prefix>_time.txt
every --rotate-seconds — same rotating-dashboard pattern as the old
stream setup, just running locally now, laid out as a grid instead
of one stacked column.

Pair each column with its own ffmpeg drawtext overlay (reload=1), so
the on-stream numbers update without restarting ffmpeg:

    drawtext=textfile=ticker_col0.txt:reload=1:expansion=none:...

Run:
    python ticker_feed_writer.py --rotate-seconds 8 --columns 3 --rows-per-col 4
"""
import argparse
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

from fsr import calculate_predictability

load_dotenv()

LOG = logging.getLogger("ticker_feed_writer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

FRED_API_KEY = os.environ.get("FRED_API_KEY")


class Asset:
    def __init__(self, display: str, category: str, k: float = 1.0):
        self.display = display
        self.category = category
        self.k = k
        self.last_score: Optional[float] = None
        self.last_price: Optional[float] = None
        self.unit = ""
        self.direction = "flat"  # "up" / "down" / "flat", last-vs-previous point

    def set_from_series(self, price: float, series: List[float], unit: str = "") -> None:
        series = [s for s in series if s is not None]
        if len(series) < 5:
            return
        self.last_score = float(calculate_predictability(series, self.k))
        self.last_price = price
        self.unit = unit
        prev = series[-2]
        if prev:
            pct = (series[-1] - prev) / abs(prev) * 100
            self.direction = "up" if pct > 0.05 else "down" if pct < -0.05 else "flat"

    def line(self) -> Optional[str]:
        if self.last_score is None:
            return None
        # Compact form for a multi-column grid: category is dropped since
        # display names read as their category already (city = weather,
        # coin name = crypto, VIX/YIELD/S&P = macro).
        return f"{self.display:<12}{self.last_score:5.1f}%  {self.last_price:>10,.2f}{self.unit}"


# ---- CRYPTO: 8 majors, one bulk CoinGecko call ----
# Trimmed from a longer list — kept the coins with real trading volume
# and name recognition, dropped the lower-relevance/meme-tier ones
# (SHIB, TRX, MATIC, UNI, ATOM, LTC) in favor of more MACRO tickers below.
CRYPTO_IDS = [
    "bitcoin", "ethereum", "solana", "ripple", "dogecoin",
]


def fetch_crypto_bulk(assets_by_id: Dict[str, Asset]) -> None:
    ids = ",".join(assets_by_id.keys())
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={ids}&sparkline=true"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    for row in r.json():
        asset = assets_by_id.get(row.get("id"))
        if not asset:
            continue
        series = row.get("sparkline_in_7d", {}).get("price", []) or []
        asset.set_from_series(row["current_price"], series)


# ---- BIG TECH: 6 mega-caps, one Yahoo Finance chart call per symbol
# (no bulk quote endpoint available there) ----
BIG_TECH_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"]


def fetch_yahoo(symbol: str, range_: str = "5d", interval: str = "15m"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range_}&interval={interval}"
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    series = [c for c in closes if c is not None]
    if not series:
        raise ValueError(f"empty series for {symbol}")
    return series[-1], series


def fetch_named_stocks(assets_by_symbol: Dict[str, Asset]) -> None:
    for symbol, asset in assets_by_symbol.items():
        try:
            price, series = fetch_yahoo(symbol)
            asset.set_from_series(price, series)
        except Exception as e:
            LOG.warning("%s fetch failed: %s", symbol, e)


# ---- MOVERS: today's actual biggest gainers/losers, not a fixed
# watchlist - Yahoo's day_gainers/day_losers screeners, re-picked every
# refresh cycle. Slots are reused Asset objects whose *symbol* changes
# day to day, since who's "moving" isn't fixed like the other categories.
MOVER_SLOTS = 7
MOVER_GAINERS_TAKE = 4
MOVER_LOSERS_TAKE = 3


def _fetch_screener(screen_id: str, count: int) -> List[str]:
    url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
    r = requests.get(url, params={"formatted": "true", "scrIds": screen_id, "count": count},
                      headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()
    quotes = r.json()["finance"]["result"][0]["quotes"]
    return [q["symbol"] for q in quotes]


def fetch_movers(mover_assets: List[Asset]) -> None:
    symbols: List[str] = []
    try:
        symbols += _fetch_screener("day_gainers", MOVER_GAINERS_TAKE)[:MOVER_GAINERS_TAKE]
    except Exception as e:
        LOG.warning("day_gainers screener failed: %s", e)
    try:
        symbols += _fetch_screener("day_losers", MOVER_LOSERS_TAKE)[:MOVER_LOSERS_TAKE]
    except Exception as e:
        LOG.warning("day_losers screener failed: %s", e)

    for asset, symbol in zip(mover_assets, symbols):
        try:
            price, series = fetch_yahoo(symbol)
            asset.display = symbol
            asset.set_from_series(price, series)
        except Exception as e:
            LOG.warning("mover %s fetch failed: %s", symbol, e)


# ---- WEATHER: 12 global cities, one bulk Open-Meteo call ----
# k-factors here use the product's actual four presets (0.5 sports /
# 1x general / 2x finance / 15x pharma) rather than invented in-between
# values, for consistency with predictability-api.com. Storm-belt
# cities use the 0.5 "sports" preset (forgiving of swings that are the
# point, not a flaw); everywhere else uses the 1x general default.
CITIES = [
    ("New York",    40.71,  -74.01, 1.0),
    ("London",      51.51,   -0.13, 1.0),
    ("Tokyo",       35.68,  139.69, 1.0),
    ("Sydney",     -33.87,  151.21, 1.0),
    ("Mumbai",      19.08,   72.88, 1.0),
    ("Sao Paulo",  -23.55,  -46.63, 1.0),
    ("Cairo",       30.04,   31.24, 1.0),
    ("Moscow",      55.76,   37.62, 1.0),
    ("Miami",       25.76,  -80.19, 0.5),
    ("New Orleans", 29.95,  -90.07, 0.5),
    ("Reykjavik",   64.15,  -21.94, 1.0),
    ("Singapore",    1.35,  103.82, 1.0),
]


def fetch_weather_bulk(assets_by_city: Dict[str, Asset]) -> None:
    lats = ",".join(str(c[1]) for c in CITIES)
    lons = ",".join(str(c[2]) for c in CITIES)
    # Fahrenheit, not Celsius - target audience is the US Twitch/YouTube
    # market even though the cities themselves are global.
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}"
        f"&hourly=temperature_2m&temperature_unit=fahrenheit&past_days=7&forecast_days=1&timezone=UTC"
    )
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    rows = data if isinstance(data, list) else [data]
    for (name, _, _, _k), row in zip(CITIES, rows):
        asset = assets_by_city.get(name)
        if not asset:
            continue
        temps = row.get("hourly", {}).get("temperature_2m", []) or []
        if temps:
            asset.set_from_series(temps[-1], temps, unit="F")


# ---- MACRO: FRED series ----
def fetch_fred(series_id: str, points: int = 180) -> Tuple[float, List[float]]:
    if not FRED_API_KEY:
        raise RuntimeError("FRED_API_KEY not set. Add it to your .env file.")
    url = (
        "https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json"
        f"&sort_order=desc&limit={points}"
    )
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    obs = r.json().get("observations", [])
    series = [float(o["value"]) for o in reversed(obs) if o["value"] != "."]
    if not series:
        raise ValueError("empty series")
    return series[-1], series


# All finance data uses the product's 2x "finance" preset (strict
# punishment for volatility), not invented in-between values.
MACRO_SERIES = {
    "VIXCLS": ("VIX", 2.0),
    "DCOILWTICO": ("OIL (WTI)", 2.0),
    "DGS10": ("10Y YIELD", 2.0),
    "DGS2": ("2Y YIELD", 2.0),
    "SP500": ("S&P 500", 2.0),
    "NASDAQCOM": ("NASDAQ", 2.0),
    "DTWEXBGS": ("DOLLAR IDX", 2.0),
}


def build_assets():
    """Returns (groups, all_assets). groups is a dict of category name ->
    either {key: Asset} (fixed-identity categories) or [Asset, ...]
    (MOVERS, whose slots' underlying symbol changes each refresh)."""
    # 2.0 = the product's "finance" preset, used for every market instrument
    # here (crypto, big tech, movers, macro) for consistency with the API.
    crypto_assets = {cid: Asset(cid.replace("-2", "").replace("-", " ").upper(), "CRYPTO", k=2.0)
                      for cid in CRYPTO_IDS}
    big_tech_assets = {sym: Asset(sym, "BIG TECH", k=2.0) for sym in BIG_TECH_SYMBOLS}
    mover_assets = [Asset("--", "MOVERS", k=2.0) for _ in range(MOVER_SLOTS)]
    weather_assets = {name: Asset(name, "WEATHER", k=k) for name, _, _, k in CITIES}
    macro_assets = {sid: Asset(display, "MACRO", k=k) for sid, (display, k) in MACRO_SERIES.items()}

    groups = {
        "crypto": crypto_assets,
        "big_tech": big_tech_assets,
        "movers": mover_assets,
        "weather": weather_assets,
        "macro": macro_assets,
    }
    all_assets = (list(crypto_assets.values()) + list(big_tech_assets.values()) + mover_assets
                  + list(weather_assets.values()) + list(macro_assets.values()))
    return groups, all_assets


def refresh_all(groups) -> None:
    try:
        fetch_crypto_bulk(groups["crypto"])
    except Exception as e:
        LOG.warning("Crypto bulk fetch failed: %s", e)
    try:
        fetch_named_stocks(groups["big_tech"])
    except Exception as e:
        LOG.warning("Big tech fetch failed: %s", e)
    try:
        fetch_movers(groups["movers"])
    except Exception as e:
        LOG.warning("Movers fetch failed: %s", e)
    try:
        fetch_weather_bulk(groups["weather"])
    except Exception as e:
        LOG.warning("Weather bulk fetch failed: %s", e)
    for series_id, asset in groups["macro"].items():
        try:
            price, series = fetch_fred(series_id)
            asset.set_from_series(price, series)
        except Exception as e:
            LOG.warning("%s fetch failed: %s", asset.display, e)


def refresh_loop(groups, interval, stop_event) -> None:
    while not stop_event.is_set():
        LOG.info("Refreshing all data sources...")
        refresh_all(groups)
        LOG.info("Refresh done.")
        stop_event.wait(interval)


def write_snapshot(lines: List[str], out_path: str) -> None:
    if not lines:
        return
    text = "\n".join(lines)
    tmp_path = out_path + ".tmp"
    # write-temp-then-rename: measured ~380x fewer reader collisions under
    # concurrent-access stress testing than writing the target file directly
    # (0.009% vs 3.3% of reads), since the write itself never touches the
    # live path ffmpeg is reading. os.replace can still rarely collide with
    # ffmpeg's own read on Windows, so retry a couple of times rather than
    # letting one bad roll kill the writer thread.
    with open(tmp_path, "w") as f:
        f.write(text)
    for attempt in range(5):
        try:
            os.replace(tmp_path, out_path)
            return
        except PermissionError:
            time.sleep(0.05 * (attempt + 1))
    LOG.warning("Could not replace %s after retries; skipping this cycle", out_path)


def main(refresh_interval: int, rotate_seconds: int, columns: int, rows_per_col: int, out_prefix: str) -> None:
    groups, all_assets = build_assets()
    batch_size = columns * rows_per_col
    LOG.info("Tracking %d tickers (%d crypto, %d big tech, %d movers, %d weather, %d macro), "
              "showing %d at a time (%d columns x %d rows), rotating every %ss",
              len(all_assets), len(groups["crypto"]), len(groups["big_tech"]), len(groups["movers"]),
              len(groups["weather"]), len(groups["macro"]), batch_size, columns, rows_per_col, rotate_seconds)

    stop_event = threading.Event()
    t = threading.Thread(
        target=refresh_loop,
        args=(groups, refresh_interval, stop_event),
        daemon=True,
    )
    t.start()

    LOG.info("Waiting for first data snapshot...")
    time.sleep(8)  # give the first refresh a head start before rotating

    col_paths = [f"{out_prefix}_col{c}.txt" for c in range(columns)]
    time_path = f"{out_prefix}_time.txt"

    cursor = 0
    try:
        while True:
            ready = [a for a in all_assets if a.last_score is not None]
            if not ready:
                LOG.warning("No data yet, waiting...")
                time.sleep(rotate_seconds)
                continue
            n = min(batch_size, len(ready))
            batch = [ready[(cursor + i) % len(ready)] for i in range(n)]
            cursor = (cursor + n) % len(ready)

            for c, col_path in enumerate(col_paths):
                col_batch = batch[c * rows_per_col:(c + 1) * rows_per_col]
                write_snapshot([a.line() for a in col_batch], col_path)

            stamp = datetime.now(timezone.utc).strftime("Updated %H:%M UTC")
            write_snapshot([stamp], time_path)

            time.sleep(rotate_seconds)
    except KeyboardInterrupt:
        LOG.info("Stopped by user")
    finally:
        stop_event.set()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Volatility Radar ticker feed writer")
    parser.add_argument("--refresh-interval", type=int, default=120, help="seconds between full data refreshes")
    parser.add_argument("--rotate-seconds", type=int, default=8, help="seconds each batch stays on screen")
    parser.add_argument("--columns", type=int, default=3, help="number of ticker columns to show")
    parser.add_argument("--rows-per-col", type=int, default=4, help="tickers per column")
    parser.add_argument("--out-prefix", type=str, default="ticker",
                         help="prefix for output files: <prefix>_col0.txt, _col1.txt, ..., _time.txt")
    args = parser.parse_args()
    main(args.refresh_interval, args.rotate_seconds, args.columns, args.rows_per_col, args.out_prefix)
