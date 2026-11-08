"""Headline charts for the pitch / video / Devpost.  Run: python headline_charts.py ../data"""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd

d = Path(sys.argv[1] if len(sys.argv) > 1 else "../data")
OUT = Path("outputs"); OUT.mkdir(exist_ok=True)
ORANGE, GREY, INK, MUTED = "#E0731C", "#8E8A83", "#1D1D1F", "#66666B"
plt.rcParams.update({"font.size": 13, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.spines.left": False, "axes.edgecolor": "#DDD", "font.family": "DejaVu Sans"})


def titles(fig, ax, title, sub):
    ax.set_title("")
    fig.text(0.02, 0.965, title, fontsize=17, fontweight="bold", color=INK, va="top")
    fig.text(0.02, 0.895, sub, fontsize=12, color=MUTED, va="top")


def rounded_bars(ax, xs, hs, colors, width=0.56):
    for x, h, c in zip(xs, hs, colors):
        ax.add_patch(FancyBboxPatch((x - width / 2, 0), width, h, boxstyle="round,pad=0,rounding_size=0.04",
                                    mutation_aspect=max(hs) / 6, fc=c, ec="none"))
    ax.set_xlim(-0.6, len(xs) - 0.4); ax.set_ylim(0, max(hs) * 1.2); ax.set_yticks([])


# ---------- 1. the warning sign
ms = pd.read_csv(d / "monthly_summary.csv"); loans = pd.read_csv(d / "loans.csv")
lo = loans.assign(start_m=pd.to_datetime(loans.loan_start).dt.strftime("%Y-%m"))
pre = ms.merge(lo[["account_id", "start_m"]], on="account_id"); pre = pre[pre.month < pre.start_m]
flag = set(pre[pre.days_below_zero > 0].account_id)
lo["flag"] = lo.account_id.isin(flag)
g = lo.groupby("flag").defaulted.agg(["mean", "sum", "count"])
fig, ax = plt.subplots(figsize=(9, 5.2))
hs = [g.loc[False, "mean"], g.loc[True, "mean"]]
rounded_bars(ax, [0, 1], hs, [GREY, ORANGE])
labels = [f"Never went below $0\nbefore the loan\n(n = {int(g.loc[False,'count'])})",
          f"Went below $0\nbefore the loan\n(n = {int(g.loc[True,'count'])})"]
ax.set_xticks([0, 1], labels, color=INK)
for x, h, (k) in zip([0, 1], hs, [False, True]):
    ax.text(x, h + max(hs) * 0.03, f"{h:.0%}", ha="center", fontsize=22, fontweight="bold", color=INK)
    ax.text(x, h + max(hs) * 0.15, f"{int(g.loc[k,'sum'])} of {int(g.loc[k,'count'])} defaulted", ha="center", fontsize=11.5, color=MUTED)
titles(fig, ax, "The warning shows up before the loan", "Loan default rate, by whether the balance went below $0 in the months before the loan")
fig.text(0.01, 0.01, "682 loans · Fisher exact p < 1e-27 · holds counting only dips ≥3 months before the loan (17 of 17)",
         fontsize=10, color=MUTED)
fig.tight_layout(rect=(0, 0.03, 1, 0.86)); fig.savefig(OUT / "headline_1_warning_sign.png", dpi=200); plt.close(fig)

# ---------- 2. income volatility
gp = pre.groupby("account_id")
cv = (gp.money_in.std() / gp.money_in.mean()).rename("cv")
x = lo.set_index("account_id").join(cv)
x["q"] = pd.qcut(x.cv, 4, labels=False)
r = x.groupby("q").defaulted.mean()
fig, ax = plt.subplots(figsize=(9, 5.2))
rounded_bars(ax, range(4), r.values, [GREY, GREY, GREY, ORANGE])
ax.set_xticks(range(4), ["Steadiest\nincome", "2nd", "3rd", "Most uneven\nincome"], color=INK)
for i, v in enumerate(r.values):
    ax.text(i, v + r.max() * 0.03, f"{v:.1%}", ha="center", fontsize=17, fontweight="bold", color=INK)
titles(fig, ax, f"Uneven income = {r.iloc[3] / r.iloc[0]:.1f}× the default rate", "Loan default rate, by month-to-month income swings before the loan (682 loans split into quarters)")
fig.tight_layout(rect=(0, 0, 1, 0.86)); fig.savefig(OUT / "headline_2_uneven_income.png", dpi=200); plt.close(fig)

# ---------- 3. resilience gap
prof = pd.read_csv(OUT / "all_profiles_runway.csv")
bins, labs = [-0.01, 1, 3, 6, 12, 1e9], ["< 1 month", "1–3", "3–6", "6–12", "12+ months"]
c = pd.cut(prof.rw_ei, bins, labels=labs).value_counts().reindex(labs) / len(prof)
fig, ax = plt.subplots(figsize=(9, 5.2))
rounded_bars(ax, range(5), c.values, [ORANGE, ORANGE, ORANGE, GREY, GREY])
ax.set_xticks(range(5), labs, color=INK)
for i, v in enumerate(c.values):
    ax.text(i, v + c.max() * 0.03, f"{v:.0%}", ha="center", fontsize=17, fontweight="bold", color=INK)
short = (prof.rw_ei < 6)
titles(fig, ax, "1 in 3 customers can't get through a 6-month layoff on EI", f"Months of savings if laid off with EI at 55% · orange = runs out before 6 months ({short.sum():,} of {len(prof):,})")
fig.tight_layout(rect=(0, 0, 1, 0.86)); fig.savefig(OUT / "headline_3_resilience_gap.png", dpi=200); plt.close(fig)
print("saved headline charts")
