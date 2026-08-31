#!/usr/bin/env python3
"""Generate a detailed 7–8 page application progress PDF."""

from __future__ import annotations

import shutil
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
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

from scripts.pdf_github_compat import disable_reportlab_ascii85, github_compat_pdf

disable_reportlab_ascii85()

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "UML_Pipeline_Application_Report.pdf"
ARTIFACTS = Path("/opt/cursor/artifacts") / "UML_Pipeline_Application_Report.pdf"

INK = colors.HexColor("#14212b")
ACCENT = colors.HexColor("#0f766e")
LIGHT = colors.HexColor("#f3efe6")
LINE = colors.HexColor("#d5cfc2")
MUTED = colors.HexColor("#3a4a57")


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "T", parent=base["Title"], fontName="Helvetica-Bold", fontSize=16,
            leading=20, textColor=INK, alignment=TA_CENTER, spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "S", parent=base["Normal"], fontName="Helvetica", fontSize=10.5,
            leading=14, textColor=ACCENT, alignment=TA_CENTER, spaceAfter=4,
        ),
        "meta": ParagraphStyle(
            "M", parent=base["Normal"], fontSize=9, leading=12,
            textColor=MUTED, alignment=TA_CENTER, spaceAfter=10,
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=12.5,
            leading=16, textColor=ACCENT, spaceBefore=11, spaceAfter=5,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=10.5,
            leading=13, textColor=INK, spaceBefore=8, spaceAfter=4,
        ),
        "h3": ParagraphStyle(
            "H3", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=9.8,
            leading=12, textColor=INK, spaceBefore=6, spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "B", parent=base["Normal"], fontName="Helvetica", fontSize=9.4,
            leading=12.4, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "Bu", parent=base["Normal"], fontName="Helvetica", fontSize=9.1,
            leading=12.0, textColor=INK,
        ),
        "cell": ParagraphStyle(
            "C", parent=base["Normal"], fontName="Helvetica", fontSize=7.9,
            leading=10.4, textColor=INK,
        ),
        "cellh": ParagraphStyle(
            "CH", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.9,
            leading=10.4, textColor=colors.white,
        ),
        "caption": ParagraphStyle(
            "Cap", parent=base["Normal"], fontName="Helvetica-Oblique", fontSize=8,
            leading=10, textColor=MUTED, spaceAfter=8, spaceBefore=2,
        ),
    }


def bullets(items, style):
    return ListFlowable(
        [ListItem(Paragraph(i, style), leftIndent=8, bulletColor=ACCENT) for i in items],
        bulletType="bullet",
        start="•",
        leftIndent=12,
    )


def P(text, st):
    return Paragraph(text, st)


