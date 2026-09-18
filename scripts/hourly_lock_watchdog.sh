#!/usr/bin/env bash
# Hourly lock-screen watchdog: analyze stack health + keep GitHub Link current.
# Screen lock is OK; keep the Dipak Yadav user logged in (do NOT Log Out).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="$ROOT/.venv/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

RUN_DIR="$ROOT/data/run"
STATUS_JSON="$RUN_DIR/hourly_watchdog_status.json"
STATUS_MD="$RUN_DIR/hourly_watchdog_status.md"
LOG_FILE="${UML_HOURLY_WATCHDOG_LOG:-/tmp/uml-hourly-watchdog.log}"
UID_NUM="$(id -u)"

mkdir -p "$RUN_DIR"
log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') [hourly-watchdog] $*" | tee -a "$LOG_FILE"; }

http_code() {
  curl -s -o /dev/null -w '%{http_code}' --max-time 12 "$1" 2>/dev/null || echo "000"
}

read_url() {
  local f="$1"
  [ -f "$f" ] && tr -d '[:space:]' <"$f" || true
}

agent_state() {
  if launchctl print "gui/${UID_NUM}/$1" >/dev/null 2>&1; then echo loaded; else echo missing; fi
}

log "=== start ==="
RECOVERED=""

LOCAL_HEALTH="$(http_code 'http://127.0.0.1:8000/api/settings/health')"
LOCAL_UI="$(http_code 'http://127.0.0.1:8501/')"
CAFFEINATE=0
pgrep -x caffeinate >/dev/null 2>&1 && CAFFEINATE=1 || true

if [ "$LOCAL_HEALTH" != "200" ]; then
  log "WARN: local API unhealthy ($LOCAL_HEALTH) — kickstarting api"
  launchctl kickstart -k "gui/${UID_NUM}/com.uml.pipeline.api" 2>/dev/null || true
  sleep 8
  LOCAL_HEALTH="$(http_code 'http://127.0.0.1:8000/api/settings/health')"
  RECOVERED="${RECOVERED}api,"
fi
if [ "$LOCAL_UI" != "200" ]; then
  log "WARN: local UI unhealthy ($LOCAL_UI) — kickstarting ui"
  launchctl kickstart -k "gui/${UID_NUM}/com.uml.pipeline.ui" 2>/dev/null || true
  sleep 8
  LOCAL_UI="$(http_code 'http://127.0.0.1:8501/')"
  RECOVERED="${RECOVERED}ui,"
fi
if [ "$CAFFEINATE" -ne 1 ]; then
  log "WARN: caffeinate missing — kickstarting"
  launchctl kickstart -k "gui/${UID_NUM}/com.uml.pipeline.caffeinate" 2>/dev/null || true
  RECOVERED="${RECOVERED}caffeinate,"
fi

TUNNEL_RC=0
bash "$ROOT/scripts/monitor_public_tunnels.sh" --once --quiet >>"$LOG_FILE" 2>&1 || TUNNEL_RC=$?

GIT_URL_RC=0
bash "$ROOT/scripts/git_push_live_urls.sh" >>/tmp/uml-git-live-urls.log 2>&1 || GIT_URL_RC=$?
GIT_URL_STATUS="$(tr '\n' ' ' <"$RUN_DIR/github_url_push.status" 2>/dev/null || echo unknown)"

GIT_AUTO_MSG="skipped"
# Default skip: git-sync LaunchAgent already commits safe drift hourly.
# Set UML_HOURLY_SKIP_GIT_AUTO=0 to also run pytest-gated auto-push here.
if [ "${UML_HOURLY_SKIP_GIT_AUTO:-1}" = "0" ]; then
  if bash "$ROOT/scripts/git_auto_push.sh" >>"$LOG_FILE" 2>&1; then
    GIT_AUTO_MSG="ok"
  else
    GIT_AUTO_MSG="rc_$?"
  fi
fi

UI="$(read_url "$RUN_DIR/public_ui_url.txt")"
API="$(read_url "$RUN_DIR/public_api_url.txt")"
PUBLIC_UI="000"
PUBLIC_API_DOCS="000"
PUBLIC_API_HEALTH="000"
[ -n "$UI" ] && PUBLIC_UI="$(http_code "${UI}/")"
[ -n "$API" ] && PUBLIC_API_DOCS="$(http_code "${API}/docs")"
[ -n "$API" ] && PUBLIC_API_HEALTH="$(http_code "${API}/api/settings/health")"

export HW_UI="$UI" HW_API="$API" HW_PUBLIC_UI="$PUBLIC_UI" HW_PUBLIC_DOCS="$PUBLIC_API_DOCS" \
  HW_PUBLIC_HEALTH="$PUBLIC_API_HEALTH" HW_LOCAL_HEALTH="$LOCAL_HEALTH" HW_LOCAL_UI="$LOCAL_UI" \
  HW_TUNNEL_RC="$TUNNEL_RC" HW_GIT_URL_RC="$GIT_URL_RC" HW_GIT_URL_STATUS="$GIT_URL_STATUS" \
  HW_GIT_AUTO="$GIT_AUTO_MSG" HW_RECOVERED="$RECOVERED" \
  HW_STATUS_JSON="$STATUS_JSON" HW_STATUS_MD="$STATUS_MD" \
  HW_AGENT_API="$(agent_state com.uml.pipeline.api)" \
  HW_AGENT_UI="$(agent_state com.uml.pipeline.ui)" \
  HW_AGENT_TUNNELS="$(agent_state com.uml.pipeline.tunnels)" \
  HW_AGENT_TM="$(agent_state com.uml.pipeline.tunnel-monitor)" \
  HW_AGENT_GS="$(agent_state com.uml.pipeline.git-sync)" \
  HW_AGENT_HW="$(agent_state com.uml.pipeline.hourly-watchdog)" \
  HW_AGENT_CAFFE="$(agent_state com.uml.pipeline.caffeinate)"

