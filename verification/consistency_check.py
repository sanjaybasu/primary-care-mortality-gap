#!/usr/bin/env python3
"""
Comprehensive consistency check: regenerate canonical numbers from result CSVs and confirm
each appears in the corresponding manuscript. Catches number drift between code and prose.
Usage:  python3 verification/consistency_check.py
"""
import os, sys
import pandas as pd

PKG = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS = os.path.join(PKG, "results")
ROOT = PKG.split(os.sep + "packaging" + os.sep)[0]
NB = os.path.join(ROOT, "notebooks", "primary-care-world-model")
MS_THRESH = os.path.join(NB, "ai-effectiveness-threshold", "manuscript",
                         "ai_effectiveness_threshold_annals.md")
MS_PORT = os.path.join(NB, "combined-intervention-simulation", "manuscript",
                       "combined_intervention_portfolio_health_affairs.md")
APX_THRESH = os.path.join(NB, "ai-effectiveness-threshold", "appendix",
                          "supplementary_table_model_input_parameters.md")
APX_PORT = os.path.join(NB, "combined-intervention-simulation", "appendix",
                        "supplementary_table_model_input_parameters.md")

port = pd.read_csv(os.path.join(RESULTS, "rederived_portfolio_summary.csv")).set_index("metric")["value"]
abl = pd.read_csv(os.path.join(RESULTS, "rederived_portfolio_ablation.csv"))
thr = pd.read_csv(os.path.join(RESULTS, "rederived_threshold_summary.csv")).set_index("metric")["value"]
grid = pd.read_csv(os.path.join(RESULTS, "rederived_threshold_scenario_grid.csv"))

BASELINE, GAP = 9.6, 2.4
port_txt = open(MS_PORT).read()
thr_txt = open(MS_THRESH).read()

checks = []  # (manuscript, expected_string, description)

# --- portfolio ---
checks += [
    (port_txt, f"{port['point_closure_fraction']*100:.1f}%", "portfolio point closure"),
    (port_txt, f"{port['median']*100:.1f}%", "portfolio PSA median"),
    (port_txt, f"{port['p2.5']*100:.1f}%", "portfolio PSA 2.5%"),
    (port_txt, f"{port['p97.5']*100:.1f}%", "portfolio PSA 97.5%"),
    (port_txt, "2.4 deaths per 1,000", "gap absolute"),
    (port_txt, "9.6", "high-vuln mortality"),
    (port_txt, "7.2", "low-vuln mortality"),
]
for _, r in abl.iterrows():
    checks.append((port_txt, f"{r['marginal_contribution']*100:.1f}", f"ablation: {r['removed']}"))

# --- threshold ---
pt_hr = thr["point_required_HR (F median closure, reach=0.30)"]
abs_red = BASELINE * (1 - pt_hr)  # required absolute reduction among reached at point
checks += [
    (thr_txt, f"{thr['required_hr_median']:.2f}", "threshold PSA median HR"),
    (thr_txt, f"{thr['required_hr_p2.5']:.2f}", "threshold PSA 2.5% HR"),
    (thr_txt, f"{thr['required_hr_p97.5']:.2f}", "threshold PSA 97.5% HR"),
    (thr_txt, f"{abs_red:.1f}", "threshold required absolute reduction /1000 among reached"),
    (thr_txt, "2.4 deaths per 1,000", "gap absolute"),
    (thr_txt, "0.93", "CHW benchmark HR"),
]
# grid cells that appear in Table 1
for _, r in grid.iterrows():
    if r["required_HR"] > 0:
        checks.append((thr_txt, f"{r['required_HR']:.3f}".rstrip("0").rstrip("."),
                       f"grid s={r['structural_closure']} r={r['ai_reach']}"))

