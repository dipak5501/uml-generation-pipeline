#!/usr/bin/env bash
# Reliable sequential download of CohereLabs/aya-vision-8b (~17GB).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -f .env ]; then set -a; # shellcheck disable=SC1091
. ./.env; set +a; fi
: "${HF_TOKEN:?HF_TOKEN missing in .env}"

OUT="$ROOT/data/aya_weights"
LOG="$ROOT/data/aya_download.log"
mkdir -p "$OUT"
exec > >(tee -a "$LOG") 2>&1

echo "==== $(date) starting Aya download into $OUT ===="
FILES=(
  model-00001-of-00004.safetensors
  model-00002-of-00004.safetensors
  model-00003-of-00004.safetensors
  model-00004-of-00004.safetensors
  model.safetensors.index.json
  config.json
  generation_config.json
  preprocessor_config.json
  processor_config.json
  tokenizer.json
  tokenizer_config.json
  special_tokens_map.json
  chat_template.json
)

for f in "${FILES[@]}"; do
  echo "[$(date +%H:%M:%S)] downloading $f"
  if curl -L --fail --retry 8 --retry-all-errors --retry-delay 5 -C - \
      -H "Authorization: Bearer ${HF_TOKEN}" \
      -o "$OUT/$f" \
      "https://huggingface.co/CohereLabs/aya-vision-8b/resolve/main/$f"; then
    sz=$(stat -f%z "$OUT/$f" 2>/dev/null || echo 0)
    echo "[$(date +%H:%M:%S)] OK $f ($sz bytes)"
  else
    echo "[$(date +%H:%M:%S)] skip/fail $f (may be optional)"
    rm -f "$OUT/$f"
  fi
done

# Link into HF cache layout so transformers finds it, OR set TRANSFORMERS offline path
echo "Linking into Hugging Face cache…"
"$ROOT/.venv/bin/python" - <<'PY'
import os, json, shutil
from pathlib import Path
from huggingface_hub import snapshot_download, hf_hub_download

# Prefer letting huggingface_hub finalize from local files via snapshot if possible.
# Fallback: ensure transformers can load via local_files_only from OUT by writing a marker.
out = Path("data/aya_weights")
needed = [
    "model-00001-of-00004.safetensors",
    "model-00002-of-00004.safetensors",
    "model-00003-of-00004.safetensors",
    "model-00004-of-00004.safetensors",
    "config.json",
]
missing = [f for f in needed if not (out / f).is_file() or (out / f).stat().st_size < 1000]
if missing:
    raise SystemExit(f"Incomplete download, missing/small: {missing}")

# Copy/symlink into HF hub cache using huggingface_hub by re-downloading with local hits —
# simplest reliable path: set AYA local dir and point provider at it.
print("WEIGHTS_READY", out.resolve())
for f in needed:
    print(f, (out / f).stat().st_size)
PY

# Point app at local folder
"$ROOT/.venv/bin/python" - <<'PY'
from pathlib import Path
import re
p = Path(".env")
text = p.read_text()
updates = {
    "VLM_AYA_BACKEND": "local",
    "AYA_VLM_MODEL": str(Path("data/aya_weights").resolve()),
    "VLM_FAST_MODE": "false",
}
for k, v in updates.items():
    if re.search(rf"^{k}=", text, flags=re.M):
        text = re.sub(rf"^{k}=.*$", f"{k}={v}", text, flags=re.M)
    else:
        text += f"\n{k}={v}\n"
p.write_text(text)
print("Updated .env AYA_VLM_MODEL -> data/aya_weights")
PY

echo "DOWNLOAD_DONE $(date)"
echo "Next: ./scripts/run_local.sh"
