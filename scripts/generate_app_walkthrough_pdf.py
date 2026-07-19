#!/usr/bin/env python3
"""Generate a detailed application walkthrough PDF."""

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
OUT = ROOT / "docs" / "Application_Walkthrough_Guide.pdf"

INK = colors.HexColor("#14212b")
ACCENT = colors.HexColor("#0f766e")
LIGHT = colors.HexColor("#f3efe6")
LINE = colors.HexColor("#d5cfc2")
MUTED = colors.HexColor("#3a4a57")


def styles():
  base = getSampleStyleSheet()
  return {
    "title": ParagraphStyle(
      "T",
      parent=base["Title"],
      fontName="Helvetica-Bold",
      fontSize=17,
      leading=21,
      textColor=INK,
      alignment=TA_CENTER,
      spaceAfter=6,
    ),
    "subtitle": ParagraphStyle(
      "S",
      parent=base["Normal"],
      fontName="Helvetica",
      fontSize=10.5,
      leading=13,
      textColor=ACCENT,
      alignment=TA_CENTER,
      spaceAfter=4,
    ),
    "meta": ParagraphStyle(
      "M",
      parent=base["Normal"],
      fontSize=9,
      leading=11.5,
      textColor=MUTED,
      alignment=TA_CENTER,
      spaceAfter=12,
    ),
    "h1": ParagraphStyle(
      "H1",
      parent=base["Heading1"],
      fontName="Helvetica-Bold",
      fontSize=12.5,
      leading=15,
      textColor=ACCENT,
      spaceBefore=12,
      spaceAfter=5,
    ),
    "h2": ParagraphStyle(
      "H2",
      parent=base["Heading2"],
      fontName="Helvetica-Bold",
      fontSize=10.5,
      leading=13,
      textColor=INK,
      spaceBefore=8,
      spaceAfter=3,
    ),
    "body": ParagraphStyle(
      "B",
      parent=base["Normal"],
      fontName="Helvetica",
      fontSize=9.4,
      leading=12.4,
      textColor=INK,
      alignment=TA_JUSTIFY,
      spaceAfter=5,
    ),
    "bullet": ParagraphStyle(
      "Bu",
      parent=base["Normal"],
      fontName="Helvetica",
      fontSize=9.1,
      leading=12,
      textColor=INK,
      alignment=TA_LEFT,
    ),
    "small": ParagraphStyle(
      "Sm",
      parent=base["Normal"],
      fontName="Helvetica",
      fontSize=8.2,
      leading=10.5,
      textColor=MUTED,
    ),
    "step": ParagraphStyle(
      "St",
      parent=base["Normal"],
      fontName="Helvetica-Bold",
      fontSize=9.3,
      leading=12,
      textColor=ACCENT,
      spaceBefore=4,
      spaceAfter=1,
    ),
  }


def bullets(items: list[str], s) -> ListFlowable:
  return ListFlowable(
    [ListItem(Paragraph(i, s["bullet"]), leftIndent=8, value="•") for i in items],
    bulletType="bullet",
    start="•",
    leftIndent=12,
    spaceBefore=2,
    spaceAfter=6,
  )


