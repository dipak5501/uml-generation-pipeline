# Claude Code / Cursor GPU Reproduction Prompt

Copy everything between **BEGIN PROMPT** and **END PROMPT** into a new Cursor Agent chat (or Claude Code session) on a machine with GPU access.

---

## BEGIN PROMPT

You are reproducing **UML-Pipeline** from scratch on **THIS machine**. The student (Dipak Yadav) has prepared sample data in `reports/reviewer_gpu_package/SAMPLE_DATA/` alongside this file.

**Paper:** *Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design*  
**Repo:** https://github.com/dipak5501/uml-generation-pipeline  
**Full handoff doc in repo:** `docs/CURSOR_GPU_HANDOFF.md`

### Goal

1. Clone and install the pipeline.  
2. Run offline tests (`make test` → expect **153** pass).  
3. Start the live stack with **real** providers (`MOCK_PROVIDERS=false`).  
4. Generate at least one NL requirement and one source-code case from the sample golden files.  
5. Confirm three VLMs return numeric scores; composite *S* and majority *A* are computed.  
6. Report results in a short summary (render OK, *S*, *A*, per-VLM scores).

---

### Step 0 — Detect hardware

```bash
uname -m
python3 -c "import torch; print('cuda:', torch.cuda.is_available())" 2>/dev/null || echo "no torch"
system_profiler SPHardwareDataType 2>/dev/null | head -5 || true
```

**Branch:**

| Platform | PlantUML Stage 2 | VLM serving |
|----------|------------------|-------------|
| **Apple Silicon (M-series)** | MLX LoRA (`USE_FINETUNED_CODE=true`) | Dual Ollama + local Aya |
| **NVIDIA CUDA (Linux/Windows)** | **No MLX** — use Ollama/HF or CUDA LoRA retrain | vLLM / Ollama GPU / HF Inference |

---

### Step 1 — Clone and install

```bash
git clone https://github.com/dipak5501/uml-generation-pipeline.git
cd uml-generation-pipeline
make install
make install-java    # macOS script; on Linux: install OpenJDK 17+
cp .env.example .env
```

**Never commit `.env`, tokens, or `models/` adapters.**

---

### Step 2 — Configure `.env` (choose ONE path)

#### Path A — Mac Studio / Apple Silicon (matches student production)

```bash
MOCK_PROVIDERS=false
USE_OLLAMA=true
USE_HF_INFERENCE=false
USE_FINETUNED_CODE=true
FINETUNED_BASE_MODEL=mlx-community/Qwen2.5-0.5B-Instruct-4bit
FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-sourcecode-30k
FINETUNED_MAX_TOKENS=1536
VLM_AYA_BACKEND=local
AYA_VLM_MODEL=CohereLabs/aya-vision-8b
VLM_FAST_MODE=false
PLANTUML_PREFER_LOCAL=true
ACCEPTANCE_TAU=4.0
MIN_COMPOSITE_FOR_DATASET=3.0
SPEC_MODEL=meta-llama/Llama-3.2-1B-Instruct
VLM_MODELS=qwen2.5vl:3b,llama3.2-vision:11b,aya-vision:8b
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_QWEN_BASE_URL=http://127.0.0.1:11435
```

Then:

```bash
bash scripts/ensure_ollama_dual.sh
ollama pull llama3.2:1b qwen2.5vl:3b llama3.2-vision:11b
bash scripts/setup_paper_aya_local.sh   # accept HF license first
```

**Note:** MLX LoRA adapters are **not in git**. Copy `models/uml-plantuml-lora-sourcecode-30k/` from the student’s Mac Studio privately, **or** retrain:

```bash
make train-source30k   # long; needs corpora downloaded first
```

#### Path B — NVIDIA GPU (CUDA) — no MLX

```bash
MOCK_PROVIDERS=false
USE_OLLAMA=true          # if Ollama with GPU is available
# OR:
USE_HF_INFERENCE=true    # needs HF_TOKEN + Inference Providers
USE_FINETUNED_CODE=false # unless you CUDA-retrain LoRA separately
VLM_AYA_BACKEND=openai_compat
AYA_VLM_MODEL=CohereLabs/aya-vision-8b
AYA_VLM_BASE_URL=http://127.0.0.1:8001/v1
VLM_FAST_MODE=false
PLANTUML_PREFER_LOCAL=true
ACCEPTANCE_TAU=4.0
MIN_COMPOSITE_FOR_DATASET=3.0
HF_TOKEN=<set privately>
```

