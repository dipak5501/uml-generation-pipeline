# UML-Pipeline: Publication-Oriented Technical Report

**Companion title (paper):** *Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design*  
**Authors (paper):** Dipak Yadav, Yutong Zhao  
**Code repository:** [github.com/dipak5501/uml-generation-pipeline](https://github.com/dipak5501/uml-generation-pipeline)  
**Code maintainer (AUTHORS.md):** Dipak Yadav ([@dipak5501](https://github.com/dipak5501))  
**Report date:** 2026-08-26  
**Scope:** Machine-verified description of the implemented application and local deployment; for citation/adaptation into a venue paper. **Paper-scale experimental tables in `paper/main.tex` are cited as paper claims, not re-verified at n=8,000 on this host.** Local smoke/job metrics below are measured from on-disk SQLite and corpora.

---

## Abstract-style summary

**UML-Pipeline** is an end-to-end system that maps natural-language software requirements (or source code) to design-phase UML artifacts. The pipeline is decomposed as:

1. **Requirement / code intake** → structured technical specification (Stage 1 LLM).  
2. **Specification → PlantUML** with chain-of-thought style prompting and validation/repair (Stage 2).  
3. **PlantUML render gate** (local Java + PlantUML JAR).  
4. **Three-VLM ensemble** scoring on the rendered image (Stage 3).  
5. **Dual acceptance signal:** MMMU-weighted composite score \(S\) and majority-vote gate \(A\), with dataset inclusion when \(A=1\) and \(S \ge 3\).

The research paper describes Stage 1 as **Llama-3.2-1B-Instruct**, Stage 2 as **DeepSeek-R1-Distill-Qwen-32B**, and Stage 3 as **Qwen2.5-VL-3B** (\(w=53.1\)), **LLaMA-3.2-Vision-11B** (\(w=50.7\)), and **Aya-Vision-8B** (\(w=39.9\)), with \(\tau=4\) and majority \(\ge 2/3\).

**This implementation** runs primarily on an **Apple Mac Studio (M1 Ultra, 128 GB)** with dual local Ollama daemons, optional **MLX LoRA** PlantUML generation (Qwen2.5-0.5B 4-bit stand-in for DeepSeek-32B), and **local Transformers** Aya-Vision-8B. A FastAPI backend and Streamlit UI persist full artifact traces in SQLite; Cloudflare quick tunnels expose the UI/API remotely for demos.

---

## 1. Authors and research context

| Role | Name | Notes |
|------|------|--------|
| Paper co-author / project owner | Dipak Yadav | Repository author and maintainer (`AUTHORS.md`, `README.md`, `config.yaml`) |
| Paper co-author | Yutong Zhao | Listed in `paper/README.md` and LaTeX front matter |
| Paper Overleaf | [project link in `paper/README.md`](https://www.overleaf.com/project/69ed35eca71ed1faa143a7b9) | Live draft; `paper/` holds a synced LaTeX snapshot |

Alignment documents in-repo: `docs/SYSTEM_DESIGN.md`, `docs/gap_analysis.md`, `docs/assumptions.md`, `docs/README_ALIGNMENT.md`, `docs/deploy.md`.

---

## 2. System architecture

### 2.1 Pipeline stages (paper ↔ code)

```text
Requirement / Code
        │
        ▼
┌───────────────────────┐
│ Stage 1: Tech Spec LLM │  Llama-3.2-1B (Ollama / HF)
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ Stage 2: PlantUML LLM  │  Paper: DeepSeek-R1-32B
│ + validate / repair    │  Local default: MLX LoRA Qwen2.5-0.5B
└───────────┬───────────┘   (+ grounded spec-builder fallback)
            ▼
┌───────────────────────┐
│ PlantUML render gate   │  Local JDK + tools/plantuml.jar
└───────────┬───────────┘  (optional remote plantuml.com)
            ▼
┌───────────────────────┐
│ Stage 3: 3 VLMs        │  Qwen2.5-VL-3B, LLaMA-3.2-Vision-11B,
│                        │  Aya-Vision-8B
└───────────┬───────────┘
            ▼
   Composite S + Majority A
            │
            ▼
   Dataset gate: A ∧ (S ≥ 3)  →  SQLite + export / UI
```

Core libraries:

| Layer | Location | Responsibility |
|-------|----------|----------------|
| Research CLI / scoring | `uml_pipeline/` | Dataset merge, render helpers, `weighted_composite` |
| Application services | `app/` | FastAPI, SQLModel, orchestration, repair, scoring gates |
| Providers | `app/providers/` | Mock, Ollama, HF, MLX LoRA, local Aya |
| UI | `ui/` | Streamlit multipage (dashboard, generate, batch, gallery, human eval, analytics, settings, system design) |
| Prompts | `prompts/` | Versioned templates |
| Paper | `paper/` | LaTeX source |

### 2.2 Application stack (FastAPI + Streamlit)

- **API:** `uvicorn app.main:app` on `:8000` (`make api` / `scripts/run_local.sh`).  
- **UI:** Streamlit on `:8501` (`make ui`).  
- **Persistence:** SQLite at `data/uml_app.db` (jobs, requirements, specs, artifacts, render/repair attempts, per-VLM `modelscore`, `compositescore`, human reviews).  
- **Artifacts:** PNGs and PlantUML under `data/artifacts/`.  
- **Jobs:** In-process background generation (no Redis/Celery; see `docs/assumptions.md`).

Principal HTTP surface (from README): `POST /api/generate`, batch generate, `GET /api/jobs/{id}`, artifact CRUD + rescore/repair, human review, analytics, dataset export (`jsonl` / `csv` / `parquet`).

### 2.3 Local inference stack (this machine)

Measured **2026-08-26** on this host:

| Component | Configuration |
|-----------|----------------|
| Hardware | Apple **Mac Studio**, chip **M1 Ultra**, **128 GB** unified memory, **20** CPU cores (16P+4E), arm64 |
| Spec LLM | Ollama `llama3.2:1b` (paper: `meta-llama/Llama-3.2-1B-Instruct`) |
| PlantUML generator | **MLX LoRA** on `mlx-community/Qwen2.5-0.5B-Instruct-4bit` at `models/uml-plantuml-lora-50k` (**complete**, 15k iters); **`uml-plantuml-lora-100k` training in progress** (~4.5k/18k iters as of 2026-08-26; see `data/training/finetune_100k.log`) — paper stand-in for DeepSeek-R1-Distill-Qwen-32B |
| VLM #1 | Ollama **0.32.1** on `:11435` → `qwen2.5vl:3b` |
| VLM #2 | Ollama **0.24.0** on `:11434` → `llama3.2-vision:11b` |
| VLM #3 | `VLM_AYA_BACKEND=local` → `CohereLabs/aya-vision-8b` via Transformers (not on Ollama) |
| Render | Local PlantUML JAR + bundled/installed JDK (`PLANTUML_PREFER_LOCAL=true`) |
| Remote UI | Cloudflare **quick tunnels** (`cloudflared`) for `:8501` and `:8000`; LaunchAgent supervisor under `scripts/launchd/` |

Dual-Ollama rationale (code comments / `.env.example`): Qwen2.5-VL needs Ollama ≥0.32; LLaMA-3.2-Vision (mllama) is pinned on 0.24.

---

## 3. Models (paper mapping)

### 3.1 Generation models

| Stage | Paper model | Local / app mapping | Notes |
|-------|-------------|---------------------|--------|
| Spec | Llama-3.2-1B-Instruct | `SPEC_MODEL`; Ollama `llama3.2:1b` when `USE_OLLAMA=true` | Lightweight JSON/tech-spec generator |
| PlantUML | DeepSeek-R1-Distill-Qwen-32B | Env still names `CODE_MODEL=deepseek-ai/DeepSeek-R1-Distill-Qwen-32B`, but **`USE_FINETUNED_CODE=true`** routes Stage 2 to **MLX LoRA Qwen2.5-0.5B-Instruct-4bit** | Explicit **stand-in** for Apple Silicon; README: DeepSeek-32B is large / often unavailable locally |
| Fallback | — | Grounded **spec-builder** PlantUML when LoRA fails validation/fidelity | Observed frequently as `code_model=spec-builder` in SQLite |

### 3.2 VLM ensemble and weights

From `config.yaml` / `app/settings.py` / paper Eq. (weighted):

| Key | Model | MMMU weight \(w\) |
|-----|--------|-------------------|
| `qwen25vl3b` | Qwen2.5-VL-3B-Instruct | **53.1** |
| `llama32vl11b` | LLaMA-3.2-11B-Vision-Instruct | **50.7** |
| `aya_vision_8b` | Aya-Vision-8B | **39.9** |

Denominator \(w_1+w_2+w_3 = 143.7\).

### 3.3 Acceptance gates

| Symbol | Rule (paper + `app/services/scoring.py`) |
|--------|------------------------------------------|
| Render gate \(\delta\) | If render fails → \(S=0\), majority forced false |
| Composite \(S\) | \(S = \delta \cdot \sum_j w_j s_j / \sum_j w_j\), scores \(s_j \in [0,6]\); numeric zeros count; `None` skipped |
| Vote | \(v_j = 1\) iff \(s_j \ge \tau\), **\(\tau = 4\)** (`ACCEPTANCE_TAU`) |
| Majority \(A\) | \(A=1\) iff \(\sum v_j \ge 2\) (of 3) |
| Dataset entry | Render OK **and** \(A=1\) **and** \(S \ge 3\) (`MIN_COMPOSITE_FOR_DATASET`) |

Worked example from paper: scores \((5,4,3)\) → \(S \approx 4.09\).

---

## 4. Datasets

### 4.1 Paper / design corpus on disk

| Artifact | Measured rows | Role |
|----------|---------------|------|
| `data/uml_design_dataset.parquet` | **8,000** | Assembled design-phase mix (class/object/component/package); partial VLM columns |
| Of which with VLM score columns filled | **3,000** | Mean composite `scores` ≈ **3.76** (only scored subset); means: Qwen ≈3.74, LLaMA-V ≈4.08, Aya ≈2.18 |
| `data/raw/class.parquet` | 5,000 | Class RAW |
| `data/raw/component.parquet` | 1,000 | Component scored |

Primary HF sources named in `config.yaml` / early manifests:

- `nguyenvanviet/UMLCode-ClassDiagram-DeepSeek-32B-Reasoning-RAW`  
- `nguyenvanviet/UMLCode_ObjectDiagram_Scored`  
- `nguyenvanviet/UMLCode_ComponentDiagram_Scored`  
- `nguyenvanviet/UMLCode_PackageDiagram_Scored`  
- Gated (optional, access failed on this host): `nguyenvanviet/UMLCode-ClassDiagram-DeepSeek-32B-Scored`

### 4.2 Hugging Face mirror inventory (`data/raw/hf/`)

From `data/data_lake_inventory.json` (measured):

- **34** mirrors OK, **3** failures (gated class-scored; one UC-Class-Sequence-Raw generation error; one empty repo).  
- Sum of mirrored train rows ≈ **217,651** (includes large stack dumps; not all unique).  
- Deduped unique PlantUML pool ≈ **58,634**.

Selected mirrored corpora with on-disk `meta.json` row counts (non-exhaustive):

| HF repo | Rows (meta) |
|---------|-------------|
| `devgpt-aimotion/the-stack-v2_PlantUML_full` | 109,000 |
| `devgpt-aimotion/the-stack-v2_PlantUML_filtered` | 43,052 |
| `nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-UC-Class-Sequence-Scored` | 8,998 |
| `nguyenvanviet/UMLCode_Reasoning_Class_UseCase_Scored` | 7,998 |
| `josoa-test/plantuml-datasets` | 7,894 |
| `nguyenvanviet/UMLCode-ClassDiagram-DeepSeek-32B-Reasoning-RAW` | 5,000 |
| `ThePeaceLovingGhost/ClassDiagram_PlantUML_Text` | 5,000 |
| Object / component / package / deployment / activity / state (various) | ~960–1,000 each |
| `coai/plantuml_generation` | 1,940 |
| `ibivibiv/plantuml-training` / `prashant182/plantuml-json` | 972 |
| Vinzur / Seym0n usecase & hand-drawn sets | 141–1,005 |

### 4.3 Training corpora currently on disk (honest timeline)

| Corpus file | Measured size | Honest status |
|-------------|---------------|---------------|
| Historical target “8k UMLCode” | README / older `data/manifest.json` schema | Original paper-aligned open assemble target: **8,000** (5k class + 1k×3) |
| Prior ≥10k path | `models/README.md` describes 8k + scenario/code supplements → ~10k merged | Superseded on this disk by 50k effort |
| `data/training/uml_training_8000.parquet` **filename retained** | **50,000** rows | Built for 50k scale-up; filename kept for pipeline compatibility |
| Type mix (50k) | class 19,335; sequence 12,500; usecase 9,122; flowchart 2,623; package 1,480; state 1,458; object 1,177; component 1,162; deployment 1,143 | From `data/training/manifest.json` |
| Scored / accepted in 50k assemble | scored_rows **7,940**; dataset_accepted **5,539** | Manifest; composite column present for all 50k but many zeros from unscored web rows (mean \(S\) ≈ 0.51 over all 50k) |
| `uml_training_supplement_merged.parquet` | **54,207** | 50k HF/web + 5k scenario + 5k multilingual code templates; **0** synthetic top-up beyond that |
| Finetune JSONL | train **61,395** / valid **1,279** / test **1,279** | `data/finetune/manifest.json`; prefer-accepted upsample |

**50k effort status:** Corpus build completed. LoRA retrain toward **15,000** iters into `models/uml-plantuml-lora-50k` was **in progress** at report time (early checkpoints present; see §5). Do not treat 50k-adapter results as finished paper metrics.

---

## 5. Training methodology (MLX LoRA)

### 5.1 Completed adapter used by the live app

| Field | Value (from `models/uml-plantuml-lora/finetune_meta.json` + `adapter_config.json`) |
|-------|-------------------------------------------------------------------------------------|
| Base | `mlx-community/Qwen2.5-0.5B-Instruct-4bit` |
| Path | `models/uml-plantuml-lora` (also mirrored as `uml-plantuml-lora-LIVE`, `uml-plantuml-lora-prev-3k`) |
| Type | LoRA, rank **8**, scale **20**, dropout **0**, **8** layers |
| Iters completed | **3,000** (checkpoints every 200 through `0003000_adapters.safetensors`) |
| Batch / LR / seq | batch **2**, lr **1e-5**, max_seq_length **2048**, Adam, grad checkpoint |
| Data | `data/finetune` chat JSONL (`specification_to_plantuml`) |
| Trainable fraction | ~0.297% (~1.47M / 494M) — same ballpark as ongoing 50k run logs |

Enablement (non-secret): `USE_FINETUNED_CODE=true`, `FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora`, `FINETUNED_MAX_TOKENS=1536`.

### 5.2 In-progress 50k-scale retrain (do not interrupt)

Observed **2026-08-26** without stopping processes:

- Script: `scripts/run_finetune_resilient.sh` → `scripts/finetune_plantuml.py` → `python -m mlx_lm lora`  
- Adapter dir: `models/uml-plantuml-lora-50k`  
- Target iters: **15,000**; `max_seq_length=1536`; save every 200  
- Log sample: Val loss ~2.31 at start; train loss ~1.3–2.0 in first few hundred iters; peak mem ~3.6 GB  
- Early artifacts: `0000200_adapters.safetensors` present; training continuing  

Makefile targets: `make finetune`, `make train-real` (3k), `make train-50k`, `make finetune-prepare`, `make training-corpus-50k`.

---

## 6. Evaluation protocol

### 6.1 Automated multimodal verification (paper-faithful)

Implemented in `app/services/scoring.py` and `uml_pipeline/scoring.py`:

1. Render PNG (or fail → \(S=0\)).  
2. Each VLM returns integer/float score in \(0..6\) plus optional explanation.  
3. Compute \(S\) with fixed MMMU weights.  
4. Compute votes at \(\tau=4\); set \(A\) if ≥2 affirmative.  
5. Persist `formula_snapshot` strings such as:  
   `final=4.4447 | majority=True votes=2 tau=4.0 | dataset_accepted=True | qwen25vl3b=5(w=53.1,vote=Y), ...`  
6. Dataset flag: `dataset_accepted = render_ok ∧ majority_accepted ∧ (S ≥ 3)`.

### 6.2 Structural / semantic gates (application, separate from VLM)

`reports/acceptance_eval.md` documents a deterministic acceptance harness (heuristic Stage-1 JSON → PlantUML builder → `-checkonly` → render → UML structure + requirement↔UML traceability; repair ≤3). **VLM scoring is explicitly excluded from that harness.** Reported there (deterministic / mock-friendly):

- Golden regression: **6/6** full pipeline accepted.  
- Benchmark 200 cases (requirements × 4 types): **200/200** accepted.  
- Negative controls: **5/5** correctly rejected (TNR 1.0).

### 6.3 Human evaluation (paper + UI)

Paper: semantic correctness, structural completeness, syntactic accuracy, overall coherence; correlation / Fleiss’ \(\kappa\) analyses in `paper/main.tex`.  
App: Streamlit Human Evaluation page + `POST /api/human-review`. **On this DB snapshot: `humanreview` count = 0** (no local human ratings stored yet).

### 6.4 Paper-reported large-scale results (cite paper, not this Mac run)

From `paper/main.tex` Table “render” (\(n=2000\) per type, **paper claim**):

| Diagram | Success % | Mean \(S\) | SD |
|---------|-----------|------------|-----|
| Class | 95.7 | 4.31 | 0.74 |
| Object | 94.4 | 4.09 | 0.81 |
| Component | 91.6 | 3.87 | 0.93 |
| Package | 81.1 | 3.12 | 1.04 |
| Overall | 94.4 | 3.85 | 0.98 |

Paper also reports majority acceptance **6,891 / 7,553** rendered (91.3%). **These numbers were not re-run end-to-end on the LoRA stand-in stack for this report.**

---

## 7. Implementation details on this hardware

### 7.1 Runtime configuration (non-secret `.env` flags observed)

```text
MOCK_PROVIDERS=false
USE_OLLAMA=true
USE_HF_INFERENCE=false
USE_FINETUNED_CODE=true
FINETUNED_BASE_MODEL=mlx-community/Qwen2.5-0.5B-Instruct-4bit
FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora
FINETUNED_MAX_TOKENS=1536
VLM_FAST_MODE=false
VLM_AYA_BACKEND=local
AYA_VLM_MODEL=CohereLabs/aya-vision-8b
ACCEPTANCE_TAU=4.0
MIN_COMPOSITE_FOR_DATASET=3.0
SPEC_MODEL=meta-llama/Llama-3.2-1B-Instruct
CODE_MODEL=deepseek-ai/DeepSeek-R1-Distill-Qwen-32B
VLM_MODELS=qwen2.5vl:3b,llama3.2-vision:11b,aya-vision:8b
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_QWEN_BASE_URL=http://127.0.0.1:11435
PLANTUML_PREFER_LOCAL=true
```

Secrets (`HF_TOKEN`, `API_ACCESS_TOKEN`, API keys) are **not** reproduced here.

### 7.2 Deployment notes

| Mode | Notes |
|------|--------|
| Local | `make run` / `./scripts/run_local.sh` |
| Public demo (this lab) | Cloudflare quick tunnels; URLs rotate; campus DNS may fail to resolve `*.trycloudflare.com` — UI keeps `API_BASE_URL` on localhost |
| Render / Railway | `docs/deploy.md`, `render.yaml`; free tier sleeps; **MLX LoRA not available** on typical Linux free instances (`USE_FINETUNED_CODE=false`) |
| GitHub Pages | Static landing only (`site/`) |
| Azure Students | `docs/CURSOR_GPU_HANDOFF.md`: T4 VMs blocked (`ResourceNotAvailableForOffer`); prior ACI Aya timeouts — prefer this Mac’s local Aya |

### 7.3 Processes observed at report time (not interrupted)

- `uvicorn` `:8000`, Streamlit `:8501`  
- Dual `ollama serve` (0.24 + 0.32 LaunchAgents)  
- Dual `cloudflared` quick tunnels  
- Resilient MLX LoRA 50k training (`models/uml-plantuml-lora-50k`)  

---

## 8. Experimental results (measured on this machine only)

**Honesty rule:** No fabricated large-\(n\) metrics. Below is what exists in `data/uml_app.db` and local eval files as of 2026-08-26.

### 8.1 SQLite generation / VLM smoke inventory

| Quantity | Count |
|----------|------:|
| `generationjob` | 32 |
| `umlartifact` | 32 |
| Artifacts with ≥3 VLM scores recorded | 30 |
| Artifacts with \(S>0\) | 29 |
| Majority \(A=1\) | 28 |
| `dataset_accepted` | 23 |
| Mean \(S\) among \(S>0\) | **≈ 4.77** (min ≈ 3.71, max ≈ 5.65) |
| `humanreview` | 0 |

**Providers:** Nearly all recent artifacts labeled `provider=finetuned-mlx`. PlantUML source often `code_model=spec-builder` (grounded fallback); a minority show `finetuned:uml-plantuml-lora`.

**Illustrative 3-VLM rows (real DB samples):**

| Type | Qwen | LLaMA-V | Aya | \(S\) (approx) | \(A\) | Dataset |
|------|-----:|--------:|----:|---------------:|:-----:|:-------:|
| class | 6 | 5 | 6 | 5.65 | 1 | 1 |
| component | 6 | 4 | 6 | 5.29 | 1 | 1 |
| package | 5 | 5 | 3 | 4.44 | 1 | 1 |
| package | 3 | 5 | 3 | 3.71 | 0 | 0 |
| class | 0 | 0 | 0 | 0.00 | 0 | 0 |

These are **smoke / interactive jobs**, not a balanced 8k evaluation.

### 8.2 Deterministic acceptance harness

See §6.2 / `reports/acceptance_eval.md` (200/200 + negatives). Suitable for syntax/structure regression; **not** a substitute for paper VLM tables.

### 8.3 Design parquet score subset

`data/uml_design_dataset.parquet`: 8,000 rows; **3,000** with filled VLM columns; mean composite ≈ **3.76** on that subset (imported/scored upstream corpora—not regenerated here with the LoRA stack).

---

## 9. Limitations and threats to validity

1. **Generator mismatch:** Paper Stage 2 is DeepSeek-R1-Distill-Qwen-32B; production Mac path uses **0.5B MLX LoRA** (+ frequent spec-builder fallback). External validity of paper RQ1 tables to this deploy is limited until DeepSeek-32B (or a stronger stand-in) is evaluated under the same protocol.  
2. **Hardware / backend mismatch:** Apple Silicon MLX + dual Ollama + local Aya ≠ paper’s presumed CUDA / HF Inference stack. Numeric parity is not guaranteed.  
3. **Aya local:** Paper-exact weights via Transformers on MPS/CPU; historically fragile on smaller Macs; Azure student GPU path blocked (handoff doc). Latency and scoring stability may differ from vLLM GPU serving.  
4. **Quick tunnels:** Ephemeral URLs, DNS flakiness on campus networks, not a production security boundary.  
5. **50k train unfinished:** Reporting mid-run losses is **not** a final model quality claim.  
6. **Filename confusion:** `uml_training_8000.*` now holds **50k** rows—cite measured counts, not the filename.  
7. **Human correlation:** Paper claims Pearson / Fleiss statistics; **zero** human reviews in local DB—cannot reproduce human alignment here.  
8. **Score key hygiene:** Some `modelscore.model_name` values store Ollama/HF tags vs canonical weight keys; composites still recompute via normalized keys in services—document carefully when exporting.  
9. **Cloud free tiers:** Render sleep + no MLX; student Azure limits constrain remote VLM hosting.  
10. **Internal validity of weights:** MMMU is a proxy for diagram understanding (paper’s own threat); ensemble may still share failure modes on UML notation.

---

## 10. Reproducibility

### 10.1 Make targets (selected)

| Target | Purpose |
|--------|---------|
| `make install` | venv, deps, PlantUML jar, `.env` |
| `make run` / `api` / `ui` | Local services |
| `make training-corpus` | Build 8k-style corpus |
| `make training-corpus-50k` / `download-all-corpora` | Scale-up data lake |
| `make finetune-prepare` / `finetune` / `train-real` / `train-50k` | MLX LoRA |
| `make test` / `smoke` / `demo` | Offline checks |
| `make eval-smoke` / `eval-batch` | Scenario/code batch eval scripts |

### 10.2 Environment variables (names only; see `.env.example`)

`MOCK_PROVIDERS`, `USE_OLLAMA`, `USE_HF_INFERENCE`, `HF_TOKEN`, `USE_FINETUNED_CODE`, `FINETUNED_*`, `SPEC_MODEL`, `CODE_MODEL`, `VLM_MODELS`, `VLM_AYA_BACKEND`, `AYA_VLM_*`, `OLLAMA_BASE_URL`, `OLLAMA_QWEN_BASE_URL`, `ACCEPTANCE_TAU`, `MIN_COMPOSITE_FOR_DATASET`, `VLM_FAST_MODE`, `PLANTUML_*`, `API_ACCESS_TOKEN`, `CORS_ORIGINS`, `API_BASE_URL`, `OPENAI_*`.

### 10.3 Key scripts

- `scripts/build_training_corpus.py`, `download_all_corpora.py`, `download_datasets.py`  
- `scripts/prepare_finetune_data.py`, `finetune_plantuml.py`, `run_finetune_resilient.sh`  
- `scripts/ensure_ollama_dual.sh`, `launchd/run_ollama{24,32}.sh`  
- `scripts/setup_paper_aya_local.sh`  
- `scripts/start_public_tunnels.sh`, `launchd/run_tunnels.sh`  
- `scripts/generate_alignment_pdf.py`, `generate_progress_pdf.py`, `generate_thesis_draft.py`  
- Dual-Ollama + Aya setup also documented in `.env.example` and `docs/CURSOR_GPU_HANDOFF.md`

### 10.4 Tests

`make test` runs pytest with `MOCK_PROVIDERS=true` and `USE_FINETUNED_CODE=false` for deterministic CI-style checks.

---

## 11. Paper ↔ implementation alignment (short)

| Paper claim | Implementation status on this host |
|-------------|-------------------------------------|
| Dual-LLM + 3-VLM + \(S\)/\(A\) gates | **Implemented** in `app/services/scoring.py` + orchestration |
| Design-phase UML types + flowchart | Supported in app; 50k corpus also includes sequence/usecase/state/deployment |
| 8,000 verified dataset release | Design parquet **8k** on disk; large-scale **paper** metrics not re-verified with LoRA |
| DeepSeek-32B Stage 2 | **Stand-in** LoRA 0.5B (+ builder fallback) |
| Human–VLM correlation | UI ready; **no** local human labels yet |
| Public app | Local + tunnels / optional Render |

---

## 12. How to use this report in a venue paper

Suggested mapping:

1. **Method** ← §§2–3, 6 (architecture, models, gates).  
2. **Data** ← §4 (cite measured tables; separate paper 8k generation claim from HF training corpora).  
3. **Experimental setup** ← §§5, 7 (hardware, LoRA hyperparams, dual Ollama).  
4. **Results** ← Prefer paper tables for DeepSeek-32B pipeline; add a clearly labeled **“Local Apple Silicon replication / smoke”** subsection from §8.  
5. **Limitations** ← §9.  
6. **Availability** ← GitHub URL, MIT license, Overleaf link.

---

## Appendix A — Composite formula (copy-ready)

\[
S_i = \delta(s_i)\cdot\frac{\sum_{j=1}^{3} w_j s_{ij}}{\sum_{j=1}^{3} w_j},\quad
w=(53.1,50.7,39.9),\quad
v_{ij}=\mathbf{1}[s_{ij}\ge 4],\quad
A_i=\mathbf{1}\Big[\sum_j v_{ij}\ge 2\Big]
\]

Dataset: \(A_i=1\) and \(S_i\ge 3\).

## Appendix B — Provenance of measured numbers

| Number | Source |
|--------|--------|
| M1 Ultra / 128 GB / 20 cores | `system_profiler SPHardwareDataType` |
| Ollama 0.24.0 / 0.32.1 | `GET :11434|:11435/api/version` |
| Parquet / JSONL row counts | `pyarrow` / line counts 2026-08-26 |
| LoRA 3000 iters | `models/uml-plantuml-lora/finetune_meta.json` |
| DB job/score stats | `data/uml_app.db` |
| 50k train in progress | `data/training/finetune_50k.log`, live `mlx_lm` process |
| Paper render table | `paper/main.tex` (not re-executed) |

---

*End of report. Primary deliverable path: `reports/PUBLICATION_TECHNICAL_REPORT.md`.*
