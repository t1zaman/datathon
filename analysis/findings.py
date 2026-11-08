"""Discovery (35%): test all six candidate findings across every account and save a chart for each.
Run:  python findings.py data     -> prints results, writes outputs/*.csv and outputs/*.png
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from profiles import RUNWAY_CAP, build_all_profiles, load_data

d = Path(sys.argv[1] if len(sys.argv) > 1 else "data")
OUT = Path("outputs"); OUT.mkdir(exist_ok=True)
ms, loans = load_data(d)
accounts = pd.read_csv(d / "accounts.csv")
districts = pd.read_csv(d / "districts.csv")

ORANGE, GREY, DARK = "#F28C28", "#B8B8B8", "#333333"   # Tangerine-ish orange accent
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "font.size": 11,
                     "axes.titleweight": "bold", "axes.titlesize": 13})


def rw(B, gap, one_off=0.0):
    B, gap = np.asarray(B, float), np.asarray(gap, float)
    bl = B - one_off
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(gap <= 0, RUNWAY_CAP, np.minimum(bl / gap, RUNWAY_CAP))
    return np.round(np.where(bl <= 0, 0, r), 1)


def pct(x):
    return f"{x:.0%}"


df = build_all_profiles(ms, loans)
g = ms.groupby("account_id")
df = df.set_index("account_id")
df["I_p25"] = g.money_in.quantile(0.25)          # a "bad month" of income
df["I_cv"] = g.money_in.std() / g.money_in.mean().replace(0, np.nan)
df["cash_share_in"] = g.cash_deposits.sum() / g.money_in.sum().replace(0, np.nan)
df["neg_share"] = g.days_below_zero.apply(lambda s: (s > 0).mean())
df = df.reset_index()

df["rw_base"] = rw(df.B, df.S - df.I)
df["rw_ei"] = rw(df.B, df.S - 0.55 * df.I)
df["rw_furnace"] = rw(df.B, df.S - df.I, df.S)
df["rw_ei_bills"] = rw(df.B, df.S + 0.15 * df.H - 0.55 * df.I)
df["buffer_months"] = df.B / df.S.replace(0, np.nan)
df["fixed_ratio"] = df.F / df.I.replace(0, np.nan)
N = len(df)
report = []


def say(s=""):
    print(s); report.append(s)


# ============================================================ A. the resilience gap
say("=" * 70); say(f"A. RESILIENCE GAP  (n = {N:,} accounts)"); say("=" * 70)
for col, name in [("rw_ei", "Laid off, EI 55%"), ("rw_ei_bills", "EI 55% + bills +15%"),
                  ("rw_furnace", "Furnace = 1 month spending (then normal)")]:
    s = df[col]
    say(f"{name:42s} median {s.median():5.1f} mo | <1 mo {pct((s < 1).mean())} | "
        f"<3 mo {pct((s < 3).mean())} | survives 6 mo {pct((s >= 6).mean())}")
say(f"Buffer smaller than ONE month of spending: {pct((df.buffer_months < 1).mean())}")
say(f"Already short every month with NO shock (S > I): {pct((df.S > df.I).mean())}")

fig, ax = plt.subplots(figsize=(8, 4.2))
bins = [-0.01, 1, 3, 6, 12, RUNWAY_CAP + 1]
labels = ["< 1 mo", "1-3 mo", "3-6 mo", "6-12 mo", "12+ mo"]
cnt = pd.cut(df.rw_ei, bins, labels=labels).value_counts().reindex(labels) / N
ax.bar(labels, cnt.values, color=[ORANGE, ORANGE, ORANGE, GREY, GREY])
for i, v in enumerate(cnt.values):
    ax.text(i, v + 0.005, pct(v), ha="center", color=DARK)
ax.set_title(f"If laid off today (EI at 55%), {pct((df.rw_ei < 6).mean())} of customers\nrun out of savings before EI's 6 months are up")
ax.set_ylabel("share of customers"); ax.set_yticks([])
fig.tight_layout(); fig.savefig(OUT / "A_resilience_gap.png", dpi=180); plt.close(fig)

# ============================================================ B. early warning for loan default
say(""); say("=" * 70); say("B. EARLY WARNING: behaviour BEFORE the loan was granted vs default"); say("=" * 70)
lo = loans.copy()
lo["start_m"] = pd.to_datetime(lo.loan_start).dt.strftime("%Y-%m")
pre = ms.merge(lo[["account_id", "start_m", "defaulted"]], on="account_id")
pre = pre[pre.month < pre.start_m]
pg = pre.groupby("account_id")
feat = pd.DataFrame({
    "pre_months": pg.size(),
    "pre_buffer_months": pg.avg_daily_balance.mean() / pg.money_out.median().replace(0, np.nan),
    "pre_min_balance": pg.min_balance.min(),
    "pre_neg_months": pg.days_below_zero.apply(lambda s: int((s > 0).sum())),
    "pre_fees_per_month": pg.bank_fees.mean(),
    "pre_income_cv": pg.money_in.std() / pg.money_in.mean().replace(0, np.nan),
    "pre_surplus_ratio": (pg.money_in.median() - pg.money_out.median()) / pg.money_in.median().replace(0, np.nan),
    "defaulted": pg.defaulted.first(),
}).reset_index()
say(f"loans with pre-loan history: {len(feat)} of {len(lo)} | median pre-loan months: {feat.pre_months.median():.0f}")
say(f"overall default rate: {pct(feat.defaulted.mean())}")
say("\nMedian pre-loan behaviour, repaid (0) vs defaulted (1):")
say(feat.groupby("defaulted")[[c for c in feat.columns if c.startswith("pre_")]].median().T.round(3).to_string())

feat["any_neg_before"] = feat.pre_neg_months > 0
t = feat.groupby("any_neg_before").defaulted.agg(["mean", "count"])
say("\nDefault rate by 'went below zero before the loan':"); say(t.round(3).to_string())
if t.shape[0] == 2 and t.loc[False, "mean"] > 0:
    say(f"-> {t.loc[True, 'mean'] / t.loc[False, 'mean']:.1f}x the default rate")
feat["buf_q"] = pd.qcut(feat.pre_buffer_months.rank(method="first"), 4, labels=["thinnest 25%", "Q2", "Q3", "thickest 25%"])
say("\nDefault rate by pre-loan buffer quartile:"); say(feat.groupby("buf_q", observed=True).defaulted.agg(["mean", "count"]).round(3).to_string())

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import cross_val_predict
    X = feat[["pre_buffer_months", "pre_neg_months", "pre_fees_per_month", "pre_income_cv", "pre_surplus_ratio"]].fillna(0)
    X = X.replace([np.inf, -np.inf], 0)
    X = X.clip(X.quantile(0.01), X.quantile(0.99), axis=1)
    X = X.loc[:, X.std() > 0]
    y = feat.defaulted.astype(int)
    if y.nunique() == 2 and y.sum() >= 10:
        p = cross_val_predict(LogisticRegression(max_iter=1000, class_weight="balanced"),
                              ((X - X.mean()) / X.std()).fillna(0), y, cv=5, method="predict_proba")[:, 1]
        say(f"\n5-fold CV AUC predicting default from pre-loan behaviour only: {roc_auc_score(y, p):.2f} (0.5 = coin flip)")
        for c in X.columns:
            say(f"   single-feature AUC {c:22s} {max(roc_auc_score(y, X[c]), 1 - roc_auc_score(y, X[c])):.2f}")
except Exception as e:
    say(f"(model skipped: {e})")

fig, ax = plt.subplots(figsize=(8, 4.2))
q = feat.groupby("buf_q", observed=True).defaulted.mean()
ax.bar(q.index.astype(str), q.values, color=[ORANGE, GREY, GREY, GREY])
for i, v in enumerate(q.values):
    ax.text(i, v + 0.005, pct(v), ha="center", color=DARK)
ax.set_title("Loan default rate by savings buffer BEFORE the loan was granted")
ax.set_ylabel("default rate"); ax.set_yticks([])
fig.tight_layout(); fig.savefig(OUT / "B_early_warning.png", dpi=180); plt.close(fig)
feat.to_csv(OUT / "B_preloan_features.csv", index=False)

# ============================================================ C. the median hides risk
say(""); say("=" * 70); say("C. DOES THE MEDIAN HIDE RISK? (income volatility)"); say("=" * 70)
df["rw_ei_badmonth"] = rw(df.B, df.S - 0.55 * df.I_p25)
safe_med = df.rw_ei >= 6
unsafe_bad = df.rw_ei_badmonth < 6
flip = safe_med & unsafe_bad
say(f"Income volatility (CV of money_in): median {df.I_cv.median():.2f}")
say(f"'Safe' for 6 months by the median, but NOT if income is a typical bad month (25th pct): {pct(flip.mean())} of all customers "
    f"({pct(flip.sum() / max(safe_med.sum(), 1))} of the 'safe' group)")
df["cv_q"] = pd.qcut(df.I_cv.rank(method="first"), 4, labels=["steadiest 25%", "Q2", "Q3", "most volatile 25%"])
tab = df.groupby("cv_q", observed=True).agg(median_rw_ei=("rw_ei", "median"), neg_share=("neg_share", "mean"),
                                            cash_share=("cash_share_in", "median"), n=("account_id", "size"))
say("\nBy income volatility quartile (neg_share = share of months that actually went below zero):")
say(tab.round(3).to_string())
say("Validation idea: if volatile customers have similar median runway but MORE real negative months, the median overstates them.")

fig, ax = plt.subplots(figsize=(8, 4.2))
ax.bar(tab.index.astype(str), tab.neg_share.values, color=[GREY, GREY, GREY, ORANGE])
for i, v in enumerate(tab.neg_share.values):
    ax.text(i, v + 0.001, f"{v:.1%}", ha="center", color=DARK)
ax.set_title("Share of months that actually went below zero, by income volatility")
ax.set_yticks([])
fig.tight_layout(); fig.savefig(OUT / "C_volatility.png", dpi=180); plt.close(fig)

# ============================================================ D. fixed-cost trap
say(""); say("=" * 70); say("D. FIXED-COST TRAP (fixed costs / income)"); say("=" * 70)
df["fr_band"] = pd.cut(df.fixed_ratio, [-0.01, 0.2, 0.35, 0.5, 10], labels=["<20%", "20-35%", "35-50%", "50%+"])
tab = df.groupby("fr_band", observed=True).agg(n=("account_id", "size"), median_rw_ei=("rw_ei", "median"),
                                               survive6=("rw_ei", lambda s: (s >= 6).mean()),
                                               default=("defaulted", "mean"), median_buffer_mo=("buffer_months", "median"))
say(tab.round(3).to_string())

# ============================================================ E. which shock hurts most
say(""); say("=" * 70); say("E. WHICH SHOCK HURTS MORE?"); say("=" * 70)
loss_ei6 = np.minimum(np.clip(df.S - 0.55 * df.I, 0, None) * 6, df.B.clip(lower=0))
loss_furn = np.minimum(df.S + np.clip(df.S - df.I, 0, None) * 6, df.B.clip(lower=0))
say(f"Furnace (1 month spending) costs MORE over 6 months than a 6-month layoff on EI for: {pct((loss_furn > loss_ei6).mean())}")
say(f"Furnace alone wipes out the buffer for: {pct((df.rw_furnace == 0).mean())}")

# ============================================================ F. small changes, big gains
say(""); say("=" * 70); say("F. SMALL CHANGES: cut discretionary spending 10% during a layoff"); say("=" * 70)
rw_cut = rw(df.B, df.S - 0.10 * df.discretionary - 0.55 * df.I)
gain = (np.minimum(rw_cut, RUNWAY_CAP) - np.minimum(df.rw_ei, RUNWAY_CAP))
mask = df.rw_ei < 6
say(f"Among customers who don't make 6 months: median gain {np.median(gain[mask]):.1f} months; "
    f"{pct((rw_cut[mask] >= 6).mean())} of them now make it")
need = np.clip((df.S - 0.55 * df.I) - df.B / 6, 0, None)
say(f"Median monthly cut needed to survive 6 months on EI (those short): ${np.median(need[mask]):,.0f} "
    f"= {np.median((need / df.discretionary.replace(0, np.nan))[mask]):.0%} of their discretionary spending")

# ============================================================ G. geography + age
say(""); say("=" * 70); say("G. GEOGRAPHY + AGE"); say("=" * 70)
geo = df.merge(accounts[["account_id", "district_id"]], on="account_id").merge(districts, on="district_id")
dl = geo.groupby("district_id").agg(unemp=("unemployment_rate_2023", "first"), salary=("average_salary", "first"),
                                    rw=("rw_ei", "median"), survive6=("rw_ei", lambda s: (s >= 6).mean()),
                                    n=("account_id", "size"))
say("District-level Spearman correlations:"); say(dl[["unemp", "salary", "rw", "survive6"]].corr(method="spearman").round(2).to_string())
dl.to_csv(OUT / "G_districts.csv")
try:
    clients = pd.read_csv(d / "clients.csv"); disp = pd.read_csv(d / "dispositions.csv")
    own = disp[disp.type.str.lower().str.startswith("own")].merge(clients, on="client_id")
    own["age"] = 2025 - pd.to_datetime(own.birth_date).dt.year
    a = df.merge(own[["account_id", "age", "gender"]], on="account_id")
    a["age_band"] = pd.cut(a.age, [0, 30, 45, 60, 120], labels=["<30", "30-44", "45-59", "60+"])
    say("\nBy owner age:"); say(a.groupby("age_band", observed=True).agg(n=("account_id", "size"),
        median_rw_ei=("rw_ei", "median"), survive6=("rw_ei", lambda s: (s >= 6).mean())).round(3).to_string())
except Exception as e:
    say(f"(age skipped: {e})")

df.to_csv(OUT / "all_profiles_runway.csv", index=False)
(OUT / "findings_report.txt").write_text("\n".join(report))
say("\nSaved outputs/findings_report.txt, outputs/*.png, outputs/*.csv")
