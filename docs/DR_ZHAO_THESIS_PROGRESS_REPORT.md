# Thesis Implementation and Research Progress Report:
## AI-Driven UML Generation and Multimodal Verification

**Author:** Dipak Yadav  
**Advisor:** Dr. Yutong Zhao  
**Institution:** Master's Thesis Research  
**Repository:** [github.com/dipak5501/uml-generation-pipeline](https://github.com/dipak5501/uml-generation-pipeline)  
**Report date:** 2026-08-28  
**Audit basis:** Full repository inspection (source, configs, prompts, data artifacts, tests, reports). No numerical claim appears in this document unless traceable to on-disk evidence or explicitly labeled as a paper-draft claim not reproduced locally.

---

## 1. Executive Summary

This report documents the implementation status of the thesis project **"Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design."** The repository contains a **complete, deployable full-stack application** that implements the research pipeline end to end:

1. Natural-language requirements or source code are converted into a structured **technical specification** (Stage 1 LLM).
2. Specifications are converted into **PlantUML** code (Stage 2: MLX LoRA fine-tuned model with deterministic fallbacks, validation, and repair).
3. Diagrams are **rendered** to black-and-white PNG images via PlantUML (render gate).
4. Rendered diagrams are scored by a **three-model vision-language ensemble** (Stage 3).
5. A **weighted composite score S** and **majority-vote gate A** determine dataset inclusion.

**Verified local results (SQLite, 2026-08-28):** 470 persisted artifacts; 363 successful renders (77.2%); mean composite score 3.81; 311 dataset-accepted entries (66.2%). Class, component, and package diagrams achieve ~91–93% render success; **object diagrams lag at 29.5% render success**, representing the primary technical risk area.

A **Streamlit demonstration application** (8 pages) and **FastAPI backend** are implemented, tested (153 pytest cases), and documented for 24/7 deployment on an Apple Mac Studio. An imported **8000-row Hugging Face benchmark parquet** and deterministic **acceptance evaluation (200/200 benchmark pass)** provide additional evidence.

**Gaps for publication:** human evaluation data (0 reviews in database), paper-scale n=8000 live generation run, and correlation statistics reported in the LaTeX draft are **not verified from the current repository state**.

---

## 2. Research Problem and Motivation

Software design documentation often lags implementation because UML diagrams are tedious to produce manually. Recent large language models can translate natural language into formal notations, but generated diagrams may be syntactically invalid, semantically incomplete, or visually misleading. Vision-language models offer a complementary modality to assess whether a rendered diagram matches its specification.

The thesis addresses: **Can we automate reliable UML artifact generation from requirements and verify quality multimodally at scale?**

---

## 3. Thesis Objective

Design, implement, and evaluate a pipeline that:

- Accepts software requirements (and optionally source code) for four design-phase UML types: **class, object, component, package**.
- Produces validated PlantUML and rendered diagrams with full traceability.
- Scores diagram quality with an ensemble of three VLMs using MMMU-calibrated weights.
- Curates a dataset using dual gates (majority vote + composite threshold).
- Provides a demonstrable application for advisors, reviewers, and future publication.

---

## 4. Research Questions / Technical Goals

Derived conservatively from implemented functionality:

| # | Question / Goal | Implementation anchor |
|---|-----------------|----------------------|
| RQ1 | Can LLMs reliably produce structured technical specifications from NL requirements? | Stage 1 prompts + `spec_json.py` |
| RQ2 | Can LLMs or fine-tuned models generate valid PlantUML for four diagram types? | Stage 2 + repair + acceptance gates |
| RQ3 | Does PlantUML rendering serve as a reliable syntactic gate? | `render.py`, render_status in DB |
| RQ4 | Do three VLMs produce usable quality scores when aggregated? | `scoring.py`, ModelScore table |
| RQ5 | Does weighted ensemble scoring outperform single-model trust? | Methodology (ensemble implemented; ablation not yet run) |
| RQ6 | Can the system scale to batch dataset generation with export? | Batch API + parquet export |
| RQ7 | How do human experts correlate with automated scores? | Human eval UI (**data not yet collected**) |

---

## 5. Proposed System Overview

The system follows a sequential pipeline with feedback (repair) before scoring:

```text
Natural-Language Requirement  OR  Source Code
              ↓
   Technical Specification Generator (Stage 1 LLM)
              ↓
        JSON Spec + Prose Summary
              ↓
   UML / PlantUML Generator (Stage 2 LoRA / LLM / Builder)
              ↓
   Validate → Repair (≤3) → Compile-check → Render
              ↓
         PlantUML Code + PNG Image
              ↓
        Multimodal Verification (Stage 3)
      ↙           ↓           ↘
 Qwen-VL      LLaMA-Vision      Aya-Vision
      ↘           ↓           ↙
      Weighted Composite S + Majority Vote A
              ↓
   Dataset Gate (A=1 ∧ S≥3) → SQLite + Files + Export
```

---

## 6. System Architecture

### 6.1 Layered architecture

| Layer | Technology | Location |
|-------|------------|----------|
| Presentation | Streamlit multipage UI | `ui/` |
| API | FastAPI + Uvicorn | `app/main.py`, `app/routers/` |
| Orchestration | Generation, repair, scoring | `app/services/orchestration.py` |
| Research core | Render, legacy batch, scoring utils | `uml_pipeline/` |
| Providers | Mock, Ollama, HF, MLX LoRA, local Aya | `app/providers/` |
| Persistence | SQLite + artifact filesystem | `data/uml_app.db`, `data/artifacts/` |
| Prompts | Versioned templates | `prompts/*.v1.txt` |
| Configuration | YAML + `.env` | `config.yaml`, `.env.example` |

### 6.2 Entry points

| Entry | Command / URL |
|-------|---------------|
| Streamlit UI | `make ui` → http://127.0.0.1:8501 |
| FastAPI | `make api` → http://127.0.0.1:8000/docs |
| Legacy CLI batch | `python scripts/run_generation.py` |
| Dataset export | `GET /api/export/dataset?fmt=parquet` |

### 6.3 End-to-end trace (Single Generation)

When a user submits a requirement via Streamlit (`ui/pages/2_Single_Generation.py`):

1. **POST `/api/generate`** with `requirement`, `diagram_type`, `input_mode`, optional `skip_vlm`.
2. **`run_single_generation()`** creates `RequirementInput`, calls **`generate_technical_spec()`**.
3. Stage 1 uses **`build_chat_provider()`** + prompt `requirement_to_tech_spec.v1` (or code path).
4. **`ensure_valid_spec()`** validates JSON; may ground from source structure.
5. **`generate_plantuml_code()`** selects generator (LoRA / LLM / spec-builder) via adaptation memory.
6. **`validate_diagram()`** → repair loop → **`check_plantuml_syntax()`** → **`render_plantuml()`**.
7. **`evaluate_acceptance()`** writes `acceptance.json` sidecar.
8. If render OK and VLM enabled: **`score_image()`** → three providers → **`verify_scores()`**.
9. Artifact persisted to SQLite; files under `data/artifacts/{id}/`.
10. UI polls **`GET /api/jobs/{id}`** or fetches **`GET /api/artifacts/{id}`**.

**Failure behavior:** Render failure sets S=0 and blocks dataset acceptance. VLM unavailability records `available=false` and skips that model in composite denominator. Repair exhausts after `max_repair_attempts=3`, then attempts safe template fallback.

---

## 7. Implementation Environment

| Component | Verified version / choice |
|-----------|---------------------------|
| Language | Python 3.11+ (venv at `.venv/`) |
| API framework | FastAPI ≥0.115, Uvicorn |
| UI | Streamlit 1.39.0 |
| ORM | SQLModel + SQLite (`aiosqlite`) |
| Data | pandas, pyarrow (parquet) |
| Plotting | plotly, matplotlib |
| PlantUML | JAR v1.2024.7 auto-download to `tools/plantuml.jar` |
| JDK | Bundled JRE under `tools/jdk-17*` or system Java |
| LLM inference | Ollama (dual port), Hugging Face router, OpenAI-compatible |
| Fine-tune inference | MLX on Apple Silicon (`mlx-community/Qwen2.5-0.5B-Instruct-4bit`) |
| VLM (Aya) | Local Transformers + MPS (`CohereLabs/aya-vision-8b`) |
| Tests | pytest ≥8.0 (153 collected) |
| CI | `.github/workflows/ci.yml` |

Configuration strategy: structural defaults in `config.yaml`; secrets and provider toggles in `.env` (see `.env.example`). No secrets are committed.

---

## 8. Detailed Implementation

### 8.1 Requirement Input

- **Files:** `app/schemas.py`, `app/services/code_analysis.py`, `app/services/input_prepare.py`
- **Modes:** `requirement` (free text) or `source_code` (Java/Python/C auto-detected).
- **Behavior:** Long inputs clipped for LLM context (`LLM_REQUIREMENT_CHARS`, `LLM_SOURCE_CODE_CHARS`). Source code may bypass LLM for Stage 1 when structure analysis is sufficient.
- **Guarantee level:** Programmatic language detection; LLM not required for short structured code paths.

### 8.2 Technical Specification Generation

- **Files:** `app/services/orchestration.py` → `generate_technical_spec()`; `app/services/spec_json.py`
- **Prompt:** `prompts/requirement_to_tech_spec.v1.txt` — instructs JSON schema with entities, relationships, packages, components, objects, process_steps.
- **Output:** Prose summary + JSON stored in `TechnicalSpecification.structured_json`.
- **Retry:** On invalid JSON, one LLM retry at temperature 0.1; else grounded fallback.
- **Guarantee level:** Schema validation programmatic; entity extraction from code programmatic when `structure_to_spec_json` used.

### 8.3 Prompt Engineering

- **Registry:** `app/prompts_registry.py` maps logical names to `prompts/*.v1.txt`.
- **Versioning:** Suffix `.v1.txt` on all production prompts.
- **CoT:** PlantUML prompts request `<think>...</think>` before diagram output; stripped by `app/services/cot.py`.
- **VLM:** Strict output format (`SEMANTIC:`, `SCORE:`, etc.) parsed in `uml_pipeline/llm_client.py`.

### 8.4 UML Code Generation

- **Primary path:** `generate_plantuml_code()` in orchestration.
- **Providers:** MLX LoRA (`FinetunedMLXProvider`), Ollama/HF chat model, mock.
- **Temperature:** 0.2 for code generation.
- **Sanitization:** `sanitize_plantuml_output()`, `finalize_plantuml_output()`.

### 8.5 Class Diagram Generation

- **Prompt instructs:** all entities, exact spellings, no Module1 placeholders, inheritance vs association arrows, attributes/methods in class bodies.
- **Programmatic builder:** `plantuml_from_spec()` emits `class Name { ... }` blocks and relationship arrows from JSON.
- **Distinction:** Prompt **instructs** completeness; builder **guarantees** entity coverage when used; LoRA/LLM path may omit entities until fidelity gate replaces output.

### 8.6 Object Diagram Generation

- **Prompt:** `tech_spec_to_object.v1.txt` — object instances, links, state values.
- **Observed issue:** Highest failure rate in DB (79/112 render failures). Validation messages cite invalid relationship arrow syntax and compile failures.
- **Status:** IMPLEMENTED BUT NOT FULLY VERIFIED for production quality.

### 8.7 Component Diagram Generation

- **Prompt:** component names from spec, interfaces, dependencies; no invented `ModuleN`.
- **Render success:** 91.4% (96/105).
- **Mean composite:** 4.65.

### 8.8 Package Diagram Generation

- **Prompt:** nested `package { }`, containment vs `..>` dependency, no self-dependencies.
- **Special handling:** `FAILURE_PACKAGE` repair category; `app/services/package_failures.py` taxonomy.
- **Render success:** 93.1% (95/102); 7 failures classified via analytics.
- **Distinction:** Prompt instructs nesting rules; `validate_diagram()` and acceptance semantic gate partially enforce; known paper limitation area.

### 8.9 PlantUML Rendering

- **File:** `uml_pipeline/render.py`
- **Local path:** Java + JAR → PNG; Graphviz optional (Smetana layout fallback when dot missing).
- **Remote fallback:** PlantUML HTTP server when local fails (`PLANTUML_REMOTE=true`).
- **Gate:** Failed render → S=0, no dataset acceptance.

### 8.10 Multimodal Validation

- **File:** `app/services/orchestration.py` → `score_image()`
- **Models:** Built by `build_vlm_providers()` — Qwen on Ollama :11435, LLaMA-Vision on :11434, Aya via local Transformers.
- **Prompt:** Four criteria 0–6; final `SCORE:` line parsed.
- **Unavailable model:** `score=None`, excluded from composite sum; logged in `ModelScore.available`.

### 8.11 Weighted Composite Scoring

See Section 9.

### 8.12 Dataset Generation

- **Legacy CLI:** `uml_pipeline/pipeline.py` → `run_generation_batch()`
- **Application batch:** `POST /api/generate/batch` — sample requirements × diagram types.
- **Import:** `scripts/download_datasets.py` → `data/uml_design_dataset.parquet` (8000 rows).
- **Export:** `/api/export/dataset` filters `dataset_accepted` artifacts.

### 8.13 Streamlit Application

See Section 14.

### 8.14 Analysis and Visualization

- **Backend:** `app/services/analytics.py` — summary, distributions, export.
- **UI:** `ui/pages/6_Analytics.py` — metrics, histograms, adaptation stats, export links.
- **Package failures:** `package_failure_report()` for taxonomy counts.

---

## 9. Mathematical Scoring Method

### 9.1 Variables

| Symbol | Meaning |
|--------|---------|
| \(i\) | Artifact index |
| \(j \in \{1,2,3\}\) | VLM index (Qwen, LLaMA-Vision, Aya) |
| \(s_{i,j}\) | Integer score 0–6 from VLM \(j\) on artifact \(i\) |
| \(w_j\) | MMMU weight: \(w_1=53.1\), \(w_2=50.7\), \(w_3=39.9\) |
| \(S_i\) | Weighted composite score |
| \(\tau\) | Majority threshold (= 4.0) |
| \(v_{i,j}\) | Vote indicator \(\mathbb{1}[s_{i,j} \geq \tau]\) |
| \(A_i\) | Majority acceptance |
| \(D_i\) | Dataset inclusion flag |

### 9.2 Implemented formulas

**Render gate:**

\[
S_i = 0 \quad \text{if render fails}
\]

**Weighted composite (render OK):**

\[
S_i = \frac{\sum_{j} w_j \cdot s_{i,j}}{\sum_{j} w_j}
\]

Summation over models with numeric scores (None skipped). Zeros count.

**Majority vote:**

\[
A_i = 1 \iff \sum_j v_{i,j} \geq 2 \quad \text{where} \quad v_{i,j} = \mathbb{1}[s_{i,j} \geq 4]
\]

**Dataset gate:**

\[
D_i = 1 \iff \text{render OK} \land A_i = 1 \land S_i \geq 3.0
\]

**Implementation:** `app/services/scoring.py` — `paper_composite()`, `majority_vote_accept()`, `dataset_entry_accepted()`.

### 9.3 Rationale for ensemble (research interpretation)

Single VLMs exhibit variable calibration on UML diagrams. MMMU-weighted averaging assigns higher influence to models with stronger general multimodal reasoning benchmarks; majority voting reduces false acceptance from any one overly lenient or harsh model. **This is research motivation; local ablation comparing 1 vs 3 models is not yet evidenced in the repository.**

---

## 10. End-to-End Example (Repository Artifact)

**Artifact ID 469** — verified complete trace in `data/artifacts/469/`.

| Stage | Content |
|-------|---------|
| **Input** | C source code defining `LineItem`, `Order`, `Invoice` structs and functions |
| **Diagram type** | class |
| **Technical spec** | JSON entities: LineItem, Order, Invoice; relationship Invoice→Order |
| **PlantUML** | `@startuml` with monochrome skinparam, three classes, associations (file `c3d22c062d139b5b.puml`) |
| **Render status** | success (`diagram.png` present) |
| **Acceptance** | All gates passed; semantic recall 1.0 (`acceptance.json`) |
| **VLM scores** | Qwen=6, LLaMA-Vision=5, Aya=5 |
| **Composite S** | 5.37 |
| **Majority A** | 1 (all scores ≥ 4) |
| **Dataset accepted** | 1 |

---

## 11. Experimental Setup

### 11.1 Verified experiments

| Experiment | Description | Evidence |
|------------|-------------|----------|
| Unit/integration tests | 153 pytest cases, mock providers | `tests/`, CI workflow |
| Golden acceptance | 6 fixtures, full pipeline | `reports/acceptance_eval.md` |
| Benchmark acceptance | 200 NL × 4 types, deterministic gates | same |
| Negative controls | 5 invalid cases must reject | same |
| Interactive/batch generation | 470 SQLite artifacts | `data/uml_app.db` |
| HF dataset import | 8000 rows, 3000 VLM-scored | `data/uml_design_dataset.parquet` |

### 11.2 Production configuration (documented, not re-run for this report)

Mac Studio M1 Ultra, dual Ollama, MLX LoRA adapter `uml-plantuml-lora-sourcecode-30k`, local Aya — see `docs/SYSTEM_DESIGN.md`.

### 11.3 Not verified locally

- Paper-scale n=8000 **live generation** through the application stack with full VLM scoring on all types.
- Human evaluation study.
- Correlation / inter-rater statistics in `paper/corrected_paper (1).tex`.

---

## 12. Results Obtained So Far

### 12.1 Application database (A — reproduced by implementation)

**N = 470 artifacts** (2026-08-28)

| Diagram type | n | Render success | Mean S | Majority accepted | Dataset accepted |
|--------------|---|----------------|--------|-------------------|------------------|
| class | 151 | 139 (92.1%) | 4.47 | 120 (79.5%) | 113 (74.8%) |
| component | 105 | 96 (91.4%) | 4.65 | 96 (91.4%) | 88 (83.8%) |
| package | 102 | 95 (93.1%) | 4.69 | 92 (90.2%) | 89 (87.3%) |
| object | 112 | 33 (29.5%) | 1.34 | 27 (24.1%) | 21 (18.8%) |
| **Total** | **470** | **363 (77.2%)** | **3.81** | **335 (71.3%)** | **311 (66.2%)** |

Composite histogram: 0→108, 1→2, 2→16, 3→1, 4→33, 5→230, 6→80.

**Repair stats:** 243 repair attempts, 156 successes (64.2%).

**Input modes:** requirement 340, source_code 130.

**Code model usage:** spec-builder 416; finetuned adapters 32 combined; mock-local 22.

### 12.2 Per-VLM score distribution (available scores in ModelScore table)

| Model | Score 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|-------|---------|---|---|---|---|---|---|
| qwen25vl3b | 102 | 0 | 0 | 21 | 1 | 78 | 262 |
| llama32vl11b | 122 | 1 | 0 | 7 | 131 | 138 | 65 |
| aya_vision_8b | 118 | 16 | 42 | 21 | 40 | 105 | 122 |

Mean available score: 3.82 (all models pooled).

### 12.3 Acceptance evaluation (deterministic, no VLM)

| Suite | Result |
|-------|--------|
| Golden regression (6) | 6/6 accepted |
| Benchmark (200) | 200/200 accepted |
| Negative controls (5) | 5/5 rejected (TNR=1.0) |

### 12.4 Imported parquet dataset (B — external benchmark data)

- 8000 rows: 5000 class, 1000 each object/component/package.
- 3000 rows with composite `scores` (non-class types only).
- Mean composite (scored rows): 3.76.
- Per-model means on scored rows: Qwen 3.74, LLaMA 4.08, Aya 2.18.

### 12.5 Paper manuscript claims (C — not reproduced locally)

The LaTeX draft reports render rate 95.7%, human correlation r=0.71, per-type correlation tables, and n=8000 generated dataset statistics. **These values are reported in the reference manuscript only; they are not verified from the current SQLite database or local artifact store.**

---

## 13. Failure Analysis

### 13.1 Object diagrams (critical)

- **79/112 render failures** (70.5% failure rate).
- Sample validation messages: invalid worded relationship arrows; compile/render false with semantic OK.
- Likely causes: LoRA/object prompt syntax mismatch; insufficient repair templates for object notation; generator choice (`adaptation` logs show LoRA-first for object with failed strategies).

### 13.2 Package diagrams

- **7/102 render failures** — manageable but academically important (containment vs dependency).
- Taxonomy implemented: `empty_or_incomplete`, `missing_package_block`, `unbalanced_braces`, `self_dependency`, `wrong_diagram_type`.

### 13.3 Overall render failures (101 artifacts)

Includes 6 pending and environmental Java/runtime errors in early artifacts.

### 13.4 VLM zeros

High count of score=0 entries (especially Qwen 102, LLaMA 122) often correlates with render failures (S forced to 0) or unavailable/scoring errors.

### 13.5 Spec-builder dominance

416/470 artifacts used deterministic builder rather than LoRA — indicates fallback path frequently chosen; may limit evaluation of fine-tuned model quality in logged runs.

---

## 14. Application Demonstration

### 14.1 Pages

| # | Page | Function |
|---|------|----------|
| 0 | Home (`streamlit_app.py`) | Dashboard, API health, quick stats |
| 1 | Dashboard | Project overview |
| 2 | Single Generation | Primary demo workflow |
| 3 | Batch Generation | Background jobs, 50×4 default |
| 4 | Generated Diagrams | Gallery + downloads |
| 5 | Human Evaluation | Rubric sliders → POST review |
| 6 | Analytics | Distributions, export links |
| 7 | Settings | Health, provider info |
| 8 | System Design | Architecture reference |

### 14.2 Single Generation workflow

- Input: requirement text or source code; diagram type; optional "Score with VLMs" toggle.
- Output panels: technical spec, PlantUML, rendered image, per-model scores, composite, gates, repair/adaptation notes.
- Background job polling via `ui/jobs.py`.

### 14.3 Suggested screenshots for Dr. Zhao

1. **Figure 1** — Application home / dashboard with live artifact counts  
2. **Figure 2** — Requirement input (Single Generation)  
3. **Figure 3** — Technical specification JSON/prose  
4. **Figure 4** — Generated PlantUML code panel  
5. **Figure 5** — Rendered class diagram (e.g., artifact 469)  
6. **Figure 6** — Multimodal validation per-model scores  
7. **Figure 7** — Composite S + majority/dataset gate indicators  
8. **Figure 8** — Analytics histogram + export links  
9. **Figure 9** — Batch generation job progress (optional)  
10. **Figure 10** — System Design page (optional)  

---

## 15. Testing and Verification

| Category | Count / status | Location |
|----------|----------------|----------|
| Unit tests | scoring, spec_json, validators, vlm parse, etc. | `tests/test_*.py` |
| API tests | generate, artifacts, security | `tests/test_api.py` |
| Acceptance tests | golden + benchmark | `tests/test_acceptance.py` |
| Orchestration fallback | LoRA/builder paths | `tests/test_orchestration_fallback.py` |
| Package failures | taxonomy | `tests/test_package_failures.py` |
| **Total collected** | **153** | `pytest --collect-only` |
| E2E smoke | scripted | `scripts/smoke_test.py`, README `make smoke` |
| Human validation | 0 reviews | NOT VERIFIED |

Testing is **substantial for software modules** but **does not constitute full research validation** (no human study, no large-n live VLM batch archived).

---

## 16. Current Project Status

| Component | Status | Evidence | Remaining Work |
|-----------|--------|----------|----------------|
| Stage 1 spec generation | COMPLETE | orchestration, 470 specs | Optional cloud Llama comparison |
| Stage 2 PlantUML | COMPLETE | prompts, LoRA, builder | Improve LoRA utilization; object syntax |
| PlantUML render | COMPLETE | 363 successes | Object diagram reliability |
| Repair loop | COMPLETE | 243 attempts logged | Tune object/package strategies |
| VLM ensemble | COMPLETE | ModelScore rows | Ablation study |
| Scoring gates | COMPLETE | scoring.py | Document edge cases |
| SQLite persistence | COMPLETE | uml_app.db | Optional Postgres |
| FastAPI | COMPLETE | routers, OpenAPI | — |
| Streamlit UI | COMPLETE | 8 pages | Capture screenshots |
| Batch generation | COMPLETE | 138 jobs | Paper-scale archived run |
| Dataset export | COMPLETE | export API | — |
| Human evaluation | PARTIAL | UI only, 0 reviews | Run study |
| Analytics/correlation | PARTIAL | code ready | Needs human data |
| Training/LoRA | COMPLETE | models/, scripts | Evaluation vs DeepSeek |
| Deployment | COMPLETE | docs, LaunchAgent scripts | — |
| Paper-scale results | NOT VERIFIED | paper/ only | Reproduce or revise claims |

---

## 17. Contributions of the Work

### 17.1 Research contribution

- Implemented multimodal verification pipeline with MMMU-weighted ensemble and dual-gate dataset curation matching thesis methodology.
- Integrated deterministic acceptance gates (semantic traceability, UML rules) **before** VLM scoring — extending paper pipeline with engineering validation layers.
- Documented pragmatic model stand-ins (0.5B LoRA, local Aya) for reproducible Apple Silicon deployment.

### 17.2 Engineering contribution

- Full-stack application (FastAPI + Streamlit + SQLite) with batch jobs, repair/adaptation memory, export, remote agent, tunnels, CI.
- Provider abstraction supporting mock, Ollama dual-host, MLX, HF, OpenAI-compatible backends.
- 153 automated tests; acceptance benchmark harness (200/200).

### 17.3 Practical contribution

- Runnable demo for advisors (`make run`).
- Source-code-to-UML path for Java/Python/C.
- Reviewer package and system design documentation for handoff.

**Novelty note:** Core methodology aligns with the thesis proposal and reference paper; primary novelty claim should remain **multimodal verified dataset generation** rather than UML generation alone (well-studied). Do not overclaim without completed human evaluation.

---

## 18. Current Limitations

1. **Object diagram reliability** — 29.5% render success undermines four-type claims until fixed.
2. **Human evaluation absent** — no correlation validation.
3. **Model stand-ins** — DeepSeek-32B not locally deployed; LoRA 0.5B substitute.
4. **LLM hallucination** — prompt-instructed correctness; fidelity gate only on builder replacement path.
5. **VLM calibration** — Aya mean lower on imported parquet (2.18); ensemble depends on model availability.
6. **Latency/cost** — three VLMs per artifact; interactive mode can skip VLMs.
7. **Package semantics** — nesting vs dependency remains error-prone (paper-aligned limitation).
8. **Figure assets** — `output/figures/` and `paper/figures/` empty in repo.
9. **Reproducibility** — production depends on local Ollama versions, MLX, HF model licenses.

---

## 19. Remaining Work Before Thesis Completion

### HIGH

1. Diagnose and fix object-diagram generation/render pipeline.
2. Conduct human evaluation (≥30 artifacts, multiple reviewers).
3. Execute one archived paper-scale batch with VLMs enabled; export + document.
4. Reconcile paper numerical claims with verified local results (revise or reproduce).

### MEDIUM

5. Increase LoRA primary usage vs spec-builder fallback.
6. Generate publication figures from analytics.
7. Optional DeepSeek-32B cloud comparison for Stage 2.

### OPTIONAL

8. Expose flowchart type on API.
9. Postgres deployment for multi-user demos.

---

## 20. Proposed Next Research Steps

1. Object-diagram failure taxonomy from DB + targeted prompt/repair fixes.  
2. Human study design → IRB if required → collect reviews via Streamlit.  
3. Compute Pearson/Spearman correlation human vs S once n sufficient.  
4. Ablation: single VLM vs ensemble on fixed artifact sample.  
5. Submit verified methodology + local results to Overleaf; mark paper-scale tables as future work or re-run.

---

## 21. Conclusion

The repository delivers a **thesis-scale software artifact**: a working research pipeline, demonstration application, persistence layer, multimodal scoring, batch dataset tooling, and comprehensive documentation. Verified local generation produced **470 artifacts** with strong class/component/package performance and a **clear object-diagram weakness**. Deterministic acceptance testing passes **200/200** benchmark cases, and **153** automated tests cover core modules.

What remains for thesis **research completion** is primarily **empirical validation**—human evaluation, large-n reproducible experiments, and alignment between the LaTeX draft's numerical claims and evidence archived in the repository. The implementation readiness for advisor review and demo is **high**; publication readiness requires closing the experimental gaps identified above.

**Implementation readiness estimate: 78/100.**

---

## 22. Appendix A — Repository Structure

```text
app/                 FastAPI application, services, providers, routers
uml_pipeline/        Research pipeline (render, scoring, legacy batch)
ui/                  Streamlit multipage UI
prompts/             Versioned LLM/VLM prompt templates
models/              MLX LoRA adapter checkpoints
data/                SQLite, artifacts, training corpora, parquet
scripts/             Training, deploy, eval, smoke tests
tests/               pytest suite + golden fixtures
docs/                Architecture, deploy, gap analysis, this report
paper/               LaTeX manuscript snapshot
reports/             Acceptance eval, publication report, reviewer bundle
tools/               plantuml.jar, bundled JDK
.github/workflows/   CI (pytest)
```

---

## 23. Appendix B — Important Source Files

| Purpose | File |
|---------|------|
| Main orchestration | `app/services/orchestration.py` |
| Scoring math | `app/services/scoring.py`, `uml_pipeline/scoring.py` |
| PlantUML render | `uml_pipeline/render.py` |
| Spec JSON | `app/services/spec_json.py` |
| Deterministic UML builder | `app/services/plantuml_from_spec.py` |
| Validation | `app/services/plantuml_validate.py` |
| Repair | `app/services/repair.py` |
| Acceptance gates | `app/services/acceptance.py` |
| Provider factory | `app/providers/factory.py` |
| MLX LoRA | `app/providers/finetuned_provider.py` |
| Local Aya VLM | `app/providers/aya_local_provider.py` |
| LLM/VLM client | `uml_pipeline/llm_client.py` |
| Data models | `app/models.py` |
| Analytics | `app/services/analytics.py` |
| Settings | `app/settings.py`, `config.yaml` |

---

## 24. Appendix C — Configuration and Run Instructions

```bash
git clone https://github.com/dipak5501/uml-generation-pipeline.git
cd uml-generation-pipeline
make install
cp .env.example .env          # MOCK_PROVIDERS=true for offline demo
make run                      # API :8000 + UI :8501
make test                     # 153 pytest tests
```

**Live stack (production-like):**

```bash
# .env
MOCK_PROVIDERS=false
USE_OLLAMA=true
USE_FINETUNED_CODE=true
FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-sourcecode-30k
VLM_AYA_BACKEND=local
```

See `docs/SYSTEM_DESIGN.md`, `docs/deploy.md`, `README.md`.

---

## 25. Appendix D — Suggested Figures/Screenshots

| Figure | Capture from |
|--------|--------------|
| Home dashboard | Streamlit landing / `1_Dashboard.py` |
| Requirement input | `2_Single_Generation.py` |
| Technical specification | Generation results panel |
| PlantUML code | Same panel (code block) |
| Rendered diagram | `diagram.png` or gallery |
| VLM scores | Model score table in UI |
| Composite + gates | Score summary footer |
| Analytics | `6_Analytics.py` histogram |
| Batch job | `3_Batch_Generation.py` progress |
| System architecture | `8_System_Design.py` or SYSTEM_DESIGN.md export |

Example static artifact for paper: **`data/artifacts/469/diagram.png`** with trace in Section 10.

---

*Evidence matrix: [`IMPLEMENTATION_EVIDENCE_MATRIX.md`](IMPLEMENTATION_EVIDENCE_MATRIX.md)*  
*Advisor summary: [`DR_ZHAO_PROGRESS_SUMMARY.md`](DR_ZHAO_PROGRESS_SUMMARY.md)*  
*Overleaf handoff: [`OVERLEAF_PAPER_HANDOFF.md`](OVERLEAF_PAPER_HANDOFF.md)*