Serve Aya with vLLM on port **8001** (FastAPI uses **8000**):

```bash
# Example (adjust for your vLLM install):
python -m vllm.entrypoints.openai.api_server \
  --model CohereLabs/aya-vision-8b --port 8001
```

For Qwen + LLaMA-Vision: Ollama with GPU, vLLM, or HF Inference.

**CUDA LoRA retrain (optional, not in repo as MLX):**

```bash
make finetune-prepare   # builds data/finetune/*.jsonl
# Implement PyTorch+PEFT training from same JSONL — do NOT use mlx_lm
```

---

### Step 3 — Offline tests (no GPU required)

```bash
make test
# Expected: 153 passed
```

Golden cases (structural, mock providers):

```bash
PYTHONPATH=. MOCK_PROVIDERS=true USE_FINETUNED_CODE=false \
  pytest tests/test_acceptance.py -q
# Expected: 21 golden parametrized tests pass (6 NL + 15 source)
```

---

### Step 4 — Start live stack

```bash
./scripts/run_local.sh
# API: http://127.0.0.1:8000
# UI: http://127.0.0.1:8501
```

Health check:

```bash
curl -s http://127.0.0.1:8000/api/settings/health | python3 -m json.tool
```

Set `API_ACCESS_TOKEN` in `.env` for authenticated generate calls.

---

### Step 5 — Smoke tests

**API smoke:**

```bash
make smoke
```

**Source-code golden live smoke (9 cases, needs live API + token):**

```bash
python scripts/smoke_source_code_golden.py
# Expected on Mac Studio production stack: 9/9 render success, VLM scores ~4.7–6.0
```

**Manual generate — NL requirement** (from sample):

```bash
curl -X POST http://127.0.0.1:8000/api/generate \
  -H "Authorization: Bearer $API_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "requirement": "Library management system with classes Book, Member, Loan, and Librarian. A Member borrows a Book through a Loan.",
    "diagram_type": "class",
    "async_mode": false
  }'
```

**Manual generate — source code** (from `SAMPLE_DATA/golden_source/SC-PY-01.py`):

```bash
SOURCE=$(cat reports/reviewer_gpu_package/SAMPLE_DATA/golden_source/SC-PY-01.py)
curl -X POST http://127.0.0.1:8000/api/generate \
  -H "Authorization: Bearer $API_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c "import json,os; print(json.dumps({'requirement': open('reports/reviewer_gpu_package/SAMPLE_DATA/golden_source/SC-PY-01.py').read(), 'diagram_type': 'class', 'input_mode': 'source_code', 'async_mode': False}))")"
```

---

### Step 6 — Training commands (optional, Apple Silicon only)

```bash
make training-corpus              # 8k HF UML corpus
make training-corpus-50k            # 50k scale-up
make train-50k                      # 50k + LoRA 15k iters
make train-100k                     # 100k combined
make train-200k                     # 200k v2
make train-source30k                # 30k Java/Python/C → production adapter
```

Download all HF mirrors:

```bash
make download-all-corpora
```

---

### Step 7 — Expected outputs

| Check | Expected |
|-------|----------|
| `make test` | 153 passed |
| Golden acceptance | 21/21 (mock mode) |
| `/api/settings/health` | `status: ok`, providers listed |
| Generate response | `render_status: success`, PNG artifact path |
| VLM scores | Three model keys with scores 0–6 |
| Composite *S* | Weighted mean using w=(53.1, 50.7, 39.9) |
| Majority *A* | true if ≥2 VLMs score ≥ τ=4 |
| Live source smoke | 9/9 render + correct language detection |

---

### Step 8 — Do NOT

- Commit `.env`, `HF_TOKEN`, or API tokens.  
- Assume MLX adapters work on NVIDIA — they do not.  
- Load Aya in-process on ≤24 GB RAM Mac (MPS hang).  
- Use one Ollama 0.32 for both Qwen-VL and LLaMA-Vision (mllama incompatibility).  
- Treat quick-tunnel URLs as permanent.

---

### Deliver back to reviewer

Short report:

1. Platform detected (Apple / NVIDIA).  
2. `make test` result.  
3. One NL + one source-code generate: render OK, *S*, *A*, per-VLM scores.  
4. Any blockers (missing adapter, HF license, Ollama version).

## END PROMPT

---

*Package prepared 2026-08-28 for reviewer OneDrive upload.*
