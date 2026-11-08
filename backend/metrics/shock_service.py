
from backend.data_loader import load_data
from backend.customer_service import build_customer_summary
from backend.shock_simulator import simulate_shock


def simulate_customer_shock(
    account_id,
    monthly,
    loans,
    income_replacement_pct=100,
    household_bills_increase_pct=0,
    one_off_cost=0,
    extra_monthly_spending=0,
    projection_months=6
):
    # Get the customer's financial information
    customer = build_customer_summary(
        account_id, monthly, loans
    )

    # Run the financial shock simulation
    result = simulate_shock(
        customer,
        income_replacement_pct=income_replacement_pct,
        household_bills_increase_pct=household_bills_increase_pct,
        one_off_cost=one_off_cost,
        extra_monthly_spending=extra_monthly_spending,
        projection_months=projection_months
    )

    return result


# Format numbers for display
def format_value(key, value):

    if key == "runway_months":
        if value is None:
            return "120+ months (no shortfall)"
        return f"{value:.1f} months"

    if isinstance(value, bool):
        return str(value)

    if isinstance(value, (int, float)):
        return f"${value:,.2f}"

    return str(value)


if __name__ == "__main__":

    # Load datasets
    monthly, loans = load_data()

    # Choose an account
    account_id = 20134

    # Simulate financial shocks
    result = simulate_customer_shock(
        account_id,
        monthly,
        loans,
        income_replacement_pct=55,
        household_bills_increase_pct=15,
        one_off_cost=2000
    )

    print("\nFINANCIAL SHOCK SIMULATION")
    print("Account:", result["account_id"])

    # Before shock
    print("\nBEFORE SHOCK")

    for key, value in result["before_shock"].items():
        print(f"{key}: {format_value(key, value)}")

    # After shock
    print("\nAFTER SHOCK")

    for key, value in result["after_shock"].items():
        print(f"{key}: {format_value(key, value)}")

    # Financial forecast
    print("\nFINANCIAL FORECAST")

    for month in result["forecast"]:
        print(
            f"Month {month['month']}: "
            f"Baseline = ${month['baseline_balance']:,.2f} | "
            f"After Shock = ${month['shock_balance']:,.2f}"
        )

    print("\nSimulation completed successfully!")
