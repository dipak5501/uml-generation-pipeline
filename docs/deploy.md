# Go live with UML-Pipeline (via GitHub)

GitHub hosts your **code** (and an optional **`.github.io` landing page**).  
A free cloud host runs the **interactive app** 24/7 so you do not need Cursor open.

**Important:** [GitHub Pages](https://pages.github.com/) only serves static HTML. It cannot run FastAPI or Streamlit. Use Pages for the project site; use **Render** for the working UML generator UI.

| Surface | URL pattern | What it is |
|---------|-------------|------------|
| GitHub Pages | `https://dipak5501.github.io/uml-generation-pipeline/` | Static landing / docs entry |
| Render UI | `https://uml-pipeline-ui.onrender.com` (after deploy) | Live Streamlit app |

---

## Option 0 — GitHub Pages landing (`.github.io`)

Already configured in this repo (`site/` + `.github/workflows/pages.yml`).

1. Push `main` to GitHub (includes the Pages workflow).
2. On the repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Open: https://dipak5501.github.io/uml-generation-pipeline/

Optional: after Render is live, open the landing with your app URL:

`https://dipak5501.github.io/uml-generation-pipeline/?app=https://YOUR-UI.onrender.com`

---

## Option A — Render from GitHub (recommended for the real app)

Your repo already includes `render.yaml` (API + UI).

### Steps

1. Push latest `main` to GitHub (this repo: `dipak5501/uml-generation-pipeline`).
2. Create a free account at https://render.com and sign in with **GitHub**.
3. In Render: **New → Blueprint**.
4. Select repository **`dipak5501/uml-generation-pipeline`** (grant access if asked).
5. Render reads `render.yaml` and creates:
   - `uml-pipeline-api` — FastAPI
   - `uml-pipeline-ui` — Streamlit (UML-Pipeline website)
6. Click **Apply** / deploy. Wait until both services are **Live** (first build ~5–10 minutes).
7. Open the **uml-pipeline-ui** public URL (looks like `https://uml-pipeline-ui.onrender.com`).

That UI URL is what you share. No Cursor required afterward.

### After every `git push` to `main`

Render can auto-redeploy if you enable auto-deploy on the services (default for Blueprints).

### Harden a public deploy (required for anything beyond a private demo)

In both Render services, set the **same** secret:

| Env var | Purpose |
|---------|---------|
| `API_ACCESS_TOKEN` | Shared secret; API rejects generate/export/repair/review without `Authorization: Bearer …` or `X-API-Key` |
| `CORS_ORIGINS` | Optional comma-separated UI origins (default `*` for demos) |

`render.yaml` already declares `API_ACCESS_TOKEN` as a sync:false secret — set it in the Render dashboard. Without it, health reports that the API is open.

### Free-tier note

Idle free services **sleep** after ~15 minutes. The first visit after sleep can take 30–60 seconds to wake.

### Fine-tuned LoRA on Render

Cloud free instances usually cannot load MLX LoRA (Apple Silicon). The blueprint sets `USE_FINETUNED_CODE=false` and uses mock/base providers online. Local Mac demos can still use your fine-tuned adapters.

---

## Option B — Railway (alternative)

1. https://railway.app → **New Project** → **Deploy from GitHub**.
2. Add **two** services from the same repo:

| Service | Start command |
|---------|----------------|
| api | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| ui | `streamlit run ui/streamlit_app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true` |

3. Env (both): `PYTHONPATH=.` `MOCK_PROVIDERS=true` `PLANTUML_REMOTE=true`
4. UI only: `API_BASE_URL=https://YOUR-API-PUBLIC-URL`

---

## Option C — Docker on a cloud VM

```bash
git clone https://github.com/dipak5501/uml-generation-pipeline.git
cd uml-generation-pipeline
docker compose up --build -d
```

- UI: `http://YOUR_SERVER_IP:8501`
- API: `http://YOUR_SERVER_IP:8000`

---

## Option D — Temporary link from your laptop

```bash
make api   # terminal 1
make ui    # terminal 2
ngrok http 8501   # terminal 3
```

Only while your machine is on — not a permanent site.

---

## Environment summary

| Variable | Online default |
|----------|----------------|
| `MOCK_PROVIDERS` | `true` |
| `PLANTUML_REMOTE` | `true` |
| `API_BASE_URL` | Public API URL (set on UI service) |
| `USE_FINETUNED_CODE` | `false` on free cloud |

Do **not** commit `.env` secrets. Set keys only in the host dashboard if you enable live models.

---

## Local development (unchanged)

```bash
make run          # recommended: API + UI together
# or:
make api          # terminal 1
make ui           # terminal 2
```

http://127.0.0.1:8501
