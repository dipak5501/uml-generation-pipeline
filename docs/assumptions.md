# Assumptions

1. **Authorship / demo branding:** Repo author remains Dipak Yadav; paper PDF describes the Nguyen et al. methodology we implement. The application reproduces that pipeline for thesis demonstration.
2. **Mock providers:** When `MOCK_PROVIDERS=true` (default for local demo), LLMs/VLMs return deterministic synthetic specs, PlantUML, and scores so the app runs without API keys or GPUs.
3. **Composite score nullability:** Existing `weighted_composite` returning `None` is treated as `0.0` at the application boundary to match the paper formula.
4. **Background jobs:** Batch generation uses an in-process thread pool, not Redis/Celery.
5. **Migrations:** Schema is created via `SQLModel.metadata.create_all` on startup; Alembic is deferred unless schema churn demands it.
6. **SVG render:** Supported when PlantUML + Java are available; PNG remains default.
7. **Private reasoning:** CoT/private reasoning from models is stripped and never shown in UI or standard logs; only structured interpretation, PlantUML, validation, and repair meta are persisted.
8. **Human rubric:** Semantic correctness, structural completeness, syntactic accuracy, overall coherence — each 1–5 (or 0–6 aligned with VLM scale via config); default 1–5 for human forms.
9. **Python version:** Target is 3.11+, but the local environment may run 3.9. Route annotations use `Optional[...]` where FastAPI evaluates types at runtime; `eval_type_backport` is included for remaining `|` syntax compatibility.

