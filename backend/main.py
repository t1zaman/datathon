
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.data_loader import load_data
from backend.customer_service import build_customer_summary
from backend.shock_service import simulate_customer_shock


# Create the API
app = FastAPI(
    title="AFTERSHOCK API",
    description="Financial Resilience Simulator",
    version="1.0"
)

# Load the datasets once when the server starts
monthly, loans = load_data()


# Information React sends when applying a shock
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


# Check whether the API is running
@app.get("/")
def home():
    return {
        "message": "AFTERSHOCK API is running"
    }


# Get all six financial metrics for an account
@app.get("/api/accounts/{account_id}/summary")
def get_customer_summary(account_id: int):

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


# Simulate a financial shock for an account
@app.post("/api/accounts/{account_id}/simulate")
def simulate_customer(account_id: int, shock: ShockRequest):

    try:
        result = simulate_customer_shock(
            account_id=account_id,
            monthly=monthly,
            loans=loans,
            income_replacement_pct=shock.income_replacement_pct,
            household_bills_increase_pct=shock.household_bills_increase_pct,
            one_off_cost=shock.one_off_cost,
            extra_monthly_spending=shock.extra_monthly_spending,
            projection_months=shock.projection_months
        )

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=404
            if "not found" in str(error).lower()
            else 400,
            detail=str(error)
        ) from error
