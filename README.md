# Squirrel Away · The Insight Job
Squirrel Away (with Hazel, the squirrel coach), a winterproofing coach (financial resilience engine) for the Tangerine track, Sheridan Datathon 2026.

## Findings
See [FINDINGS.md](FINDINGS.md) and the charts in `docs/`.

## Run
```
pip install -r requirements.txt
# put the track's CSVs in data/
uvicorn backend.main:app --port 8000   # then open http://127.0.0.1:8000/app  (API docs: /docs)
streamlit run demo_app.py            # backup demo screen if the frontend has issues
python -m tests.test_consistency     # confirms runway matches the judges' formula on every account
cd analysis && python checks.py ../data && python findings.py ../data   # data checks + findings -> analysis/outputs/
```

## Frontend
`frontend/index.html`: one file, no build step, served by the API at `/app`. Paste the judge's twist card, press Enter, and runway, verdict, chart and plans update.

## AI: Ask Hazel (Gemini)
Chat coach about the loaded customer, in any language. **Gemini interprets, the engine computes:**
Gemini decides whether a question needs a what-if (e.g. "cut card spending in half"), the engine runs it with the
same formulas the judges use, then Gemini explains the real result. The LLM never invents a number.
Without a key, a rule-based reader handles the same questions, so the demo never breaks.
```
export GEMINI_API_KEY=your_key      # free key: https://aistudio.google.com/apikey
```
The same key powers the twist-card reader (`/api/twist/parse`).

## API
- `GET  /api/accounts/{id}/summary`: I, F, S, B, H, P, plus the spending breakdown
- `POST /api/accounts/{id}/simulate`: shock: `income_replacement_pct`, `household_bills_increase_pct`, `one_off_cost`, `one_off_months_of_spending`, `extra_monthly_spending`, `duration_months`
- `POST /api/accounts/{id}/recovery`: emergency-fund goal plus a backup plan based on the customer's own discretionary spending
- `GET  /api/accounts/random`: random account (dice button)
- `POST /api/accounts/{id}/chat` `{"message", "history", "shock"}`: Ask Hazel
- `POST /api/twist/parse` `{"text": "..."}`: turns a judge's twist card into a `simulate` body (uses Gemini if `GEMINI_API_KEY` is set)

## Data credits
- PKDD'99 Discovery Challenge Financial dataset, CTU Prague Relational Dataset Repository: https://relational.fel.cvut.cz/dataset/Financial
- EI regular benefits: https://www.canada.ca/en/services/benefits/ei/ei-regular-benefit.html
