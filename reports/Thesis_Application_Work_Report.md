# Thesis–Application Work Report

**Paper / thesis title:** *Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design*  
**Authors:** Dipak Yadav, Yutong Zhao  
**Student / implementer:** Dipak Yadav  
**Repository:** https://github.com/dipak5501/uml-generation-pipeline  
**Report date:** 2026-08-31  
**Purpose:** Answer a reviewer request for a detailed account of what has been built: the research thesis, the software application that implements it, and recent engineering on the live system.

---

## 1. Relationship between the thesis and the application

The thesis (and the companion paper draft in `paper/main.tex`) defines a **method**. The GitHub repository is the **working system** that implements that method so it can be run, inspected, and used to generate scored UML artifacts.

The paper’s central claim is that **verification is first-class**: a UML diagram that compiles is not automatically acceptable. Each artifact is scored by three vision-language models (VLMs), combined with an MMMU-weighted composite **S** and a majority-vote gate **A**. Dataset inclusion requires both signals.

The application is not a separate product. It is the same three-stage pipeline, exposed as:

- a FastAPI service (`/api/generate`, jobs, artifacts, analytics, human review);
- a Streamlit UI (dashboard, generate, batch, gallery, human evaluation, analytics, settings, system design);
- SQLite + PNG artifact storage;
- a 24/7 production server on the Math department **Mac Studio** (Apple M1 Ultra, 128 GB).

LaTeX source: `paper/main.tex`. Overleaf: https://www.overleaf.com/project/69ed35eca71ed1faa143a7b9  
Architecture: `docs/SYSTEM_DESIGN.md`  
Gap analysis (paper vs code): `docs/gap_analysis.md`

---

## 2. What the thesis specifies (paper contributions)

From `paper/main.tex`:

1. A **three-stage pipeline**: natural-language requirement → structured specification → PlantUML → render → image-based evaluation.
2. An **MMMU-weighted composite score S** with a render-failure indicator (failed renders do not inflate statistics; S is forced to 0).
3. A **majority-voting acceptance gate A** on top of S (dual-signal quality decision).
4. Comparative evaluation against prior LLM-based UML generators (paper-scale tables).
5. A planned public dataset of (specification, PlantUML, composite score) triples.

The four **design-phase** UML types used in the live API and UI are **class, object, component, and package**. Flowchart/activity diagrams exist in training corpora but are not exposed on `/api/generate`.

Scoring in code (`uml_pipeline/scoring.py`, `app/services/scoring.py`):

| Signal | Definition used in the app |
|--------|----------------------------|
| Per-VLM score | Integer 0–6 (semantic / structural / syntactic / coherence parsed from model text) |
| Weights | Qwen2.5-VL-3B **53.1**, LLaMA-3.2-Vision-11B **50.7**, Aya-Vision-8B **39.9** |
| Composite **S** | Weighted average of available numeric scores (zeros count; missing skipped) |
| Majority **A** | At least 2 of 3 models ≥ τ (**ACCEPTANCE_TAU = 4**) |
| Dataset gate | Render success, **A = 1**, and **S ≥ 3** (`MIN_COMPOSITE_FOR_DATASET`) |

---

## 3. What the application implements (end-to-end)

### 3.1 Pipeline stages

| Stage | Thesis role | Production implementation |
|-------|-------------|---------------------------|
| Input | NL requirements | Also **source code** (Java, Python, C) via `input_mode=source_code` |
| Stage 1 | Spec LLM | Ollama `llama3.2:1b` (Llama-3.2-1B-Instruct) |
| Stage 2 | PlantUML generator | **MLX LoRA** on Qwen2.5-0.5B-Instruct-4bit, adapter `models/uml-plantuml-lora-sourcecode-30k` (6,000 iters, warm-started from the 200k adapter). Spec-builder / LLM repair if LoRA output fails validation |
| Render gate | PlantUML → PNG | Local JDK + `tools/plantuml.jar`; remote PlantUML HTTP fallback |
| Stage 3 | Three VLMs | Qwen2.5-VL-3B (Ollama 0.32 `:11435`), LLaMA-3.2-Vision-11B (Ollama 0.24 `:11434`), Aya-Vision-8B (local Transformers, paper-exact, `VLM_AYA_BACKEND=local`) |
| Persistence | Dataset construction | SQLite `data/uml_app.db` + PNG files + PlantUML text + per-model explanations |

**Honest stand-in (documented, not hidden):** the paper names DeepSeek-R1-Distill-Qwen-32B for Stage 2. The Mac serves a **0.5B MLX LoRA** stand-in. Architecture, gates, and VLM ensemble match the thesis; numeric parity with the 32B paper tables is **not claimed** on this stack.

### 3.2 Software surfaces

