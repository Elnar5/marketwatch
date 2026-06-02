# 📈 Trading News + AI Analyst

A local web dashboard that:

1. **Faza 1 — aggregates news** from many free sources (CNBC, MarketWatch, Yahoo,
   Investing, Seeking Alpha, NASDAQ + a Google News search feed per ticker that
   pulls from *thousands* of outlets, so you don't miss anything).
2. **Faza 2 — shows it live** in a browser dashboard you can filter and search.
3. **Faza 3 — explains it with Google Gemini** as a plain-text analysis: what's
   happening, whether it's already priced in, near-term catalysts, and bull/base/bear
   scenarios.

> Research tool, not financial advice. An LLM cannot truly predict prices — it helps
> you *think*, it does not give you a magic "buy" signal.

---

## Setup (local computer)

```bash
# 1. (optional but recommended) create a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. get a FREE Gemini API key:
#    https://aistudio.google.com/app/apikey

# 4. run it
streamlit run app.py
```

It opens in your browser (usually http://localhost:8501).
Paste your Gemini key in the sidebar, set your watchlist (e.g. `MU, NVDA, AVGO`),
and you're live.

---

## How to extend it

- **More news sources:** add an entry to `GENERAL_FEEDS` or a URL inside
  `ticker_feeds()` in `news_sources.py`. Any RSS feed works.
- **Different model:** change the model name in the sidebar (e.g. a newer Gemini).
- **Trusted-people feeds:** add their RSS / newsletter feeds to `GENERAL_FEEDS`.
  (X/Twitter now needs a paid API, so start with RSS + Google News.)

## Files
- `news_sources.py` — fetches & dedupes news (Faza 1)
- `app.py` — the Streamlit dashboard (Faza 2)
- `analysis.py` — Gemini text analysis (Faza 3)
- `requirements.txt` — dependencies
