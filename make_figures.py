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


def fig_threshold_heatmap():
    g = pd.read_csv(os.path.join(RESULTS, "rederived_threshold_scenario_grid.csv"))
    piv = g.pivot(index="structural_closure", columns="ai_reach", values="required_HR")
    piv = piv.sort_index(ascending=True)
    M = piv.values.astype(float)
    disp = np.where(M > 0, M, np.nan)
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    im = ax.imshow(disp, cmap="viridis", aspect="auto", origin="lower", vmin=0, vmax=1)
    ax.set_xticks(range(len(piv.columns))); ax.set_xticklabels([f"{c:.2f}" for c in piv.columns])
    ax.set_yticks(range(len(piv.index))); ax.set_yticklabels([f"{i:.2f}" for i in piv.index])
    ax.set_xlabel("AI reach (fraction of high-vulnerability population)")
    ax.set_ylabel("Structural gap closure (fraction)")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            txt = f"{v:.2f}" if v > 0 else "n/a"
            ax.text(j, i, txt, ha="center", va="center",
                    color="white" if (v > 0 and v < 0.6) else "black", fontsize=9)
    cbar = fig.colorbar(im, ax=ax); cbar.set_label("Required AI hazard ratio")
    ax.set_title("Required clinical AI hazard ratio among patients reached")
    fig.text(0.5, -0.02,
             "n/a: residual gap not closable at that reach even at HR=0. "
             "HR~0.91 arises only at full reach with 75% structural closure.",
             ha="center", fontsize=8, wrap=True)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_THRESH, "figure1_required_hr_heatmap.png"),
                dpi=300, bbox_inches="tight")
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
    fig_threshold_heatmap()
    fig_portfolio_psa()
    fig_portfolio_ablation()
    fig_portfolio_tornado()
    print("Figures written:")
    for d in (FIG_THRESH, FIG_PORT):
        for f in sorted(os.listdir(d)):
            if f.endswith(".png"):
                print(" ", os.path.join(d, f))
