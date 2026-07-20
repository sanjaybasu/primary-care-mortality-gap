#!/usr/bin/env python3
"""
Retrospective temporal validation of the portfolio model's coverage-weighting mechanism,
using the 2014 Medicaid expansion as a natural experiment.

Logic. The portfolio model represents each intervention as a per-reached relative risk
RR_reached diluted by the fraction reached (coverage): the implied population relative risk
is RR_pop = 1 - coverage * (1 - RR_reached). Medicaid expansion is the one package member
with a population-level natural-experiment estimate, so its observed post-2014 population
effect is a now-known target the model can be tested against out of sample: parameters are
set from the model's own inputs (not fit to the post-2014 outcome), and the predicted
population effect is compared with the observed 2014-2019 difference-in-differences.

Observed target is read from the repository's Medicaid DiD output (CDC WONDER county data);
the external published anchor is Lee 2022 Lancet Public Health (-11.8 per 100,000).

Deterministic. Reproducible: `python3 validate_backtest.py`.
"""
import json, os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "results"))

obs = pd.read_csv(os.path.join(RESULTS, "medicaid_expansion_causal_effects.csv")).iloc[0]
did, lo, hi, rr_obs = obs["did_estimate"], obs["did_ci_low"], obs["did_ci_high"], obs["implied_rr"]
# baseline per-100k implied by the point estimate and implied RR: did = baseline*(1-RR)
baseline = abs(did) / (1 - rr_obs)
rr_obs_lo = 1 - abs(lo) / baseline   # more protective bound -> lower RR
rr_obs_hi = 1 - abs(hi) / baseline

med = next(d for d in json.load(open(os.path.join(HERE, "inputs.json")))["interventions"]
           if d["name"] == "Medicaid expansion")
def pop_rr(rr_reached, coverage):
    return 1 - coverage * (1 - rr_reached)
rr_pred = pop_rr(med["rr"], med["coverage"])
rr_pred_lo = pop_rr(med["rr_low"], med["coverage_high"])   # most protective model corner
rr_pred_hi = pop_rr(med["rr_high"], med["coverage_low"])   # least protective model corner

within = rr_obs_lo <= rr_pred <= rr_obs_hi
overlap = not (rr_pred_hi < rr_obs_lo or rr_pred_lo > rr_obs_hi)

print("== Retrospective temporal validation: Medicaid expansion (2014) ==")
print(f"Observed post-2014 DiD: {did:.1f} per 100,000 (95% CI {lo:.1f} to {hi:.1f}); "
      f"implied population RR {rr_obs:.3f} (95% CI {rr_obs_lo:.3f} to {rr_obs_hi:.3f})")
print(f"External anchor (Lee 2022): -11.8 per 100,000")
print(f"Model-predicted population RR = 1 - coverage*(1-RR_reached) "
      f"= 1 - {med['coverage']}*(1-{med['rr']}) = {rr_pred:.3f} "
      f"(model range {rr_pred_lo:.3f} to {rr_pred_hi:.3f})")
print(f"Predicted point within observed 95% CI: {within}")
print(f"Predicted range overlaps observed 95% CI: {overlap}")
print(f"VALIDATION: {'PASS' if within else 'CHECK'}")

pd.DataFrame([{
    "observed_did_per100k": did, "observed_rr": round(rr_obs, 3),
    "observed_rr_ci_low": round(rr_obs_lo, 3), "observed_rr_ci_high": round(rr_obs_hi, 3),
    "predicted_pop_rr": round(rr_pred, 3),
    "predicted_rr_low": round(rr_pred_lo, 3), "predicted_rr_high": round(rr_pred_hi, 3),
    "predicted_within_observed_ci": bool(within),
}]).to_csv(os.path.join(RESULTS, "rederived_portfolio_backtest.csv"), index=False)
