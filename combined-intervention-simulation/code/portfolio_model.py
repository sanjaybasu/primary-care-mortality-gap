#!/usr/bin/env python3
"""
Paper F -- Combined-intervention portfolio model (transparent re-derivation).

Replaces the omnibus "~75% gap closure" claim, which depended on non-reproducible,
mostly literature-synthesized HRs combined by an undocumented method (see
notebooks/primary-care-world-model/RECONCILIATION_phase2.md).

Model (physician-legible):
  Each structural intervention i reaches a fraction coverage_i of the high-vulnerability
  (SVI Q4) population and lowers all-cause mortality among those reached by (1 - rr_i).
  Its population-level relative mortality reduction is pr_i = coverage_i * (1 - rr_i).
  Interventions combine MULTIPLICATIVELY (avoids additive over-counting), with a
  diminishing-returns penalty lambda on the combined log relative-risk to reflect
  overlapping populations and shared causal pathways:
      logRR_combined = (1 - lambda) * sum_i log(1 - pr_i)
      RR_combined    = exp(logRR_combined)
  New high-vuln mortality = baseline_highvuln * RR_combined.
  Gap closed (fraction) = baseline_highvuln * (1 - RR_combined) / gap.

Outputs (all written to ../../results/, prefixed rederived_F_):
  - point estimate, PSA (median + 95% interval), one-way tornado, leave-one-out ablation
  - a provenance record (inputs hash, seed, versions, timestamp passed in)

Deterministic: fixed seed. Reproducible: `python3 portfolio_model.py`.
Auditable: every parameter sourced in inputs_F.json; every output carries the inputs hash.
"""
import json, hashlib, os, sys, platform
from datetime import datetime, timezone
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "results"))
os.makedirs(RESULTS, exist_ok=True)


def load_inputs(path=None):
    path = path or os.path.join(HERE, "inputs.json")
    with open(path, "rb") as f:
        raw = f.read()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()[:16]


def lognormal_sd_from_ci(point, lo, hi):
    """SD on the log scale from a 95% CI, assuming lognormal rr."""
    return (np.log(hi) - np.log(lo)) / (2 * 1.959964)


def closure_fraction(rr, coverage, lam, gap, baseline):
    """Core deterministic transform. Vectorized over draws (arrays) or scalars."""
    pr = coverage * (1.0 - rr)                       # per-intervention pop reduction
    log_rr = np.sum(np.log1p(-pr), axis=0)           # sum log(1 - pr_i)
    rr_comb = np.exp((1.0 - lam) * log_rr)
    return baseline * (1.0 - rr_comb) / gap          # fraction of gap closed


