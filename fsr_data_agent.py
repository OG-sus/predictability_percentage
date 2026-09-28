"""fsr_data_agent.py

Lightweight agent that periodically fetches time-series from public sources
and evaluates them with the project's FSR implementation (`fsr.calculate_predictability`).

Usage:
    python fsr_data_agent.py --interval 3600 --threshold 70

The script appends interesting findings to `fsr_agent_results.jsonl`.
"""
import argparse
import json
import logging
import time
from datetime import datetime
from typing import List, Tuple

import requests
import numpy as np

from fsr import calculate_predictability

LOG = logging.getLogger("fsr_data_agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class DataSource:
    """Simple interface for time-series data sources."""

    def fetch(self) -> Tuple[str, List[float]]:
        """Return (label, list_of_values) - list is newest-first or oldest-first consistently per source.
        Must return numeric values (floats)."""
        raise NotImplementedError()


class CoinGeckoSource(DataSource):
    """Fetch daily prices for a coin from CoinGecko (no API key)."""

    def __init__(self, coin_id: str = "bitcoin", days: int = 90):
        self.coin_id = coin_id
        self.days = days

    def fetch(self):
        url = (
            f"https://api.coingecko.com/api/v3/coins/{self.coin_id}/market_chart"
            f"?vs_currency=usd&days={self.days}&interval=daily"
        )
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        prices = data.get("prices", [])
        # prices are [ [ts_ms, price], ... ]
        series = [float(p[1]) for p in prices]
        label = f"coingecko:{self.coin_id}"
        return label, series


class StaticCSVSource(DataSource):
    """Load a CSV time series from a public raw URL (expects single column of numeric values).
    This is a forgiving loader for quick experimentation.
    """

    def __init__(self, url: str, label: str = None):
        self.url = url
        self.label = label or url

    def fetch(self):
        r = requests.get(self.url, timeout=20)
        r.raise_for_status()
        text = r.text.strip().splitlines()
        vals = []
        for line in text:
            line = line.strip()
            if not line:
                continue
            # try to parse last comma-separated column
            parts = line.split(",")
            try:
                v = float(parts[-1])
            except Exception:
                continue
            vals.append(v)
        return self.label, vals


def is_interesting(prev_score: float, score: float, threshold: float, min_delta: float) -> bool:
    """Heuristic: interesting if above threshold or changed by min_delta percent."""
    if score >= threshold:
        return True
    if prev_score is None:
        return False
    # percent change
    if prev_score == 0:
        return abs(score - prev_score) >= min_delta
    pct = abs((score - prev_score) / prev_score) * 100.0
    return pct >= min_delta


def evaluate_source(source: DataSource, k: float = 1.0) -> dict:
    label, series = source.fetch()
    # Ensure we have numeric values and take last N if long
    if len(series) < 3:
        raise ValueError("Series too short")
    # Use raw list as-is; fsr expects numeric list
    score = float(calculate_predictability(series, k))
    return {"label": label, "n": len(series), "score": score}


def main(interval: int, threshold: float, min_delta: float, k: float):
    # configure sources - start small and make this configurable later
    sources: List[DataSource] = [
        CoinGeckoSource("bitcoin", days=90),
        CoinGeckoSource("ethereum", days=90),
        # Example CSV (user can add raw CSV URLs to monitor by editing this list)
        # StaticCSVSource("https://raw.githubusercontent.com/datasets/covid-19/main/data/time-series-19-covid-combined.csv", label="covid_combined")
    ]

    state = {}  # label -> last score
    out_path = "fsr_agent_results.jsonl"
    LOG.info("Starting FSR data agent: interval=%ss threshold=%s min_delta=%s k=%s", interval, threshold, min_delta, k)

    while True:
        for src in sources:
            try:
                result = evaluate_source(src, k=k)
            except Exception as e:
                LOG.warning("Source failed: %s -> %s", getattr(src, "coin_id", getattr(src, "url", "?")), e)
                continue

            label = result["label"]
            score = result["score"]
            prev = state.get(label)
            ts = datetime.utcnow().isoformat() + "Z"
            if is_interesting(prev, score, threshold, min_delta):
                out = {"ts": ts, "label": label, "score": score, "n": result["n"]}
                LOG.info("Interesting: %s -> score=%.3f", label, score)
                with open(out_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(out) + "\n")
            else:
                LOG.debug("Checked: %s -> score=%.3f", label, score)
            state[label] = score

        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FSR Data Finder Agent")
    parser.add_argument("--interval", type=int, default=3600, help="seconds between fetch cycles")
    parser.add_argument("--threshold", type=float, default=70.0, help="FSR threshold to flag as interesting")
    parser.add_argument("--min-delta", type=float, default=10.0, help="minimum percent change in FSR to flag")
    parser.add_argument("--k", type=float, default=1.0, help="K factor passed to calculate_predictability")
    args = parser.parse_args()
    try:
        main(args.interval, args.threshold, args.min_delta, args.k)
    except KeyboardInterrupt:
        LOG.info("Agent stopped by user")
