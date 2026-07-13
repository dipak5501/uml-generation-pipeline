# End-to-end flow

1. `make install` then `make api` + `make ui`
2. Open http://127.0.0.1:8501 → Single Generation
3. Paste a requirement, pick diagram type, Generate
4. Inspect requirement → tech spec → PlantUML → image (or failure) → scores
5. Optionally Human Evaluation + Analytics export

Without Java JDK, rendering fails and composite score is forced to 0 (per the paper formula).
With JDK + PlantUML jar, mock mode still produces deterministic scores; set `MOCK_PROVIDERS=false` for live models.

Paper: *Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design*.
