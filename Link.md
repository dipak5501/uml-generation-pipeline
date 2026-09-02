# Remote access — UML-Pipeline (Mac Studio server)

This **Mac Studio** runs the always-on UML-Pipeline server. Keep the **Dipak Yadav** macOS account logged in (screen lock is fine; use Fast User Switch for other users — **do not Log Out**).

## Open from any device

**Live UI:** **offline** as of 2026-09-02 18:56 UTC.

The previous GitHub hostnames (`individual-cinema-uri-checkout.trycloudflare.com` and `hypothetical-advanced-meanwhile-wow.trycloudflare.com`) **do not resolve**. Cloudflare quick-tunnel names are deleted when the Mac `cloudflared` process stops. This cloud checkout cannot mint a new public hostname.

| Endpoint | URL |
|----------|-----|
| Public UI (browser, any network) | **offline** — start tunnels on the Mac (below) |
| Public API (docs / exports) | **offline** |
| Remote command agent | **offline** |
| Local Streamlit (this Mac) | http://127.0.0.1:8501 |
| Local FastAPI (this Mac) | http://127.0.0.1:8000 |

On the Mac Studio:

```bash
cd /Users/033783670/Desktop/uml-generation-pipeline-main
git checkout main && git pull origin main
bash scripts/bring_up_public_links.sh
cat data/run/public_ui_url.txt
```

That command writes a **new** `https://….trycloudflare.com` into this file and pushes GitHub `main`. Until then there is no public URL.

Canonical copies on the Mac: `data/run/public_ui_url.txt` and `data/run/public_api_url.txt`.

Updated: 2026-09-02 18:56 UTC

## Authentication

`API_ACCESS_TOKEN` must be set in **`.env` on this Mac** (never commit). Streamlit sends `Authorization: Bearer …` automatically. Remote agent commands use the same token (or optional `REMOTE_AGENT_TOKEN`).

## Remote command agent

Control this Mac Studio from any device after tunnels are up. Until then use local `http://127.0.0.1:8000/api/agent`.

**Auth:** `Authorization: Bearer <API_ACCESS_TOKEN>` or `X-API-Key` (or dedicated `REMOTE_AGENT_TOKEN` from `.env` on this Mac — never commit).

Allowlisted commands: `health`, `restart-api`, `restart-ui`, `restart-tunnels`, `smoke-test`, `generate`, `training-status`, `server-status`, `agent-prompt` (needs `CURSOR_API_KEY`).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Cloudflare **429 / 1015** | Wait 15–30 min, then `bash scripts/start_public_tunnels.sh` |
| Local UI/API down | `bash scripts/macos_server_status.sh` or reinstall LaunchAgents |
| Stale Link on GitHub | `bash scripts/bring_up_public_links.sh` then `cat data/run/github_url_push.status` |

See also: [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md)

## Git auto-sync

Safe changes push to [github.com/dipak5501/uml-generation-pipeline](https://github.com/dipak5501/uml-generation-pipeline) automatically (~45 min LaunchAgent + after every tunnel/Link update).

- Manual full sync: `bash scripts/auto_sync_all.sh`
- Git only: `bash scripts/git_auto_push.sh`
- Live URLs: `bash scripts/git_push_live_urls.sh`
- See [docs/git_sync.md](docs/git_sync.md)
