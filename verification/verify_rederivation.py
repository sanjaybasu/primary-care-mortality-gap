#!/usr/bin/env python3
"""
One-command auditor for the transparent re-derivations (Papers E and F).
Re-runs both models, checks determinism and sanity invariants, prints PASS/FAIL.
Usage:  python3 verification/verify_rederivation.py
"""
import os, subprocess, sys, hashlib
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS = os.path.join(ROOT, "results")
F_CODE = os.path.join(ROOT, "combined-intervention-simulation", "code", "portfolio_model.py")
E_CODE = os.path.join(ROOT, "ai-effectiveness-threshold", "code", "threshold_model.py")


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def run(p):
    subprocess.run([sys.executable, p], check=True, cwd=os.path.dirname(p),
                   stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def main():
    checks = []
    # F determinism
    run(F_CODE); h1 = sha(os.path.join(RESULTS, "rederived_portfolio_summary.csv"))
    run(F_CODE); h2 = sha(os.path.join(RESULTS, "rederived_portfolio_summary.csv"))
    checks.append(("Portfolio (combined-intervention) model deterministic", h1 == h2))
    # E determinism (depends on F draws)
    run(E_CODE); h3 = sha(os.path.join(RESULTS, "rederived_threshold_summary.csv"))
    run(E_CODE); h4 = sha(os.path.join(RESULTS, "rederived_threshold_summary.csv"))
    checks.append(("AI-effectiveness threshold model deterministic", h3 == h4))
    # F invariant: closure in (0,1), point < 0.75 (not the omnibus figure)
    fs = pd.read_csv(os.path.join(RESULTS, "rederived_portfolio_summary.csv")).set_index("metric")["value"]
    checks.append(("portfolio point closure in (0,1)", 0 < fs["point_closure_fraction"] < 1))
    checks.append(("portfolio point closure < 0.75 (omnibus claim not reproduced)",
                   fs["point_closure_fraction"] < 0.75))
    # E invariant: omnibus 0.91 only in optimistic corner; realistic corner much lower
    grid = pd.read_csv(os.path.join(RESULTS, "rederived_threshold_scenario_grid.csv"))
    corner = grid[(grid.structural_closure == 0.75) & (grid.ai_reach == 1.00)]["required_HR"].iloc[0]
    realistic = grid[(grid.structural_closure == 0.35) & (grid.ai_reach == 0.30)]["required_HR"].iloc[0]
    checks.append(("threshold optimistic corner ~ omnibus 0.91 (>=0.90)", corner >= 0.90))
    checks.append(("threshold realistic corner far below 0.90", realistic < 0.90))
    checks.append(("threshold required HR rises with reach and with structural closure",
                   realistic < corner))

    ok = all(v for _, v in checks)
    for name, v in checks:
        print(f"[{'PASS' if v else 'FAIL'}] {name}")
    print("\nOVERALL:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
