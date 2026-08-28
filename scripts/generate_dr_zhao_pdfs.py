#!/usr/bin/env python3
"""Convert Dr. Zhao markdown reports to PDF via ReportLab (no LaTeX required)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

INK = colors.HexColor("#14212b")
ACCENT = colors.HexColor("#0f766e")
MUTED = colors.HexColor("#3a4a57")
CODE_BG = colors.HexColor("#f4f4f0")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=16, leading=20, textColor=INK, alignment=TA_CENTER, spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=13, leading=16, textColor=ACCENT, spaceBefore=14, spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=11, leading=14, textColor=INK, spaceBefore=10, spaceAfter=4,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontName="Helvetica-Bold",
            fontSize=10, leading=13, textColor=INK, spaceBefore=8, spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.5, leading=12.5, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=5,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.2, leading=12, textColor=INK, leftIndent=14, bulletIndent=6,
        ),
        "code": ParagraphStyle(
            "code", parent=base["Code"], fontName="Courier",
            fontSize=7.5, leading=9.5, textColor=INK,
        ),
        "cell": ParagraphStyle(
            "cell", parent=base["Normal"], fontName="Helvetica",
            fontSize=7.5, leading=9.5, textColor=INK,
        ),
        "cellh": ParagraphStyle(
            "cellh", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=7.5, leading=9.5, textColor=colors.white,
        ),
        "meta": ParagraphStyle(
            "meta", parent=base["Normal"], fontSize=9, leading=12,
            textColor=MUTED, alignment=TA_CENTER, spaceAfter=10,
        ),
    }


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _inline(text: str) -> str:
    text = _esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r"<font face='Courier' size='8'>\1</font>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<link href="\2" color="blue">\1</link>', text)
    return text


def _parse_table(lines: list[str]) -> list[list[str]]:
    rows = []
    for line in lines:
        if not line.strip().startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.match(r"^[-:\s]+$", c) for c in cells):
            continue
        rows.append(cells)
    return rows


def md_to_story(md_path: Path, st: dict) -> list:
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    story: list = []
    i = 0
    first_h1 = True

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            story.append(Spacer(1, 6))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
            story.append(Spacer(1, 6))
            i += 1
            continue

        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            i += 1
            block: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            content = "\n".join(block)
            if len(content) > 3000:
                content = content[:3000] + "\n... [truncated]"
            story.append(Preformatted(content, st["code"]))
            story.append(Spacer(1, 6))
            continue

        if stripped.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            rows = _parse_table(table_lines)
            if rows:
                data = [[Paragraph(_inline(c), st["cellh" if ri == 0 else "cell"]) for c in row]
                        for ri, row in enumerate(rows)]
                col_n = max(len(r) for r in rows)
                avail = 6.5 * inch
                cw = avail / col_n
                tbl = Table(data, colWidths=[cw] * col_n, repeatRows=1)
                tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 8))
            continue

        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if first_h1:
                story.append(Paragraph(_inline(title), st["title"]))
                first_h1 = False
            else:
                story.append(PageBreak())
                story.append(Paragraph(_inline(title), st["h1"]))
            i += 1
            continue

        if stripped.startswith("## "):
            story.append(Paragraph(_inline(stripped[3:]), st["h1"]))
            i += 1
            continue

        if stripped.startswith("### "):
            story.append(Paragraph(_inline(stripped[4:]), st["h2"]))
            i += 1
            continue

        if stripped.startswith("#### "):
            story.append(Paragraph(_inline(stripped[5:]), st["h3"]))
            i += 1
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            story.append(Paragraph(f"• {_inline(stripped[2:])}", st["bullet"]))
            i += 1
            continue

        if re.match(r"^\d+\.\s", stripped):
            story.append(Paragraph(_inline(stripped), st["bullet"]))
            i += 1
            continue

        if stripped.startswith(">"):
            story.append(Paragraph(f"<i>{_inline(stripped.lstrip('> '))}</i>", st["body"]))
            i += 1
            continue

        para_lines = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt or nxt.startswith("#") or nxt.startswith("|") or nxt.startswith("```") or nxt.startswith("- ") or nxt == "---":
                break
            para_lines.append(nxt)
            i += 1
        story.append(Paragraph(_inline(" ".join(para_lines)), st["body"]))

    return story


def build_pdf(md_path: Path, pdf_path: Path) -> None:
    st = _styles()
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=md_path.stem.replace("_", " "),
        author="Dipak Yadav",
    )
    story = md_to_story(md_path, st)

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(0.75 * inch, 0.5 * inch, md_path.name)
        canvas.drawRightString(7.75 * inch, 0.5 * inch, f"Page {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"  wrote {pdf_path} ({pdf_path.stat().st_size // 1024} KB)")


def main() -> int:
    files = [
        "DR_ZHAO_PROGRESS_SUMMARY.md",
        "DR_ZHAO_THESIS_PROGRESS_REPORT.md",
        "OVERLEAF_PAPER_HANDOFF.md",
        "IMPLEMENTATION_EVIDENCE_MATRIX.md",
    ]
    print("Generating PDFs in docs/ ...")
    for name in files:
        md = DOCS / name
        pdf = DOCS / name.replace(".md", ".pdf")
        if not md.is_file():
            print(f"  SKIP missing {md}")
            continue
        print(f"→ {pdf.name}")
        build_pdf(md, pdf)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
