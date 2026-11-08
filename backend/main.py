
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import random
from pydantic import BaseModel, Field

from backend.data_loader import load_data
from backend.customer_service import build_customer_summary
from backend.shock_service import simulate_customer_shock
from backend.recovery_planner import build_recovery_plan
from backend.twist_parser import parse_twist
from backend.chat import chat as hazel_chat
from backend.insights_data import build_insights_data


# Create the FastAPI application
app = FastAPI(
    title="Squirrel Away API",
    description="Financial Resilience Simulator",
    version="1.0"
)


# Let a separate frontend (e.g. localhost:3000 / 5173) call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
    # "repair costs a full month of typical spending" -> 1.0
    one_off_months_of_spending: float = Field(
        default=0, ge=0
    )
    # "EI for 6 months" -> 6 (sets the make-it / don't-make-it target)
    duration_months: int | None = Field(
        default=None, ge=1, le=120
    )
    # What-if only (chat / plan testing): reduce monthly spending by this many $
    spending_cut_monthly: float = Field(
        default=0, ge=0
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
            projection_months=shock.projection_months,
            one_off_months_of_spending=shock.one_off_months_of_spending,
            duration_months=shock.duration_months,
            spending_cut_monthly=shock.spending_cut_monthly
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
        "message": "Squirrel Away API is running. Open /app"
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


# Live twist: turn the judge's twist card into shock settings
class TwistRequest(BaseModel):
    text: str


@app.post("/api/twist/parse")
def parse_twist_card(request: TwistRequest):
    params, parsed_by = parse_twist(request.text)
    return {
        "parsed_by": parsed_by,
        # Same field names as ShockRequest, so the frontend can send it straight to /simulate
        "shock": {
            "income_replacement_pct": round(params["income_factor"] * 100, 2),
            "household_bills_increase_pct": round(params["household_bills_up_pct"] * 100, 2),
            "one_off_cost": params["one_off_cost"],
            "one_off_months_of_spending": params["one_off_months_of_spending"],
            "extra_monthly_spending": params["extra_monthly_spending"],
            "duration_months": params["duration_months"],
        },
    }


# Random account for the demo's dice button
@app.get("/api/accounts/random")
def random_account():
    return {"account_id": int(random.choice(monthly["account_id"].unique()))}


# Frontend: open http://127.0.0.1:8000/app
FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "index.html"


app.mount("/assets", StaticFiles(directory=FRONTEND.parent / "assets"), name="assets")


@app.get("/app", include_in_schema=False)
def frontend():
    return FileResponse(FRONTEND)


# Insights tab: page + the per-account profiles it charts (computed from the CSVs, never stored in the repo)
_insights_cache = {}


@app.get("/api/insights/data")
def insights_data():
    if "data" not in _insights_cache:
        _insights_cache["data"] = build_insights_data(monthly, loans)
    return _insights_cache["data"]


@app.get("/insights", include_in_schema=False)
def insights_page():
    return FileResponse(FRONTEND.parent / "insights.html")


# Ask Hazel: chat coach. Gemini interprets, the engine computes (see backend/chat.py)
class ChatTurn(BaseModel):
    role: str = "user"
    text: str = ""


class ChatRequest(BaseModel):
    message: str
    history: list[ChatTurn] = []
    shock: RecoveryRequest = RecoveryRequest()


@app.post("/api/accounts/{account_id}/chat")
def ask_hazel(account_id: int, request: ChatRequest):
    customer = get_summary_or_error(account_id)
    simulation = get_simulation_or_error(account_id, request.shock)
    plan = build_recovery_plan(customer, simulation,
                               emergency_fund_months=request.shock.emergency_fund_months,
                               survival_target_months=request.shock.survival_target_months)

    def run_whatif(changes):
        merged = request.shock.model_dump()
        for key, value in changes.items():
            if key in merged:
                merged[key] = value
        try:
            what_if = RecoveryRequest(**merged)
        except Exception as error:
            raise HTTPException(status_code=400, detail=f"Invalid what-if: {error}") from error
        result = get_simulation_or_error(account_id, what_if)["after_shock"]
        return {
            "runway_display": result["runway_display"],
            "runway_months": result["runway_months"],
            "verdict": result["verdict"],
            "shock": what_if.model_dump(),
        }

    return hazel_chat(request.message, [t.model_dump() for t in request.history],
                      customer, simulation, plan, run_whatif)
