"""Builds the data behind the Insights tab from the CSVs at request time,
so no account-level data has to live in the repo."""
import pandas as pd

OUTFLOW_COLS = ["household_bills", "insurance", "loan_payments", "bank_fees",
                "cash_withdrawals_genuine", "card_withdrawals", "transfers_out_other"]


def build_insights_data(monthly: pd.DataFrame, loans: pd.DataFrame) -> dict:
    m = monthly.sort_values(["account_id", "month"])
    g = m.groupby("account_id")
    fixed = m["household_bills"] + m["insurance"] + m["loan_payments"]
    prof = pd.DataFrame({
        "I": g["money_in"].median(),
        "S": g["money_out"].median(),
        "F": fixed.groupby(m["account_id"]).median(),
        "H": g["household_bills"].median(),
        "B": g.tail(6).groupby("account_id")["avg_daily_balance"].mean(),
        "negative": g["min_balance"].min() < 0,
        "months": g.size(),
        "last": g["month"].max(),
    })
    running = set(loans.loc[loans["status"].isin(["C", "D"]), "account_id"])
    prof["loan"] = prof.index.isin(running)
    prof["quartile"] = pd.qcut(prof["I"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
    tot = m[OUTFLOW_COLS].sum()
    shares = (tot / tot.sum() * 100).round(4).tolist()
    fields = ["I", "S", "F", "H", "B", "loan", "negative", "quartile", "months", "last"]
    rows = [[str(i)] + [r[f].item() if hasattr(r[f], "item") else r[f] for f in fields]
            for i, r in prof[fields].iterrows()]
    return {
        "fields": ["id"] + fields,
        "accounts": rows,
        "outflowShares": shares,
        "latest": str(m["month"].max()),
        "metadata": {"accounts": len(prof), "monthlyRows": len(m), "loanRows": len(loans),
                     "historyEndsBeforeLatest": int((prof["last"] < m["month"].max()).sum()),
                     "minMonths": int(prof["months"].min()), "maxMonths": int(prof["months"].max())},
    }
