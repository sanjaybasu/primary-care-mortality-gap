#!/usr/bin/env python3
"""
AI-effectiveness threshold model.

Question: primary care physician supply is falling. What per-patient effect and reach would
clinical AI need to (1) offset the mortality associated with that loss and (2) do so without
widening the mortality difference between high- and low-vulnerability communities?

Benchmark: the excess mortality associated with the supply loss (Basu 2019 elasticity), not the
poverty-driven Social Vulnerability Index mortality gap. Basu 2019 found the decline was not
disproportionate by county poverty or race, so the loss is applied uniformly by vulnerability
(excess proportional to baseline mortality) and inequality is located in the reach gradient.

Identity:
  epsilon = sum_cause (cause_share * cause_reduction_per_10pcp)          [Basu 2019]
  delta   = epsilon * (S / 10)        relative all-cause mortality rise from supply loss S
  D_k     = delta * m_k               excess mortality per 1,000 in stratum k
  Offset requires  m_k * r_k * (1 - HR) >= D_k, so HR_required(r) = 1 - delta / r,
  and the reach a given effect needs is r* = delta / (1 - HR).
  Equity (do not widen the absolute high-vs-low difference) for effect HR:
      (1 - HR) * (m_high * r_high - m_low * r_low) >= D_high - D_low .

Demonstrated effect (disease-specific AI for hypertension):
  SBP reduction from Ong 2026 (RCTs of AI-based mobile health; Lindsay-Perez 2025 non-AI digital
  programs as a comparison), transmitted to ALL-CAUSE mortality two ways:
  (a) cardiovascular-death pathway (base case; parallel to the cause-specific benchmark):
      HR = 1 - cv_share * (1 - HR_cvdeath_per5 ^ (SBP/5))     [BPLTTC 2021]
  (b) trial all-cause pathway (sensitivity): HR = RR_allcause_per10 ^ (SBP/10)   [Ettehad 2016]
  The BPLTTC major-cardiovascular-event HR is reported for reference only; it is not a
  mortality effect. Upper-bound scenario: the only randomized all-cause mortality effect of an AI
  tool (Lin 2024, AI-ECG alert, hospitalized patients), HR 0.83.

Deterministic under a fixed seed; inputs hashed; provenance written.
"""
import json, hashlib, os, platform
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "results"))
os.makedirs(RESULTS, exist_ok=True)


def elasticity(el):
    cs = el["cause_shares_of_all_cause"]; rd = el["per_10pcp_cause_specific_reduction"]
    return sum(cs[c] * rd[c] for c in rd)


def hr_cvdeath_path(sbp, hr_cv5, cv_share):
    return 1 - cv_share * (1 - hr_cv5 ** (sbp / 5.0))


def hr_allcause_trial_path(sbp, rr10):
    return rr10 ** (sbp / 10.0)


