"""
app.py — Trading News + AI Analyst  (polished mobile-friendly dashboard)
Run:  streamlit run app.py
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

import streamlit as st

import news_sources
import analysis


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


# ----------------------------- sidebar ---------------------------------------
with st.sidebar:
    st.title("Settings")
    api_key = st.text_input("Gemini API key", type="password",
                            help="Free: aistudio.google.com/app/apikey")
    model_name = st.text_input("Model", value="gemini-2.5-flash")
    tickers_raw = st.text_input("Watchlist", value="MU, NVDA, AVGO")
    max_per_feed = st.slider("Items per source", 10, 50, 25)
    if st.button("Refresh news"):
        load_news.clear()

tickers = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]


# ----------------------------- header ----------------------------------------
st.markdown(
    "<div class='app-head'>"
    "<div class='app-title'>Market<span class='dot'>.</span>Watch</div>"
    "<div class='app-tag'>News feed · AI read · not advice</div>"
    "</div>", unsafe_allow_html=True)

with st.spinner("Pulling the wires…"):
    items = load_news(tuple(tickers), max_per_feed)

tab_feed, tab_ticker, tab_paste = st.tabs(["📰 Feed", "🤖 Ticker", "📋 Paste"])


# ------------------------- tab 1: feed ---------------------------------------
with tab_feed:
    only = st.selectbox("Filter", ["All"] + tickers, label_visibility="collapsed")
    shown = items
    if only != "All":
        shown = [it for it in shown if only in it["title"].upper()
                 or f"[{only}]" in it["source"].upper()]
    st.caption(f"{len(shown)} headlines · newest first")

    for i, it in enumerate(shown):
        title = html.escape(it["title"])
        link = html.escape(it["link"] or "#")
        summ = html.escape(it["summary"]) if it["summary"] else ""
        src = html.escape(it["source"])
        st.markdown(
            f"<div class='news-card'>"
            f"<div class='news-meta'><span class='src'>{src}</span> · {humanize(it['dt'])}</div>"
            f"<a class='news-title' href='{link}' target='_blank'>{title}</a>"
            f"{f'<p class=\"news-sum\">{summ}</p>' if summ else ''}"
            f"</div>", unsafe_allow_html=True)

        rid = f"res::{it['link'] or it['title']}"
        if st.button("🔍 Analyze", key=f"b::{i}"):
            if not api_key:
                st.session_state[rid] = "⚠️ Add your Gemini key in Settings (left)."
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


# ------------------------- tab 2: ticker -------------------------------------
with tab_ticker:
    target = st.selectbox("Analyze ticker", ["(general market)"] + tickers, key="tk")
    tt = "" if target == "(general market)" else target
    if st.button("Analyze ✨", type="primary", key="tkb"):
        if not api_key:
            st.error("Add your Gemini key in Settings.")
        else:
            rel = ([it for it in items if tt in it["title"].upper()
                    or f"[{tt}]" in it["source"].upper()] or items[:40]) if tt else items[:40]
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
