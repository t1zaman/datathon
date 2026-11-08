# Findings: Squirrel Away (The Insight Job)
All numbers from the Tangerine track data (4,500 accounts, 682 loans). Reproduce with
`cd analysis && python checks.py ../data && python findings.py ../data && python headline_charts.py ../data`.

## Headline: big balances hide thin cushions
Splitting all 4,500 customers into quarters by typical money in (deposits and transfers, not salary):

| Income quarter | Median savings | Savings in months of own spending | Run out within 3 months on EI (55%) | One-month repair wipes out savings |
|---|---|---|---|---|
| Lowest | $13,850 | 8.4 | 2.3% | 1.2% |
| 2nd | $17,870 | 4.5 | 4.9% | 2.7% |
| 3rd | $26,958 | 2.6 | 12.4% | 3.7% |
| Highest | $34,775 | 1.9 | 20.7% | 8.4% |

The highest earners hold 2.5× the dollars but have less than a quarter of the cushion in months, and they are
9× more likely to run out on EI. It holds for every shock type, not just one formula. Running-loan customers show
the same pattern: bigger median buffers ($28,710 vs $21,606) but more vulnerable (19.87% vs 9.01% below 3 months
on EI). First surfaced in the team's insights dashboard (insights/insights.html).

## Second finding: the warning shows up before the loan
Every customer whose balance went below $0 in the months before taking a loan later defaulted: **27 of 27 (100%)**,
vs **49 of 655 (7.5%)** for everyone else.

- Not chance: Fisher exact p ≈ 1.6e-28.
- Not tiny fee overdrafts: median worst balance among the 27 was −$1,564.
- Still holds counting only dips ≥3 months before the loan (17 of 17) or only dips below −$100 (26 of 26).
- It catches 36% of all defaults (27 of 76), so it's a red flag, not a full credit model.
- 321 of the 454 customers who can't last 3 months on EI never went below $0, so the flag must be paired with the stress test.

**Second signal: uneven income.** Splitting loans into quarters by month-to-month income swings before the loan,
default rates were 4.1% / 4.7% / 12.9% / **22.8%**: the most uneven quarter defaults **5.6×** as often as the steadiest.
It holds among customers who never dipped below $0 (3.0% vs 15.9%). Together, the pre-loan signals predict
default with cross-validated AUC 0.77.

## Context: how resilient are customers?
- **1 in 3 customers (1,578 of 4,500) can't get through a 6-month layoff on EI** (55% income); median runway 8.6 months.
- **26% already spend more than they earn** in a typical month, with no shock at all.
- Income type matters: pension income → 99% survive; mostly-cash income (64% of customers) → 57%.
- **The fix is within reach:** for 97.5% of at-risk customers, the monthly cut needed to last 6 months is smaller
  than their flexible spending (median: 21% of it).

## Impact (next step for Tangerine)
- 212 customers without a loan have already dipped below $0, 122 of them in 2025. Before they apply for credit,
  reach out with a winter-stash plan, not a loan.
- Show the early-warning flag to advisors at loan time (built into the app: "Know the customer").

## Data checks and limits (Data Use)
- Parts add up to totals in every row; no account has < 12 months of history; 23 accounts start with a buffer ≤ $0;
  14 accounts have median income $0; 76 accounts stop before 2025-12; district 69 is missing 2022 unemployment and crime values.
- "Loan running at end of 2025" by status C/D and by start date + duration agree on all 448 loans.
- The source is the PKDD'99 Czech bank dataset with dates shifted to 2020–2025 and amounts in CAD, so it isn't real Canadian customers.
- Runway assumes a constant monthly gap. "EI = 55%" ignores the weekly maximum.
  "Flexible spending" includes cash withdrawals, some of which may be essential.
- The 100% result is based on 27 customers: strong evidence of a red flag, but correlation, not causation.