def main():
    with open(os.path.join(HERE, "inputs.json"), "rb") as f:
        raw = f.read()
    inp = json.loads(raw); ihash = hashlib.sha256(raw).hexdigest()[:16]
    mort = inp["mortality"]; sup = inp["pcp_supply"]; el = inp["mortality_elasticity"]
    reach = inp["ai_reach"]; ade = inp["adequacy_sensitivity"]; htn = inp["benchmarks"]["ai_htn"]; prox = inp["benchmarks"]["digital_htn_proxy"]; ub = inp["benchmarks"]["ai_mortality_upper_bound"]
    m = {"high": mort["high_vuln_per_1000"], "low": mort["low_vuln_per_1000"]}
    r = {"high": reach["high_vuln"]["point"], "low": reach["low_vuln"]["point"]}
    eps = elasticity(el)
    scen = {"realized": sup["decline_per_100k"], "projected": ade["shortage_per_100k"],
            "rural": sup["rural_decline_per_100k"]}
    delta = {k: eps * S / 10.0 for k, S in scen.items()}

    # ---- demonstrated effect, transmitted to all-cause mortality ----
    sbp = htn["sbp_reduction_mmHg"]
    hr_dem = {"cvdeath": hr_cvdeath_path(sbp, htn["cvdeath_hr_per_5mmHg"], htn["cv_share_of_deaths"]),
              "allcause_trial": hr_allcause_trial_path(sbp, htn["allcause_rr_per_10mmHg"]),
              "digital_proxy_cvdeath": hr_cvdeath_path(prox["sbp_reduction_mmHg"], htn["cvdeath_hr_per_5mmHg"], htn["cv_share_of_deaths"]),
              "inpatient_ai_upper_bound": ub["hr"]}
    hr_mace_reference = htn["mace_hr_per_5mmHg"] ** (sbp / 5.0)
    BASE = "cvdeath"

    def reach_to_not_widen(hr, d, r_low):
        dD = d * (m["high"] - m["low"])
        return (dD / (1 - hr) + m["low"] * r_low) / m["high"]

    # ---- deterministic results: scenario x transmission ----
    det = []
    for sk, d in delta.items():
        row = {"scenario": sk, "supply_loss_per_100k": scen[sk], "rel_mortality_rise": d,
               "excess_high_per_1000": d * m["high"], "excess_low_per_1000": d * m["low"],
               "required_HR_high_at_point_reach": 1 - d / r["high"],
               "required_HR_low_at_point_reach": 1 - d / r["low"],
               "required_HR_at_full_reach": 1 - d}
        for tk, h in hr_dem.items():
            row[f"{tk}_HR"] = h
            row[f"{tk}_meets_at_point_reach"] = bool(h <= 1 - d / r["high"])
            row[f"{tk}_reach_needed_to_match"] = d / (1 - h)
            row[f"{tk}_reach_needed_to_not_widen"] = reach_to_not_widen(h, d, r["low"])
        det.append(row)
    det = pd.DataFrame(det)
    det.to_csv(os.path.join(RESULTS, "threshold_deterministic.csv"), index=False)

    # equity threshold across the low-vulnerability reach range (realized decline)
    het = []
    for tk, h in hr_dem.items():
        for label, r_lo in [("low", reach["low_vuln"]["low"]), ("point", reach["low_vuln"]["point"]),
                            ("high", reach["low_vuln"]["high"])]:
            het.append({"transmission": tk, "low_vuln_reach_scenario": label, "low_vuln_reach": r_lo,
                        "high_vuln_reach_needed_to_not_widen": reach_to_not_widen(h, delta["realized"], r_lo)})
    pd.DataFrame(het).to_csv(os.path.join(RESULTS, "threshold_equity_heterogeneity.csv"), index=False)

    # ---- probabilistic sensitivity analysis ----
    n = inp["psa"]["n_draws"]; rng = np.random.default_rng(inp["psa"]["seed"])
    eps_d = rng.uniform(el["elasticity_range_per10_allcause"]["low"], el["elasticity_range_per10_allcause"]["high"], n)
    dec_d = rng.uniform(sup["decline_range"]["low"], sup["decline_range"]["high"], n)
    proj_d = rng.triangular(ade["shortage_range_low"], ade["shortage_per_100k"], ade["shortage_range_high"], n)
    rh, rl = reach["high_vuln"], reach["low_vuln"]
    r_hi = rng.triangular(rh["low"], rh["point"], rh["high"], n)
    r_lo = rng.triangular(rl["low"], rl["point"], rl["high"], n)
    lo, hi = htn["sbp_reduction_ci95"]
    sbp_d = np.clip(rng.normal(sbp, (hi - lo) / 3.92, n), 0, None)
    rlo, rhi_ = htn["allcause_rr_per_10mmHg_ci95"]
    rr10_d = np.exp(rng.normal(np.log(htn["allcause_rr_per_10mmHg"]), (np.log(rhi_) - np.log(rlo)) / 3.92, n))
    m_hi_d = rng.uniform(*mort["high_vuln_range"], n); m_lo_d = rng.uniform(*mort["low_vuln_range"], n)
    ulo, uhi = ub["ci95"]
    ub_d = np.exp(rng.normal(np.log(ub["hr"]), (np.log(uhi) - np.log(ulo)) / 3.92, n))
    hr_d = {"cvdeath": hr_cvdeath_path(sbp_d, htn["cvdeath_hr_per_5mmHg"], htn["cv_share_of_deaths"]),
            "allcause_trial": hr_allcause_trial_path(sbp_d, rr10_d),
            "inpatient_ai_upper_bound": ub_d}
    psa = {}
    for sk, S_d in [("realized", dec_d), ("projected", proj_d)]:
        d_d = eps_d * S_d / 10.0
        req = 1 - d_d / r_hi
        psa[f"{sk}_required_HR_high_median"] = float(np.median(req))
        psa[f"{sk}_required_HR_high_p2.5"] = float(np.percentile(req, 2.5))
        psa[f"{sk}_required_HR_high_p97.5"] = float(np.percentile(req, 97.5))
        Dh = d_d * m_hi_d; Dl = d_d * m_lo_d
        for tk, h in hr_d.items():
            meets = h <= req
            widens = (1 - h) * (m_hi_d * r_hi - m_lo_d * r_lo) < (Dh - Dl)
            psa[f"{sk}_{tk}_prob_meets_requirement"] = float(np.mean(meets))
            psa[f"{sk}_{tk}_prob_widens"] = float(np.mean(widens))
            ordered = r_hi < r_lo
            psa[f"{sk}_{tk}_prob_widens_given_lower_high_reach"] = float(np.mean(widens[ordered]))
            if True:
                psa[f"{tk}_HR_median"] = float(np.median(h))
                psa[f"{tk}_HR_p2.5"] = float(np.percentile(h, 2.5))
                psa[f"{tk}_HR_p97.5"] = float(np.percentile(h, 97.5))
        if sk == "realized":
            np.save(os.path.join(RESULTS, "threshold_psa_required_hr_realized.npy"), req)
            np.save(os.path.join(RESULTS, "threshold_psa_demonstrated_hr_cvdeath.npy"), hr_d["cvdeath"])
    psa["share_draws_high_reach_below_low_reach"] = float(np.mean(r_hi < r_lo))

    # reach needed (with uncertainty) and acceptability by reach
    accept = []
    for sk, S_d in [("realized", dec_d), ("projected", proj_d)]:
        d_d = eps_d * S_d / 10.0
        for tk, h in hr_d.items():
            need = d_d / np.clip(1 - h, 1e-12, None)
            psa[f"{sk}_{tk}_reach_needed_median"] = float(np.median(need))
            psa[f"{sk}_{tk}_reach_needed_p2.5"] = float(np.percentile(need, 2.5))
            psa[f"{sk}_{tk}_reach_needed_p97.5"] = float(np.percentile(need, 97.5))
            psa[f"{sk}_{tk}_prob_not_attainable"] = float(np.mean(need > 1))
            for rr in np.round(np.arange(0.01, 1.0001, 0.01), 2):
                accept.append({"scenario": sk, "transmission": tk, "reach": float(rr),
                               "prob_meets": float(np.mean(h <= 1 - d_d / rr))})
    pd.DataFrame(accept).to_csv(os.path.join(RESULTS, "threshold_acceptability.csv"), index=False)
    # equity: reach parity alone (AI's own effect does not widen the post-loss gap)
    psa["parity_reach_high_point"] = m["low"] * r["low"] / m["high"]

    # ---- reach grid ----
    grid = pd.DataFrame({"reach": np.round(np.arange(0.01, 1.0001, 0.01), 2)})
    for sk in ("realized", "projected"):
        grid[f"required_HR_{sk}"] = 1 - delta[sk] / grid["reach"]
    grid.to_csv(os.path.join(RESULTS, "threshold_reach_grid.csv"), index=False)

    # ---- capacity pathway ----
    P1 = sup["current_per_100k"]; phi_inp = inp["capacity_discount"]
    cap = []
    for sk, S, (Slo, Shi) in [("realized", scen["realized"], (sup["decline_range"]["low"], sup["decline_range"]["high"])),
                              ("projected", scen["projected"], (ade["shortage_range_low"], ade["shortage_range_high"]))]:
        for phi in np.round(np.linspace(phi_inp["range_low"], phi_inp["range_high"], 6), 2):
            cap.append({"scenario": sk, "phi": float(phi), "required_throughput": S / (P1 * phi),
                        "range_low": Slo / (P1 * phi), "range_high": Shi / (P1 * phi)})
    pd.DataFrame(cap).to_csv(os.path.join(RESULTS, "threshold_capacity.csv"), index=False)

    # ---- canonical summary ----
    canon = {"inputs_sha256_16": ihash, "seed": inp["psa"]["seed"], "n_draws": n,
             "elasticity_per10_allcause": eps, "base_transmission": BASE,
             "demonstrated_HR": hr_dem, "mace_HR_reference_not_mortality": hr_mace_reference,
             "deterministic": det.set_index("scenario").to_dict(orient="index"), "psa": psa,
             "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}
    with open(os.path.join(RESULTS, "threshold_canonical.json"), "w") as f:
        json.dump(canon, f, indent=2)

    print(f"inputs {ihash} | elasticity {eps*100:.3f}% per 10 PCP/100k")
    for tk, h in hr_dem.items():
        print(f"demonstrated all-cause HR ({tk}): {h:.4f}")
    print(f"(MACE reference, not mortality: {hr_mace_reference:.4f})")
    print(det.round(4).T.to_string())
    for k, v in psa.items():
        print(f"{k}: {v:.4f}")


if __name__ == "__main__":
    main()
