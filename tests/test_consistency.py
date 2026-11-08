"""Checks the API's runway equals the judges' formula, and that analysis/profiles.py
(used for findings) gives the same numbers as backend/metrics. Run: python -m tests.test_consistency"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))
from backend.data_loader import load_data
from backend.customer_service import build_customer_summary
from backend.shock_service import simulate_customer_shock
from profiles import build_all_profiles


def judges_runway(B, I, S, H, inc=1.0, bills=0.0, one_off=0.0):
    buffer_left = B - one_off
    gap = (S + bills * H) - inc * I
    if buffer_left <= 0:
        return 0.0
    if gap <= 0:
        return None
    return round(min(buffer_left / gap, 120), 1)


monthly, loans = load_data()
monthly["month"] = monthly["month"].astype(str)
allp = build_all_profiles(monthly, loans).set_index("account_id")
bad = 0
ids = monthly["account_id"].unique()
for a in ids:
    c = build_customer_summary(a, monthly, loans)
    for k, col in [("income", "I"), ("spending", "S"), ("buffer", "B"), ("household_bills", "H"), ("loan_payment", "P")]:
        if abs(c[k] - allp.loc[a, col]) > 0.01:
            bad += 1; print("metric mismatch", a, k, c[k], allp.loc[a, col])
    for inc, bills, k in [(55, 0, 0), (100, 0, 1), (55, 15, 0)]:
        r = simulate_customer_shock(a, monthly, loans, income_replacement_pct=inc,
                                    household_bills_increase_pct=bills, one_off_months_of_spending=k)
        exp = judges_runway(c["buffer"], c["income"], c["spending"], c["household_bills"], inc / 100, bills / 100, k * c["spending"])
        if r["after_shock"]["runway_months"] != exp:
            bad += 1; print("runway mismatch", a, inc, bills, k, r["after_shock"]["runway_months"], exp)
print(f"checked {len(ids)} accounts x 3 twists: {bad} mismatches")
assert bad == 0
