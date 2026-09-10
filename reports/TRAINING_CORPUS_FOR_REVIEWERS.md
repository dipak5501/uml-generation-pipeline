# Training corpus for reviewers (Mac Studio live stack)

**Purpose:** One place for committee / reviewers to see what corpus the **live production app** was trained on, how that differs from the **paper DeepSeek** setup, and which other adapters exist on disk.

**As of:** 2026-09-10 (live health + on-disk manifests).  
**Do not start a new training run from this document** — it is inventory only.

---

## Claim hygiene (read first)

| Claim | Correct framing |
|-------|-----------------|
| Paper Stage 2 | **DeepSeek-R1-Distill-Qwen-32B** on a design/eval set of **n ≈ 8,000** (4 diagram types × 4 domains × 500). Paper metrics ≠ Mac Studio metrics. |
| Live Stage 2 | **MLX LoRA** on `mlx-community/Qwen2.5-0.5B-Instruct-4bit` — a **stand-in** with the same pipeline gates (S / A / dataset). |
| Filename `uml_training_8000.*` | On disk this parquet is **50,000** rows (50k scale-up kept the old name). Cite measured counts, not the filename. |
| “Trained on 30k” | Production **focus** corpus is **30k** Java/Python/C source→UML rows; the finetune parquet also **merges prior ~200k** combined data (**224,349** rows total). Warm-start weights come from the 200k adapter. |
| Industrial / adaptation adapters | Present or in progress under `models/` — **not** pointed at by live `.env`. |

---

## 1. What is serving production NOW

Verified from `.env` and live `GET /api/settings/health` on this Mac Studio:

| Field | Value |
|-------|--------|
| `USE_FINETUNED_CODE` | `true` |
| Live adapter path | **`models/uml-plantuml-lora-sourcecode-30k`** |
| Health `provider` | `finetuned-mlx` (`spec/VLM=ollama · code=finetuned-mlx`) |
| Adapter present | yes |
| Base model | `mlx-community/Qwen2.5-0.5B-Instruct-4bit` |
| Train recipe | `make train-source30k` |
| Iters completed | **6,000** (`finetune_meta.json`) |
| Adapter file date | **2026-08-27** |
| Warm-start | Copied from `models/uml-plantuml-lora-200k` before the 6k run |

**Corpus the production adapter maps to**

| Layer | Artifact | Approx. *n* | Role |
|-------|----------|-------------|------|
| Focus (named “sourcecode-30k”) | `data/training/uml_source_code_30k_jpc.parquet` | **30,000** | 10k Java + 10k Python + 10k C |
| Finetune input (actual JSONL source) | `data/training/uml_training_combined_sourcecode_30k.parquet` | **224,349** | 30k JPC **merged with** prior 200k combined corpus |
| Manifest | `data/training/language_source_manifest.json` | — | Per-language sources |

**30k focus sources** (`language_source_manifest.json`):

- Java: Hugging Face `code-search-net` (java) — 10k  
- Python: `code-search-net` (python) 5k + `semeru/code-text-python` 5k  
- C: CodeParrot-style `.c` stream + **synthetic_topup_c** when the public pool is exhausted (10k C rows)

**Diagram types in the combined 224k finetune parquet** (measured): class 76,094; package 34,385; flowchart 33,300; component 29,340; object 23,093; sequence 12,883; usecase 11,302; deployment 2,035; state 1,917.  
API generation types remain **class / object / component / package** (flowchart may appear in training data only).

**Paper vs live (one sentence):** Paper numbers are DeepSeek-32B @ n=8k design set; live PlantUML is a 0.5B LoRA trained primarily on a 30k Java/Python/C source-code UML mix (warm-started from a larger HF/stack/synthetic lineage).

---

## 2. Adapter inventory (`models/`)

| Adapter path | Train command | Corpus (approx *n*) | Iters | Status / date |
|--------------|---------------|---------------------|-------|---------------|
| **`uml-plantuml-lora-sourcecode-30k`** | **`make train-source30k`** | 30k JPC + merge → **224k** combined parquet | 6,000 | **PRODUCTION** · 2026-08-27 |
| `uml-plantuml-lora-200k` | `make train-200k` | Combined **202,445** (`uml_training_combined_200k.parquet`) | 20,000 | Complete · 2026-08-26 · warm-start parent |
| `uml-plantuml-lora-100k` | `make train-100k` | Combined **62,445** (`uml_training_combined_100k.parquet`; target was ≥100k with upsampling) | 18,000 | Complete · 2026-08-26 · superseded |
| `uml-plantuml-lora-50k` | `make train-50k` | Supplement merged **54,207** (from 50k HF/web + scenario/code) | 15,000 | Complete · 2026-08-26 · superseded |
| `uml-plantuml-lora-source10k` | `make train-source10k` | **10,000** JPC (`uml_source_code_10k_jpc.parquet`) | 4,000 | Interim · 2026-08-27 · superseded |
| `uml-plantuml-lora` (+ `LIVE`, `prev-3k`) | `make train-real` / early finetune | Legacy ~8k–10k HF path | 3,000 | Legacy · 2026-08-24 |
| `uml-plantuml-lora-industrial-complete` | `make train-industrial-complete` | Industrial complete **8,901** (+ ongoing industrial mix) | long run (meta shows high iter count) | **Not live** — training path does not swap `.env` |
| `uml-plantuml-lora-adaptation` | self-train LaunchAgent | Accepted live top-up mix | — | Empty / not production |

