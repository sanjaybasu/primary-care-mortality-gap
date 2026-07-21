#!/usr/bin/env python3
"""
AI-specific validation by extract-replicate-transmit.

Rather than assume a mortality effect for clinical AI, this module takes the effect sizes
actually measured in AI/digital intervention studies (the proximal effect), transmits them
to cardiovascular events through externally validated coefficients from cardiovascular
outcome trials, and compares the resulting per-patient effect with the threshold the
framework requires. This turns the framework's "current clinical AI hazard ratio ~ 1.00"
input into a derived, validated quantity.

Extracted evidence (all peer-reviewed; see manuscript references):
  Transmission (proximal -> cardiovascular events):
    SBP:  5-mmHg systolic reduction -> MACE HR 0.90  (BPLTTC IPD meta-analysis, 48 trials,
          344,716 participants; Blood Pressure Lowering Treatment Trialists' Collaboration, Lancet 2021, doi:10.1016/S0140-6736(21)00590-0)
    LDL:  1 mmol/L reduction -> major vascular event rate ratio 0.78  (CTT methodology;
          Cholesterol Treatment Trialists' (CTT) Collaboration, Lancet 2010, doi:10.1016/S0140-6736(10)61350-5)
  Replicated AI/digital proximal effects:
    Digital hypertension programs -> SBP  -2.91 mmHg (17 RCTs; Lindsay-Perez et al.,
          J Hum Hypertens 2025, doi:10.1038/s41371-025-01051-3)  and
          -1.45 mmHg (26 RCTs, 33,826 patients; Motta-Yanac et al., Int J Med Inform 2024,
          doi:10.1016/j.ijmedinf.2024.105755)
    Ambient AI scribe -> no change in clinician efficiency or output (pajama time, note
          time, wRVUs) (RCT; Shin et al., Appl Clin Inform 2025, doi:10.1055/a-2657-8087)
          => transmission to mortality ~ 0.

Note: the SBP->MACE transmission bounds the all-cause mortality effect from below in
magnitude (all-cause mortality responds less than MACE to blood-pressure lowering), so the
derived hazard ratios here are an UPPER bound on the achievable all-cause mortality effect,
i.e., favorable to AI.

Deterministic. Reproducible: `python3 validate_ai_transmission.py`.
"""
import json, os, math
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "results"))
GAP, M = 2.4, 9.6                      # mortality gap and high-vulnerability mortality per 1,000
S_MEDIAN = 0.32                        # structural gap closure (portfolio median)

SBP_MACE_HR_PER5 = 0.90                # BPLTTC IPD meta-analysis (Lancet 2021): ~10% per 5 mmHg
beta_sbp = math.log(SBP_MACE_HR_PER5) / 5.0   # per-mmHg log hazard

def hr_from_sbp(delta_sbp_mmHg):       # delta given as positive reduction
    return math.exp(beta_sbp * delta_sbp_mmHg)

def required_hr(s, r):
    return 1 - GAP * (1 - s) / (M * r)

# --- disease-management archetype: transmit replicated SBP effects ---
htn = {"Lindsay-Perez 2025 (17 RCTs)": 2.91, "Motta-Yanac 2024 (26 RCTs)": 1.45}
rows = []
for src, dsbp in htn.items():
    hr = hr_from_sbp(dsbp)
    rows.append({"archetype": "patient-facing disease management (hypertension)",
                 "proximal_effect": f"SBP -{dsbp} mmHg", "source": src,
                 "transmitted_HR_MACE_among_reached": round(hr, 3)})
best_hr = min(hr_from_sbp(d) for d in htn.values())   # most favorable to AI

# scribe archetype: measured null on efficiency/output -> no transmission to mortality
rows.append({"archetype": "ambient documentation (scribe)",
             "proximal_effect": "no change in efficiency/output (Shin 2025 RCT)",
             "source": "Shin 2025", "transmitted_HR_MACE_among_reached": 1.000})

# --- compare best transmitted AI effect with the requirement ---
req_universal = required_hr(S_MEDIAN, 1.00)   # easiest case: universal reach
req_reach30 = required_hr(S_MEDIAN, 0.30)      # plausible reach
# SBP reduction that WOULD be needed to meet the universal-reach requirement
sbp_needed_universal = math.log(req_universal) / beta_sbp

pd.DataFrame(rows).to_csv(os.path.join(RESULTS, "rederived_ai_transmission.csv"), index=False)

print("== AI-specific validation: extract -> replicate -> transmit ==")
print(f"Transmission: 5-mmHg SBP reduction -> MACE HR {SBP_MACE_HR_PER5} (BPLTTC IPD, Lancet 2021)")
for r in rows:
    print(f"  {r['archetype']}: {r['proximal_effect']} -> HR {r['transmitted_HR_MACE_among_reached']} ({r['source']})")
print(f"Best transmitted disease-management HR among reached (favorable to AI): {best_hr:.3f}")
print(f"Required HR at structural closure {S_MEDIAN}: universal reach {req_universal:.2f}; reach 0.30 {req_reach30:.2f}")
meets_universal = best_hr <= req_universal
print(f"Best current AI meets even the universal-reach requirement: {meets_universal}")
print(f"SBP reduction needed to meet universal-reach requirement: {sbp_needed_universal:.1f} mmHg "
      f"(vs best measured {max(htn.values())} mmHg)")
print("Validation conclusion: current best measured clinical-AI effect, transmitted through "
      "validated coefficients, falls short of the requirement even under universal reach; "
      "documentation tools transmit ~0. The framework's HR~1.00 input for current clinical "
      "AI is therefore derived, not assumed.")
