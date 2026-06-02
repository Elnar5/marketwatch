"""
news_sources.py
-----------------
Faza 1 — Xəbər toplama (ingestion).

Goal: BROAD coverage so you don't miss anything. Everything here is free and
needs no API key. Two layers:

  1. GENERAL_FEEDS  -> broad market/finance headlines (CNBC, MarketWatch, Yahoo, ...)
  2. ticker_feeds() -> per-ticker feeds, including a Google News SEARCH feed that
                       itself aggregates THOUSANDS of sources for that ticker.

To add more sources: just add an entry to GENERAL_FEEDS, or add another URL
inside ticker_feeds(). That's the whole job.
"""

from __future__ import annotations

import concurrent.futures
from urllib.parse import quote_plus

import feedparser
from dateutil import parser as dateparser


# ---------------------------------------------------------------------------
# 1) GENERAL market / finance feeds (broad coverage, no ticker filter)
# ---------------------------------------------------------------------------
GENERAL_FEEDS: dict[str, str] = {
    "CNBC Top News":        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "CNBC Markets":         "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "CNBC Finance":         "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "CNBC Technology":      "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
    "MarketWatch Top":      "http://feeds.marketwatch.com/marketwatch/topstories/",
    "MarketWatch Pulse":    "http://feeds.marketwatch.com/marketwatch/marketpulse/",
    "MarketWatch RealTime": "http://feeds.marketwatch.com/marketwatch/realtimeheadlines/",
    "Yahoo Finance":        "https://finance.yahoo.com/news/rssindex",
    "Investing.com":        "https://www.investing.com/rss/news.rss",
    "Investing Stock News": "https://www.investing.com/rss/news_25.rss",
    "Seeking Alpha":        "https://seekingalpha.com/market_currents.xml",
    "NASDAQ Markets":       "https://www.nasdaq.com/feed/rssoutbound?category=Markets",
    "Google News: markets": "https://news.google.com/rss/search?q=stock%20market%20when%3A1d&hl=en-US&gl=US&ceid=US:en",
}


def ticker_feeds(ticker: str) -> dict[str, str]:
    """Per-ticker feeds. The Google News one is the 'don't miss anything' net:
    it pulls that ticker's news from thousands of outlets."""
    t = ticker.strip().upper()
    q_news = quote_plus(f"{t} stock when:2d")
    return {
        f"Yahoo [{t}]":        f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={t}&region=US&lang=en-US",
        f"NASDAQ [{t}]":       f"https://www.nasdaq.com/feed/rssoutbound?symbol={t}",
        f"Seeking Alpha [{t}]": f"https://seekingalpha.com/api/sa/combined/{t}.xml",
        f"Google News [{t}]":  f"https://news.google.com/rss/search?q={q_news}&hl=en-US&gl=US&ceid=US:en",
    }


# ---------------------------------------------------------------------------
# Fetching / parsing helpers
# ---------------------------------------------------------------------------
def _parse_date(entry):
    """Return a timezone-aware-ish sortable datetime, or None."""
    for key in ("published", "updated", "pubDate"):
        val = entry.get(key)
        if val:
            try:
                return dateparser.parse(val)
            except (ValueError, TypeError, OverflowError):
                pass
    # feedparser sometimes gives a parsed struct_time
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                import time
                from datetime import datetime, timezone
                return datetime.fromtimestamp(time.mktime(st), tz=timezone.utc)
            except Exception:
                pass
    return None


def _clean_summary(entry) -> str:
    raw = entry.get("summary", "") or ""
    # feedparser leaves HTML in summaries; strip tags cheaply
    import re
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:400]


def fetch_feed(name: str, url: str, max_items: int = 25) -> list[dict]:
    """Fetch a single RSS feed. Never raises — returns [] on any problem."""
    out: list[dict] = []
    try:
        parsed = feedparser.parse(url)
        for entry in parsed.entries[:max_items]:
            out.append({
                "title":   (entry.get("title") or "").strip(),
                "link":    entry.get("link") or "",
                "source":  name,
                "summary": _clean_summary(entry),
                "dt":      _parse_date(entry),
            })
    except Exception as exc:  # noqa: BLE001 - we want this to be bullet-proof
        print(f"[warn] feed failed: {name} -> {exc}")
    return out


def fetch_all(tickers: list[str] | None = None, max_per_feed: int = 25) -> list[dict]:
    """Fetch every general feed + per-ticker feeds, in parallel.
    Returns a deduped list sorted newest-first."""
    feeds: dict[str, str] = dict(GENERAL_FEEDS)
    for tk in (tickers or []):
        if tk.strip():
            feeds.update(ticker_feeds(tk))

    items: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(fetch_feed, name, url, max_per_feed)
                   for name, url in feeds.items()]
        for fut in concurrent.futures.as_completed(futures):
            items.extend(fut.result())

    # de-duplicate by (normalized title) keeping the first seen
    seen: set[str] = set()
    deduped: list[dict] = []
    for it in items:
        key = it["title"].lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(it)

    # sort newest first; items without a date go to the bottom
    from datetime import datetime, timezone
    def sort_key(it):
        dt = it["dt"]
        if dt is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    deduped.sort(key=sort_key, reverse=True)
    return deduped