All completed MLX adapters use LoRA rank 8, scale 20, 8 layers; production/50k–200k use `max_seq_length` 1536.

---

## 3. Corpus inventory (`data/training/`)

Measured parquet row counts and sizes (quick scan, 2026-09-10):

| Parquet | Rows | Size (MB) | Notes |
|---------|-----:|----------:|-------|
| `uml_training_8000.parquet` | 50,000 | 58.7 | **Filename ≠ count**; HF/web 50k build (`manifest.json`) |
| `uml_training_supplement_merged.parquet` | 54,207 | 59.3 | 50k + scenarios/code templates |
| `uml_source_code_50k.parquet` | 50,000 | 19.6 | Source-code / stack path for 100k merge |
| `uml_training_combined_100k.parquet` | 62,445 | 61.6 | Supplement + source-code merge |
| `uml_source_code_100k_v2.parquet` | 100,000 | 7.5 | v2 web + large synthetic top-up |
| `uml_training_combined_200k.parquet` | 202,445 | 92.5 | Prior combined + v2 |
| `uml_source_code_10k_jpc.parquet` | 10,000 | 2.4 | Interim source10k |
| `uml_source_code_30k_jpc.parquet` | 30,000 | 8.9 | **Production focus** corpus |
| `uml_training_combined_sourcecode_30k.parquet` | 224,349 | 105.7 | **Production finetune input** |
| `uml_source_code_{java,python,c}_10000.parquet` | 10,000 each | 1.4–4.6 | Per-language slices |
| `uml_industrial_complete.parquet` | 8,901 | 9.0 | Industrial path (not live) |
| `uml_industrial_enriched_mix.parquet` | 97,204 | 60.4 | Enriched industrial mix (not live) |
| `uml_adaptation_mix.parquet` | 16,999 | 11.3 | Self-train mix (not live) |
| `uml_accepted_live_topup.parquet` | 548 | 0.2 | Harvested accepted jobs |

### Primary HF / stack / synthetic sources (50k web corpus)

From `data/training/manifest.json` (50k rows in `uml_training_8000.parquet`):

- Dominant: `devgpt-aimotion/the-stack-v2_PlantUML_filtered` (~34k)  
- nguyenvanviet UMLCode scored / DeepSeek-labeled sets (class, object, component, package, state, activity, …)  
- Other HF PlantUML sets: `ThePeaceLovingGhost/ClassDiagram_PlantUML_Text`, `ibivibiv/plantuml-training`, vinzur use-case sets, etc.

### 200k v2 note

`corpus_v2_manifest.json`: target 100k v2 rows with **~99.8k synthetic top-up** after a small unique web pool — document as mostly synthetic for that slice, not “100k pure Stack.”

---

## 4. Train recipes (Makefile) → adapter

| Make target | Builds / uses | Writes adapter |
|-------------|----------------|----------------|
| `make training-corpus` | ~8k target (historical) | — |
| `make training-corpus-50k` | 50k HF/web | — |
| `make train-real` | 8k-style + supplement | `models/uml-plantuml-lora` |
| `make train-50k` | 50k + prepare + resilient LoRA | `…-lora-50k` |
| `make train-100k` | source-code 50k merge + LoRA | `…-lora-100k` |
| `make train-200k` | corpus v2 100k + LoRA | `…-lora-200k` |
| `make train-source10k` | 10k JPC + LoRA | `…-lora-source10k` |
| **`make train-source30k`** | **30k JPC + combined parquet + LoRA** | **`…-lora-sourcecode-30k` (live)** |
| `make train-industrial-complete` | industrial parquet | `…-lora-industrial-complete` (does **not** auto-swap live) |

Runner: `scripts/run_finetune_resilient.sh` → `scripts/finetune_plantuml.py` → `python -m mlx_lm lora`.

---

## 5. What to tell reviewers in one breath

1. Live PlantUML is **`uml-plantuml-lora-sourcecode-30k`** (health + `.env`), not DeepSeek-32B.  
2. That adapter was produced by **`make train-source30k`** (6k iters, 2026-08-27), warm-started from the **200k** adapter.  
3. Focus data: **30k** real-ish source snippets (Java/Python/C) mapped to PlantUML; finetune parquet is **~224k** after merging prior corpora.  
4. Earlier **50k / 100k / 200k** adapters are complete on disk and superseded for production.  
5. Paper **n=8k DeepSeek** evaluation must not be equated with this Mac LoRA corpus or live smoke jobs.  
6. Filename **`uml_training_8000`** currently holds **50k** rows — cite manifests/row counts.  
7. Spec + VLMs remain Ollama / local Aya; only Stage 2 code uses the LoRA.  
8. Industrial / adaptation training may continue in the background; they are **not** the live adapter until `.env` is changed and the API restarted.

---

## Pointers

- Adapter docs: [`models/README.md`](../models/README.md)  
- System design / data lake: [`docs/SYSTEM_DESIGN.md`](../docs/SYSTEM_DESIGN.md)  
- Broader progress notes: [`reports/REVIEWER_PROGRESS_REPORT.md`](REVIEWER_PROGRESS_REPORT.md)  
- Live check: `curl -s http://127.0.0.1:8000/api/settings/health | python3 -m json.tool`
