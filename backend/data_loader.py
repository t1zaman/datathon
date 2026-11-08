
import pandas as pd
from pathlib import Path

# Locate the data folder
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def load_data():
    # Set dataset paths
    monthly_path = DATA_DIR / "monthly_summary.csv"
    loans_path = DATA_DIR / "loans.csv"

    # Check that both files exist
    if not monthly_path.exists():
        raise FileNotFoundError("monthly_summary.csv not found")

    if not loans_path.exists():
        raise FileNotFoundError("loans.csv not found")

    # Load datasets
    monthly = pd.read_csv(monthly_path)
    loans = pd.read_csv(loans_path)

    # Check required columns
    monthly_columns = [
        "account_id",
        "month",
        "money_in",
        "money_out",
        "household_bills",
        "insurance",
        "loan_payments",
        "avg_daily_balance"
    ]

    loan_columns = [
        "account_id",
        "status",
        "monthly_payment"
    ]

    for column in monthly_columns:
        if column not in monthly.columns:
            raise ValueError(f"Missing monthly column: {column}")

    for column in loan_columns:
        if column not in loans.columns:
            raise ValueError(f"Missing loan column: {column}")

    return monthly, loans


# Run this section when testing the file directly
if __name__ == "__main__":
    monthly, loans = load_data()

    print("Datasets loaded successfully!")
    print("Monthly records:", len(monthly))
    print("Unique accounts:", monthly["account_id"].nunique())
    print("Loan records:", len(loans))
