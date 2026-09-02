# Cursor GPU handoff

Use this on a **new computer with a GPU**, signed into the **same Cursor account**.
Chat history does **not** follow you. Open the repo in Cursor and paste the **prompt in section 8**.

Repo: https://github.com/dipak5501/uml-generation-pipeline

Do **not** commit `.env`, tokens, or `models/`. Copy secrets privately.

---

## 1. Open the project in Cursor (new device)

1. Install Cursor and sign in with the **same** Cursor account.
2. Get the code:

```bash
git clone https://github.com/dipak5501/uml-generation-pipeline.git
cd uml-generation-pipeline
```

   Optional: copy from the old Mac (keeps LoRA + DB, gitignored):

   - `models/uml-plantuml-lora/` (Apple MLX adapters — **only useful on Apple Silicon**)
   - `data/` (SQLite, training parquet — large)
   - `.env` (tokens — never commit)

3. In Cursor: **File → Open Folder** → that clone.
4. New Agent chat. Paste the prompt in section 8.

---

## 2. What this application is

**UML-Pipeline** (Dipak Yadav / Yutong Zhao): requirement or code → spec LLM → PlantUML (LoRA or LLM) → render → **3 VLMs** (paper ensemble) → composite **S** and majority **A**.

| Stage | Paper models | How we ran it on the M2 Mac (24 GB) |
|--------|----------------|-------------------------------------|
| Spec | Llama-3.2-1B | Ollama `llama3.2:1b` |
| PlantUML | DeepSeek-32B stand-in | **MLX LoRA** `mlx-community/Qwen2.5-0.5B-Instruct-4bit` + `models/uml-plantuml-lora` |
| VLM 1 | Qwen2.5-VL-3B (w=53.1) | Ollama `qwen2.5vl:3b` (needs Ollama **0.32** on `:11435`) |
| VLM 2 | LLaMA-3.2-Vision-11B (w=50.7) | Ollama `llama3.2-vision:11b` (needs Ollama **0.24** on `:11434`; **0.32 cannot run mllama**) |
| VLM 3 | Aya-Vision-8B (w=39.9) | **Not** on Ollama. Do **not** load in-process on 24 GB Mac (MPS hang). GPU: **vLLM**. Azure Students **cannot** create T4 VMs (`ResourceNotAvailableForOffer`). Kaggle T4 batch worked. |

Gates: τ=4, majority ≥2 of 3, dataset if A and S≥3.

Start script: `./scripts/run_local.sh` → API `:8000`, UI `:8501`.

---

## 3. Hardware split (critical)

### Apple Silicon GPU (M-series iMac / Mac Studio)

**Verified target device:** Mac Studio (`Mac13,2`), **Apple M1 Ultra**, **128 GB** unified memory. That is **not** NVIDIA CUDA. Do **not** run `make finetune-cuda` or `scripts/finetune_plantuml_cuda.py` on it.

Use the Apple stack:

- `make install` / `make install-java` / `make train-real` (**MLX** LoRA)
- Dual Ollama: `scripts/ensure_ollama_dual.sh` (0.24 `:11434` for LLaMA-Vision, 0.32 `:11435` for Qwen2.5-VL)
- Copy `models/uml-plantuml-lora/` from the old Mac if you already trained it (MLX adapters **are** useful here)
- Aya-Vision-8B: **128 GB is enough** for `VLM_AYA_BACKEND=local` (transformers on MPS). The old **24 GB** M2 hung on `model.to("mps")` — that guard still applies below 64 GB. Do **not** use NVIDIA vLLM on this Mac.

`.env` on the Mac Studio (live, not mock):

```bash
MOCK_PROVIDERS=false
USE_OLLAMA=true
USE_HF_INFERENCE=false
USE_FINETUNED_CODE=true
FINETUNED_BASE_MODEL=mlx-community/Qwen2.5-0.5B-Instruct-4bit
FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora
USE_AYA=true
VLM_AYA_BACKEND=local
VLM_MODELS=qwen2.5vl:3b,llama3.2-vision:11b,aya-vision:8b
VLM_FAST_MODE=false
```

Put `HF_TOKEN` only in that machine’s `.env`. Never commit it.

### NVIDIA GPU (Linux / Windows + CUDA)

**MLX LoRA adapters will not run.** Do not enable `USE_FINETUNED_CODE=true` with those files.

On NVIDIA the agent should:

1. Download the **same Hugging Face training corpora** (`make training-corpus` / `scripts/build_training_corpus.py --target 8000 --include-flowchart`).
2. Retrain PlantUML LoRA with **PyTorch + PEFT + CUDA** (`scripts/finetune_plantuml_cuda.py`, `make finetune-cuda`). Do not call `mlx_lm`.
3. Serve **Aya-Vision-8B** with vLLM (OpenAI-compat) and set:

