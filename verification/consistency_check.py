#!/usr/bin/env python3
"""
Comprehensive consistency check: regenerate canonical numbers from result CSVs and confirm
each appears in the corresponding manuscript. Catches number drift between code and prose.
Usage:  python3 verification/consistency_check.py
"""
import os, sys, json
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
                          "supplementary_appendix.md")
APX_PORT = os.path.join(NB, "combined-intervention-simulation", "appendix",
                        "supplementary_table_model_input_parameters.md")

thr_txt = open(MS_THRESH).read()
thr_apx = open(APX_THRESH).read() if os.path.exists(APX_THRESH) else ""
port_txt = open(MS_PORT).read() if os.path.exists(MS_PORT) else ""
port_apx = open(APX_PORT).read() if os.path.exists(APX_PORT) else ""

checks = []  # (text, expected_string, description)

# ======================= THRESHOLD (Medical Decision Making) =======================
thr = pd.read_csv(os.path.join(RESULTS, "rederived_threshold_summary.csv")).set_index("metric")["value"]
by = pd.read_csv(os.path.join(RESULTS, "rederived_threshold_by_stratum.csv")).set_index("stratum")
eq = pd.read_csv(os.path.join(RESULTS, "rederived_threshold_equity.csv"))
ade = pd.read_csv(os.path.join(RESULTS, "rederived_threshold_adequacy.csv")).iloc[0]
ru = pd.read_csv(os.path.join(RESULTS, "rederived_threshold_rural_urban.csv")).set_index("locale")

D_high = float(by.loc["high", "attributable_excess_per_1000"])
D_low = float(by.loc["low", "attributable_excess_per_1000"])
delta = float(thr["elasticity_per10_allcause_point"]) * (5.2 / 10.0)
rural_req_high = 1 - float(ru.loc["rural", "rel_mortality_increase"]) / 0.20
narrow_p = float(thr["prob_AI_narrows_gap_at_current_reach"])
eq_chw = float(eq[eq["demonstrated_tool"] == "community_health_worker"]
               ["high_vuln_reach_needed_to_not_widen"].iloc[0])

checks += [
    (thr_txt, "9.6", "baseline mortality high-vulnerability"),
    (thr_txt, "7.2", "baseline mortality low-vulnerability"),
    (thr_txt, "46.6", "PCP supply 2005"),
    (thr_txt, "41.4", "PCP supply 2015"),
    (thr_txt, "5.2", "PCP supply decline"),
    (thr_txt, f"{D_high:.3f}", "attributable excess high-vulnerability"),
    (thr_txt, f"{D_low:.3f}", "attributable excess low-vulnerability"),
    (thr_txt, f"{float(thr['required_HR_high_point']):.3f}", "required HR high point"),
    (thr_txt, f"{float(thr['required_HR_high_median']):.3f}", "required HR high median"),
    (thr_txt, f"{float(thr['required_HR_high_p2.5']):.3f}", "required HR high 2.5%"),
    (thr_txt, f"{float(thr['required_HR_high_p97.5']):.3f}", "required HR high 97.5%"),
    (thr_txt, f"{round((1-narrow_p)*100):.0f}%", "share of draws AI widens the gap"),
    (thr_txt, f"{round(eq_chw*100):.0f}%", "high-vuln reach needed to not widen"),
    (thr_txt, "0.93", "CHW benchmark HR"),
    (thr_txt, "0.94", "digital hypertension transmitted HR"),
    (thr_txt, "7.0", "rural decline"),
    (thr_txt, "2.6", "urban decline"),
    (thr_txt, f"{float(ade['required_HR_high_at_point_reach']):.2f}", "adequacy required HR high"),
    (thr_txt, f"{rural_req_high:.2f}", "rural required HR high"),
    (thr_txt, f"{delta*100:.1f}%", "relative mortality rise from the loss"),
    # appendix
    (thr_apx, "9.6", "appendix baseline present"),
    (thr_apx, f"{float(thr['required_HR_high_point']):.3f}", "appendix reach-grid required HR at 0.20"),
    (thr_apx, f"{float(ade['attributable_excess_high_per_1000']):.3f}", "appendix adequacy excess"),
    (thr_apx, "CHEERS 2022", "appendix CHEERS checklist present"),
]

# three-type analysis: chatbot unsafe-advice rate
bnd_path = os.path.join(RESULTS, "rederived_ai_bundles.csv")
if os.path.exists(bnd_path):
    bnd = pd.read_csv(bnd_path)
    b = bnd[bnd["bundle"].str.startswith("B generalist")]
    if len(b) and "p_harmful_advice" in bnd.columns and pd.notna(b["p_harmful_advice"].iloc[0]):
        checks.append((thr_txt, f"{round(b['p_harmful_advice'].iloc[0]*100):.0f}%", "chatbot unsafe-advice rate"))

# ======================= PORTFOLIO (Health Affairs) =======================
if port_txt:
    port = pd.read_csv(os.path.join(RESULTS, "rederived_portfolio_summary.csv")).set_index("metric")["value"]
    abl = pd.read_csv(os.path.join(RESULTS, "rederived_portfolio_ablation.csv"))
    checks += [
        (port_txt, f"{port['point_closure_fraction']*100:.1f}%", "portfolio point closure"),
        (port_txt, f"{port['median']*100:.1f}%", "portfolio PSA median"),
        (port_txt, f"{port['p2.5']*100:.1f}%", "portfolio PSA 2.5%"),
        (port_txt, f"{port['p97.5']*100:.1f}%", "portfolio PSA 97.5%"),
        (port_txt, f"{port['robust_median']*100:.1f}%", "portfolio evidence-robust median"),
        (port_txt, "2.4 deaths per 1,000", "gap absolute"),
        (port_txt, "9.6", "high-vuln mortality"),
        (port_txt, "7.2", "low-vuln mortality"),
    ]
    for _, r in abl.iterrows():
        checks.append((port_txt, f"{r['marginal_contribution']*100:.1f}", f"ablation: {r['removed']}"))
    pj = json.load(open(os.path.join(PKG, "combined-intervention-simulation", "code", "inputs.json")))
    for it in pj["interventions"]:
        checks.append((port_apx, f"{it['rr']:.2f} ({it['rr_low']:.2f}-{it['rr_high']:.2f})",
                       f"portfolio appendix rr matches inputs: {it['name']}"))
    cost_path = os.path.join(RESULTS, "rederived_portfolio_cost.csv")
    if os.path.exists(cost_path):
        cost = pd.read_csv(cost_path).set_index("metric")
        da = cost.loc["deaths_averted_per_100k_per_year", "median"]
        cly = cost.loc["cost_per_life_year_usd"]
        checks += [
            (port_txt, f"{da:.0f}", "cost: deaths averted per 100k median"),
            (port_txt, f"{round(cly['median'], -3):,.0f}", "cost: cost per life-year median"),
            (port_txt, f"{round(cly['p2_5'], -3):,.0f}", "cost: cost per life-year 2.5%"),
            (port_txt, f"{round(cly['p97_5'], -3):,.0f}", "cost: cost per life-year 97.5%"),
        ]

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
