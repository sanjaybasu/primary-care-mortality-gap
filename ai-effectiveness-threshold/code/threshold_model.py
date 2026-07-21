#!/usr/bin/env python3
"""
Paper E -- AI-effectiveness threshold model (transparent re-derivation).

Replaces the omnibus "HR approx 0.91 / five-fold" claim, which does NOT exist in the
pipeline (src/20 emits a `required_multiplier` in mixed units; no HR 0.91). See
notebooks/primary-care-world-model/RECONCILIATION_phase2.md.

Model (physician-legible):
  After the structural package closes fraction s of the 2.4/1,000 high-vuln mortality gap,
  the residual is  R = gap * (1 - s)  deaths per 1,000.
  A clinical AI agent reaches fraction r of the high-vulnerability population and lowers
  all-cause mortality among those reached by (1 - HR_ai). To close the residual:
      baseline_highvuln * r * (1 - HR_ai) = R
  Solve for the required AI effect:
      HR_ai = 1 - R / (baseline_highvuln * r)
  Required per-patient absolute risk reduction among reached = baseline * (1 - HR_ai).

Key output: required HR is a JOINT function of structural closure (s) and AI reach (r).
The omnibus's 0.91 corresponds to the optimistic corner (s=0.75, r=1.0); realistic values
imply a far more demanding requirement. Structural-closure uncertainty is propagated from
Paper F PSA draws.

Deterministic (fixed seed); reproducible (`python3 threshold_model.py`); auditable
(inputs_E.json sourced; provenance written).
"""
import json, hashlib, os, platform
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "results"))
os.makedirs(RESULTS, exist_ok=True)


def required_hr(structural_closure, reach, gap, baseline):
    """Required AI hazard ratio among reached to close the residual gap. Vectorized."""
    residual = gap * (1.0 - structural_closure)
    hr = 1.0 - residual / (baseline * reach)
    return hr  # values <=0 mean 'not achievable at this reach even at HR=0'


