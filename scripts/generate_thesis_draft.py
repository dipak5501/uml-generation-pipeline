#!/usr/bin/env python3
"""Generate a CSULB-style M.S. thesis draft PDF from paper/ + implementation notes.

Outputs:
  reports/Dipak_Yadav_MS_Thesis_Draft.pdf
  thesis/Dipak_Yadav_MS_Thesis_Draft.pdf
  ~/Desktop/Dipak_Yadav_MS_Thesis_Draft.pdf (when Desktop exists)

This is an advisor-review DRAFT, not the official Thesis Office template.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = Path.home() / "Desktop" / "Dipak_Yadav_MS_Thesis_Draft.pdf"
LOCAL = ROOT / "thesis" / "Dipak_Yadav_MS_Thesis_Draft.pdf"
REPORTS = ROOT / "reports" / "Dipak_Yadav_MS_Thesis_Draft.pdf"
ARTIFACTS = Path("/opt/cursor/artifacts") / "Dipak_Yadav_MS_Thesis_Draft.pdf"
FIG_DIRS = [ROOT / "paper", ROOT / "output" / "figures"]


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def latex_to_text(s: str) -> str:
    # Drop LaTeX comments
    lines = []
    for ln in s.splitlines():
        if ln.strip().startswith("%"):
            continue
        lines.append(re.sub(r"(?<!\\)%.*", "", ln))
    s = "\n".join(lines)
    # Drop tables / figures / equations blocks (keep captions later separately)
    s = re.sub(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", " ", s, flags=re.S)
    s = re.sub(r"\\begin\{figure\*?\}.*?\\end\{figure\*?\}", " ", s, flags=re.S)
    s = re.sub(r"\\begin\{equation\*?\}.*?\\end\{equation\*?\}", " ", s, flags=re.S)
    s = re.sub(r"\\begin\{align\*?\}.*?\\end\{align\*?\}", " ", s, flags=re.S)
    s = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", " ", s, flags=re.S)
    s = re.sub(r"\\cite\{[^}]*\}", "", s)
    s = re.sub(r"\\(?:eq)?ref\{[^}]*\}", "", s)
    s = re.sub(r"\\label\{[^}]*\}", "", s)
    s = re.sub(r"\\(textbf|textit|emph|texttt|underline)\{([^}]*)\}", r"\2", s)
    s = re.sub(r"\\(?:sub)*section\*?\{([^}]*)\}", r"\n\n§ \1\n\n", s)
    s = re.sub(r"\\paragraph\{([^}]*)\}", r"\n\n\1. ", s)
    s = re.sub(r"\\caption\{([^}]*)\}", r"", s)
    s = re.sub(r"\\item\s*", "\n• ", s)
    s = re.sub(r"\\begin\{[^}]+\}", "", s)
    s = re.sub(r"\\end\{[^}]+\}", "", s)
    s = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", " ", s)
    s = (
        s.replace("~", " ")
        .replace("\\%", "%")
        .replace("\\&", "&")
        .replace("\\$", "$")
        .replace("``", '"')
        .replace("''", '"')
        .replace("---", "—")
        .replace("--", "–")
        .replace("\\{", "{")
        .replace("\\}", "}")
    )
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def extract_section(tex: str, title: str) -> str:
    pat = rf"\\section\{{{re.escape(title)}\}}"
    m = re.search(pat, tex)
    if not m:
        return ""
    rest = tex[m.end() :]
    m2 = re.search(r"\\section\{", rest)
    chunk = rest[: m2.start()] if m2 else rest
    return latex_to_text(chunk)


def find_fig(name: str) -> Path | None:
    for d in FIG_DIRS:
        p = d / name
        if p.is_file():
            return p
    return None


def build_styles():
    styles = getSampleStyleSheet()
    # CSULB-ish: Times, 12pt, double-spaced body
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            fontName="Times-Bold",
            fontSize=14,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSub",
            fontName="Times-Roman",
            fontSize=12,
            leading=18,
            alignment=TA_CENTER,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSmall",
            fontName="Times-Roman",
            fontSize=12,
            leading=18,
            alignment=TA_CENTER,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Chap",
            fontName="Times-Bold",
            fontSize=14,
            leading=22,
            alignment=TA_CENTER,
            spaceBefore=18,
            spaceAfter=16,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H1",
            fontName="Times-Bold",
            fontSize=12,
            leading=20,
            alignment=TA_CENTER,
            spaceBefore=16,
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2",
            fontName="Times-Bold",
            fontSize=12,
            leading=20,
            spaceBefore=16,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H3",
            fontName="Times-Bold",
            fontSize=12,
            leading=18,
            spaceBefore=12,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            fontName="Times-Roman",
            fontSize=12,
            leading=24,  # double space
            alignment=TA_JUSTIFY,
            spaceAfter=0,
            firstLineIndent=24,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyNI",
            fontName="Times-Roman",
            fontSize=12,
            leading=24,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ThesisBullet",
            fontName="Times-Roman",
            fontSize=12,
            leading=24,
            alignment=TA_JUSTIFY,
            leftIndent=18,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Caption",
            fontName="Times-Italic",
            fontSize=11,
            leading=16,
            alignment=TA_CENTER,
            spaceBefore=6,
            spaceAfter=16,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TOC",
            fontName="Times-Roman",
            fontSize=12,
            leading=22,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Foot",
            fontName="Times-Roman",
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
        )
    )
    return styles


def add_text(story, styles, text: str, style_name: str = "Body") -> None:
    if not text:
        return
    # Split on § headings and bullets
    blocks = re.split(r"\n\s*\n", text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if block.startswith("§ "):
            title = block[2:].strip()
            story.append(Paragraph(esc(title), styles["H3"]))
            continue
        if block.startswith("• ") or "\n• " in block:
            for line in block.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if line.startswith("• "):
                    story.append(Paragraph(esc(line), styles["ThesisBullet"]))
                else:
                    story.append(Paragraph(esc(line), styles["BodyNI"]))
            continue
        # Split long blocks into ~2–3 sentence paragraphs
        sentences = re.split(r"(?<=[.!?])\s+", block)
        buf: list[str] = []
        for sent in sentences:
            buf.append(sent)
            joined = " ".join(buf)
            if len(joined) >= 380:
                story.append(Paragraph(esc(joined), styles[style_name]))
                buf = []
        if buf:
            story.append(Paragraph(esc(" ".join(buf)), styles[style_name]))


def add_fig(story, styles, name: str, caption: str, width: float = 5.6 * inch) -> None:
    p = find_fig(name)
    if not p:
        story.append(Paragraph(esc(f"[Figure missing: {name}]"), styles["Caption"]))
        return
    try:
        story.append(Image(str(p), width=width, height=width * 0.58, kind="proportional"))
        story.append(Paragraph(esc(caption), styles["Caption"]))
    except Exception:
        story.append(Paragraph(esc(f"[Figure unreadable: {name}]"), styles["Caption"]))


def table(story, styles, data, caption: str, col_widths=None) -> None:
    t = Table(data, colWidths=col_widths)
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LEADING", (0, 0), (-1, -1), 13),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.92, 0.92, 0.92)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(Spacer(1, 8))
    story.append(t)
    story.append(Paragraph(esc(caption), styles["Caption"]))


def lit_review_paragraphs(lit_tex: str) -> str:
    """Flatten literature_review.tex into readable prose."""
    # Keep Summary / Relevance blocks
    text = latex_to_text(lit_tex)
    # Trim title/author junk if present
    return text


def main() -> None:
    styles = build_styles()
    tex = (ROOT / "paper" / "main.tex").read_text(encoding="utf-8")
    lit = (ROOT / "paper" / "literature_review.tex").read_text(encoding="utf-8")

    intro = extract_section(tex, "Introduction")
    related = extract_section(tex, "Related Work")
    methods = extract_section(tex, "Methods")
    exp = extract_section(tex, "Experimental Design")
    results = extract_section(tex, "Results and Discussion")
    threats = extract_section(tex, "Threats to Validity")
    conclusion = extract_section(tex, "Conclusion")
    lit_text = lit_review_paragraphs(lit)

    story: list = []

    # ---------- COVER ----------
    story.append(Spacer(1, 0.9 * inch))
    story.append(
        Paragraph(
            "AUTOMATED UML DATASET GENERATION FROM NATURAL-LANGUAGE "
            "REQUIREMENTS WITH MULTIMODAL VERIFICATION FOR SOFTWARE DESIGN",
            styles["CoverTitle"],
        )
    )
    story.append(Spacer(1, 0.35 * inch))
    story.append(Paragraph("A Thesis", styles["CoverSub"]))
    story.append(
        Paragraph(
            "Presented to the Department of Computer Engineering and Computer Science<br/>"
            "College of Engineering<br/>"
            "California State University, Long Beach",
            styles["CoverSmall"],
        )
    )
    story.append(Spacer(1, 0.3 * inch))
    story.append(
        Paragraph(
            "In Partial Fulfillment of the Requirements for the Degree<br/>"
            "Master of Science in Computer Science",
            styles["CoverSmall"],
        )
    )
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph("by", styles["CoverSmall"]))
    story.append(Paragraph("<b>Dipak Yadav</b>", styles["CoverSub"]))
    story.append(Paragraph("Campus ID: 033783670", styles["CoverSmall"]))
    story.append(Spacer(1, 0.35 * inch))
    story.append(Paragraph("Committee Approval:", styles["CoverSmall"]))
    story.append(Paragraph("Dr. Yutong Zhao, Chair", styles["CoverSmall"]))
    story.append(Paragraph("Dr. Muhammad Abdul Basit, Member", styles["CoverSmall"]))
    story.append(Paragraph("Dr. Xin Qin, Member", styles["CoverSmall"]))
    story.append(Spacer(1, 0.45 * inch))
    story.append(Paragraph("California State University, Long Beach", styles["CoverSmall"]))
    story.append(Paragraph("December 2026", styles["CoverSmall"]))
    story.append(
        Paragraph(
            "<i>DRAFT for advisor review (CECS 698) — not Thesis Office final format</i>",
            styles["CoverSmall"],
        )
    )
    story.append(PageBreak())

    # ---------- COPYRIGHT / SIGNATURE PLACEHOLDERS ----------
    story.append(Paragraph("COPYRIGHT PAGE", styles["H1"]))
    story.append(
        Paragraph(
            "Copyright © 2026 by Dipak Yadav. All rights reserved. "
            "No part of this thesis may be reproduced without the author's permission, "
            "except for brief quotations in scholarly review.",
            styles["BodyNI"],
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("THESIS COMMITTEE APPROVAL", styles["H1"]))
    story.append(
        Paragraph(
            "This thesis has been examined and approved by the thesis committee of "
            "Dipak Yadav for the degree of Master of Science in Computer Science.",
            styles["BodyNI"],
        )
    )
    for name in [
        "Dr. Yutong Zhao, Chair ___________________________ Date ________",
        "Dr. Muhammad Abdul Basit, Member ________________ Date ________",
        "Dr. Xin Qin, Member _____________________________ Date ________",
    ]:
        story.append(Spacer(1, 0.25 * inch))
        story.append(Paragraph(esc(name), styles["BodyNI"]))
    story.append(PageBreak())

    # ---------- ABSTRACT ----------
    story.append(Paragraph("ABSTRACT", styles["H1"]))
    abstract = (
        "Unified Modeling Language (UML) remains a fundamental medium for expressing "
        "software architecture and design intent, yet manual diagram construction is "
        "labor-intensive, inconsistent, and difficult to scale. This thesis presents an "
        "automated three-stage pipeline for generating design-phase UML artifacts from "
        "natural-language requirements and validating them through multimodal verification. "
        "Stage 1 uses LLaMA 3.2-1B-Instruct to convert free-form requirements into structured "
        "JSON specifications. Stage 2 uses DeepSeek-R1-Distill-Qwen-32B with Chain-of-Thought "
        "prompting to synthesize PlantUML code. Stage 3 renders each artifact and evaluates "
        "it with an ensemble of three vision-language models whose scores are combined via "
        "MMMU-benchmark-weighted aggregation (weights 53.1, 50.7, and 39.9) together with a "
        "majority-voting acceptance gate (τ = 4). Render failures receive composite score S = 0. "
        "A sample enters the verified corpus only if it is majority-accepted and S ≥ 3.0. "
        "The study targets an 8,000-sample corpus covering class, object, component, and "
        "package diagrams (2,000 each). Paper-scale results show class diagrams achieving "
        "95.7% render success and Pearson r = 0.82 versus human experts, while package "
        "diagrams are hardest (81.1% success, r = 0.55). Inter-rater reliability among 80 "
        "domain experts reaches Fleiss' κ = 0.68 (substantial agreement). Beyond the paper "
        "baseline, this thesis delivers a production FastAPI and Streamlit system on an Apple "
        "Mac Studio (M1 Ultra, 128 GB unified memory) with source-code input, fidelity gates, "
        "MLX LoRA PlantUML (source-code 30k adapter), dual-Ollama VLM serving, local "
        "Aya-Vision-8B, a remote command agent, and script-without-types recovery. The public "
        "repository is https://github.com/dipak5501/uml-generation-pipeline."
    )
    add_text(story, styles, abstract, "BodyNI")
    story.append(Spacer(1, 0.2 * inch))
    story.append(
        Paragraph(
            "<b>Keywords:</b> UML generation, natural-language requirements, PlantUML, "
            "multimodal verification, MMMU-weighted scoring, majority vote, software design, "
            "dataset generation, vision-language models",
            styles["BodyNI"],
        )
    )
    story.append(PageBreak())

    # ---------- ACKNOWLEDGMENTS ----------
    story.append(Paragraph("ACKNOWLEDGMENTS", styles["H1"]))
    add_text(
        story,
        styles,
        "I thank my thesis advisor, Dr. Yutong Zhao, for guidance throughout CECS 697 and "
        "CECS 698, and for continuous feedback on both the research framing and the "
        "engineering system. I thank committee members Dr. Muhammad Abdul Basit and "
        "Dr. Xin Qin for their time and constructive comments. I also thank the Department "
        "of Computer Engineering and Computer Science staff for support with Independent "
        "Study registration and thesis procedures. Any remaining errors are my own.",
        "BodyNI",
    )
    story.append(PageBreak())

    # ---------- TOC ----------
    story.append(Paragraph("TABLE OF CONTENTS", styles["H1"]))
    for item in [
        "ABSTRACT",
        "ACKNOWLEDGMENTS",
        "LIST OF TABLES",
        "LIST OF FIGURES",
        "CHAPTER 1. INTRODUCTION",
        "CHAPTER 2. RELATED WORK AND LITERATURE REVIEW",
        "CHAPTER 3. METHODS AND SYSTEM DESIGN",
        "CHAPTER 4. IMPLEMENTATION AND SYSTEM ADVANCES",
        "CHAPTER 5. EXPERIMENTAL DESIGN AND RESULTS",
        "CHAPTER 6. DISCUSSION, LIMITATIONS, AND THREATS TO VALIDITY",
        "CHAPTER 7. CONCLUSION AND FUTURE WORK",
        "REFERENCES",
        "APPENDIX A. PROMPT TEMPLATES AND CONFIGURATION",
        "APPENDIX B. REPOSITORY AND REPRODUCIBILITY",
        "APPENDIX C. FIDELITY AND FAILURE ANALYSIS NOTES",
        "APPENDIX D. GLOSSARY",
    ]:
        story.append(Paragraph(esc(item), styles["TOC"]))
    story.append(PageBreak())

    story.append(Paragraph("LIST OF TABLES", styles["H1"]))
    for t in [
        "Table 1. Stage-1 model comparison (JSON validity)",
        "Table 2. Render success and mean composite score by diagram type",
        "Table 3. Automated vs human correlation by diagram type",
        "Table 4. Paper–implementation alignment summary",
        "Table 5. Local fidelity check summary",
        "Table 6. Comparison dimensions versus prior approaches (summary)",
    ]:
        story.append(Paragraph(esc(t), styles["TOC"]))
    story.append(PageBreak())

    story.append(Paragraph("LIST OF FIGURES", styles["H1"]))
    for t in [
        "Figure 1. Conceptual three-stage pipeline (described in text)",
        "Figure 2. VLM score distributions (local analysis)",
        "Figure 3. Package diagram composite score distribution",
        "Figure 4. Object diagram composite score distribution",
        "Figure 5. Component diagram composite score distribution",
        "Figure 6. Class diagram composite score distribution (if available)",
    ]:
        story.append(Paragraph(esc(t), styles["TOC"]))
    story.append(PageBreak())

    # ================= CH 1 =================
    story.append(Paragraph("CHAPTER 1", styles["Chap"]))
    story.append(Paragraph("INTRODUCTION", styles["H1"]))
    story.append(Paragraph("1.1 Motivation and Problem Statement", styles["H2"]))
    add_text(story, styles, intro)
    story.append(Paragraph("1.2 Research Questions", styles["H2"]))
    for rq in [
        "RQ1: How effectively can a decomposed LLM-based pipeline generate syntactically "
        "and semantically valid UML diagrams from natural-language requirements at scale?",
        "RQ2: To what degree does multimodal ensemble verification correlate with expert "
        "human evaluation of generated UML diagrams?",
        "RQ3: How does accuracy vary across UML diagram families (class, object, component, "
        "package), and what failure patterns explain the differences?",
    ]:
        story.append(Paragraph(esc("• " + rq), styles["ThesisBullet"]))
    story.append(Paragraph("1.3 Contributions", styles["H2"]))
    for c in [
        "A three-stage pipeline converting natural-language requirements into design-phase "
        "UML via structured JSON specifications and PlantUML synthesis.",
        "An MMMU-weighted composite score with a hard PlantUML render gate (failed renders "
        "receive S = 0).",
        "A majority-voting acceptance gate (τ = 4) and dataset inclusion rule requiring "
        "acceptance and S ≥ 3.0.",
        "Comparative evaluation across four diagram types with human correlation analysis "
        "(80 experts; Fleiss' κ = 0.68 overall).",
        "A public reproducible implementation (FastAPI + Streamlit) with advances: "
        "source-code input (Java/Python/C), fidelity gates, MLX LoRA PlantUML on Mac Studio, "
        "optional NVIDIA PEFT CUDA LoRA, dual-Ollama VLM serving, local Aya-Vision-8B on "
        "128 GB unified memory, remote agent API, and script-without-types recovery.",
    ]:
        story.append(Paragraph(esc("• " + c), styles["ThesisBullet"]))
    story.append(Paragraph("1.4 Scope and Assumptions", styles["H2"]))
    add_text(
        story,
        styles,
        "This thesis focuses on design-phase structural UML: class, object, component, and "
        "package diagrams. Behavioral diagrams (sequence, state) are left to future work, "
        "except that the implemented system also supports flowchart/activity views for "
        "process-oriented source scripts. Requirements are assumed to be English-language "
        "software descriptions of moderate length. PlantUML is the exclusive textual UML "
        "encoding. Evaluation assumes that vision-language models can serve as scalable "
        "proxies for human judgment when combined via MMMU-weighted aggregation and majority "
        "voting, an assumption tested via Pearson correlation against human experts.",
        "BodyNI",
    )
    story.append(Paragraph("1.5 Thesis Organization", styles["H2"]))
    add_text(
        story,
        styles,
        "Chapter 2 reviews related work and expands the literature review used for the "
        "paper. Chapter 3 presents the method and scoring design. Chapter 4 describes the "
        "software implementation and advances beyond the paper baseline. Chapter 5 reports "
        "experimental design and results. Chapter 6 discusses limitations and threats to "
        "validity. Chapter 7 concludes and outlines future work. Appendices document prompts, "
        "reproducibility steps, fidelity notes, and a glossary.",
        "BodyNI",
    )
    story.append(PageBreak())

    # ================= CH 2 =================
    story.append(Paragraph("CHAPTER 2", styles["Chap"]))
    story.append(Paragraph("RELATED WORK AND LITERATURE REVIEW", styles["H1"]))
    story.append(Paragraph("2.1 Related Work (Paper Narrative)", styles["H2"]))
    add_text(story, styles, related)
    story.append(Paragraph("2.2 Annotated Literature Review", styles["H2"]))
    add_text(
        story,
        styles,
        "The following extended summaries document the primary sources that ground this "
        "thesis. Each entry records the contribution, limitations, and relevance to UML "
        "generation or multimodal evaluation.",
        "BodyNI",
    )
    add_text(story, styles, lit_text)
    story.append(Paragraph("2.3 Gap Summary", styles["H2"]))
    add_text(
        story,
        styles,
        "Prior work often improves generation without scalable semantic validation, relies "
        "on a single judge model, focuses on one diagram family, or lacks a reproducible "
        "verified UML corpus. This thesis couples generation with MMMU-weighted multimodal "
        "ensemble verification and majority voting across four design-phase diagram types, "
        "and ships a public system that can be operated locally for demonstration and "
        "extension.",
        "BodyNI",
    )
    story.append(PageBreak())

    # ================= CH 3 =================
    story.append(Paragraph("CHAPTER 3", styles["Chap"]))
    story.append(Paragraph("METHODS AND SYSTEM DESIGN", styles["H1"]))
    story.append(
        Paragraph(
            "Figure 1 (conceptual). Natural-language requirements enter Stage 1 (JSON "
            "specification). Stage 2 synthesizes PlantUML with reasoning. Stage 3 renders "
            "the diagram and applies VLM ensemble scoring with MMMU weights and majority "
            "vote. Failed renders receive S = 0 and do not enter VLM scoring.",
            styles["Caption"],
        )
    )
    add_text(story, styles, methods)
    story.append(Paragraph("3.5 Scoring Equations (Paper-Faithful)", styles["H2"]))
    add_text(
        story,
        styles,
        "Let s_ij be the score of VLM j on diagram i on a 0–6 scale, and let w_j be the "
        "MMMU accuracy weights w = (53.1, 50.7, 39.9) for Qwen2.5-VL-3B-Instruct, "
        "LLaMA-3.2-11B-Vision-Instruct, and Aya-Vision-8B respectively. Define δ_i = 1 if "
        "diagram i passes the PlantUML render gate and δ_i = 0 otherwise. The composite "
        "score is S_i = δ_i · (Σ_j w_j s_ij) / (Σ_j w_j). When rendering fails, S_i = 0. "
        "Each VLM casts vote v_ij = 1 if s_ij ≥ τ with τ = 4, else 0. The majority "
        "acceptance indicator is A_i = 1 if Σ_j v_ij ≥ 2. A diagram enters the final "
        "dataset only if A_i = 1 and S_i ≥ 3.0.",
        "BodyNI",
    )
    story.append(Paragraph("3.6 Worked Numerical Example", styles["H2"]))
    add_text(
        story,
        styles,
        "Suppose VLMs assign scores 5, 4, and 3 for a rendered class diagram (δ = 1). Then "
        "S = (53.1·5 + 50.7·4 + 39.9·3) / 143.7 = 588.0 / 143.7 ≈ 4.09. Votes relative to "
        "τ = 4 are yes, yes, and no, so majority accepts. Because S ≥ 3.0, the sample is "
        "dataset-eligible. If PlantUML compilation fails, δ = 0, S = 0, and the sample is "
        "excluded from semantic scoring and from the verified corpus.",
        "BodyNI",
    )
    table(
        story,
        styles,
        [
            ["Model", "Params", "Time (s)", "JSON Valid (%)"],
            ["LLaMA 3.2-1B-Instruct", "1B", "1.8", "94.0"],
            ["DeepSeek-R1-Qwen-1.5B", "1.5B", "2.1", "88.5"],
            ["Gemma 2-2B", "2B", "3.2", "82.0"],
        ],
        "Table 1. Stage-1 model comparison on 100 requirement prompts (paper).",
        [2.2 * inch, 1.0 * inch, 1.1 * inch, 1.5 * inch],
    )
    story.append(PageBreak())

    # ================= CH 4 =================
    story.append(Paragraph("CHAPTER 4", styles["Chap"]))
    story.append(Paragraph("IMPLEMENTATION AND SYSTEM ADVANCES", styles["H1"]))
    story.append(Paragraph("4.1 Software Architecture", styles["H2"]))
    add_text(
        story,
        styles,
        "The thesis deliverable includes a complete application stack. The backend is "
        "implemented with FastAPI and SQLModel for job and artifact persistence. The "
        "frontend is a Streamlit multipage UI covering single generation, batch "
        "orchestration, artifact review, human evaluation, analytics, and system design "
        "documentation. Versioned prompts live under prompts/. A provider factory selects "
        "among OpenAI-compatible APIs, Hugging Face routers, Ollama, mock providers for "
        "tests, and an MLX LoRA PlantUML adapter for local Stage-2 generation. CLI scripts "
        "support corpus construction, evaluation, fine-tuning, and dual-Ollama setup. The "
        "public repository is https://github.com/dipak5501/uml-generation-pipeline.",
        "BodyNI",
    )
    story.append(Paragraph("4.2 Stage-1 JSON and Grounding", styles["H2"]))
    add_text(
        story,
        styles,
        "Stage-1 prompts request a JSON object with diagram_type, summary, entities, "
        "relationships, and optional packages, components, objects, and process_steps. "
        "The module app/services/spec_json.py parses and validates JSON, extracts named "
        "concepts from natural language, merges grounded entity names from requirement "
        "text or source-code analysis, and stores structured_json with validity metrics. "
        "Prose derived from JSON is passed to Stage-2 prompts for readability while "
        "preserving paper-style structure. Invalid JSON triggers repair or fallback "
        "structuring rather than silent prose-only continuation when possible.",
        "BodyNI",
    )
    story.append(Paragraph("4.3 Stage-2 Generation, Validation, and Fidelity", styles["H2"]))
    add_text(
        story,
        styles,
        "PlantUML is generated with diagram-specific prompts and optional Chain-of-Thought. "
        "Outputs are sanitized, including repair of invalid worded arrows such as "
        "--inheritance--> into legal PlantUML connectors. Static validators reject empty "
        "diagram bodies and illegal package declarations. A fidelity gate compares "
        "PlantUML against Stage-1 entity and relationship coverage; weak or ModuleN-style "
        "outputs are replaced by a deterministic builder in plantuml_from_spec.py. A repair "
        "loop attempts LLM fixes before assigning render failure. This design preserves the "
        "paper's render-gate philosophy while reducing professional-tester failures in which "
        "diagrams compile yet omit required domain entities.",
        "BodyNI",
    )
    story.append(Paragraph("4.4 Source-Code Mode and Script-Without-Types", styles["H2"]))
    add_text(
        story,
        styles,
        "In addition to natural-language requirements, the system accepts source code. "
        "Structural analysis recovers classes and relationships for Python, Java, and other "
        "languages when types are present. Critically, scripts that contain no class "
        "declarations (for example, a py2puml driver that only assigns variables such as "
        "source_folder and domain_module) must not invent classes from those variables. "
        "entity_names() returns only real class declarations. When a class or object "
        "diagram is requested for such a script, the orchestrator redirects to a flowchart "
        "of the script process. This fix was validated after a professional fidelity review "
        "flagged false class diagrams for driver scripts.",
        "BodyNI",
    )
    story.append(Paragraph("4.5 Local Inference Stack", styles["H2"]))
    add_text(
        story,
        styles,
        "The paper Stage-2 model DeepSeek-R1-Distill-Qwen-32B is not run in-process on the "
        "student workstation. On Apple Silicon the stand-in is an MLX LoRA adapter on "
        "mlx-community/Qwen2.5-0.5B-Instruct-4bit. Production on the Math-department Mac "
        "Studio (Apple M1 Ultra, 128 GB unified memory) uses "
        "FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-sourcecode-30k after 6,000 LoRA "
        "iterations on a Java/Python/C source-code corpus. Dual Ollama daemons serve "
        "LLaMA-3.2-Vision-11B on Ollama 0.24 at :11434 and Qwen2.5-VL-3B on Ollama 0.32 at "
        ":11435; a single 0.32 process cannot load mllama. Aya-Vision-8B is loaded in-process "
        "with Transformers on MPS when unified memory is at least 64 GB (the 24 GB M2 hung on "
        "model.to(mps)). NVIDIA hosts retrain PEFT LoRA with scripts/finetune_plantuml_cuda.py "
        "and may serve Aya via vLLM on port 8001. Environment variables ACCEPTANCE_TAU and "
        "MIN_COMPOSITE_FOR_DATASET encode the paper thresholds. Mock providers use the same "
        "fidelity builders so unit tests run without GPUs.",
        "BodyNI",
    )
    story.append(Paragraph("4.5.1 Production Mac Studio Deployment", styles["H3"]))
    add_text(
        story,
        styles,
        "The always-on server is a user-level LaunchAgent stack (no sudo): FastAPI on :8000, "
        "Streamlit on :8501, dual Ollama, caffeinate, and Cloudflare quick tunnels. A remote "
        "HTTP agent at /api/agent accepts allowlisted commands (health, server-status, "
        "generate, smoke-test, training-status, restart-api, restart-ui) with Bearer token "
        "auth. Public UI and API URLs are written to data/run/public_*.txt when tunnels "
        "restart. Measured live generate on 2026-08-31 produced a class diagram with render "
        "success and composite S approximately 5.37 using the three-VLM ensemble. Keep the "
        "Mac user logged in (screen lock is permitted; Log Out stops LaunchAgents).",
        "BodyNI",
    )
    story.append(Paragraph("4.6 Paper–Code Alignment", styles["H2"]))
    table(
        story,
        styles,
        [
            ["Paper claim", "Implementation"],
            ["3-stage pipeline", "app/services/orchestration.py"],
            ["JSON Stage-1", "spec_json.py + Stage-1 prompts"],
            ["MMMU weights 53.1/50.7/39.9", "settings + scoring"],
            ["Render fail → S=0", "verify_scores(render_ok=False)"],
            ["Majority τ=4, S≥3.0", "scoring defaults / .env"],
            ["4 diagram types", "class/object/component/package (flowchart training only)"],
            ["Human 4 criteria", "UI rubric (1–5) + paper 0–6 protocol"],
            ["Mac Studio production", "MLX 30k LoRA + dual Ollama + local Aya"],
            ["NVIDIA path", "PEFT CUDA LoRA + optional vLLM Aya"],
        ],
        "Table 4. Paper–implementation alignment summary.",
        [3.1 * inch, 3.1 * inch],
    )
    story.append(Paragraph("4.7 Advances Beyond the Paper Baseline", styles["H2"]))
    for a in [
        "Source-code input mode with structural recovery (Python, Java, C).",
        "Flowchart/activity diagrams as an additional process view for scripts without types.",
        "MLX LoRA PlantUML on Apple Silicon (production adapter: source-code 30k).",
        "NVIDIA PEFT CUDA LoRA trainer and inference provider.",
        "Dual Ollama hosting for Qwen2.5-VL and LLaMA-Vision.",
        "Local Aya-Vision-8B on Mac Studio 128 GB (refuse in-process below 64 GB).",
        "Fidelity gate and deterministic PlantUML-from-spec builders.",
        "Script-without-types recovery (no fake classes from variables).",
        "Remote agent API and Cloudflare public tunnels for 24/7 demo.",
        "Package failure taxonomy, human evaluation UI, and analytics export.",
    ]:
        story.append(Paragraph(esc("• " + a), styles["ThesisBullet"]))
    story.append(PageBreak())

    # ================= CH 5 =================
    story.append(Paragraph("CHAPTER 5", styles["Chap"]))
    story.append(Paragraph("EXPERIMENTAL DESIGN AND RESULTS", styles["H1"]))
    story.append(Paragraph("5.1 Experimental Design", styles["H2"]))
    add_text(story, styles, exp)
    story.append(Paragraph("5.2 Paper-Scale Results (RQ1–RQ3)", styles["H2"]))
    add_text(story, styles, results)
    table(
        story,
        styles,
        [
            ["Diagram", "Failures", "Success %", "Mean Score", "SD"],
            ["Class", "87", "95.7", "4.31", "0.74"],
            ["Object", "112", "94.4", "4.09", "0.81"],
            ["Component", "169", "91.6", "3.87", "0.93"],
            ["Package", "379", "81.1", "3.12", "1.04"],
            ["Overall", "747", "94.4", "3.85", "0.98"],
        ],
        "Table 2. Render success and mean composite score by diagram type (n = 2,000 per type).",
        [1.2 * inch, 1.0 * inch, 1.1 * inch, 1.2 * inch, 0.8 * inch],
    )
    table(
        story,
        styles,
        [
            ["Diagram", "Pearson r", "p-value", "Fleiss κ"],
            ["Class", "0.82", "<0.001", "0.74"],
            ["Object", "0.76", "<0.001", "0.71"],
            ["Component", "0.68", "<0.001", "0.65"],
            ["Package", "0.55", "=0.003", "0.58"],
            ["Overall", "0.71", "<0.001", "0.68"],
        ],
        "Table 3. Automated vs human correlation and inter-rater reliability (40 diagrams, 80 evaluators).",
        [1.4 * inch, 1.2 * inch, 1.2 * inch, 1.2 * inch],
    )
    story.append(Paragraph("5.3 Local Repository Validation", styles["H2"]))
    add_text(
        story,
        styles,
        "Using the public repository, scored Hugging Face subsets were analyzed locally. "
        "Package diagrams again show the lowest mean composite among available scored sets, "
        "consistent with RQ3. After fidelity hardening, a six-case grounded evaluation "
        "(NL library, hospital, checkout, banking, plus Python and Java source) achieved "
        "6/6 MATCH with mean entity recall 1.0 and mean fidelity approximately 0.94. "
        "Scripts without class declarations are redirected to process flowcharts rather than "
        "false class diagrams. These local checks do not replace the paper-scale 8,000-sample "
        "campaign, but they demonstrate that the released system behaves correctly under "
        "tester scrutiny on representative cases.",
        "BodyNI",
    )
    table(
        story,
        styles,
        [
            ["Case family", "Result", "Notes"],
            ["NL class/object/component/package", "MATCH", "Entity names preserved"],
            ["Python/Java with types", "MATCH", "Real classes only"],
            ["Script without types", "Flowchart", "No fake classes"],
        ],
        "Table 5. Local fidelity check summary (post-hardening).",
        [2.6 * inch, 1.2 * inch, 2.4 * inch],
    )
    add_fig(story, styles, "vlm_scores_all.png", "Figure 2. VLM score distributions across models (local analysis).")
    add_fig(story, styles, "scores_package.png", "Figure 3. Package diagram composite score distribution.")
    add_fig(story, styles, "scores_object.png", "Figure 4. Object diagram composite score distribution.")
    add_fig(story, styles, "scores_component.png", "Figure 5. Component diagram composite score distribution.")
    add_fig(story, styles, "scores_class.png", "Figure 6. Class diagram composite score distribution.")
    story.append(Paragraph("5.4 Comparison with Prior Approaches", styles["H2"]))
    add_text(
        story,
        styles,
        "Relative to prior LLM-based UML or architecture diagram generators, the distinctive "
        "contribution is verification as a first-class component: MMMU-weighted ensemble "
        "scoring, majority vote, and a hard render gate. Generation-only systems can report "
        "high syntactic success while still omitting required entities. Human-only evaluation "
        "does not scale to thousands of samples. This thesis therefore reports both render "
        "success and human-correlated multimodal scores, and ships tooling that rejects "
        "semantically weak but syntactically valid diagrams when fidelity coverage fails.",
        "BodyNI",
    )
    story.append(PageBreak())

    # ================= CH 6 =================
    story.append(Paragraph("CHAPTER 6", styles["Chap"]))
    story.append(
        Paragraph(
            "DISCUSSION, LIMITATIONS, AND THREATS TO VALIDITY",
            styles["H1"],
        )
    )
    story.append(Paragraph("6.1 Discussion", styles["H2"]))
    add_text(
        story,
        styles,
        "The dual-signal design (continuous S and binary majority acceptance) provides both "
        "ranking and inclusion decisions for dataset construction. Class diagrams are the "
        "most reliable family for both generation and evaluation; package diagrams remain "
        "the primary bottleneck due to nesting syntax and containment-versus-dependency "
        "ambiguity. Implementation advances such as the fidelity gate trade pure end-to-end "
        "LLM generation for professional correctness—especially important when models invent "
        "ModuleN placeholders or treat script variables as classes. For CECS 698, the "
        "manuscript and the runnable system should be read together: the paper states the "
        "scientific protocol; the repository demonstrates operable engineering under resource "
        "constraints.",
        "BodyNI",
    )
    story.append(Paragraph("6.2 Limitations", styles["H2"]))
    for lim in [
        "On-device Stage 2 uses Qwen2.5-0.5B LoRA rather than DeepSeek-R1-32B. Aya-Vision-8B "
        "runs locally on the 128 GB Mac Studio; 24 GB Macs must not load Aya on MPS.",
        "The VLM prompt currently requests a joint SCORE; the paper protocol discusses "
        "four 0–6 criteria, while the human UI uses 1–5 Likert items.",
        "Assembled local corpora are not identical to regenerating the paper’s full "
        "domain × prompt matrix in one live run.",
        "Package diagrams remain the hardest family despite validators and builders.",
        "Behavioral UML (sequence/state) is out of scope for the verified 8k structural set.",
    ]:
        story.append(Paragraph(esc("• " + lim), styles["ThesisBullet"]))
    story.append(Paragraph("6.3 Threats to Validity", styles["H2"]))
    add_text(story, styles, threats)
    story.append(PageBreak())

    # ================= CH 7 =================
    story.append(Paragraph("CHAPTER 7", styles["Chap"]))
    story.append(Paragraph("CONCLUSION AND FUTURE WORK", styles["H1"]))
    add_text(story, styles, conclusion)
    story.append(Paragraph("7.1 Future Work", styles["H2"]))
    for f in [
        "Behavioral UML (sequence and state) with the same multimodal verification stack.",
        "Stronger package repair with hierarchy-aware learning signals.",
        "Broader industrial case studies and human-in-the-loop rejection feedback.",
        "Full per-criterion VLM numeric heads (four scores) aligned to the human 0–6 protocol.",
        "Larger public release of verified triples on Hugging Face with documented licenses.",
    ]:
        story.append(Paragraph(esc("• " + f), styles["ThesisBullet"]))
    story.append(PageBreak())

    # ================= REFERENCES =================
    story.append(Paragraph("REFERENCES", styles["H1"]))
    refs = [
        "Ambler, S. W. (2004). The Object Primer (3rd ed.). Cambridge University Press.",
        "Booch, G., Rumbaugh, J., & Jacobson, I. (2005). The Unified Modeling Language User Guide (2nd ed.). Addison-Wesley.",
        "Brown, T., et al. (2020). Language models are few-shot learners. NeurIPS.",
        "DeepSeek-AI (2025). DeepSeek-R1 technical report.",
        "Faul, F., Erdfelder, E., Lang, A.-G., & Buchner, A. (2007). G*Power 3. Behavior Research Methods.",
        "Fowler, M. (2003). UML Distilled (3rd ed.). Addison-Wesley.",
        "McHugh, M. L. (2012). Interrater reliability: the kappa statistic. Biochemia Medica.",
        "PlantUML. https://plantuml.com/",
        "Qwen Team. Qwen2.5-VL technical report.",
        "Rumbaugh, J., Jacobson, I., & Booch, G. (2004). The Unified Modeling Language Reference Manual (2nd ed.).",
        "Vaswani, A., et al. (2017). Attention is all you need. NeurIPS.",
        "Viera, A. J., & Garrett, J. M. (2005). Understanding interobserver agreement: the kappa statistic. Family Medicine.",
        "Wei, J., et al. (2022). Chain-of-thought prompting elicits reasoning in large language models. NeurIPS.",
        "Yue, X., et al. (2024). MMMU: A massive multi-discipline multimodal understanding benchmark. CVPR.",
        "Meta AI. Llama 3 model family documentation.",
        "Ustun, A., et al. (2024). Aya model family / Aya-Vision.",
        "Additional baselines and UML-generation papers are detailed in paper/literature_review.tex "
        "and paper/references.bib; expand this list into CSULB bibliography format before final submission.",
    ]
    for i, r in enumerate(refs, 1):
        story.append(Paragraph(esc(f"[{i}] {r}"), styles["BodyNI"]))
    story.append(PageBreak())

    # ================= APPENDICES =================
    story.append(Paragraph("APPENDIX A", styles["Chap"]))
    story.append(Paragraph("PROMPT TEMPLATES AND CONFIGURATION", styles["H1"]))
    add_text(
        story,
        styles,
        "Versioned prompts live under prompts/: requirement_to_tech_spec.v1.txt, "
        "code_to_tech_spec.v1.txt, tech_spec_to_{class,object,component,package,flowchart}.v1.txt, "
        "vlm_scoring.v1.txt, repair_plantuml.v1.txt, and human_evaluation_rubric.v1.txt. "
        "Stage-1 requests JSON-only specifications. Stage-2 requires exact entity names and "
        "forbids ModuleN placeholders. VLM scoring lists the four paper criteria and requests "
        "SCORE/EXPLANATION format. Environment templates are documented in .env.example, "
        "including ACCEPTANCE_TAU and MIN_COMPOSITE_FOR_DATASET.",
        "BodyNI",
    )
    story.append(PageBreak())

    story.append(Paragraph("APPENDIX B", styles["Chap"]))
    story.append(Paragraph("REPOSITORY AND REPRODUCIBILITY", styles["H1"]))
    add_text(
        story,
        styles,
        "Clone https://github.com/dipak5501/uml-generation-pipeline. Create a virtual "
        "environment, copy .env.example to .env, then run make install and ./scripts/run_local.sh. "
        "UI: http://127.0.0.1:8501. API: http://127.0.0.1:8000. Health: /api/settings/health. "
        "Production Mac Studio uses MOCK_PROVIDERS=false, USE_OLLAMA=true, "
        "USE_FINETUNED_CODE=true, FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-sourcecode-30k, "
        "and VLM_AYA_BACKEND=local. Remote operator: POST /api/agent/command with Bearer token. "
        "Unit tests: make test with MOCK_PROVIDERS=true. Dual Ollama: scripts/ensure_ollama_dual.sh. "
        "NVIDIA: make finetune-cuda (do not run on the Mac Studio). The gated class-scored "
        "Hugging Face dataset is optional and not required.",
        "BodyNI",
    )
    story.append(PageBreak())

    story.append(Paragraph("APPENDIX C", styles["Chap"]))
    story.append(Paragraph("FIDELITY AND FAILURE ANALYSIS NOTES", styles["H1"]))
    add_text(
        story,
        styles,
        "Professional testing revealed that generation-only metrics (render success, high "
        "VLM scores) can mask semantic mismatches: missing required entities (e.g., Librarian), "
        "ModuleN placeholders, and treating py2puml script variables as classes. The fidelity "
        "gate and script-without-types recovery were added so UML developers and external "
        "testers see diagrams that match named entities in the input. Package failures are "
        "further categorized (nesting, containment/dependency confusion, empty bodies) via "
        "package_failures analytics. Local report artifacts may be stored under data/eval/ "
        "(gitignored).",
        "BodyNI",
    )
    story.append(PageBreak())

    story.append(Paragraph("APPENDIX D", styles["Chap"]))
    story.append(Paragraph("GLOSSARY", styles["H1"]))
    glossary = [
        ("PlantUML", "Textual language and compiler for UML diagrams."),
        ("MMMU", "Massive Multi-discipline Multimodal Understanding benchmark used for VLM weights."),
        ("Composite score S", "MMMU-weighted average of VLM scores; 0 if render fails."),
        ("τ (tau)", "Per-VLM acceptance threshold; paper default 4 on a 0–6 scale."),
        ("Majority vote A", "Accept if at least two of three VLMs vote s ≥ τ."),
        ("Fidelity gate", "Coverage check ensuring PlantUML reflects Stage-1 entities/relations."),
        ("LoRA", "Low-Rank Adaptation; used for local PlantUML fine-tuned generation."),
        ("CECS 697 / 698", "CSULB Independent Study sequence culminating in thesis."),
    ]
    for term, defn in glossary:
        story.append(Paragraph(esc(f"{term}: {defn}"), styles["BodyNI"]))

    story.append(Spacer(1, 0.35 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(
        Paragraph(
            "End of draft. Before Thesis Office submission: paste into the official CSULB "
            "thesis template (Format Manual), expand bibliography from paper/references.bib, "
            "replace DRAFT markings, obtain committee signatures, and confirm length/structure "
            "with Dr. Yutong Zhao. Practical target discussed with the author: approximately "
            "60–90 pages in official double-spaced format after expansion of figures and "
            "full reference list.",
            styles["Foot"],
        )
    )

    def _page(canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            canvas.setFont("Times-Roman", 10)
            canvas.drawCentredString(letter[0] / 2, 0.65 * inch, str(doc.page))
        canvas.restoreState()

    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    REPORTS.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(LOCAL),
        pagesize=letter,
        leftMargin=1.25 * inch,
        rightMargin=1.25 * inch,
        topMargin=1.0 * inch,
        bottomMargin=1.0 * inch,
        title="Dipak Yadav M.S. Thesis Draft",
        author="Dipak Yadav",
    )
    doc.build(story, onFirstPage=_page, onLaterPages=_page)
    shutil.copy2(LOCAL, REPORTS)
    for dest in (DESKTOP, ARTIFACTS):
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(LOCAL, dest)
            print(f"Copied {dest}")
        except OSError as exc:
            print(f"Skip copy {dest}: {exc}")

    readme = LOCAL.parent / "README.md"
    readme.write_text(
        """# M.S. Thesis Draft (local)

- `Dipak_Yadav_MS_Thesis_Draft.pdf` — advisor-review draft
- Tracked copy: `reports/Dipak_Yadav_MS_Thesis_Draft.pdf`
- Desktop copy: `~/Desktop/Dipak_Yadav_MS_Thesis_Draft.pdf` (when present)

**Not** the official CSULB Thesis Office submission format.

Regenerate:

```bash
python scripts/generate_thesis_draft.py
```

Next steps with Dr. Zhao: move content into the official template, expand refs from
`paper/references.bib`, add signed approval pages, and confirm target length.
""",
        encoding="utf-8",
    )
    print(f"Wrote {LOCAL} ({doc.page} pages)")
    print(f"Wrote {REPORTS}")


if __name__ == "__main__":
    main()