# --- appendix parameter tables exist and match inputs.json ---
import json
port_apx = open(APX_PORT).read() if os.path.exists(APX_PORT) else ""
thr_apx = open(APX_THRESH).read() if os.path.exists(APX_THRESH) else ""
pj = json.load(open(os.path.join(PKG, "combined-intervention-simulation", "code", "inputs.json")))
for it in pj["interventions"]:
    checks.append((port_apx, f"{it['rr']:.2f} ({it['rr_low']:.2f}-{it['rr_high']:.2f})",
                   f"appendix rr matches inputs: {it['name']}"))
checks.append((thr_apx, "9.6", "threshold appendix baseline present"))

# --- supplementary cost-layer numbers (portfolio) ---
cost_path = os.path.join(RESULTS, "rederived_portfolio_cost.csv")
if os.path.exists(cost_path):
    cost = pd.read_csv(cost_path).set_index("metric")
    da = cost.loc["deaths_averted_per_100k_per_year", "median"]
    cly = cost.loc["cost_per_life_year_usd"]
    checks.append((port_txt, f"{da:.0f}", "cost: deaths averted per 100k median"))
    checks.append((port_txt, f"{round(cly['median'], -3):,.0f}", "cost: cost per life-year median"))
    checks.append((port_txt, f"{round(cly['p2_5'], -3):,.0f}", "cost: cost per life-year 2.5%"))
    checks.append((port_txt, f"{round(cly['p97_5'], -3):,.0f}", "cost: cost per life-year 97.5%"))

# --- retrospective natural-experiment backtest (threshold manuscript) ---
bt_path = os.path.join(RESULTS, "rederived_portfolio_backtest.csv")
if os.path.exists(bt_path):
    bt = pd.read_csv(bt_path).iloc[0]
    checks.append((thr_txt, f"{bt['predicted_pop_rr']:.3f}", "backtest predicted population RR"))
    checks.append((thr_txt, f"{bt['observed_rr']:.3f}", "backtest observed RR"))
    checks.append((thr_txt, f"{bt['observed_rr_ci_low']:.3f}", "backtest observed RR CI low"))
    checks.append((thr_txt, f"{bt['observed_rr_ci_high']:.3f}", "backtest observed RR CI high"))

# --- driver analysis (threshold manuscript) ---
drv_path = os.path.join(RESULTS, "rederived_threshold_drivers.csv")
if os.path.exists(drv_path):
    drv = pd.read_csv(drv_path).iloc[0]
    checks.append((thr_txt, f"{round(drv['variance_share_reach']*100):.0f}%", "driver: reach variance share"))

# --- three-bundle AI analysis (threshold manuscript) ---
bnd_path = os.path.join(RESULTS, "rederived_ai_bundles.csv")
if os.path.exists(bnd_path):
    bnd = pd.read_csv(bnd_path)
    pooled = bnd.loc[bnd["bundle"] == "A disease-specific (pooled)", "gap_closure_fraction"]
    if len(pooled) and pd.notna(pooled.iloc[0]):
        checks.append((thr_txt, f"{round(pooled.iloc[0]*100):.0f}%", "bundle A gap closure"))
    gen = bnd.loc[bnd["bundle"] == "B generalist"]
    if len(gen):
        if pd.notna(gen["p_harmful_advice"].iloc[0]):
            checks.append((thr_txt, f"{round(gen['p_harmful_advice'].iloc[0]*100):.0f}%", "bundle B harmful advice"))
        if pd.notna(gen["p_incorrect_dx"].iloc[0]):
            checks.append((thr_txt, f"{round(gen['p_incorrect_dx'].iloc[0]*100):.0f}%", "bundle B incorrect dx"))

fails = []
for txt, s, desc in checks:
    ok = s in txt
    print(f"[{'PASS' if ok else 'FAIL'}] {desc}: expected '{s}'")
    if not ok:
        fails.append((desc, s))

print(f"\n{len(checks)-len(fails)}/{len(checks)} consistent")
if fails:
    print("MISMATCHES (fix manuscript to match code):")
    for d, s in fails:
        print(f"  - {d}: '{s}' not found")
    sys.exit(1)
print("OVERALL: PASS")
