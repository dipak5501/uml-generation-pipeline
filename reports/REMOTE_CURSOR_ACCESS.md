# Remote Cursor Access — UML-Pipeline Mac Studio

**For:** Dipak Yadav  
**Server:** Mac Studio (always-on UML-Pipeline)  
**Updated:** 2026-09-06 06:18 UTC
**Repo:** https://github.com/dipak5501/uml-generation-pipeline

---

## Current public URLs

<!-- LIVE_DEMO_BEGIN -->
**Live demo (as of 2026-09-06):**

- **UI:** [https://march-specifics-virtue-ink.trycloudflare.com](https://march-specifics-virtue-ink.trycloudflare.com)
- **API:** [https://pit-handy-toolkit-hist.trycloudflare.com](https://pit-handy-toolkit-hist.trycloudflare.com)
- **Agent:** [https://pit-handy-toolkit-hist.trycloudflare.com/api/agent](https://pit-handy-toolkit-hist.trycloudflare.com/api/agent)

Quick-tunnel URLs rotate on restart. This block is rewritten by `scripts/tunnel_notify.py` whenever tunnels publish (GitHub is updated via `scripts/git_auto_push.sh`). Always-current copy: [../Link.md](../Link.md). On the Mac Studio: `data/run/public_ui_url.txt`, `data/run/public_api_url.txt`.
<!-- LIVE_DEMO_END -->

| Endpoint | URL |
|----------|-----|
| **Public UI** (browser, any network) | **offline** |
| **Public API** (docs, generate, exports) | **offline** |
| **Remote command agent** | **offline** |
| Local Streamlit (Mac only) | http://127.0.0.1:8501 |
| Local FastAPI (Mac only) | http://127.0.0.1:8000 |

Canonical URL files (auto-updated when tunnels restart):

- `data/run/public_ui_url.txt`
- `data/run/public_api_url.txt`

Quick-tunnel URLs **change every time Cloudflare tunnels restart**. Check `Link` or `Link.md` at repo root for the latest.

---

## Environment status (Mac Studio)

| Variable | Status |
|----------|--------|
| `API_ACCESS_TOKEN` | **SET** |
| `CURSOR_API_KEY` | **NOT SET** |

`agent-prompt` commands require `CURSOR_API_KEY` in `.env` on the Mac Studio plus `cursor-sdk` installed.

---

## Get token on Mac Studio (never paste in chat)

On the Mac Studio, in the project directory:

```bash
grep '^API_ACCESS_TOKEN=' .env
```

Copy the value **locally** into an environment variable on your remote device — do not paste secrets into Cursor chat or commit `.env`.

```bash
export TOKEN="$(grep '^API_ACCESS_TOKEN=' .env | cut -d= -f2-)"
export AGENT_URL="$(cat data/run/public_api_url.txt)/api/agent"
export API_URL="$(cat data/run/public_api_url.txt)"
```

On Device B (laptop, phone, another Cursor):

```bash
export TOKEN="paste-value-locally-not-in-chat"
export AGENT_URL="https://pit-handy-toolkit-hist.trycloudflare.com/api/agent"
export API_URL="https://pit-handy-toolkit-hist.trycloudflare.com"
```

**Auth headers:** `Authorization: Bearer $TOKEN` or `X-API-Key: $TOKEN`  
Optional dedicated token: `REMOTE_AGENT_TOKEN` in `.env` (falls back to `API_ACCESS_TOKEN`).

---

## curl examples

### Agent health (no auth required)

```bash
curl -s "$AGENT_URL/health" | python3 -m json.tool
```

### Submit command — health check

```bash
curl -s -X POST "$AGENT_URL/command" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"health"}' | python3 -m json.tool
```

Returns `task_id`. Poll until `status` is `completed` or `failed`.

### Submit command — server status

```bash
curl -s -X POST "$AGENT_URL/command" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"server-status"}' | python3 -m json.tool
```

### Submit command — smoke test (~15 min)

```bash
curl -s -X POST "$AGENT_URL/command" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"smoke-test"}' | python3 -m json.tool
```

### Submit command — generate UML

```bash
curl -s -X POST "$AGENT_URL/command" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "generate",
    "args": {
      "requirement": "Bookstore with carts, orders, and inventory.",
      "diagram_type": "class",
      "input_mode": "requirement",
      "skip_vlm": true
    }
  }' | python3 -m json.tool
```

### Submit command — training status

```bash
curl -s -X POST "$AGENT_URL/command" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"training-status"}' | python3 -m json.tool
```

### Submit command — restart API / UI

```bash
curl -s -X POST "$AGENT_URL/command" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"restart-api"}' | python3 -m json.tool

curl -s -X POST "$AGENT_URL/command" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"restart-ui"}' | python3 -m json.tool
```

### Submit command — agent-prompt (requires CURSOR_API_KEY on Mac)

```bash
curl -s -X POST "$AGENT_URL/command" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "agent-prompt",
    "args": {
      "prompt": "Run scripts/macos_server_status.sh and summarize the output."
    }
  }' | python3 -m json.tool
```

### Poll task status

```bash
TASK_ID="abc123def456"   # from POST /command response
curl -s "$AGENT_URL/tasks/$TASK_ID" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Poll loop (bash):

```bash
TASK_ID="abc123def456"
while true; do
  STATUS=$(curl -s "$AGENT_URL/tasks/$TASK_ID" -H "Authorization: Bearer $TOKEN" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))")
  echo "status: $STATUS"
  case "$STATUS" in completed|failed) break ;; esac
  sleep 5
done
curl -s "$AGENT_URL/tasks/$TASK_ID" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### List recent tasks

```bash
curl -s "$AGENT_URL/tasks?limit=10" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### Direct API health (no auth)

```bash
curl -s "$API_URL/api/settings/health" | python3 -m json.tool
```

### Direct API generate (auth required)

```bash
curl -s -X POST "$API_URL/api/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "requirement": "Library system with books, members, and loans.",
    "diagram_type": "class",
    "input_mode": "requirement",
    "async_mode": false,
    "skip_vlm": true
  }' | python3 -m json.tool
