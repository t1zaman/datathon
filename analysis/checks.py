"""Data-quality checks (Data Use = 25%). Run: python checks.py data
Everything printed here is something to mention honestly in the write-up / Q&A."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

d = Path(sys.argv[1] if len(sys.argv) > 1 else "data")
ms = pd.read_csv(d / "monthly_summary.csv")
loans = pd.read_csv(d / "loans.csv")
districts = pd.read_csv(d / "districts.csv")

print("=== SHAPE ===")
print(f"monthly_summary: {len(ms):,} rows, {ms.account_id.nunique():,} accounts, months {ms.month.min()} -> {ms.month.max()}")

print("\n=== DO THE PARTS ADD UP? ===")
in_parts = ["cash_deposits", "transfers_in", "pension_in", "interest_in"]
out_parts = ["household_bills", "insurance", "loan_payments", "bank_fees",
             "cash_withdrawals_genuine", "card_withdrawals", "transfers_out_other"]
din = (ms[in_parts].sum(axis=1) - ms.money_in).abs()
dout = (ms[out_parts].sum(axis=1) - ms.money_out).abs()
print(f"money_in parts mismatch >$1: {(din > 1).sum()} rows | money_out parts mismatch >$1: {(dout > 1).sum()} rows")

print("\n=== QUIET MONTHS (pull medians down) ===")
quiet_in = (ms.money_in == 0).mean(); quiet_all = ((ms.money_in == 0) & (ms.money_out == 0)).mean()
print(f"months with money_in = 0: {quiet_in:.1%} | fully quiet months: {quiet_all:.1%}")
g = ms.groupby("account_id")
I_all = g.money_in.median()
I_nz = ms[ms.money_in > 0].groupby("account_id").money_in.median()
diff = (I_nz.reindex(I_all.index) - I_all) / I_all.replace(0, np.nan)
print(f"accounts where ignoring quiet months raises I by >10%: {(diff > 0.10).mean():.1%}")
print(f"accounts with I = 0 (median income zero): {(I_all == 0).sum()}")

print("\n=== HISTORY LENGTH ===")
n = g.size()
print(n.describe().round(1).to_string())
print(f"accounts with < 6 months: {(n < 6).sum()} | < 12 months: {(n < 12).sum()}")

print("\n=== BUFFER ===")
B = g.avg_daily_balance.apply(lambda s: s.tail(6).mean())
print(f"accounts with B <= 0 (runway 0 instantly): {(B <= 0).sum()}")
last = g.month.max()
print(f"accounts whose last month is before 2025-12 (closed/dormant?): {(last < '2025-12').sum()}")

print("\n=== NEGATIVE BALANCES ===")
print(f"account-months with any day below zero: {(ms.days_below_zero > 0).mean():.2%}")
print(f"accounts ever below zero: {(g.days_below_zero.max() > 0).mean():.1%}")

print("\n=== LOANS ===")
print(loans.status.value_counts().sort_index().to_string())
print(f"default rate: {loans.defaulted.mean():.1%}")
chk = (loans.amount - loans.duration_months * loans.monthly_payment).abs()
print(f"loans where amount != duration x payment (>$1): {(chk > 1).sum()}")
ls = pd.to_datetime(loans.loan_start)
end = ls + pd.to_timedelta(loans.duration_months * 30.44, unit="D")
running_by_dates = end > "2025-12-31"
running_by_status = loans.status.isin(["C", "D"])
print(f"'running' by status C/D: {running_by_status.sum()} | by start+duration: {running_by_dates.sum()} | "
      f"disagree: {(running_by_status != running_by_dates).sum()}  <- ask mentor which they use")

print("\n=== DISTRICTS ===")
print(districts.isna().sum()[lambda s: s > 0].to_string() or "no missing values")
