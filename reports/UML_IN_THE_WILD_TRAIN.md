# UML-in-the-Wild training run (Mac Studio)

**Status:** **RUNNING unattended** (started 2026-09-10 ~15:24 PDT).  
**Chain PID:** see `data/training/wild_train_chain.pid` (was **12016** at launch).  
**Logs:** `data/training/wild_train_chain.log` · `data/training/finetune_wild.log`  
**Live API adapter:** still `models/uml-plantuml-lora-sourcecode-30k` — **not swapped**.  
**ETA:** ~2–3.5 h total from chain start (import done; prepare + ~1–1.5 h LoRA remain).

## Dataset

| Field | Value |
|-------|--------|
| DOI | [10.5281/zenodo.18952372](https://doi.org/10.5281/zenodo.18952372) |
| Record | https://zenodo.org/records/18952372 |
| Downloaded | `uml_metadata_enriched.json` (~116 MB) + `puml_files.zip` (~105 MB) |
| **Skipped** | `puml_images.zip` (~4.3 GB PNGs) — text-only import |
| Raw dir | `data/raw/uml_in_the_wild/` |
| Import script | `scripts/import_uml_in_the_wild.py` |
| Training parquet (app types) | `data/training/uml_in_the_wild_app.parquet` (**84 248** rows) |
| Full-type parquet | `data/training/uml_in_the_wild.parquet` (**140 626** rows) |
| Import manifest | `data/training/uml_in_the_wild_import_manifest.json` |
| Finetune JSONL | `data/finetune_wild/` (train **80 880** / valid 1 684 / test 1 684) |
| **New adapter (NOT live)** | `models/uml-plantuml-lora-wild` |
| Target iters | 18 000 (warm-start from `sourcecode-30k`) |

**Claim hygiene:** Specs are synthesized from Wild classification metadata (repo/path/elements/reasoning), not human-authored requirements. No VLM scores (`dataset_accepted=false`). Filtered to class/object/component/package when converting the app parquet. Deduped on UML hash.

## Unattended chain (lock-safe)

| Item | Path / command |
|------|----------------|
| Chain script | `scripts/run_wild_train_unattended.sh` |
| Chain log | `data/training/wild_train_chain.log` |
| Train log | `data/training/finetune_wild.log` |
| PID file | `data/training/wild_train_chain.pid` |
| Caffeinate | LaunchAgent `com.uml.pipeline.caffeinate` (+ extra `caffeinate -dimsu`) |

Industrial continuous train was **paused** so Metal is free:

```bash
# already done at start of this run:
launchctl bootout gui/$(id -u)/com.uml.pipeline.finetune-industrial
```

**Restore industrial later (after Wild finishes):**

```bash
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/com.uml.pipeline.finetune-industrial.plist"
# or: launchctl load -w ~/Library/LaunchAgents/com.uml.pipeline.finetune-industrial.plist
```

## After unlock — check commands

```bash
cd /Users/033783670/Desktop/uml-generation-pipeline-main
cat data/training/wild_train_chain.pid   # chain PID if still running
pgrep -lf 'run_wild_train|finetune_plantuml|mlx_lm lora'
tail -40 data/training/wild_train_chain.log
tail -30 data/training/finetune_wild.log
# progress:
rg -n 'Iter [0-9]+:|Fine-tune complete|Wild chain COMPLETE|FATAL' data/training/finetune_wild.log data/training/wild_train_chain.log | tail -20
ls -lt models/uml-plantuml-lora-wild/ | head
# confirm live adapter untouched:
grep FINETUNED_ADAPTER_PATH .env
```

## ETA

Import + prepare finished in ~15 s after metadata load (already done).  
Early Wild train rate ~**2.1 it/s** → 18 000 iters ≈ **~2.0–2.5 h** from 15:25 PDT (**done ~17:25–17:55 PDT** if sustained). Historical idle rates were higher (~4–6 it/s); if rate rises, finish sooner.

## Eval / swap later (manual only)

1. Confirm `Fine-tune complete` / `Wild chain COMPLETE` in logs.  
2. Smoke / batch eval against `models/uml-plantuml-lora-wild` (do not point production yet).  
3. If Wild wins: set `FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-wild` in `.env` and `bash scripts/restart_api.sh`.  
4. Optionally restore industrial LaunchAgent (above).

## License

Dataset license: **CC-BY-4.0** (see `data/raw/uml_in_the_wild/LICENSE`).
