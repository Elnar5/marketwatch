"""
gainers.py — fetch the day's top gainers across the whole US market.

Uses Yahoo Finance's free predefined screener (no API key). Broad universe.
If Yahoo blocks the cloud server's IP, fetch_gainers returns [] and the UI
will say so — then we can switch to a key-based source (e.g. FMP).
"""

from __future__ import annotations

import requests

_URL = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json",
}


def fetch_gainers(count: int = 50) -> list[dict]:
    """Return the day's top gainers: [{ticker, name, pct, price, volume}], newest %."""
    try:
        r = requests.get(_URL, params={"count": count, "scrIds": "day_gainers"},
                         headers=_HEADERS, timeout=8)
        r.raise_for_status()
        quotes = r.json()["finance"]["result"][0]["quotes"]
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] gainers fetch failed: {exc}")
        return []

    out: list[dict] = []
    for q in quotes:
        out.append({
            "ticker": q.get("symbol", ""),
            "name":   q.get("shortName") or q.get("longName") or q.get("symbol", ""),
            "pct":    float(q.get("regularMarketChangePercent", 0) or 0),
            "price":  float(q.get("regularMarketPrice", 0) or 0),
            "volume": int(q.get("regularMarketVolume", 0) or 0),
        })
    out.sort(key=lambda x: x["pct"], reverse=True)
    return out