```

---

## Allowed agent commands

| Command | Description | Typical duration |
|---------|-------------|------------------|
| `health` | Calls `/api/settings/health` on the Mac Studio API | seconds |
| `server-status` | Runs `scripts/macos_server_status.sh` (API, UI, Ollama, tunnels) | seconds |
| `smoke-test` | Runs `scripts/smoke_test.py` (full pipeline check) | up to ~15 min |
| `generate` | POSTs to `/api/generate` with optional `args` | 1–5 min |
| `training-status` | LoRA adapter path, finetune meta, running processes | seconds |
| `restart-api` | Runs `scripts/restart_api.sh` | ~30 sec |
| `restart-ui` | Runs `scripts/restart_ui.sh` | ~30 sec |
| `restart-tunnels` | Runs `scripts/start_public_tunnels.sh` (new trycloudflare URLs) | ~1–3 min |
| `publish-urls` | Pushes current `data/run/public_*_url.txt` to GitHub `Link.md` / `Link` | ~30s |
| `pull-main` | `git fetch` + `git reset --hard origin/main` (then run `restart-api`) | ~30s |
| `agent-prompt` | Runs a Cursor SDK local agent on the Mac (`args.prompt` or `args.text`) | varies |

**`generate` args (all optional):**

- `requirement` — natural-language spec (default: bookstore test)
- `diagram_type` — `class`, `object`, `component`, `package` (default: `class`)
- `input_mode` — `requirement` or `source_code` (default: `requirement`)
- `async_mode` — boolean (default: `false`)
- `skip_vlm` — boolean (default: `true`)

**Rate limit:** configurable via `REMOTE_AGENT_RATE_LIMIT` (default enforced per client IP per minute).

---

## Limitations

1. **Not remote Cursor IDE** — You cannot open the Mac Studio's Cursor UI from another device. Control is via HTTP API or Cursor Cloud Agent against the GitHub repo.
2. **Cloudflare quick tunnels** — URLs change when tunnels restart. Re-read `Link`, `Link.md`, or `data/run/public_*.txt` before each session.
3. **Queued execution** — Commands run in a thread pool (max 2 workers). Long tasks (`smoke-test`, `generate`) block other commands until done.
4. **Auth required** — When `API_ACCESS_TOKEN` is set (it is), all mutating agent endpoints require the token.
5. **`agent-prompt` disabled** — `CURSOR_API_KEY` is not set on the Mac Studio. Set it in `.env` and install `cursor-sdk` to enable.
6. **Mac must stay logged in** — Dipak Yadav account logged in (screen lock OK; do not Log Out). LaunchAgents keep API/UI/tunnels running.
7. **No shell access** — Only allowlisted commands; arbitrary shell is not exposed.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Cloudflare **429 / 1015** | Wait 15–30 min, then `bash scripts/start_public_tunnels.sh` on Mac |
| 401 Unauthorized | Token mismatch — re-read from Mac `.env`, never from chat history |
| Stale URLs on GitHub | On Mac: `cat /tmp/uml-git-live-urls.log data/run/github_url_push.status`; rotate `GH_TOKEN` in `.env` (do not paste); `bash scripts/git_push_live_urls.sh` |
| Stale URLs | `bash scripts/ensure_public_tunnel.sh` or check `Link` |
| Local services down | `bash scripts/macos_server_status.sh` on Mac |
| Task stuck `queued` | Another long task may be running; poll or wait |

---

## COPY-PASTE PROMPT FOR OTHER CURSOR (Device B)

Paste everything below into a **new Cursor chat on your laptop/phone/other Mac**. Replace placeholders before starting — **never paste the real token into chat**; set it as an env var in your terminal instead.

```
You are a remote operator for the UML-Pipeline Mac Studio server owned by Dipak Yadav.

