#!/usr/bin/env bash
# Promote a completed LoRA adapter to live (updates .env + restarts API).
# Usage: bash scripts/switch_live_adapter.sh models/uml-plantuml-lora-all
# Does nothing unless adapters.safetensors exists.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  echo "Usage: $0 <adapter-dir-relative-to-repo>" >&2
  echo "Example: $0 models/uml-plantuml-lora-all" >&2
  exit 2
fi
# Normalize to relative path from ROOT
TARGET="${TARGET#"$ROOT/"}"
ADAPTER_FILE="$ROOT/$TARGET/adapters.safetensors"
if [[ ! -f "$ADAPTER_FILE" ]]; then
  echo "Missing $ADAPTER_FILE — refuse to switch" >&2
  exit 1
fi
ENV_FILE="$ROOT/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing .env" >&2
  exit 1
fi
prev="$(grep '^FINETUNED_ADAPTER_PATH=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
if grep -q '^FINETUNED_ADAPTER_PATH=' "$ENV_FILE"; then
  sed -i '' "s|^FINETUNED_ADAPTER_PATH=.*|FINETUNED_ADAPTER_PATH=$TARGET|" "$ENV_FILE"
else
  echo "FINETUNED_ADAPTER_PATH=$TARGET" >>"$ENV_FILE"
fi
echo "Switched FINETUNED_ADAPTER_PATH: ${prev:-unset} → $TARGET"
if [[ -x "$ROOT/scripts/restart_api.sh" ]]; then
  bash "$ROOT/scripts/restart_api.sh"
else
  echo "Update applied; restart API manually (scripts/restart_api.sh missing)." >&2
fi
