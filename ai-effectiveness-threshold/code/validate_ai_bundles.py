#!/usr/bin/env python3
"""
Three-bundle clinical-AI analysis: what each mechanism class actually delivers against the
mortality-gap threshold, computed from replicated effect sizes and validated transmission.

Bundles (each reduces to accountable reach x transmitted per-patient effect, net of harm):
  A. Disease-specific patient-facing (prevalence-conditioned): bounded by disease prevalence
     x sustained engagement x transmitted per-patient effect. Transmission is condition-
     specific: strong for blood pressure (BPLTTC), weak/contested for glycemia (ACCORD).
  B. Generalist consumer (net of harm): benefit net of hallucination/unsafe-advice harm;
     can be <= 0. Bounded by the accuracy/harm ratio.
  C. Provider-facing (decision-transmission threshold): effect transmits through the
     clinician. Ambient scribes show no output/decision change (transmission ~ 0); knowledge
     tools improve simulated diagnosis but have no demonstrated outcome/mortality effect.

Evidence (peer-reviewed; see manuscript references):
  Transmission:  SBP 5 mmHg -> MACE HR 0.88 (BPLTTC/Yang 2026); LDL 1 mmol/L -> RR 0.78
                 (CTT/Lincoff 2024); glycemia -> mortality weak/null (ACCORD).
  Bundle A:      digital-HTN SBP -2.91 mmHg (Lindsay-Perez 2025) / -1.45 (Motta-Yanac 2024);
                 digital-diabetes effectiveness + low reach/uptake (Moschonis 2023).
  Bundle B:      7-10% potentially harmful therapeutic advice (Tausky 2025); 28.6% fully
                 incorrect diagnoses, "ideal safety profiles uncommon" (Lin 2026).
  Bundle C:      ambient scribe: no change in note time / pajama time / wRVUs (Shin 2025);
                 knowledge tool: superior simulated diagnosis, no outcome effect (Tu 2025).

Evidence grades are attached to each parameter. Deterministic; reproducible.
"""
import json, os, math
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "results"))
GAP, M, S_MEDIAN = 2.4, 9.6, 0.32

beta_sbp = math.log(0.88) / 5.0            # per-mmHg log hazard (MACE; upper bound vs all-cause)

def required_hr(s, r):
    return 1 - GAP * (1 - s) / (M * r)

def closure_from_pop_reduction(rel_reduction):
    return (M * rel_reduction) / GAP        # fraction of gap closed

# ---------- Bundle A: disease-specific, prevalence-conditioned ----------
# per-reached transmitted relative mortality reduction (1-HR), condition-specific
htn_sbp = 2.91                              # best measured (favorable to AI), Lindsay-Perez 2025
htn_hr = math.exp(beta_sbp * htn_sbp)       # ~0.928 (MACE)
A = [
    {"condition": "hypertension", "prevalence_highvuln": 0.45, "engagement": 0.30,
     "per_reached_HR": round(htn_hr, 3), "transmission": "strong (BPLTTC)", "grade": "moderate"},
    {"condition": "diabetes (glycemic)", "prevalence_highvuln": 0.15, "engagement": 0.30,
     "per_reached_HR": 1.00, "transmission": "weak/null (ACCORD)", "grade": "moderate"},
]
poolA = 0.0
for a in A:
    poolA += a["prevalence_highvuln"] * a["engagement"] * (1 - a["per_reached_HR"])
closureA = closure_from_pop_reduction(poolA)

# ---------- Bundle B: generalist consumer, net of harm ----------
p_harm = 0.08          # potentially harmful therapeutic advice (Tausky 2025, 7-10%)
p_incorrect = 0.286    # fully incorrect diagnoses (Lin 2026)
# Net per-interaction effect is benefit*P(correct) - harm_severity*P(harm). For a credible
# net-positive mortality effect the benefit must exceed harm*severity; with ~8% harmful
# advice at high severity in acute presentations, the net is not established as positive.
netB_positive = False
closureB_note = "net effect not established as positive; potential to widen the gap (backfire)"

# ---------- Bundle C: provider-facing, decision-transmission ----------
scribe_transmission = 0.0        # Shin 2025: no change in output/decisions
# knowledge tool: required improvement to move the gap at plausible adoption (illustrative)
adoption, panel_highvuln_share = 0.30, 0.50   # clinician adoption x high-vuln share of panel
reachC = adoption * panel_highvuln_share
req_hr_universal = required_hr(S_MEDIAN, 1.00)
# decision-quality-driven per-patient reduction needed at reach reachC to close residual:
req_reduction_C = GAP * (1 - S_MEDIAN) / (M * reachC) if reachC > 0 else float("inf")

rows = []
for a in A:
    rows.append({"bundle": "A disease-specific", **a,
                 "population_rel_reduction": round(a["prevalence_highvuln"]*a["engagement"]*(1-a["per_reached_HR"]), 4)})
rows.append({"bundle": "A disease-specific (pooled)", "condition": "HTN+diabetes",
             "gap_closure_fraction": round(closureA, 4)})
rows.append({"bundle": "B generalist", "p_harmful_advice": p_harm, "p_incorrect_dx": p_incorrect,
             "net_positive": netB_positive, "note": closureB_note})
rows.append({"bundle": "C provider scribe", "transmission_to_mortality": scribe_transmission,
             "note": "no demonstrated decision/output change (Shin 2025)"})
rows.append({"bundle": "C provider knowledge tool", "reach": round(reachC, 3),
             "required_per_patient_reduction_to_close_residual": round(req_reduction_C, 3),
             "note": "no demonstrated outcome/mortality effect (Tu 2025); threshold shown"})
pd.DataFrame(rows).to_csv(os.path.join(RESULTS, "rederived_ai_bundles.csv"), index=False)

print("== Three-bundle clinical-AI analysis ==")
print(f"A. Disease-specific (best case, MACE-favorable): HTN per-reached HR {htn_hr:.3f}; "
      f"pooled gap closure {closureA*100:.1f}% (bounded by prevalence x engagement; "
      f"glycemia transmission ~ null)")
print(f"B. Generalist consumer: {p_harm*100:.0f}% harmful therapeutic advice, "
      f"{p_incorrect*100:.1f}% incorrect diagnoses -> net effect not established positive "
      f"(potential backfire)")
print(f"C. Provider scribe: transmission to mortality {scribe_transmission} (Shin 2025 null). "
      f"Knowledge tool at reach {reachC:.2f}: would need per-patient mortality reduction "
      f"{req_reduction_C*100:.0f}% to close the residual; none demonstrated on outcomes.")
print("Conclusion: all three bundles fall far short of the gap-closure threshold, each for a "
      "structurally distinct reason (prevalence ceiling; net harm; weak decision-transmission).")