def table(data, col_widths):
  t = Table(data, colWidths=col_widths, hAlign="LEFT")
  t.setStyle(
    TableStyle(
      [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("LEADING", (0, 0), (-1, -1), 10.5),
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


def footer(canvas, doc):
  canvas.saveState()
  canvas.setStrokeColor(LINE)
  canvas.setLineWidth(0.6)
  canvas.line(0.75 * inch, 0.55 * inch, letter[0] - 0.75 * inch, 0.55 * inch)
  canvas.setFont("Helvetica", 8)
  canvas.setFillColor(MUTED)
  canvas.drawString(
    0.75 * inch,
    0.35 * inch,
    "UML-Pipeline — Application Walkthrough (Dipak Yadav)",
  )
  canvas.drawRightString(letter[0] - 0.75 * inch, 0.35 * inch, f"Page {doc.page}")
  canvas.restoreState()


def build():
  s = styles()
  story = []

  story.append(Paragraph("UML-Pipeline", s["title"]))
  story.append(
    Paragraph(
      "Application Walkthrough — UI Pages and Pipeline",
      s["subtitle"],
    )
  )
  story.append(
    Paragraph(
      "Paper: <i>Automated UML Dataset Generation from Natural-Language Requirements "
      "with Multimodal Verification for Software Design</i><br/>"
      "Author: Dipak Yadav &nbsp;|&nbsp; Advisor: Yutong Zhao<br/>"
      "Repository: github.com/dipak5501/uml-generation-pipeline",
      s["meta"],
    )
  )

  # 1. Overview
  story.append(Paragraph("1. What this application is", s["h1"]))
  story.append(
    Paragraph(
      "This is an end-to-end <b>UML generation system</b>. It turns a plain-English "
      "software requirement (or a snippet of source code) into design-phase UML diagrams, "
      "renders them with PlantUML, scores them with three vision-language models (VLMs), "
      "applies the paper’s dual-signal acceptance rules, and stores every artifact for "
      "review, human evaluation, analytics, and export.",
      s["body"],
    )
  )
  story.append(
    Paragraph(
      "The UI is a Streamlit multipage app. The backend is a FastAPI service with SQLite "
      "persistence. By default the system runs in <b>mock provider mode</b> so "
      "no paid API keys are required. Real OpenAI-compatible or Ollama models can be enabled "
      "via environment variables.",
      s["body"],
    )
  )

  story.append(Paragraph("1.1 Architecture at a glance", s["h2"]))
  story.append(
    table(
      [
        [Paragraph("<b>Layer</b>", s["small"]), Paragraph("<b>Technology</b>", s["small"]), Paragraph("<b>Role</b>", s["small"])],
        [Paragraph("UI", s["small"]), Paragraph("Streamlit (:8501)", s["small"]), Paragraph("Dashboard, generate, batch, review, human eval, analytics, settings", s["small"])],
        [Paragraph("API", s["small"]), Paragraph("FastAPI (:8000)", s["small"]), Paragraph("Generation, jobs, artifacts, scoring, export, health", s["small"])],
        [Paragraph("Core pipeline", s["small"]), Paragraph("uml_pipeline + app/services", s["small"]), Paragraph("Spec → CoT PlantUML → validate/repair → render → VLM scores", s["small"])],
        [Paragraph("Storage", s["small"]), Paragraph("SQLite + image files", s["small"]), Paragraph("Full artifact trace (requirement, spec, code, scores, reviews)", s["small"])],
        [Paragraph("Training data", s["small"]), Paragraph("HF open corpora + builder script", s["small"]), Paragraph("Assemble ~8,000 training rows from open sources", s["small"])],
      ],
      [1.1 * inch, 1.9 * inch, 4.2 * inch],
    )
  )
  story.append(Spacer(1, 8))

  story.append(Paragraph("1.2 How to start the application", s["h2"]))
  story.append(bullets([
    "<b>Terminal 1:</b> <font face='Courier'>make api</font> — starts FastAPI on http://127.0.0.1:8000",
    "<b>Terminal 2:</b> <font face='Courier'>make ui</font> — starts Streamlit on http://127.0.0.1:8501",
    "Open the UI in a browser. The sidebar lists every page described below.",
    "API docs (optional): http://127.0.0.1:8000/docs",
  ], s))

  # 2. End-to-end pipeline
  story.append(Paragraph("2. End-to-end pipeline (what happens on every Generate click)", s["h1"]))
  story.append(
    Paragraph(
      "Every generation—whether from the Single Generation page or a Batch job—runs the "
      "same orchestration path. This section describes the pipeline core.",
      s["body"],
    )
  )

  steps = [
    ("Step A — Intake", "User submits a requirement paragraph <i>or</i> source code, plus a diagram type "
     "(class, object, component, package, or flowchart). The API stores a RequirementInput row."),
    ("Step B — Technical specification (Stage 1)", "An LLM with a System Architect persona converts the input into a structured technical specification "
     "(entities, relationships, modules, or process steps for flowchart). Source-code mode reverse-engineers structure first."),
    ("Step C — Chain-of-Thought PlantUML (Stage 2)", "A code model reasons privately inside &lt;think&gt;…&lt;/think&gt; tags, then emits only PlantUML between "
     "@startuml and @enduml. Private reasoning is stripped before UI/display; <b>used_cot</b> is recorded."),
    ("Step D — Static validation &amp; repair", "Syntax/semantic guards run (especially important for package diagrams). On failure, a repair loop "
     "asks the model to fix the PlantUML (bounded by max_repair_attempts)."),
    ("Step E — Render gate", "PlantUML is rendered to PNG/SVG via local JAR (if Java exists) or remote plantuml.com. "
     "<b>If render fails, composite score S is forced to 0</b> — paper rule."),
    ("Step F — Multimodal VLM scoring (Stage 3)", "Three VLMs score the image vs the specification on a 0–6 scale using four criteria: "
     "semantic correctness, structural completeness, syntactic accuracy, overall coherence. "
     "Default MMMU-inspired weights: Qwen 53.1, LLaMA-Vision 50.7, Aya-Vision 39.9."),
    ("Step G — Dual-signal verification", "<b>Composite S</b> = weighted average of the three scores (after render gate). "
     "<b>Majority A</b> = 1 if at least 2 VLMs score ≥ τ=4. "
     "<b>Dataset accepted</b> only if A=1 and S≥3.0."),
    ("Step H — Persist artifact", "SQLite stores the full trace: requirement, spec, PlantUML, image path, per-model scores, "
     "composite, majority/dataset flags, repairs, and timestamps. The UI then displays the result."),
  ]
  for title, body in steps:
    story.append(Paragraph(title, s["step"]))
    story.append(Paragraph(body, s["body"]))

  story.append(PageBreak())

  # 3. Home
  story.append(Paragraph("3. Home page (streamlit_app)", s["h1"]))
  story.append(
    Paragraph(
      "The landing page is the first screen after <font face='Courier'>make ui</font>. "
      "It confirms the API is reachable and summarizes system status.",
      s["body"],
    )
  )
  story.append(Paragraph("What you see", s["h2"]))
  story.append(bullets([
    "Thesis title / branding and short description of the system.",
    "Live stats: total artifacts, dataset-accepted count, majority-accepted count, active provider (MOCK / live).",
    "Connection status to the API base URL.",
    "Three guide cards: Generate → Batch → Review &amp; analytics.",
    "A 3-step how-to: write a requirement, pick a diagram type, inspect quality.",
  ], s))
  story.append(Paragraph("How it works", s["h2"]))
  story.append(
    Paragraph(
      "On load, the page calls <font face='Courier'>GET /api/settings/health</font> and "
      "<font face='Courier'>GET /api/analytics/summary</font>. If the API is down, it shows "
      "an offline panel and stops. Use this page to prove the stack is healthy before use.",
      s["body"],
    )
  )

  # 4. Dashboard
  story.append(Paragraph("4. Dashboard", s["h1"]))
  story.append(
    Paragraph(
      "Purpose: project health overview — counts, score health, and recent work.",
      s["body"],
    )
  )
  story.append(Paragraph("Step-by-step use", s["h2"]))
  story.append(bullets([
    "Open <b>Dashboard</b> in the sidebar.",
    "Read the top metrics: Artifacts, Mean score, Render fails, Human reviews.",
    "Inspect the <b>By diagram type</b> table (count, mean score, failures per type).",
    "Scroll <b>Recent artifacts</b> (latest ~25) to jump mentally into Artifact Review later.",
  ], s))
  story.append(Paragraph("How it works internally", s["h2"]))
  story.append(
    Paragraph(
      "Calls <font face='Courier'>/api/analytics/summary</font> and <font face='Courier'>/api/artifacts</font>. "
      "No generation happens here — it is read-only monitoring.",
      s["body"],
    )
  )

  # 5. Single Generation
  story.append(Paragraph("5. Single Generation (primary generation page)", s["h1"]))
  story.append(
    Paragraph(
      "Purpose: primary interactive generation. One requirement (or code snippet) → one or more diagrams "
      "with full paper validation strip.",
      s["body"],
    )
  )
  story.append(Paragraph("Step-by-step use", s["h2"]))
  story.append(bullets([
    "Choose input type: <b>Requirement / paragraph</b> or <b>Software source code</b>.",
    "Optionally pick a built-in example (bookstore, hospital, food delivery) or paste your own text/code.",
    "Select diagram type: class, object, component, package, or flowchart.",
    "Optionally enable <b>Generate all diagram types</b> for the same input.",
    "Click <b>Generate</b>. Wait for the API to finish the full pipeline.",
    "Read the <b>Paper validation pipeline</b> strip: Spec+CoT → PlantUML syntax → Render gate → Composite S → Majority A.",
    "Confirm whether <b>Dataset entry accepted</b> (needs A=1 and S≥3).",
    "Inspect technical specification, PlantUML code, rendered image, and per-model VLM scores.",
    "Download PlantUML and/or the image if needed.",
  ], s))
  story.append(Paragraph("What the validation strip means", s["h2"]))
  story.append(
    table(
      [
        [Paragraph("<b>Metric</b>", s["small"]), Paragraph("<b>Meaning</b>", s["small"])],
        [Paragraph("1. Spec + CoT", s["small"]), Paragraph("Technical spec produced; Chain-of-Thought used for PlantUML", s["small"])],
        [Paragraph("2. PlantUML syntax", s["small"]), Paragraph("Static validation flags (package guards, bounds, etc.)", s["small"])],
        [Paragraph("3. Render gate", s["small"]), Paragraph("Pass = image exists; Fail forces S = 0", s["small"])],
        [Paragraph("4. Composite S", s["small"]), Paragraph("Weighted VLM ensemble score on 0–6 scale", s["small"])],
        [Paragraph("5. Majority A", s["small"]), Paragraph("Yes if ≥2 VLMs score ≥ τ=4; votes shown as x/3", s["small"])],
        [Paragraph("Dataset accepted", s["small"]), Paragraph("Final paper rule: A=1 and S≥3.0", s["small"])],
      ],
      [1.6 * inch, 5.6 * inch],
    )
  )
  story.append(Spacer(1, 6))
  story.append(Paragraph("How it works internally", s["h2"]))
  story.append(
    Paragraph(
      "UI posts to <font face='Courier'>POST /api/generate</font> (or loops types). "
      "Backend <font face='Courier'>run_single_generation</font> executes Steps A–H from Section 2, "
      "then returns an ArtifactDetail JSON that the page renders.",
      s["body"],
    )
  )

  story.append(PageBreak())

  # 6. Batch
  story.append(Paragraph("6. Batch Generation", s["h1"]))
  story.append(
    Paragraph(
      "Purpose: build a larger evaluation dataset quickly (e.g., 50 requirements × 5 types).",
      s["body"],
    )
  )
  story.append(Paragraph("Step-by-step use", s["h2"]))
  story.append(bullets([
    "Set <b>Number of sample requirements</b> (1–200; default 50).",
    "Multiselect diagram types (class/object/component/package/flowchart).",
    "Optionally paste one custom sentence (system creates n variants) or keep built-in samples.",
    "Click <b>Preview sample sentences</b> to see what will be used.",
    "Note the estimated artifact count = n × number of types.",
    "Click <b>Start batch job</b>. The page polls job status until completed/failed.",
    "Review the resulting artifact table; export later from Analytics.",
  ], s))
  story.append(Paragraph("How it works internally", s["h2"]))
  story.append(
    Paragraph(
      "UI calls <font face='Courier'>POST /api/generate/batch</font>, which creates a GenerationJob and "
      "runs units in a thread pool. Each unit is the same single-generation pipeline. Progress is "
      "read via <font face='Courier'>GET /api/jobs/{id}</font>. Sample sentences come from "
      "<font face='Courier'>sample_data/requirements.txt</font> (cycled if n exceeds file length).",
      s["body"],
    )
  )

  # 7. Artifact Review
  story.append(Paragraph("7. Artifact Review", s["h1"]))
  story.append(
    Paragraph(
      "Purpose: browse and inspect any stored artifact in depth — the “evidence room” for detailed inspection.",
      s["body"],
    )
  )
  story.append(Paragraph("Step-by-step use", s["h2"]))
  story.append(bullets([
    "Filter by diagram type, render status, and minimum composite score.",
    "Scan the filtered table of artifacts.",
    "Select an artifact ID from the dropdown.",
    "Read the source requirement; expand Technical specification and PlantUML.",
    "Check composite score and render status; view the image if render succeeded.",
    "Review per-model VLM scores, repair attempts (if any), and prior human reviews.",
  ], s))
  story.append(Paragraph("How it works internally", s["h2"]))
  story.append(
    Paragraph(
      "Uses <font face='Courier'>GET /api/artifacts</font> with query filters and "
      "<font face='Courier'>GET /api/artifacts/{id}</font> for detail, plus "
      "<font face='Courier'>/image</font> for the PNG/SVG bytes.",
      s["body"],
    )
  )

  # 8. Human Evaluation
  story.append(Paragraph("8. Human Evaluation", s["h1"]))
  story.append(
    Paragraph(
      "Purpose: collect expert/student ratings that can be correlated with AI composite scores "
      "(paper-style human validation).",
      s["body"],
    )
  )
  story.append(Paragraph("Step-by-step use", s["h2"]))
  story.append(bullets([
    "Read the on-page rubric (loaded from <font face='Courier'>prompts/human_evaluation_rubric.v1.txt</font>).",
    "Select an artifact from the list.",
    "Enter reviewer name and role (expert / student / advisor / author).",
    "Score four criteria on 1–5 sliders: semantic correctness, structural completeness, "
    "syntactic accuracy, overall coherence.",
    "Add optional comments and click <b>Save evaluation</b>.",
    "A mean score is stored and later appears in Analytics correlation.",
  ], s))
  story.append(Paragraph("How it works internally", s["h2"]))
  story.append(
    Paragraph(
      "Posts to <font face='Courier'>POST /api/human-review</font>. Backend creates/updates a Reviewer "
      "and a HumanReview row linked to the artifact.",
      s["body"],
    )
  )

  # 9. Analytics
  story.append(Paragraph("9. Analytics", s["h1"]))
  story.append(
    Paragraph(
      "Purpose: quantitative summary for evaluation summaries.",
      s["body"],
    )
  )
  story.append(Paragraph("Step-by-step use", s["h2"]))
  story.append(bullets([
    "Open Analytics to see totals: artifacts, render failures, package failures, "
    "majority accepted, dataset accepted, human↔AI correlation.",
    "Inspect composite score distribution charts (overall and by diagram type).",
    "Check repair success statistics.",
    "Export the dataset as CSV / JSONL / Parquet via the API export endpoints "
    "(documented on the page / README).",
  ], s))
  story.append(Paragraph("How it works internally", s["h2"]))
  story.append(
    Paragraph(
      "Reads <font face='Courier'>/api/analytics/summary</font> and "
      "<font face='Courier'>/api/analytics/distributions</font>. Export uses "
      "<font face='Courier'>/api/export/dataset?fmt=jsonl|csv|parquet</font>.",
      s["body"],
    )
  )

  story.append(PageBreak())

  # 10. Settings
  story.append(Paragraph("10. Settings", s["h1"]))
  story.append(
    Paragraph(
      "Purpose: verify runtime configuration before or during a session.",
      s["body"],
    )
  )
  story.append(Paragraph("Step-by-step use", s["h2"]))
  story.append(bullets([
    "Confirm API base URL.",
    "Read health JSON: provider mode, Java availability, mock flag, status.",
    "Check artifact / failure / mean-score metrics.",
    "If Java is missing, remote PlantUML rendering remains available.",
    "If mock providers are ON, the system is in offline mode (no external API keys required).",
  ], s))
  story.append(Paragraph("Important environment flags", s["h2"]))
  story.append(
    table(
      [
        [Paragraph("<b>Variable</b>", s["small"]), Paragraph("<b>Purpose</b>", s["small"])],
        [Paragraph("MOCK_PROVIDERS", s["small"]), Paragraph("true = offline mode without paid APIs (default)", s["small"])],
        [Paragraph("PLANTUML_REMOTE", s["small"]), Paragraph("true = use plantuml.com when local Java JDK is missing", s["small"])],
        [Paragraph("USE_OLLAMA", s["small"]), Paragraph("Use local Ollama models instead of cloud APIs", s["small"])],
        [Paragraph("OPENAI_API_KEY / BASE_URL", s["small"]), Paragraph("OpenAI-compatible live generation + scoring", s["small"])],
        [Paragraph("DATABASE_URL", s["small"]), Paragraph("SQLite by default; can point to Postgres", s["small"])],
        [Paragraph("ACCEPTANCE_TAU", s["small"]), Paragraph("Majority threshold (default 4.0)", s["small"])],
        [Paragraph("MIN_COMPOSITE_FOR_DATASET", s["small"]), Paragraph("Dataset gate minimum S (default 3.0)", s["small"])],
      ],
      [2.2 * inch, 5.0 * inch],
    )
  )

  # 11. Sidebar map
  story.append(Spacer(1, 10))
  story.append(Paragraph("11. Sidebar map (all UI pages)", s["h1"]))
  story.append(
    table(
      [
        [Paragraph("<b>Page</b>", s["small"]), Paragraph("<b>Audience intent</b>", s["small"]), Paragraph("<b>Writes data?</b>", s["small"])],
        [Paragraph("Home", s["small"]), Paragraph("Orientation + API health", s["small"]), Paragraph("No", s["small"])],
        [Paragraph("Dashboard", s["small"]), Paragraph("Counts &amp; recent artifacts", s["small"]), Paragraph("No", s["small"])],
        [Paragraph("Single Generation", s["small"]), Paragraph("Interactive generation pipeline", s["small"]), Paragraph("Yes — creates artifacts", s["small"])],
        [Paragraph("Batch Generation", s["small"]), Paragraph("Batch generation / dataset building", s["small"]), Paragraph("Yes — many artifacts", s["small"])],
        [Paragraph("Artifact Review", s["small"]), Paragraph("Inspect evidence in detail", s["small"]), Paragraph("No (read)", s["small"])],
        [Paragraph("Human Evaluation", s["small"]), Paragraph("Expert rubric scores", s["small"]), Paragraph("Yes — reviews", s["small"])],
        [Paragraph("Analytics", s["small"]), Paragraph("Distributions &amp; export", s["small"]), Paragraph("No (export read)", s["small"])],
        [Paragraph("Settings", s["small"]), Paragraph("Health &amp; config flags", s["small"]), Paragraph("No", s["small"])],
      ],
      [1.55 * inch, 3.3 * inch, 2.35 * inch],
    )
  )

  # 12. Training corpus
  story.append(Spacer(1, 10))
  story.append(Paragraph("12. Training corpus builder (CLI, not a UI page)", s["h1"]))
  story.append(
    Paragraph(
      "Separate from the interactive UI, the repository includes "
      "<font face='Courier'>scripts/build_training_corpus.py</font> (also "
      "<font face='Courier'>make training-corpus</font>). It downloads open Hugging Face "
      "UMLCode datasets, normalizes them into the thesis schema (spec/code/scores/majority/"
      "dataset flags), and writes <b>8,000</b> training rows to "
      "<font face='Courier'>data/training/</font> (parquet + JSONL). "
      "Open sources are abundant for class diagrams but only ~1k each for object/component/package; "
      "flowchart/activity rows help reach the 8,000 total. This supports the training-corpus construction "
      "without requiring the gated class-scored Hugging Face repo.",
      s["body"],
    )
  )

  # 13. Demo script
  story.append(Paragraph("13. Recommended 5-minute local run script", s["h1"]))
  story.append(bullets([
    "<b>0:30</b> — Home: show API connected, provider status, and UML-Pipeline branding.",
    "<b>1:00</b> — Single Generation: paste bookstore requirement → class diagram.",
    "<b>2:00</b> — Walk the validation strip (render gate, S, majority A, dataset accepted).",
    "<b>2:45</b> — Show PlantUML + image + three VLM scores.",
    "<b>3:30</b> — Optionally regenerate as flowchart (extension beyond paper’s four UML types).",
    "<b>4:00</b> — Artifact Review: open the same artifact and show stored trace.",
    "<b>4:30</b> — Human Evaluation: submit a quick 4-criterion rubric.",
    "<b>5:00</b> — Analytics / Dashboard: show counts and mention 8k open training corpus CLI.",
  ], s))

  # 14. Scope
  story.append(Paragraph("14. Implementation scope notes", s["h1"]))
  story.append(bullets([
    "This is a <b>research prototype</b> for automated dataset generation and multimodal verification — not a commercial UML modeling IDE.",
    "Default mock mode produces content-aware but simulated LLM/VLM behavior for reliable offline runs.",
    "Live models require API keys or Ollama and will produce different scores/diagrams.",
    "The paper’s ideal balance is 2,000 samples × 4 UML types; open Hugging Face sources are not perfectly balanced, so the assembled 8k corpus documents its mix in <font face='Courier'>manifest.json</font>.",
    "Flowchart is an explicit extension beyond the paper’s four design-phase UML types.",
  ], s))

  story.append(Spacer(1, 10))
  story.append(
    Paragraph(
      "Regenerate this PDF anytime with:<br/>"
      "<font face='Courier'>PYTHONPATH=. python scripts/generate_app_walkthrough_pdf.py</font><br/>"
      "Output: <font face='Courier'>docs/Application_Walkthrough_Guide.pdf</font>",
      s["small"],
    )
  )

  OUT.parent.mkdir(parents=True, exist_ok=True)
  doc = SimpleDocTemplate(
    str(OUT),
    pagesize=letter,
    leftMargin=0.75 * inch,
    rightMargin=0.75 * inch,
    topMargin=0.65 * inch,
    bottomMargin=0.7 * inch,
    title="UML Multimodal Studio — Application Walkthrough",
    author="Dipak Yadav",
  )
  doc.build(story, onFirstPage=footer, onLaterPages=footer)
  print(f"Wrote {OUT}")


if __name__ == "__main__":
  build()
