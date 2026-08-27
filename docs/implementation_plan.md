# Implementation Plan

**Status:** Implemented (2026-08-26). This document records original architecture decisions and maps them to the current codebase. For production deployment details, see [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md).

---

## Architecture decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend | FastAPI | Typed API, OpenAPI docs, BackgroundTasks |
| Frontend | Streamlit multipage | Fast thesis-ready UI (8 pages) |
| DB | SQLite default; Postgres via `DATABASE_URL` | Simple local demo; production uses SQLite on Mac |
| ORM | SQLModel | Pydantic + SQLAlchemy in one |
| Jobs | In-process thread pool | No Redis/Celery |
| Providers | Protocol + factory (Mock / Ollama / HF / MLX LoRA / local Aya) | Local runnable without cloud APIs |
| Core pipeline | `uml_pipeline/` + `app/services/orchestration.py` | Reuse render, scoring, prompts |
| Prompt store | `prompts/` files + registry | Version without code changes |
| Migrations | SQLModel `create_all` on startup | Thesis simplicity |
| Production host | Mac Studio M1 Ultra + LaunchAgents | No Azure; dual Ollama + MLX LoRA |

```
Requirement / Source Code → Spec Generator → PlantUML Generator (LoRA)
       → Validate / Acceptance Gates → Renderer
       → [fail] Repair Loop (≤ 3) → Renderer
       → VLM Ensemble (3 models) → Weighted Composite S + Majority A
       → Dataset gate (A ∧ S≥3) → Persist Artifact Trace → UI / API / Export
```

---

## Milestones (completed)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| M0 | Docs (gap + plan + assumptions + SYSTEM_DESIGN) | ✅ |
| M1 | DB models, providers, prompt registry | ✅ |
| M2 | Orchestration: generate/render/repair/score/acceptance | ✅ |
| M3 | FastAPI routes + optional API token auth | ✅ |
| M4 | Streamlit UI (8 pages incl. System Design) | ✅ |
| M5 | Human review + analytics + export | ✅ |
| M6 | Tests, Docker, Makefile, README, demo data | ✅ |
| M7 | MLX LoRA 50k training + 100k in progress | 🔄 100k training running |
| M8 | macOS LaunchAgents + Cloudflare tunnels | ✅ |

---

## Directory map (current)

```
docs/                 SYSTEM_DESIGN, deploy, demo_flow, gap_analysis, assumptions
prompts/              versioned prompt templates
app/
  main.py             FastAPI entry
  db.py, models.py, schemas.py, settings.py, security.py
  providers/          factory, mock, ollama, finetuned MLX, aya local
  services/           orchestration, repair, scoring, acceptance, adaptation, analytics
  routers/            generate, artifacts, human, analytics (incl. health)
  jobs/               background runner
ui/
  streamlit_app.py + pages/ (8 pages)
models/
  uml-plantuml-lora-50k/    complete (15k iters)
  uml-plantuml-lora-100k/   training in progress
data/
  uml_app.db, artifacts/, training/, finetune/, run/
scripts/
  install_macos_user_server.sh, start_public_tunnels.sh, restart_api.sh
  build_training_corpus.py, prepare_finetune_data.py, run_finetune_resilient.sh
tests/
sample_data/
Dockerfile, docker-compose.yml, Makefile
```

---

## Data model (SQLModel)

Implemented in `app/models.py`:

- **Project** — named workspace (default “UML-Pipeline”)
- **GenerationJob** — single/batch status, progress, errors
- **RequirementInput** — raw text, diagram type, `input_mode` (requirement | source_code)
- **TechnicalSpecification** — structured + raw text, prompt/model meta
- **UMLArtifact** — PlantUML, diagram type, image path, status, composite score, dataset flags
- **RenderAttempt** — attempt #, success, stderr, fmt
- **RepairAttempt** — before/after code, reason, success
- **ModelScore** — model key, score 0–6, weight, explanation, available flag
- **CompositeScore** — final weighted score, formula snapshot, majority_accepted
- **HumanReview** — rubric dims + comments
- **Reviewer** — name, role

Sidecar JSON: `data/artifacts/{id}/acceptance.json`, `adaptation.json`.

---

## API design (implemented)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/generate` | Single generation (async default) |
| POST | `/api/generate/batch` | Batch job |
| GET | `/api/jobs/{job_id}` | Job status |
| GET | `/api/jobs/{job_id}/artifacts` | Job artifacts |
| GET | `/api/artifacts` | List/filter |
| GET | `/api/artifacts/{id}` | Full trace |
| GET | `/api/artifacts/{id}/image` | Image bytes |
| GET | `/api/artifacts/{id}/plantuml` | Raw PlantUML |
| POST | `/api/artifacts/{id}/rescore` | Re-run VLMs |
| POST | `/api/artifacts/{id}/repair` | Force repair retry |
| POST | `/api/human-review` | Save human eval |
| GET | `/api/analytics/summary` | Counts, means, failures |
| GET | `/api/analytics/distributions` | Histograms |
| GET | `/api/export/dataset` | CSV/JSONL/parquet |
| GET | `/api/settings/health` | Provider/PlantUML/DB/adapter status |
| GET | `/api/adaptation/status` | Adaptation memory snapshot |

Auth: `API_ACCESS_TOKEN` → Bearer or X-API-Key on protected routes.

---

## UI (Streamlit — 8 pages)

1. **Dashboard** — counts, recent jobs, score summary  
2. **Single Generation** — input → full trace viewer  
3. **Batch Generation** — n samples, types, progress  
4. **Generated Diagrams** — filters + gallery  
5. **Human Evaluation** — rubric form  
6. **Analytics** — plotly charts + export  
7. **Settings** — provider mode, health checks  
8. **System Design** — in-app architecture overview  

---

## Scoring formula (per the paper)

```
valid scores: all numeric VLM outputs (None skipped; 0 counts when render OK)
S = 0 if render fails
else S = sum(w_j * s_j) / sum(w_j)

Majority A = 1 if count(s_j >= tau) >= 2  (tau = 4, 3 models)
Dataset entry: render OK ∧ A = 1 ∧ S >= 3.0
```

Weights: Qwen2.5-VL-3B = 53.1, LLaMA-3.2-11B-Vision = 50.7, Aya-Vision-8B = 39.9

---

## Testing (implemented)

```bash
make test     # pytest, MOCK_PROVIDERS=true
make smoke    # live API smoke script
```

Coverage: scoring, validators, repair, API routes, security, e2e mock generation.

---

## Deployment (production path)

```bash
bash scripts/install_macos_user_server.sh   # LaunchAgents + tunnels + dual Ollama
bash scripts/macos_server_status.sh
bash scripts/restart_api.sh                 # after .env / code changes
```

Cloud fallback: `docs/deploy.md` (Render, Railway, Docker).