def table(rows, col_widths, header=True):
    t = Table(rows, colWidths=col_widths, hAlign="LEFT")
    cmds = [
        ("FONTSIZE", (0, 0), (-1, -1), 7.9),
        ("BACKGROUND", (0, 1 if header else 0), (-1, -1), LIGHT),
        ("TEXTCOLOR", (0, 1 if header else 0), (-1, -1), INK),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        cmds.extend([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])
    t.setStyle(TableStyle(cmds))
    return t


def add_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(0.7 * inch, 0.52 * inch, letter[0] - 0.7 * inch, 0.52 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#5a6a75"))
    canvas.drawString(0.7 * inch, 0.36 * inch, "UML-Pipeline — Application Report (M.S. Thesis)")
    canvas.drawRightString(letter[0] - 0.7 * inch, 0.36 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build():
    s = styles()
    c, h = s["cell"], s["cellh"]
    story = []
    W = 7.1 * inch

    story.append(P("UML-Pipeline Application", s["title"]))
    story.append(P("Detailed Progress and System Design Report", s["title"]))
    story.append(P(
        "Automated UML Dataset Generation from Natural-Language Requirements<br/>"
        "with Multimodal Verification for Software Design",
        s["subtitle"],
    ))
    story.append(P(
        "Student: Dipak Yadav (Campus ID 033783670) &nbsp;·&nbsp; Advisor: Dr. Yutong Zhao<br/>"
        "M.S. Thesis application — California State University, Long Beach (CECS 698)<br/>"
        "Production host: Apple Mac Studio M1 Ultra, 128 GB &nbsp;·&nbsp; Report date: 31 August 2026<br/>"
        "Public code: https://github.com/dipak5501/uml-generation-pipeline",
        s["meta"],
    ))

    # --- 1 ---
    story.append(P("1. Purpose and research goal", s["h1"]))
    story.append(P(
        "This report documents the UML-Pipeline application: what the software does, which UML "
        "types it produces, where training and test data come from, how the system is designed, "
        "which features are implemented, and what has been measured. It also states how each "
        "part of the application realizes the thesis method (specification, PlantUML synthesis, "
        "render gate, and multimodal verification).",
        s["body"],
    ))
    story.append(P(
        "Manual UML modeling is slow and inconsistent. Large language models can draft diagrams "
        "from text, but outputs may be syntactically invalid or semantically wrong. This project "
        "treats generation and verification as one pipeline so that a requirement or source file "
        "becomes a technical specification, then PlantUML, then a rendered image that can be "
        "scored and gated for a research dataset of (specification, PlantUML, score) triples.",
        s["body"],
    ))
    story.append(P("1.1 How the application implements the thesis", s["h2"]))
    story.append(P(
        "The thesis defines a three-stage method. The application is the runnable realization of "
        "that method, plus engineering needed to make generation reliable (validation, repair, "
        "grounded PlantUML builders, persistence, and a user interface).",
        s["body"],
    ))
    story.append(table(
        [
            [P("Thesis element", h), P("What the application does", h)],
            [P("Stage 1 — technical specification", c),
             P("LLaMA-class spec model (local Ollama) turns NL or source into JSON (entities, relationships, type-specific fields), then validity + grounding", c)],
            [P("Stage 2 — PlantUML for class, object, component, package", c),
             P("Paper path: DeepSeek-R1-32B. Local path: LoRA PlantUML + spec-faithful builder so diagrams stay typed and named", c)],
            [P("Stage 3 — render gate", c),
             P("PlantUML JAR compile and PNG; failed render forces composite score S = 0", c)],
            [P("Three VLMs + MMMU weights 53.1 / 50.7 / 39.9", c),
             P("Qwen2.5-VL-3B, LLaMA-3.2-Vision-11B, Aya-Vision-8B score each image 0–6 on the four-criterion rubric", c)],
            [P("Majority acceptance A and composite S", c),
             P("τ = 4 with ≥2 votes; dataset entry requires render_ok, A, and S ≥ 3", c)],
            [P("Design-phase UML only", c),
             P("UI and API expose class, object, component, package only", c)],
            [P("Human evaluation / alignment", c),
             P("Same four criteria in the Human Evaluation page; correlation study not yet run", c)],
            [P("Public code and dataset tooling", c),
             P("GitHub repository, SQLite artifacts, export filtered by the thesis gate", c)],
        ],
        [2.4 * inch, 4.7 * inch],
    ))
    story.append(P("Thesis method mapped onto the running application.", s["caption"]))

    # --- 2 ---
    story.append(P("2. What the application creates: UML diagram types", s["h1"]))
    story.append(P(
        "The product generates four design-phase UML types. Sequence, use-case, deployment, "
        "and activity/flowchart diagrams are not offered in the UI. Sequence PlantUML is "
        "rejected by UML structure rules (negative control NEG-sequence-unsupported). "
        "Flowchart/activity rows may appear in optional training top-up data but are not a "
        "thesis product type.",
        s["body"],
    ))
    story.append(table(
        [
            [P("Type", h), P("What it shows", h), P("Typical PlantUML", h), P("When the app uses it", h)],
            [P("<b>Class</b>", c),
             P("Types, attributes, methods, associations, inheritance, composition/aggregation", c),
             P("class Name { fields; methods() } with --|&gt; *-- o-- --&gt;", c),
             P("Default type; strongest LoRA coverage; structural analysis from source code", c)],
            [P("<b>Object</b>", c),
             P("Runtime instances, slots, and links between objects", c),
             P('object "name" as alias { slot = value } and links', c),
             P("Instance view of the same domain; historically weaker render rate in bulk NL tests", c)],
            [P("<b>Component</b>", c),
             P("Deployable/logical components, provided interfaces, dependencies", c),
             P("[Name] as Alias, () \"IName\", ..&gt; uses", c),
             P("Service/architecture view; local path uses spec-builder until LoRA is proven", c)],
            [P("<b>Package</b>", c),
             P("Namespaces/modules, nested contents, package dependencies", c),
             P("package Name { ... } and ..&gt; between packages", c),
             P("Module structure; hardest type historically; spec-builder default locally", c)],
        ],
        [0.95 * inch, 2.05 * inch, 2.05 * inch, 2.05 * inch],
    ))
    story.append(P(
        "Table 1. Product UML types. Inputs may be English (or other) requirements or source code "
        "(Python, Java, and other languages detected by the code-analysis service).",
        s["caption"],
    ))
    story.append(P("2.1 Class diagrams", s["h2"]))
    story.append(P(
        "Class diagrams are the primary design artifact. Stage 1 extracts entity names, attributes, "
        "and methods from the requirement or from declared types in source. Stage 2 emits PlantUML "
        "class blocks and relationships. Inheritance is rendered with --|&gt; only when the spec "
        "marks inheritance; otherwise associations, dependencies, composition, or aggregation are "
        "used. The fidelity gate replaces placeholder names such as Module1/EntityA with spec names.",
        s["body"],
    ))
    story.append(P("2.2 Object diagrams", s["h2"]))
    story.append(P(
        "Object diagrams instantiate types from the specification (for example book1 : Book). "
        "They are intended to show a snapshot of collaborating instances, not the type system. "
        "In the 1,000-row multilingual NL bulk test, object diagrams were the weakest of the four "
        "types among render failures.",
        s["body"],
    ))
    story.append(P("2.3 Component diagrams", s["h2"]))
    story.append(P(
        "Component diagrams map domain concepts to components and interfaces (for example [Cart] "
        "with ICart). A prior defect produced empty @startuml/@enduml and a blank PNG when LoRA "
        "failed and a filter dropped generic names. The application now defaults "
        "component generation to the grounded spec-builder, never emits an empty component diagram, "
        "and harvests actors and verb objects (Customer, Cart, Product, Order, Payment, and so on). "
        "A live e-commerce requirement produced eight named components, compiled, rendered, and "
        "passed UML acceptance.",
        s["body"],
    ))
    story.append(P("2.4 Package diagrams", s["h2"]))
    story.append(P(
        "Package diagrams group types into packages (core, api, domain-named packages) with "
        "dependency arrows. Nesting and dependency semantics are a known failure mode in the "
        "literature and in earlier live VLM runs (one package render failure in a 12-run smoke). "
        "The application includes a package-failure taxonomy API for analytics.",
        s["body"],
    ))

    # --- 3 ---
    story.append(P("3. System design", s["h1"]))
    story.append(P("3.1 Deployment view", s["h2"]))
    story.append(P(
        "Production runs on an always-on Apple Mac Studio (M1 Ultra, 128 GB unified memory) "
        "under user LaunchAgents. Clients are the Streamlit UI (http://127.0.0.1:8501 and a "
        "Cloudflare public URL) and HTTP/CLI callers, including POST /api/agent/command. "
        "They call FastAPI on :8000. Orchestration in app/services/orchestration.py runs "
        "Stages 1–3. Background jobs use a thread pool. Persistence is SQLite "
        "(data/uml_app.db) plus PNG files under data/artifacts/. PlantUML rendering uses "
        "a local JDK plus tools/plantuml.jar (optional remote PlantUML HTTP). PlantUML "
        "generation uses the MLX LoRA adapter models/uml-plantuml-lora-sourcecode-30k. "
        "Fine-tuning is offline (make train-source30k / make finetune), not in the request path.",
        s["body"],
    ))
    story.append(P(
        "[Streamlit UI / HTTP clients] → FastAPI routers → orchestration → "
        "(providers | PlantUML JAR | SQLite+PNG). Providers: Mock, Ollama (spec + VLMs), "
        "MLX LoRA (PlantUML), Hugging Face or OpenAI-compatible (optional), local Aya-Vision weights.",
        s["body"],
    ))
    story.append(P("3.2 End-to-end generation flow", s["h2"]))
    story.append(P(
        "1. Intake. The client sends requirement text or source code, a diagram type, and flags "
        "(async_mode, skip_vlm). Input is clipped and classified (requirement vs source_code). "
        "2. Stage 1. A chat model (paper: LLaMA 3.2-1B-Instruct; local Ollama llama3.2:1b) writes "
        "JSON. ensure_valid_spec merges grounded names from NL or AST-like code analysis. "
        "3. Stage 2. choose_generator selects lora, spec-builder, or llm from adaptation memory. "
        "PlantUML is sanitized, validated, and optionally repaired (max 3). "
        "4. Compile and render. plantuml -checkonly then PNG. Render fail ⇒ S = 0. "
        "5. Deterministic acceptance. Syntax, compile, render, UML rules, spec fidelity, "
        "semantic/traceability. "
        "6. Stage 3 VLMs (unless skip_vlm). Three vision models score 0–6 on four criteria. "
        "7. Dual-signal gate. Majority A (τ=4, ≥2 votes) and composite S; dataset flag if "
        "render_ok ∧ A ∧ S≥3. "
        "8. Persist. Artifact, scores, repairs, traces; UI gallery and analytics.",
        s["body"],
    ))
    story.append(P("3.3 Software modules", s["h2"]))
    story.append(table(
        [
            [P("Module", h), P("Responsibility", h)],
            [P("app/routers/generate.py", c), P("POST /api/generate, /generate/batch, GET /samples", c)],
            [P("app/routers/artifacts.py", c),
             P("Jobs, artifact CRUD-style reads, PNG, PlantUML text, rescore, repair, library gallery", c)],
            [P("app/routers/analytics.py", c),
             P("Summary, score distributions, package failures, dataset export, adaptation status, health", c)],
            [P("app/routers/human_review.py", c), P("POST /api/human-review four-criterion rubric", c)],
            [P("app/services/orchestration.py", c), P("run_single_generation: spec → PlantUML → repair → render → VLM → persist", c)],
            [P("app/services/spec_json.py", c), P("JSON validity, NL concept harvest, code-to-spec structure", c)],
            [P("app/services/plantuml_from_spec.py", c), P("Deterministic builders for all four types + fidelity replace", c)],
            [P("app/services/repair.py / adaptation.py", c), P("Category repair strategies; generator/strategy win rates", c)],
            [P("app/services/acceptance.py / uml_structure.py / traceability.py", c),
             P("Multi-layer accept/reject with failure categories", c)],
            [P("app/services/scoring.py", c), P("MMMU-weighted S, majority A, dataset_entry_accepted", c)],
            [P("app/providers/", c), P("Mock, Ollama, HF, OpenAI-compatible, MLX LoRA, PEFT CUDA, local Aya", c)],
            [P("app/routers/agent.py", c), P("Remote allowlisted commands for the Mac Studio operator API", c)],
            [P("prompts/*.v1.txt", c), P("Versioned Stage-1, Stage-2, VLM, repair, human rubric templates", c)],
            [P("ui/pages/", c), P("Eight Streamlit pages listed in Section 5", c)],
        ],
        [2.35 * inch, 4.75 * inch],
    ))
    story.append(P("Table 2. Principal code modules.", s["caption"]))

    story.append(P("3.4 Provider routing", s["h2"]))
    story.append(table(
        [
            [P("Stage", h), P("Paper model", h), P("Local application path", h)],
            [P("Specification", c), P("LLaMA 3.2-1B-Instruct", c), P("Ollama llama3.2:1b; mock; optional HF/OpenAI", c)],
            [P("PlantUML (class)", c), P("DeepSeek-R1-Distill-Qwen-32B", c),
             P("MLX LoRA Qwen2.5-0.5B (production: models/uml-plantuml-lora-sourcecode-30k)", c)],
            [P("PlantUML (object)", c), P("Same 32B", c), P("LoRA if chosen; fidelity + builder fallback", c)],
            [P("PlantUML (component, package)", c), P("Same 32B", c),
             P("Spec-builder default until LoRA has ≥8 proven samples; skip empty LLM rewrite", c)],
            [P("VLM Qwen slot", c), P("Qwen2.5-VL-3B (w=53.1)", c), P("Ollama 0.32 qwen2.5vl:3b on :11435", c)],
            [P("VLM LLaMA slot", c), P("LLaMA-3.2-11B-Vision (w=50.7)", c), P("Ollama 0.24 llama3.2-vision:11b on :11434", c)],
            [P("VLM Aya slot", c), P("Aya-Vision-8B (w=39.9)", c),
             P("VLM_AYA_BACKEND=local Hugging Face weights; optional llava stand-in or vLLM", c)],
        ],
        [1.7 * inch, 2.2 * inch, 3.2 * inch],
    ))
    story.append(P(
        "Table 3. Model routing. Dual Ollama is required because 0.32 cannot load llama3.2-vision "
        "and 0.24 cannot run qwen2.5vl. scripts/ensure_ollama_dual.sh starts both.",
        s["caption"],
    ))

    story.append(P("3.5 Scoring formulas (as coded)", s["h2"]))
    story.append(P(
        "Render gate: if PNG rendering fails, S = 0. Otherwise "
        "S = Σ(w_j · s_j) / Σ(w_j) over available numeric scores, with w = (53.1, 50.7, 39.9). "
        "Unavailable scorers (None) are skipped. Majority: v_j = 1 if s_j ≥ τ (default 4); "
        "A = 1 if Σ v_j ≥ 2. Dataset entry: render_ok ∧ A ∧ S ≥ 3.0. VLM rubric criteria: "
        "semantic correctness, structural completeness, syntactic accuracy, overall coherence.",
        s["body"],
    ))

    story.append(P("3.6 Acceptance and repair", s["h2"]))
    story.append(P(
        "Independent of VLMs, evaluate_acceptance checks syntax, PlantUML compile, render, "
        "UML type rules (for example no sequence as a product type), consistency with the spec, "
        "and semantic/traceability to the requirement. Repair strategies include sanitize_syntax, "
        "inject_missing, strip_hallucinations, spec_rebuild, and llm_targeted. Empty PlantUML "
        "from a strategy is discarded. Adaptation memory stores per-type generator and strategy "
        "success rates under data/adaptation_memory.json.",
        s["body"],
    ))

    # --- 4 data ---
    story.append(P("4. Datasets for training, testing, and evaluation", s["h1"]))
    story.append(P(
        "Data fall into four buckets: (A) open Hugging Face UML corpora for LoRA training, "
        "(B) locally generated supplemental NL and code rows, (C) application sample requirements "
        "and golden tests, (D) evaluation runs that measure the running pipeline. Training files "
        "under data/ are gitignored; scripts rebuild them.",
        s["body"],
    ))

    story.append(P("4.1 Training corpora (Hugging Face UMLCode)", s["h2"]))
    story.append(P(
        "scripts/build_training_corpus.py assembles a paper-oriented set of about 8,000 rows "
        "across class, object, component, and package (target up to 2,000 per type, topped up "
        "with extra class rows if a type is short). Optional --include-flowchart appends activity "
        "rows; that is not a product diagram type.",
        s["body"],
    ))
    story.append(table(
        [
            [P("Hugging Face dataset", h), P("Forced / allowed type", h), P("Role", h)],
            [P("nguyenvanviet/UMLCode-ClassDiagram-DeepSeek-32B-Reasoning-RAW", c),
             P("class", c), P("Primary class PlantUML + requirement/spec pairs", c)],
            [P("nguyenvanviet/UMLCode_ObjectDiagram_Scored", c), P("object", c), P("Scored object diagrams", c)],
            [P("nguyenvanviet/UMLCode_ComponentDiagram_Scored", c), P("component", c), P("Scored component diagrams", c)],
            [P("nguyenvanviet/UMLCode_PackageDiagram_Scored", c), P("package", c), P("Scored package diagrams", c)],
            [P("nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-UC-Class-Sequence-Scored", c),
             P("class, object, component, package (filtered)", c), P("Top-up; sequence/use-case dropped for product types", c)],
            [P("nguyenvanviet/UMLCode_Activity_Final (optional)", c), P("flowchart/activity", c), P("Optional fill only; not in UI", c)],
            [P("nguyenvanviet/UMLCode_DeploymentDiagram (top-up)", c), P("filtered to paper types", c), P("Used only if count &lt; 8000", c)],
        ],
        [2.7 * inch, 2.0 * inch, 2.4 * inch],
    ))
    story.append(P(
        "Table 4. Open sources listed in scripts/build_training_corpus.py. A gated class-scored "
        "HF set is optional via scripts/download_datasets.py --include-gated (HF_TOKEN + license).",
        s["caption"],
    ))
    story.append(P(
        "Local artifacts after build: data/training/uml_training_8000.parquet and .jsonl, "
        "manifest.json. After supplements: uml_training_supplement_merged.parquet. Fine-tune "
        "JSONL: data/finetune/{train,valid,test}.jsonl. Production LoRA on the Mac Studio is "
        "models/uml-plantuml-lora-sourcecode-30k (6,000 iters, Java/Python/C source corpus) on "
        "mlx-community/Qwen2.5-0.5B-Instruct-4bit. NVIDIA hosts use PEFT via "
        "scripts/finetune_plantuml_cuda.py. Only Stage 2 PlantUML uses LoRA.",
        s["body"],
    ))

    story.append(P("4.2 Supplemental training and stress-test sets (local)", s["h2"]))
    story.append(P(
        "scripts/build_scenario_code_corpus.py synthesizes two extra 1,000-row sets used both "
        "as LoRA supplements and as generate/render stress tests (VLM mocked for throughput):",
        s["body"],
    ))
    story.append(table(
        [
            [P("Set", h), P("n", h), P("Contents", h), P("Files", h)],
            [P("NL scenarios", c), P("1,000", c),
             P("20 domains (ecommerce, hospital, banking, education, logistics, IoT, HR, …) × templates in 19 languages (en, es, fr, de, hi, zh, pt, it, ja, ko, ar, ru, nl, tr, pl, sv, vi, th, id)", c),
             P("data/training/scenarios_1000.jsonl; data/eval/scenarios_1000.jsonl", c)],
            [P("Source code", c), P("1,000", c),
             P("20 languages: Python, Java, JavaScript, TypeScript, Rust, Go, C#, Kotlin, Swift, C++, Ruby, PHP, Scala, Dart, Perl, Lua, R, MATLAB, Haskell, Elixir", c),
             P("data/training/code_langs_1000.jsonl; data/eval/code_langs_1000.jsonl", c)],
            [P("Merged supplement", c), P("2,000", c),
             P("Parquet compatible with prepare_finetune_data", c),
             P("data/training/uml_supplement_2000.parquet", c)],
        ],
        [1.25 * inch, 0.7 * inch, 2.85 * inch, 2.3 * inch],
    ))
    story.append(P("Table 5. Locally generated supplemental corpora.", s["caption"]))

    story.append(P("4.3 Application sample and golden tests", s["h2"]))
    story.append(table(
        [
            [P("Resource", h), P("Size", h), P("Use", h)],
            [P("sample_data/requirements.txt", c),
             P("50 English design requirements (bookstore, hospital, fleet, LMS, …)", c),
             P("UI samples API; acceptance benchmark × 4 types = 200 cases", c)],
            [P("tests/golden/cases.json", c),
             P("6 labeled cases (class, package, component, object)", c),
             P("Golden regression for names/relationships", c)],
            [P("NEGATIVE_CASES in eval_acceptance.py", c),
             P("5 must-reject diagrams (empty, missing names, hallucinations, bad syntax, sequence)", c),
             P("True-negative rate of the acceptance stack", c)],
            [P("pytest suite", c),
             P("Unit/API tests under tests/ (acceptance, spec JSON, PlantUML builder, adaptation, validators, API)", c),
             P("Continuous checks of services, not a 8k dataset pass", c)],
        ],
        [1.9 * inch, 2.6 * inch, 2.6 * inch],
    ))
    story.append(P("Table 6. In-repo test fixtures.", s["caption"]))

    story.append(P("4.4 Evaluation campaigns and measured counts", s["h2"]))
    story.append(P(
        "The following counts are what this application has actually run. They must not be "
        "conflated with manuscript human-study figures unless those studies are re-executed.",
        s["body"],
    ))
    story.append(table(
        [
            [P("Campaign", h), P("Data source", h), P("n (how computed)", h), P("What was measured", h), P("Result", h)],
            [P("Golden acceptance", c), P("tests/golden/cases.json", c), P("6", c),
             P("Generate+compile+render+UML+semantic (no VLM)", c), P("6/6 accepted", c)],
            [P("Benchmark acceptance", c), P("requirements.txt × {class,object,component,package}", c),
             P("50 × 4 = 200", c), P("Same deterministic stack; reports/acceptance_eval.md", c),
             P("200/200 accepted", c)],
            [P("Negative controls", c), P("Hand-crafted invalid PlantUML", c), P("5", c),
             P("Must reject", c), P("5/5 rejected; 0 false accepts", c)],
            [P("Live 3-VLM smoke", c), P("Stratified types + multilingual + source-code", c), P("12", c),
             P("All scorers up, render, mean S", c),
             P("12/12 scorers; 11/12 render; mean S≈4.93", c)],
            [P("Mac Studio live generate (31 Aug 2026)", c),
             P("Bookstore class diagram via /api/agent generate, skip_vlm=false", c), P("1", c),
             P("Render + three-VLM composite S", c),
             P("render success; S ≈ 5.37", c)],
            [P("NL bulk generate/render", c), P("data/eval/scenarios_1000.jsonl", c), P("1,000", c),
             P("Valid UML + PNG; VLM mocked", c), P("974/1000 (97.4%)", c)],
            [P("Code bulk generate/render", c), P("data/eval/code_langs_1000.jsonl", c), P("1,000", c),
             P("Valid UML + PNG; VLM mocked", c), P("1000/1000 (100%)", c)],
        ],
        [1.35 * inch, 1.55 * inch, 1.15 * inch, 1.55 * inch, 1.5 * inch],
    ))
    story.append(P(
        "Table 7. Evaluation inventory. Total distinct evaluation items in these campaigns: "
        "6 + 200 + 5 + 12 + 1,000 + 1,000 = 2,223 pipeline runs of different kinds. The 8,000-row "
        "HF set is for training, not a full live 3-VLM pass. The 2,000 bulk rows measure render, "
        "not S. Interactive UI generate may skip VLMs; batch/rescore apply the paper gate.",
        s["caption"],
    ))

    # --- 5 features ---
    story.append(P("5. Application features", s["h1"]))
    story.append(P("5.1 Streamlit UI", s["h2"]))
    story.append(table(
        [
            [P("Page", h), P("Features", h)],
            [P("Home / Dashboard", c),
             P("API health, artifact counts, render/score snapshot, navigation into generate and batch", c)],
            [P("Single Generation", c),
             P("NL or paste source code; select class/object/component/package; async job; skip_vlm for faster interactive diagrams; show spec, PlantUML, PNG, acceptance, S/A when scored", c)],
            [P("Batch Generation", c),
             P("Many requirements, multiple types, progress, job status; intended path for paper scoring", c)],
            [P("Generated Diagrams", c),
             P("Paginated gallery of rendered UML, PlantUML text, filters, dataset flags", c)],
            [P("Human Evaluation", c),
             P("Four scores matching the VLM rubric plus comments; stored on the artifact", c)],
            [P("Analytics", c),
             P("Distributions of S, render rates by type, package-failure breakdown, adaptation win rates", c)],
            [P("Settings", c),
             P("Provider mix, LoRA path, VLM backend, health of dual Ollama, adaptation status", c)],
            [P("System Design", c),
             P("In-app architecture text aligned with this report", c)],
        ],
        [1.7 * inch, 5.4 * inch],
    ))
    story.append(P("Table 8. UI feature map.", s["caption"]))

    story.append(P("5.2 API and jobs", s["h2"]))
    story.append(P(
        "REST under /api: generate (sync or async), batch generate, samples, jobs, artifacts, "
        "library, image, plantuml download, rescore, repair, human-review, analytics summary "
        "and distributions, package-failures, export/dataset (majority + S≥3 filter), "
        "adaptation/status, settings/health. Optional API_ACCESS_TOKEN. Input caps "
        "(requirement length, batch size). PlantUML preprocessor directives are stripped "
        "from labels to reduce injection into the renderer.",
        s["body"],
    ))
    story.append(P("5.3 Generation quality features", s["h2"]))
    story.append(bullets([
        "Two input modes: natural-language requirements and source code (structure-first for long files).",
        "JSON Stage-1 spec with validity metrics and grounded concept merge (Cart, Order, … from prose).",
        "Chain-of-thought stripping so private reasoning is not shown as PlantUML.",
        "Spec-faithful builders so class/object/component/package stay typed and named.",
        "Adaptive generator policy and repair ordered by empirical win rate.",
        "Render-as-gate, MMMU-weighted ensemble, majority vote, dataset export.",
        "Human rubric parallel to VLMs for later correlation studies.",
        "Mock providers so the app runs without GPUs; live Mac Studio path uses Ollama + 30k LoRA + local Aya.",
        "Remote agent: health, generate, smoke-test, training-status, restart API/UI.",
        "Colab helper for Qwen2.5-VL-3B scoring only (not Aya-8B or LLaMA-11B on free T4).",
    ], s["bullet"]))

    story.append(P("5.4 Production Mac Studio (always-on)", s["h2"]))
    story.append(P(
        "The thesis demonstration server is an Apple Mac Studio (Mac13,2, M1 Ultra, 128 GB) "
        "at /Users/033783670/Desktop/uml-generation-pipeline-main. User LaunchAgents keep "
        "API, UI, dual Ollama, caffeinate, and Cloudflare tunnels running while the account "
        "stays logged in. Remote Cursor Cloud Agents do not run on this hardware; they "
        "operate the Mac through POST /api/agent/command. NVIDIA CUDA LoRA "
        "(make finetune-cuda) is documented for other machines and must not be run on this Mac.",
        s["body"],
    ))
    story.append(table(
        [
            [P("Service", h), P("Local", h), P("Notes", h)],
            [P("FastAPI", c), P(":8000", c), P("Live providers; API_ACCESS_TOKEN on public tunnels", c)],
            [P("Streamlit UI", c), P(":8501", c), P("Eight pages; public Cloudflare URL", c)],
            [P("Ollama 0.24", c), P(":11434", c), P("llama3.2-vision:11b (and llama3.2:1b spec)", c)],
            [P("Ollama 0.32", c), P(":11435", c), P("qwen2.5vl:3b", c)],
            [P("Aya-Vision-8B", c), P("in-process MPS", c), P("VLM_AYA_BACKEND=local; ≥64 GB RAM", c)],
            [P("PlantUML LoRA", c), P("MLX", c), P("models/uml-plantuml-lora-sourcecode-30k", c)],
            [P("Remote agent", c), P("/api/agent", c), P("Allowlisted commands; 2 workers", c)],
        ],
        [1.5 * inch, 1.5 * inch, 4.1 * inch],
    ))
    story.append(P("Table 8b. Production Mac Studio services (measured 31 August 2026).", s["caption"]))

    # --- 6 results recap ---
    story.append(P("6. Connection to the thesis and remaining work", s["h1"]))
    story.append(table(
        [
            [P("Milestone", h), P("Application status", h)],
            [P("1. Pipeline completion", c),
             P("Stages 1–3, JSON spec, majority gate, UI, API, remote agent, 30k MLX LoRA, dual Ollama, local Aya on Mac Studio 128 GB: implemented and live", c)],
            [P("2. Dataset and evaluation", c),
             P("Training corpus scripts + 8k target; 2k supplement; 200-type acceptance; 2k bulk render; 12 live VLM; longer archived 3-VLM tables still needed", c)],
            [P("3. Human-alignment study", c),
             P("UI + prompt rubric ready; expert correlation study not executed", c)],
            [P("4. Thesis manuscript and research paper", c),
             P("Draft chapters exist; university format pass and paper revision remaining", c)],
        ],
        [1.9 * inch, 5.2 * inch],
    ))
    story.append(P("Table 9. Thesis work items versus application status.", s["caption"]))

    story.append(P("6.1 Limitations (application)", s["h2"]))
    story.append(bullets([
        "On-device Stage 2 is 0.5B LoRA + spec-builder, not DeepSeek-R1-32B.",
        "24 GB Macs must not load Aya on MPS; Mac Studio 128 GB is the paper-exact local Aya path.",
        "LoRA training data is class-heavy; component/package rely on the grounded builder locally.",
        "Full three-VLM scoring is ~100–120 s per diagram; interactive skip_vlm does not compute S.",
        "The 1,000+1,000 bulk numbers mock VLMs; they are render success, not dataset-accepted counts.",
        "The 8,000 HF rows train LoRA; they are not a completed live scored dataset export from this UI.",
        "Package/object remain harder than class.",
        "Human vs S correlation is not yet a finished study.",
    ], s["bullet"]))

    story.append(P("6.2 Next engineering and writing work", s["h2"]))
    story.append(bullets([
        "Freeze a reproducible live 3-VLM + acceptance snapshot for thesis tables.",
        "Package-diagram failure examples from package-failures analytics.",
        "Scope or run the human-alignment protocol on a stratified subset.",
        "Thesis formatting, citation check, and paper revision.",
    ], s["bullet"]))

    story.append(P("7. How to reproduce the local application", s["h1"]))
    story.append(P(
        "Clone https://github.com/dipak5501/uml-generation-pipeline . Create the venv (make install). "
        "Mac Studio live path: MOCK_PROVIDERS=false USE_OLLAMA=true USE_FINETUNED_CODE=true "
        "FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-sourcecode-30k VLM_AYA_BACKEND=local, "
        "then LaunchAgents or ./scripts/run_local.sh. UI: http://127.0.0.1:8501 . "
        "Health: GET /api/settings/health . Remote: POST /api/agent/command . "
        "Tests: make test (MOCK_PROVIDERS=true). NVIDIA only: make finetune-cuda. "
        "Java and plantuml.jar are required to render. Regenerate this PDF: "
        "python scripts/generate_progress_pdf.py . Thesis PDF: python scripts/generate_thesis_draft.py .",
        s["body"],
    ))

    story.append(Spacer(1, 8))
    story.append(P(
        "Respectfully submitted,<br/><b>Dipak Yadav</b><br/>"
        "dipak.yadav01@student.csulb.edu<br/>"
        "https://github.com/dipak5501/uml-generation-pipeline",
        s["body"],
    ))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.7 * inch,
        title="UML-Pipeline Application Report",
        author="Dipak Yadav",
    )
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    github_compat_pdf(OUT)
    print(OUT)
    try:
        ARTIFACTS.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(OUT, ARTIFACTS)
        print(ARTIFACTS)
    except OSError as exc:
        print(f"Skip artifacts copy: {exc}")


if __name__ == "__main__":
    build()
