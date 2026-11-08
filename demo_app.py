"""AFTERSHOCK live-demo screen (backup UI on top of the team's backend).
Run from the repo root:  streamlit run demo_app.py"""
import pandas as pd
import streamlit as st

from backend.customer_service import build_customer_summary
from backend.data_loader import load_data
from backend.recovery_planner import build_recovery_plan
from backend.shock_service import simulate_customer_shock
from backend.twist_parser import parse_twist

st.set_page_config(page_title="AFTERSHOCK", layout="wide")


@st.cache_data
def _load():
    return load_data()


monthly, loans = _load()
ids = sorted(monthly["account_id"].unique())

DEFAULTS = {"inc": 55, "dur": 6, "bills": 0, "k": 0.0, "oneoff": 0, "extra": 0}
for key, v in DEFAULTS.items():
    st.session_state.setdefault(key, v)

with st.sidebar:
    acct = st.number_input("account_id", int(min(ids)), int(max(ids)), int(ids[0]), 1)
    card = st.text_area("Judge's twist card", height=100,
                        placeholder="They lose their job (EI at 55%) and household bills go up 15%...")
    if st.button("Read twist", type="primary") and card.strip():
        p, how = parse_twist(card)
        st.session_state.update(inc=int(round(p["income_factor"] * 100)), dur=int(p["duration_months"] or 0),
                                bills=int(round(p["household_bills_up_pct"] * 100)),
                                k=float(p["one_off_months_of_spending"]), oneoff=int(p["one_off_cost"]),
                                extra=int(p["extra_monthly_spending"]), parsed_by=how)
    if st.session_state.get("parsed_by"):
        st.caption(f"Read by {st.session_state['parsed_by']}. Check the values below.")
    inc = st.slider("Income kept % (EI = 55)", 0, 100, step=5, key="inc")
    dur = st.number_input("Shock lasts (months, 0 = not stated)", 0, 120, key="dur")
    bills = st.slider("Household bills up %", 0, 100, step=5, key="bills")
    k = st.slider("One-off (months of typical spending)", 0.0, 6.0, step=0.25, key="k")
    oneoff = st.number_input("One-off ($)", 0, 1_000_000, step=100, key="oneoff")
    extra = st.number_input("Extra monthly spending ($)", 0, 100_000, step=50, key="extra")
    fund_m = st.slider("Emergency fund target (months)", 1, 12, 3)

if acct not in set(ids):
    st.error(f"account_id {acct} not found"); st.stop()

c = build_customer_summary(int(acct), monthly, loans)
sim = simulate_customer_shock(int(acct), monthly, loans, income_replacement_pct=inc,
                              household_bills_increase_pct=bills, one_off_cost=oneoff,
                              extra_monthly_spending=extra, projection_months=max(12, (dur or 6) + 6),
                              one_off_months_of_spending=k, duration_months=dur or None)
plan = build_recovery_plan(c, sim, emergency_fund_months=fund_m, survival_target_months=dur or 6)
a, b = sim["after_shock"], sim["before_shock"]

st.title("AFTERSHOCK · Financial Resilience Engine")
st.subheader(f"1 · Know the customer: account {c['account_id']}")
m = st.columns(6)
m[0].metric("Money in (I)", f"${c['income']:,.0f}")
m[1].metric("Spending (S)", f"${c['spending']:,.0f}")
m[2].metric("Fixed costs (F)", f"${c['fixed_costs']:,.0f}")
m[3].metric("Buffer (B)", f"${c['buffer']:,.0f}")
m[4].metric("Loan payment (P)", f"${c['loan_payment']:,.0f}")
m[5].metric("Runway today", b["runway_display"])
st.caption(f"{c['months_of_data']} months of data ({c['first_month']} → {c['last_month']}) · "
           f"{c['months_below_zero']} months went below zero")

st.subheader("2 · Take a shock")
m = st.columns(4)
m[0].metric("Income after", f"${a['income']:,.0f}", f"{a['income'] - b['income']:,.0f}")
m[1].metric("Spending after", f"${a['spending']:,.0f}", f"{a['spending'] - b['spending']:,.0f}", delta_color="inverse")
m[2].metric("Buffer after one-offs", f"${a['buffer_left']:,.0f}")
m[3].metric("RUNWAY", a["runway_display"])
(st.success if a["survives_target"] else st.error)(a["verdict"])
fc = pd.DataFrame(sim["forecast"]).set_index("month")[["baseline_balance", "shock_balance"]]
st.line_chart(fc, height=240)

st.subheader("3 · Make a plan")
l, r = st.columns(2)
ef = plan["emergency_fund"]
with l:
    st.markdown("**Goal: emergency fund**")
    st.write(f"Target ${ef['target_amount']:,.0f} ({ef['target_months']} months of spending). "
             f"Still needed ${ef['amount_still_needed']:,.0f}.")
    if ef["amount_still_needed"] > 0:
        st.write(f"Save ${ef['monthly_savings_needed']:,.0f}/month for {ef['savings_build_months']} months"
                 + ("" if ef["feasible_from_current_surplus"] else
                    f" (more than their ${ef['estimated_monthly_surplus']:,.0f}/month surplus; "
                    f"at current surplus: {ef['months_to_goal_at_current_surplus'] or 'never'} months)."))
with r:
    st.markdown("**Backup: if the shock hits**")
    for s in plan["backup_plan"]["actions"]:
        st.write("• " + s)

with st.expander("Show the math"):
    st.code(f"buffer_left = {b['buffer']:,.2f} - {sim['shock_inputs']['one_off_cost']:,.2f} = {a['buffer_left']:,.2f}\n"
            f"gap = {a['spending']:,.2f} - {a['income']:,.2f} = {a['monthly_gap']:,.2f}\n"
            f"runway = {a['runway_display']}")
    st.dataframe(pd.Series(c["spending_breakdown"], name="median $/month"))