| Surface | What it does |
|---------|----------------|
| Generate | One requirement or one source file → one or all four diagram types; optional VLM scoring |
| Batch | Many requirements × diagram types as background jobs |
| Generated diagrams | Gallery of every artifact (image, PlantUML, S, A, repairs) |
| Human evaluation | Rubric UI aligned with the thesis dimensions |
| Analytics | Counts, score distributions, dataset export (JSONL / CSV / Parquet) |
| Settings | Health of providers, Java, PlantUML JAR, LoRA adapter, auth |
| Remote agent | `POST /api/agent/command` (health, generate, smoke-test, restart, server-status) |

### 3.3 Production server

Always-on via **user LaunchAgents** (no admin) on the Mac Studio:

- FastAPI `:8000`, Streamlit `:8501`
- Dual Ollama (0.24 and 0.32 — required because one Ollama build cannot load both `llama3.2-vision` and `qwen2.5vl`)
- Local Aya-Vision-8B in the API process
- Cloudflare quick tunnels for public UI and API
- `API_ACCESS_TOKEN` on public endpoints

**Live access (as of 2026-08-31; URLs rotate when tunnels restart):**

- UI: https://individual-cinema-uri-checkout.trycloudflare.com
- API: https://hypothetical-advanced-meanwhile-wow.trycloudflare.com
- Agent: https://hypothetical-advanced-meanwhile-wow.trycloudflare.com/api/agent

Canonical copies on the Mac: `data/run/public_ui_url.txt`, `data/run/public_api_url.txt`. GitHub copy: `Link.md`. `scripts/tunnel_notify.py` rewrites a marked **Live demo** block in README and related docs when tunnels publish.

---

## 4. Evaluation that has been done

### 4.1 Automated tests (CI)

`MOCK_PROVIDERS=true pytest`: **153 tests** on `main` (deterministic mocks; no live GPU/VLM). Covers API, security, scoring, golden NL and source-code structure, PlantUML validation, jobs, agent allowlist.

Golden fixtures: **6** NL cases (`tests/golden/cases.json`) + **15** source-code cases (`tests/golden/source_code_cases.json`) = **21**.

### 4.2 Live Mac Studio smoke (production LoRA + three VLMs)

`scripts/smoke_source_code_golden.py` (9 default Java/Python/C cases): render **9/9**, language detection **9/9**, composite **S** in about **4.72–6.00**, majority **A** on passing cases.

These are interactive smoke jobs, **not** a re-run of the paper’s n≈8,000 DeepSeek-32B tables.

### 4.3 Live functional check (2026-08-31)

Under current model load (no finetune running; dual Ollama + Aya + MLX LoRA):

- Health: `status=ok`, provider `spec/VLM=ollama · code=finetuned-mlx`, adapter present, Java and PlantUML JAR present.
- Single class generate (campus parking): completed in ~43 s; render **success**; **S ≈ 5.65**; majority **true**; dataset **accepted**; all three VLMs available (Qwen 6, LLaMA-Vision 5, Aya 6).
- Concurrent 4-type job from Java source (class, object, component, package): all four rendered successfully with all three VLMs scoring.
- UI (Dashboard, gallery, Settings) stayed connected to the API during that load.

Historical note: object diagrams have a higher lifetime render-failure rate than class/component/package in the stored database. Recent object jobs on the live stack can still succeed (the Java-source object in that 4-type job scored **S ≈ 5.65**).

### 4.4 Paper-scale numbers (cite the paper, do not treat as re-measured here)

Paper tables (DeepSeek-32B pipeline, large n): overall render success about **94.4%**, mean **S ≈ 3.85**, majority acceptance about **91.3%**. Those figures are **not** re-verified on the Mac LoRA stack.

Human–AI correlation: the UI and API exist; a large-n human study has **not** been completed (`human_review_count` on the live DB was **0** at the 2026-08-31 check).

---

## 5. Training data and LoRA (what was trained)

| Corpus / adapter | Role |
|------------------|------|
| 8k / 50k / 100k / 200k UML PlantUML corpora | Earlier MLX LoRA runs (superseded for production) |
| 30k source-code block (10k Java, 10k Python, 10k C) | **Production** adapter `uml-plantuml-lora-sourcecode-30k`, 6,000 iterations |
| NVIDIA path | `scripts/finetune_plantuml_cuda.py` — **not** for the Mac Studio (MLX ≠ CUDA) |

The Mac must not run `make finetune-cuda`. GPU reviewers use `docs/CURSOR_GPU_HANDOFF.md`.

---

## 6. Work completed recently (application + thesis packaging)

This section is the engineering completed around late August 2026 on top of the already-running pipeline.

### 6.1 Readable UML for software-lifecycle tracking

Generated class / object / component / package diagrams now include a **title**, a plain-English “what this shows” note, **English arrow labels** (related to, owns, depends on, …), an **SDLC phase** hint by diagram type, and a **symbol legend**. Stage-1/2 prompts and the LoRA prompt ask for the same structure. The Generate UI explains how each diagram type tracks design vs architecture vs runtime snapshot.

