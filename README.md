# UML-Pipeline

**Author:** [Dipak Yadav](https://github.com/dipak5501)  
**Repository:** [github.com/dipak5501/uml-generation-pipeline](https://github.com/dipak5501/uml-generation-pipeline)

End-to-end application that turns plain-English software requirements **or source code** into design-phase UML diagrams (**Class, Object, Component, Package, Flowchart**), renders them as **black-and-white** PlantUML PNGs, scores them with a multimodal VLM ensemble (weighted composite **S** + majority-vote gate **A**), and supports human evaluation, analytics, and dataset export.

This repository implements the system described in **Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design** (Dipak Yadav, Yutong Zhao).

**Full architecture:** [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md)

---

## Production stack (Mac Studio)

The primary deployment runs on an **Apple Mac Studio (M1 Ultra, 128 GB)** with **no Azure dependency**:

| Component | Production default |
|-----------|-------------------|
| API / UI | FastAPI `:8000` + Streamlit `:8501` |
| Database | SQLite `data/uml_app.db` |
| Spec LLM | Ollama `llama3.2:1b` |
| PlantUML | MLX LoRA Qwen2.5-0.5B (`models/uml-plantuml-lora-50k`; **100k adapter training in progress**) |
| VLM #1 | Ollama **0.32** `:11435` → `qwen2.5vl:3b` |
| VLM #2 | Ollama **0.24** `:11434` → `llama3.2-vision:11b` |
| VLM #3 | Local Transformers **Aya-Vision-8B** (`VLM_AYA_BACKEND=local`) |
| Public access | Cloudflare quick tunnels + user LaunchAgents |
| Supervision | `scripts/install_macos_user_server.sh` |

```bash
# Always-on server (survives Cursor quit; no sudo)
bash scripts/install_macos_user_server.sh
bash scripts/macos_server_status.sh
```

---

## Architecture

```mermaid
flowchart LR
  A[Requirement / Code] --> B[Tech Spec LLM]
  B --> C[PlantUML LoRA / LLM]
  C --> D[Validate / Repair]
  D --> E[PlantUML Render Gate]
  E --> F[3 VLMs]
  F --> G[Composite S + Majority A]
  G --> H[Dataset gate A and S≥3]
  H --> I[SQLite + UI]
```

---

## Quick start (local)

```bash
git clone https://github.com/dipak5501/uml-generation-pipeline.git
cd uml-generation-pipeline

make install
cp .env.example .env   # MOCK_PROVIDERS=true for offline demo

# One command (API :8000 + UI :8501)
make run

# Or two terminals:
# make api
# make ui
```

- Streamlit UI: http://127.0.0.1:8501  
- API docs: http://127.0.0.1:8000/docs  

### Live local stack (Ollama + LoRA + Aya)

```bash
# Dual Ollama (0.24 on :11434, 0.32 on :11435) — started by make run
ollama pull llama3.2:1b qwen2.5vl:3b llama3.2-vision:11b

# In .env:
MOCK_PROVIDERS=false
USE_OLLAMA=true
USE_HF_INFERENCE=false
USE_FINETUNED_CODE=true
FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-50k
VLM_AYA_BACKEND=local

make run
bash scripts/restart_api.sh   # after .env changes when using LaunchAgents
```

Setup helper for paper-exact Aya: `bash scripts/setup_paper_aya_local.sh`

### Public demo (Cloudflare tunnels)

```bash
bash scripts/start_public_tunnels.sh
# URLs → data/run/public_ui_url.txt
```

Set `API_ACCESS_TOKEN` in `.env` before exposing tunnels. Streamlit attaches Bearer auth automatically.

---

## Training corpus and LoRA

| Stage | Command | Output |
|-------|---------|--------|
| 8k starter | `make training-corpus` | `data/training/uml_training_8000.parquet` |
| 50k HF/web | `make train-50k` | `models/uml-plantuml-lora-50k` (**complete**, 15k iters) |
| 100k combined | `make train-100k` | `models/uml-plantuml-lora-100k` (**in progress**, target 18k iters) |

Corpus merges open Hugging Face UMLCode datasets with web PlantUML and a **50k source-code block** (`input_mode=source_code`). Details: [models/README.md](models/README.md), [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md#8-data-lake-and-training-design).

After training completes, point `.env` at the new adapter and restart the API:

```bash
FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-100k
bash scripts/restart_api.sh
```

---

## Model providers

| Mode | Config | Notes |
|------|--------|-------|
| Mock (default) | `MOCK_PROVIDERS=true` | Offline; no API keys |
| **Ollama (production)** | `MOCK_PROVIDERS=false` `USE_OLLAMA=true` | Dual-host for Qwen-VL + LLaMA-Vision |
| LoRA PlantUML | `USE_FINETUNED_CODE=true` | Apple Silicon MLX; Stage 2 only |
| Local Aya VLM | `VLM_AYA_BACKEND=local` | Paper-exact 3rd scorer; not on Ollama |
| Hugging Face | `USE_HF_INFERENCE=true` + `HF_TOKEN` | Optional cloud inference |
| OpenAI-compatible | `OPENAI_API_KEY` | vLLM / cloud fallback |

Composite score (thesis formula): MMMU-weighted average of all three VLM scores (0–6; zeros count). Render failure forces **S = 0**. Dataset entry requires majority **A = 1** (τ = 4, ≥ 2/3 models) and **S ≥ 3**.

---

## UI pages

1. Dashboard  
2. Single Generation (full artifact trace)  
3. Batch Generation  
4. Generated Diagrams (history gallery)  
5. Human Evaluation (rubric)  
6. Analytics + export links  
7. Settings / health  
8. System Design (architecture overview)  

---

## API highlights

Auth (when `API_ACCESS_TOKEN` set): `Authorization: Bearer <token>` or `X-API-Key`.

- `POST /api/generate` — `input_mode`: `requirement` | `source_code`  
- `POST /api/generate/batch`  
- `GET /api/jobs/{id}`  
- `GET /api/artifacts/{id}` (+ `/image`, `/plantuml`)  
- `POST /api/artifacts/{id}/rescore` / `/repair`  
- `POST /api/human-review`  
- `GET /api/analytics/summary` / `/distributions`  
- `GET /api/export/dataset?fmt=jsonl|csv|parquet`  
- `GET /api/settings/health`  

---

## Project layout

```
app/           FastAPI + SQLModel services, provider factory, orchestration
ui/            Streamlit multipage UI
uml_pipeline/  Research pipeline (render, scoring, LLM client)
prompts/       Versioned prompt templates
models/        MLX LoRA adapters (50k complete, 100k in progress)
data/          SQLite, artifacts, training corpora, tunnel state
scripts/       Deploy, training, tunnels, LaunchAgents
docs/          SYSTEM_DESIGN.md, deploy, demo flow, gap analysis
tests/         Unit + API + e2e smoke tests
paper/         LaTeX paper (Overleaf sync)
```

---

## Deployment options

| Environment | Guide |
|-------------|-------|
| **Mac Studio (production)** | [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md#9-deployment-and-operations) |
| Render / Railway / Docker | [docs/deploy.md](docs/deploy.md) |
| GitHub Pages landing | https://dipak5501.github.io/uml-generation-pipeline/ |

---

## PlantUML / Java

Rendering requires a JDK. The PlantUML jar auto-downloads to `tools/plantuml.jar` on first render.

```bash
make install-java   # or: brew install --cask temurin
```

Check health: `GET /api/settings/health`

---

## Demo and tests

```bash
make demo          # mock single artifact
make test          # pytest
make smoke         # live API smoke
```

---

## Research paper / Overleaf

**Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design** — see [paper/README.md](paper/README.md). Technical report: [reports/PUBLICATION_TECHNICAL_REPORT.md](reports/PUBLICATION_TECHNICAL_REPORT.md).

---

## Legacy CLI (still available)

| Task | Command |
|------|---------|
| Download benchmark data | `python scripts/download_datasets.py` |
| Render diagrams | `python scripts/render_diagrams.py --limit 20` |
| Analyze scores | `python scripts/analyze_dataset.py` |
| Generate (legacy batch) | `python scripts/run_generation.py --diagram-type class -n 10` |

---

## License

MIT — see [LICENSE](LICENSE).
