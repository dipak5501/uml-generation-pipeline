# Remote access — UML-Pipeline (Mac Studio server)

This **Mac Studio** runs the always-on UML-Pipeline server. Keep the **Dipak Yadav** macOS account logged in (screen lock is fine; use Fast User Switch for other users — **do not Log Out**).

## Open from any device

**Live UI:** [https://thousands-steal-configuration-adaptive.trycloudflare.com](https://thousands-steal-configuration-adaptive.trycloudflare.com)

| Endpoint | URL |
|----------|-----|
| Public UI (browser, any network) | https://thousands-steal-configuration-adaptive.trycloudflare.com |
| Public API (docs / exports) | https://fellowship-exclude-clarity-nano.trycloudflare.com |
| Remote command agent | https://fellowship-exclude-clarity-nano.trycloudflare.com/api/agent |
| Local Streamlit (this Mac) | http://127.0.0.1:8501 |
| Local FastAPI (this Mac) | http://127.0.0.1:8000 |

Quick-tunnel URLs **change every time tunnels restart**. Auto-updated by `scripts/tunnel_notify.py` whenever tunnels publish. Canonical copies: `data/run/public_ui_url.txt` and `data/run/public_api_url.txt`.

Updated: 2026-09-06 06:20 UTC

## Authentication

`API_ACCESS_TOKEN` must be set in **`.env` on this Mac** (never commit). Streamlit sends `Authorization: Bearer …` automatically. Remote agent commands use the same token (or optional `REMOTE_AGENT_TOKEN`).

## Remote command agent

Control this Mac Studio from any device (phone, laptop, another network).

| Endpoint | URL |
|----------|-----|
| Agent health (open) | `https://fellowship-exclude-clarity-nano.trycloudflare.com/api/agent/health` |
| Submit command (auth) | `POST https://fellowship-exclude-clarity-nano.trycloudflare.com/api/agent/command` |
| Task status (auth) | `GET https://fellowship-exclude-clarity-nano.trycloudflare.com/api/agent/tasks/{task_id}` |

**Auth:** `Authorization: Bearer <API_ACCESS_TOKEN>` or `X-API-Key` (or dedicated `REMOTE_AGENT_TOKEN` from `.env` on this Mac — never commit).

**Example from phone/laptop:**

```bash
export TOKEN="your-token-from-env"
curl -s "https://fellowship-exclude-clarity-nano.trycloudflare.com/api/agent/health" | python3 -m json.tool
curl -s -X POST "https://fellowship-exclude-clarity-nano.trycloudflare.com/api/agent/command" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"health"}'
```

Allowlisted commands: `health`, `restart-api`, `restart-ui`, `restart-tunnels`, `publish-urls`, `pull-main`, `smoke-test`, `generate`, `training-status`, `server-status`, `agent-prompt` (needs `CURSOR_API_KEY`).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Cloudflare **1033 / 530** | `cloudflared` died — `bash scripts/start_public_tunnels.sh` |
| Cloudflare **429 / 1015** | Wait 15–30 min, then `bash scripts/start_public_tunnels.sh` |
| Local UI/API down | `bash scripts/macos_server_status.sh` or reinstall LaunchAgents |
| Stale Link | `bash scripts/ensure_public_tunnel.sh` (or wait for tunnel-monitor) |

See also: [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md)

## Git auto-sync

Safe changes push to [github.com/dipak5501/uml-generation-pipeline](https://github.com/dipak5501/uml-generation-pipeline) automatically (~45 min LaunchAgent + after every tunnel/Link update).

- Manual full sync: `bash scripts/auto_sync_all.sh`
- Git only: `bash scripts/git_auto_push.sh`
- See [docs/git_sync.md](docs/git_sync.md)
