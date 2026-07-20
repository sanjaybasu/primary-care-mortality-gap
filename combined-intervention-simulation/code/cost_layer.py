#!/usr/bin/env python3
"""
Supplementary, illustrative cost layer for the combined-intervention portfolio (CHEERS
items 14, 20). Computes deaths averted and cost per death averted per 100,000
high-vulnerability population, from cited annual per-person-reached unit costs, with
probabilistic sensitivity analysis.

IMPORTANT (stated in the appendix and Discussion): this layer carries a joint-cost
limitation. Coverage-based programs, especially Medicaid expansion, produce benefits far
beyond closing this mortality gap; attributing their full per-person cost to gap closure
overstates cost per death averted. The layer is therefore an upper-bound, illustrative
analysis, not a headline cost-effectiveness estimate.

Deterministic (fixed seed). Reproducible: `python3 cost_layer.py`. Every unit cost is
sourced in unit_costs.json.
"""
import json, os, hashlib
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "results"))

UNIT = {
    "_meta": "Annual USD per person reached, with source and a +/-50% PSA range. Joint-cost "
             "limitation applies (see module docstring).",
    "Medicaid expansion": {"cost": 6500, "source": "KFF Medicaid per-enrollee spending, adults (approx.)"},
    "Community health workers": {"cost": 1700, "source": "Basu 2024 J Community Health, ~$140 PMPM capitated"},
    "Integrated behavioral health": {"cost": 500, "source": "CMS Collaborative Care (CoCM) G-code annual (approx.)"},
    "FQHC expansion": {"cost": 1200, "source": "HRSA UDS incremental per-patient (approx.)"},
    "Physician workforce (+10 PCP/100k)": {"cost_per_capita": 30,
        "source": "10 PCPs/100k x ~$300k loaded annual cost / 100k population"},
}
LIFE_YEARS_PER_DEATH = {"point": 12.0, "low": 8.0, "high": 16.0,
    "note": "Life-years gained per premature death averted in high-vulnerability adults (approx.)."}
SEED, NDRAWS = 20260720, 20000


def main():
    inp = json.load(open(os.path.join(HERE, "inputs.json")))
    ihash = hashlib.sha256(json.dumps(UNIT, sort_keys=True).encode()).hexdigest()[:16]
    gap = inp["gap"]["gap_per_1000"]
    ivs = {d["name"]: d for d in inp["interventions"]}
    psa_closure = np.load(os.path.join(RESULTS, "rederived_portfolio_psa_draws.npy"))

    rng = np.random.default_rng(SEED)
    n = NDRAWS
    closure = rng.choice(psa_closure, size=n, replace=True)
    deaths_averted_per100k = 100.0 * gap * closure  # per 100k high-vuln population per year

    # package cost per 100k population per year
    cost = np.zeros(n)
    for name, d in ivs.items():
        u = UNIT[name]
        if "cost_per_capita" in u:
            unit_cost = rng.uniform(u["cost_per_capita"]*0.5, u["cost_per_capita"]*1.5, n)
            cost += unit_cost * 100000
        else:
            unit_cost = rng.uniform(u["cost"]*0.5, u["cost"]*1.5, n)
            cov = np.clip(rng.triangular(d["coverage_low"], d["coverage"], d["coverage_high"], n)
                          if d["coverage_high"] > d["coverage_low"] else np.full(n, d["coverage"]),
                          1e-6, 1.0)
            cost += unit_cost * cov * 100000

    ly = rng.triangular(LIFE_YEARS_PER_DEATH["low"], LIFE_YEARS_PER_DEATH["point"],
                        LIFE_YEARS_PER_DEATH["high"], n)
    cost_per_death = cost / np.maximum(deaths_averted_per100k, 1e-9)
    cost_per_ly = cost_per_death / ly

    def summ(x):
        return dict(median=float(np.median(x)), p2_5=float(np.percentile(x, 2.5)),
                    p97_5=float(np.percentile(x, 97.5)))
    out = {"deaths_averted_per_100k_per_year": summ(deaths_averted_per100k),
           "package_cost_per_100k_per_year_usd": summ(cost),
           "cost_per_death_averted_usd": summ(cost_per_death),
           "cost_per_life_year_usd": summ(cost_per_ly)}
    rows = []
    for k, v in out.items():
        rows.append({"metric": k, **v})
    pd.DataFrame(rows).to_csv(os.path.join(RESULTS, "rederived_portfolio_cost.csv"), index=False)
    json.dump({"unit_costs_hash": ihash, "seed": SEED, "n_draws": n,
               "life_years_per_death": LIFE_YEARS_PER_DEATH},
              open(os.path.join(RESULTS, "rederived_portfolio_cost_provenance.json"), "w"), indent=2)

    print("== Portfolio supplementary cost layer (illustrative, upper-bound) ==")
    print(f"unit-cost hash {ihash} | seed {SEED} | draws {n}")
    for k, v in out.items():
        print(f"{k}: median {v['median']:.0f} ({v['p2_5']:.0f} to {v['p97_5']:.0f})"
              if v['median'] > 100 else
              f"{k}: median {v['median']:.1f} ({v['p2_5']:.1f} to {v['p97_5']:.1f})")
    print("Joint-cost limitation: Medicaid and other coverage benefits far exceed gap closure; "
          "cost per death averted is an upper bound.")


if __name__ == "__main__":
    main()
