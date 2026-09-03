#!/usr/bin/env bash
# Install KeepAlive LaunchAgent for industrial-complete LoRA training only.
# Does not restart API/UI and does not change .env / live adapter.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCHD_DIR="$ROOT/scripts/launchd"
USER_HOME="${HOME}"
UID_NUM="$(id -u)"
USER_NAME="$(id -un)"
AGENT_DIR="$USER_HOME/Library/LaunchAgents"
LABEL="com.uml.pipeline.finetune-industrial"
PROGRAM="$LAUNCHD_DIR/run_finetune_industrial.sh"
PATH_VAL="$ROOT/.venv/bin:$USER_HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
STDOUT="$ROOT/data/training/finetune_industrial_complete.launchd.out"
STDERR="$ROOT/data/training/finetune_industrial_complete.launchd.err"

chmod +x "$PROGRAM" "$ROOT/scripts/run_finetune_resilient.sh"
mkdir -p "$AGENT_DIR" "$ROOT/data/training" "$ROOT/data/run/launchd_plists"

DEST="$ROOT/data/run/launchd_plists/${LABEL}.plist"
# SuccessfulExit=false: stay down when training completes (exit 0); restart on crash.
cat >"$DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${PROGRAM}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>
  <key>ProcessType</key>
  <string>Interactive</string>
  <key>StandardOutPath</key>
  <string>${STDOUT}</string>
  <key>StandardErrorPath</key>
  <string>${STDERR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>${PATH_VAL}</string>
    <key>HOME</key>
    <string>${USER_HOME}</string>
    <key>USER</key>
    <string>${USER_NAME}</string>
    <key>BATCH_SIZE</key>
    <string>8</string>
    <key>ITERS</key>
    <string>8000</string>
    <key>MAX_SEQ</key>
    <string>2048</string>
    <key>SAVE_EVERY</key>
    <string>100</string>
    <key>STEPS_EVAL</key>
    <string>100</string>
    <key>ADAPTER_PATH</key>
    <string>models/uml-plantuml-lora-industrial-complete</string>
    <key>DATA</key>
    <string>data/finetune_industrial</string>
    <key>LOG</key>
    <string>data/training/finetune_industrial_complete.log</string>
  </dict>
  <key>ThrottleInterval</key>
  <integer>20</integer>
</dict>
</plist>
EOF

launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
rm -f "${AGENT_DIR}/${LABEL}.plist"
cp "$DEST" "$AGENT_DIR/"
launchctl bootstrap "gui/${UID_NUM}" "$AGENT_DIR/${LABEL}.plist" 2>/dev/null \
  || launchctl load -w "$AGENT_DIR/${LABEL}.plist" 2>/dev/null \
  || true
launchctl enable "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
launchctl kickstart -k "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
echo "Loaded ${LABEL}"
echo "Log: $ROOT/data/training/finetune_industrial_complete.log"
echo "Adapter dest: $ROOT/models/uml-plantuml-lora-industrial-complete"
echo "Live API adapter is unchanged."
