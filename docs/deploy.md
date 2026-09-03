# Deployment guide

This document covers **production deployment on macOS** (primary) and optional **cloud demos**. There is no Azure path in this repository.

| Surface | URL | What it is |
|---------|-----|------------|
| Local UI | `http://127.0.0.1:8501` | Streamlit app |
| Local API | `http://127.0.0.1:8000/docs` | FastAPI OpenAPI |
| Cloudflare tunnel | `data/run/public_ui_url.txt` | Ephemeral public HTTPS (changes each restart) |
| GitHub Pages | `https://dipak5501.github.io/uml-generation-pipeline/` | Static landing only |
| Render (optional) | `https://uml-pipeline-ui.onrender.com` | Cloud demo without MLX LoRA |

<!-- LIVE_DEMO_BEGIN -->
**Live demo (as of 2026-09-03):**

- **UI:** [https://jar-discover-compromise-step.trycloudflare.com](https://jar-discover-compromise-step.trycloudflare.com)
- **API:** [https://walker-driving-crops-yale.trycloudflare.com](https://walker-driving-crops-yale.trycloudflare.com)
- **Agent:** [https://walker-driving-crops-yale.trycloudflare.com/api/agent](https://walker-driving-crops-yale.trycloudflare.com/api/agent)

Quick-tunnel URLs rotate on restart. This block is rewritten by `scripts/tunnel_notify.py` whenever tunnels publish (GitHub is updated via `scripts/git_auto_push.sh`). Always-current copy: [../Link.md](../Link.md). On the Mac Studio: `data/run/public_ui_url.txt`, `data/run/public_api_url.txt`.
<!-- LIVE_DEMO_END -->

Full architecture: [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md)

---

## Option A — Mac Studio production (recommended)

Hardware: Math department **Apple Mac Studio**, M1 Ultra, 128 GB RAM, **24/7** via LaunchAgents. Stack: FastAPI, Streamlit, SQLite, dual Ollama (:11434 llama3.2-vision, :11435 qwen2.5vl), MLX LoRA (`sourcecode-30k`), local Aya-Vision-8B, Cloudflare tunnels.

### 1. Install dependencies

```bash
make install
make install-java          # local PlantUML render
cp .env.example .env       # configure production flags — do NOT commit .env
```

Production `.env` essentials:

```bash
MOCK_PROVIDERS=false
USE_OLLAMA=true
USE_FINETUNED_CODE=true
FINETUNED_ADAPTER_PATH=models/uml-plantuml-lora-sourcecode-30k
VLM_AYA_BACKEND=local
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_QWEN_BASE_URL=http://127.0.0.1:11435
PLANTUML_PREFER_LOCAL=true
API_ACCESS_TOKEN=<strong-secret>   # required before public tunnels
```

Install Aya weights (one-time): `bash scripts/setup_paper_aya_local.sh`

### 2. Install always-on LaunchAgents (no sudo)

```bash
bash scripts/install_macos_user_server.sh
```

Installs and starts:

- `com.uml.pipeline.api` — FastAPI `:8000`
- `com.uml.pipeline.ui` — Streamlit `:8501`
- `com.uml.pipeline.tunnels` — Cloudflare quick tunnels
- `com.uml.pipeline.caffeinate` — prevent sleep while logged in
- `com.uml.pipeline.ollama24` — Ollama 0.24 on `:11434`
- `com.uml.pipeline.ollama32` — Ollama 0.32 on `:11435`

**Survives:** Cursor quit, Terminal close, screen lock.  
**Does not survive:** full Log Out of the macOS user (no admin LaunchDaemons).  
**Multi-user:** keep this account logged in; others use Fast User Switching.

### 3. Check status

```bash
bash scripts/macos_server_status.sh
curl -s http://127.0.0.1:8000/api/settings/health | python3 -m json.tool
```

Public URLs (when tunnels are up):

```bash
cat data/run/public_ui_url.txt
cat data/run/public_api_url.txt
```

### 4. Restart API after code or `.env` changes

```bash
bash scripts/restart_api.sh
```

Safe while LoRA training runs — only recycles the API process.

### 5. Remote command agent (control server from another device)

The API exposes an authenticated command agent at `/api/agent`. Public URL is tracked in repo root [`Link`](../Link) / [`Link.md`](../Link.md).

```bash
# On the Mac Studio — read token from .env (never commit or paste in chat)
export TOKEN="$(grep '^API_ACCESS_TOKEN=' .env | cut -d= -f2-)"
export AGENT="$(cat data/run/public_api_url.txt)/api/agent"

curl -s "$AGENT/health" | python3 -m json.tool
curl -s -X POST "$AGENT/command" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"server-status"}'
```

Screen lock is fine; do **not** Log Out. After code lands on GitHub, `pull-main` then `restart-api` loads it without a Terminal session. `publish-urls` pushes the current Cloudflare hostnames to `Link.md`.

Rollback: point `.env` at a prior adapter (e.g. `models/uml-plantuml-lora-200k`) and `bash scripts/restart_api.sh`.

### 6. Tunnel monitoring and email alerts

```bash
# One-shot health check + tunnel restart if needed
bash scripts/monitor_public_tunnels.sh --once

# Continuous loop (or install tunnel monitor LaunchAgent)
bash scripts/monitor_public_tunnels.sh --loop
bash scripts/install_tunnel_monitor.sh
```

SMTP settings in `.env` for failure notifications (`NOTIFY_EMAIL`, `SMTP_*`). Do not commit credentials.

### 7. Uninstall

```bash
bash scripts/uninstall_macos_user_server.sh
```

---

## Option B — Interactive local (development)

```bash
make run          # ./scripts/run_local.sh — dual Ollama + API + UI
# or separately:
make api          # terminal 1
make ui           # terminal 2
```

Public tunnels (manual):

```bash
bash scripts/start_public_tunnels.sh
```

**Note:** If LaunchAgents are already running, `make run` will boot them out to free ports `:8000`/`:8501`.

---

## Option C — Render from GitHub (cloud demo)

GitHub Pages serves static HTML only — it cannot run FastAPI or Streamlit. Use Render for a hosted demo without Apple Silicon.

1. Push `main` to GitHub.
2. https://render.com → **New → Blueprint** → select the repo.
3. Render reads `render.yaml` and creates `uml-pipeline-api` + `uml-pipeline-ui`.
4. Set `API_ACCESS_TOKEN` in both services (sync:false secret in blueprint).

Cloud defaults: `MOCK_PROVIDERS=true`, `USE_FINETUNED_CODE=false` (MLX LoRA unavailable). Free tier sleeps after ~15 minutes idle.

See [render.yaml](../render.yaml).

---

## Option D — Railway (alternative cloud)

1. https://railway.app → **Deploy from GitHub**.
2. Two services:

| Service | Start command |
|---------|----------------|
| api | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| ui | `streamlit run ui/streamlit_app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true` |

3. Env: `PYTHONPATH=.` `MOCK_PROVIDERS=true` `PLANTUML_REMOTE=true`  
4. UI only: `API_BASE_URL=https://YOUR-API-PUBLIC-URL`

---

## Option E — Docker

```bash
docker compose up --build -d
# UI :8501  API :8000
```

---

## Option F — Temporary laptop link

```bash
make run
ngrok http 8501
```

Only while the machine is on — not a permanent site.

---

## Environment summary

| Variable | Mac production | Cloud demo |
|----------|----------------|------------|
| `MOCK_PROVIDERS` | `false` | `true` |
| `USE_OLLAMA` | `true` | `false` |
| `USE_FINETUNED_CODE` | `true` | `false` |
| `VLM_AYA_BACKEND` | `local` | `ollama_standin` or mock |
| `API_BASE_URL` | `http://127.0.0.1:8000` | Public API URL (UI service) |
| `API_ACCESS_TOKEN` | **Required** for tunnels | **Required** for public deploy |
| `PLANTUML_PREFER_LOCAL` | `true` | `false` (remote fallback) |

Do **not** commit `.env` or secrets. Set keys only in the host dashboard or local `.env`.

---

## LoRA training (offline, same machine)

Training does not block the API but competes for GPU/CPU:

```bash
make train-50k          # → models/uml-plantuml-lora-50k (superseded)
make train-100k         # → models/uml-plantuml-lora-100k (superseded)
make train-200k         # → models/uml-plantuml-lora-200k (superseded)
make train-source30k    # → models/uml-plantuml-lora-sourcecode-30k (production)
```

After swapping adapters, update `FINETUNED_ADAPTER_PATH` and `bash scripts/restart_api.sh`.
