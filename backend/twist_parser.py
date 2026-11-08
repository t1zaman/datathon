"""Turn a judge's twist card (plain English) into shock parameters.
Uses Gemini if GEMINI_API_KEY is set (Best Use of Gemini track), otherwise a rule-based parser.
Always show the parsed values on screen so the presenter can confirm or fix them before running."""
from __future__ import annotations

import json
import os
import re

FIELDS = {
    "income_factor": "fraction of usual income still coming in (EI at 55% -> 0.55, no income -> 0, no change -> 1)",
    "duration_months": "how many months the shock lasts, or null if not stated",
    "household_bills_up_pct": "increase in household bills / rent / utilities as a fraction (15% -> 0.15), else 0",
    "one_off_months_of_spending": "one-off cost expressed in months of typical spending (a full month -> 1.0), else 0",
    "one_off_cost": "one-off cost in dollars if given as an amount, else 0",
    "extra_monthly_spending": "any other recurring monthly dollar increase, else 0",
}

_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
        "nine": 9, "ten": 10, "twelve": 12, "half a": 0.5, "a half": 0.5, "a full": 1, "a": 1, "an": 1}


def _num(tok: str) -> float:
    tok = tok.strip().lower()
    return float(_NUM[tok]) if tok in _NUM else float(tok.replace(",", ""))


def parse_rules(text: str) -> dict:
    t = text.lower()
    out = {k: 0.0 for k in FIELDS}
    out["income_factor"], out["duration_months"] = 1.0, None
    NUMW = r"(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|twelve|half a|a half|a full|an|a)"

    if re.search(r"laid off|lose[s]? (?:their|his|her) job|job loss|lost (?:their|his|her) job|unemploy", t):
        out["income_factor"] = 0.55 if "ei" in re.findall(r"\b\w+\b", t) or "employment insurance" in t else 0.0
    m = re.search(r"(?:ei|employment insurance)[^.%]*?(\d+(?:\.\d+)?)\s*%", t) or \
        re.search(r"(\d+(?:\.\d+)?)\s*%\s*of (?:their|his|her)? ?(?:usual |normal |typical )?income", t)
    if m:
        out["income_factor"] = float(m.group(1)) / 100
    m = re.search(r"income (?:drops|falls|is cut|goes down) (?:by )?(\d+(?:\.\d+)?)\s*%", t)
    if m:
        out["income_factor"] = 1 - float(m.group(1)) / 100
    if re.search(r"no income|income stops|lose all income", t):
        out["income_factor"] = 0.0

    m = re.search(rf"for {NUMW}\s*months?", t)
    if m:
        out["duration_months"] = int(_num(m.group(1)))

    m = re.search(r"(?:household bills|bills|rent|utilities|hydro)[^.]*?(?:up|rise|rises|increase|increases|go up|goes up|jump)[^.\d]*(\d+(?:\.\d+)?)\s*%", t) or \
        re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:higher|more|increase)[^.]*?(?:rent|bills|utilities)", t)
    if m:
        out["household_bills_up_pct"] = float(m.group(1)) / 100

    m = re.search(rf"{NUMW}\s*(?:full )?months? of (?:their )?(?:typical |usual |normal )?spending", t)
    if m:
        out["one_off_months_of_spending"] = _num(m.group(1))
    m = re.search(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(k)?", t)
    if m:
        amt = float(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1)
        if re.search(r"(?:per|a|every|each) month|monthly", t[m.end():m.end() + 25]):
            out["extra_monthly_spending"] = amt
        else:
            out["one_off_cost"] = amt
    # Track rule: a furnace (or similar emergency repair) costs one month of typical spending
    # when the card names no amount.
    if not out["one_off_months_of_spending"] and not out["one_off_cost"] and re.search(
            r"furnace|boiler|water heater|roof|(?:car|house|home|emergency|big|major|surprise)\s+repair|repair bill|breaks down|break[s]? down", t):
        out["one_off_months_of_spending"] = 1.0
    return out


def parse_gemini(text: str) -> dict | None:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    try:
        from google import genai
        timeout_ms = int(float(os.environ.get("GEMINI_TIMEOUT", "8")) * 1000)
        client = genai.Client(api_key=key, http_options={"timeout": timeout_ms})
        prompt = ("You convert a bank stress-test 'twist card' into JSON parameters for a resilience engine.\n"
                  "Return ONLY a JSON object with these keys:\n" +
                  "\n".join(f"- {k}: {v}" for k, v in FIELDS.items()) +
                  f"\n\nTwist card: \"{text}\"")
        r = client.models.generate_content(model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"), contents=prompt,
                                           config={"response_mime_type": "application/json"})
        data = json.loads(r.text)
        base = parse_rules("")
        base.update({k: data[k] for k in FIELDS if k in data})
        return base
    except Exception as e:  # never break the live demo
        print("Gemini parse failed, using rules:", e)
        return None


def parse_twist(text: str) -> tuple[dict, str]:
    # Live-twist speed matters most: use the instant rule reader when it understands the card,
    # and only ask Gemini when the rules found nothing (unusual wording).
    rules = parse_rules(text)
    understood = (rules["income_factor"] != 1.0 or rules["household_bills_up_pct"] or rules["one_off_cost"]
                  or rules["one_off_months_of_spending"] or rules["extra_monthly_spending"])
    if understood:
        return rules, "rules"
    g = parse_gemini(text)
    return (g, "Gemini") if g else (rules, "rules")


if __name__ == "__main__":
    for card in ["This customer was laid off. EI pays 55% of their usual income for 6 months. Do they make it?",
                 "The furnace dies, and the repair costs a full month of their typical spending.",
                 "They lose their job (EI at 55%) and their household bills go up 15% in the same month.",
                 "Rent goes up 20% and their car needs a $2,500 repair.",
                 "Income drops 30% for 4 months and daycare adds $600 per month."]:
        print(card, "\n  ->", parse_twist(card))
