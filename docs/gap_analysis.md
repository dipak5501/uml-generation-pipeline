# Gap Analysis: UML Generation Thesis Application

**Date:** 2026-07-13 
**Paper:** *Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design* (Dipak Yadav, Yutong Zhao) 
**Repo:** [dipak5501/uml-generation-pipeline](https://github.com/dipak5501/uml-generation-pipeline)

## Current repo capabilities

| Area | Status | Notes |
|------|--------|-------|
| Spec generation | Partial | Invents specs via architect/user prompts; does **not** accept arbitrary user requirements as primary input |
| PlantUML generation | Partial | Class/object/component/package via diagram hints; no versioned prompt files |
| Rendering | Working | PlantUML JAR + Java; PNG; error capture |
| VLM scoring | Partial | 3-model weighted composite (`scoring.weighted_composite`); scores return `None` when all zero (paper wants `0`) |
| LLM providers | Partial | OpenAI-compatible + Ollama; **no mock**, no graceful scorer skip abstraction layer |
| Dataset tooling | Working | HF download, parquet merge, analyze + matplotlib figures |
| Batch generation | CLI only | `scripts/run_generation.py` → parquet/jsonl |
| Persistence | Missing | Files only (parquet/jsonl/images); no DB, jobs, artifact IDs |
| API | Missing | No FastAPI/HTTP layer |
| UI | Missing | No Streamlit/web UI |
| Repair/retry | Missing | Failures get score 0; no package validators or repair loop |
| Human evaluation | Missing | Paper describes human rubrics; not in code |
| Analytics app | Partial | Offline `analyze.py` only |
| Tests | Missing | CI only import/config checks |
| Docker / deployment | Missing | README is CLI-oriented |
| Prompt management | Inline | Strings in `uml_pipeline/prompts.py` |

## Target application capabilities

1. Requirement intake (single + batch) → structured technical specs 
2. Diagram-specific PlantUML generation (class, object, component, package) 
3. Render PNG/SVG with failure handling 
4. Package-aware validation + repair/retry 
5. Multimodal scoring with paper weights (53.1 / 50.7 / 39.9) 
6. Persist full artifact traces in SQLite (optional Postgres) 
7. REST API + Streamlit thesis UI 
8. Human review rubric + analytics + export 
9. Local runnable via mock providers without paid APIs 
10. Real tests, Docker, complete README 

## Paper requirements vs repo

| Paper element | In repo? | Gap |
|---------------|----------|-----|
| Dual-LLM (lightweight spec + reasoning PlantUML) | Yes (env models) | Need requirement→spec path + metadata persistence |
| Design-phase diagram types (4) | Yes | Strengthen package prompts/guards |
| PlantUML render as gate | Yes | Tie to repair + score=0 |
| 3 VLMs + MMMU weights | Yes | Provider failover; force composite `0` if no valid scores |
| Human evaluation correlation | No | Reviewer UX + analytics correlation |
| Large dataset generation | CLI batch only | Batch jobs + progress UI |
| Failure analysis (esp. package) | Analysis plots only | Repair metrics + package failure breakdown |

## Missing modules (to build)

- `app/` — FastAPI, SQLModel models, services, routers, job runner 
- `ui/` — Streamlit multipage application 
- `prompts/` — versioned prompt templates + registry 
- `app/providers/` — OpenAI / Ollama / Mock with swap via config 
- Package validator + repair service 
- Human review + analytics services 
- `tests/` — scoring, repair, API, e2e smoke 
- Docker, Makefile, updated README 

## Quick wins

1. Reuse `render.py`, `scoring.py`, `pipeline.generate_*`, `llm_client` as core engines 
2. Wrap existing functions in services instead of rewriting 
3. Fix composite score to return `0.0` when no valid scores (per the paper formula) 
4. Ship **mock mode** so the demo runs without GPUs/APIs 
5. SQLite default — zero external infra for application 

## Risky areas

| Risk | Mitigation |
|------|------------|
| Real VLMs unavailable locally | Mock + graceful unavailable markers; score on available models only |
| Package diagram syntax/nesting | Dedicated validator + repair prompts + retry limit |
| Long-running generation | In-process background jobs (FastAPI BackgroundTasks / thread pool) |
| Reasoning model leaks CoT into UI | Strip private reasoning; persist only final PlantUML + structured interpretation |
| Java/PlantUML missing | Settings health check + clear error messages |

## Recommended implementation order

1. Gap docs + assumptions 
2. Persistence + pydantic/SQLModel data model 
3. Provider abstraction + mock 
4. Orchestrated generation service (intake → spec → PlantUML → render → repair → score) 
5. FastAPI endpoints 
6. Streamlit UI (all pages) 
7. Human review + analytics export 
8. Tests, Docker, README, sample/demo dataset 

## Verdict

The repo is a **working research pipeline library + CLI**, not an application. Core generation/render/score logic is valuable and should be **wrapped and extended**, not rewritten.
