# Implementation Plan

## Architecture decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend | FastAPI | Typed API, OpenAPI docs, BackgroundTasks |
| Frontend | Streamlit multipage | Fastest thesis-ready UI |
| DB | SQLite default; Postgres via `DATABASE_URL` | Simple local demo |
| ORM | SQLModel | Pydantic + SQLAlchemy in one |
| Jobs | In-process thread pool / BackgroundTasks | No Redis/Celery |
| Providers | Protocol + OpenAI / Ollama / Mock | Local runnable without APIs |
| Core pipeline | Keep `uml_pipeline/` | Reuse render, scoring, prompts |
| Prompt store | `prompts/` files + registry | Version without code changes |
| Migrations | SQLModel `create_all` + optional Alembic later | Thesis simplicity |

```
Requirement → Spec Generator → PlantUML Generator
       → Package/Syntax Validator → Renderer
       → [fail] Repair Loop (≤ N) → Renderer
       → VLM Ensemble → Weighted Composite
       → Persist Artifact Trace → UI / API / Export
```

## Milestones

| Phase | Deliverable |
|-------|-------------|
| M0 | Docs (gap + plan + assumptions) |
| M1 | DB models, providers, prompt registry |
| M2 | Orchestration: generate/render/repair/score |
| M3 | FastAPI routes |
| M4 | Streamlit UI (7 pages) |
| M5 | Human review + analytics |
| M6 | Tests, Docker, Makefile, README, demo data |

## Changed / new directories

```
docs/                 gap_analysis, implementation_plan, assumptions
prompts/              versioned prompt templates
app/
  main.py             FastAPI entry
  db.py, models.py, schemas.py, settings.py
  providers/          openai, ollama, mock
  services/           intake, spec, plantuml, render, repair, validation, human, analytics, orchestration
  routers/            generate, artifacts, jobs, human, analytics, export, settings
  jobs/               background runner
ui/
  streamlit_app.py + pages/
tests/
sample_data/
Dockerfile, docker-compose.yml, Makefile
```

## Dependencies (add)

`fastapi`, `uvicorn`, `streamlit`, `sqlmodel`, `pydantic-settings`, `python-multipart`, `plotly`, `pytest`, `httpx`, `aiosqlite` (optional)

## Data model (SQLModel)

- **Project** — named workspace (default “Thesis Demo”)
- **GenerationJob** — single/batch status, progress, errors
- **RequirementInput** — raw text, diagram type, mode
- **TechnicalSpecification** — structured + raw text, prompt/model meta
- **UMLArtifact** — PlantUML, diagram type, image path, status, composite score
- **RenderAttempt** — attempt #, success, stderr, fmt
- **RepairAttempt** — before/after code, reason, success
- **ModelScore** — model key, score 0–6, weight, explanation, available flag
- **CompositeScore** — final weighted score, formula snapshot
- **HumanReview** — rubric dims + comments
- **Reviewer** — name, role
- **PromptTemplate** — name, version, body (or file-backed registry)
- **SystemConfig** — key/value runtime flags

## API design

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/generate` | Single requirement generation |
| POST | `/api/generate/batch` | Batch job |
| GET | `/api/jobs/{job_id}` | Job status |
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
| GET | `/api/settings/health` | Provider/PlantUML/DB status |

## UI plan (Streamlit)

1. **Dashboard** — counts, recent jobs, score summary  
2. **Single Generation** — input → full trace viewer  
3. **Batch Generation** — n samples, types, progress  
4. **Artifact Review** — filters + detail  
5. **Human Evaluation** — rubric form  
6. **Analytics** — plotly charts  
7. **Settings** — provider mode, health checks  

## Scoring formula (paper-aligned)

```
valid = [(s_i, w_i) for each model where s_i > 0]
final = 0 if empty else sum(s_i * w_i) / sum(w_i)
```

Weights: Qwen2.5-VL-3B = 53.1, LLaMA-3.2-11B-Vision = 50.7, Aya-Vision-8B = 39.9  
Render failure → all scores 0 → final = 0

## Package repair strategy

1. Static checks: `@startuml`/`@enduml`, nested `package` blocks, self-deps, dotted-name confusion  
2. If render fails or validators flag → targeted repair prompt with error log  
3. Retry up to `MAX_REPAIR_ATTEMPTS` (default 3)  
4. Persist every attempt  

## Testing plan

- Unit: `weighted_composite`, package validators, repair transforms, prompt registry  
- Provider: mock chat/vision  
- API: TestClient generate (mock), get artifact, human review, analytics  
- Render: smoke when Java available; skip otherwise  
- E2E: one artifact per diagram type under `MOCK_PROVIDERS=true`  

## Deployment plan

```bash
make install
cp .env.example .env   # MOCK_PROVIDERS=true for offline demo
make api               # uvicorn :8000
make ui                # streamlit :8501
# or
make docker-up
```

## Implementation order (execute next)

1. Settings + DB + models  
2. Providers + prompts  
3. Services (repair critical)  
4. Orchestration + routers  
5. Streamlit UI  
6. Tests + Docker + README  
