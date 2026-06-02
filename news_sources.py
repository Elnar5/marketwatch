"""
news_sources.py — Faza 1 (ingestion) with per-ticker relevance tagging.

Broad coverage from free RSS (mostly Google News, cloud-reliable), plus each
item is TAGGED with which watchlist ticker(s) it relates to, so the UI can show
only the news that actually affects a given stock.
"""

from __future__ import annotations

import concurrent.futures
import re
import socket
from urllib.parse import quote_plus

import feedparser
from dateutil import parser as dateparser

# Never let a slow/dead feed hang the whole app.
socket.setdefaulttimeout(6)

# Company-name aliases so "Nvidia" matches NVDA, etc. Add your own freely.
TICKER_ALIASES: dict[str, list[str]] = {
    "NVDA": ["nvidia"], "TSLA": ["tesla"], "MU": ["micron"],
    "AVGO": ["broadcom"], "AAPL": ["apple"], "AMD": ["advanced micro"],
    "MSFT": ["microsoft"], "GOOGL": ["alphabet", "google"], "GOOG": ["alphabet", "google"],
    "AMZN": ["amazon"], "META": ["meta platforms", "facebook"], "NFLX": ["netflix"],
    "INTC": ["intel"], "SNDK": ["sandisk"], "VRT": ["vertiv"], "BE": ["bloom energy"],
    "VST": ["vistra"], "CLS": ["celestica"], "CCJ": ["cameco"], "COHR": ["coherent"],
    "BUD": ["ab inbev", "anheuser"], "NKE": ["nike"], "DKNG": ["draftkings"],
}

GENERAL_FEEDS: dict[str, str] = {
    "Google News: Business":  "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en",
    "Google News: Markets":   "https://news.google.com/rss/search?q=stock%20market%20when:1d&hl=en-US&gl=US&ceid=US:en",
    "Google News: Earnings":  "https://news.google.com/rss/search?q=earnings%20OR%20stock%20when:1d&hl=en-US&gl=US&ceid=US:en",
    "CNBC Markets":           "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "CNBC Top News":          "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "MarketWatch Top":        "http://feeds.marketwatch.com/marketwatch/topstories/",
}


def ticker_feeds(ticker: str) -> dict[str, str]:
    t = ticker.strip().upper()
    q_news = quote_plus(f"{t} stock when:2d")
    return {
        f"Google News [{t}]": f"https://news.google.com/rss/search?q={q_news}&hl=en-US&gl=US&ceid=US:en",
        f"Yahoo [{t}]":       f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={t}&region=US&lang=en-US",
    }


def _parse_date(entry):
    for key in ("published", "updated", "pubDate"):
        if entry.get(key):
            try:
                return dateparser.parse(entry[key])
            except (ValueError, TypeError, OverflowError):
                pass
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
    text = re.sub(r"<[^>]+>", " ", entry.get("summary", "") or "")
    return re.sub(r"\s+", " ", text).strip()[:400]


def _clean_title(raw: str) -> str:
    t = (raw or "").replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", t).strip()


def _dedup_key(title: str) -> str:
    """Normalize for de-duplication: lowercase, drop a trailing ' - Publisher'
    that Google News appends, drop punctuation, collapse spaces."""
    t = title.lower()
    t = re.sub(r"\s+[-–|]\s+[^-–|]{2,45}$", "", t)   # remove trailing " - Source"
    t = re.sub(r"[^a-z0-9 ]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def fetch_feed(name: str, url: str, tag: str | None, max_items: int = 25) -> list[dict]:
    """Fetch one feed. `tag` = the ticker this feed belongs to (or None for general)."""
    out: list[dict] = []
    try:
        parsed = feedparser.parse(url)
        for entry in parsed.entries[:max_items]:
            out.append({
                "title":   _clean_title(entry.get("title") or ""),
                "link":    entry.get("link") or "",
                "source":  name,
                "summary": _clean_summary(entry),
                "dt":      _parse_date(entry),
                "tickers": {tag} if tag else set(),
            })
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] feed failed: {name} -> {exc}")
    return out


def _match_tickers(text: str, watchlist: list[str]) -> set[str]:
    """Which watchlist tickers are mentioned in this text (symbol or company name)."""
    low = text.lower()
    hits = set()
    for t in watchlist:
        terms = [t.lower()] + TICKER_ALIASES.get(t, [])
        for term in terms:
            # word-boundary match avoids 'MU' matching inside other words
            if re.search(r"\b" + re.escape(term) + r"\b", low):
                hits.add(t)
                break
    return hits


def fetch_all(tickers: list[str] | None = None, max_per_feed: int = 25) -> list[dict]:
    watchlist = [t.strip().upper() for t in (tickers or []) if t.strip()]

    jobs: list[tuple[str, str, str | None]] = [(n, u, None) for n, u in GENERAL_FEEDS.items()]
    for t in watchlist:
        for n, u in ticker_feeds(t).items():
            jobs.append((n, u, t))

    items: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(fetch_feed, n, u, tag, max_per_feed) for n, u, tag in jobs]
        for fut in concurrent.futures.as_completed(futures):
            items.extend(fut.result())

    # de-dup by normalized title (merges "X" and "X - Publisher"), merging tags
    seen: dict[str, dict] = {}
    for it in items:
        key = _dedup_key(it["title"])
        if not key:
            continue
        if key in seen:
            seen[key]["tickers"] |= it["tickers"]
        else:
            seen[key] = it
    deduped = list(seen.values())

    # text-match pass: tag general-feed items that mention a watchlist company
    for it in deduped:
        it["tickers"] |= _match_tickers(f"{it['title']} {it['summary']}", watchlist)
        it["tickers"] = sorted(it["tickers"])

    from datetime import datetime, timezone
    def sort_key(it):
        dt = it["dt"]
        if dt is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    deduped.sort(key=sort_key, reverse=True)
    return deduped
