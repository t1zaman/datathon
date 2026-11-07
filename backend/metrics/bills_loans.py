
def calculate_household_bills(history):
    # Calculate median monthly household bills
    household_bills = history["household_bills"].median()

    return float(household_bills)


def calculate_loan_payment(account_loans):
    # Return 0 if the account has no loans
    if account_loans.empty:
        return 0.0

    # C = running, OK
    # D = running, in debt
    # A and B = finished
    active_loans = account_loans[
        account_loans["status"].isin(["C", "D"])
    ]

    # Return 0 if there are no active loans
    if active_loans.empty:
        return 0.0

    # Calculate the monthly payment for active loans
    payment = active_loans["monthly_payment"].sum()

    return float(payment)
