#!/usr/bin/env python3
"""
Build the Medical Decision Making submission package from the canonical markdown.

Inputs (notebooks/.../manuscript): ai_primary_care_threshold_mdm.md, supplementary_appendix_mdm.md,
titlepage_mdm.md, statements_and_declarations_mdm.md, anonymized_information_mdm.md, cover_letter_mdm.md
Outputs (notebooks/.../submission):
  threshold_main_MDM.docx           anonymized main document (title only, abstract, highlights, text,
                                    placeholders, references, tables, figure legends, figures, appendix)
  threshold_appendix_MDM.docx       anonymized supplementary appendix (web-only)
  threshold_titlepage.docx, threshold_statements_and_declarations.docx,
  threshold_anonymized_information.docx, threshold_cover_letter.docx
  figures/Figure1.tif ... (600 dpi, for production)
Equations render as native, editable Word equations (OMML); citation superscripts become Word
superscript runs; self-citations are replaced with "Anonymous" per MDM double-anonymized rules.
Usage: python3 build_mdm_submission.py
"""
import os, re, shutil, subprocess, tempfile, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE.split(os.sep + "packaging" + os.sep)[0]
PROJ = os.path.join(ROOT, "notebooks", "primary-care-world-model", "ai-effectiveness-threshold")
MS, SUB, FIG = (os.path.join(PROJ, d) for d in ("manuscript", "submission", "figures"))
TEMPLATE = os.path.expanduser("~/.claude/templates/sanjay_paper_reference.docx")
os.makedirs(os.path.join(SUB, "figures"), exist_ok=True)

FIGURES = [("Figure 1", "figure1_two_way_threshold"), ("Figure 2", "figure2_equity_reach"),
           ("Figure 3", "figure3_acceptability")]
SELF_CITE_DOIS = {"10.1001/jamainternmed.2018.7624": "2019", "10.7326/M20-7381": "2021"}
PAGE = '\n```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```\n'

SUP = dict(zip("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-"))
RUN = re.compile("[⁰¹²³⁴⁵⁶⁷⁸⁹](?:[⁰¹²³⁴⁵⁶⁷⁸⁹⁻]|[,∙](?=[⁰¹²³⁴⁵⁶⁷⁸⁹]))*")


def supfix(t):
    return RUN.sub(lambda m: "^" + "".join(SUP.get(c, ",") for c in m.group(0)) + "^", t)


def anonymize(t):
    def ref(m):
        line = m.group(0)
        for doi, yr in SELF_CITE_DOIS.items():
            if doi in line:
                return m.group(1) + f"Anonymous ({yr}). Details omitted for double-anonymized reviewing."
        return line
    t = re.sub(r"^(\*\*\d+\.\*\* |\d+\. ).*$", ref, t, flags=re.M)
    t = t.replace("Basu 2019", "Anonymous 2019").replace("Basu 2021", "Anonymous 2021")
    t = re.sub(r"https://github\.com/sanjaybasu/\S+", "[repository link withheld for review]", t)
    return t


def breaks(t, heads):
    for h in heads:
        t = re.sub(rf"^({re.escape(h)})", PAGE + r"\1", t, flags=re.M)
    return t


def pandoc(md_text, out_name):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(md_text); src = f.name
    out = os.path.join(SUB, out_name)
    subprocess.run(["pandoc", src, "-f", "markdown+tex_math_dollars+pipe_tables+raw_attribute",
                    "-o", out, f"--reference-doc={TEMPLATE}", "--resource-path", FIG],
                   check=True)
    os.unlink(src)
    scrub(out)
    print("built", out)


def scrub(docx):
    """Blank author/editor metadata in docProps/core.xml."""
    tmp = docx + ".tmp"
    with zipfile.ZipFile(docx) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "docProps/core.xml":
                s = data.decode()
                s = re.sub(r"<dc:creator>.*?</dc:creator>", "<dc:creator></dc:creator>", s)
                s = re.sub(r"<cp:lastModifiedBy>.*?</cp:lastModifiedBy>", "<cp:lastModifiedBy></cp:lastModifiedBy>", s)
                data = s.encode()
            zout.writestr(item, data)
    os.replace(tmp, docx)


def main_doc():
    t = open(os.path.join(MS, "ai_primary_care_threshold_mdm.md")).read()
    title = t.split("\n", 1)[0]
    body = t[t.index("## Abstract"):]
    body = breaks(body, ["## Abstract", "## References", "## Table 1.", "## Table 2.", "## Figure Legends"])
    figs = "".join(f"{PAGE}\n**{lab}.**\n\n![]({os.path.join(FIG, name + '.png')}){{width=6.3in}}\n"
                   for lab, name in FIGURES)
    return title + "\n\n" + body + figs


def appendix_doc():
    return open(os.path.join(MS, "supplementary_appendix_mdm.md")).read()


def main():
    apx = anonymize(supfix(appendix_doc()))
    pandoc(anonymize(supfix(main_doc())) + PAGE + apx, "threshold_main_MDM.docx")
    pandoc(apx, "threshold_appendix_MDM.docx")
    for src, out in [("titlepage_mdm.md", "threshold_titlepage.docx"),
                     ("statements_and_declarations_mdm.md", "threshold_statements_and_declarations.docx"),
                     ("anonymized_information_mdm.md", "threshold_anonymized_information.docx"),
                     ("cover_letter_mdm.md", "threshold_cover_letter.docx")]:
        pandoc(supfix(open(os.path.join(MS, src)).read()), out)
    for lab, name in FIGURES:
        shutil.copy2(os.path.join(FIG, name + ".tif"), os.path.join(SUB, "figures", lab.replace(" ", "") + ".tif"))
    print("figures copied to", os.path.join(SUB, "figures"))


if __name__ == "__main__":
    main()
