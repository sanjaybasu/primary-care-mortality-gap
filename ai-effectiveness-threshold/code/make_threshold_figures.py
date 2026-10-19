#!/usr/bin/env python3
"""
Figures for the AI-effectiveness threshold manuscript (Medical Decision Making).
Reads only results/threshold_canonical.json, results/threshold_reach_grid.csv and the saved PSA
draws written by threshold_model.py. No titles inside panels (titles live in the legends).
Line styles and markers differ so each figure reads in grayscale. Writes PNG (300 dpi) and
TIFF (600 dpi) to the notebooks figures folder.
Usage: python3 threshold_model.py && python3 make_threshold_figures.py
"""
import json, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "results"))
ROOT = HERE.split(os.sep + "packaging" + os.sep)[0]
FIG = os.path.join(ROOT, "notebooks", "primary-care-world-model", "ai-effectiveness-threshold", "figures")
os.makedirs(FIG, exist_ok=True)
CB = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73", "red": "#D55E00",
      "grey": "#666666", "purple": "#CC79A7", "black": "#000000"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})

C = json.load(open(os.path.join(RESULTS, "threshold_canonical.json")))
INP = json.load(open(os.path.join(HERE, "inputs.json")))
HR = C["demonstrated_HR"]; P = C["psa"]; DET = C["deterministic"]
r_hi0 = INP["ai_reach"]["high_vuln"]["point"]; r_lo0 = INP["ai_reach"]["low_vuln"]["point"]
m_hi = INP["mortality"]["high_vuln_per_1000"]; m_lo = INP["mortality"]["low_vuln_per_1000"]


def save(fig, name):
    fig.savefig(os.path.join(FIG, name + ".png"), dpi=300, bbox_inches="tight")
    fig.savefig(os.path.join(FIG, name + ".tif"), dpi=600, bbox_inches="tight",
                pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


def fig1_two_way_threshold():
    g = pd.read_csv(os.path.join(RESULTS, "threshold_reach_grid.csv"))
    fig, ax = plt.subplots(figsize=(6.6, 4.8))
    ax.plot(g["reach"], g["required_HR_realized"], color=CB["blue"], lw=2.2, ls="-",
            label="Required effect, realized decline")
    ax.plot(g["reach"], g["required_HR_projected"], color=CB["red"], lw=2.2, ls="--",
            label="Required effect, projected shortfall")
    ax.axhspan(P["cvdeath_HR_p2.5"], P["cvdeath_HR_p97.5"], color=CB["green"], alpha=0.18, lw=0)
    ax.axhline(HR["cvdeath"], color=CB["green"], lw=1.6, ls="-.",
               label=f"Hypertension AI, base case ({HR['cvdeath']:.3f})")
    ax.axhline(HR["allcause_trial"], color=CB["purple"], lw=1.4, ls=":",
               label=f"Hypertension AI, trial all-cause transmission ({HR['allcause_trial']:.3f})")
    ax.axvline(r_hi0, color=CB["grey"], lw=1.0, ls=(0, (4, 2)))
    ax.axvline(r_lo0, color=CB["grey"], lw=1.0, ls=(0, (1, 2)))
    ax.text(r_hi0 + 0.005, 0.903, "assumed reach,\nhigh-vulnerability", fontsize=7, color=CB["grey"])
    ax.text(r_lo0 + 0.005, 0.903, "assumed reach,\nlow-vulnerability", fontsize=7, color=CB["grey"])
    ax.set_xlim(0, 1.0); ax.set_ylim(0.90, 1.0)
    ax.set_xlabel("Reach (fraction of community residents who use the AI tool)")
    ax.set_ylabel("Per-patient all-cause mortality hazard ratio")
    ax.text(0.52, 0.925, "An effect below a curve offsets the\nexcess mortality at that reach", fontsize=7.5)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2, fontsize=7.5, frameon=False)
    save(fig, "figure1_two_way_threshold")


def fig2_equity():
    r_lo = np.linspace(0.20, 0.65, 200)
    dD = DET["realized"]["excess_high_per_1000"] - DET["realized"]["excess_low_per_1000"]
    fig, ax = plt.subplots(figsize=(6.6, 4.8))
    for key, col, ls, lab in [("cvdeath", CB["green"], "-", "Hypertension AI, base case"),
                              ("allcause_trial", CB["purple"], "-.", "Hypertension AI, trial transmission"),
                              ("inpatient_ai_upper_bound", CB["orange"], "--", "Hypothetical AI effect, HR 0.83")]:
        h = HR[key]
        need = (dD / (1 - h) + m_lo * r_lo) / m_hi
        ax.plot(r_lo, need, color=col, lw=2, ls=ls, label=f"{lab}")
    ax.plot(r_lo, r_lo, color=CB["grey"], lw=1, ls=":", label="Equal reach in both communities")
    ax.fill_between(r_lo, 0, (dD / (1 - HR["cvdeath"]) + m_lo * r_lo) / m_hi, color=CB["red"], alpha=0.08, lw=0)
    ax.plot([r_lo0], [r_hi0], marker="o", ms=7, color=CB["black"], ls="none", label="Assumed reach (base case)")
    ax.set_xlim(0.20, 0.65); ax.set_ylim(0, 0.75)
    ax.set_xlabel("Reach in low-vulnerability communities")
    ax.set_ylabel("Reach in high-vulnerability communities")
    ax.text(0.40, 0.06, "Shaded: difference wider than before the loss\n(base-case effect)", fontsize=7.5)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2, fontsize=7.5, frameon=False)
    save(fig, "figure2_equity_reach")


def fig3_acceptability():
    acc = pd.read_csv(os.path.join(RESULTS, "threshold_acceptability.csv"))
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    styles = {("realized", "cvdeath"): (CB["blue"], "-", "Realized decline, base-case transmission"),
              ("realized", "allcause_trial"): (CB["blue"], ":", "Realized decline, trial all-cause transmission"),
              ("projected", "cvdeath"): (CB["red"], "--", "Projected shortfall, base-case transmission"),
              ("projected", "allcause_trial"): (CB["red"], (0, (6, 2, 1, 2)), "Projected shortfall, trial all-cause transmission")}
    for (sk, tk), (col, ls, lab) in styles.items():
        g = acc[(acc.scenario == sk) & (acc.transmission == tk)]
        ax.plot(g["reach"], g["prob_meets"], color=col, ls=ls, lw=2, label=lab)
    ax.axvline(r_hi0, color=CB["grey"], lw=1.0, ls=(0, (4, 2)))
    ax.text(r_hi0 + 0.01, 0.03, "assumed reach,\nhigh-vulnerability", fontsize=7, color=CB["grey"])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.0)
    ax.set_xlabel("Reach in high-vulnerability communities")
    ax.set_ylabel("Probability that AI for hypertension offsets the excess")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2, fontsize=7.5, frameon=False, handlelength=4.5)
    save(fig, "figure3_acceptability")


if __name__ == "__main__":
    fig1_two_way_threshold(); fig2_equity(); fig3_acceptability()
    print("figures written to", FIG)
