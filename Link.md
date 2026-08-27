# Remote access — UML-Pipeline (Mac Studio server)

This **Mac Studio** runs the always-on UML-Pipeline server. Keep the **Dipak Yadav** macOS account logged in (screen lock is fine; use Fast User Switch for other users — **do not Log Out**).

## Open from any device

**Live UI:** [https://vcr-calculations-sub-gossip.trycloudflare.com](https://vcr-calculations-sub-gossip.trycloudflare.com)

| Endpoint | URL |
|----------|-----|
| Public UI (browser, any network) | https://vcr-calculations-sub-gossip.trycloudflare.com |
| Public API (docs / exports) | https://computed-soma-toner-architecture.trycloudflare.com |
| Local Streamlit (this Mac) | http://127.0.0.1:8501 |
| Local FastAPI (this Mac) | http://127.0.0.1:8000 |

Quick-tunnel URLs **change every time tunnels restart**. Auto-updated by `scripts/tunnel_notify.py` whenever tunnels publish. Canonical copies: `data/run/public_ui_url.txt` and `data/run/public_api_url.txt`.

Updated: 2026-08-27 19:10 UTC

## Authentication

`API_ACCESS_TOKEN` must be set in **`.env` on this Mac** (never commit). Streamlit sends `Authorization: Bearer …` automatically.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Cloudflare **429 / 1015** | Wait 15–30 min, then `bash scripts/start_public_tunnels.sh` |
| Local UI/API down | `bash scripts/macos_server_status.sh` or reinstall LaunchAgents |
| Stale Link | `bash scripts/ensure_public_tunnel.sh` (or wait for tunnel-monitor) |

See also: [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md)
