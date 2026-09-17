# Train on all merged corpora (`uml-plantuml-lora-all`)

**Status:** training in progress — PID in `data/training/all_corpora_train_chain.pid`; logs `data/training/finetune_all.log` + `data/training/all_corpora_train_chain.log`.  
**Live adapter unchanged:** `FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-sourcecode-30k` until explicit promote after eval.

## Why not “all adapters live at once”

Stage-2 loads a **single** LoRA path. Architecture does not support multi-adapter ensemble generation. “All trainings live” is delivered as **one model trained on all corpora**, plus optional promote via `scripts/switch_live_adapter.sh`.

## Merged corpus

| Item | Value |
|------|--------|
| Output | `data/training/uml_training_all_merged.parquet` |
| Manifest | `data/training/uml_training_all_merged_manifest.json` |
| Rows before dedupe | 423,384 |
| Rows after SHA1(`uml_code`) dedupe | **328,064** |
| Finetune JSONL | `data/finetune_all/` (493,184 usable after `--prefer-accepted` upsample; train 473,458 / valid 9,863 / test 9,863) |
| Adapter (new) | `models/uml-plantuml-lora-all` |
| Target iters | 25,000 |
| Warm-start | `models/uml-plantuml-lora-wild` (18k completed; fallback sourcecode-30k) |
| Train PID / log | see `data/training/all_corpora_train_chain.pid` · `data/training/finetune_all.log` |
| ETA | ~2–4 h wall (≈2–6 it/sec historically; Metal hiccups extend) |

### Sources included (kept after dedupe)

| Label | Input rows | Kept unique |
|-------|------------|-------------|
| `combined_sourcecode_30k` | 224,349 | 224,349 |
| `wild_app` (UML-in-the-Wild app types) | 84,248 | 64,003 |
| `industrial_enriched` | 97,213 | 39,674 |
| `adaptation_mix` | 17,017 | 38 |
| `accepted_live_topup` | 557 | 0 (already in industrial/adaptation) |

Nested corpora **skipped** as redundant subsets of the above: combined 200k/100k, source_* slices, `uml_training_8000`, supplement merged, industrial_complete alone, full wild (non-app types), empty open-source topup.

### Claim hygiene

Do **not** describe synthetic scenario rows or UML-in-the-Wild metadata-derived specs as “www real” human requirements. Wild specs are synthesized from Zenodo classification metadata; industrial mix includes HF/web PlantUML plus synthetic top-ups (see `industrial_enriched_mix_manifest.json`).

## How to run / resume

```bash
# Full chain (merge → prepare → resilient LoRA). Never edits .env.
nohup bash scripts/run_all_corpora_train_unattended.sh \
  > data/training/all_corpora_train_chain.nohup.out 2>&1 &

# Logs
tail -f data/training/all_corpora_train_chain.log
tail -f data/training/finetune_all.log
```

Env overrides: `ITERS=30000`, `WARM_START=models/uml-plantuml-lora-sourcecode-30k`, `ADAPTER_PATH=…`, `DATA=…`.

## Promote to live (after smoke/eval only)

```bash
# Keep production on 30k until you are ready:
grep FINETUNED_ADAPTER_PATH .env

bash scripts/switch_live_adapter.sh models/uml-plantuml-lora-all
# → updates .env + restart_api.sh
```

Rollback:

```bash
bash scripts/switch_live_adapter.sh models/uml-plantuml-lora-sourcecode-30k
```

## ETA (rough)

Wild train hit ~2–6 it/sec (batch 1–2) and finished 18k iters in ~1.5h including Metal restarts. **25k iters ≈ 2–4 hours** wall time on this Mac Studio, longer if UI/VLM shares GPU (`BATCH_SIZE_BUSY=1`).
