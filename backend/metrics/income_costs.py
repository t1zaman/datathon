def calculate_income(history):
    if history.empty:
        raise ValueError("No monthly history available")

    income = history["money_in"].median()

    return float(income)


def calculate_fixed_costs(history):
    if history.empty:
        raise ValueError("No monthly history available")

    monthly_fixed_costs = (
        history["household_bills"]
        + history["insurance"]
        + history["loan_payments"]
    )

    fixed_costs = monthly_fixed_costs.median()

    return float(fixed_costs)