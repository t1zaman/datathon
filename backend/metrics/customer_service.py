
# Import the six financial calculations
from backend.metrics.income_costs import (
    calculate_income,
    calculate_fixed_costs
)

from backend.metrics.spending_buffer import (
    calculate_spending,
    calculate_buffer
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

    # Calculate and combine all six metrics
    return {
        "account_id": int(account_id),
        "income": calculate_income(history),
        "fixed_costs": calculate_fixed_costs(history),
        "spending": calculate_spending(history),
        "buffer": calculate_buffer(history),
        "household_bills": calculate_household_bills(history),
        "loan_payment": calculate_loan_payment(account_loans)
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
