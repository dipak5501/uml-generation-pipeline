# Launch this website live

You have two processes: **API** (FastAPI `:8000`) and **UI** (Streamlit `:8501`).  
For a public demo, deploy both (Docker is easiest).

## Option A — Fastest personal demo (temporary public URL)

On your laptop (API + UI already running):

```bash
# Terminal 1
make api

# Terminal 2
make ui

# Terminal 3 — install once: https://ngrok.com
ngrok http 8501
```

Ngrok gives a public HTTPS link to the UI.  
Also expose the API if the UI is configured with a remote `API_BASE_URL`, or keep both local behind one reverse proxy.

Good for class/thesis demos lasting hours, not months.

## Option B — Docker on a cloud VM (recommended for a stable site)

1. Push the repo to GitHub (already done: `dipak5501/uml-generation-pipeline`).
2. Create a small VM (DigitalOcean, AWS Lightsail, Linode, Google Cloud) with Docker.
3. On the VM:

```bash
git clone https://github.com/dipak5501/uml-generation-pipeline.git
cd uml-generation-pipeline
docker compose up --build -d
```

Open:
- UI: `http://YOUR_SERVER_IP:8501`
- API docs: `http://YOUR_SERVER_IP:8000/docs`

Optional: point a domain + HTTPS with Caddy/Nginx reverse proxy to port `8501`.

## Option C — Railway / Render / Fly.io

### Railway (simple)

1. Create a Railway project from the GitHub repo.
2. Add **two services** from the same repo:
   - **api**: start command  
     `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **ui**: start command  
     `streamlit run ui/streamlit_app.py --server.port $PORT --server.address 0.0.0.0`
3. Environment variables (both):

```env
MOCK_PROVIDERS=true
PLANTUML_REMOTE=true
PYTHONPATH=.
```

4. For the UI service set:

```env
API_BASE_URL=https://YOUR-API-SERVICE.up.railway.app
```

5. Deploy. Share the **UI** public URL.

Render is similar: one Web Service for API, one for Streamlit, same env vars.

## Option D — Streamlit Community Cloud (UI only)

Streamlit Cloud can host the UI for free, but **not** the FastAPI backend by itself.

Use only if you also host the API elsewhere, then set:

```env
API_BASE_URL=https://your-api-host.example.com
```

## What you need from your side

| Item | Needed? |
|------|---------|
| GitHub repo | Already have |
| Cloud account (Railway / Render / DigitalOcean) | Yes for permanent live site |
| Domain name | Optional |
| OpenAI / Ollama keys | Optional (`MOCK_PROVIDERS=true` works without keys) |
| Java JDK on server | Optional if `PLANTUML_REMOTE=true` |

## Security notes for public demos

- Keep `MOCK_PROVIDERS=true` for public demos unless you intend to pay for model APIs.
- Do not commit `.env` with secrets.
- If you enable live models, put API keys only in the host’s secret env vars.

## Local attractive UI after pull

```bash
make api   # terminal 1
make ui    # terminal 2
```

Then open http://127.0.0.1:8501
