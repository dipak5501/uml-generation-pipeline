# End-to-end demo flow

Paper: *Automated UML Dataset Generation from Natural-Language Requirements with Multimodal Verification for Software Design* (Dipak Yadav, Yutong Zhao).

Architecture reference: [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md)

---

## A. Offline mock demo (no GPU, no API keys)

```bash
make install
cp .env.example .env          # MOCK_PROVIDERS=true (default)
make run
```

1. Open http://127.0.0.1:8501  
2. **Single Generation** → paste a requirement, pick diagram type (e.g. class), click Generate  
3. Inspect trace: requirement → tech spec → PlantUML → PNG → mock VLM scores → acceptance flags  
4. Optional: **Human Evaluation**, **Analytics**, **Generated Diagrams**

Mock mode returns deterministic scores; useful for CI and UI testing.

---

## B. Production demo (Mac Studio stack)

Prerequisites: dual Ollama, MLX LoRA adapter, local Aya, Java JDK.

```bash
# .env
MOCK_PROVIDERS=false
USE_OLLAMA=true
USE_FINETUNED_CODE=true
FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-sourcecode-30k
VLM_AYA_BACKEND=local
API_ACCESS_TOKEN=<secret>

bash scripts/install_macos_user_server.sh
# or: make run
```

### Flow

1. **Settings** page — confirm health: Ollama dual-host, LoRA adapter present, Aya local backend, Java OK  
2. **Single Generation** — choose input mode:
   - **Requirement:** paste e.g. *"Online bookstore with customers, orders, and inventory."*
   - **Source code:** paste a Python/Java class; language auto-detected  
3. Select diagram type (class / object / component / package)  
4. Generate (async) — job runs in background; poll until complete  
5. Review artifact trace:
   - Stage 1 structured spec (JSON)  
   - Stage 2 PlantUML (black-and-white; LoRA or fallback)  
   - Validation / repair attempts  
   - Render status (local Java + PlantUML JAR)  
   - Three VLM scores → composite **S**, majority **A**  
   - Dataset accepted: render OK ∧ A = 1 ∧ S ≥ 3  
6. **Generated Diagrams** — filter by type, score, dataset acceptance  
7. **Analytics** — export accepted rows as JSONL/CSV/Parquet  

### Scoring interpretation

| Signal | Rule |
|--------|------|
| Render gate | PNG must render; else **S = 0** |
| Majority **A** | ≥ 2 of 3 VLMs score ≥ 4 (τ = 4) |
| Composite **S** | MMMU-weighted mean of Qwen (53.1), LLaMA-Vision (50.7), Aya (39.9) |
| Dataset entry | A ∧ S ≥ 3 ∧ render OK |

---

## C. Public demo via Cloudflare tunnel

```bash
bash scripts/start_public_tunnels.sh
cat data/run/public_ui_url.txt    # share this URL
```

- Browser opens the tunnel URL; Streamlit still calls API at `http://127.0.0.1:8000` internally.  
- `API_ACCESS_TOKEN` must be set — UI sends Bearer auth automatically.  
- Tunnel URLs change on restart; use `monitor_public_tunnels.sh` for auto-recovery.

---

## D. Batch dataset generation

**UI:** Batch Generation page — set N samples, diagram types, optional sample file.

**API:**

```bash
curl -X POST http://127.0.0.1:8000/api/generate/batch \
  -H "Authorization: Bearer $API_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"n_samples": 10, "diagram_types": ["class"], "use_sample_file": true}'
```

Poll `GET /api/jobs/{id}` until `status=completed`. Export via `GET /api/export/dataset?fmt=jsonl`.

---

## E. Common failure modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| S = 0, no image | Java missing or PlantUML error | `make install-java`; check `/api/settings/health` |
| Only 1–2 VLM scores | Ollama down or Aya not loaded | `macos_server_status.sh`; run `setup_paper_aya_local.sh` |
| Package diagrams weak | LoRA may emit class-style UML | Repair loop + typed templates; rollback to prior adapter if needed |
| UI "API offline" | API not running or wrong `API_BASE_URL` | Keep `API_BASE_URL=http://127.0.0.1:8000`; restart API |
| 401 on generate | Token mismatch | Same `API_ACCESS_TOKEN` in `.env` for API and UI |

---

## F. CLI smoke (no UI)

```bash
make demo
# or
PYTHONPATH=. MOCK_PROVIDERS=true python scripts/demo_generate.py -n 1
make smoke    # requires running API
```
