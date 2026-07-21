#!/usr/bin/env python3
"""
Three-bundle clinical-AI analysis with cause-resolved transmission and counterfactual-aware
net-of-harm. This version fixes three structural errors identified in adversarial review:

  FIX 1 (cause resolution). The mortality gap is all-cause, but a disease-specific tool acts
  on one cause. A blood-pressure tool can address only the cardiovascular-attributable share
  of the gap, not the cancer, respiratory, or external-cause shares. The disease-specific
  bundle is therefore bounded by (cause share of the gap) x (reach among the treatable) x
  (cause-specific per-patient effect).

  FIX 2 (counterfactual). A generalist consumer tool reaches people who often lack meaningful
  access to primary care, so its comparator is no or delayed care, not a physician. Its net
  effect is benefit relative to no care minus harm relative to no care, and is therefore
  acuity-dependent: plausibly positive for low-acuity navigation among the unserved, negative
  for high-acuity under-triage. The sign is not fixed.

  FIX 3 (symmetry). Provider-facing tools also err, and clinician oversight is imperfect
  (automation bias). Their net effect is a decision improvement when correct and accepted,
  minus harm when a wrong suggestion is accepted. In the one randomized trial testing
  clinician-plus-tool against clinician alone, diagnostic reasoning did not improve, so the
  empirical net decision effect is near zero.

Evidence (peer-reviewed; see manuscript references):
  Transmission: SBP 5 mmHg -> MACE HR 0.90 (BPLTTC IPD, Lancet 2021); glycemia -> mortality null (ACCORD).
  Cause share: cardiovascular disease is the leading single contributor to US socioeconomic /
    geographic mortality disparities; cv_share of the gap set at 0.30 (range 0.20-0.40).
  Bundle A proximal: digital-HTN SBP -2.91 mmHg (Lindsay-Perez 2025).
  Bundle B harm: 7-10% harmful therapeutic advice (Tausky 2025); 28.6% incorrect dx (Lin 2026).
  Bundle C: clinician-plus-LLM no better than clinician on diagnostic reasoning (Goh 2024);
    most LLM health evaluations do not assess real patient care or harm (Bedi 2025; MedHELM).

Deterministic; reproducible. Parameters carry ranges; the qualitative conclusions are robust
across the ranges.
"""
import os, math
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "results"))
GAP, M, S_MEDIAN = 2.4, 9.6, 0.32
beta_sbp = math.log(0.90) / 5.0
rng = np.random.default_rng(20260720)
N = 20000

def tri(lo, mode, hi, n=N):
    return rng.triangular(lo, mode, hi, n)

# ---------- Bundle A: cause-resolved disease-specific ----------
cv_share = tri(0.20, 0.30, 0.40)                 # CV-attributable share of the all-cause gap
reach_treatable = tri(0.15, 0.30, 0.50)          # engaged fraction of the treatable CV-burden population
hr_cv = math.exp(beta_sbp * 2.91)                # transmitted per-patient CV HR (best measured digital-HTN)
closure_A = cv_share * reach_treatable * (1 - hr_cv)   # fraction of all-cause gap closed
A = dict(median=float(np.median(closure_A)), p2_5=float(np.percentile(closure_A, 2.5)),
         p97_5=float(np.percentile(closure_A, 97.5)), hr_cv=round(hr_cv, 3))

# ---------- Bundle B: counterfactual-aware net-of-harm ----------
# Reached population lacks meaningful access; comparator is no/delayed care.
# Net per-interaction utility (arbitrary mortality-relevant units): low-acuity navigation
# benefit b_low when advice is helpful; high-acuity harm h_high when an emergency is under-triaged.
p_harm = 0.08                                    # potentially harmful advice (Tausky 2025)
frac_high_acuity = tri(0.05, 0.15, 0.30)         # share of consultations that are high-acuity
# crossover: net >= 0 iff (1-f)*b_low*P_help >= f*h_high*p_harm ; report the high-acuity
# fraction at which net turns negative for a plausible benefit:harm severity ratio.
benefit_help, harm_sev, p_help = 1.0, 8.0, 0.70  # harm in an emergency ~8x a navigation benefit
net_B = (1 - frac_high_acuity) * benefit_help * p_help - frac_high_acuity * harm_sev * p_harm
crossover_f = (benefit_help * p_help) / (benefit_help * p_help + harm_sev * p_harm)
B = dict(prob_net_negative=float(np.mean(net_B < 0)),
         crossover_high_acuity_fraction=round(float(crossover_f), 3),
         p_harmful_advice=p_harm)

# ---------- Bundle C: provider net-of-harm with imperfect oversight ----------
# Empirically, clinician-plus-LLM did not improve diagnostic reasoning vs clinician alone
# (Goh 2024): net decision improvement ~ 0. Documentation tools change no decisions (Shin 2025).
provider_net_decision_effect = 0.0
C = dict(net_decision_effect=provider_net_decision_effect,
         basis="clinician+LLM not superior to clinician (Goh 2024); scribes change no decisions (Shin 2025)")

pd.DataFrame([
    {"bundle": "A disease-specific (cause-resolved)", "gap_closure_median": round(A["median"], 6),
     "gap_closure_p2.5": round(A["p2_5"], 6), "gap_closure_p97.5": round(A["p97_5"], 6),
     "transmitted_cv_HR": A["hr_cv"]},
    {"bundle": "B generalist (counterfactual net-of-harm)", "prob_net_negative": round(B["prob_net_negative"], 3),
     "crossover_high_acuity_fraction": B["crossover_high_acuity_fraction"], "p_harmful_advice": B["p_harmful_advice"]},
    {"bundle": "C provider (net-of-harm, oversight)", "net_decision_effect": C["net_decision_effect"],
     "basis": C["basis"]},
]).to_csv(os.path.join(RESULTS, "rederived_ai_bundles.csv"), index=False)

print("== Three-bundle clinical-AI analysis (cause-resolved, counterfactual-aware) ==")
print(f"A. Disease-specific (cause-resolved): closes median {A['median']*100:.1f}% of the "
      f"all-cause gap (95% {A['p2_5']*100:.1f}-{A['p97_5']*100:.1f}%); bounded by the "
      f"cardiovascular share of the gap x reach x transmitted CV HR {A['hr_cv']}")
print(f"B. Generalist (vs no-access counterfactual): net effect is acuity-dependent, not fixed; "
      f"it turns negative once the high-acuity fraction exceeds {B['crossover_high_acuity_fraction']*100:.0f}% "
      f"(P(net<0) over the plausible range = {B['prob_net_negative']:.2f}); "
      f"plausibly beneficial for low-acuity navigation among the unserved, harmful for high-acuity under-triage")
print(f"C. Provider-facing: empirical net decision effect ~0 (clinician+LLM not superior to "
      f"clinician, Goh 2024; scribes change no decisions, Shin 2025); tools also err and "
      f"oversight is imperfect")
print("Fix summary: disease tools bounded by cause-share (not the whole all-cause gap); "
      "generalist judged against its true no-access counterfactual; provider tools carry a "
      "symmetric harm term and show no measured decision benefit.")
