# Assumptions

1. **Authorship / paper:** This application implements **Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design** by Dipak Yadav and Yutong Zhao. Repo author and primary maintainer: Dipak Yadav.
2. **Mock providers:** When `MOCK_PROVIDERS=true` (default for local demo), LLMs/VLMs return deterministic synthetic specs, PlantUML, and scores so the app runs without API keys or GPUs.
3. **Composite score:** Thesis Eq. (weighted) averages all numeric VLM scores (zeros included; `None` skipped). Render failure forces \(S=0\). Legacy `weighted_composite` matches this; callers map empty/`None` to `0.0`.
4. **Background jobs:** Batch generation uses an in-process thread pool, not Redis/Celery.
5. **Migrations:** Schema is created via `SQLModel.metadata.create_all` on startup; Alembic is deferred unless schema churn demands it.
6. **SVG render:** Supported when PlantUML + Java are available; PNG remains default.
7. **Private reasoning:** CoT/private reasoning from models is stripped and never shown in UI or standard logs; only structured interpretation, PlantUML, validation, and repair meta are persisted.
8. **Human rubric:** Semantic correctness, structural completeness, syntactic accuracy, overall coherence — each 1–5 (or 0–6 aligned with VLM scale via config); default 1–5 for human forms.
9. **Default project:** A single “UML-Pipeline” project is auto-created on first run.
10. **Python version:** Target is 3.11+; local production venv may run 3.13.
11. **Production host:** Primary deployment is Math department Mac Studio M1 Ultra (128 GB), 24/7 via user LaunchAgents — dual Ollama (:11434/:11435), MLX LoRA (`sourcecode-30k`), local Aya, Cloudflare tunnels — not Azure.
12. **LoRA adapters:** Production default `models/uml-plantuml-lora-sourcecode-30k` (30k Java/Python/C, 6k iters). Prior adapters (50k, 100k, 200k, source10k) are superseded but kept for rollback.