def main():
    inp, ihash = load_inputs()
    gap = inp["gap"]["gap_per_1000"]
    base = inp["gap"]["baseline_highvuln_per_1000"]
    ivs = inp["interventions"]
    names = [d["name"] for d in ivs]
    k = len(ivs)

    rr_pt = np.array([d["rr"] for d in ivs])
    cov_pt = np.array([d["coverage"] for d in ivs])
    lam_pt = inp["diminishing_returns_lambda"]["point"]

    # ---- point estimate ----
    point = float(closure_fraction(rr_pt[:, None], cov_pt[:, None],
                                   lam_pt, gap, base)[0])

    # ---- PSA ----
    n = inp["psa"]["n_draws"]; seed = inp["psa"]["seed"]
    rng = np.random.default_rng(seed)
    rr_draws = np.empty((k, n)); cov_draws = np.empty((k, n))
    for i, d in enumerate(ivs):
        if d["rr_high"] > d["rr_low"]:
            sd = lognormal_sd_from_ci(d["rr"], d["rr_low"], d["rr_high"])
            rr_draws[i] = np.exp(rng.normal(np.log(d["rr"]), sd, n))
        else:
            rr_draws[i] = d["rr"]
        # coverage ~ triangular(low, point, high) clipped to (0,1]; constant if degenerate
        if d["coverage_high"] > d["coverage_low"]:
            cov_draws[i] = np.clip(rng.triangular(d["coverage_low"], d["coverage"],
                                                  d["coverage_high"], n), 1e-6, 1.0)
        else:
            cov_draws[i] = d["coverage"]
    lamd = inp["diminishing_returns_lambda"]
    lam_draws = rng.uniform(lamd["low"], lamd["high"], n)
    psa = closure_fraction(rr_draws, cov_draws, lam_draws, gap, base)
    psa_summary = {
        "median": float(np.median(psa)),
        "p2.5": float(np.percentile(psa, 2.5)),
        "p97.5": float(np.percentile(psa, 97.5)),
        "mean": float(np.mean(psa)),
        "prob_ge_50pct": float(np.mean(psa >= 0.50)),
        "prob_ge_75pct": float(np.mean(psa >= 0.75)),
    }

    # ---- evidence-robust subset: exclude interventions flagged associational (physician supply) ----
    robust_mask = np.array([not d.get("associational", False) for d in ivs])
    point_robust = float(closure_fraction(rr_pt[robust_mask][:, None], cov_pt[robust_mask][:, None],
                                          lam_pt, gap, base)[0])
    psa_robust = closure_fraction(rr_draws[robust_mask], cov_draws[robust_mask], lam_draws, gap, base)
    robust_summary = {
        "robust_point_closure_fraction": point_robust,
        "robust_median": float(np.median(psa_robust)),
        "robust_p2.5": float(np.percentile(psa_robust, 2.5)),
        "robust_p97.5": float(np.percentile(psa_robust, 97.5)),
    }

    # ---- one-way sensitivity (tornado): each param to its CI/range, others at point ----
    tornado = []
    for i, d in enumerate(ivs):
        for lo, hi, label in [(d["rr_low"], d["rr_high"], "rr"),
                              (d["coverage_low"], d["coverage_high"], "coverage")]:
            for bound, val in [("low", lo), ("high", hi)]:
                rr_v = rr_pt.copy(); cov_v = cov_pt.copy()
                if label == "rr":
                    rr_v[i] = val
                else:
                    cov_v[i] = val
                c = float(closure_fraction(rr_v[:, None], cov_v[:, None], lam_pt, gap, base)[0])
                tornado.append({"intervention": d["name"], "param": label,
                                "bound": bound, "value": val, "closure": c})
    # lambda sweep
    for bound, val in [("low", lamd["low"]), ("high", lamd["high"])]:
        c = float(closure_fraction(rr_pt[:, None], cov_pt[:, None], val, gap, base)[0])
        tornado.append({"intervention": "ALL (diminishing returns)", "param": "lambda",
                        "bound": bound, "value": val, "closure": c})

    # ---- leave-one-out ablation ----
    ablation = []
    for i in range(k):
        keep = [j for j in range(k) if j != i]
        c = float(closure_fraction(rr_pt[keep][:, None], cov_pt[keep][:, None],
                                   lam_pt, gap, base)[0])
        ablation.append({"removed": names[i], "closure_without": c,
                         "marginal_contribution": point - c})

    # ---- write outputs ----
    prov = {
        "model": "Combined-intervention portfolio (transparent re-derivation)",
        "inputs_sha256_16": ihash, "seed": seed, "n_draws": n,
        "python": platform.python_version(), "numpy": np.__version__,
        "pandas": pd.__version__,
        "generated_utc": os.environ.get("REDERIVE_TS", "set REDERIVE_TS for stamped run"),
    }
    pd.DataFrame([{"metric": "point_closure_fraction", "value": point},
                  *[{"metric": kk, "value": vv} for kk, vv in psa_summary.items()],
                  *[{"metric": kk, "value": vv} for kk, vv in robust_summary.items()]]
                 ).to_csv(os.path.join(RESULTS, "rederived_portfolio_summary.csv"), index=False)
    pd.DataFrame(tornado).to_csv(os.path.join(RESULTS, "rederived_portfolio_tornado.csv"), index=False)
    pd.DataFrame(ablation).to_csv(os.path.join(RESULTS, "rederived_portfolio_ablation.csv"), index=False)
    np.save(os.path.join(RESULTS, "rederived_portfolio_psa_draws.npy"), psa)
    np.save(os.path.join(RESULTS, "rederived_portfolio_robust_psa_draws.npy"), psa_robust)
    with open(os.path.join(RESULTS, "rederived_portfolio_provenance.json"), "w") as f:
        json.dump(prov, f, indent=2)

    # ---- console summary ----
    print("== Combined-intervention portfolio re-derivation ==")
    print(f"inputs hash {ihash} | seed {seed} | draws {n}")
    print(f"POINT gap closure: {point*100:.1f}%")
    print(f"PSA median (95% interval): {psa_summary['median']*100:.1f}% "
          f"({psa_summary['p2.5']*100:.1f}% to {psa_summary['p97.5']*100:.1f}%)")
    print(f"P(>=50% closed) = {psa_summary['prob_ge_50pct']:.2f} | "
          f"P(>=75% closed) = {psa_summary['prob_ge_75pct']:.2f}")
    print(f"EVIDENCE-ROBUST (excl. associational physician supply): point {point_robust*100:.1f}%, "
          f"median {robust_summary['robust_median']*100:.1f}% "
          f"({robust_summary['robust_p2.5']*100:.1f}-{robust_summary['robust_p97.5']*100:.1f}%)")
    print("Leave-one-out marginal contributions (pp of gap):")
    for a in sorted(ablation, key=lambda x: -x["marginal_contribution"]):
        print(f"  {a['removed']:<38} {a['marginal_contribution']*100:5.1f} pp")


if __name__ == "__main__":
    main()
