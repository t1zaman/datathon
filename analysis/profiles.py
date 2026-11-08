"""Vectorised version of backend/metrics for ALL accounts at once (used by findings.py).
Same definitions as the judges / backend; tests/test_consistency.py checks they agree."""
from pathlib import Path
import numpy as np
import pandas as pd

RUNWAY_CAP = 120
DISCRETIONARY_COLS = ["card_withdrawals", "cash_withdrawals_genuine", "transfers_out_other"]


def load_data(data_dir="data"):
    d = Path(data_dir)
    ms = pd.read_csv(d / "monthly_summary.csv")
    ms["month"] = ms["month"].astype(str)
    ms = ms.sort_values(["account_id", "month"]).reset_index(drop=True)
    return ms, pd.read_csv(d / "loans.csv")


def build_all_profiles(ms: pd.DataFrame, loans: pd.DataFrame) -> pd.DataFrame:
    """Vectorised version for all 4,500 accounts (used by the analysis + fast app lookups)."""
    g = ms.groupby("account_id")
    df = pd.DataFrame({
        "I": g["money_in"].median(),
        "S": g["money_out"].median(),
        "H": g["household_bills"].median(),
        "B": g["avg_daily_balance"].apply(lambda s: s.tail(6).mean()),
        "months_of_data": g.size(),
        "months_negative": g["days_below_zero"].apply(lambda s: int((s > 0).sum())),
        "total_bank_fees": g["bank_fees"].sum(),
    })
    fixed = ms["household_bills"] + ms["insurance"] + ms["loan_payments"]
    df["F"] = fixed.groupby(ms["account_id"]).median()
    disc = ms[[c for c in DISCRETIONARY_COLS if c in ms.columns]].sum(axis=1)
    df["discretionary"] = disc.groupby(ms["account_id"]).median()
    l = loans.set_index("account_id")
    df["loan_status"] = l["status"].reindex(df.index)
    df["defaulted"] = l["defaulted"].reindex(df.index)
    df["P"] = np.where(df["loan_status"].isin(["C", "D"]),
                       l["monthly_payment"].reindex(df.index), 0.0)
    return df.reset_index()


