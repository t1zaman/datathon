"""Ask Hazel: a chat coach grounded in ONE customer's real numbers.

Design rule: the LLM never does the math.
  1. Gemini reads the question + the customer's numbers and decides whether a what-if is needed
     (returns the shock changes as JSON).
  2. Our engine (simulate_shock / build_recovery_plan) computes the real result.
  3. Gemini explains the computed result in plain language.
Without a GEMINI_API_KEY the same flow runs with a rule-based reader, so the demo never breaks.
"""
from __future__ import annotations

import json
import os
import re

from backend.twist_parser import parse_rules

SHOCK_KEYS = ["income_replacement_pct", "household_bills_increase_pct", "one_off_cost",
              "one_off_months_of_spending", "extra_monthly_spending", "duration_months",
              "spending_cut_monthly"]

SYSTEM = """You are Hazel, a friendly squirrel coach inside "Squirrel Away", a bank's financial-resilience tool.
You help a bank advisor (or customer) understand ONE customer's numbers and plan for shocks.
Rules:
- Use ONLY the numbers in CONTEXT or RESULT. Never invent or estimate figures yourself.
- Any new scenario (job loss, bills up, repair, spending cut...) must be run by the engine: request it as a what-if.
- Plain language, warm, short: 2-4 sentences, max ~70 words. Use $ and months. No markdown headings.
- Reply in the same language the user writes in (English, French, Urdu, Arabic, Hindi...).
- This is planning information, not financial advice; don't recommend specific investment products.
- Runway = how many months the savings buffer lasts at the monthly shortfall (judges' formula, capped at 120)."""


def _context(customer: dict, sim: dict, plan: dict) -> dict:
    a, b = sim["after_shock"], sim["before_shock"]
    return {
        "customer": {k: customer.get(k) for k in ["account_id", "income", "spending", "fixed_costs", "buffer",
                                                   "household_bills", "loan_payment", "discretionary_spending",
                                                   "spending_breakdown", "months_of_data", "months_below_zero"]},
        "runway_no_shock": b["runway_display"],
        "current_shock": sim["shock_inputs"],
        "after_current_shock": {k: a[k] for k in ["income", "spending", "buffer_left", "monthly_gap",
                                                  "runway_display", "verdict"]},
        "goal_plan": plan["emergency_fund"],
        "backup_plan": {k: plan["backup_plan"][k] for k in ["status", "minimum_monthly_adjustment_needed", "actions"]},
    }


def _money(v):
    return f"${v:,.0f}"


# ------------------------------------------------------------------ rule-based fallback
def _rules_whatif(message: str, customer: dict, current: dict) -> dict | None:
    t = message.lower()
    changes = {}
    # spending cuts: "cut $300", "cut card spending in half", "cut 20% of spending"
    m = re.search(r"(?:cut|reduce|trim|lower|save)\D{0,40}?\$\s?(\d[\d,]*)", t)
    if m:
        changes["spending_cut_monthly"] = float(m.group(1).replace(",", ""))
    else:
        disc = customer.get("discretionary_spending") or 0
        bd = customer.get("spending_breakdown") or {}
        target = disc
        for word, col in [("card", "card_withdrawals"), ("cash", "cash_withdrawals_genuine"), ("withdraw", "cash_withdrawals_genuine"), ("transfer", "transfers_out_other")]:
            if word in t and col in bd:
                target = bd[col]
        m = re.search(r"(?:cut|reduce|trim|lower)\D{0,40}?(\d+(?:\.\d+)?)\s*%", t)
        if m:
            changes["spending_cut_monthly"] = round(target * float(m.group(1)) / 100, 2)
        elif re.search(r"(?:cut|reduce|trim|lower).*(?:half|50 ?%)", t):
            changes["spending_cut_monthly"] = round(target * 0.5, 2)
    # shocks the twist reader understands
    p = parse_rules(message)
    if p["income_factor"] != 1.0:
        changes["income_replacement_pct"] = round(p["income_factor"] * 100, 2)
    if p["household_bills_up_pct"]:
        changes["household_bills_increase_pct"] = round(p["household_bills_up_pct"] * 100, 2)
    if p["one_off_months_of_spending"]:
        changes["one_off_months_of_spending"] = p["one_off_months_of_spending"]
    if p["one_off_cost"] and "spending_cut_monthly" not in changes:
        changes["one_off_cost"] = p["one_off_cost"]
    if p["extra_monthly_spending"] and "spending_cut_monthly" not in changes:
        changes["extra_monthly_spending"] = p["extra_monthly_spending"]
    if p["duration_months"]:
        changes["duration_months"] = p["duration_months"]
    return changes or None


NAMES = {"cash_withdrawals_genuine": "cash withdrawals", "card_withdrawals": "card spending",
         "transfers_out_other": "other transfers out"}


