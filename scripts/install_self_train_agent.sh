#!/usr/bin/env bash
# Install interval LaunchAgent for self-adaptation data harvest + idle LoRA self-training.
# Cooperates with com.uml.pipeline.finetune-industrial (yields GPU). Does not touch live .env adapter.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCHD_DIR="$ROOT/scripts/launchd"
USER_HOME="${HOME}"
UID_NUM="$(id -u)"
USER_NAME="$(id -un)"
AGENT_DIR="$USER_HOME/Library/LaunchAgents"
LABEL="com.uml.pipeline.self-train"
PROGRAM="$LAUNCHD_DIR/run_self_train.sh"
PATH_VAL="$ROOT/.venv/bin:$USER_HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
STDOUT="$ROOT/data/training/self_train.launchd.out"
STDERR="$ROOT/data/training/self_train.launchd.err"
GEN_DIR="$ROOT/data/run/launchd_plists"
DEST="$GEN_DIR/${LABEL}.plist"
INTERVAL="${START_INTERVAL:-900}"

chmod +x "$PROGRAM" "$ROOT/scripts/run_self_training_loop.sh" \
  "$ROOT/scripts/harvest_accepted_for_finetune.py" \
  "$ROOT/scripts/build_adaptation_finetune_mix.py" 2>/dev/null || true
mkdir -p "$AGENT_DIR" "$GEN_DIR" "$ROOT/data/training" "$ROOT/data/run"

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
  <key>StartInterval</key>
  <integer>${INTERVAL}</integer>
  <key>ProcessType</key>
  <string>Background</string>
  <key>Nice</key>
  <integer>10</integer>
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
    <key>ADAPTER_PATH</key>
    <string>models/uml-plantuml-lora-adaptation</string>
    <key>DATA</key>
    <string>data/finetune_adaptation</string>
    <key>LOG</key>
    <string>data/training/self_train.log</string>
    <key>CYCLE_ITERS</key>
    <string>400</string>
    <key>BATCH_SIZE</key>
    <string>4</string>
    <key>MIN_HARVEST</key>
    <string>32</string>
    <key>SLEEP_BUSY</key>
    <string>900</string>
    <key>WARM_START</key>
    <string>models/uml-plantuml-lora-sourcecode-30k</string>
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
# Do not kickstart -k (avoids killing a mid-cycle train); soft start if idle.
launchctl kickstart "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true

echo "Installed ${LABEL} (StartInterval=${INTERVAL}s)"
echo "Harvest+mix always; LoRA only when industrial/API idle."
echo "Log: $ROOT/data/training/self_train.log"
echo "State: $ROOT/data/run/self_train_state.json"
echo "Adapter (not live): $ROOT/models/uml-plantuml-lora-adaptation"
echo "Live API adapter unchanged: models/uml-plantuml-lora-sourcecode-30k"
echo "Industrial agent left alone: com.uml.pipeline.finetune-industrial"