```bash
USE_AYA=true
VLM_AYA_BACKEND=openai_compat
AYA_VLM_MODEL=CohereLabs/aya-vision-8b
AYA_VLM_BASE_URL=http://127.0.0.1:8001/v1
```

   (Use port **8001** if FastAPI already owns **8000**. Helper: `bash scripts/serve_aya_vllm.sh`.)

4. Qwen + LLaMA-Vision: vLLM, Hugging Face Transformers+CUDA, or Ollama-with-GPU.

Accept Aya license: https://huggingface.co/CohereLabs/aya-vision-8b
Set `HF_TOKEN` (never put it in git or a public notebook).

---

## 4. Datasets to download (do all of this)

### Training corpus (open HF UMLCode)

```bash
python scripts/build_training_corpus.py --target 8000 --include-flowchart
```

Repos (see `scripts/build_training_corpus.py`):

- `nguyenvanviet/UMLCode-ClassDiagram-DeepSeek-32B-Reasoning-RAW`
- `nguyenvanviet/UMLCode_ObjectDiagram_Scored`
- `nguyenvanviet/UMLCode_ComponentDiagram_Scored`
- `nguyenvanviet/UMLCode_PackageDiagram_Scored`
- `nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-UC-Class-Sequence-Scored`
- flowchart: `nguyenvanviet/UMLCode_Activity_Final`
- top-up: `nguyenvanviet/UMLCode_DeploymentDiagram`

Outputs (gitignored): `data/training/uml_training_8000.parquet`, manifest.

### Fine-tune JSONL + extra pairs

```bash
make scenario-corpus    # or scripts/build_scenario_code_corpus.py
make finetune-prepare   # data/finetune/{train,valid,test}.jsonl
```

### Optional gated class scored set — skip if you do not have access

`nguyenvanviet/UMLCode-ClassDiagram-DeepSeek-32B-Scored` is **not required**.
The 8k training corpus already uses the **open** class RAW repo
(`UMLCode-ClassDiagram-DeepSeek-32B-Reasoning-RAW`, ~5k rows) plus object/component/package scored sets.

If Hugging Face still says “ask for access” on the *Scored* page, ignore it and continue.
Do not block Mac Studio setup, LoRA training, or live VLM scoring on that dataset.

```bash
# only if the owner later grants you access:
python scripts/download_datasets.py --include-gated --only class --skip-errors
```

### Kaggle batch (optional GPU Aya scoring)

Private kernel: `dipakyadav01/uml-vlm-gpu-score`
Dataset: `dipakyadav01/uml-pipeline-diagrams` (24 PNGs + `manifest.json`)
Version 11 already scored 24 diagrams on **2× T4**. Many stored scores of **0** were parse failures (`SEMANTIC: <0-6>` placeholder).
Kaggle is **not** the live HTTP scorer for the Streamlit app.

---

## 5. Training (PlantUML LoRA)

**Apple Silicon only (existing code):**

```bash
make train-real
# or: make finetune-prepare && make finetune
```

Writes `models/uml-plantuml-lora/`. Then `.env`:

```bash
USE_FINETUNED_CODE=true
FINETUNED_BASE_MODEL=mlx-community/Qwen2.5-0.5B-Instruct-4bit
FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora
FINETUNED_MAX_TOKENS=1536
```

**NVIDIA:**

```bash
make train-real          # auto-detects CUDA and calls finetune_plantuml_cuda.py
# or: make finetune-cuda
```

Uses `Qwen/Qwen2.5-0.5B-Instruct` + PEFT. Then `.env`:

```bash
USE_FINETUNED_CODE=true
FINETUNED_BASE_MODEL=Qwen/Qwen2.5-0.5B-Instruct
FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora
FINETUNED_MAX_TOKENS=1536
```

---

## 6. App `.env` (live, not mock)

**Mac Studio M1 Ultra 128 GB (Apple path):**

```bash
MOCK_PROVIDERS=false
USE_OLLAMA=true
USE_HF_INFERENCE=false
USE_FINETUNED_CODE=true
FINETUNED_BASE_MODEL=mlx-community/Qwen2.5-0.5B-Instruct-4bit
FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora
USE_AYA=true
VLM_AYA_BACKEND=local
VLM_MODELS=qwen2.5vl:3b,llama3.2-vision:11b,aya-vision:8b
VLM_FAST_MODE=false
PLANTUML_PREFER_LOCAL=true
ACCEPTANCE_TAU=4.0
MIN_COMPOSITE_FOR_DATASET=3.0
```

**NVIDIA only** (not the Mac Studio):

