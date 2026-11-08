
def calculate_spending(history):
    # Calculate median monthly spending
    spending = history["money_out"].median()

    return float(spending)


def calculate_buffer(history):
    # Sort account history by month
    sorted_history = history.sort_values("month")

    # Select the last 6 months
    last_six = sorted_history.tail(6)

    # Calculate average daily balance
    buffer = last_six["avg_daily_balance"].mean()

    return float(buffer)


# Spending the customer can realistically adjust in a crisis
DISCRETIONARY_COLUMNS = [
    "card_withdrawals",
    "cash_withdrawals_genuine",
    "transfers_out_other"
]

ESSENTIAL_COLUMNS = [
    "household_bills",
    "insurance",
    "loan_payments",
    "bank_fees"
]


def calculate_discretionary(history):
    # Median monthly card + cash withdrawals + unlabelled transfers out
    columns = [c for c in DISCRETIONARY_COLUMNS if c in history.columns]
    if not columns:
        return 0.0
    return float(history[columns].sum(axis=1).median())


def calculate_spending_breakdown(history):
    # Median of every money_out component, for the "where does the money go" view
    columns = [
        c for c in ESSENTIAL_COLUMNS + DISCRETIONARY_COLUMNS
        if c in history.columns
    ]
    return {c: float(history[c].median()) for c in columns}
