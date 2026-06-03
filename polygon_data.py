"""
polygon_data.py — historical daily top-gainer rankings via Polygon.io.

Free tier: 5 calls/minute, EOD historical data. One "grouped daily" call returns
every US ticker's OHLC for a date, so one call == one trading day's universe.

Get a free key: https://polygon.io  (no credit card)
"""

from __future__ import annotations

import time
import requests

BASE = "https://api.polygon.io"


def grouped_daily(api_key: str, date: str) -> dict[str, float]:
    """Return {ticker: close} for every US stock on `date` (YYYY-MM-DD).
    Empty dict = non-trading day (weekend/holiday) or no data."""
    url = f"{BASE}/v2/aggs/grouped/locale/us/market/stocks/{date}"
    r = requests.get(url, params={"adjusted": "true", "apiKey": api_key}, timeout=25)
    if r.status_code == 429:
        raise RuntimeError("Polygon rate limit (5/min on free tier) — slow down.")
    r.raise_for_status()
    out: dict[str, float] = {}
    for row in (r.json().get("results") or []):
        t, c = row.get("T"), row.get("c")
        if t and c:
            out[t] = float(c)
    return out


def fetch_range(api_key: str, dates: list[str], pace_seconds: float = 12.5,
                on_progress=None) -> dict[str, dict[str, float]]:
    """Fetch grouped daily for each date, pacing to respect the free 5/min limit.
    Returns {date: {ticker: close}} (only trading days with data)."""
    closes: dict[str, dict[str, float]] = {}
    for i, d in enumerate(dates):
        try:
            g = grouped_daily(api_key, d)
        except RuntimeError:
            time.sleep(pace_seconds * 2)   # backoff on rate limit, retry once
            g = grouped_daily(api_key, d)
        if g:
            closes[d] = g
        if on_progress:
            on_progress(i + 1, len(dates), d, len(g))
        if i < len(dates) - 1:
            time.sleep(pace_seconds)
    return closes


def compute_rankings(closes: dict[str, dict[str, float]], top_n: int = 10) -> tuple[list[str], dict]:
    """From {date: {ticker: close}} compute each day's top-N gainers (close-to-close %),
    plus persistence (consecutive days in top-N) and whether each stayed the next day.
    Returns (ranked_dates, {date: [ {ticker, pct, close, days_in_top, stayed_next} ]})."""
    trading = sorted(closes.keys())
    rankings: dict[str, list[dict]] = {}
    for j in range(1, len(trading)):
        prev, cur = trading[j - 1], trading[j]
        cp, cc = closes[prev], closes[cur]
        changes = []
        for t, c in cc.items():
            p = cp.get(t)
            if p and p > 0:
                changes.append((t, (c - p) / p * 100.0, c))
        changes.sort(key=lambda x: x[1], reverse=True)
        rankings[cur] = [{"ticker": t, "pct": pct, "close": c} for t, pct, c in changes[:top_n]]

    ranked_dates = sorted(rankings.keys())
    topsets = {d: {e["ticker"] for e in rankings[d]} for d in ranked_dates}
    for idx, d in enumerate(ranked_dates):
        for e in rankings[d]:
            run, k = 1, idx - 1
            while k >= 0 and e["ticker"] in topsets[ranked_dates[k]]:
                run += 1
                k -= 1
            e["days_in_top"] = run
            e["stayed_next"] = (e["ticker"] in topsets[ranked_dates[idx + 1]]
                                if idx + 1 < len(ranked_dates) else None)
    return ranked_dates, rankings