def _rules_reply(message: str, ctx: dict, result: dict | None, changes: dict | None) -> str:
    c, a = ctx["customer"], ctx["after_current_shock"]
    if changes is not None and changes.get("spending_cut_monthly") == 0 and len(changes) == 1:
        bd = c.get("spending_breakdown") or {}
        flex = sorted(((k, v) for k, v in bd.items() if k in NAMES), key=lambda kv: -kv[1])
        top = flex[0] if flex and flex[0][1] > 0 else None
        return ("That category is $0 for this customer, so cutting it changes nothing."
                + (f" Their flexible money mostly goes to {NAMES[top[0]]} ({_money(top[1])}/month). "
                   f"Try \"what if they cut {NAMES[top[0]]} by 20%?\"" if top else ""))
    if result:
        bits = []
        if changes.get("spending_cut_monthly"):
            bits.append(f"cutting {_money(changes['spending_cut_monthly'])}/month")
        if "income_replacement_pct" in changes:
            bits.append(f"income at {changes['income_replacement_pct']:g}%")
        if changes.get("household_bills_increase_pct"):
            bits.append(f"bills up {changes['household_bills_increase_pct']:g}%")
        if changes.get("one_off_months_of_spending") or changes.get("one_off_cost"):
            bits.append("the one-off cost")
        return (f"I ran it with {', '.join(bits) or 'that change'}: runway goes from {a['runway_display']} "
                f"to {result['runway_display']}. {result['verdict']}")
    t = message.lower()
    if re.search(r"why|short|explain|how come|low", t):
        gap = a["monthly_gap"]
        if gap <= 0:
            return "Income still covers spending after this shock, so the savings never get touched."
        return (f"After the shock, {_money(a['spending'])} goes out but only {_money(a['income'])} comes in, a "
                f"{_money(gap)} gap every month. Their {_money(a['buffer_left'])} buffer covers that for "
                f"{a['runway_display']}.")
    if re.search(r"plan|what should|advice|do\b|help", t):
        return " ".join(ctx["backup_plan"]["actions"]) or "They're covered for this shock."
    if re.search(r"spend|money go|where", t):
        bd = sorted((c.get("spending_breakdown") or {}).items(), key=lambda kv: -kv[1])[:3]
        names = {"cash_withdrawals_genuine": "cash withdrawals", "card_withdrawals": "card spending",
                 "transfers_out_other": "other transfers out"}
        return "Biggest monthly costs: " + ", ".join(f"{names.get(k, k.replace('_', ' '))} {_money(v)}" for k, v in bd) + "."
    return ("Try a what-if like \"what if they cut card spending in half?\", \"what if rent goes up 10%?\" "
            "or ask \"why is the runway so short?\"")


# ------------------------------------------------------------------ Gemini
def _gemini():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    try:
        from google import genai
        # Hard timeout per call so a slow model can never stall a live demo (falls back to rules)
        timeout_ms = int(float(os.environ.get("GEMINI_TIMEOUT", "12")) * 1000)
        return genai.Client(api_key=key, http_options={"timeout": timeout_ms})
    except Exception:
        return None


def _gen_json(client, prompt: str) -> dict:
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    r = client.models.generate_content(model=model, contents=prompt,
                                       config={"system_instruction": SYSTEM, "response_mime_type": "application/json"})
    return json.loads(r.text)


def chat(message: str, history: list, customer: dict, sim: dict, plan: dict, run_whatif) -> dict:
    """run_whatif(changes: dict) -> {'runway_display', 'runway_months', 'verdict', 'shock'} using the real engine."""
    ctx = _context(customer, sim, plan)
    client = _gemini()
    if client:
        try:
            convo = "\n".join(f"{h.get('role', 'user')}: {h.get('text', '')}" for h in (history or [])[-6:])
            step1 = _gen_json(client, (
                f"CONTEXT (this customer's real numbers):\n{json.dumps(ctx, default=float)}\n\n"
                f"RECENT CHAT:\n{convo}\n\nUSER: {message}\n\n"
                "If answering needs a new scenario, return {\"whatif\": {<only the changed keys>}} using keys "
                f"{SHOCK_KEYS} (percentages as numbers like 55, money in $, spending_cut_monthly = $ cut per month, "
                "computed from the customer's breakdown if they say e.g. 'half of card spending'). "
                "Changes apply on top of current_shock. Otherwise return {\"reply\": \"<your answer>\"}."))
            changes = {k: v for k, v in (step1.get("whatif") or {}).items() if k in SHOCK_KEYS and v is not None}
            if changes:
                result = run_whatif(changes)
                step2 = _gen_json(client, (
                    f"CONTEXT:\n{json.dumps(ctx, default=float)}\n\nUSER: {message}\n\n"
                    f"RESULT computed by the engine for what-if {json.dumps(changes)}:\n{json.dumps(result, default=float)}\n\n"
                    "Explain the result to the user. Return {\"reply\": \"...\"}."))
                return {"reply": step2.get("reply", ""), "mode": "Gemini", "whatif": {"changes": changes, **result}}
            return {"reply": step1.get("reply", ""), "mode": "Gemini", "whatif": None}
        except Exception as e:  # never break the demo: fall through to rules
            print("Gemini chat failed, using rules:", e)

    changes = _rules_whatif(message, customer, sim["shock_inputs"])
    zero_cut = changes is not None and changes.get("spending_cut_monthly") == 0 and len(changes) == 1
    result = run_whatif(changes) if changes and not zero_cut else None
    return {"reply": _rules_reply(message, ctx, result, changes), "mode": "rules",
            "whatif": {"changes": changes, **result} if result else None}
