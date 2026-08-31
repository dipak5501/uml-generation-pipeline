#!/usr/bin/env python3
"""Rescore all successful renders via the live API (real Ollama + Aya, not mock)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)

BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
# Force localhost — Streamlit may have PUBLIC tunnel URLs elsewhere
if "trycloudflare.com" in BASE:
    BASE = "http://127.0.0.1:8000"
TOKEN = (os.environ.get("API_ACCESS_TOKEN") or "").strip()


def _headers() -> dict[str, str]:
    h: dict[str, str] = {}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
        h["X-API-Key"] = TOKEN
    return h


def api(method: str, path: str, data: dict | None = None, timeout: int = 900) -> dict:
    headers = _headers()
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def main() -> None:
    if not TOKEN:
        raise SystemExit(
            "API_ACCESS_TOKEN missing in .env — required for POST /rescore on this server"
        )
    health = api("GET", "/api/settings/health")
    print(
        f"api mock={health.get('mock_providers')} provider={health.get('provider_summary')}",
        flush=True,
    )
    if health.get("mock_providers"):
        raise SystemExit("API is still in MOCK mode — refuse to score")

    ids: list[int] = []
    offset = 0
    while True:
        d = api("GET", f"/api/artifacts/library?limit=100&offset={offset}")
        items = d.get("items") or []
        if not items:
            break
        for it in items:
            if it.get("render_status") == "success":
                ids.append(int(it["id"]))
        offset += len(items)
        if offset >= int(d.get("total") or 0):
            break

    print(f"to_rescore={len(ids)}", flush=True)
    ok = fail = 0
    for i, aid in enumerate(ids, 1):
        t0 = time.time()
        try:
            detail = api("POST", f"/api/artifacts/{aid}/rescore", {})
            scores = detail.get("model_scores") or []
            parts = []
            for s in scores:
                parts.append(f"{s.get('model_key')}={s.get('score')}")
                raw = (s.get("raw_output") or s.get("explanation") or "")[:40]
                if "Mock VLM" in raw:
                    parts.append("MOCK!")
            print(
                f"[{i}/{len(ids)}] id={aid} S={detail.get('composite_score')} "
                f"{','.join(parts)} {time.time() - t0:.0f}s",
                flush=True,
            )
            ok += 1
        except urllib.error.HTTPError as exc:
            fail += 1
            body = exc.read().decode("utf-8", errors="replace")[:200]
            print(f"[{i}/{len(ids)}] id={aid} FAIL HTTP {exc.code} {body}", flush=True)
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"[{i}/{len(ids)}] id={aid} FAIL {exc}", flush=True)
    print(f"DONE ok={ok} fail={fail}", flush=True)


if __name__ == "__main__":
    main()
