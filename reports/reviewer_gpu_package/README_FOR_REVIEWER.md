# Reviewer GPU Package — One-Page Guide

**Student:** Dipak Yadav  
**Paper:** *Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design*  
**Repository:** https://github.com/dipak5501/uml-generation-pipeline  
**Date:** 2026-08-28

---

## What is in this package

| Item | Description |
|------|-------------|
| `SAMPLE_DATA/` | Representative inputs: requirements, Python sample, 5 NL golden cases, 5 source-code cases (Java/Python/C), 10-line finetune JSONL sample, data-lake excerpt |
| `CLAUDE_CODE_GPU_PROMPT.md` | Complete prompt to paste into Cursor / Claude Code on a GPU machine |
| `README_FOR_REVIEWER.md` | This guide |
| `ONEDRIVE_UPLOAD_INSTRUCTIONS.md` | Steps for Dipak to zip and share via OneDrive |

**Detailed progress report (paper draft):** `../REVIEWER_PROGRESS_REPORT.md` (also in repo root under `reports/`)

---

## Live demo (Mac Studio server)

| Service | URL (2026-08-27) |
|---------|------------------|
| **Streamlit UI** | https://orange-fountain-especially-positive.trycloudflare.com |
| **FastAPI API** | https://easter-replication-mug-dee.trycloudflare.com |
| **Remote agent** | https://easter-replication-mug-dee.trycloudflare.com/api/agent |

> Cloudflare **quick tunnels** rotate URLs on restart. Check `Link` in the repo or ask Dipak for current URLs.

**Production adapter:** `models/uml-plantuml-lora-sourcecode-30k` (30k Java/Python/C LoRA, warm-started from 200k)

---

## Quick verification (reviewer machine)

```bash
git clone https://github.com/dipak5501/uml-generation-pipeline.git
cd uml-generation-pipeline
make install && make test          # expect 153 passed (offline, mock providers)
```

For **live GPU/VLM** reproduction, open `CLAUDE_CODE_GPU_PROMPT.md` and follow Path A (Apple Silicon) or Path B (NVIDIA CUDA).

---

## Key results (Mac Studio, Aug 2026)

| Metric | Result |
|--------|--------|
| Pytest | **153 / 153** pass |
| Golden cases | **21 / 21** (6 NL + 15 source-code) |
| Live source smoke | **9 / 9** render success |
| VLM composite scores (smoke) | **4.72 – 6.00** |

---

## Platform honesty

- Student runs on **Apple Mac Studio M1 Ultra (128 GB)** with **MLX LoRA**, not NVIDIA CUDA.
- Full paper pipeline is implemented; Stage 2 uses a **0.5B LoRA stand-in** for paper’s DeepSeek-32B on this hardware.
- NVIDIA reviewers should use Ollama/HF inference paths or retrain LoRA with PyTorch (see GPU prompt).

---

## Contact / next steps

- Dipak will upload this zip to **OneDrive** and share the link with the reviewer.
- Reviewer will share **Overleaf** link for paper draft integration.
- Questions: refer to `reports/REVIEWER_PROGRESS_REPORT.md` and `docs/SYSTEM_DESIGN.md`.
