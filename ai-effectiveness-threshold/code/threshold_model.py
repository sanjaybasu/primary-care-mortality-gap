#!/usr/bin/env python3
"""
Recentered AI-effectiveness threshold model.

Question: primary-care supply is eroding. What per-patient effect and reach would clinical AI
need to (1) offset the mortality attributable to that erosion and (2) do so without widening the
mortality difference between high- and low-vulnerability communities?

Target: the primary-care-supply-attributable excess mortality, NOT the poverty-driven Social
Vulnerability Index mortality gap. Basu 2019 estimates primary-care density's effect on life
expectancy at about one-fifth that of poverty, and found the supply decline was NOT
disproportionate by county poverty or race, but was concentrated in rural areas. We therefore
apply the national decline uniformly by vulnerability (the attributable excess is proportional
to baseline mortality) and locate inequality in the REACH gradient. Framework: NASEM 2021.

Identity:
  epsilon = sum_cause (cause_share * cause_reduction_per_10pcp)          [Basu 2019]
  delta   = epsilon * (decline_per_100k / 10)   = relative all-cause mortality rise from the loss
  D_k     = delta * m_k    (attributable excess mortality per 1,000 in stratum k)
  Offset requires  m_k * r_k * (1 - HR) >= D_k, so the required per-patient effect is
      HR_required(r) = 1 - delta / r .
  Equity (do not widen the high-vs-low differential) for a tool with per-patient effect HR:
      (1 - HR) * (m_high * r_high - m_low * r_low) >= D_high - D_low ,
  which sets the high-vulnerability reach needed to prevent net widening.

Deterministic (fixed seed); reproducible; auditable (inputs.json sourced; provenance written).
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


def main():
    with open(os.path.join(HERE, "inputs.json"), "rb") as f:
        raw = f.read()
    inp = json.loads(raw); ihash = hashlib.sha256(raw).hexdigest()[:16]
    mort = inp["mortality"]; sup = inp["pcp_supply"]; el = inp["mortality_elasticity"]
    reach = inp["ai_reach"]; bm = inp["benchmarks"]
    m = {"high": mort["high_vuln_per_1000"], "low": mort["low_vuln_per_1000"]}
    eps = elasticity(el)
    dec = sup["decline_per_100k"]
    r = {"high": reach["high_vuln"]["point"], "low": reach["low_vuln"]["point"]}
    delta_pt = eps * (dec / 10.0)                     # uniform relative mortality rise

    # ---- point estimates by stratum ----
    rows = []
    for k in ("high", "low"):
        Dk = delta_pt * m[k]
        rows.append({"stratum": k, "baseline_mortality_per_1000": m[k],
                     "attributable_excess_per_1000": round(Dk, 4),
                     "required_HR_to_offset_at_point_reach": round(1 - delta_pt / r[k], 4)})
    by = pd.DataFrame(rows).set_index("stratum")
    by.to_csv(os.path.join(RESULTS, "rederived_threshold_by_stratum.csv"))
    D_high = by.loc["high", "attributable_excess_per_1000"]
    D_low = by.loc["low", "attributable_excess_per_1000"]

    # ---- equity: high-vuln reach needed so a demonstrated effect does not widen the gap ----
    def reach_high_to_not_widen(hr_dem, r_low=r["low"]):
        need = (D_high - D_low) / (1 - hr_dem) + m["low"] * r_low
        return need / m["high"]
    eq_rows = []
    for name, hr_dem in [("digital_htn_transmitted", bm["digital_htn_transmitted_hr"])]:
        rhi = reach_high_to_not_widen(hr_dem)
        eq_rows.append({"demonstrated_tool": name, "demonstrated_HR": hr_dem,
                        "high_vuln_reach_needed_to_not_widen": round(rhi, 3),
                        "current_high_vuln_reach": r["high"],
                        "widens_gap_at_current_reach": bool(rhi > r["high"])})
    pd.DataFrame(eq_rows).to_csv(os.path.join(RESULTS, "rederived_threshold_equity.csv"), index=False)

    # ---- PSA over elasticity and reach ----
    n = inp["psa"]["n_draws"]; seed = inp["psa"]["seed"]
    rng = np.random.default_rng(seed)
    eps_d = rng.uniform(el["elasticity_range_per10_allcause"]["low"],
                        el["elasticity_range_per10_allcause"]["high"], n)
    dr = sup["decline_range"]
    dec_d = rng.uniform(dr["low"], dr["high"], n)
    rh = reach["high_vuln"]; rl = reach["low_vuln"]
    r_hi = rng.triangular(rh["low"], rh["point"], rh["high"], n)
    r_lo = rng.triangular(rl["low"], rl["point"], rl["high"], n)
    delta_d = eps_d * (dec_d / 10.0)
    hr_req_hi = 1 - delta_d / r_hi
    Dh = delta_d * m["high"]; Dl = delta_d * m["low"]
    hr_dem = bm["digital_htn_transmitted_hr"]
    offsets_high = (m["high"] * r_hi * (1 - hr_dem)) >= Dh
    narrows = ((1 - hr_dem) * (m["high"] * r_hi - m["low"] * r_lo)) >= (Dh - Dl)
    summ = {
        "elasticity_per10_allcause_point": round(eps, 5),
        "attributable_excess_high_per_1000": D_high,
        "attributable_excess_low_per_1000": D_low,
        "required_HR_high_point": round(1 - delta_pt / r["high"], 4),
        "required_HR_low_point": round(1 - delta_pt / r["low"], 4),
        "required_HR_high_median": round(float(np.median(hr_req_hi)), 4),
        "required_HR_high_p2.5": round(float(np.percentile(hr_req_hi, 2.5)), 4),
        "required_HR_high_p97.5": round(float(np.percentile(hr_req_hi, 97.5)), 4),
        "prob_demonstrated_effect_offsets_high": round(float(np.mean(offsets_high)), 3),
        "prob_AI_narrows_gap_at_current_reach": round(float(np.mean(narrows)), 3),
    }
    np.save(os.path.join(RESULTS, "rederived_threshold_psa_draws.npy"), hr_req_hi)

    # ---- reach grid: required HR to offset the loss vs reach ----
    reach_grid = np.round(np.arange(0.05, 1.0001, 0.05), 2)
    grid = [{"reach": float(rr), "required_HR_to_offset": round(1 - delta_pt / rr, 4)}
            for rr in reach_grid]
    pd.DataFrame(grid).to_csv(os.path.join(RESULTS, "rederived_threshold_reach_grid.csv"), index=False)

    # ---- sensitivity 1: rural vs urban concentration of the loss ----
    ru = []
    for locale, d in [("rural", sup["rural_decline_per_100k"]),
                      ("urban", sup["urban_decline_per_100k"])]:
        dloc = eps * (d / 10.0)
        ru.append({"locale": locale, "supply_decline_per_100k": d,
                   "rel_mortality_increase": round(dloc, 5),
                   "attributable_excess_per_1000_at_high_vuln_mortality": round(dloc * m["high"], 4)})
    pd.DataFrame(ru).to_csv(os.path.join(RESULTS, "rederived_threshold_rural_urban.csv"), index=False)

    # ---- sensitivity 2: NASEM/AAMC adequacy reference point ----
    short = inp["adequacy_sensitivity"]["shortage_per_100k"]
    d_ade = eps * (short / 10.0)
    ade = [{"reference": "NASEM/AAMC adequacy (shortage)", "shortage_per_100k": short,
            "rel_mortality_increase": round(d_ade, 5),
            "attributable_excess_high_per_1000": round(d_ade * m["high"], 4),
            "required_HR_high_at_point_reach": round(1 - d_ade / r["high"], 4)}]
    pd.DataFrame(ade).to_csv(os.path.join(RESULTS, "rederived_threshold_adequacy.csv"), index=False)

    # ---- capacity pathway: required per-physician throughput increase ----
    # If AI raises each remaining physician's effective patient throughput by theta, the
    # physician-equivalent capacity added is theta * P1 (current supply per 100k). Setting this
    # equal to the supply lost, S, gives theta = S / P1. This assumes the supply-mortality
    # elasticity applies symmetrically to throughput-derived capacity, not just headcount; we
    # state that assumption explicitly in the manuscript rather than embed it silently here.
    P1 = sup["current_per_100k"]
    ade_inp = inp["adequacy_sensitivity"]
    cap_rows = []
    for scenario, S, S_range in [
        ("realized_decline", dec, (dr["low"], dr["high"])),
        ("projected_shortfall", short, (ade_inp["shortage_range_low"], ade_inp["shortage_range_high"])),
    ]:
        theta = S / P1
        theta_lo = S_range[0] / P1
        theta_hi = S_range[1] / P1
        cap_rows.append({"scenario": scenario, "supply_loss_per_100k": S,
                          "current_supply_per_100k": P1,
                          "required_throughput_increase": round(theta, 4),
                          "required_throughput_increase_range_low": round(theta_lo, 4),
                          "required_throughput_increase_range_high": round(theta_hi, 4)})
    pd.DataFrame(cap_rows).to_csv(os.path.join(RESULTS, "rederived_threshold_capacity.csv"), index=False)

    # ---- write summary + provenance ----
    pd.DataFrame([{"metric": k, "value": v} for k, v in summ.items()]
                 ).to_csv(os.path.join(RESULTS, "rederived_threshold_summary.csv"), index=False)
    prov = {"model": "Recentered PC-attributable AI threshold", "inputs_sha256_16": ihash,
            "seed": seed, "n_draws": n, "python": platform.python_version(),
            "numpy": np.__version__, "pandas": pd.__version__,
            "generated_utc": os.environ.get("REDERIVE_TS", "set REDERIVE_TS for stamped run")}
    with open(os.path.join(RESULTS, "rederived_threshold_provenance.json"), "w") as f:
        json.dump(prov, f, indent=2)

    # ---- console ----
    print("== Recentered PC-attributable AI threshold ==")
    print(f"inputs {ihash} | seed {seed} | draws {n}")
    print(f"all-cause mortality elasticity: {eps*100:.2f}% per 10 PCP/100k")
    print(f"national supply decline: {dec} per 100k (46.6->41.4, Basu 2019); uniform by poverty")
    print(f"relative mortality rise from the loss: {delta_pt*100:.2f}%")
    print(f"attributable excess: high-vuln {D_high:.3f}/1,000, low-vuln {D_low:.3f}/1,000")
    print(f"required per-patient HR to offset at point reach: high {summ['required_HR_high_point']} "
          f"(r={r['high']}), low {summ['required_HR_low_point']} (r={r['low']})")
    print(f"required HR high (PSA median, 95%): {summ['required_HR_high_median']} "
          f"({summ['required_HR_high_p2.5']}-{summ['required_HR_high_p97.5']})")
    print(f"P(demonstrated digital-hypertension-level effect {bm['digital_htn_transmitted_hr']} offsets the high-vuln loss): "
          f"{summ['prob_demonstrated_effect_offsets_high']}")
    print(f"P(AI narrows the gap at current reach gradient): "
          f"{summ['prob_AI_narrows_gap_at_current_reach']}")
    print("Equity - high-vuln reach needed so a demonstrated effect does not widen the gap:")
    for row in eq_rows:
        print(f"  {row['demonstrated_tool']:<26} (HR {row['demonstrated_HR']}): reach >= "
              f"{row['high_vuln_reach_needed_to_not_widen']} (current {row['current_high_vuln_reach']}; "
              f"{'WIDENS' if row['widens_gap_at_current_reach'] else 'ok'})")
    print(f"Rural loss -7.0 vs urban -2.6 per 100k -> attributable excess concentrates rural.")


if __name__ == "__main__":
    main()