*(These prompt/UI changes live on PR branch `cursor/gpu-handoff-cuda-lora-2084` until that PR is merged. The Mac still serves whatever checkout is running there until `git pull` + API/UI restart.)*

### 6.2 English-only Aya judge text

Aya-Vision is multilingual; sampling mixed Japanese into EXPLANATION text even when the numeric score was valid. Prompts now require English-only judge output.

### 6.3 Thesis draft and application report PDFs

Generators: `scripts/generate_thesis_draft.py`, `scripts/generate_progress_pdf.py`. Tracked PDFs (on the GPU-handoff PR):

- Application / system report
- CSULB-style **M.S. thesis draft** (advisor review, not Thesis Office final format)

GitHub PDF preview was fixed by rewriting ReportLab streams as Flate-only (no ASCII85).

### 6.4 Live demo URLs kept current on GitHub

Stale 2026-08-27 Cloudflare URLs were replaced with the working tunnels. A marked `<!-- LIVE_DEMO_BEGIN -->` block in README, deploy notes, and reviewer docs is rewritten by `scripts/tunnel_notify.py` whenever tunnels rotate, then `scripts/git_auto_push.sh` can sync `main`.

### 6.5 Removed unused reviewer GPU package

`reports/reviewer_gpu_package/` and `reports/reviewer_gpu_package.zip` were deleted from **GitHub `main`** (commit `a82217f`, 2026-08-31). They duplicated `tests/golden/` and `sample_data/` and were not needed for the thesis or the live app. GPU instructions remain in `docs/CURSOR_GPU_HANDOFF.md`.

### 6.6 CUDA / GPU handoff (for machines that are not the Mac)

PR https://github.com/dipak5501/uml-generation-pipeline/pull/1 documents NVIDIA PEFT LoRA and vLLM Aya. The **production server is Apple Silicon**, not CUDA.

---

## 7. Mapping: paper contribution → software status

| Paper item | In the application? | Status |
|------------|---------------------|--------|
| Three-stage pipeline | Yes | Live on Mac Studio |
| NL → spec → PlantUML | Yes | Plus source-code intake |
| Four design-phase UML types | Yes | class, object, component, package |
| PlantUML render as hard gate | Yes | Failed render → S = 0 |
| Three VLMs + MMMU weights | Yes | Dual Ollama + local Aya |
| Composite S + majority A | Yes | Same τ and dataset rule |
| Human evaluation protocol | UI + rubric | Large-n study **not run** |
| 8,000-triple public dataset | Batch + export APIs | HuggingFace release **not completed** as the paper’s public artifact |
| DeepSeek-32B Stage 2 | No (stand-in) | 0.5B MLX LoRA; documented |
| Comparison vs five prior systems | Paper tables | Not re-run on LoRA stack |

---

## 8. What is still open (honest)

1. **Stage-2 model size:** paper DeepSeek-32B vs production 0.5B LoRA — architecture matches; numbers may not.
2. **Human alignment study:** screens exist; correlation with VLM scores is not yet a finished thesis experiment.
3. **Official CSULB thesis format:** current PDF is an advisor draft, not Thesis Office template + complete bibliography from `paper/references.bib`.
4. **Public 8k HuggingFace dataset:** generation machinery exists; the paper’s public dump is a remaining release step.
5. **Mac checkout vs latest PR:** clearer UML labels and English Aya prompts need `git pull` of the GPU-handoff branch (or merge to `main`) and restart of API/UI on the Studio.
6. **Object-diagram reliability:** historically weaker in the stored corpus; still the weakest of the four types.

---

## 9. How a reviewer can inspect the work

| What to inspect | Where |
|-----------------|--------|
| Live app | UI / API URLs in §3.3 and `Link.md` |
| Source code | https://github.com/dipak5501/uml-generation-pipeline |
| Paper method | `paper/main.tex` |
| System design | `docs/SYSTEM_DESIGN.md` |
| Tests | `make test` (153 on `main`) |
| Live code→UML smoke | `python scripts/smoke_source_code_golden.py` on the Mac with `API_ACCESS_TOKEN` |
| GPU-only reproduction | `docs/CURSOR_GPU_HANDOFF.md` |

Do not commit `.env`. Tokens stay on the Mac Studio.

---

## 10. One-sentence summary for the reviewer

The thesis defines a **multimodal-verified UML generation pipeline**; the repository is that pipeline as a **running application** (API, UI, LoRA, three VLMs, dataset gates) on a department Mac Studio, with documented stand-ins where 32B/CUDA hardware is not used, and with remaining research work in human correlation and paper-scale public data release rather than missing software modules.

---

*Prepared 2026-08-31 for reviewer discussion of the M.S. thesis and the UML-Pipeline application.*
