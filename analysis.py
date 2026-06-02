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

You will be given ONE specific news item. Give a focused, detailed read of it,
and you ARE allowed to state a probability/likelihood of the stock rising — but
honestly:
- Give a clear directional lean (more likely up / down / unclear) and a rough
  confidence in WORDS (low / moderate / high), and you may give a rough % RANGE
  (e.g. "maybe 55-65% lean to the upside short-term"), NOT a fake precise number.
- Always justify the number with reasoning, and remind that it is a judgment from
  public information, not a guarantee or real predictive edge.
- If most of the move is likely already priced in, the honest lean may be DOWN or
  flat even on good news."""


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

Cover:
1. What this news actually says / means (plainly).
2. Which company/stock it most affects, and why it matters.
3. Is the move likely already priced in, or are expectations low? (expectations bar)
4. Likely near-term effect on the stock, and any catalysts this sets up.
5. PROBABILITY: your honest lean on whether the stock rises in the near term —
   direction + confidence (low/moderate/high), optionally a rough % range, WITH
   your reasoning. Be clear it's a judgment, not a guarantee.
6. The single most important thing to watch next.
"""
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SINGLE_INSTRUCTION),
    )
    return response.text