## Connection (set in terminal — NEVER paste TOKEN into this chat)

export TOKEN="<API_ACCESS_TOKEN from Mac Studio .env>"
export AGENT_URL="https://pit-handy-toolkit-hist.trycloudflare.com/api/agent"
export API_URL="https://pit-handy-toolkit-hist.trycloudflare.com"
export UI_URL="https://march-specifics-virtue-ink.trycloudflare.com"

On the Mac Studio the token is obtained with:
  grep '^API_ACCESS_TOKEN=' /path/to/uml-generation-pipeline/.env

If the user has not set TOKEN in their shell, ask them to export it locally. Do NOT ask them to paste the token in chat. Use curl with $TOKEN from their environment.

URLs change when Cloudflare tunnels restart. If requests fail with DNS/404 errors, tell the user to check Link or data/run/public_api_url.txt on the Mac Studio.

## Your job

Control the Mac Studio UML server via the remote agent HTTP API. You do NOT have SSH or direct filesystem access — only HTTP.

## API reference

- GET  $AGENT_URL/health          — no auth; returns allowed_commands, auth_required, cursor_agent_enabled
- POST $AGENT_URL/command         — auth: Authorization: Bearer $TOKEN
- GET  $AGENT_URL/tasks/{task_id} — auth required; poll until status is completed or failed
- GET  $AGENT_URL/tasks?limit=20  — list recent tasks
- GET  $API_URL/api/settings/health — direct API health (no auth)

POST /command body: {"command":"<name>", "args":{...}}

Allowed commands:
  health, server-status, smoke-test, generate, training-status, restart-api, restart-ui, agent-prompt

## Standard workflows

### 1. Check agent is alive
curl -s "$AGENT_URL/health" | python3 -m json.tool

