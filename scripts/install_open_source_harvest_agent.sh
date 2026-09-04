#!/usr/bin/env bash
# Install low-priority StartInterval LaunchAgent: re-harvest public UML every few hours.
# Does not kill industrial LoRA; does not change live API adapter.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCHD_DIR="$ROOT/scripts/launchd"
USER_HOME="${HOME}"
UID_NUM="$(id -u)"
USER_NAME="$(id -un)"
AGENT_DIR="$USER_HOME/Library/LaunchAgents"
LABEL="com.uml.pipeline.open-source-uml-harvest"
PROGRAM="$LAUNCHD_DIR/run_open_source_uml_harvest.sh"
PATH_VAL="$ROOT/.venv/bin:$USER_HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
STDOUT="$ROOT/data/training/open_source_uml_harvest.launchd.out"
STDERR="$ROOT/data/training/open_source_uml_harvest.launchd.err"
# Every 4 hours
INTERVAL="${HARVEST_INTERVAL_SECS:-14400}"

chmod +x "$PROGRAM"
mkdir -p "$AGENT_DIR" "$ROOT/data/training" "$ROOT/data/run/launchd_plists"

DEST="$ROOT/data/run/launchd_plists/${LABEL}.plist"
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
  <false/>
  <key>StartInterval</key>
  <integer>${INTERVAL}</integer>
  <key>ProcessType</key>
  <string>Background</string>
  <key>Nice</key>
  <integer>15</integer>
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
    <key>HARVEST_LOG</key>
    <string>data/training/open_source_uml_harvest.log</string>
  </dict>
  <key>ThrottleInterval</key>
  <integer>60</integer>
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
echo "Loaded ${LABEL} (StartInterval=${INTERVAL}s ≈ every $((INTERVAL / 3600))h)"
echo "Log: $ROOT/data/training/open_source_uml_harvest.log"
echo "Does not stop industrial training; live adapter unchanged."