OVERALL="$("$ROOT/.venv/bin/python" - <<'PY'
import json, os, urllib.request
from datetime import datetime, timezone
from pathlib import Path

def http_json(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.load(r)
    except Exception:
        return {}

ui = os.environ.get("HW_UI", "")
api = os.environ.get("HW_API", "")
local_health = os.environ.get("HW_LOCAL_HEALTH", "000")
local_ui = os.environ.get("HW_LOCAL_UI", "000")
pub_ui = os.environ.get("HW_PUBLIC_UI", "000")
pub_docs = os.environ.get("HW_PUBLIC_DOCS", "000")
pub_health = os.environ.get("HW_PUBLIC_HEALTH", "000")
git_rc = int(os.environ.get("HW_GIT_URL_RC") or 0)
tunnel_rc = int(os.environ.get("HW_TUNNEL_RC") or 0)

h = http_json("http://127.0.0.1:8000/api/settings/health") if local_health == "200" else {}
cf_ui = bool(__import__("subprocess").call(["pgrep", "-f", "cloudflared tunnel --protocol http2 --url http://127.0.0.1:8501"], stdout=__import__("subprocess").DEVNULL, stderr=__import__("subprocess").DEVNULL) == 0)
cf_api = bool(__import__("subprocess").call(["pgrep", "-f", "cloudflared tunnel --protocol http2 --url http://127.0.0.1:8000"], stdout=__import__("subprocess").DEVNULL, stderr=__import__("subprocess").DEVNULL) == 0)
caff = bool(__import__("subprocess").call(["pgrep", "-x", "caffeinate"], stdout=__import__("subprocess").DEVNULL, stderr=__import__("subprocess").DEVNULL) == 0)

overall = "ok"
if local_health != "200" or local_ui != "200" or pub_ui != "200" or pub_docs != "200" or git_rc != 0:
    overall = "degraded"

recovered = [x for x in (os.environ.get("HW_RECOVERED") or "").split(",") if x]
status = {
    "checked_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "overall": overall,
    "local": {
        "api_health": local_health,
        "ui": local_ui,
        "adapter": h.get("finetuned_adapter_path"),
        "adapter_present": h.get("finetuned_adapter_present"),
        "provider": h.get("provider"),
    },
    "public": {
        "ui_url": ui,
        "api_url": api,
        "api_docs_url": f"{api.rstrip('/')}/docs" if api else "",
        "ui_http": pub_ui,
        "api_docs_http": pub_docs,
        "api_health_http": pub_health,
    },
    "processes": {"cloudflared_ui": cf_ui, "cloudflared_api": cf_api, "caffeinate": caff},
    "launch_agents": {
        "api": os.environ.get("HW_AGENT_API"),
        "ui": os.environ.get("HW_AGENT_UI"),
        "tunnels": os.environ.get("HW_AGENT_TUNNELS"),
        "tunnel_monitor": os.environ.get("HW_AGENT_TM"),
        "git_sync": os.environ.get("HW_AGENT_GS"),
        "hourly_watchdog": os.environ.get("HW_AGENT_HW"),
        "caffeinate": os.environ.get("HW_AGENT_CAFFE"),
    },
    "actions": {
        "tunnel_monitor_rc": tunnel_rc,
        "git_push_live_urls_rc": git_rc,
        "git_url_status": os.environ.get("HW_GIT_URL_STATUS", ""),
        "git_auto_push": os.environ.get("HW_GIT_AUTO", ""),
        "recovered": recovered,
    },
    "github_link_md": "https://github.com/dipak5501/uml-generation-pipeline/blob/main/Link.md",
}
Path(os.environ["HW_STATUS_JSON"]).write_text(json.dumps(status, indent=2) + "\n")
docs = status["public"]["api_docs_url"]
md = f"""# Hourly lock-screen watchdog

**Checked (UTC):** {status['checked_at_utc']}
**Overall:** `{overall}`

## Public links
- UI: {ui} (HTTP {pub_ui})
- API docs: {docs} (HTTP {pub_docs})
- GitHub Link.md: {status['github_link_md']}

## Live adapter
- path: `{status['local']['adapter']}`
- present: {status['local']['adapter_present']}
- provider: `{status['local']['provider']}`

## Local / GitHub
- API health HTTP: {local_health} · UI HTTP: {local_ui}
- live URL push: `{status['actions']['git_url_status']}` (rc={git_rc})
- auto-push: `{status['actions']['git_auto_push']}`
- tunnel monitor rc: {tunnel_rc}

Keep this macOS user **logged in** (lock OK). Do **not** Log Out.
"""
Path(os.environ["HW_STATUS_MD"]).write_text(md)
print(overall)
PY
)"

log "overall=$OVERALL ui=$UI api_docs=${API%/}/docs git=$GIT_URL_STATUS"
log "=== done (status: $STATUS_MD) ==="
[ "$OVERALL" = "ok" ]
