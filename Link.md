# Remote access — UML-Pipeline (Mac Studio server)

This **Mac Studio** runs the always-on UML-Pipeline server. Keep the **Dipak Yadav** macOS account logged in (screen lock is fine; use Fast User Switch for other users — **do not Log Out**).

## Current public UI URL

**Status (2026-08-26):** Cloudflare quick tunnels are **offline** — restart hit Cloudflare rate limit (429 / error 1015). Wait ~15 minutes, then run:

```bash
bash scripts/start_public_tunnels.sh
bash scripts/macos_server_status.sh
```

Copy the **UI** line from status output into [`Link`](Link) at repo root for easy sharing.

| Endpoint | URL |
|----------|-----|
| Public UI (browser, any network) | *(none live — see above)* |
| Public API (browser/docs only) | *(none live — see above)* |
| Last notified UI (stale) | `https://portable-oxford-supreme-evident.trycloudflare.com` |

Quick-tunnel URLs **change every time tunnels restart**. Canonical runtime copies: `data/run/public_ui_url.txt` and `data/run/public_api_url.txt` (gitignored).

## Local URLs (this Mac only)

| Service | URL |
|---------|-----|
| Streamlit UI | http://127.0.0.1:8501 |
| FastAPI | http://127.0.0.1:8000 |
| API health | http://127.0.0.1:8000/api/settings/health |

The Streamlit UI always talks to the API at **http://127.0.0.1:8000** on the server, even when you open the app via a Cloudflare link in a remote browser.

## Authentication

`API_ACCESS_TOKEN` must be set in **`.env` on this Mac** (never commit). Streamlit sends `Authorization: Bearer …` automatically. Do not paste the token into this file or into chat.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Cloudflare **Error 1033** (tunnel unreachable) | Restart tunnels: `bash scripts/start_public_tunnels.sh` |
| **429 / 1015** when starting tunnels | Cloudflare rate limit — wait ~15 min, retry once |
| **Errno 8** / DNS errors from UI | UI must use localhost API (`API_BASE_URL=http://127.0.0.1:8000`) — already the default |
| Local UI/API down | `bash scripts/macos_server_status.sh` — check launchctl and `:8501` / `:8000` |

## Related docs

- [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) — architecture, LaunchAgents, tunnels
- [scripts/install_macos_user_server.sh](scripts/install_macos_user_server.sh) — install always-on user services
- [scripts/macos_server_status.sh](scripts/macos_server_status.sh) — status + current public URLs
- [scripts/start_public_tunnels.sh](scripts/start_public_tunnels.sh) — start / refresh Cloudflare tunnels
