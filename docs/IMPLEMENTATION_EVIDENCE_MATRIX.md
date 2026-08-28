# Implementation Evidence Matrix

**Repository:** [uml-generation-pipeline](https://github.com/dipak5501/uml-generation-pipeline)  
**Audit date:** 2026-08-28  
**Purpose:** Map every reportable claim to verifiable repository evidence.

Legend: **VERIFIED** = confirmed in source code and/or on-disk artifacts; **PARTIAL** = implemented but incomplete or stand-in; **NOT VERIFIED** = code exists but no measured outcome in repo; **NOT IMPLEMENTED** = absent or UI-only stub.

| Claim | Evidence | File | Function/Class | Verified Status |
|-------|----------|------|----------------|-----------------|
| End-to-end NL requirement → UML artifact | 470 SQLite artifacts; orchestration pipeline | `app/services/orchestration.py` | `run_single_generation` | VERIFIED |
| Source code input mode (Java/Python/C) | `input_mode=source_code`; 130 artifacts | `app/services/code_analysis.py` | `structure_to_spec`, `detect_source_language` | VERIFIED |
| Stage-1 technical specification (JSON + prose) | Persisted `TechnicalSpecification` rows | `app/services/orchestration.py` | `generate_technical_spec` | VERIFIED |
| Stage-1 JSON schema validation / grounding | Validity metrics in DB JSON | `app/services/spec_json.py` | `ensure_valid_spec` | VERIFIED |
| Stage-2 PlantUML via LLM prompts | Versioned prompts + orchestration | `prompts/tech_spec_to_*.v1.txt` | `generate_plantuml_code` | VERIFIED |
| Stage-2 MLX LoRA PlantUML generator | Provider + model dirs | `app/providers/finetuned_provider.py` | `FinetunedMLXProvider` | VERIFIED (code); PARTIAL (17/470 artifacts used LoRA in DB) |
| Stage-2 deterministic spec-builder fallback | 416/470 artifacts used `spec-builder` | `app/services/plantuml_from_spec.py` | `plantuml_from_spec` | VERIFIED |
| Chain-of-thought prompting for PlantUML | `enable_cot`; CoT strip | `app/services/cot.py` | `COT_SYSTEM`, `finalize_plantuml_output` | VERIFIED |
| Class diagram generation | 151 artifacts; prompts | `prompts/tech_spec_to_class.v1.txt` | `generate_plantuml_code` | VERIFIED |
| Object diagram generation | 112 artifacts | `prompts/tech_spec_to_object.v1.txt` | same | VERIFIED (high render failure rate) |
| Component diagram generation | 105 artifacts | `prompts/tech_spec_to_component.v1.txt` | same | VERIFIED |
| Package diagram generation | 102 artifacts | `prompts/tech_spec_to_package.v1.txt` | same | VERIFIED |
| Programmatic UML entity guarantee | Spec-builder + fidelity gate | `app/services/plantuml_from_spec.py` | `ensure_faithful_plantuml` | VERIFIED (builder path only) |
| Prompt-only UML semantics (LoRA/LLM path) | Prompt text instructs entities | `prompts/tech_spec_to_class.v1.txt` | N/A | VERIFIED (prompt layer only) |
| PlantUML syntax validation | Validator + tests | `app/services/plantuml_validate.py` | `validate_diagram` | VERIFIED |
| PlantUML compile gate (`-checkonly`) | Render pipeline | `uml_pipeline/render.py` | `check_plantuml_syntax` | VERIFIED |
| PlantUML PNG rendering (local Java) | 363 successful renders | `uml_pipeline/render.py` | `render_plantuml` | VERIFIED |
| Remote PlantUML HTTP fallback | Env flag + function | `uml_pipeline/render.py` | `render_plantuml_remote` | VERIFIED (code) |
| Black-and-white publication style | Sanitizer + finetune SYSTEM | `app/services/plantuml_validate.py` | `apply_publication_plantuml_style` | VERIFIED |
| Repair loop (≤3 attempts) | 243 repair attempts in DB | `app/services/repair.py` | `repair_plantuml` | VERIFIED |
| Package-specific repair categories | Package failure taxonomy | `app/services/package_failures.py` | `classify_package_failure` | VERIFIED |
| Acceptance gates (syntax/compile/render/semantic) | `acceptance.json` sidecars | `app/services/acceptance.py` | `evaluate_acceptance` | VERIFIED |
| Three-VLM multimodal scoring | ModelScore rows (1410+) | `app/services/orchestration.py` | `score_image` | VERIFIED |
| VLM scoring prompt (0–6 rubric) | Prompt file | `prompts/vlm_scoring.v1.txt` | `render_prompt("vlm_scoring")` | VERIFIED |
| MMMU weights w₁=53.1, w₂=50.7, w₃=39.9 | Config + settings | `config.yaml`, `app/settings.py` | `vlm_weight_map` | VERIFIED |
| Weighted composite score S | Scoring module | `app/services/scoring.py` | `paper_composite` | VERIFIED |
| Majority vote gate A (τ=4, ≥2/3) | Scoring module | `app/services/scoring.py` | `majority_vote_accept` | VERIFIED |
| Render failure forces S=0 | Scoring module | `app/services/scoring.py` | `paper_composite(render_ok=False)` | VERIFIED |
| Dataset gate (A=1 ∧ S≥3) | 311 dataset_accepted artifacts | `app/services/scoring.py` | `dataset_entry_accepted` | VERIFIED |
| FastAPI REST API | App entry | `app/main.py` | routers | VERIFIED |
| Streamlit 8-page UI | UI pages | `ui/streamlit_app.py`, `ui/pages/*.py` | N/A | VERIFIED |
| SQLite persistence | `data/uml_app.db` (6.2 MB) | `app/models.py` | SQLModel entities | VERIFIED |
| Artifact file storage | 470 dirs under `data/artifacts/` | `app/services/artifacts.py` | N/A | VERIFIED |
| Batch generation jobs | 138 completed jobs | `app/services/orchestration.py` | `create_job` | VERIFIED |
| Dataset export (JSONL/CSV/Parquet) | Analytics router | `app/services/analytics.py` | `export_dataset` | VERIFIED |
| Human evaluation UI | Page exists; 0 reviews in DB | `ui/pages/5_Human_Evaluation.py` | POST `/api/human-review` | PARTIAL (UI only; no collected data) |
| Human↔AI correlation metric | Analytics computes when reviews exist | `app/services/analytics.py` | `analytics_summary` | NOT VERIFIED (0 reviews) |
| Mock provider offline demo | Default `.env.example` | `app/providers/mock_provider.py` | `MockProvider` | VERIFIED |
| Ollama dual-host VLM routing | Factory routing | `app/providers/factory.py` | `build_vlm_providers` | VERIFIED (code) |
| Local Aya-Vision-8B (Transformers) | Aya provider | `app/providers/aya_local_provider.py` | `LocalAyaVisionProvider` | VERIFIED (code) |
| Hugging Face Inference Providers | HF provider | `app/providers/factory.py` | `HuggingFaceProvider` | VERIFIED (code) |
| OpenAI-compatible API fallback | OpenAI provider | `app/providers/factory.py` | `OpenAIProvider` | VERIFIED (code) |
| Training corpus builders (8k–200k) | Scripts + training dir | `scripts/build_training_corpus.py` | N/A | VERIFIED (code + `data/training/`) |
| **50k LoRA training corpus** | **50,000 rows** | `data/training/manifest.json` | `make train-50k` | **VERIFIED** (15k iters, adapter complete) |
| **100k LoRA training corpus** | **~102,445 rows; 131,153 train JSONL** | `data/data_lake_inventory.json` | `make train-100k` | **VERIFIED** (18k iters complete) |
| **200k LoRA training corpus** | **~224k rows; 202,445+ JSONL** | `data/training/200k_final_metrics.json` | `make train-200k` | **VERIFIED** (20k iters, val loss 0.565) |
| **30k source-code LoRA (production)** | **30,000 Java/Python/C** | `data/training/finetune_sourcecode_30k.log` | `make train-source30k` | **VERIFIED** (6k iters, warm-start from 200k) |
| MLX LoRA fine-tune scripts | Scripts + adapter dirs | `scripts/finetune_plantuml.py` | N/A | VERIFIED (model dirs present) |
| Imported HF **evaluation** dataset (8000 rows, not training) | Parquet manifest | `data/uml_design_dataset.parquet` | `data/manifest.json` | VERIFIED |
| VLM scores on imported dataset (3000 rows) | Parquet column stats | `data/uml_design_dataset.parquet` | N/A | VERIFIED (object/component/package only) |
| Golden acceptance regression (6/6) | Report file | `reports/acceptance_eval.md` | `tests/test_acceptance.py` | VERIFIED |
| Benchmark acceptance (200/200) | Report file | `reports/acceptance_eval.md` | `scripts/eval_acceptance.py` | VERIFIED |
| pytest suite (153 tests) | Test collection | `tests/` | N/A | VERIFIED |
| Mac Studio LaunchAgent deployment | Docs + scripts | `scripts/install_macos_user_server.sh` | N/A | VERIFIED (documented; runtime not re-verified here) |
| Cloudflare public tunnels | Docs + scripts | `scripts/start_public_tunnels.sh` | N/A | VERIFIED (documented) |
| Paper n=8000 generation at scale | Paper LaTeX only | `paper/main.tex` | N/A | NOT VERIFIED in local SQLite |
| Paper human correlation r=0.71 | Paper LaTeX only | `paper/corrected_paper (1).tex` | N/A | NOT VERIFIED (0 human reviews in DB) |
| Paper render rate 95.7% | Paper LaTeX only | `paper/main.tex` | N/A | NOT VERIFIED at paper scale locally |
| Output figure PNGs in repo | Empty dirs | `output/figures/`, `paper/figures/` | N/A | NOT VERIFIED |
