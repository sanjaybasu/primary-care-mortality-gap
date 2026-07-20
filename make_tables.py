#!/usr/bin/env python3
"""
Reproducible parameter tables. Reads each model's inputs.json and writes a sourced,
graded input-parameter table (markdown) into the corresponding appendix folder. Ensures the
appendix parameter table cannot drift from the inputs the code actually uses.
Usage:  python3 make_tables.py
"""
import json, os

PKG = os.path.dirname(os.path.abspath(__file__))
ROOT = PKG.split(os.sep + "packaging" + os.sep)[0]
NB = os.path.join(ROOT, "notebooks", "primary-care-world-model")

PORT_IN = os.path.join(PKG, "combined-intervention-simulation", "code", "inputs.json")
THR_IN = os.path.join(PKG, "ai-effectiveness-threshold", "code", "inputs.json")
PORT_OUT = os.path.join(NB, "combined-intervention-simulation", "appendix",
                        "supplementary_table_model_input_parameters.md")
THR_OUT = os.path.join(NB, "ai-effectiveness-threshold", "appendix",
                       "supplementary_table_model_input_parameters.md")


def portfolio_table():
    d = json.load(open(PORT_IN))
    lines = ["# Supplementary Table. Combined-intervention portfolio: model input parameters",
             "",
             "Generated from `inputs.json` (source of truth). rr = relative all-cause mortality "
             "among the population reached; coverage = reachable fraction of the high-vulnerability "
             "(SVI Q4) population.", "",
             "| Intervention | rr (95% CI) | Coverage (range) | Evidence grade | Status | Source |",
             "|---|---|---|---|---|---|"]
    for it in d["interventions"]:
        lines.append(f"| {it['name']} | {it['rr']:.2f} ({it['rr_low']:.2f}-{it['rr_high']:.2f}) "
                     f"| {it['coverage']:.2f} ({it['coverage_low']:.2f}-{it['coverage_high']:.2f}) "
                     f"| {it['grade']} | {it['status']} | {it['source']} |")
    lam = d["diminishing_returns_lambda"]
    lines += ["",
              f"Diminishing-returns penalty lambda: point {lam['point']:.2f} "
              f"(range {lam['low']:.2f}-{lam['high']:.2f}).",
              f"Gap: high-vulnerability {d['gap']['baseline_highvuln_per_1000']} vs "
              f"low-vulnerability {d['gap']['baseline_lowvuln_per_1000']} = "
              f"{d['gap']['gap_per_1000']} deaths per 1,000 person-years "
              f"({d['_meta']['gap_source']}).",
              f"Probabilistic sensitivity analysis: {d['psa']['n_draws']} draws, seed {d['psa']['seed']}.",
              "", "Notes on individual parameters:"]
    for it in d["interventions"]:
        if it.get("note"):
            lines.append(f"- {it['name']}: {it['note']}")
    open(PORT_OUT, "w").write("\n".join(lines) + "\n")


def threshold_table():
    d = json.load(open(THR_IN))
    r = d["ai_reach"]; b = d["benchmarks"]
    lines = ["# Supplementary Table. AI-effectiveness threshold: model input parameters",
             "",
             "Generated from `inputs.json` (source of truth).", "",
             "| Parameter | Value / range | Source | Status |",
             "|---|---|---|---|",
             f"| High-vulnerability mortality | {d['gap']['baseline_highvuln_per_1000']} per 1,000 "
             f"| {d['gap']['source']} | verified |",
             f"| Mortality gap | {d['gap']['gap_per_1000']} per 1,000 | {d['gap']['source']} | verified |",
             f"| AI reach | {r['point']:.2f} (range {r['low']:.2f}-{r['high']:.2f}) | {r['source']} "
             f"| {r['status']} |",
             f"| Structural gap closure | from portfolio PSA draws | {d['structural_closure_source']} "
             f"| derived |",
             f"| Current clinical AI HR | {b['current_clinical_ai_hr']:.2f} | {b['note']} | provisional |",
             f"| Community health worker HR | {b['community_health_worker_hr']:.2f} | {b['note']} "
             f"| provisional |",
             "",
             f"Probabilistic sensitivity analysis: {d['psa']['n_draws']} draws, seed {d['psa']['seed']}.",
             f"Reach note: {r['note']}"]
    open(THR_OUT, "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    portfolio_table(); threshold_table()
    print("Parameter tables written:")
    print(" ", PORT_OUT)
    print(" ", THR_OUT)
