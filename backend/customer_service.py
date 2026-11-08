
# Import the six financial calculations
from backend.metrics.income_costs import (
    calculate_income,
    calculate_fixed_costs
)

from backend.metrics.spending_buffer import (
    calculate_spending,
    calculate_buffer,
    calculate_discretionary,
    calculate_spending_breakdown
)

from backend.metrics.bills_loans import (
    calculate_household_bills,
    calculate_loan_payment
)


def build_customer_summary(account_id, monthly, loans):
    # Find the account's monthly financial records
    history = monthly[
        monthly["account_id"] == account_id
    ]

    # Check if the account exists
    if history.empty:
        raise ValueError(f"Account {account_id} not found")

    # Find loans belonging to this account
    account_loans = loans[
        loans["account_id"] == account_id
    ]

    # Early-warning signals (our Discovery finding, see analysis/findings.py):
    # in this bank's data, every customer whose balance went below $0 in the months
    # before taking a loan later defaulted (27 of 27, vs 7.5% of everyone else),
    # and the most volatile incomes defaulted 5.6x as often as the steadiest.
    money_in = history["money_in"]
    income_cv = float(money_in.std() / money_in.mean()) if money_in.mean() > 0 else None
    total_in = float(money_in.sum()) or 1.0
    pension_share = float(history["pension_in"].sum()) / total_in if "pension_in" in history.columns else 0.0
    cash_share = float(history["cash_deposits"].sum()) / total_in if "cash_deposits" in history.columns else 0.0
    below_zero = history[history["days_below_zero"] > 0] if "days_below_zero" in history.columns else history.iloc[0:0]
    warnings = []
    if len(below_zero):
        warnings.append({
            "level": "high",
            "title": f"Balance went below $0 in {len(below_zero)} month(s), most recently {below_zero['month'].max()}",
            "why": "In this bank's data, all 27 customers who dipped below $0 before taking a loan later defaulted "
                   "(vs 7.5% of everyone else).",
        })
    if income_cv is not None and income_cv >= 0.84:  # top quartile of pre-loan income volatility
        warnings.append({
            "level": "medium",
            "title": f"Very uneven income: top 25% for month-to-month swings ({income_cv:.0%})",
            "why": "Customers with the most volatile income defaulted 5.6x as often as the steadiest (22.8% vs 4.1%). "
                   "Their typical (median) month can look safer than reality.",
        })

    # Calculate and combine all six metrics
    return {
        "account_id": int(account_id),
        "income": calculate_income(history),
        "fixed_costs": calculate_fixed_costs(history),
        "spending": calculate_spending(history),
        "buffer": calculate_buffer(history),
        "household_bills": calculate_household_bills(history),
        "loan_payment": calculate_loan_payment(account_loans),
        # Extra context (not part of the judges' six numbers)
        "discretionary_spending": calculate_discretionary(history),
        "spending_breakdown": calculate_spending_breakdown(history),
        "months_of_data": int(len(history)),
        "first_month": str(history["month"].min()),
        "last_month": str(history["month"].max()),
        "months_below_zero": int((history["days_below_zero"] > 0).sum())
        if "days_below_zero" in history.columns else None,
        "income_volatility": income_cv,
        "income_type": "pension" if pension_share > 0.3 else ("mostly cash" if cash_share > 0.5 else "transfers (salary-like)"),
        "warnings": warnings
    }


# Run this section only when testing directly
if __name__ == "__main__":
    from backend.data_loader import load_data

    # Load real datasets
    monthly, loans = load_data()

    # Test a customer
    account_id = 20134

    customer = build_customer_summary(
        account_id,
        monthly,
        loans
    )

    print("\nCUSTOMER FINANCIAL SUMMARY")

    for metric, value in customer.items():
        print(f"{metric}: {value}")
