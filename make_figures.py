#!/usr/bin/env python3
"""
Reproducible figures for both manuscripts. Reads results/rederived_* and writes PNGs to
the notebooks manuscript figure folders. Colorblind-safe palette; legends/labels below
panels. Deterministic (reads fixed model outputs).
Usage:  python3 make_figures.py
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PKG = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(PKG, "results")
# map to notebooks manuscript figure folders
ROOT = PKG.split(os.sep + "packaging" + os.sep)[0]
NB = os.path.join(ROOT, "notebooks", "primary-care-world-model")
FIG_THRESH = os.path.join(NB, "ai-effectiveness-threshold", "figures")
FIG_PORT = os.path.join(NB, "combined-intervention-simulation", "figures")
for d in (FIG_THRESH, FIG_PORT):
    os.makedirs(d, exist_ok=True)

CB = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73",
      "red": "#D55E00", "grey": "#999999", "purple": "#CC79A7"}


def fig_shortfall():
    by = pd.read_csv(os.path.join(RESULTS, "rederived_threshold_by_stratum.csv")).set_index("stratum")
    Dh = float(by.loc["high", "attributable_excess_per_1000"])
    diff = 9.6 - 7.2
    fig, ax = plt.subplots(figsize=(6.8, 2.8))
    ax.barh([0], [diff], color=CB["grey"], edgecolor="white")
    ax.barh([0], [Dh], color=CB["blue"], edgecolor="white")
    ax.set_yticks([]); ax.set_xlabel("Deaths per 1,000 (high- vs low-vulnerability difference)")
    ax.set_xlim(0, diff * 1.05)
    ax.annotate(f"attributable to primary care loss: {Dh:.3f}", xy=(Dh, 0),
                xytext=(diff * 0.30, 0.35), fontsize=8,
                arrowprops=dict(arrowstyle="->", lw=0.8))
    ax.text(diff * 0.55, 0, f"remainder (poverty and other causes): {diff - Dh:.2f}",
            va="center", fontsize=8, color="black")
    ax.set_title("Most of the community mortality difference is not attributable to primary care")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_THRESH, "figure1_shortfall.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig_required_by_reach():
    g = pd.read_csv(os.path.join(RESULTS, "rederived_threshold_reach_grid.csv"))
    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    ax.plot(g["reach"], g["required_HR_to_offset"], color=CB["blue"], linewidth=2,
            label="required effect to offset the loss")
    ax.axhline(0.93, color=CB["green"], linestyle="-", linewidth=1.4,
               label="community health worker 0.93")
    ax.axhline(0.94, color=CB["purple"], linestyle="-", linewidth=1.2,
               label="digital hypertension 0.94")
    ax.axhline(1.00, color=CB["red"], linestyle=":", linewidth=1.2, label="no effect 1.00")
    ax.axvline(0.20, color=CB["grey"], linestyle="--", linewidth=1.0)
    ax.text(0.205, 0.945, "current high-vuln reach", fontsize=7.5, color="black")
    ax.set_xlabel("Reach (fraction of the community served)")
    ax.set_ylabel("Required clinical AI hazard ratio")
    ax.set_xlim(0, 1.0); ax.set_ylim(0.90, 1.005)
    ax.set_title("The required per-patient effect is small at plausible reach")
    ax.legend(loc="lower right", fontsize=8)
    fig.text(0.5, -0.02, "The required effect (blue) stays above the best demonstrated effects "
             "(0.93, 0.94) for any reach above about 0.05, so a demonstrated effect is sufficient "
             "in per-patient terms.", ha="center", fontsize=7.5, wrap=True)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_THRESH, "figure2_required_by_reach.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig_equity():
    by = pd.read_csv(os.path.join(RESULTS, "rederived_threshold_by_stratum.csv")).set_index("stratum")
    Dh = float(by.loc["high", "attributable_excess_per_1000"])
    Dl = float(by.loc["low", "attributable_excess_per_1000"])
    eq = pd.read_csv(os.path.join(RESULTS, "rederived_threshold_equity.csv"))
    cross = float(eq[eq["demonstrated_tool"] == "community_health_worker"]
                  ["high_vuln_reach_needed_to_not_widen"].iloc[0])
    m_high, m_low, r_low, k = 9.6, 7.2, 0.40, (1 - 0.93)
    r = np.arange(0.05, 0.601, 0.005)
    prevented_high = m_high * r * k
    threshold = m_low * r_low * k + (Dh - Dl)
    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    ax.plot(r, prevented_high, color=CB["blue"], linewidth=2,
            label="mortality prevented in high-vulnerability communities")
    ax.axhline(threshold, color=CB["orange"], linestyle="-", linewidth=1.4,
               label="level needed to not widen the difference")
    ax.axvline(cross, color=CB["green"], linestyle="--", linewidth=1.1)
    ax.axvline(0.20, color=CB["grey"], linestyle="--", linewidth=1.0)
    ax.axvspan(0.05, cross, color=CB["red"], alpha=0.07)
    ax.text(0.10, threshold * 1.5, "widens the difference", fontsize=8, color=CB["red"])
    ax.text(cross + 0.01, threshold * 0.5, f"reach needed: {cross:.2f}", fontsize=8, color=CB["green"])
    ax.text(0.205, threshold * 0.25, "current 0.20", fontsize=7.5, color="black")
    ax.set_xlabel("Reach in high-vulnerability communities")
    ax.set_ylabel("Mortality prevented per 1,000")
    ax.set_xlim(0.05, 0.60)
    ax.set_title("Whether clinical AI narrows or widens the mortality difference")
    ax.legend(loc="lower right", fontsize=8)
    fig.text(0.5, -0.02, "A tool with a demonstrated effect prevents more mortality in "
             "low-vulnerability communities until high-vulnerability reach rises to about "
             f"{cross:.2f}. Below that reach it widens the difference.", ha="center",
             fontsize=7.5, wrap=True)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_THRESH, "figure3_equity.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig_required_psa():
    hr = np.load(os.path.join(RESULTS, "rederived_threshold_psa_draws.npy"))
    s = pd.read_csv(os.path.join(RESULTS, "rederived_threshold_summary.csv")).set_index("metric")["value"]
    med = float(s["required_HR_high_median"]); lo = float(s["required_HR_high_p2.5"]); hi = float(s["required_HR_high_p97.5"])
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    ax.hist(np.clip(hr, 0.9, 1.0), bins=60, color=CB["blue"], alpha=0.75, edgecolor="white", linewidth=0.3)
    ax.axvline(med, color=CB["blue"], linestyle="--", linewidth=1.4, label=f"required effect median {med:.3f}")
    ax.axvspan(lo, hi, color=CB["blue"], alpha=0.10, label=f"95% interval {lo:.3f}-{hi:.3f}")
    ax.axvline(0.93, color=CB["green"], linestyle="-", linewidth=1.4, label="community health worker 0.93")
    ax.axvline(0.94, color=CB["purple"], linestyle="-", linewidth=1.2, label="digital hypertension 0.94")
    ax.set_xlabel("Required clinical AI hazard ratio, high-vulnerability communities")
    ax.set_ylabel("Probabilistic draws")
    ax.set_xlim(0.90, 1.0)
    ax.set_title("Required per-patient effect to offset the loss (20,000 draws)")
    ax.legend(loc="upper left", fontsize=7.5)
    fig.text(0.5, -0.02, "The best demonstrated effects (0.93, 0.94) lie to the left of the required "
             "effect in every draw, so a demonstrated effect offsets the loss in per-patient terms.",
             ha="center", fontsize=7.5, wrap=True)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_THRESH, "figure4_required_psa.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig_portfolio_psa():
    full = np.load(os.path.join(RESULTS, "rederived_portfolio_psa_draws.npy")) * 100
    robust = np.load(os.path.join(RESULTS, "rederived_portfolio_robust_psa_draws.npy")) * 100
    mfull, mrob = np.median(full), np.median(robust)
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    ax.hist(robust, bins=60, color=CB["green"], alpha=0.7, edgecolor="white", linewidth=0.3,
            label=f"evidence-robust (median {mrob:.1f}%)")
    ax.hist(full, bins=60, color=CB["blue"], alpha=0.5, edgecolor="white", linewidth=0.3,
            label=f"including physician supply (median {mfull:.1f}%)")
    ax.axvline(mrob, color=CB["green"], linestyle="--", linewidth=1.3)
    ax.axvline(mfull, color=CB["blue"], linestyle="--", linewidth=1.3)
    ax.axvline(50, color=CB["orange"], linestyle=":", linewidth=1.0)
    ax.axvline(75, color=CB["orange"], linestyle=":", linewidth=1.0)
    ax.set_xlabel("Fraction of mortality gap closed (%)")
    ax.set_ylabel("Probabilistic draws")
    ax.set_title("Combined structural package: gap closure (20,000 draws)")
    ax.legend(loc="upper right", fontsize=8)
    fig.text(0.5, -0.02, "Evidence-robust package (Medicaid, community health workers, integrated "
             "behavioral health, FQHC) versus the same package plus the associational physician-"
             "supply effect; dotted lines mark 50% and 75%.", ha="center", fontsize=7.5, wrap=True)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_PORT, "exhibit1_gap_closure_psa.png"),
                dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig_portfolio_ablation():
    a = pd.read_csv(os.path.join(RESULTS, "rederived_portfolio_ablation.csv"))
    a = a.sort_values("marginal_contribution", ascending=True)
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    ax.barh(a["removed"], a["marginal_contribution"] * 100, color=CB["green"], alpha=0.9)
    for y, v in enumerate(a["marginal_contribution"] * 100):
        ax.text(v + 0.2, y, f"{v:.1f}", va="center", fontsize=9)
    ax.set_xlabel("Marginal contribution to gap closure (percentage points)")
    ax.set_title("Leave-one-out contribution by intervention")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_PORT, "exhibit2_ablation.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig_portfolio_tornado():
    t = pd.read_csv(os.path.join(RESULTS, "rederived_portfolio_tornado.csv"))
    base = pd.read_csv(os.path.join(RESULTS, "rederived_portfolio_summary.csv")
                       ).set_index("metric")["value"]["point_closure_fraction"] * 100
    # swing per (intervention, param)
    key = t.groupby(["intervention", "param"])["closure"].agg(["min", "max"]).reset_index()
    key["swing"] = (key["max"] - key["min"]) * 100
    key = key.sort_values("swing", ascending=True).tail(10)
    labels = [f"{r.intervention} ({r.param})" for r in key.itertuples()]
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    for y, r in enumerate(key.itertuples()):
        ax.plot([r.min * 100, r.max * 100], [y, y], color=CB["purple"], linewidth=6, alpha=0.8)
    ax.axvline(base, color=CB["red"], linestyle="--", linewidth=1.2, label=f"base {base:.1f}%")
    ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Fraction of gap closed (%)")
    ax.set_title("One-way sensitivity (top 10 parameters)")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_PORT, "exhibit3_tornado.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    fig_shortfall()
    fig_required_by_reach()
    fig_equity()
    fig_required_psa()
    fig_portfolio_psa()
    fig_portfolio_ablation()
    fig_portfolio_tornado()
    print("Figures written:")
    for d in (FIG_THRESH, FIG_PORT):
        for f in sorted(os.listdir(d)):
            if f.endswith(".png"):
                print(" ", os.path.join(d, f))
