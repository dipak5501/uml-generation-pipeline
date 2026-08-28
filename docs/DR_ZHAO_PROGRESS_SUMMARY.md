# Thesis Progress Summary for Dr. Zhao

**Student:** Dipak Yadav  
**Advisor:** Dr. Yutong Zhao  
**Project:** AI-Driven UML Generation and Multimodal Verification  
**Repository:** [github.com/dipak5501/uml-generation-pipeline](https://github.com/dipak5501/uml-generation-pipeline)  
**Date:** 2026-08-28

---

## Thesis Objective

Build and demonstrate an end-to-end system that converts natural-language software requirements (and source code) into design-phase UML diagrams—Class, Object, Component, and Package—using large language models for specification and PlantUML generation, PlantUML for rendering, and a three-model vision-language ensemble for automated quality verification. The system should support dataset generation, persistence, analytics, and a working demonstration application suitable for thesis evaluation and eventual publication.

---

## What Has Been Implemented

A **complete full-stack application** is implemented and running:

| Layer | Implementation |
|-------|----------------|
| **Backend** | FastAPI (`app/`) with REST API, async batch jobs, SQLite persistence |
| **Research pipeline** | `uml_pipeline/` — render, scoring, legacy batch generation |
| **UI** | Streamlit multipage app (`ui/`) — 8 pages including generate, batch, gallery, analytics |
| **Providers** | Mock (offline), Ollama (dual-host), MLX LoRA, local Aya-Vision, Hugging Face, OpenAI-compatible |
| **Validation** | Multi-gate acceptance: syntax → compile → render → UML rules → semantic traceability |
| **Scoring** | Three VLMs with MMMU-weighted composite **S** and majority-vote gate **A** |
| **Deployment** | Mac Studio production stack (documented); Docker; Cloudflare tunnels |

**Verified on-disk evidence (2026-08-28):**

- **470** generated artifacts in SQLite (`data/uml_app.db`)
- **363** successful renders (77.2%); **311** dataset-accepted (66.2%)
- Mean composite score **S = 3.81** (range 0–6)
- **153** automated tests passing (mock mode)
- **8000-row** imported Hugging Face benchmark parquet (`data/uml_design_dataset.parquet`); **3000** rows with VLM scores

---

## Architecture (Concise)

```text
Requirement / Source Code
        ↓
Stage 1: Technical Specification (JSON + prose)
        LLM: Llama-3.2-1B (Ollama llama3.2:1b in production)
        ↓
Stage 2: PlantUML Generation
        MLX LoRA Qwen2.5-0.5B (primary when enabled)
        + spec-builder fallback (deterministic from JSON)
        + repair loop (≤3 iterations)
        ↓
PlantUML Render Gate (local JDK + plantuml.jar)
        ↓
Stage 3: Multimodal Verification
    Qwen2.5-VL-3B  |  LLaMA-3.2-Vision-11B  |  Aya-Vision-8B
        ↓
Weighted Composite S + Majority Vote A (τ=4)
        ↓
Dataset Gate (A=1 and S≥3) → SQLite + Export
```

Core orchestration: `app/services/orchestration.py` → `run_single_generation`.

---

## Models and Tools

| Stage | Paper Model | Production Default | Config |
|-------|-------------|-------------------|--------|
| Spec | Llama-3.2-1B-Instruct | Ollama `llama3.2:1b` | `.env` `SPEC_MODEL` |
| PlantUML | DeepSeek-R1-Distill-Qwen-32B | MLX LoRA on Qwen2.5-0.5B-4bit | `USE_FINETUNED_CODE`, `FINETUNED_ADAPTER_PATH` |
| VLM #1 | Qwen2.5-VL-3B (w=53.1) | Ollama :11435 | `VLM_MODELS` |
| VLM #2 | LLaMA-3.2-Vision-11B (w=50.7) | Ollama :11434 | `VLM_MODELS` |
| VLM #3 | Aya-Vision-8B (w=39.9) | Local Transformers (MPS) | `VLM_AYA_BACKEND=local` |
| Rendering | PlantUML + JDK | `tools/plantuml.jar` | `PLANTUML_PREFER_LOCAL` |

**Documented stand-ins:** DeepSeek-32B is not run locally; a fine-tuned 0.5B LoRA adapter (`models/uml-plantuml-lora-sourcecode-30k`) serves Stage 2. Aya is not available on Ollama; local Transformers loads the paper-exact model.

---

## Working Application

The Streamlit demo connects to the FastAPI backend and exposes:

1. **Dashboard** — live stats, provider health  
2. **Single Generation** — requirement or code → spec → PlantUML → image → scores  
3. **Batch Generation** — up to 200 artifacts per run (50 samples × 4 types)  
4. **Generated Diagrams** — historical gallery with downloads  
5. **Human Evaluation** — rubric-based review form (UI ready; **0 reviews collected yet**)  
6. **Analytics** — score distributions, repair stats, dataset export links  
7. **Settings** — health check, provider summary  
8. **System Design** — architecture overview page  

Run locally: `make run` (API :8000 + UI :8501).

---

## Current Results (Repository-Verified Only)

### Application database (470 artifacts)

| Diagram Type | Count | Render Success | Mean S | Dataset Accepted |
|--------------|-------|----------------|--------|------------------|
| Class | 151 | 139 (92.1%) | 4.47 | 113 (74.8%) |
| Component | 105 | 96 (91.4%) | 4.65 | 88 (83.8%) |
| Package | 102 | 95 (93.1%) | 4.69 | 89 (87.3%) |
| Object | 112 | 33 (29.5%) | 1.34 | 21 (18.8%) |
| **Total** | **470** | **363 (77.2%)** | **3.81** | **311 (66.2%)** |

**Notable finding:** Object diagrams have substantially lower render success and composite scores than the other three types. Failure messages frequently cite invalid relationship arrows and compile/render errors.

### Deterministic acceptance evaluation (no VLM)

From `reports/acceptance_eval.md`:

- Golden regression: **6/6** full pipeline accepted  
- Benchmark (200 cases): **200/200** accepted  
- Negative controls: **5/5** correctly rejected  

### Imported benchmark parquet (8000 rows)

- 5000 class + 1000 each object/component/package (Hugging Face UMLCode datasets)  
- **3000 rows** have VLM scores (1000 per non-class type); class rows are unscored in this file  
- Mean composite on scored rows: **3.76**

### Paper claims NOT reproduced locally

The LaTeX draft (`paper/`) reports n=8000 generation, render rate 95.7%, human correlation r=0.71, and per-type correlation tables. **These are not verified from the current SQLite database or artifact store.** See full report Section 12 for explicit separation.

---

## Remaining Work

| Priority | Item |
|----------|------|
| **HIGH** | Fix object-diagram render/validation failures (29.5% success vs ~92% for other types) |
| **HIGH** | Collect human evaluation data (UI exists; 0 reviews in DB) |
| **HIGH** | Run controlled batch experiment at paper scale with live VLMs; export reproducible tables |
| **MEDIUM** | Increase LoRA usage vs spec-builder fallback (416/470 artifacts used builder, not LoRA) |
| **MEDIUM** | Generate publication figures from analytics export |
| **MEDIUM** | Document correlation analysis once human reviews exist |
| **OPTIONAL** | Paper-exact DeepSeek-32B via cloud GPU for Stage 2 comparison |
| **OPTIONAL** | Flowchart diagram type on API (present in training corpus only) |

---

## Proposed Next Steps

1. **Share this report and demo URL** with Dr. Zhao; capture Streamlit screenshots (see Appendix D in full report).  
2. **Prioritize object-diagram debugging** — inspect failure taxonomy, repair strategies, and LoRA vs builder routing.  
3. **Design human evaluation protocol** — recruit 2–3 reviewers; target n≥30 artifacts across diagram types.  
4. **Run one reproducible batch** (e.g., 50×4=200 with VLMs enabled) and archive export + git tag.  
5. **Transfer verified methodology sections** into Overleaf once Dr. Zhao shares the project (handoff doc prepared: `docs/OVERLEAF_PAPER_HANDOFF.md`).

---

## Conclusion

The thesis implementation is **functionally complete** as an end-to-end application: generation, rendering, multimodal scoring, persistence, batch jobs, analytics, and a Streamlit demo are all implemented and evidenced in the repository. The primary gaps for publication readiness are **experimental completion** (large-n reproducible runs, human evaluation, object-diagram reliability) rather than missing software modules.

**Estimated implementation readiness: 78/100** (see full report for rationale).

---

*Full technical report: [`docs/DR_ZHAO_THESIS_PROGRESS_REPORT.md`](DR_ZHAO_THESIS_PROGRESS_REPORT.md)*  
*Evidence matrix: [`docs/IMPLEMENTATION_EVIDENCE_MATRIX.md`](IMPLEMENTATION_EVIDENCE_MATRIX.md)*
