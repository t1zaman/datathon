
"""Financial Shock Simulator for AFTERSHOCK."""

import math


def _number(value, name):
    # Check that the value is a valid number
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc

    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")

    return result


def _runway(buffer_left, income, spending):
    # Calculate monthly financial shortfall
    gap = spending - income

    # Follow the judges' runway formula
    if buffer_left <= 0:
        return 0.0, "0.0 months"

    if gap <= 0:
        return None, "No shortfall (120+)"

    months = round(min(buffer_left / gap, 120), 1)

    return months, f"{months:.1f} months"


def simulate_shock(
    customer,
    income_replacement_pct=100,
    household_bills_increase_pct=0,
    one_off_cost=0,
    extra_monthly_spending=0,
    projection_months=6,
    one_off_months_of_spending=0,
    duration_months=None,
    spending_cut_monthly=0,
):
    # Check required customer information
    required = (
        "account_id",
        "income",
        "spending",
        "buffer",
        "household_bills"
    )

    missing = [
        key for key in required
        if key not in customer
    ]

    if missing:
        raise ValueError(
            f"Customer summary is missing: {', '.join(missing)}"
        )

    # Get financial information from customer summary
    income = _number(customer["income"], "income")
    spending = _number(customer["spending"], "spending")
    buffer = _number(customer["buffer"], "buffer")
    household_bills = _number(
        customer["household_bills"], "household_bills"
    )

    # Get shock values
    replacement = _number(
        income_replacement_pct, "income_replacement_pct"
    )

    bills_increase = _number(
        household_bills_increase_pct,
        "household_bills_increase_pct"
    )

    one_off_k = _number(one_off_months_of_spending, "one_off_months_of_spending")
    if one_off_k < 0:
        raise ValueError("one_off_months_of_spending cannot be negative")
    # Twist cards often size one-offs as "a full month of typical spending" -> k x S
    one_off = _number(one_off_cost, "one_off_cost") + one_off_k * spending

    extra_monthly = _number(
        extra_monthly_spending, "extra_monthly_spending"
    )

    # Validate inputs
    if any(
        value < 0
        for value in (income, spending, household_bills)
    ):
        raise ValueError(
            "Income, spending, and household bills cannot be negative"
        )

    if not 0 <= replacement <= 100:
        raise ValueError(
            "income_replacement_pct must be between 0 and 100"
        )

    if bills_increase < 0 or one_off < 0 or extra_monthly < 0:
        raise ValueError(
            "Bill increases and costs cannot be negative"
        )

    if (
        not isinstance(projection_months, int)
        or not 1 <= projection_months <= 120
    ):
        raise ValueError(
            "projection_months must be an integer from 1 to 120"
        )

    # Calculate income after the shock
    # Example: EI replaces 55% of normal income
    income_after = income * (replacement / 100)

    # Optional what-if: a monthly spending cut (used by the plan / chat, never by twist cards)
    cut = _number(spending_cut_monthly, "spending_cut_monthly")
    if cut < 0:
        raise ValueError("spending_cut_monthly cannot be negative")

    # Calculate spending after the shock
    # Household bills are already included in spending
    spending_after = max(0.0, (
        spending
        + household_bills * (bills_increase / 100)
        + extra_monthly
        - cut
    ))

    # Deduct one-time emergency expenses from buffer
    buffer_left = buffer - one_off

    # Calculate monthly shortfall
    monthly_gap = spending_after - income_after

    # Calculate runway before the shock
    original_runway, original_display = _runway(
        buffer, income, spending
    )

    # Calculate runway after the shock
    runway, runway_display = _runway(
        buffer_left, income_after, spending_after
    )

    # Check if customer can survive six months
    # Use unrounded values for accuracy
    survives_six_months = (
        buffer_left > 0
        and (
            monthly_gap <= 0
            or buffer_left >= 6 * monthly_gap
        )
    )

    # Verdict for the live twist ("EI for 6 months. Do they make it?")
    target = int(duration_months) if duration_months else 6
    survives_target = buffer_left > 0 and (
        monthly_gap <= 0 or buffer_left >= target * monthly_gap
    )
    if buffer <= 0:
        verdict = (f"No savings to fall back on: their buffer is already −${abs(buffer):,.0f}, "
                   f"so runway is 0 before any shock.")
    elif buffer_left <= 0:
        verdict = (f"Can't absorb it: the one-off cost (${one_off:,.0f}) is bigger "
                   f"than the buffer (${buffer:,.0f}).")
    elif monthly_gap <= 0:
        verdict = "Makes it: income still covers spending, the buffer is never touched."
    elif not duration_months:
        verdict = (f"Buffer lasts {runway:.1f} months at a ${monthly_gap:,.0f}/month shortfall"
                   + (" (meets the 6-month safety line)." if survives_target
                      else " (below the 6-month safety line)."))
    elif survives_target:
        verdict = (f"Makes it: {runway:.1f} months of runway vs a {target}-month shock "
                   f"(${buffer_left - target * monthly_gap:,.0f} left at the end).")
    else:
        verdict = (f"Doesn't make it: runs out after {runway:.1f} months, "
                   f"{target - buffer_left / monthly_gap:.1f} months short "
                   f"(needs ${target * monthly_gap - buffer_left:,.0f} more).")

    # Generate projected balances for graphs
    forecast = []

    for month in range(projection_months + 1):
        forecast.append({
            "month": month,

            "baseline_balance": (
                buffer + month * (income - spending)
            ),

            "shock_balance": (
                buffer_left
                + month * (income_after - spending_after)
            )
        })

    # Return results for the website
    return {
        "account_id": int(customer["account_id"]),

        "before_shock": {
            "income": income,
            "spending": spending,
            "buffer": buffer,
            "runway_months": original_runway,
            "runway_display": original_display
        },

        "shock_inputs": {
            "income_replacement_pct": replacement,
            "household_bills_increase_pct": bills_increase,
            "one_off_cost": one_off,
            "one_off_months_of_spending": one_off_k,
            "extra_monthly_spending": extra_monthly,
            "spending_cut_monthly": cut,
            "duration_months": duration_months
        },

        "after_shock": {
            "income": income_after,
            "spending": spending_after,
            "buffer_left": buffer_left,
            "monthly_gap": monthly_gap,
            "monthly_shortfall": max(monthly_gap, 0.0),
            "runway_months": runway,
            "runway_display": runway_display,
            "survives_six_months": survives_six_months,
            "target_months": target,
            "survives_target": survives_target,
            "verdict": verdict
        },

        "forecast": forecast
    }


if __name__ == "__main__":
    # Sample data for testing only
    sample_customer = {
        "account_id": 1,
        "income": 4000,
        "fixed_costs": 1200,
        "spending": 3000,
        "buffer": 5000,
        "household_bills": 1000,
        "loan_payment": 0
    }

    # Simulate job loss, higher bills, and emergency cost
    result = simulate_shock(
        sample_customer,
        income_replacement_pct=55,
        household_bills_increase_pct=15,
        one_off_cost=1000
    )

    print(
        "Income after shock:",
        result["after_shock"]["income"]
    )

    print(
        "Spending after shock:",
        result["after_shock"]["spending"]
    )

    print(
        "Buffer after shock:",
        result["after_shock"]["buffer_left"]
    )

    print(
        "Runway:",
        result["after_shock"]["runway_display"]
    )

    print(
        "Survives six months:",
        result["after_shock"]["survives_six_months"]
    )

    assert result["after_shock"]["runway_months"] == 4.2

    print("Example test passed!")
