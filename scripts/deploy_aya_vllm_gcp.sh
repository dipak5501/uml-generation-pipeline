#!/usr/bin/env bash
# Deploy paper-exact Aya-Vision-8B on a GCP GPU VM with vLLM, then wire .env.
#
# Prerequisites (one-time on this Mac):
#   export CLOUDSDK_PYTHON="$PWD/.mamba/envs/gcloudpy/bin/python"
#   export PATH="/tmp/google-cloud-sdk/bin:$PATH"   # or install gcloud permanently
#   gcloud auth login
#   gcloud config set project YOUR_PROJECT_ID
#   gcloud auth application-default login
#
# Usage:
#   bash scripts/deploy_aya_vllm_gcp.sh
#   bash scripts/deploy_aya_vllm_gcp.sh --zone us-central1-a --machine g2-standard-8
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GCLOUD_BIN="${GCLOUD_BIN:-gcloud}"
if ! command -v "$GCLOUD_BIN" >/dev/null 2>&1; then
  if [ -x /tmp/google-cloud-sdk/bin/gcloud ]; then
    export PATH="/tmp/google-cloud-sdk/bin:$PATH"
  fi
fi
export CLOUDSDK_PYTHON="${CLOUDSDK_PYTHON:-$ROOT/.mamba/envs/gcloudpy/bin/python}"

ZONE="${ZONE:-us-central1-a}"
MACHINE="${MACHINE:-g2-standard-8}"   # 1x L4 24GB — enough for Aya-Vision-8B
VM_NAME="${VM_NAME:-uml-aya-vllm}"
BOOT_DISK_GB="${BOOT_DISK_GB:-200}"
HF_MODEL="${HF_MODEL:-CohereLabs/aya-vision-8b}"
VLLM_PORT="${VLLM_PORT:-8000}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --zone) ZONE="$2"; shift 2 ;;
    --machine) MACHINE="$2"; shift 2 ;;
    --name) VM_NAME="$2"; shift 2 ;;
    --project) PROJECT="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

PROJECT="${PROJECT:-$($GCLOUD_BIN config get-value project 2>/dev/null || true)}"
if [ -z "$PROJECT" ] || [ "$PROJECT" = "(unset)" ]; then
  echo "ERROR: No GCP project set. Run:" >&2
  echo "  gcloud auth login" >&2
  echo "  gcloud config set project YOUR_PROJECT_ID" >&2
  exit 1
fi

ACCOUNT="$($GCLOUD_BIN auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -1 || true)"
if [ -z "$ACCOUNT" ]; then
  echo "ERROR: Not logged in. Run: gcloud auth login" >&2
  exit 1
fi

echo "Project=$PROJECT account=$ACCOUNT zone=$ZONE machine=$MACHINE vm=$VM_NAME"

# Enable required APIs
$GCLOUD_BIN services enable compute.googleapis.com --project "$PROJECT" >/dev/null

# Firewall for vLLM (tag: uml-aya)
if ! $GCLOUD_BIN compute firewall-rules describe allow-uml-aya-vllm --project "$PROJECT" >/dev/null 2>&1; then
  $GCLOUD_BIN compute firewall-rules create allow-uml-aya-vllm \
    --project "$PROJECT" \
    --allow=tcp:${VLLM_PORT} \
    --target-tags=uml-aya \
    --description="UML-Pipeline Aya-Vision vLLM" \
    --direction=INGRESS \
    --priority=1000
fi

STARTUP_SCRIPT=$(cat <<'EOS'
#!/bin/bash
set -euxo pipefail
apt-get update
apt-get install -y python3-pip git
# NVIDIA drivers usually preinstalled on GPU images; ensure nvidia-smi works
nvidia-smi || true
pip3 install -U "vllm" huggingface_hub
# Optional: HF token from metadata if provided
if curl -sf -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/hf-token \
  -o /tmp/hf_token; then
  export HF_TOKEN="$(cat /tmp/hf_token)"
  export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"
fi
MODEL="${MODEL:-CohereLabs/aya-vision-8b}"
# Serve OpenAI-compatible API
nohup python3 -m vllm.entrypoints.openai.api_server \
  --model "$MODEL" \
  --host 0.0.0.0 \
  --port 8000 \
  --max-model-len 4096 \
  --trust-remote-code \
  --limit-mm-per-prompt image=1 \
  > /var/log/aya-vllm.log 2>&1 &
EOS
)

