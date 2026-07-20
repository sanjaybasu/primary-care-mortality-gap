# Re-derivation of the two headline results (reproducible & auditable)

The omnibus manuscript's two headline numbers were **not reproducible** from the inherited
pipeline (see `../../notebooks/primary-care-world-model/RECONCILIATION_phase2.md`):
- Paper F "~75% gap closure" — additive over-count of mostly literature-synthesized HRs.
- Paper E "HR≈0.91 / five-fold" — absent from the code entirely (`src/20` emits a mixed-unit
  `required_multiplier`).

Both are re-derived here with transparent, physician-legible, deterministic models. Every
input is sourced in a JSON file; every run writes provenance (inputs hash, seed, versions).

## How to run (from this folder)

```bash
export REDERIVE_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"   # optional timestamp stamp
python3 combined-intervention-simulation/code/portfolio_model.py          # combined-intervention (CRA) model
python3 ai-effectiveness-threshold/code/threshold_model.py                # threshold + driver analysis
python3 combined-intervention-simulation/code/validate_backtest.py        # Medicaid natural-experiment backtest
python3 ai-effectiveness-threshold/code/validate_ai_transmission.py       # extract-replicate-transmit (AI)
python3 ai-effectiveness-threshold/code/validate_ai_bundles.py            # three-bundle AI analysis
python3 combined-intervention-simulation/code/cost_layer.py               # supplementary cost layer
python3 make_tables.py && python3 make_figures.py                         # tables + figures
python3 verification/verify_rederivation.py                               # determinism + invariants
python3 verification/consistency_check.py                                 # manuscript numbers <-> code
```

Inputs: `paper-*/code/inputs_*.json`. Outputs: `results/rederived_*`. Deterministic
(seed 20260720); the auditor confirms bit-identical reruns.

## Method (both models)

Gap = 2.4 deaths/1,000/yr between high- (SVI Q4, 9.6) and low-vulnerability (Q1, 7.2)
counties [CDC WONDER × CDC SVI].

**Paper F.** Each intervention reaches `coverage_i` of the high-vuln population and cuts
mortality among reached by `(1-rr_i)`; combined multiplicatively with a diminishing-returns
penalty λ (overlap). Closure = baseline·(1−RR_combined)/gap. PSA (20k draws) over rr (log-CI),
coverage (triangular), λ (uniform); one-way tornado; leave-one-out ablation.

**Paper E.** Residual after structural closure s is R = gap·(1−s); AI reaching fraction r
must satisfy baseline·r·(1−HR_ai)=R, so **HR_ai = 1 − R/(baseline·r)**. Structural-closure
uncertainty propagated from Paper F's PSA draws. Scenario grid over s×r.

## Results snapshot (provisional inputs — finalized in literature-review phase)

**Paper F — combined structural package:** point **34.6%** gap closure; PSA median **32.4%**
(95% interval 20.6–46.1%); P(≥75%)≈0. Largest marginal contributor: physician workforce
(17.3 pp), then CHW (7.0), IBH (4.0), FQHC (3.3), Medicaid (2.0). → The omnibus "75%" is not
reproduced; the honest figure is ~one-third.

**Paper E — required AI effectiveness:** point required **HR 0.44** (structural closure 0.32,
reach 0.30); PSA median **0.46** (95% interval 0.08–0.65); P(required HR<0.90)=1.00. The
omnibus's 0.91 appears only in the optimistic corner (structural closure 0.75 **and** universal
reach 1.0 → 0.94). Under realistic reach the required per-patient effect is far larger than any
demonstrated clinical-AI or even CHW effect — quantifying why AI must be **paired with reach-
extending navigation (CHWs)**, not deployed alone. This is a stronger, honest reframing.

## Causal inputs (IV / DiD / DML)

The two headline models use published, cited effect sizes as inputs; they do not re-estimate
the causal parameters. The inherited pipeline's own causal estimates (physician-supply IV,
Medicaid Callaway-Sant'Anna DiD, double machine learning) cannot be re-run here because they
require restricted individual-level mortality-linked data (NHANES-NDI, NHIS-NDI, MEPS). Their
influence on the headline results is bounded and disclosed:
- The inherited Medicaid DiD implied RR (0.988, near-null) falls inside the modeled Medicaid
  input CI (0.93-0.99). The one-way tornado varies Medicaid across this range; Medicaid's
  leave-one-out contribution is 2.0 pp, so the near-null inherited estimate changes total
  closure by less than a percentage point. The portfolio conclusion is robust to it.
- The physician-supply IV point estimate is not statistically significant; this is stated in
  `inputs.json` and in both manuscripts, and physician supply's contribution is flagged as
  associational.

## Supplementary layers

- Cost: `combined-intervention-simulation/code/cost_layer.py` -> `results/rederived_portfolio_cost.csv`.
  Illustrative upper bound (joint-cost limitation): deaths averted median 78 per 100k
  high-vulnerability population per year; cost per life-year median ~$205,000 (95% interval
  $111,000-$389,000).
- Recurrent state-space model: reported per TRIPOD-AI in
  `../../notebooks/primary-care-world-model/combined-intervention-simulation/appendix/supplementary_tripod_ai_world_model.md`.
  Supplementary only (validation C-statistic 0.62; calibration slope 2.35-2.95).

## Status / caveats

- Input effect sizes are `provisional` (defensible published values); the literature-review +
  citation-management phase finalizes and verifies each, which may shift the numbers.
- Physician-workforce term is modeled population-wide (coverage=1.0); note this study's own IV
  estimate is not statistically significant — flagged in `inputs_F.json`.
- These models deliberately supersede the RSSM as the load-bearing engine (poorly calibrated,
  slope 2.4–2.9); the RSSM is retained only as a supplementary robustness layer (TRIPOD-AI).
