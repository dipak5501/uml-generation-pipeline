#!/usr/bin/env python3
"""Assemble thesis/chapters/*.md into a draft PDF on Desktop + thesis/."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[1]
CH = ROOT / "thesis" / "chapters"
OUT_LOCAL = ROOT / "thesis" / "Dipak_Yadav_MS_Thesis_Draft.pdf"
OUT_DESKTOP = Path.home() / "Desktop" / "Dipak_Yadav_MS_Thesis_Draft.pdf"

FILES = [
    "00_abstract.md",
    "01_introduction.md",
    "02_related_work.md",
    "03_methodology.md",
    "04_implementation.md",
    "05_experimental_design.md",
    "06_results.md",
    "07_discussion.md",
    "08_conclusion.md",
    "09_references.md",
    "10_appendices.md",
]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_md(text: str) -> list[tuple[str, str]]:
    paras: list[tuple[str, str]] = []
    buf: list[str] = []
    in_code = False
    code_buf: list[str] = []
    table_buf: list[str] = []

    def flush_buf() -> None:
        if buf:
            paras.append(("p", " ".join(buf)))
            buf.clear()

    def flush_table() -> None:
        if table_buf:
            paras.append(("code", "\n".join(table_buf)))
            table_buf.clear()

    for line in text.splitlines():
        if line.startswith("```"):
            flush_buf()
            flush_table()
            if in_code:
                paras.append(("code", "\n".join(code_buf)))
                code_buf.clear()
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue
        if line.startswith("# "):
            flush_buf()
            flush_table()
            paras.append(("h1", line[2:].strip()))
        elif line.startswith("## "):
            flush_buf()
            flush_table()
            paras.append(("h2", line[3:].strip()))
        elif line.startswith("### "):
            flush_buf()
            flush_table()
            paras.append(("h3", line[4:].strip()))
        elif line.startswith("|") and "|" in line[1:]:
            flush_buf()
            table_buf.append(line)
        elif line.startswith(">"):
            flush_buf()
            flush_table()
            paras.append(("quote", line.lstrip("> ").strip()))
        elif line.startswith("- ") or line.startswith("* ") or re.match(r"^\d+\.\s", line):
            flush_buf()
            flush_table()
            paras.append(("bullet", re.sub(r"^(\d+\.|[-*])\s+", "", line)))
        elif line.strip() == "":
            flush_buf()
            flush_table()
        else:
            flush_table()
            buf.append(line.strip())
    flush_buf()
    flush_table()
    if in_code and code_buf:
        paras.append(("code", "\n".join(code_buf)))
    return paras


def main() -> None:
    styles = getSampleStyleSheet()
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
            name="HChap",
            fontName="Times-Bold",
            fontSize=12,
            leading=20,
            alignment=TA_CENTER,
            spaceBefore=10,
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2t",
            fontName="Times-Bold",
            fontSize=12,
            leading=20,
            spaceBefore=12,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H3t",
            fontName="Times-Bold",
            fontSize=12,
            leading=18,
            spaceBefore=8,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Bodyt",
            fontName="Times-Roman",
            fontSize=12,
            leading=24,
            alignment=TA_JUSTIFY,
            firstLineIndent=18,
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
            name="TBullet",
            fontName="Times-Roman",
            fontSize=12,
            leading=24,
            leftIndent=18,
            spaceAfter=4,
        )
    )
    styles.add(ParagraphStyle(name="ThesisCode", fontName="Courier", fontSize=9, leading=12, spaceAfter=8))

    story: list = []
    story.append(Spacer(1, 0.8 * inch))
    story.append(
        Paragraph(
            "AUTOMATED UML DATASET GENERATION FROM NATURAL-LANGUAGE "
            "REQUIREMENTS WITH MULTIMODAL VERIFICATION FOR SOFTWARE DESIGN",
            styles["CoverTitle"],
        )
    )
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("A Thesis", styles["CoverSub"]))
    story.append(
        Paragraph(
            "Presented to the Department of Computer Engineering and Computer Science<br/>"
            "College of Engineering<br/>California State University, Long Beach",
            styles["CoverSub"],
        )
    )
    story.append(Spacer(1, 0.25 * inch))
    story.append(
        Paragraph(
            "In Partial Fulfillment of the Requirements for the Degree<br/>"
            "Master of Science in Computer Science",
            styles["CoverSub"],
        )
    )
    story.append(Spacer(1, 0.35 * inch))
    story.append(Paragraph("by", styles["CoverSub"]))
    story.append(Paragraph("<b>Dipak Yadav</b>", styles["CoverSub"]))
    story.append(Paragraph("Campus ID: 033783670", styles["CoverSub"]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(
        Paragraph(
            "Committee: Dr. Yutong Zhao (Chair); Dr. Muhammad Abdul Basit; Dr. Xin Qin",
            styles["CoverSub"],
        )
    )
    story.append(Paragraph("December 2026", styles["CoverSub"]))
    story.append(
        Paragraph(
            "<i>DRAFT — written chapters in thesis/chapters/; verify citations "
            "against paper/references.bib before Thesis Office submission</i>",
            styles["CoverSub"],
        )
    )
    story.append(PageBreak())

    story.append(Paragraph("TABLE OF CONTENTS", styles["HChap"]))
    for f in FILES:
        label = f.split("_", 1)[1].replace(".md", "").replace("_", " ").title()
        story.append(Paragraph(esc(label), styles["BodyNI"]))
    story.append(PageBreak())

    for fname in FILES:
        text = (CH / fname).read_text(encoding="utf-8")
        for kind, val in parse_md(text):
            val = val.replace("**", "")
            if kind == "h1":
                story.append(Paragraph(esc(val), styles["HChap"]))
            elif kind == "h2":
                story.append(Paragraph(esc(val), styles["H2t"]))
            elif kind == "h3":
                story.append(Paragraph(esc(val), styles["H3t"]))
            elif kind == "bullet":
                story.append(Paragraph("• " + esc(val), styles["TBullet"]))
            elif kind == "quote":
                story.append(Paragraph("<i>" + esc(val) + "</i>", styles["BodyNI"]))
            elif kind == "code":
                story.append(Preformatted(val, styles["ThesisCode"]))
            else:
                story.append(Paragraph(esc(val), styles["Bodyt"]))
        story.append(PageBreak())

    def page(canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            canvas.setFont("Times-Roman", 10)
            canvas.drawCentredString(letter[0] / 2, 0.65 * inch, str(doc.page))
        canvas.restoreState()

    OUT_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT_LOCAL),
        pagesize=letter,
        leftMargin=1.25 * inch,
        rightMargin=1.25 * inch,
        topMargin=1.0 * inch,
        bottomMargin=1.0 * inch,
        title="Dipak Yadav M.S. Thesis Draft",
        author="Dipak Yadav",
    )
    doc.build(story, onFirstPage=page, onLaterPages=page)
    shutil.copy2(OUT_LOCAL, OUT_DESKTOP)
    print(f"Wrote {OUT_LOCAL} ({doc.page} pages)")
    print(f"Copied {OUT_DESKTOP}")


if __name__ == "__main__":
    main()
