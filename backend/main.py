
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.data_loader import load_data
from backend.customer_service import build_customer_summary
from backend.shock_service import simulate_customer_shock
from backend.recovery_planner import build_recovery_plan


# Create the FastAPI application
app = FastAPI(
    title="AFTERSHOCK API",
    description="Financial Resilience Simulator",
    version="1.0"
)


# Load datasets once when the server starts
monthly, loans = load_data()


# Request format for financial shock simulations
class ShockRequest(BaseModel):
    income_replacement_pct: float = Field(
        default=100, ge=0, le=100
    )
    household_bills_increase_pct: float = Field(
        default=0, ge=0
    )
    one_off_cost: float = Field(
        default=0, ge=0
    )
    extra_monthly_spending: float = Field(
        default=0, ge=0
    )
    projection_months: int = Field(
        default=6, ge=1, le=120
    )


# Request format for personalized recovery planning
class RecoveryRequest(ShockRequest):
    emergency_fund_months: int = Field(
        default=3, ge=1, le=36
    )
    savings_build_months: int = Field(
        default=12, ge=1, le=120
    )
    survival_target_months: int = Field(
        default=6, ge=1, le=120
    )


# Get customer summary and handle errors
def get_summary_or_error(account_id):
    try:
        return build_customer_summary(
            account_id,
            monthly,
            loans
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404
            if "not found" in str(error).lower()
            else 400,
            detail=str(error)
        ) from error


# Run shock simulation and handle errors
def get_simulation_or_error(account_id, shock):
    try:
        return simulate_customer_shock(
            account_id=account_id,
            monthly=monthly,
            loans=loans,
            income_replacement_pct=shock.income_replacement_pct,
            household_bills_increase_pct=shock.household_bills_increase_pct,
            one_off_cost=shock.one_off_cost,
            extra_monthly_spending=shock.extra_monthly_spending,
            projection_months=shock.projection_months
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404
            if "not found" in str(error).lower()
            else 400,
            detail=str(error)
        ) from error


# Check whether the API is running
@app.get("/")
def home():
    return {
        "message": "AFTERSHOCK API is running"
    }


# Feature 1: Customer financial overview
@app.get("/api/accounts/{account_id}/summary")
def get_customer_summary(account_id: int):
    return get_summary_or_error(account_id)


# Feature 2: Financial shock simulator
@app.post("/api/accounts/{account_id}/simulate")
def simulate_customer(account_id: int, shock: ShockRequest):
    return get_simulation_or_error(account_id, shock)


# Feature 3: Personalized recovery planner
@app.post("/api/accounts/{account_id}/recovery")
def get_customer_recovery_plan(
    account_id: int,
    request: RecoveryRequest
):
    # Get actual customer financial information
    customer = get_summary_or_error(account_id)

    # Calculate the financial shock
    simulation = get_simulation_or_error(
        account_id,
        request
    )

    # Generate personalized savings and recovery plans
    try:
        return build_recovery_plan(
            customer,
            simulation,
            emergency_fund_months=request.emergency_fund_months,
            savings_build_months=request.savings_build_months,
            survival_target_months=request.survival_target_months
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        ) from error