# Create VM if missing
if ! $GCLOUD_BIN compute instances describe "$VM_NAME" --zone "$ZONE" --project "$PROJECT" >/dev/null 2>&1; then
  echo "Creating GPU VM (this incurs GCP cost)…"
  HF_TOKEN_VAL=""
  if [ -f "$ROOT/.env" ]; then
    HF_TOKEN_VAL="$(grep -E '^HF_TOKEN=' "$ROOT/.env" | head -1 | cut -d= -f2- || true)"
  fi
  META=( "startup-script=$STARTUP_SCRIPT" "MODEL=$HF_MODEL" )
  if [ -n "$HF_TOKEN_VAL" ]; then
    META+=( "hf-token=$HF_TOKEN_VAL" )
  fi
  # Join metadata for gcloud
  META_ARGS=()
  for m in "${META[@]}"; do
    META_ARGS+=( --metadata="${m}" )
  done
  $GCLOUD_BIN compute instances create "$VM_NAME" \
    --project "$PROJECT" \
    --zone "$ZONE" \
    --machine-type "$MACHINE" \
    --accelerator=type=nvidia-l4,count=1 \
    --maintenance-policy=TERMINATE \
    --boot-disk-size="${BOOT_DISK_GB}GB" \
    --boot-disk-type=pd-balanced \
    --image-family=pytorch-latest-gpu \
    --image-project=deeplearning-platform-release \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --tags=uml-aya \
    "${META_ARGS[@]}"
else
  echo "VM $VM_NAME already exists — ensuring it is running"
  $GCLOUD_BIN compute instances start "$VM_NAME" --zone "$ZONE" --project "$PROJECT" || true
fi

IP="$($GCLOUD_BIN compute instances describe "$VM_NAME" --zone "$ZONE" --project "$PROJECT" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')"
echo "VM external IP: $IP"
BASE="http://${IP}:${VLLM_PORT}/v1"

echo "Waiting for vLLM to become ready (first boot downloads the model; can take 10–30+ min)…"
for i in $(seq 1 90); do
  if curl -sf "${BASE}/models" >/dev/null 2>&1; then
    echo "vLLM is up: $BASE"
    break
  fi
  echo "  …still starting ($i/90)"
  sleep 20
  if [ "$i" -eq 90 ]; then
    echo "WARNING: vLLM not ready yet. Check logs:" >&2
    echo "  gcloud compute ssh $VM_NAME --zone $ZONE --command 'sudo tail -n 100 /var/log/aya-vllm.log'" >&2
  fi
done

# Wire local .env
ENV_FILE="$ROOT/.env"
touch "$ENV_FILE"
python3 - <<PY
from pathlib import Path
p = Path("$ENV_FILE")
text = p.read_text() if p.exists() else ""
updates = {
    "VLM_AYA_BACKEND": "openai_compat",
    "AYA_VLM_MODEL": "$HF_MODEL",
    "AYA_VLM_BASE_URL": "$BASE",
    "VLM_FAST_MODE": "false",
    "VLM_MODELS": "qwen2.5vl:3b,llama3.2-vision:11b,aya-vision:8b",
    "USE_OLLAMA": "true",
    "MOCK_PROVIDERS": "false",
}
lines = text.splitlines()
keys = set(updates)
out = []
seen = set()
for line in lines:
    if "=" in line and not line.strip().startswith("#"):
        k = line.split("=", 1)[0].strip()
        if k in updates:
            out.append(f"{k}={updates[k]}")
            seen.add(k)
            continue
    out.append(line)
for k, v in updates.items():
    if k not in seen:
        out.append(f"{k}={v}")
p.write_text("\n".join(out).rstrip() + "\n")
print("Updated .env with Aya endpoint", "$BASE")
PY

echo
echo "NEXT:"
echo "  1) ./scripts/run_local.sh"
echo "  2) Generate a diagram — scores should include real Aya-Vision-8B"
echo "  3) When done (to stop GCP charges):"
echo "       gcloud compute instances stop $VM_NAME --zone $ZONE --project $PROJECT"
echo "     or delete:"
echo "       gcloud compute instances delete $VM_NAME --zone $ZONE --project $PROJECT"
