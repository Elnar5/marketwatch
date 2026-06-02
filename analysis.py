"""
analysis.py
-----------
Faza 3 — LLM analizi (Google Gemini, current `google-genai` SDK).

Two functions:
  analyze()        -> analyze a BATCH of headlines for a ticker (scenarios, prose).
  analyze_single() -> analyze ONE news item in detail + an honest likelihood/
                      probability lean that the stock rises from here.

Get a free API key at: https://aistudio.google.com/app/apikey
"""

from __future__ import annotations

from google import genai
from google.genai import types


SYSTEM_INSTRUCTION = """You are a sharp, honest equity research assistant.
You read market news and explain, in plain prose, what it might mean for a stock.

Hard rules:
- Direction from here depends on REALITY vs EXPECTATIONS, not on whether news is
  "good". A great company can fall if the price already assumed even better.
- Always judge the "expectations bar": is this news already priced in (the stock
  already ran, hype is high) or are expectations low (a low bar is easier to beat)?
- If the news is just a rumor or a meeting (no signed deal, no revenue), say so and
  flag "sell the news" risk.
- Be concrete about near-term catalysts (earnings dates, product launches, events).
- Keep it readable prose. No JSON, no tables."""


# For single-news analysis we DO ask for a probability lean — but an honest one.
SINGLE_INSTRUCTION = SYSTEM_INSTRUCTION + """

You will be given ONE specific news item. Give a focused, detailed read of it.
You ARE allowed to give a probability lean AND rough move-size ranges, but honestly:
- Express probability as NUMERIC % RANGES, never vague words. Give the chance of
  UP vs DOWN over ~5 trading days as ranges, e.g. "Up: 60-70% / Down: 30-40%".
  Do NOT use terms like "low/moderate/high confidence" or "slightly" on their own —
  always attach numbers. A RANGE (not a single point) is what keeps it honest.
- You may give rough PRICE-MOVE RANGES over a short horizon (~5 trading days) as
  bull / base / bear SCENARIOS, each with the CONDITION that would cause it
  (e.g. "Bull, if guidance is raised: +6 to +10%"). These are ILLUSTRATIVE
  scenarios about the SIZE of possible moves — NOT predictions. Say plainly you
  cannot actually predict the price; smart money sees the same news.
- List READ-THROUGH tickers: other companies (peers, suppliers, customers) this
  news could move, each with direction (up/down) and a one-line why.
- If most of the move is likely already priced in, the honest lean may be down/flat
  even on good news, and the scenario sizes should reflect that."""


def _build_prompt(ticker: str, news_items: list[dict]) -> str:
    header = (
        f"Ticker / focus: {ticker or 'general market'}\n"
        f"Here are the most recent headlines (newest first). Use them as your evidence.\n\n"
    )
    lines = []
    for i, it in enumerate(news_items, 1):
        when = it["dt"].strftime("%Y-%m-%d %H:%M") if it.get("dt") else "n/a"
        lines.append(f"{i}. [{when}] ({it['source']}) {it['title']}\n   {it['summary']}")
    body = "\n".join(lines) if lines else "(no headlines found)"

    ask = f"""

Write a clear analysis of {ticker or 'the current market'} based ONLY on the
headlines above plus general knowledge of the company/sector. Cover, in prose:

1. What is actually happening right now (the key story in 2-3 sentences).
2. Why it matters for the stock — possible causes and effects.
3. The expectations bar: is this already priced in, or are expectations low? Explain.
4. The company's known plans / direction relevant to this.
5. Near-term catalysts to watch (with rough dates if known) that could move it.
6. Scenarios: bull / base / bear — what would have to happen for each, and which
   feels more likely and WHY.
7. End with: the single most important thing to watch next.
"""
    return header + body + ask


def analyze(api_key: str, ticker: str, news_items: list[dict],
            model_name: str = "gemini-2.5-flash") -> str:
    """Batch analysis of a ticker's recent headlines."""
    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(ticker, news_items[:40])
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION),
    )
    return response.text


def analyze_single(api_key: str, news_text: str, ticker: str = "",
                   model_name: str = "gemini-2.5-flash") -> str:
    """Detailed analysis of ONE news item + an honest probability lean."""
    client = genai.Client(api_key=api_key)
    focus = f"(stock in focus: {ticker})\n\n" if ticker else ""
    prompt = f"""{focus}Here is a single news item. Analyze it in detail, in prose:

NEWS:
\"\"\"{news_text}\"\"\"

Cover, in this order:

VERDICT (first line, one line, all numeric — no vague words): direction arrow +
UP vs DOWN probability as % ranges over ~5 trading days + the bull/bear move sizes.
Example: "↑ Lean up · Up 60-70% / Down 30-40% over ~5d · bull +6 to +10%, bear -8%".

1. What this news actually says / means (plainly).
2. Which company/stock it most affects, and why it matters.
3. Is the move likely already priced in, or are expectations low? (expectations bar)
4. Likely near-term effect on the stock, and any catalysts this sets up.
5. READ-THROUGH — other companies this could move (peers / suppliers / customers):
   for each, give TICKER, direction (up/down), and a one-line why. This is the
   ripple effect to watch BEFORE those names report themselves.
6. SCENARIOS over ~5 trading days (illustrative, NOT a prediction): bull / base /
   bear, each with a numeric % range AND the condition that would trigger it.
7. PROBABILITY: the UP vs DOWN chance as NUMERIC % RANGES over ~5 days
   (e.g. "Up 60-70% / Down 30-40%") — NO vague words like "moderate". Then your
   reasoning. Remind that this is an estimate, not a guarantee.
8. The single most important thing to watch next.
"""
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SINGLE_INSTRUCTION),
    )
    return response.text


def score_news(api_key: str, titles: list[str], watchlist: list[str],
               model_name: str = "gemini-2.5-flash") -> list[dict]:
    """One cheap call: for each headline return impact (0-10) + which watchlist
    tickers it affects directly OR indirectly. Returns [{"i","impact","tickers"}]."""
    import json
    client = genai.Client(api_key=api_key)
    wl = ", ".join(watchlist) if watchlist else "(empty — leave tickers [])"
    listing = "\n".join(f"{i}: {t}" for i, t in enumerate(titles[:60]))
    prompt = f"""Watchlist tickers: {wl}

For EACH headline below decide:
- "impact": integer 0-10 = how market-moving / explosive it is (10 = could move a
  stock sharply today; 3-5 = normal; 0 = noise/duplicate).
- "tickers": which of the watchlist tickers this news could affect DIRECTLY OR
  INDIRECTLY. Indirect counts: e.g. "AI memory demand surges" affects MU/NVDA even
  if unnamed; "rate cut" affects rate-sensitive names. Use ONLY tickers from the
  watchlist above. If watchlist is empty, return [].

Return ONLY a JSON array, no prose:
[{{"i":0,"impact":7,"tickers":["NVDA"]}}, ...]

Headlines:
{listing}"""
    resp = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    data = json.loads(resp.text)
    out = []
    for d in data:
        if isinstance(d, dict) and "i" in d:
            out.append({
                "i": int(d["i"]),
                "impact": int(d.get("impact", 0)),
                "tickers": [str(t).upper() for t in (d.get("tickers") or [])],
            })
    return out
