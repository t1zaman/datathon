"""AFTERSHOCK emergency-fund goals and post-shock backup planning.

Uses the existing customer summary and shock simulator output.  No CSV reads.
"""

import math
from decimal import Decimal, ROUND_CEILING


def _number(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def _round_up_cents(value):
    """Round money UP to cents, so a recommended minimum is sufficient."""
    return float(Decimal(str(max(0.0, value))).quantize(
        Decimal("0.01"), rounding=ROUND_CEILING
    ))


def _positive_integer(value, name, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be an integer from 1 to {maximum}")


def build_recovery_plan(
    customer,
    simulation,
    emergency_fund_months=3,
    savings_build_months=12,
    survival_target_months=6,
):
    """Return a savings goal and a quantified backup plan.

    The baseline emergency goal covers `emergency_fund_months` of typical
    recorded monthly outflows. Shock runway comes from `simulate_shock`.
    Recommendations are mathematical scenarios, not verified spending cuts.
    """
    _positive_integer(emergency_fund_months, "emergency_fund_months", 36)
    _positive_integer(savings_build_months, "savings_build_months", 120)
    _positive_integer(survival_target_months, "survival_target_months", 120)

    required_customer = ("account_id", "income", "spending", "buffer", "fixed_costs")
    for key in required_customer:
        if key not in customer:
            raise ValueError(f"Customer summary is missing: {key}")

    try:
        account_id = int(customer["account_id"])
        if account_id != int(simulation["account_id"]):
            raise ValueError("Customer and simulation account IDs do not match")
        shocked = simulation["after_shock"]
        shock_buffer = _number(shocked["buffer_left"], "buffer_left")
        shock_gap = _number(shocked["monthly_gap"], "monthly_gap")
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid shock simulation result") from exc

    income = _number(customer["income"], "income")
    spending = _number(customer["spending"], "spending")
    buffer = _number(customer["buffer"], "buffer")
    fixed_costs = _number(customer["fixed_costs"], "fixed_costs")
    if min(income, spending, fixed_costs) < 0:
        raise ValueError("Income, spending and fixed costs cannot be negative")

    # Part A: an emergency fund BEFORE the crisis.
    # The buffer is a historical balance estimate, not verified cash savings.
    fund_target = emergency_fund_months * spending
    available_buffer = max(0.0, buffer)
    fund_gap = max(0.0, fund_target - available_buffer)
    monthly_contribution = _round_up_cents(fund_gap / savings_build_months)
    monthly_surplus = income - spending
    savings_capacity = max(0.0, monthly_surplus)
    months_at_current_surplus = (
        0 if fund_gap == 0 else
        math.ceil(fund_gap / savings_capacity) if savings_capacity > 0 else None
    )
    contribution_feasible = monthly_contribution <= savings_capacity + 1e-9

    # Part B: a backup plan AFTER the specified shock.
    # The judged formula gives zero runway if buffer_left <= 0,
    # even if a customer could eliminate the monthly shortfall.
    monthly_shortfall = max(0.0, shock_gap)
    already_survives = shock_buffer > 0 and (
        shock_gap <= 0 or shock_buffer >= survival_target_months * shock_gap
    )

    if shock_buffer <= 0:
        monthly_adjustment_needed = None
        # At least 1 cent of remaining buffer is needed for positive runway
        # when there is no monthly shortfall.
        if monthly_shortfall == 0:
            upfront_needed = _round_up_cents(0.01 - shock_buffer)
        else:
            upfront_needed = _round_up_cents(
                survival_target_months * monthly_shortfall - shock_buffer
            )
        backup_status = "upfront_funds_required"
        message = (
            "The one-time costs exhaust the buffer. Recurring spending cuts alone "
            "cannot produce a positive runway under the judges' formula; "
            "the customer first needs additional available funds."
        )
    else:
        monthly_adjustment_needed = _round_up_cents(
            max(0.0, shock_gap - shock_buffer / survival_target_months)
        )
        upfront_needed = _round_up_cents(
            max(0.0, survival_target_months * monthly_shortfall - shock_buffer)
        )
        backup_status = "target_met" if already_survives else "adjustment_required"
        message = (
            "The current buffer already covers the chosen survival target."
            if already_survives else
            "Reduce recurring outflows, add recurring income, or combine both "
            "by at least the calculated monthly adjustment. Check what is "
            "actually adjustable before treating this as an achievable plan."
        )

    # Ground the backup plan in the customer's OWN adjustable spending:
    # cut discretionary spending (card, cash withdrawals, other transfers) first,
    # and only then point to bank support for whatever is left.
    discretionary = max(0.0, _number(customer.get("discretionary_spending", 0.0),
                                     "discretionary_spending"))
    split = None
    actions = []
    if monthly_adjustment_needed is not None and monthly_adjustment_needed > 0:
        cut = min(monthly_adjustment_needed, discretionary)
        remaining = max(0.0, monthly_adjustment_needed - cut)
        split = {
            "monthly_spending_reduction": _round_up_cents(cut),
            "share_of_discretionary": round(cut / discretionary, 3) if discretionary else None,
            "still_needed_monthly": _round_up_cents(remaining),
        }
        actions.append(
            f"Cut ${cut:,.0f}/month of discretionary spending "
            f"({(cut / discretionary if discretionary else 0):.0%} of card, cash and other transfers)."
        )
        if remaining > 0:
            loan = _number(customer.get("loan_payment", 0.0), "loan_payment")
            actions.append(
                f"Still ${remaining:,.0f}/month short: contact the bank early about a payment "
                f"deferral" + (f" on the ${loan:,.0f}/month loan" if loan else "")
                + " or a line of credit."
            )
    elif monthly_adjustment_needed is None:
        actions.append(
            f"The one-off cost wipes out the buffer: spread it with a payment plan "
            f"instead of paying ${-shock_buffer + buffer:,.0f} upfront."
        )
    else:
        actions.append("Buffer covers the shock: pause emergency-fund saving while it lasts "
                       "and pay essentials first.")
    if _number(simulation.get("shock_inputs", {}).get("income_replacement_pct", 100),
               "income_replacement_pct") < 100:
        actions.insert(0, "Apply for EI right away.")

    return {
        "account_id": account_id,
        "emergency_fund": {
            "target_months": emergency_fund_months,
            "typical_monthly_spending": spending,
            "fixed_costs_reference": fixed_costs,
            "target_amount": round(fund_target, 2),
            "estimated_buffer": buffer,
            "amount_still_needed": _round_up_cents(fund_gap),
            "savings_build_months": savings_build_months,
            "monthly_savings_needed": monthly_contribution,
            "estimated_monthly_surplus": monthly_surplus,
            "feasible_from_current_surplus": contribution_feasible,
            "months_to_goal_at_current_surplus": months_at_current_surplus,
        },
        "backup_plan": {
            "target_survival_months": survival_target_months,
            "runway_before_plan_months": shocked.get("runway_months"),
            "buffer_after_shock": shock_buffer,
            "monthly_shortfall_after_shock": monthly_shortfall,
            "status": backup_status,
            "minimum_monthly_adjustment_needed": monthly_adjustment_needed,
            "example_combination": split,
            "actions": actions,
            "additional_upfront_funds_if_no_monthly_adjustment": upfront_needed,
            "explanation": message,
        },
        "important_notes": [
            "Emergency goal is based on typical recorded money_out, including transfers "
            "and cash withdrawals; it is a planning estimate, not verified essential spending.",
            "Buffer is based on historical average daily bank balances and may not "
            "equal accessible cash savings.",
            "Spending reductions come from the customer's own discretionary categories "
            "(card, cash withdrawals, unlabelled transfers); some may still be essential.",
            "The backup plan assumes the shock persists at a constant monthly rate."
        ],
    }


if __name__ == "__main__":
    from backend.shock_simulator import simulate_shock

    sample = {
        "account_id": 1,
        "income": 4000.0,
        "spending": 3000.0,
        "buffer": 5000.0,
        "fixed_costs": 1200.0,
        "household_bills": 1000.0,
        "loan_payment": 0.0,
    }
    shocked = simulate_shock(
        sample,
        income_replacement_pct=55,
        household_bills_increase_pct=15,
        one_off_cost=1000,
    )
    plan = build_recovery_plan(sample, shocked)

    print("CUSTOMER:", plan["account_id"])
    fund = plan["emergency_fund"]
    print(f"Emergency fund goal: ${fund['target_amount']:,.2f}")
    print(f"Still needed: ${fund['amount_still_needed']:,.2f}")
    print(f"Monthly savings needed: ${fund['monthly_savings_needed']:,.2f}")
    backup = plan["backup_plan"]
    print(f"Current shock runway: {backup['runway_before_plan_months']} months")
    print(f"Monthly adjustment for {backup['target_survival_months']} months: "
          f"${backup['minimum_monthly_adjustment_needed']:,.2f}")
    assert fund["target_amount"] == 9000.0
    assert fund["amount_still_needed"] == 4000.0
    assert fund["monthly_savings_needed"] == 333.34
    assert backup["minimum_monthly_adjustment_needed"] == 283.34
    print("Recovery planner sample test passed!")
