"""
daily50.py — build the day's "worth watching" universe (NOT a buy list).

Combines three free Yahoo predefined screeners — biggest gainers, biggest
losers, and most active by volume — into one de-duplicated list, ranked by how
much is going on (absolute % move, volume as tiebreaker). This is an ATTENTION
screen: the stocks with the most movement/liquidity today.
"""

from __future__ import annotations

import requests

_URL = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json",
}
_SCREENS = ("day_gainers", "day_losers", "most_actives")


def _fetch(scr_id: str, count: int) -> list[dict]:
    try:
        r = requests.get(_URL, params={"count": count, "scrIds": scr_id},
                         headers=_HEADERS, timeout=8)
        r.raise_for_status()
        quotes = r.json()["finance"]["result"][0]["quotes"]
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] {scr_id} fetch failed: {exc}")
        return []
    out = []
    for q in quotes:
        out.append({
            "ticker": q.get("symbol", ""),
            "name":   q.get("shortName") or q.get("longName") or q.get("symbol", ""),
            "pct":    float(q.get("regularMarketChangePercent", 0) or 0),
            "price":  float(q.get("regularMarketPrice", 0) or 0),
            "volume": int(q.get("regularMarketVolume", 0) or 0),
            "src":    scr_id,
        })
    return out


def build_universe(top_n: int = 50, per_screen: int = 50) -> list[dict]:
    """Merge gainers+losers+most-actives, de-dup, rank by |%| then volume."""
    merged: dict[str, dict] = {}
    for scr in _SCREENS:
        for row in _fetch(scr, per_screen):
            tk = row["ticker"]
            if not tk:
                continue
            if tk not in merged or abs(row["pct"]) > abs(merged[tk]["pct"]):
                merged[tk] = row
    rows = list(merged.values())
    # rank: biggest absolute move first, volume as tiebreaker
    rows.sort(key=lambda x: (abs(x["pct"]), x["volume"]), reverse=True)
    return rows[:top_n]


# Compact fallback universe (liquid names) if tickers.txt isn't in the repo.
FALLBACK_UNIVERSE = (
    "AAPL MSFT NVDA AMZN GOOGL META TSLA AVGO AMD TSM MU SMCI MRVL ASML QCOM INTC "
    "ARM PLTR ORCL CRM NFLX ADBE AMAT LRCX KLAC ANET DELL VRT NOW SNOW PANW CRWD "
    "NET DDOG MDB ZS COIN MSTR MARA RIOT CLSK CORZ HOOD SOFI AFRM UPST NU SHOP "
    "UBER ABNB DASH RBLX RDDT DUOL APP SNAP PINS SPOT ROKU DKNG BABA PDD JD BIDU "
    "NIO XPEV LI NTES TME GRAB SE MELI CPNG SNDK WDC ON MPWR NXPI ADI TXN COHR "
    "ALAB CRDO GFS WOLF AI SOUN BBAI IONQ RGTI QBTS ASTS RKLB LUNR OKLO SMR CEG "
    "VST NRG GEV ETN PWR JPM GS MS BAC WFC C SCHW IBKR LLY NVO UNH JNJ MRK ABBV "
    "ISRG VRTX REGN MRNA AMGN GILD DXCM XOM CVX COP EOG SLB OXY DVN CAT DE GE HON "
    "BA RTX LMT NOC F GM RIVN LCID CVNA GME AMC PEP KO PG COST WMT HD LOW TGT NKE "
    "SBUX CMG MCD DIS WBD TMUS V MA AXP PYPL"
).split()


def load_universe_file(path: str = "tickers.txt") -> list[str]:
    try:
        with open(path) as f:
            u = [ln.strip().upper() for ln in f if ln.strip()]
        return u or list(FALLBACK_UNIVERSE)
    except FileNotFoundError:
        return list(FALLBACK_UNIVERSE)


