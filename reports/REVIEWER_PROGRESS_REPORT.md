# Reviewer Progress Report — UML-Pipeline

**Paper title:** *Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design*  
**Authors:** Dipak Yadav, Yutong Zhao  
**Student / maintainer:** Dipak Yadav ([@dipak5501](https://github.com/dipak5501))  
**Repository:** [github.com/dipak5501/uml-generation-pipeline](https://github.com/dipak5501/uml-generation-pipeline)  
**Report date:** 2026-08-28  
**Companion technical report:** [`reports/PUBLICATION_TECHNICAL_REPORT.md`](PUBLICATION_TECHNICAL_REPORT.md)

---

## 1. Problem Statement and Goals

Software design documentation often lags implementation. Manual UML authoring from natural-language requirements is slow, inconsistent, and hard to verify at scale. This project builds an **automated pipeline** that:

1. Accepts **natural-language requirements** or **source code** (Java, Python, C, and others).
2. Produces **design-phase UML** (class, object, component, package, flowchart) as black-and-white PlantUML.
3. **Verifies** each diagram with a **three-VLM ensemble** using MMMU-weighted composite score *S* and majority-vote gate *A*.
4. Gates dataset inclusion when render succeeds, *A* = 1, and *S* ≥ 3.

The research contribution—aligned with the paper draft—is **multimodal verification** of generated UML rather than syntax-only checks, enabling scalable dataset construction with quality control.

---

## 2. Infrastructure Decision: Math Department Mac Studio as 24/7 Server

### 2.1 Why this machine

| Factor | Decision |
|--------|----------|
| Hardware | Mac Studio **M1 Ultra**, **128 GB** unified memory, **20** CPU cores (16P+4E), arm64 |
| GPU | Apple **Metal / MLX** — not NVIDIA CUDA |
| Memory | Sufficient for dual Ollama (Qwen2.5-VL-3B + LLaMA-3.2-Vision-11B) plus local Aya-Vision-8B via Transformers |
| Availability | Department-owned; can run 24/7 with LaunchAgent supervision |
| Prior blockers | Azure for Students T4 VMs blocked (`ResourceNotAvailableForOffer`); in-process Aya on 24 GB Mac hung on MPS |

### 2.2 Honest platform note

The paper describes **DeepSeek-R1-Distill-Qwen-32B** for Stage 2 PlantUML generation. On Apple Silicon we train and serve a **MLX LoRA adapter** on **Qwen2.5-0.5B-Instruct-4bit** as a practical stand-in. The **architecture, scoring gates, and evaluation protocol** match the paper; numeric parity with CUDA/DeepSeek-32B runs is **not claimed** without a cross-platform retrain (see §9).

### 2.3 Production stack (current)

| Component | Configuration |
|-----------|---------------|
| API / UI | FastAPI `:8000` + Streamlit `:8501` |
| Persistence | SQLite `data/uml_app.db` |
| Spec LLM (Stage 1) | Ollama `llama3.2:1b` → Llama-3.2-1B-Instruct |
| PlantUML (Stage 2) | **MLX LoRA** `models/uml-plantuml-lora-sourcecode-30k` (warm-started from 200k adapter) |
| VLM #1 | Ollama **0.32.1** on `:11435` → `qwen2.5vl:3b` (w=53.1) |
| VLM #2 | Ollama **0.24.0** on `:11434` → `llama3.2-vision:11b` (w=50.7) |
| VLM #3 | Local Transformers **Aya-Vision-8B** (`VLM_AYA_BACKEND=local`, w=39.9) |
| Render gate | Local JDK + `tools/plantuml.jar` |
| Public access | Cloudflare quick tunnels (UI + API); URLs in `Link` |
| Remote agent | `POST /api/agent/command` (Cursor SDK) |

<!-- LIVE_DEMO_BEGIN -->
**Live demo (as of 2026-08-31):**

- **UI:** [https://individual-cinema-uri-checkout.trycloudflare.com](https://individual-cinema-uri-checkout.trycloudflare.com)
- **API:** [https://hypothetical-advanced-meanwhile-wow.trycloudflare.com](https://hypothetical-advanced-meanwhile-wow.trycloudflare.com)
- **Agent:** [https://hypothetical-advanced-meanwhile-wow.trycloudflare.com/api/agent](https://hypothetical-advanced-meanwhile-wow.trycloudflare.com/api/agent)

Quick-tunnel URLs rotate on restart. This block is rewritten by `scripts/tunnel_notify.py` whenever tunnels publish (GitHub is updated via `scripts/git_auto_push.sh`). Always-current copy: [../Link.md](../Link.md). On the Mac Studio: `data/run/public_ui_url.txt`, `data/run/public_api_url.txt`.
<!-- LIVE_DEMO_END -->

---

## 3. Architecture — Three-Stage Pipeline

```text
Requirement / Source Code
        │
        ▼
┌───────────────────────┐
│ Stage 1: Tech Spec LLM │  Llama-3.2-1B (Ollama)
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ Stage 2: PlantUML LLM  │  MLX LoRA Qwen2.5-0.5B (+ spec-builder fallback)
│ + validate / repair    │
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ PlantUML render gate   │  Local Java + plantuml.jar
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ Stage 3: 3-VLM ensemble│  Qwen2.5-VL-3B, LLaMA-3.2-Vision-11B, Aya-Vision-8B
└───────────┬───────────┘
            ▼
   Composite S + Majority A  (τ=4, need ≥2/3 votes)
            │
            ▼
   Dataset gate: A ∧ (S ≥ 3)  →  SQLite + export / UI
```

**Core modules:** `uml_pipeline/` (research CLI, scoring), `app/` (FastAPI, orchestration, providers), `ui/` (Streamlit), `prompts/` (versioned templates). Full design: [`docs/SYSTEM_DESIGN.md`](../docs/SYSTEM_DESIGN.md).

**Composite formula:**

\[
S = \delta \cdot \frac{\sum_j w_j s_j}{\sum_j w_j}, \quad w=(53.1, 50.7, 39.9), \quad v_j = \mathbf{1}[s_j \ge 4], \quad A = \mathbf{1}\Big[\sum_j v_j \ge 2\Big]
\]

---

## 4. Data and Training

### 4.1 Data lake summary

| Artifact | Rows / size | Role |
|----------|-------------|------|
| HF mirror inventory | 34 OK, 3 failures | `data/data_lake_inventory.json` |
| Mirrored HF rows (sum) | ~217,651 | Includes stack dumps; deduped pool ~58,634 unique PlantUML |
| 50k web/HF training corpus | 50,000 | Class, sequence, use case, flowchart, package, state, object, component, deployment |
| 50k source-code corpus | 50,000 | Java/Python/C + web stack + HF instruction pairs |
| Combined 100k+ merge | 102,445 | HF/web + source-code blocks |
| Finetune JSONL | 131,153 train / 1,687 valid / 1,687 test | MLX-LM chat format, prefer-accepted upsampling |
| Design dataset (paper) | 8,000 | `data/uml_design_dataset.parquet` (3,000 with VLM columns) |

### 4.2 Source-code training (30k Java/Python/C)

Production adapter **`models/uml-plantuml-lora-sourcecode-30k`**:

| Field | Value |
|-------|-------|
| Corpus | 10k Java + 10k Python + 10k C (via `build_language_source_corpus.py`) |
| Warm-start | `models/uml-plantuml-lora-200k` (224k combined corpus, 20k iters) |
| Training iters | 6,000 |
| Base model | `mlx-community/Qwen2.5-0.5B-Instruct-4bit` |
| LoRA | rank 8, scale 20, 8 layers, max_seq_length 1536 |

**Adapter lineage:** legacy 3k → 50k (15k iters) → 100k (18k iters) → 200k (20k iters) → **sourcecode-30k** (production default).

### 4.3 Training commands

```bash
make train-50k          # 50k HF/web corpus + LoRA
make train-100k         # 100k combined merge
make train-200k         # 200k v2 web/synthetic merge
make train-source30k    # 30k Java/Python/C → production adapter
```

All Apple-Silicon training uses `scripts/finetune_plantuml.py` → `python -m mlx_lm lora` via `scripts/run_finetune_resilient.sh`.

---

## 5. Implementation Milestones

| Phase | Deliverable | Status |
|-------|-------------|--------|
| Core pipeline | Spec → PlantUML → render → 3-VLM → *S*/*A* gates | Complete |
| FastAPI + Streamlit app | Jobs, artifacts, human eval UI, dataset export | Complete |
| Dual Ollama | 0.24 (LLaMA-Vision) + 0.32 (Qwen-VL) | Complete |
| Local Aya-Vision-8B | Transformers on Mac Studio 128 GB | Complete |
| MLX LoRA adapters | 50k, 100k, 200k, sourcecode-30k | Complete |
| Source-code intake | Java/Python/C detection, `input_mode=source_code` | Complete |
| Golden test suite | 6 NL + 15 source-code cases | Complete |
| Remote access | Cloudflare tunnels + remote agent API | Complete |
| macOS server supervision | LaunchAgents for API, UI, Ollama, tunnels | Complete |
| Publication report | `reports/PUBLICATION_TECHNICAL_REPORT.md` + PDF | Complete |
| GPU reproduction notes | `docs/CURSOR_GPU_HANDOFF.md` | CUDA / vLLM handoff |

**Fixes during development (selected):**

- Dual Ollama version split (mllama vs qwen2.5vl compatibility).
- VLM score parser handles markdown `**SEMANTIC: N**` and `<0-6>` placeholders.
- PlantUML `FINETUNED_MAX_TOKENS=1536` (512 truncated complex class diagrams).
- Grounded spec-builder fallback when LoRA output fails validation.
- In-process job polling no longer reports “API offline” during slow VLM calls.

---

## 6. Evaluation Results

### 6.1 Automated test suite

| Suite | Result | Notes |
|-------|--------|-------|
| `make test` (pytest) | **153 / 153 pass** | `MOCK_PROVIDERS=true`, deterministic CI mode |
| Golden NL acceptance | **6 / 6** | `tests/golden/cases.json` |
| Golden source-code acceptance | **15 / 15** | `tests/golden/source_code_cases.json` |
| **Total golden** | **21 / 21** | Structural + render + traceability (no live VLM in unit tests) |

### 6.2 Live smoke — source-code golden (Mac Studio, production stack)

Script: `scripts/smoke_source_code_golden.py`  
Cases: 9 default (3 Java, 3 Python, 3 C) — SC-JAVA-01/02/03, SC-PY-01/02/03, SC-C-01/02/03

| Metric | Result |
|--------|--------|
| Render success | **9 / 9** |
| Language detection | **9 / 9** correct |
| Composite VLM score *S* | **4.72 – 6.00** (scale 0–6) |
| Majority *A* | ≥2/3 VLM votes at τ=4 on passing cases |

These are **interactive smoke jobs** on the live adapter (`uml-plantuml-lora-sourcecode-30k`), not a balanced n=8,000 paper evaluation.

### 6.3 Deterministic acceptance harness

From `reports/acceptance_eval.md` (VLM excluded):

- Golden regression: 6/6 accepted  
- Benchmark 200 cases: 200/200 accepted  
- Negative controls: 5/5 correctly rejected  

### 6.4 Paper-scale results (cite paper, not re-run here)

Paper Table (n=2000 per diagram type, DeepSeek-32B pipeline): overall render success 94.4%, mean *S* = 3.85. Majority acceptance 6,891 / 7,553 (91.3%). See `paper/main.tex` — **not re-verified on the LoRA stand-in stack**.

---

## 7. Remote Access and Reproducibility

### 7.1 Public demo

- **UI:** Cloudflare quick tunnel → Streamlit `:8501`  
- **API:** Separate tunnel → FastAPI `:8000`  
- **Remote agent:** `POST /api/agent/command` with `REMOTE_AGENT_TOKEN` / Cursor SDK  

Install always-on server:

```bash
bash scripts/install_macos_user_server.sh
bash scripts/macos_server_status.sh
```

### 7.2 Reproduce locally (Mac Studio path)

```bash
git clone https://github.com/dipak5501/uml-generation-pipeline.git
cd uml-generation-pipeline
make install && make install-java
cp .env.example .env   # set MOCK_PROVIDERS=false, USE_OLLAMA=true, USE_FINETUNED_CODE=true
bash scripts/ensure_ollama_dual.sh
ollama pull llama3.2:1b qwen2.5vl:3b llama3.2-vision:11b
./scripts/run_local.sh
make test
python scripts/smoke_source_code_golden.py   # requires live API + API_ACCESS_TOKEN
```

### 7.3 NVIDIA GPU path (reviewer / cloud)

MLX adapters **do not run on CUDA**. Reviewer should use:

- `USE_OLLAMA=true` or `USE_HF_INFERENCE=true` for spec + VLMs  
- `USE_FINETUNED_CODE=false` (or retrain LoRA with PyTorch/PEFT on CUDA)  
- Aya via vLLM: `VLM_AYA_BACKEND=openai_compat`  

Full instructions: `docs/CURSOR_GPU_HANDOFF.md`.

### 7.4 Key environment variables (names only)

`MOCK_PROVIDERS`, `USE_OLLAMA`, `USE_HF_INFERENCE`, `HF_TOKEN`, `USE_FINETUNED_CODE`, `FINETUNED_*`, `VLM_AYA_BACKEND`, `AYA_VLM_*`, `OLLAMA_BASE_URL`, `OLLAMA_QWEN_BASE_URL`, `ACCEPTANCE_TAU`, `MIN_COMPOSITE_FOR_DATASET`, `API_ACCESS_TOKEN`, `REMOTE_AGENT_TOKEN`.

See `.env.example` — **never commit secrets**.

---

## 8. Limitations and Future Work

1. **Generator stand-in:** Paper Stage 2 is DeepSeek-32B; Mac production uses 0.5B MLX LoRA. Cross-platform CUDA retrain needed for numeric parity.  
2. **Platform split:** MLX is Apple-only; NVIDIA reviewers must retrain or use Ollama/HF inference paths.  
3. **Ephemeral tunnels:** Cloudflare quick URLs rotate; not a production security boundary.  
4. **Human evaluation:** UI and API ready; local DB has limited human-review rows for correlation analysis.  
5. **Paper Overleaf sync:** Reviewer will share Overleaf link; `paper/` holds a synced LaTeX snapshot.  
6. **Future:** Department static hostname or VPN instead of quick tunnels; optional DeepSeek-32B via HF Inference for Stage 2 on GPU hosts; expand source-code languages beyond Java/Python/C.

---

## 9. References and Artifacts

| Artifact | Path |
|----------|------|
| This report | `reports/REVIEWER_PROGRESS_REPORT.md` |
| Publication technical report | `reports/PUBLICATION_TECHNICAL_REPORT.md` |
| System design | `docs/SYSTEM_DESIGN.md` |
| GPU handoff | `docs/CURSOR_GPU_HANDOFF.md` |
| Sample data | `sample_data/`, `tests/golden/` |
| Live URL file | `Link` |
| Adapter inventory | `models/README.md` |
| Data inventory | `data/data_lake_inventory.json` |

**Paper title (for citation):** *Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design* — Dipak Yadav, Yutong Zhao.

---

*Prepared for reviewer Q2 (detailed progress report for paper draft).*
