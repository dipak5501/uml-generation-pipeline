#!/usr/bin/env python3
"""Two-page M.S. thesis research brief for committee invitation emails."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from scripts.pdf_github_compat import disable_reportlab_ascii85, github_compat_pdf

disable_reportlab_ascii85()

ROOT = Path(__file__).resolve().parents[1]
OUTS = [
    ROOT / "reports" / "Dipak_Yadav_Thesis_Research_Brief.pdf",
    Path("/opt/cursor/artifacts") / "Dipak_Yadav_Thesis_Research_Brief.pdf",
]
NAVY = colors.HexColor("#003366")
GOLD = colors.HexColor("#C4A35A")
RULE = colors.HexColor("#8A7A4B")
ROW = colors.HexColor("#F4F1EA")
HEAD = colors.HexColor("#E8EEF4")


def p(text, style):
    return Paragraph(text, style)


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Uni",
            fontName="Times-Roman",
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            textColor=NAVY,
            spaceAfter=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="DocKind",
            fontName="Times-Bold",
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            textColor=NAVY,
            spaceBefore=2,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TitleMain",
            fontName="Times-Bold",
            fontSize=12.5,
            leading=15.5,
            alignment=TA_CENTER,
            textColor=NAVY,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Meta",
            fontName="Times-Roman",
            fontSize=9.5,
            leading=12.5,
            alignment=TA_CENTER,
            spaceAfter=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Sec",
            fontName="Times-Bold",
            fontSize=10.5,
            leading=13,
            textColor=NAVY,
            spaceBefore=6,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            fontName="Times-Roman",
            fontSize=9.4,
            leading=11.7,
            alignment=TA_JUSTIFY,
            spaceAfter=2.6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BriefBullet",
            fontName="Times-Roman",
            fontSize=9.4,
            leading=11.7,
            alignment=TA_JUSTIFY,
            leftIndent=12,
            firstLineIndent=-10,
            spaceAfter=1.4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Th",
            fontName="Times-Bold",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=NAVY,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Td",
            fontName="Times-Roman",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TdL",
            fontName="Times-Roman",
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Cap",
            fontName="Times-Italic",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#333333"),
            spaceBefore=1,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Foot",
            fontName="Times-Italic",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#444444"),
        )
    )
    return styles


def table(data, col_widths, styles):
    t = Table(data, colWidths=col_widths, hAlign="CENTER")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEAD),
                ("BACKGROUND", (0, -1), (-1, -1), ROW),
                ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
                ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C2CC")),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return t


def header_footer(canvas, doc):
    canvas.saveState()
    w, h = letter
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 18, w, 18, fill=1, stroke=0)
    canvas.setFillColor(GOLD)
    canvas.rect(0, h - 21, w, 3, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Times-Roman", 8)
    canvas.drawString(0.7 * inch, h - 13, "California State University, Long Beach  ·  CECS")
    canvas.drawRightString(
        w - 0.7 * inch,
        h - 13,
        "M.S. Thesis Research Brief",
    )
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, w, 22, fill=1, stroke=0)
    canvas.setFillColor(GOLD)
    canvas.rect(0, 22, w, 2.5, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Times-Roman", 8)
    canvas.drawString(0.7 * inch, 8, "Dipak Yadav  ·  Confidential — for thesis committee invitation")
    canvas.drawRightString(w - 0.7 * inch, 8, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf(out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    S = build_styles()
    doc = SimpleDocTemplate(
        str(out),
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.44 * inch,
        bottomMargin=0.38 * inch,
        title="M.S. Thesis Research Brief — Dipak Yadav",
        author="Dipak Yadav",
        subject="Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification",
    )
    story = []

    story.append(p("Department of Computer Engineering &amp; Computer Science", S["Uni"]))
    story.append(p("M.S. THESIS RESEARCH BRIEF  ·  FOR PROPOSED COMMITTEE MEMBERS", S["DocKind"]))
    story.append(
        p(
            "Automated UML Dataset Generation from Natural-Language Requirements "
            "with Multimodal Verification for Software Design",
            S["TitleMain"],
        )
    )
    story.append(p("<b>Student:</b> Dipak Yadav, M.S. Computer Science", S["Meta"]))
    story.append(
        p(
            "<b>Thesis chair:</b> Yutong Zhao, Ph.D., Assistant Professor, CECS",
            S["Meta"],
        )
    )
    story.append(
        p(
            "Email: dipak.yadav5501@gmail.com  ·  Repository: github.com/dipak5501/uml-generation-pipeline",
            S["Meta"],
        )
    )
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=0.8, color=NAVY, spaceAfter=6))

    story.append(p("1. Problem and motivation", S["Sec"]))
    story.append(
        p(
            "Unified Modeling Language (UML) is a standard medium for communicating software "
            "architecture, but constructing diagrams by hand is slow, inconsistent, and hard to "
            "scale when requirements are informal or frequently revised. Large language models can "
            "draft diagrams from text, yet a diagram that compiles is not necessarily a correct "
            "design: it may omit entities, misuse relationships, or look valid while remaining "
            "conceptually misleading. Prior work has emphasized generation more than verification, "
            "and existing UML datasets are typically small, narrowly typed, or scored only by "
            "syntax checks or a single model. This thesis treats <b>verification as a first-class "
            "stage</b> of automated UML construction.",
            S["Body"],
        )
    )

    story.append(p("2. Research objective and questions", S["Sec"]))
    story.append(
        p(
            "The objective is to generate design-phase UML from natural-language requirements at "
            "dataset scale, then validate each artifact with a vision-language model (VLM) ensemble "
            "that can be compared with expert ratings. Four families are studied: <b>class, object, "
            "component, and package</b>. Three research questions guide the evaluation:",
            S["Body"],
        )
    )
    story.append(
        p(
            "<b>RQ1.</b> How effectively can a decomposed LLM pipeline generate syntactically "
            "and semantically valid UML artifacts from natural-language requirements at scale?",
            S["BriefBullet"],
        )
    )
    story.append(
        p(
            "<b>RQ2.</b> To what degree does multimodal ensemble verification correlate with "
            "expert human evaluation of the generated diagrams?",
            S["BriefBullet"],
        )
    )
    story.append(
        p(
            "<b>RQ3.</b> How does accuracy vary across UML diagram families, and what failure "
            "patterns explain the differences?",
            S["BriefBullet"],
        )
    )

    story.append(p("3. Method: three-stage pipeline", S["Sec"]))
    story.append(
        p(
            "The framework assigns each model a narrower job so failures can be isolated at stage "
            "boundaries, and the PlantUML generator never sees raw unprocessed requirement text.",
            S["Body"],
        )
    )
    story.append(
        p(
            "<b>Stage 1 — Technical specification (LLaMA 3.2-1B-Instruct).</b> A free-form "
            "requirement becomes structured JSON: entities and attributes, relationships "
            "(association, aggregation, composition, dependency, realization), containment, and "
            "diagram-type constraints. A 1B instruction-tuned model is used because this stage is "
            "extraction, not deep reasoning. On 100 held-out prompts it produced valid JSON in 94% "
            "of cases (1.8 s/spec), ahead of DeepSeek-R1-Qwen-1.5B (88.5%) and Gemma 2-2B (82%). "
            "Specifications span four domains—e-commerce, healthcare, IoT, and banking—with 500 "
            "per domain per diagram type (4 × 500 × 4 = 8,000).",
            S["Body"],
        )
    )
    story.append(
        p(
            "<b>Stage 2 — PlantUML synthesis (DeepSeek-R1-Distill-Qwen-32B).</b> The JSON "
            "specification is the sole input to a 32B reasoning model with chain-of-thought "
            "prompting. Decomposition narrows the search space relative to mapping raw text "
            "directly to diagrams.",
            S["Body"],
        )
    )
    story.append(
        p(
            "<b>Stage 3 — Render gate and multimodal verification.</b> PlantUML is rendered to an "
            "image. Failed renders are excluded (δ = 0; composite score forced to zero). Each "
            "successful image is scored independently by three VLMs on a 0–6 rubric: semantic "
            "correctness, structural completeness, syntactic / notational accuracy, and overall "
            "coherence. Evaluators: Qwen2.5-VL-3B (MMMU 53.1), LLaMA-3.2-Vision-11B (MMMU 50.7), "
            "and Aya-Vision-8B (MMMU 39.9). The original requirement and the JSON specification "
            "are also given to the VLMs for cross-modal consistency checking.",
            S["Body"],
        )
    )
    story.append(
        p(
            "<b>Dual-signal quality decision.</b> Scores <i>s<sub>ij</sub></i> are combined with "
            "MMMU weights into <i>S<sub>i</sub></i> = δ<sub>i</sub> · (Σ w<sub>j</sub> s<sub>ij</sub>) / "
            "(Σ w<sub>j</sub>), w = (53.1, 50.7, 39.9). Each VLM votes accept if "
            "<i>s<sub>ij</sub></i> ≥ τ = 4; majority <i>A<sub>i</sub></i> = 1 if at least two of "
            "three vote yes. A sample enters the dataset only if rendering succeeds, "
            "<i>A<sub>i</sub></i> = 1, and <i>S<sub>i</sub></i> ≥ 3.0. Example: scores 5, 4, 3 give "
            "<i>S</i> ≈ 4.09; scores 5, 5, 4 give <i>S</i> ≈ 4.70 with <i>A</i> = 1.",
            S["Body"],
        )
    )
    story.append(p("4. Experimental design", S["Sec"]))
    story.append(
        p(
            "The study dataset contains <b>8,000</b> UML samples (2,000 per type). Human evaluation "
            "used a stratified random sample of <b>40 diagrams</b> (10 per type; seed 42). G*Power "
            "for a medium correlation effect (f² = 0.15, α = 0.05, power 0.80) requires at least 37 "
            "observations. <b>Eighty</b> domain experts rated every sampled diagram on the same 0–6 "
            "rubric: 23 IT lecturers, 35 enterprise architects (≥5 years), and 22 software-engineering "
            "Ph.D. students. Inter-rater reliability uses Fleiss’ Kappa; alignment between composite "
            "<i>S</i> and mean human scores uses Pearson <i>r</i>.",
            S["Body"],
        )
    )

    story.append(p("5. Principal results", S["Sec"]))
    story.append(
        p(
            "<b>RQ1 — generation at scale.</b> Per-type render success is 95.7% (class), 94.4% "
            "(object), 91.6% (component), and 81.1% (package). The paper reports overall render "
            "success of <b>94.4%</b> and majority-vote acceptance of <b>91.3%</b> (6,891 of 7,553 "
            "rendered diagrams). Packages remain the bottleneck; typical failures are incorrect "
            "PlantUML nesting and renderer stress above ~50 nested elements.",
            S["Body"],
        )
    )

    t1 = table(
        [
            [
                p("<b>Diagram</b>", S["Th"]),
                p("<b>Failures</b>", S["Th"]),
                p("<b>Success %</b>", S["Th"]),
                p("<b>Mean S (0–6)</b>", S["Th"]),
                p("<b>SD</b>", S["Th"]),
            ],
            [p("Class", S["TdL"]), p("87", S["Td"]), p("95.7", S["Td"]), p("4.31", S["Td"]), p("0.74", S["Td"])],
            [p("Object", S["TdL"]), p("112", S["Td"]), p("94.4", S["Td"]), p("4.09", S["Td"]), p("0.81", S["Td"])],
            [p("Component", S["TdL"]), p("169", S["Td"]), p("91.6", S["Td"]), p("3.87", S["Td"]), p("0.93", S["Td"])],
            [p("Package", S["TdL"]), p("379", S["Td"]), p("81.1", S["Td"]), p("3.12", S["Td"]), p("1.04", S["Td"])],
            [p("<b>Overall</b>", S["TdL"]), p("<b>747</b>", S["Td"]), p("<b>94.4</b>", S["Td"]), p("<b>3.85</b>", S["Td"]), p("<b>0.98</b>", S["Td"])],
        ],
        [1.35 * inch, 1.1 * inch, 1.15 * inch, 1.35 * inch, 0.85 * inch],
        S,
    )
    story.append(t1)
    story.append(p("Table 1. Render success and mean composite VLM score S (n = 2,000 per type).", S["Cap"]))

    story.append(
        p(
            "<b>RQ2 — agreement with experts.</b> Ensemble <i>S</i> vs. mean human ratings: "
            "<b>r = 0.71</b> (p &lt; 0.001). Fleiss’ κ = <b>0.68</b> (substantial agreement). "
            "Class diagrams align most strongly (r = 0.82, κ = 0.74); packages least "
            "(r = 0.55, p = 0.003, κ = 0.58), reflecting containment-versus-dependency ambiguity. "
            "Component diagrams (r = 0.68) diverge mainly when dense layouts impair VLM parsing.",
            S["Body"],
        )
    )

    t2 = table(
        [
            [
                p("<b>Diagram</b>", S["Th"]),
                p("<b>Pearson r</b>", S["Th"]),
                p("<b>p-value</b>", S["Th"]),
                p("<b>Fleiss’ κ</b>", S["Th"]),
            ],
            [p("Class", S["TdL"]), p("0.82", S["Td"]), p("&lt; 0.001", S["Td"]), p("0.74", S["Td"])],
            [p("Object", S["TdL"]), p("0.76", S["Td"]), p("&lt; 0.001", S["Td"]), p("0.71", S["Td"])],
            [p("Component", S["TdL"]), p("0.68", S["Td"]), p("&lt; 0.001", S["Td"]), p("0.65", S["Td"])],
            [p("Package", S["TdL"]), p("0.55", S["Td"]), p("= 0.003", S["Td"]), p("0.58", S["Td"])],
            [p("<b>Overall</b>", S["TdL"]), p("<b>0.71</b>", S["Td"]), p("<b>&lt; 0.001</b>", S["Td"]), p("<b>0.68</b>", S["Td"])],
        ],
        [1.6 * inch, 1.4 * inch, 1.4 * inch, 1.4 * inch],
        S,
    )
    story.append(t2)
    story.append(
        p(
            "Table 2. Automated vs. human correlation and inter-rater reliability "
            "(n = 10 diagrams per type; 80 evaluators).",
            S["Cap"],
        )
    )

    story.append(
        p(
            "<b>RQ3 — why types differ.</b> Metrics follow class &gt; object &gt; component &gt; "
            "package. (1) Class diagrams dominate public training data. (2) Class PlantUML is "
            "syntactically rigid; package syntax has competing containment constructs. "
            "(3) Packages mix namespace, deployment, and grouping semantics; component boundaries "
            "must often be inferred from the requirement.",
            S["Body"],
        )
    )

    story.append(p("6. Comparison with prior work and contributions", S["Sec"]))
    story.append(
        p(
            "A two-round search (IEEE Xplore, ACM DL, arXiv/Scholar; 187 candidates → 23 papers) "
            "identified five comparable LLM-based UML or architecture generators. This work offers "
            "(i) broader coverage (four types vs. at most two in one prior study), (ii) stronger "
            "semantic verification (three-VLM ensemble, r = 0.71, vs. single-VLM r = 0.61 in "
            "de Oliveira et al., or no automated semantic score in several prompt-only studies), "
            "and (iii) larger validated scale (8,000 vs. a prior maximum of 300). Prior limits "
            "include no automated verification (Jahan et al.; Bates et al.), image-to-code without "
            "upstream generation (Conrardy &amp; Cabot), and Mermaid-only rendering (Gheorghita et al.).",
            S["Body"],
        )
    )
    story.append(
        p(
            "<b>Contributions:</b> (1) a three-stage pipeline from requirements to design-phase UML "
            "via a structured specification; (2) an MMMU-weighted composite score with a "
            "render-failure indicator; (3) a majority-vote acceptance gate (dual-signal quality); "
            "(4) comparison with five prior approaches on render success, semantic alignment, and "
            "human correlation; (5) a public dataset of 8,000 (specification, PlantUML, score) triples.",
            S["Body"],
        )
    )

    story.append(p("7. Threats to validity and planned extensions", S["Sec"]))
    story.append(
        p(
            "<b>Internal.</b> Weights come from MMMU (general multimodal reasoning), not a "
            "UML-specific benchmark. <b>External.</b> The 8,000 specifications are "
            "pipeline-generated and may miss some industrial requirement ambiguity. "
            "<b>Construct.</b> The shared 0–6 rubric’s 3-versus-4 boundary was the most frequent "
            "human disagreement, especially on component diagrams. Planned extensions: sequence "
            "and activity diagrams, real OSS requirement corpora, and UML-specific VLM calibration.",
            S["Body"],
        )
    )

    story.append(p("8. Request to the committee member", S["Sec"]))
    story.append(
        p(
            "Dr. Yutong Zhao has approved inviting you to the defense committee. I would be "
            "honored if you would consider serving. After you accept, committee members sign the "
            "DocuSign <b>Thesis Approval Form</b> when the manuscript is ready for Thesis Office "
            "submission (https://www.csulb.edu/thesis-and-dissertation-office/signature-page-procedure). "
            "I will send that form only after you have agreed, as advised by the graduate advisor. "
            "I am happy to share the full draft, paper, or a live pipeline demonstration on request.",
            S["Body"],
        )
    )
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.6, color=NAVY, spaceBefore=2, spaceAfter=4))
    story.append(
        p(
            "Respectfully submitted for committee consideration  ·  Dipak Yadav  ·  "
            "Chair: Dr. Yutong Zhao  ·  CECS, California State University, Long Beach",
            S["Foot"],
        )
    )

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)

    github_compat_pdf(out)
    try:
        from pypdf import PdfReader

        n = len(PdfReader(str(out)).pages)
    except Exception:
        n = "?"
    print(f"Wrote {out} pages={n} bytes={out.stat().st_size}")


def main():
    for dest in OUTS:
        try:
            build_pdf(dest)
        except OSError as exc:
            print(f"skip {dest}: {exc}")


if __name__ == "__main__":
    main()