### 2. Server status
TASK=$(curl -s -X POST "$AGENT_URL/command" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"command":"server-status"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
Poll: curl -s "$AGENT_URL/tasks/$TASK" -H "Authorization: Bearer $TOKEN"

### 3. Health (pipeline providers)
Same pattern with {"command":"health"}

### 4. Generate UML diagram
POST command generate with args:
  {"requirement":"...", "diagram_type":"class", "input_mode":"requirement", "skip_vlm":true}
Poll task; result contains generation JSON in result field.

### 5. Smoke test (long — warn user, ~15 min)
{"command":"smoke-test"}

### 6. Poll helper
After every POST /command, extract task_id and poll every 5s until status is completed or failed. Show result.output and result.result to the user. On failed, show error field.

## GitHub Cloud Agent (alternative)

For code changes, docs, or repo work without hitting the Mac API:
  Repository: https://github.com/dipak5501/uml-generation-pipeline
  Branch: main (auto-syncs from Mac Studio ~45 min)

Use Cursor Cloud Agent against that repo when the task is editing code or reading docs — use the Mac agent API when the task requires running generation, smoke tests, or checking live server status on Apple Silicon hardware.

## Security rules

- NEVER ask the user to paste API_ACCESS_TOKEN or REMOTE_AGENT_TOKEN in chat.
- NEVER commit or log tokens.
- Use $TOKEN from the user's shell environment for all curl calls.
- If auth fails (401), instruct user to re-export TOKEN from Mac .env locally.

## When user asks to "control the Mac" or "run UML server"

1. Verify AGENT_URL/health responds
2. Run server-status
3. Report UI_URL for browser access
4. Offer generate or smoke-test if they want validation

Begin by confirming TOKEN is exported in the terminal (yes/no only — do not ask for the value).
```

---

## COPY-PASTE PROMPT FOR agent-prompt (when CURSOR_API_KEY configured)

Use this **only after** `CURSOR_API_KEY` is set in `.env` on the Mac Studio and `cursor-sdk` is installed. Submit via the remote agent API — the Mac runs a **local Cursor agent** in the project directory.

```bash
curl -s -X POST "$AGENT_URL/command" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "agent-prompt",
    "args": {
      "prompt": "PASTE PROMPT BELOW AS ONE STRING"
    }
  }' | python3 -m json.tool
```

**Prompt to put in `args.prompt`:**

```
You are the on-Mac Studio Cursor agent for uml-generation-pipeline at the project root.

Tasks you can perform locally (Apple Silicon, MLX/Ollama):
- Read and edit repo files under the project root
- Run bash scripts: scripts/macos_server_status.sh, scripts/smoke_test.py, scripts/restart_api.sh, scripts/restart_ui.sh
- Check models/ adapter paths and finetune status
- Inspect data/run/public_api_url.txt and Link for current tunnel URLs

Constraints:
- Do not expose secrets from .env (API_ACCESS_TOKEN, HF_TOKEN, CURSOR_API_KEY, SMTP passwords)
- Do not git push unless the user explicitly asks
- Prefer scripts/ over ad-hoc commands for server operations
- Report public UI/API URLs from data/run/ when discussing remote access

Current adapter: models/uml-plantuml-lora-sourcecode-30k

User request: [DESCRIBE WHAT THE USER WANTS DONE ON THE MAC STUDIO]
```

Poll the returned `task_id` until complete. The `result` field contains `status`, `result`, and `agent_id` from the Cursor SDK run.

**Note:** As of 2026-08-31, `CURSOR_API_KEY` is **NOT SET** on the Mac Studio — `agent-prompt` will fail until configured.

---

## Quick reference card

```
UI:     https://march-specifics-virtue-ink.trycloudflare.com
API:    https://march-specifics-virtue-ink.trycloudflare.com
Agent:  https://pit-handy-toolkit-hist.trycloudflare.com/api/agent

Mac token:  grep '^API_ACCESS_TOKEN=' .env
Export:     export TOKEN="$(grep '^API_ACCESS_TOKEN=' .env | cut -d= -f2-)"
Health:     curl -s $AGENT_URL/health
Command:    curl -s -X POST $AGENT_URL/command -H "Authorization: Bearer $TOKEN" \
              -H "Content-Type: application/json" -d '{"command":"server-status"}'
Poll:       curl -s $AGENT_URL/tasks/TASK_ID -H "Authorization: Bearer $TOKEN"
```

See also: [Link.md](../Link.md) · [docs/deploy.md](../docs/deploy.md) · [docs/SYSTEM_DESIGN.md](../docs/SYSTEM_DESIGN.md)
