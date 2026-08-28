# Overleaf / Paper Handoff Notes

**For:** Dr. Yutong Zhao → shared Overleaf project  
**Student:** Dipak Yadav  
**Paper working title:** *Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design*  
**Repository:** [github.com/dipak5501/uml-generation-pipeline](https://github.com/dipak5501/uml-generation-pipeline)  
**Date:** 2026-08-28

> **Rule applied:** Only facts supported by repository evidence are marked **AVAILABLE**. Items marked **PAPER ONLY** or **MISSING** must not be copied into the manuscript without new experiments.

---

## 1. Candidate Paper Title

*Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design*

(Confirmed in `README.md`, `paper/main.tex`, `config.yaml` author block.)

---

## 2. Abstract Facts / Bullet Points (Evidence-Checked)

**Safe to include (implementation verified):**

- End-to-end pipeline: natural-language requirement or source code → structured technical specification → PlantUML → rendered PNG → three-VLM ensemble scoring.
- Four structural UML types exposed in the application API: class, object, component, package.
- Multimodal verification uses Qwen2.5-VL-3B, LLaMA-3.2-Vision-11B, and Aya-Vision-8B with MMMU-derived weights (53.1, 50.7, 39.9).
- Dual acceptance signal: weighted composite score **S** and majority-vote gate **A** (threshold τ=4, ≥2 of 3 models); dataset inclusion requires render success, **A=1**, and **S≥3**.
- Render failure forces **S=0** regardless of VLM output.
- Full artifact traces persisted (requirement, spec, PlantUML, image, per-model scores, repair history) in SQLite with export to JSONL/CSV/Parquet.
- **MLX LoRA fine-tuning** on staged corpora: **50k → 100k (~102k rows) → 200k (~224k rows) → 30k source-code** (Java/Python/C); production adapter `uml-plantuml-lora-sourcecode-30k` (6k iters, warm-started from 200k).
- FastAPI + Streamlit demonstration application deployed on local Apple Silicon hardware with documented production configuration.

**Do NOT assert without new experiments:**

- n=8,000 locally generated dataset (parquet import exists; local generation count is 470).
- Render success rate 95.7% (local: 77.2% overall; object type 29.5%).
- Human–automated correlation r=0.71 or per-type correlation tables (0 human reviews in DB).

---

## 3. Introduction — Contribution Bullets

| Contribution | Evidence | Status |
|--------------|----------|--------|
| Dual-LLM pipeline (spec + PlantUML) with CoT and repair | `orchestration.py`, `prompts/` | AVAILABLE |
| Multimodal verification ensemble with MMMU-weighted scoring | `scoring.py`, `vlm_scoring.v1.txt` | AVAILABLE |
| Majority-vote gate combined with composite threshold for dataset curation | `scoring.py` | AVAILABLE |
| Four diagram-type support with package-specific validation/repair | `package_failures.py`, package prompts | AVAILABLE |
| Source-code reverse engineering path (Java/Python/C) | `code_analysis.py` | AVAILABLE |
| Open application + reproducible export | GitHub repo, export API | AVAILABLE |
| Large-scale empirical evaluation with human correlation | Paper LaTeX | PAPER ONLY / MISSING locally |

Suggested framing: emphasize **system + methodology implementation**; treat large-n empirical claims as **planned or in-progress** unless re-run.

---

## 4. Methodology (Transfer-Ready)

### 4.1 Stage 1 — Technical Specification

- Input: requirement text or source code; diagram type selected.
- LLM prompt: `prompts/requirement_to_tech_spec.v1.txt` or `code_to_tech_spec.v1.txt`.
- Output: JSON schema (entities, relationships, packages, components, objects) + prose summary.
- Validation: `ensure_valid_spec()` with grounding from source structure when LLM JSON fails.

### 4.2 Stage 2 — PlantUML Generation

- Primary: MLX LoRA fine-tuned Qwen2.5-0.5B (`models/uml-plantuml-lora-sourcecode-30k`) when enabled.
- Fallback chain: base LLM → deterministic `plantuml_from_spec` → safe template.
- Diagram-type prompts: `prompts/tech_spec_to_{class,object,component,package}.v1.txt`.
- Repair loop: up to 3 iterations (`repair_plantuml`) categorized by syntax, compile, render, package, structure failures.

### 4.3 Render Gate

- Local PlantUML 1.2024.7 JAR + JDK; optional remote HTTP fallback.
- Black-and-white policy enforced in sanitizer and training corpus.

### 4.4 Stage 3 — Multimodal Verification

- Scoring prompt: `prompts/vlm_scoring.v1.txt` (0–6 rubric on semantic, structural, syntactic, coherence).
- Models and weights from `config.yaml` / `app/settings.py`.

### 4.5 Scoring Formulas (LaTeX-ready)

**Weighted composite (render OK):**

\[
S_i = \frac{\sum_{j=1}^{3} w_j \cdot s_{i,j}}{\sum_{j=1}^{3} w_j}
\]

where \(s_{i,j} \in \{0,\ldots,6\}\), weights \(w = (53.1, 50.7, 39.9)\), unavailable models skipped. If render fails: \(S_i = 0\).

**Majority vote:**

\[
v_{i,j} = \mathbb{1}[s_{i,j} \geq \tau], \quad A_i = \mathbb{1}\left[\sum_j v_{i,j} \geq 2\right], \quad \tau = 4
\]

**Dataset inclusion:**

\[
D_i = \mathbb{1}[A_i = 1 \land S_i \geq 3.0 \land \text{render OK}]
\]

Implementation: `app/services/scoring.py`.

---

## 5. System Architecture

Use diagram from `docs/SYSTEM_DESIGN.md` (Mermaid + ASCII). Layers:

- Clients: Streamlit, CLI, public tunnel
- FastAPI + orchestration + in-process job pool
- Provider factory (mock, Ollama, MLX, Aya, HF)
- Validation gates + VLM ensemble
- SQLite + `data/artifacts/`

---

## 6. Experimental Setup (What Can Be Described Now)

| Element | Description | Verified? |
|---------|-------------|-----------|
| Hardware | Mac Studio M1 Ultra, 128 GB (documented in SYSTEM_DESIGN) | Documented |
| Software | Python 3.11+, FastAPI, Streamlit, PlantUML, Ollama dual-host | Yes |
| Test suite | 153 pytest tests, mock providers | Yes |
| Acceptance benchmark | 200 NL samples × 4 types, deterministic gates | Yes (`acceptance_eval.md`) |
| Live generation DB | 470 artifacts, mixed requirement/code input | Yes |
| LoRA fine-tuning (50k/100k/200k/30k source) | Scripts, logs, adapters | AVAILABLE |
| HF evaluation import (8000 rows, not training) | `data/uml_design_dataset.parquet` | AVAILABLE |
| Paper-scale live run | 8000 generated + scored on production stack | NOT VERIFIED locally |

---

## 7. Results Available for Tables/Figures

### Table A — Local application artifacts (n=470)

| Type | n | Render OK | Mean S | Dataset OK |
|------|---|-----------|--------|------------|
| class | 151 | 92.1% | 4.47 | 74.8% |
| component | 105 | 91.4% | 4.65 | 83.8% |
| package | 102 | 93.1% | 4.69 | 87.3% |
| object | 112 | 29.5% | 1.34 | 18.8% |
| **All** | **470** | **77.2%** | **3.81** | **66.2%** |

Source: SQLite query on `data/uml_app.db`, 2026-08-28.

### Table B — Composite score histogram (local n=470)

| Score bucket | Count |
|--------------|-------|
| 0 | 108 |
| 1 | 2 |
| 2 | 16 |
| 3 | 1 |
| 4 | 33 |
| 5 | 230 |
| 6 | 80 |

### Table C — Per-VLM score distribution (available model scores in DB)

Aggregated from `modelscore` table; see full report Section 12.

### Table D — Acceptance evaluation (deterministic, no VLM)

| Suite | Result |
|-------|--------|
| Golden (6) | 6/6 accepted |
| Benchmark (200) | 200/200 accepted |
| Negative controls (5) | 5/5 rejected |

Source: `reports/acceptance_eval.md`.

### Table E — Imported parquet VLM stats (n=3000 scored)

| Model | Mean score |
|-------|------------|
| qwen25vl3b | 3.74 |
| llama32vl11b | 4.08 |
| aya_vision_8b | 2.18 |
| composite | 3.76 |

Source: `data/uml_design_dataset.parquet`.

---

## 8. Figures Available

| Figure | Source | Status |
|--------|--------|--------|
| Architecture diagram | `docs/SYSTEM_DESIGN.md` Mermaid | AVAILABLE (export to PDF/SVG) |
| Streamlit screenshots | Running app | **TO CAPTURE** (see list below) |
| Example UML PNG | `data/artifacts/469/diagram.png` | AVAILABLE |
| Score distribution charts | Analytics page / export | AVAILABLE from live app |
| Paper figures | `paper/figures/` | **EMPTY** in repo |
| `output/figures/` | Empty | NOT AVAILABLE |

**Screenshots to capture before Overleaf transfer:**

1. Dashboard with live stats  
2. Single Generation — requirement input  
3. Technical specification panel  
4. PlantUML code display  
5. Rendered class diagram  
6. Per-VLM scores  
7. Composite + majority/dataset gates  
8. Analytics page with histogram  
9. Batch job progress  
10. System Design page  

---

## 9. Limitations (Evidence-Based)

- Object diagram render success far below other types (29.5% vs ~92%).
- Stage 2 often uses deterministic spec-builder rather than LoRA (416/470 artifacts).
- DeepSeek-32B not run locally; 0.5B LoRA is a documented stand-in.
- Human evaluation UI exists but **zero reviews** collected; no correlation analysis possible yet.
- VLM inference latency and cost limit interactive scoring (optional skip in UI).
- LLM/VLM hallucination and semantic correctness not guaranteed—prompt-instructed, not formally verified except on builder/fidelity paths.
- Package nesting/containment vs dependency remains a known failure category (7 package render failures locally).

---

## 10. Future Work (For Paper Discussion Section)

- Object-diagram reliability improvements  
- Human evaluation study (target n≥30–50 per type)  
- Reproducible paper-scale batch with archived export  
- Ablation: LoRA vs spec-builder vs base LLM  
- Optional cloud DeepSeek-32B comparison  
- Correlation and inter-rater reliability analysis  

---

## 11. Repository / Code Availability

- **Public GitHub:** https://github.com/dipak5501/uml-generation-pipeline  
- **License:** MIT  
- **Run instructions:** `README.md`, `make install && make run`  
- **Production docs:** `docs/SYSTEM_DESIGN.md`, `docs/deploy.md`  
- **Evidence matrix:** `docs/IMPLEMENTATION_EVIDENCE_MATRIX.md`

---

## 12. Missing Information Required Before Submission

| Item | Why needed |
|------|------------|
| Human evaluation dataset (n, reviewers, protocol) | Correlation claims in paper draft |
| Paper-scale generation run log (8000 artifacts) | Match abstract sample size |
| Render-rate table by type at scale | Validate 95.7% claim |
| Statistical tests (p-values, CI) on local runs | Results section rigor |
| Publication-quality figures exported from app | Figure placeholders in LaTeX |
| Explicit stand-in disclosure for DeepSeek-32B and Aya deployment | Reproducibility / limitations |
| IRB or evaluation ethics note (if human subjects) | Human study section |

---

## 13. Suggested Section Mapping (Overleaf)

| Paper section | Primary repo source |
|---------------|---------------------|
| Abstract | This handoff §2 + verified Table A |
| Introduction | README, gap_analysis, contributions §3 |
| Related work | `paper/literature_review.tex` |
| Methodology | SYSTEM_DESIGN §4, prompts/, scoring.py |
| System design | SYSTEM_DESIGN.md, architecture figure |
| Implementation | DR_ZHAO_THESIS_PROGRESS_REPORT §8 |
| Evaluation setup | acceptance_eval.md + batch UI |
| Results | Table A–E (local); paper tables marked "prior run" if retained |
| Limitations | §9 above |
| Conclusion | Progress summary conclusion |

---

*Prepared for handoff to Dr. Zhao's Overleaf project. Update after next batch experiment and human evaluation collection.*
