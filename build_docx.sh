#!/usr/bin/env bash
# Build submission .docx for both papers: anonymized main (figures/tables embedded at end),
# separate title page, and comprehensive appendix. Equations render as native Word (OMML);
# tables render as native Word tables; figures embedded; citation/affiliation superscripts
# converted from Unicode glyphs to true Word superscript runs (pandoc ^n^).
# Reproducible: re-run after any manuscript edit.
set -euo pipefail
TEMPLATE="/Users/sanjaybasu/.claude/templates/sanjay_paper_reference.docx"
NB="/Users/sanjaybasu/waymark-local/notebooks/primary-care-world-model"
TH="$NB/ai-effectiveness-threshold"
PO="$NB/combined-intervention-simulation"
TMP="$(mktemp -d)"

python3 - "$TMP" <<'PY'
import re, sys, os
TMP = sys.argv[1]
NB = "/Users/sanjaybasu/waymark-local/notebooks/primary-care-world-model"
SUP = {'⁰':'0','¹':'1','²':'2','³':'3','⁴':'4','⁵':'5','⁶':'6','⁷':'7','⁸':'8','⁹':'9'}
CLS = ''.join(SUP)
RUN = re.compile(r'[%s](?:[∙,–−\-]?[%s])*' % (CLS, CLS))

def supfix(text):
    # convert runs of unicode superscript digits (with ∙ or , separators) to pandoc ^n,m^
    def repl(m):
        digits = ''.join(SUP.get(c, ',') for c in m.group(0))
        digits = re.sub(r'[^0-9,\-]', '', digits)
        return '^%s^' % digits
    return RUN.sub(repl, text)

def write(name, text):
    p = os.path.join(TMP, name)
    open(p, 'w').write(text)
    return p

def main_doc(src, figs):
    t = open(src).read()
    idx = t.index("## Abstract")           # drop author block (double-anonymized main)
    doc = t.split("\n", 1)[0] + "\n\n" + t[idx:]
    doc += "\n\n# Figures\n\n"              # figures embedded at end (tables already at end)
    for cap, fp in figs:
        doc += f"**{cap}**\n\n![]({fp}){{width=6.0in}}\n\n"
    return supfix(doc)

th = f"{NB}/ai-effectiveness-threshold"
po = f"{NB}/combined-intervention-simulation"
write("th_main.md", main_doc(f"{th}/manuscript/ai_effectiveness_threshold_annals.md",
    [("Figure 1. Required AI hazard ratio among patients reached, by reach and structural gap closure.",
      f"{th}/figures/figure1_required_hr_heatmap.png")]))
write("th_title.md", supfix(open(f"{th}/submission/threshold_titlepage.md").read()))
write("th_apx.md",   supfix(open(f"{th}/submission/threshold_appendix.md").read()))
write("po_main.md", main_doc(f"{po}/manuscript/combined_intervention_portfolio_health_affairs.md",
    [("Exhibit 1. Distribution of the fraction of the mortality gap closed by the combined package.",
      f"{po}/figures/exhibit1_gap_closure_psa.png"),
     ("Exhibit 2. Marginal contribution of each intervention (leave-one-out).",
      f"{po}/figures/exhibit2_ablation.png"),
     ("Exhibit 3. One-way sensitivity (tornado).",
      f"{po}/figures/exhibit3_tornado.png")]))
write("po_title.md", supfix(open(f"{po}/submission/portfolio_titlepage.md").read()))
write("po_apx.md",   supfix(open(f"{po}/submission/portfolio_appendix.md").read()))
# keep a copy of the processed main for the record
open(f"{th}/submission/threshold_main_anonymized.md","w").write(open(os.path.join(TMP,"th_main.md")).read())
open(f"{po}/submission/portfolio_main.md","w").write(open(os.path.join(TMP,"po_main.md")).read())
print("preprocessed (superscripts fixed) ->", TMP)
PY

conv() { pandoc "$1" -o "$2" --reference-doc="$TEMPLATE"; echo "  built $(basename "$2")"; }

echo "Threshold (Medical Decision Making):"
conv "$TMP/th_main.md"  "$TH/submission/threshold_main_MDM.docx"
conv "$TMP/th_title.md" "$TH/submission/threshold_titlepage.docx"
conv "$TMP/th_apx.md"   "$TH/submission/threshold_appendix_MDM.docx"
echo "Portfolio (Health Affairs):"
conv "$TMP/po_main.md"  "$PO/submission/portfolio_main_HealthAffairs.docx"
conv "$TMP/po_title.md" "$PO/submission/portfolio_titlepage.docx"
conv "$TMP/po_apx.md"   "$PO/submission/portfolio_appendix_HealthAffairs.docx"
rm -rf "$TMP"
echo "Done."
