#!/usr/bin/env bash
# Download paper-exact Aya-Vision-8B and enable local scoring (Apple Silicon MPS).
# Prerequisite: accept the model license while logged into Hugging Face as the
# same account that owns HF_TOKEN in .env:
#   https://huggingface.co/CohereLabs/aya-vision-8b
# Click "Agree and access repository".
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if [ -z "${HF_TOKEN:-}" ]; then
  echo "ERROR: HF_TOKEN missing in .env" >&2
  exit 1
fi

echo "Opening model page (accept the license if you have not already)…"
open "https://huggingface.co/CohereLabs/aya-vision-8b" 2>/dev/null || true

echo "Waiting for gated access…"
"$ROOT/.venv/bin/python" - <<'PY'
import os, sys, time
from huggingface_hub import hf_hub_download

token = os.environ["HF_TOKEN"]
for i in range(120):  # up to ~10 minutes
    try:
        path = hf_hub_download(
            "CohereLabs/aya-vision-8b",
            "config.json",
            token=token,
        )
        print("Access OK:", path)
        break
    except Exception as exc:
        msg = str(exc).lower()
        if "403" in msg or "gated" in msg or "restricted" in msg or "authorized" in msg:
            print(f"  [{i+1}/120] waiting — accept license in browser…")
            time.sleep(5)
            continue
        print("ERROR:", exc)
        sys.exit(1)
else:
    print("ERROR: still gated. Accept the license, then re-run this script.")
    sys.exit(2)

print("Downloading full Aya-Vision-8B weights (~17GB)…")
from huggingface_hub import snapshot_download
path = snapshot_download("CohereLabs/aya-vision-8b", token=token, resume_download=True)
print("Downloaded to", path)
PY

# Wire .env
"$ROOT/.venv/bin/python" - <<'PY'
from pathlib import Path
import re
p = Path(".env")
text = p.read_text()
updates = {
    "VLM_AYA_BACKEND": "local",
    "AYA_VLM_MODEL": "CohereLabs/aya-vision-8b",
    "VLM_FAST_MODE": "false",
    "VLM_MODELS": "qwen2.5vl:3b,llama3.2-vision:11b,aya-vision:8b",
    "USE_OLLAMA": "true",
    "MOCK_PROVIDERS": "false",
}
for k, v in updates.items():
    if re.search(rf"^{k}=", text, flags=re.M):
        text = re.sub(rf"^{k}=.*$", f"{k}={v}", text, flags=re.M)
    else:
        text = text.rstrip() + f"\n{k}={v}\n"
p.write_text(text)
print("Updated .env for paper VLM ensemble + local Aya")
PY

echo
echo "Smoke-testing Aya local scorer (first load can take several minutes)…"
PYTHONPATH=. "$ROOT/.venv/bin/python" - <<'PY'
from pathlib import Path
from app.settings import get_settings
from app.providers.factory import build_vlm_providers
get_settings.cache_clear()
s = get_settings()
assert s.vlm_aya_backend == "local"
providers = build_vlm_providers(s)
aya = providers["aya_vision_8b"]
img = Path("data/artifacts/4721/diagram.png")
if not img.is_file():
    # any png under artifacts
    imgs = list(Path("data/artifacts").glob("*/diagram.png"))
    img = imgs[0] if imgs else None
if img is None:
    print("No diagram.png found to smoke-test; skip score")
else:
    a = aya.vision_assess(img, "Score this UML diagram 0-6. Reply SCORE: N")
    print("Aya score", a.score, "model", aya.model)
print("OK — restart app: ./scripts/run_local.sh")
PY