def compute_setups(closes_by_date: dict[str, dict[str, float]], tickers: list[str],
                   ma_window: int = 30, mom_window: int = 15) -> list[dict]:
    """Transparent trend/momentum SETUP screen (forward-looking, heuristic).

    Higher setup score = in a confirmed uptrend, momentum building (not blown-off),
    with room (slightly above the moving average, near but not far past recent high).
    This surfaces names 'on the way up' — NOT a prediction, just a measurable setup.
    """
    dates = sorted(closes_by_date.keys())
    tset = set(tickers)
    out = []
    for tk in tset:
        series = [closes_by_date[d][tk] for d in dates if tk in closes_by_date[d]]
        if len(series) < ma_window + 1:
            continue
        price = series[-1]
        ma = sum(series[-ma_window:]) / ma_window
        if ma <= 0:
            continue
        above_ma = (price - ma) / ma * 100.0
        base = series[-mom_window - 1] if len(series) > mom_window else series[0]
        mom = (price - base) / base * 100.0 if base else 0.0
        recent_high = max(series[-mom_window:])
        off_high = (price - recent_high) / recent_high * 100.0 if recent_high else 0.0

        score = 0.0
        if price > ma:                       # in an uptrend
            score += 40
        mom_pts = max(0.0, min(25.0, mom))   # momentum capped at 25
        if mom > 40:                         # parabolic blow-off → penalize
            mom_pts -= 10
        score += mom_pts
        if 1 <= above_ma <= 12:              # room: healthily above MA, not extended
            score += 20
        elif 12 < above_ma <= 20:
            score += 5
        elif above_ma > 20:                  # too far above MA → bad entry, likely to pull back
            score -= 10
        if -5 <= off_high <= 0:              # coiled near a breakout
            score += 10
        out.append({
            "ticker": tk, "price": round(price, 2), "above_ma": round(above_ma, 1),
            "mom": round(mom, 1), "off_high": round(off_high, 1),
            "setup": round(score, 1),
        })
    out.sort(key=lambda x: x["setup"], reverse=True)
    return out


def compute_setups_market(data_by_date: dict, min_price: float = 5.0,
                          min_dollar_vol: float = 2e7, ma_window: int = 20,
                          mom_window: int = 10, top_n: int = 50) -> list[dict]:
    """Whole-market SETUP scan — NO fixed ticker list. Junk is removed by
    measurable liquidity (price + average dollar volume), not by a whitelist.

    data_by_date: {date: {ticker: (close, volume)}}
    Filters: latest price >= min_price; avg dollar volume (recent) >= min_dollar_vol;
             skip warrants/units/rights/preferred (symbols containing '.').
    """
    dates = sorted(data_by_date.keys())
    if len(dates) < ma_window + 1:
        return []
    # collect per-ticker close series + recent volumes
    series: dict[str, list[float]] = {}
    vols: dict[str, list[float]] = {}
    for d in dates:
        for tk, (c, v) in data_by_date[d].items():
            if "." in tk or not tk.isalpha() or len(tk) > 5:
                continue                      # drop warrants/units/rights/odd symbols
            series.setdefault(tk, []).append(c)
            vols.setdefault(tk, []).append(v)

    out = []
    for tk, s in series.items():
        if len(s) < ma_window + 1:
            continue
        price = s[-1]
        if price < min_price:
            continue
        recent_v = vols[tk][-5:] or vols[tk]
        avg_dollar_vol = (sum(recent_v) / len(recent_v)) * price
        if avg_dollar_vol < min_dollar_vol:
            continue
        ma = sum(s[-ma_window:]) / ma_window
        if ma <= 0:
            continue
        above_ma = (price - ma) / ma * 100.0
        base = s[-mom_window - 1] if len(s) > mom_window else s[0]
        mom = (price - base) / base * 100.0 if base else 0.0
        recent_high = max(s[-mom_window:])
        off_high = (price - recent_high) / recent_high * 100.0 if recent_high else 0.0

        score = 0.0
        if price > ma:
            score += 40
        mom_pts = max(0.0, min(25.0, mom))
        if mom > 40:
            mom_pts -= 10
        score += mom_pts
        if 1 <= above_ma <= 12:
            score += 20
        elif 12 < above_ma <= 20:
            score += 5
        elif above_ma > 20:
            score -= 10
        if -5 <= off_high <= 0:
            score += 10
        out.append({
            "ticker": tk, "price": round(price, 2), "above_ma": round(above_ma, 1),
            "mom": round(mom, 1), "off_high": round(off_high, 1),
            "dollar_vol_m": round(avg_dollar_vol / 1e6, 1), "setup": round(score, 1),
        })
    out.sort(key=lambda x: x["setup"], reverse=True)
    return out[:top_n]
