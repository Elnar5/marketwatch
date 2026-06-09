"""
app.py — Trading News + AI Analyst  (polished mobile-friendly dashboard)
Run:  streamlit run app.py
"""

from __future__ import annotations

import html
from datetime import datetime, timezone, date, timedelta

import streamlit as st

import news_sources
import analysis
import gainers
import polygon_data


st.set_page_config(page_title="MarketWatch", page_icon="icon.png", layout="centered")


# ----------------------------- styling --------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&family=JetBrains+Mono:wght@500&display=swap');

:root{
  --ink:#14120d; --ink2:#1d1a13; --card:#211d15; --line:#3a3326;
  --cream:#ece3d2; --muted:#9a8f78; --amber:#e0a33e; --amber-dim:#a87f33;
  --up:#7fb069; --down:#cf6a5a;
}
.stApp{
  background:
    radial-gradient(1200px 600px at 80% -10%, #241f16 0%, transparent 60%),
    radial-gradient(900px 500px at -10% 10%, #1c1810 0%, transparent 55%),
    var(--ink);
  color:var(--cream);
}
/* hide streamlit chrome for an app-like feel */
#MainMenu, header, footer, [data-testid="stDecoration"]{display:none!important;}
.block-container{padding-top:1.1rem; padding-bottom:3rem; max-width:680px;}

/* typography */
html, body, [class*="css"]{font-family:'Newsreader', Georgia, serif;}
h1,h2,h3,.app-title{font-family:'Fraunces', serif!important; letter-spacing:-.01em;}

/* header */
.app-head{border-bottom:1px solid var(--line); padding-bottom:.7rem; margin-bottom:1rem;}
.app-title{font-size:2.05rem; font-weight:600; color:var(--cream); line-height:1.05; margin:0;}
.app-title .dot{color:var(--amber);}
.app-tag{font-family:'JetBrains Mono',monospace; font-size:.72rem; letter-spacing:.18em;
  text-transform:uppercase; color:var(--amber-dim); margin-top:.35rem;}

/* news cards */
.news-card{background:linear-gradient(180deg,var(--card),var(--ink2));
  border:1px solid var(--line); border-radius:14px; padding:.95rem 1.05rem .55rem;
  margin-bottom:.2rem; box-shadow:0 1px 0 rgba(255,255,255,.02) inset;}
.news-meta{font-family:'JetBrains Mono',monospace; font-size:.66rem; letter-spacing:.06em;
  text-transform:uppercase; color:var(--muted); margin-bottom:.35rem;}
.news-meta .src{color:var(--amber);}
.news-title{font-family:'Fraunces',serif; font-size:1.12rem; font-weight:600;
  color:var(--cream); text-decoration:none; line-height:1.25; display:block;}
.news-title:hover{color:var(--amber);}
.news-sum{font-size:.95rem; color:#cfc4ad; line-height:1.5; margin:.45rem 0 .2rem;}
.tk{display:inline-block; font-family:'JetBrains Mono',monospace; font-size:.6rem;
  color:var(--ink); background:var(--amber); border-radius:5px; padding:.05rem .35rem;
  margin-left:.25rem; letter-spacing:.05em; vertical-align:middle;}
.imp{font-family:'JetBrains Mono',monospace; font-size:.62rem; color:var(--down);
  font-weight:700; letter-spacing:.03em;}

/* buttons */
.stButton > button{
  font-family:'JetBrains Mono',monospace!important; font-size:.7rem!important;
  letter-spacing:.1em; text-transform:uppercase;
  background:transparent; color:var(--amber); border:1px solid var(--amber-dim);
  border-radius:9px; padding:.32rem .8rem; transition:all .15s ease;}
.stButton > button:hover{background:var(--amber); color:var(--ink); border-color:var(--amber);}
.stButton > button[kind="primary"]{background:var(--amber); color:var(--ink); border:none;}

/* inputs */
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"]{
  background:var(--ink2)!important; color:var(--cream)!important;
  border:1px solid var(--line)!important; border-radius:10px!important;
  font-family:'JetBrains Mono',monospace!important; font-size:.85rem!important;}
label, .stCaption, [data-testid="stCaptionContainer"]{color:var(--muted)!important;}

/* tabs */
.stTabs [data-baseweb="tab-list"]{gap:.2rem; border-bottom:1px solid var(--line);}
.stTabs [data-baseweb="tab"]{font-family:'JetBrains Mono',monospace; font-size:.72rem;
  letter-spacing:.08em; text-transform:uppercase; color:var(--muted); padding:.4rem .6rem;}
.stTabs [aria-selected="true"]{color:var(--amber)!important;}
.stTabs [data-baseweb="tab-highlight"]{background:var(--amber)!important;}

/* sidebar */
[data-testid="stSidebar"]{background:var(--ink2); border-right:1px solid var(--line);}
[data-testid="stSidebar"] h1{font-size:1.2rem; color:var(--amber);}

/* analysis container */
[data-testid="stExpander"]{border:1px solid var(--line)!important; border-radius:12px!important;
  background:var(--ink2)!important;}
[data-testid="stExpander"] summary{font-family:'JetBrains Mono',monospace; font-size:.72rem;
  letter-spacing:.08em; text-transform:uppercase; color:var(--amber);}
hr{border-color:var(--line);}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data(ttl=300, show_spinner=False)
def load_news(tickers_tuple: tuple[str, ...], max_per_feed: int):
    return news_sources.fetch_all(list(tickers_tuple), max_per_feed=max_per_feed)


@st.cache_data(ttl=600, show_spinner=False)
def get_scores(titles: tuple, watchlist: tuple, api_key: str, model: str):
    """Cached impact + semantic-ticker scoring. Returns {title: {impact, tickers}}."""
    rows = analysis.score_news(api_key, list(titles), list(watchlist), model)
    tl = list(titles)
    out = {}
    for r in rows:
        i = r.get("i")
        if isinstance(i, int) and 0 <= i < len(tl):
            out[tl[i]] = {"impact": int(r.get("impact", 0)), "tickers": r.get("tickers", [])}
    return out


@st.cache_data(ttl=300, show_spinner=False)
def load_gainers(count: int):
    return gainers.fetch_gainers(count)


@st.cache_data(show_spinner=False)
def bt_fetch(poly_key: str, dates: tuple, pace: float = 12.5):
    return polygon_data.fetch_range(poly_key, list(dates), pace_seconds=pace)


def bt_calendar(s: date, e: date) -> list[str]:
    # never request today/future — free tier forbids today before EOD
    last = min(e + timedelta(days=6), date.today() - timedelta(days=1))
    cur, out = s - timedelta(days=5), []   # pad back for prior close
    while cur <= last:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def humanize(dt):
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    mins = int((datetime.now(timezone.utc) - dt).total_seconds() // 60)
    if mins < 1: return "just now"
    if mins < 60: return f"{mins}m ago"
    if mins < 1440: return f"{mins // 60}h ago"
    return dt.strftime("%d %b %H:%M")


# ----------------------------- header ----------------------------------------
st.markdown(
    "<div class='app-head'>"
    "<div class='app-title'>Market<span class='dot'>.</span>Watch</div>"
    "<div class='app-tag'>News feed · AI read · not advice</div>"
    "</div>", unsafe_allow_html=True)

# Settings live in the main page (not the sidebar) so they're always reachable on
# mobile. Open by default until a key is entered, then it stays where you leave it.
with st.expander("⚙️ Settings — Gemini key, watchlist",
                 expanded=not st.session_state.get("api_key")):
    api_key = st.text_input("Gemini API key", type="password",
                            value=st.session_state.get("api_key", ""),
                            help="Free: aistudio.google.com/app/apikey")
    st.session_state["api_key"] = api_key
    model_name = st.text_input("Model", value="gemini-2.5-flash")
    tickers_raw = st.text_input("Watchlist (comma-separated)", value="MU, NVDA, AVGO")
    poly_key = st.text_input("Polygon API key (for 🔬 Backtest — free: polygon.io)",
                             type="password", value=st.session_state.get("poly_key", ""))
    st.session_state["poly_key"] = poly_key
    max_per_feed = st.slider("Items per source", 10, 50, 25)
    if st.button("🔄 Refresh news"):
        load_news.clear()
        st.session_state.pop("scores", None)

tickers = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]

with st.spinner("Pulling the wires…"):
    items = load_news(tuple(tickers), max_per_feed)

# Apply previously-computed impact scores if present. This costs NO API call —
# scoring only runs when you tap "Rank by impact" (see the Feed tab).
_scores = st.session_state.get("scores") or {}
for it in items:
    row = _scores.get(it["title"])
    if row:
        it["impact"] = int(row.get("impact", 0))
        it["tickers"] = sorted(set(it.get("tickers", [])) | {t for t in row.get("tickers", []) if t})
    else:
        it.setdefault("impact", 0)
if _scores:
    items.sort(key=lambda it: it.get("impact", 0), reverse=True)

tab_feed, tab_gainers, tab_backtest, tab_calc, tab_ticker, tab_paste = st.tabs(
    ["📰 Feed", "🚀 Gainers", "🔬 Backtest", "💰 Calc", "🤖 Ticker", "📋 Paste"])


# ------------------------- tab 1: feed ---------------------------------------
with tab_feed:
    ranked = bool(st.session_state.get("scores"))
    cols = st.columns([1, 1])
    if cols[0].button("🔥 Rank by impact" + (" ✓" if ranked else " (1 request)")):
        if not api_key:
            st.warning("Add your Gemini key in Settings first.")
        else:
            with st.spinner("Reading every headline & ranking…"):
                try:
                    st.session_state["scores"] = get_scores(
                        tuple(it["title"] for it in items[:60]), tuple(tickers), api_key, model_name)
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Failed: {exc}")
    if ranked and cols[1].button("↺ Clear ranking"):
        st.session_state.pop("scores", None)
        st.rerun()

    # If a watchlist is set, show only news relevant to it (by ticker/company-name
    # tags) — works WITHOUT spending an API call. If that finds nothing (rare),
    # fall back to all news so the feed is never empty. Ranking later adds the
    # semantic (indirect) matches + impact ordering.
    if tickers:
        relevant = [it for it in items if set(it.get("tickers", [])) & set(tickers)]
        base = relevant if relevant else items
    else:
        base = items
    only = st.selectbox("Filter", ["All"] + tickers, label_visibility="collapsed")
    shown = base if only == "All" else [it for it in base if only in it.get("tickers", [])]
    if ranked:
        order = "most explosive first 🔥" + (" · your watchlist" if tickers else "")
    elif tickers:
        order = "your watchlist · newest first · tap Rank by impact for impact + indirect"
    else:
        order = "newest first · tap Rank by impact to sort"
    st.caption(f"{len(shown)} headlines · {order}")

    for i, it in enumerate(shown):
        title = html.escape(it["title"])
        link = html.escape(it["link"] or "#")
        summ = html.escape(it["summary"]) if it["summary"] else ""
        src = html.escape(it["source"])
        tags = "".join(f"<span class='tk'>{html.escape(t)}</span>" for t in it.get("tickers", []))
        imp = it.get("impact", 0)
        flame = f"<span class='imp'>🔥 {imp}</span> " if imp >= 7 else ""
        st.markdown(
            f"<div class='news-card'>"
            f"<div class='news-meta'>{flame}<span class='src'>{src}</span> · {humanize(it['dt'])}{tags}</div>"
            f"<a class='news-title' href='{link}' target='_blank'>{title}</a>"
            f"{f'<p class=\"news-sum\">{summ}</p>' if summ else ''}"
            f"</div>", unsafe_allow_html=True)

        rid = f"res::{it['link'] or it['title']}"
        if st.button("🔍 Analyze", key=f"b::{i}"):
            if not api_key:
                st.session_state[rid] = "⚠️ Add your Gemini key in ⚙️ Settings (top)."
            else:
                with st.spinner("Reading the tea leaves…"):
                    try:
                        st.session_state[rid] = analysis.analyze_single(
                            api_key, f"{it['title']}. {it['summary']}", "", model_name)
                    except Exception as exc:  # noqa: BLE001
                        st.session_state[rid] = f"Gemini failed: {exc}"
        if st.session_state.get(rid):
            with st.expander("AI analysis", expanded=True):
                st.markdown(st.session_state[rid])


# ------------------------- tab: gainers --------------------------------------
with tab_gainers:
    st.caption("Today's biggest gainers across the US market. ⚠️ Chasing these is "
               "high-risk — most extreme daily gainers pull back. Read each one first.")
    gl = load_gainers(40)
    if not gl:
        st.warning("Couldn't load gainers right now — the data source may be blocking "
                   "the server. Tell Claude and we'll switch to another source.")
    for i, g in enumerate(gl):
        st.markdown(
            f"<div class='news-card'>"
            f"<div class='news-meta'>"
            f"<span style='color:var(--up);font-weight:700'>+{g['pct']:.1f}%</span> "
            f"<span class='src'>{html.escape(g['ticker'])}</span> · ${g['price']:.2f}</div>"
            f"<div class='news-title' style='font-size:1rem'>{html.escape(g['name'])}</div>"
            f"</div>", unsafe_allow_html=True)
        rid = f"gain::{g['ticker']}"
        if st.button("Why is it up? ✨", key=f"g::{i}"):
            if not api_key:
                st.session_state[rid] = "⚠️ Add your Gemini key in ⚙️ Settings (top)."
            else:
                with st.spinner(f"Reading {g['ticker']}…"):
                    try:
                        feeds = news_sources.ticker_feeds(g["ticker"])
                        name, url = list(feeds.items())[0]   # Google News [TICKER]
                        heads = [it["title"] for it in
                                 news_sources.fetch_feed(name, url, g["ticker"], 10)]
                        st.session_state[rid] = analysis.analyze_gainer(
                            api_key, g["ticker"], g["name"], g["pct"], heads, model_name)
                    except Exception as exc:  # noqa: BLE001
                        st.session_state[rid] = f"Failed: {exc}"
        if st.session_state.get(rid):
            with st.expander("Why + persistence read", expanded=True):
                st.markdown(st.session_state[rid])


# ------------------------- tab: backtest -------------------------------------
with tab_backtest:
    st.caption("Pick a past date → that day's REAL top gainers → why → did they stay? "
               "Price facts (top-N, days-in-top, next-day) are exact. ⏳ First build "
               "takes ~4-5 min (Polygon 5/min free limit), then it's cached.")
    cc1, cc2 = st.columns(2)
    bt_start = cc1.date_input("From", value=date.today() - timedelta(days=21), key="bts")
    bt_end = cc2.date_input("To", value=date.today() - timedelta(days=1), key="bte")
    bt_n = st.slider("Top N", 5, 20, 10, key="btn_n")

    if st.button("📊 Build rankings", type="primary"):
        if not poly_key:
            st.error("Add your Polygon key in ⚙️ Settings (top).")
        elif bt_start >= bt_end:
            st.error("'From' must be before 'To'.")
        else:
            dts = bt_calendar(bt_start, bt_end)
            with st.spinner(f"Fetching ~{len(dts)} days from Polygon "
                            f"(~{len(dts)*12//60}+ min first time, then cached)…"):
                try:
                    closes = bt_fetch(poly_key, tuple(dts))
                    rd, rk = polygon_data.compute_rankings(closes, bt_n)
                    rd = [d for d in rd if bt_start.isoformat() <= d <= bt_end.isoformat()]
                    st.session_state["bt"] = {"dates": rd, "rk": rk}
                    if rd:
                        st.success(f"Done — {len(rd)} trading days ranked.")
                    else:
                        st.warning("No trading days returned. Check your Polygon key, or "
                                   "pick an older / wider range (today isn't available "
                                   "on the free tier until after market close).")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Failed: {exc}")

    bt = st.session_state.get("bt")
    if bt and bt["dates"]:
        sel = st.selectbox("Date", bt["dates"][::-1], key="bt_sel")
        rows = bt["rk"][sel]
        st.markdown(f"#### Top {len(rows)} — {sel}")
        for i, e in enumerate(rows):
            nxt = e.get("stayed_next")
            tag = ("✅ stayed" if nxt else ("❌ dropped" if nxt is False else "— last day"))
            st.markdown(
                f"**{i+1}. {e['ticker']}** · +{e['pct']:.1f}% · ${e['close']:.2f}  \n"
                f"🔥 {e['days_in_top']}d in top {len(rows)} · next day: {tag}")
            fwd = e.get("fwd") or []
            if fwd:
                fwd_txt = " · ".join(f"+{j}d {p:+.0f}%" for j, (_, p) in enumerate(fwd, 1))
                st.caption(f"from this day's close → {fwd_txt}")
            rid = f"bt::{sel}::{e['ticker']}"
            if st.button(f"Analyze {e['ticker']} ✨", key=f"bta::{i}"):
                if not api_key:
                    st.session_state[rid] = "⚠️ Add your Gemini key in ⚙️ Settings."
                else:
                    with st.spinner(f"Analysing {e['ticker']} (news around {sel})…"):
                        try:
                            heads = polygon_data.ticker_news(poly_key, e["ticker"], sel)
                            st.session_state[rid] = analysis.analyze_gainer(
                                api_key, e["ticker"], e["ticker"], e["pct"], heads, model_name)
                        except Exception as exc:  # noqa: BLE001
                            st.session_state[rid] = f"Failed: {exc}"
            if st.session_state.get(rid):
                with st.expander(f"{e['ticker']} — reasons + persistence", expanded=True):
                    st.caption(f"News pulled from around {sel} (Polygon). Empty = no "
                               "coverage for that date (often itself a no-news pump).")
                    st.markdown(st.session_state[rid])
            st.divider()

        stayed = sum(1 for d in bt["dates"] for e in bt["rk"][d]
                     if e.get("stayed_next") is True)
        total = sum(1 for d in bt["dates"] for e in bt["rk"][d]
                    if e.get("stayed_next") is not None)
        if total:
            st.info(f"This range: **{stayed}/{total} ({stayed/total*100:.0f}%)** of "
                    f"top-{bt_n} gainers stayed in the top-{bt_n} the next day.")


# ------------------------- tab: calc -----------------------------------------
with tab_calc:
    st.caption("Net profit calculator — uses your REAL ABB/Birbank rates + the 0.40% "
               "commission (both ways) and shows the true % you keep. The FX cost is "
               "derived automatically from the buy/sell rates.")

    c1, c2 = st.columns(2)
    buy_price = c1.number_input("Buy price / share ($)", min_value=0.01, value=200.0, step=1.0)
    amount_azn = c2.number_input("Amount invested (AZN)", min_value=1.0, value=1200.0, step=50.0)
    target = st.select_slider("Target NET profit (%)",
                              options=[1, 2, 3, 4, 5, 6, 7, 8, 10, 15, 20], value=3)

    with st.expander("⚙️ Rates & commission (your ABB / Birbank numbers)"):
        rate_buy = st.number_input("AZN→USD rate (you pay buying $)", value=1.7190,
                                   step=0.0001, format="%.4f")
        rate_sell = st.number_input("USD→AZN rate (you get selling $)", value=1.6965,
                                    step=0.0001, format="%.4f")
        comm_pct = st.number_input("Commission per trade (%)", value=0.40, step=0.05) / 100
        cc1, cc2 = st.columns(2)
        comm_min = cc1.number_input("Min commission ($)", value=1.0, step=0.5)
        comm_max = cc2.number_input("Max commission ($)", value=100.0, step=10.0)

    fx_legs = st.radio(
        "Currency conversions to count",
        options=[2, 1, 0],
        format_func=lambda n: {
            2: "Round trip: AZN→USD→trade→USD→AZN  (pay FX twice)",
            1: "One way: convert once, keep the rest in USD  (FX once)",
            0: "Already in USD, stays in USD  (no FX, only commission)",
        }[n], index=0,
        help="If you keep money in USD and don't cash out to AZN, FX is paid fewer times.")

    def comm_usd(v):
        return min(max(v * comm_pct, comm_min), comm_max)

    ratio = rate_sell / rate_buy
    fx_factor = {2: ratio, 1: ratio ** 0.5, 0: 1.0}[fx_legs]
    fx_cost = (1 - fx_factor) * 100                 # FX cost for chosen legs
    unit = "AZN" if fx_legs == 2 else "USD"
    usd_avail = amount_azn / rate_buy if fx_legs >= 1 else amount_azn
    c_eff = comm_usd(usd_avail) / usd_avail         # effective comm rate (respects min/max)
    T = target / 100

    g = (1 + T) / (fx_factor * (1 - c_eff) ** 2) - 1   # gross rise to NET target
    target_price = buy_price * (1 + g)
    net_amt = amount_azn * T
    friction = g * 100 - target

    st.markdown(f"### To NET **{target}%** (≈ **{net_amt:.0f} {unit}**)")
    st.markdown(f"- Stock must rise **{g*100:.2f}%** (gross)")
    st.markdown(f"- Sell target: **${target_price:.2f}**  (from ${buy_price:.2f})")
    st.caption(f"Friction **{friction:.2f}%** = FX {fx_cost:.2f}% (counted ×{fx_legs}) + "
               f"commission ~{c_eff*200:.2f}% (both trades). Rates {rate_buy:.4f}/{rate_sell:.4f}.")

    st.divider()
    st.markdown("**↩︎ Reverse — what did I ACTUALLY net?**")
    sell_price = st.number_input("Actual sell price ($)", min_value=0.0, value=210.0, step=1.0)
    if sell_price > 0 and buy_price > 0:
        g_act = sell_price / buy_price - 1
        net_frac = fx_factor * (1 - c_eff) ** 2 * (1 + g_act) - 1
        net_amt2 = amount_azn * net_frac
        color = "var(--up)" if net_frac >= 0 else "var(--down)"
        st.markdown(
            f"Stock moved **{g_act*100:.2f}%** → you NET "
            f"<span style='color:{color};font-weight:700'>{net_frac*100:.2f}%</span> "
            f"(≈ **{net_amt2:+.0f} {unit}**)", unsafe_allow_html=True)
        st.caption(f"FX counted ×{fx_legs}. Commission ~{c_eff*100:.2f}%/trade "
                   f"(min ${comm_min:.0f} / max ${comm_max:.0f}).")
        if net_frac < 0:
            st.warning("Net negative — costs swallowed the move.")


# ------------------------- tab 2: ticker -------------------------------------
with tab_ticker:
    target = st.selectbox("Analyze ticker", ["(general market)"] + tickers, key="tk")
    tt = "" if target == "(general market)" else target
    if st.button("Analyze ✨", type="primary", key="tkb"):
        if not api_key:
            st.error("Add your Gemini key in Settings.")
        else:
            rel = ([it for it in items if tt in it.get("tickers", [])] or items[:40]) if tt else items[:40]
            with st.spinner(f"Analyzing {target}…"):
                try:
                    st.markdown(analysis.analyze(api_key, tt, rel, model_name))
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Gemini failed: {exc}")


# ------------------------- tab 3: paste --------------------------------------
with tab_paste:
    pt = st.text_input("Stock (optional)", value="", key="pt")
    txt = st.text_area("Paste a news item", height=170,
                       placeholder="Paste any headline or article…")
    if st.button("Analyze this ✨", type="primary", key="pb"):
        if not api_key:
            st.error("Add your Gemini key in Settings.")
        elif not txt.strip():
            st.warning("Paste some text first.")
        else:
            with st.spinner("Reading…"):
                try:
                    st.markdown(analysis.analyze_single(
                        api_key, txt.strip(), pt.strip().upper(), model_name))
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Gemini failed: {exc}")
