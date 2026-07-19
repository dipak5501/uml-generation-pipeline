#!/usr/bin/env python3
"""Generate the UML-Pipeline system alignment PDF."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
  ListFlowable,
  ListItem,
  PageBreak,
  Paragraph,
  SimpleDocTemplate,
  Spacer,
  Table,
  TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "Thesis_System_Alignment_Report.pdf"

INK = colors.HexColor("#14212b")
ACCENT = colors.HexColor("#0f766e")
LIGHT = colors.HexColor("#f3efe6")
LINE = colors.HexColor("#d5cfc2")


def styles():
  base = getSampleStyleSheet()
  return {
    "title": ParagraphStyle(
      "T",
      parent=base["Title"],
      fontName="Helvetica-Bold",
      fontSize=18,
      leading=22,
      textColor=INK,
      alignment=TA_CENTER,
      spaceAfter=8,
    ),
    "subtitle": ParagraphStyle(
      "S",
      parent=base["Normal"],
      fontName="Helvetica",
      fontSize=11,
      leading=14,
      textColor=ACCENT,
      alignment=TA_CENTER,
      spaceAfter=6,
    ),
    "meta": ParagraphStyle(
      "M",
      parent=base["Normal"],
      fontSize=9.5,
      leading=12,
      textColor=colors.HexColor("#3a4a57"),
      alignment=TA_CENTER,
      spaceAfter=14,
    ),
    "h1": ParagraphStyle(
      "H1",
      parent=base["Heading1"],
      fontName="Helvetica-Bold",
      fontSize=13,
      leading=16,
      textColor=ACCENT,
      spaceBefore=14,
      spaceAfter=6,
    ),
    "h2": ParagraphStyle(
      "H2",
      parent=base["Heading2"],
      fontName="Helvetica-Bold",
      fontSize=11,
      leading=14,
      textColor=INK,
      spaceBefore=10,
      spaceAfter=4,
    ),
    "body": ParagraphStyle(
      "B",
      parent=base["Normal"],
      fontName="Helvetica",
      fontSize=9.8,
      leading=13,
      textColor=INK,
      alignment=TA_JUSTIFY,
      spaceAfter=6,
    ),
    "bullet": ParagraphStyle(
      "Bu",
      parent=base["Normal"],
      fontName="Helvetica",
      fontSize=9.5,
      leading=12.5,
      textColor=INK,
    ),
    "small": ParagraphStyle(
      "Sm",
      parent=base["Normal"],
      fontName="Helvetica",
      fontSize=8.5,
      leading=11,
      textColor=colors.HexColor("#3a4a57"),
    ),
    "footer": ParagraphStyle(
      "F",
      parent=base["Normal"],
      fontName="Helvetica",
      fontSize=8,
      textColor=colors.HexColor("#5a6a75"),
      alignment=TA_CENTER,
    ),
  }


def bullets(items, style):
  return ListFlowable(
    [ListItem(Paragraph(i, style), leftIndent=8, bulletColor=ACCENT) for i in items],
    bulletType="bullet",
    start="•",
    leftIndent=12,
  )


def table(data, col_widths):
  t = Table(data, colWidths=col_widths, hAlign="LEFT")
  t.setStyle(
    TableStyle(
      [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 1), (-1, -1), LIGHT),
        ("TEXTCOLOR", (0, 1), (-1, -1), INK),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
      ]
    )
  )
  return t


def add_footer(canvas, doc):
  canvas.saveState()
  canvas.setStrokeColor(LINE)
  canvas.line(0.75 * inch, 0.6 * inch, letter[0] - 0.75 * inch, 0.6 * inch)
  canvas.setFont("Helvetica", 8)
  canvas.setFillColor(colors.HexColor("#5a6a75"))
  canvas.drawString(
    0.75 * inch,
    0.4 * inch,
    "UML-Pipeline — System Alignment Report",
  )
  canvas.drawRightString(letter[0] - 0.75 * inch, 0.4 * inch, f"Page {doc.page}")
  canvas.restoreState()


def build():
  s = styles()
  doc = SimpleDocTemplate(
    str(OUT),
    pagesize=letter,
    leftMargin=0.75 * inch,
    rightMargin=0.75 * inch,
    topMargin=0.7 * inch,
    bottomMargin=0.85 * inch,
    title="UML-Pipeline System Alignment Report",
    author="Dipak Yadav",
  )
  story = []

  story.append(Paragraph(
    "UML-Pipeline — System Alignment Report",
    s["title"],
  ))
  story.append(Paragraph(
    "Automated UML Dataset Generation from Natural-Language Requirements<br/>"
    "with Multimodal Verification for Software Design",
    s["subtitle"],
  ))
  story.append(Paragraph(
    "Student: <b>Dipak Yadav</b> &nbsp;|&nbsp; Advisor: <b>Yutong Zhao, Ph.D.</b><br/>"
    "Department of Computer Engineering &amp; Computer Science<br/>"
    "California State University, Long Beach<br/>"
    "Software artifact: <b>github.com/dipak5501/uml-generation-pipeline</b><br/>"
    "Document purpose: Map the implemented program to the paper methodology",
    s["meta"],
  ))

  story.append(Paragraph("1. Purpose of This Document", s["h1"]))
  story.append(Paragraph(
    "This report maps the paper method to the implemented system. It explains how the software system "
    "implements the end-to-end methodology described in the thesis paper: generating "
    "design-phase UML artifacts from natural-language requirements (and, as an application "
    "extension, from source code), rendering them with PlantUML, and verifying quality "
    "using a multimodal vision–language model (VLM) ensemble with MMMU-weighted scoring, "
    "plus human-evaluation support.",
    s["body"],
  ))

  story.append(Paragraph("2. Thesis Contributions Mapped to Software", s["h1"]))
  story.append(Paragraph(
    "The thesis proposes a three-stage AI pipeline. The application realizes each stage "
    "as executable services with persistence, API, and UI.",
    s["body"],
  ))
  story.append(
    table(
      [
        [
          Paragraph("<b>Thesis element</b>", s["small"]),
          Paragraph("<b>Paper claim</b>", s["small"]),
          Paragraph("<b>Implemented in software</b>", s["small"]),
        ],
        [
          Paragraph("Stage 1 — Spec generation", s["small"]),
          Paragraph(
            "Lightweight LLM converts free-form requirements into structured "
            "technical specifications for design-phase modeling.",
            s["small"],
          ),
          Paragraph(
            "<b>TechnicalSpecification Generator</b>: "
            "requirement → structured spec (architect prompts). "
            "Also supports <b>source-code → spec</b> recovery.",
            s["small"],
          ),
        ],
        [
          Paragraph("Stage 2 — PlantUML synthesis", s["small"]),
          Paragraph(
            "Reasoning-oriented LLM synthesizes syntactically valid PlantUML "
            "for class, object, component, and package diagrams.",
            s["small"],
          ),
          Paragraph(
            "<b>PlantUML Generator</b> with diagram-specific versioned prompts "
            "under <font face='Courier'>prompts/</font>. "
            "Also supports <b>flowchart</b> (activity) diagrams in the application.",
            s["small"],
          ),
        ],
        [
          Paragraph("Stage 3 — Render + multimodal verification", s["small"]),
          Paragraph(
            "PlantUML is rendered; diagram images are scored by three VLMs; "
            "scores are combined with MMMU weights; invalid renders score 0.",
            s["small"],
          ),
          Paragraph(
            "<b>Renderer</b> (local JAR or remote PlantUML fallback) + "
            "<b>Validation Service</b> with Qwen / LLaMA-Vision / Aya-Vision "
            "weights <b>53.1 / 50.7 / 39.9</b> and paper composite formula.",
            s["small"],
          ),
        ],
        [
          Paragraph("Human evaluation", s["small"]),
          Paragraph(
            "Expert rubric ratings and correlation with automated scores.",
            s["small"],
          ),
          Paragraph(
            "<b>Human Evaluation</b> UI/API: semantic correctness, structural "
            "completeness, syntactic accuracy, overall coherence + comments; "
            "analytics correlation when reviews exist.",
            s["small"],
          ),
        ],
        [
          Paragraph("Dataset / scale", s["small"]),
          Paragraph(
            "Large verified design-phase UML dataset generation and analysis.",
            s["small"],
          ),
          Paragraph(
            "Batch jobs, SQLite artifact store, export CSV/JSONL/Parquet, "
            "analytics distributions, batch dataset scripts (≥200 artifacts).",
            s["small"],
          ),
        ],
      ],
      [1.4 * inch, 2.5 * inch, 3.1 * inch],
    )
  )

  story.append(Paragraph("3. End-to-End Runtime Pipeline (How It Works)", s["h1"]))
  story.append(Paragraph(
    "When a user submits either a natural-language requirement or source code, "
    "the system executes the following thesis-aligned flow:",
    s["body"],
  ))
  story.append(
    bullets(
      [
        "<b>Intake</b> — Validate input; select diagram type "
        "(class / object / component / package / flowchart).",
        "<b>Specification</b> — Produce a structured technical specification "
        "(entities, relationships, modules/process steps).",
        "<b>PlantUML generation</b> — Convert the specification into diagram-specific PlantUML.",
        "<b>Static validation + repair</b> — Syntax/semantic guards (especially package diagrams); "
        "targeted repair retries when needed.",
        "<b>Render gate</b> — Render PNG/SVG. If rendering fails, composite score is forced to <b>0</b> "
        "(paper rule).",
        "<b>Multimodal scoring</b> — Three VLMs each assign 0–6. Composite is the "
        "MMMU-weighted average of all three scores (zeros included), matching thesis Eq. (weighted).",
        "<b>Persist + review</b> — Store full artifact trace; optional human rubric; analytics/export.",
      ],
      s["bullet"],
    )
  )

  story.append(Paragraph("4. Scoring Formula (Paper-Faithful)", s["h1"]))
  story.append(Paragraph(
    "Let score<sub>i</sub> ∈ {0,…,6} be the score from model i with weight w<sub>i</sub>, "
    "and let δ=1 when the diagram passes the render gate (else δ=0). Then:",
    s["body"],
  ))
  story.append(Paragraph(
    "<font face='Courier' size='9'>"
    "S = δ · Σ (score_i × w_i) / Σ w_i<br/>"
    "A = 1 if at least two models score ≥ τ (τ=4); dataset entry if A=1 and S≥3."
    "</font>",
    s["body"],
  ))
  story.append(Paragraph(
    "Weights implemented exactly as in the thesis configuration: "
    "Qwen2.5-VL-3B = <b>53.1</b>, LLaMA-3.2-11B-Vision = <b>50.7</b>, Aya-Vision-8B = <b>39.9</b>.",
    s["body"],
  ))

  story.append(Paragraph("5. Application Features Beyond Scripts", s["h1"]))
  story.append(Paragraph(
    "To make the methodology runnable as software, the research pipeline was "
    "wrapped into a full application:",
    s["body"],
  ))
  story.append(
    bullets(
      [
        "<b>FastAPI backend</b> — generation, jobs, artifacts, rescore/repair, human review, analytics, export.",
        "<b>Streamlit UI</b> — dashboard, free-text/code generation, batch dataset runs, artifact review, "
        "human evaluation, analytics, settings/health.",
        "<b>SQLite persistence</b> — full requirement → spec → PlantUML → image → model scores → composite.",
        "<b>Provider abstraction</b> — OpenAI-compatible, Ollama, and mock mode for offline runs.",
        "<b>Docker / deploy docs</b> — local and cloud launch instructions.",
      ],
      s["bullet"],
    )
  )

  story.append(PageBreak())
  story.append(Paragraph("6. Evidence Checklist for Faculty Demo", s["h1"]))
  story.append(Paragraph(
    "The following checklist shows what can be observed in a live run "
    "to confirm paper–system alignment.",
    s["body"],
  ))
  story.append(
    table(
      [
        [
          Paragraph("<b>#</b>", s["small"]),
          Paragraph("<b>Thesis behavior</b>", s["small"]),
          Paragraph("<b>Where to see it in the program</b>", s["small"]),
        ],
        [
          Paragraph("1", s["small"]),
          Paragraph("Requirement → technical specification", s["small"]),
          Paragraph("Generate page → Technical specification panel", s["small"]),
        ],
        [
          Paragraph("2", s["small"]),
          Paragraph("Spec → PlantUML for design diagrams", s["small"]),
          Paragraph("Generate page → PlantUML code + download", s["small"]),
        ],
        [
          Paragraph("3", s["small"]),
          Paragraph("Render gate / failure ⇒ score 0", s["small"]),
          Paragraph("Paper validation pipeline strip + composite metric", s["small"]),
        ],
        [
          Paragraph("4", s["small"]),
          Paragraph("Three VLM scores + weighted composite", s["small"]),
          Paragraph("Per-model VLM scores table + final weighted score", s["small"]),
        ],
        [
          Paragraph("5", s["small"]),
          Paragraph("Package difficulty / repair awareness", s["small"]),
          Paragraph("Package diagram type + repair attempts history", s["small"]),
        ],
        [
          Paragraph("6", s["small"]),
          Paragraph("Human expert-style evaluation", s["small"]),
          Paragraph("Human Evaluation page (4 rubric dimensions)", s["small"]),
        ],
        [
          Paragraph("7", s["small"]),
          Paragraph("Dataset-style batch generation & analytics", s["small"]),
          Paragraph("Batch Generation + Analytics + export endpoints", s["small"]),
        ],
        [
          Paragraph("8", s["small"]),
          Paragraph("Traceable artifacts for audit", s["small"]),
          Paragraph("Artifact Review: full stored trace per sample", s["small"]),
        ],
      ],
      [0.4 * inch, 2.8 * inch, 3.8 * inch],
    )
  )

  story.append(Paragraph("7. How to Run the Demonstration", s["h1"]))
  story.append(Paragraph("<b>Local run (recommended)</b>", s["h2"]))
  story.append(Paragraph(
    "<font face='Courier' size='8'>"
    "cd uml-generation-pipeline<br/>"
    "make install<br/>"
    "make api &nbsp;&nbsp;# http://127.0.0.1:8000/docs<br/>"
    "make ui &nbsp;&nbsp;&nbsp;# http://127.0.0.1:8501"
    "</font>",
    s["body"],
  ))
  story.append(Paragraph(
    "Default <font face='Courier'>MOCK_PROVIDERS=true</font> allows a complete offline run without "
    "paid APIs. Rendering uses PlantUML (local Java if available, otherwise remote fallback). "
    "For live models, set <font face='Courier'>MOCK_PROVIDERS=false</font> and configure Ollama "
    "or an OpenAI-compatible endpoint.",
    s["body"],
  ))
  story.append(Paragraph("<b>Suggested 5-minute usage path</b>", s["h2"]))
  story.append(
    bullets(
      [
        "Open the UI home/dashboard and show artifact counts and mean scores.",
        "Generate from a plain-English requirement (class diagram) and show the full trace.",
        "Switch to source-code mode, paste sample code, generate a class diagram.",
        "Point to the validation strip: syntax → render gate → VLM scores → composite.",
        "Open Human Evaluation and submit a rubric score; show Analytics page.",
      ],
      s["bullet"],
    )
  )

  story.append(Paragraph("8. Repository Layout (Implementation Surface)", s["h1"]))
  story.append(Paragraph(
    "<font face='Courier' size='8'>"
    "app/&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; FastAPI services, providers, scoring, repair, orchestration<br/>"
    "ui/&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Streamlit application UI<br/>"
    "uml_pipeline/&nbsp; Core research pipeline (render, scoring helpers)<br/>"
    "prompts/&nbsp;&nbsp;&nbsp;&nbsp; Versioned prompt templates aligned to thesis stages<br/>"
    "paper/&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; LaTeX thesis paper sources<br/>"
    "tests/&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Scoring, validators, code analysis, API smoke tests<br/>"
    "docs/&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Plans, assumptions, deploy guide, this report"
    "</font>",
    s["body"],
  ))

  story.append(Paragraph("9. Implementation Notes (Scope Boundaries)", s["h1"]))
  story.append(
    bullets(
      [
        "The software implements the <b>methodology</b> of the thesis (pipeline stages, diagram types, "
        "render gate, weighted VLM ensemble, human rubric, analytics).",
        "A full 8,000-sample paper-scale experiment still depends on provisioned LLM/VLM compute; "
        "the app supports that mode and also an offline mock mode for reliable local execution.",
        "Flowchart diagrams and source-code intake are <b>application extensions</b> that reuse the "
        "same specification → PlantUML → multimodal validation pipeline.",
        "Private model reasoning is not exposed in UI/logs; only final specs, PlantUML, validation, "
        "and scores are persisted.",
      ],
      s["bullet"],
    )
  )

  story.append(Paragraph("10. Conclusion", s["h1"]))
  story.append(Paragraph(
    "The implemented system is not merely a collection of scripts: it is a runnable "
    "implementation of <i>Automated UML Dataset Generation from Natural-Language Requirements "
    "with Multimodal Verification for Software Design</i>. It operationalizes dual-stage "
    "generation, PlantUML rendering as a hard quality gate, MMMU-weighted multimodal "
    "verification, human evaluation, and dataset analytics—matching the paper’s methodological "
    "core while providing an interface for inspection and evaluation.",
    s["body"],
  ))
  story.append(Spacer(1, 12))
  story.append(Paragraph(
    "Contact: Dipak.yadav5501@gmail.com &nbsp;·&nbsp; "
    "Repository: https://github.com/dipak5501/uml-generation-pipeline",
    s["meta"],
  ))

  OUT.parent.mkdir(parents=True, exist_ok=True)
  doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
  print(f"Wrote {OUT}")


if __name__ == "__main__":
  build()