```bash
MOCK_PROVIDERS=false
USE_OLLAMA=true          # or false if all VLMs are vLLM
USE_HF_INFERENCE=false
USE_FINETUNED_CODE=true
FINETUNED_BASE_MODEL=Qwen/Qwen2.5-0.5B-Instruct
USE_AYA=true
VLM_AYA_BACKEND=openai_compat
AYA_VLM_BASE_URL=http://127.0.0.1:8001/v1
VLM_MODELS=qwen2.5vl:3b,llama3.2-vision:11b,aya-vision:8b
VLM_FAST_MODE=false
```

Copy `HF_TOKEN` from the old Mac `.env` (do not paste into chat).

Start:

```bash
make install
make install-java   # macOS; on Linux install a JDK 17+
./scripts/run_local.sh
```

UI: http://127.0.0.1:8501

Parser: `uml_pipeline/llm_client.py` `extract_vlm_score` must accept `**SEMANTIC: 5**` and must not treat `<0-6>` as a live score of 0.

---

## 7. What we already learned (do not repeat mistakes)

- Azure for Students: T4 quota **0**; increase failed `ResourceNotAvailableForOffer`. CPU ACI Aya was slow and **timed out** in the live app.
- Do not load Aya with `model.to("mps")` on **24 GB**. On **Mac Studio M1 Ultra 128 GB**, `VLM_AYA_BACKEND=local` is the paper path (unified memory is enough).
- One Ollama **0.32** cannot run LLaMA-Vision (`mllama`). Dual servers: 0.24 `:11434` + 0.32 `:11435`.
- Generate jobs are **in-process**; restarting the API kills them. Status polls must not report “API offline” on slow VLM calls.
- Interactive UI on one LAN Mac: `./scripts/run_local.sh`, bind `0.0.0.0`, don’t sleep the machine.
- Stop Azure: `bash scripts/stop_azure_aya.sh`. Stop Kaggle GPU sessions when idle.

---

## 8. Prompt to paste into Cursor on the GPU machine

Copy everything between the lines:

----- BEGIN PROMPT -----

You are setting up UML-Pipeline from scratch on THIS machine (it has a GPU). Full handoff: `docs/CURSOR_GPU_HANDOFF.md` in the repo.

Goal: download all training/eval datasets, train (or CUDA-retrain) the PlantUML generator, run Aya-Vision-8B, run Qwen2.5-VL-3B and LLaMA-3.2-Vision-11B as the other two paper VLMs, start FastAPI :8000 + Streamlit :8501, verify a generate+score with all three VLMs returning numeric scores.

Repo: clone https://github.com/dipak5501/uml-generation-pipeline.git if not already open.

Detect GPU first:
- **Apple Silicon (including Mac Studio M1 Ultra 128 GB):** MLX LoRA (`make train-real` / `scripts/finetune_plantuml.py`). Dual Ollama (0.24 `:11434` llama3.2-vision:11b, 0.32 `:11435` qwen2.5vl:3b). Aya: `VLM_AYA_BACKEND=local` (128 GB is enough; do **not** use CUDA scripts or vLLM). Copy existing `models/uml-plantuml-lora/` from the old Mac if present.
- **NVIDIA CUDA:** download the same HF corpora, prepare `data/finetune/*.jsonl`, train PEFT with `scripts/finetune_plantuml_cuda.py` (do not use mlx_lm), serve Aya with vLLM on port 8001, wire `.env` `VLM_AYA_BACKEND=openai_compat`.

Steps:
1. `make install` (and Java/PlantUML). Copy HF_TOKEN into `.env` from the user (never commit, never print).
2. `python scripts/build_training_corpus.py --target 8000 --include-flowchart`
3. `make scenario-corpus` then `make finetune-prepare`
4. Train: `make train-real` on Apple; CUDA LoRA only on NVIDIA.
5. Pull/serve VLMs. Aya: accept CohereLabs/aya-vision-8b license. On 24 GB Mac do not load Aya in-process; on 128 GB Mac Studio local MPS is OK.
6. `.env`: MOCK_PROVIDERS=false, VLM_FAST_MODE=false, USE_AYA=true, paper VLM_MODELS, USE_FINETUNED_CODE if adapters exist for this platform. Apple: VLM_AYA_BACKEND=local USE_OLLAMA=true. NVIDIA: openai_compat + :8001.
7. `./scripts/run_local.sh`. Health: http://127.0.0.1:8000/api/settings/health
8. Generate one class diagram with VLM scoring on. Confirm three model keys qwen25vl3b, llama32vl11b, aya_vision_8b are available≠0 timeout.

Do not convert Azure to PAYG. Do not put secrets in notebooks or git. Prefer this machine’s GPU over Azure student VMs (T4 blocked) and over Kaggle for the live app.

----- END PROMPT -----