def main():
    with open(os.path.join(HERE, "inputs.json"), "rb") as f:
        raw = f.read()
    inp = json.loads(raw); ihash = hashlib.sha256(raw).hexdigest()[:16]
    gap = inp["gap"]["gap_per_1000"]; base = inp["gap"]["baseline_highvuln_per_1000"]
    reach = inp["ai_reach"]

    # ---- structural closure draws from portfolio model (propagate uncertainty) ----
    f_draws_path = os.path.join(RESULTS, "rederived_portfolio_psa_draws.npy")
    used_F = os.path.exists(f_draws_path)
    n = inp["psa"]["n_draws"]; seed = inp["psa"]["seed"]
    rng = np.random.default_rng(seed)
    if used_F:
        s_all = np.load(f_draws_path)
        s_draws = rng.choice(s_all, size=n, replace=True)
    else:
        s_draws = rng.triangular(0.25, 0.35, 0.50, n)  # fallback
    r_draws = np.clip(rng.triangular(reach["low"], reach["point"], reach["high"], n), 1e-6, 1.0)

    # ---- point estimate (F point closure 0.346 unknown here; use F median proxy) ----
    s_point = float(np.median(s_draws)); r_point = reach["point"]
    hr_point = float(required_hr(s_point, r_point, gap, base))

    # ---- PSA ----
    hr_draws = required_hr(s_draws, r_draws, gap, base)
    achievable = hr_draws > 0
    psa = {
        "required_hr_median": float(np.median(hr_draws)),
        "required_hr_p2.5": float(np.percentile(hr_draws, 2.5)),
        "required_hr_p97.5": float(np.percentile(hr_draws, 97.5)),
        "prob_requires_HR_below_0.90": float(np.mean(hr_draws < 0.90)),
        "prob_not_achievable_even_at_HR0 (reach too low)": float(np.mean(~achievable)),
    }

    # ---- driver analysis (ANCOVA-style variance decomposition of the required HR) ----
    # share of variance in the required HR attributable to structural closure vs reach,
    # via drop-in-R^2 when each input is removed from an OLS of hr on (s, r).
    ok = achievable
    y = hr_draws[ok]; ss = s_draws[ok]; rr = r_draws[ok]
    def r2(cols):
        X = np.column_stack([np.ones_like(y)] + cols)
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        return 1 - np.sum(resid**2) / np.sum((y - y.mean())**2)
    r2_full = r2([ss, rr]); r2_wo_s = r2([rr]); r2_wo_r = r2([ss])
    contrib_s = max(r2_full - r2_wo_s, 0.0); contrib_r = max(r2_full - r2_wo_r, 0.0)
    tot = contrib_s + contrib_r if (contrib_s + contrib_r) > 0 else 1.0
    drivers = {"r2_full": round(float(r2_full), 3),
               "variance_share_reach": round(float(contrib_r / tot), 3),
               "variance_share_structural_closure": round(float(contrib_s / tot), 3)}
    pd.DataFrame([drivers]).to_csv(os.path.join(RESULTS, "rederived_threshold_drivers.csv"), index=False)

    # ---- scenario grid: required HR by (structural closure x reach) ----
    grid_rows = []
    for s in inp["scenarios_for_grid"]["structural_closure"]:
        for r in inp["scenarios_for_grid"]["ai_reach"]:
            hr = float(required_hr(s, r, gap, base))
            grid_rows.append({"structural_closure": s, "ai_reach": r,
                              "required_HR": round(hr, 3),
                              "required_abs_reduction_per1000_among_reached":
                                  round(base * (1 - hr), 2) if hr > 0 else None,
                              "achievable_(HR>0)": hr > 0})
    grid = pd.DataFrame(grid_rows)

    # ---- one-way sensitivity (tornado) of the required HR ----
    # Each input is moved across its range with the others held at the point/median.
    # Reach and structural closure carry documented ranges (inputs range; portfolio PSA
    # 2.5-97.5th percentiles); the epidemiologic gap and baseline carry a +/-15% structural
    # sensitivity range (SENS_REL), documented as such in the appendix (not a statistical CI).
    SENS_REL = 0.15
    s_lo, s_hi = float(np.percentile(s_draws, 2.5)), float(np.percentile(s_draws, 97.5))
    tornado_specs = [
        ("AI reach", "reach", reach["low"], reach["high"]),
        ("structural gap closure", "structural_closure", s_lo, s_hi),
        ("mortality gap (per 1,000)", "gap", gap * (1 - SENS_REL), gap * (1 + SENS_REL)),
        ("high-vulnerability mortality (per 1,000)", "baseline",
         base * (1 - SENS_REL), base * (1 + SENS_REL)),
    ]
    tornado = []
    for label, key, lo, hi in tornado_specs:
        vals = {"structural_closure": s_point, "reach": r_point, "gap": gap, "baseline": base}
        row = {"parameter": label, "low_value": round(lo, 3), "high_value": round(hi, 3)}
        for bound, v in [("required_HR_at_low", lo), ("required_HR_at_high", hi)]:
            vv = dict(vals); vv[key] = v
            hr = float(required_hr(vv["structural_closure"], vv["reach"], vv["gap"], vv["baseline"]))
            row[bound] = round(hr, 3) if hr > 0 else None
        tornado.append(row)
    pd.DataFrame(tornado).to_csv(os.path.join(RESULTS, "rederived_threshold_tornado.csv"), index=False)

    # ---- attainability curve: required HR vs reach, with structural-closure band ----
    reach_grid = np.round(np.arange(0.10, 1.0001, 0.05), 2)
    att_rows = []
    for r in reach_grid:
        att_rows.append({
            "reach": float(r),
            "required_HR_median_closure": round(float(required_hr(s_point, r, gap, base)), 3),
            "required_HR_low_closure": round(float(required_hr(s_lo, r, gap, base)), 3),
            "required_HR_high_closure": round(float(required_hr(s_hi, r, gap, base)), 3),
        })
    att = pd.DataFrame(att_rows)
    # reach at which a demonstrated/transmitted effect would suffice (required HR >= demonstrated HR)
    bm = inp["benchmarks"]
    attain_reach = {}
    for name, hr_dem in [("community_health_worker", bm["community_health_worker_hr"]),
                         ("best_transmitted_digital_htn", 0.93),
                         ("current_clinical_ai", bm["current_clinical_ai_hr"])]:
        # smallest reach on a fine grid where required HR (median closure) is >= demonstrated HR
        fine = np.round(np.arange(0.05, 1.0001, 0.001), 3)
        req = required_hr(s_point, fine, gap, base)
        ok = np.where(req >= hr_dem)[0]
        attain_reach[name] = float(fine[ok[0]]) if len(ok) else None
    att.to_csv(os.path.join(RESULTS, "rederived_threshold_attainability.csv"), index=False)

    # ---- formal scenario analysis (base / optimistic / pessimistic) ----
    scen = [
        {"scenario": "pessimistic", "structural_closure": round(s_lo, 3), "reach": reach["low"]},
        {"scenario": "base case", "structural_closure": round(s_point, 3), "reach": reach["point"]},
        {"scenario": "optimistic", "structural_closure": 0.50, "reach": reach["high"]},
    ]
    for sc in scen:
        hr = float(required_hr(sc["structural_closure"], sc["reach"], gap, base))
        sc["required_HR"] = round(hr, 3) if hr > 0 else None
        sc["required_abs_reduction_per1000_among_reached"] = round(base * (1 - hr), 2) if hr > 0 else None
    pd.DataFrame(scen).to_csv(os.path.join(RESULTS, "rederived_threshold_scenarios.csv"), index=False)

    # ---- write ----
    prov = {"model": "AI-effectiveness threshold (transparent re-derivation)",
            "inputs_sha256_16": ihash, "seed": seed, "n_draws": n,
            "consumed_portfolio_psa": used_F,
            "python": platform.python_version(), "numpy": np.__version__,
            "generated_utc": os.environ.get("REDERIVE_TS", "set REDERIVE_TS for stamped run")}
    pd.DataFrame([{"metric": "point_required_HR (F median closure, reach=0.30)", "value": hr_point},
                  *[{"metric": k, "value": v} for k, v in psa.items()]]
                 ).to_csv(os.path.join(RESULTS, "rederived_threshold_summary.csv"), index=False)
    grid.to_csv(os.path.join(RESULTS, "rederived_threshold_scenario_grid.csv"), index=False)
    np.save(os.path.join(RESULTS, "rederived_threshold_psa_draws.npy"), hr_draws)
    with open(os.path.join(RESULTS, "rederived_threshold_provenance.json"), "w") as f:
        json.dump(prov, f, indent=2)

    print("== Paper E AI-threshold re-derivation ==")
    print(f"inputs hash {ihash} | seed {seed} | consumed Paper F PSA: {used_F}")
    print(f"POINT required AI HR (structural closure={s_point:.2f}, reach={r_point}): {hr_point:.2f}")
    print(f"PSA required HR median (95% interval): {psa['required_hr_median']:.2f} "
          f"({psa['required_hr_p2.5']:.2f} to {psa['required_hr_p97.5']:.2f})")
    print(f"P(requires HR < 0.90) = {psa['prob_requires_HR_below_0.90']:.2f}")
    print(f"Driver analysis: reach explains {drivers['variance_share_reach']*100:.0f}% and "
          f"structural closure {drivers['variance_share_structural_closure']*100:.0f}% of "
          f"variance in the required HR (full R^2 {drivers['r2_full']:.2f})")
    print("Scenario grid (required AI HR among reached):")
    piv = grid.pivot(index="structural_closure", columns="ai_reach", values="required_HR")
    print(piv.to_string())
    print("Note: HR<=0 (blank/negative) = residual not closable by AI at that reach even at HR=0.")
    print("\nOne-way sensitivity (required HR, others at point):")
    for t in tornado:
        print(f"  {t['parameter']:<42} [{t['low_value']}, {t['high_value']}] -> "
              f"HR {t['required_HR_at_low']} .. {t['required_HR_at_high']}")
    print("\nAttainability (smallest reach at which a demonstrated effect suffices, median closure):")
    for k, v in attain_reach.items():
        print(f"  {k:<32} reach {'>1.0 (not attainable)' if v is None else v}")
    print("\nScenario analysis:")
    for sc in scen:
        print(f"  {sc['scenario']:<12} s={sc['structural_closure']}, r={sc['reach']} -> "
              f"required HR {sc['required_HR']}, abs reduction "
              f"{sc['required_abs_reduction_per1000_among_reached']}/1000")


if __name__ == "__main__":
    main()
