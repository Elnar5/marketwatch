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
    idx_in_trading = {d: i for i, d in enumerate(trading)}
    for idx, d in enumerate(ranked_dates):
        for e in rankings[d]:
            run, k = 1, idx - 1
            while k >= 0 and e["ticker"] in topsets[ranked_dates[k]]:
                run += 1
                k -= 1
            e["days_in_top"] = run
            e["stayed_next"] = (e["ticker"] in topsets[ranked_dates[idx + 1]]
                                if idx + 1 < len(ranked_dates) else None)
            # forward returns from this day's close (next up-to-3 trading days)
            base, ti, fwd = e["close"], idx_in_trading[d], []
            for kk in (1, 2, 3):
                if ti + kk < len(trading):
                    fd = trading[ti + kk]
                    fc = closes[fd].get(e["ticker"])
                    if fc:
                        fwd.append((fd, (fc - base) / base * 100.0))
            e["fwd"] = fwd
    return ranked_dates, rankings


def ticker_news(api_key: str, ticker: str, date_str: str,
                window_days: int = 4, limit: int = 20) -> list[str]:
    """Headlines for `ticker` published around `date_str` (YYYY-MM-DD), via Polygon's
    news endpoint. Returns ['[YYYY-MM-DD] title', ...]. Empty if none / not on tier /
    tiny stock with no coverage (which itself usually means a no-news pump)."""
    from datetime import date as _d, timedelta as _td
    d = _d.fromisoformat(date_str)
    lo = (d - _td(days=window_days)).isoformat()
    hi = (d + _td(days=window_days)).isoformat()
    url = f"{BASE}/v2/reference/news"
    params = {"ticker": ticker, "published_utc.gte": lo, "published_utc.lte": hi,
              "order": "desc", "limit": limit, "apiKey": api_key}
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        arts = r.json().get("results") or []
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] ticker_news failed: {exc}")
        return []
    out = []
    for a in arts:
        t = a.get("title")
        if t:
            out.append(f"[{(a.get('published_utc') or '')[:10]}] {t}")
    return out
