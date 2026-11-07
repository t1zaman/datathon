
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
