#!/usr/bin/env python3
"""Rescore successful renders via the live API (real Ollama + Aya, not mock).

Default: every successful render (full library).
--unscored-only: only success rows whose composite_score is missing/0, or
whose stored VLM text looks like mock scores. Does not wipe the DB.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
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


def _token() -> str:
    env_tok = (os.environ.get("API_ACCESS_TOKEN") or "").strip()
    if env_tok:
        return env_tok
    out = subprocess.check_output(
        ["bash", str(ROOT / "scripts" / "read_env_key.sh"), "API_ACCESS_TOKEN", str(ROOT / ".env")],
        text=True,
    ).strip()
    if out:
        os.environ["API_ACCESS_TOKEN"] = out
    return out


def _headers() -> dict[str, str]:
    h: dict[str, str] = {}
    tok = _token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
        h["X-API-Key"] = tok
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


def _db_unscored_ids() -> list[int]:
    """Read-only: success renders with S missing/0 or mock VLM text."""
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from sqlmodel import Session, select

    from app.db import get_engine
    from app.models import ModelScore, UMLArtifact

    mocks: set[int] = set()
    with Session(get_engine()) as session:
        for row in session.exec(select(ModelScore)).all():
            text = (row.raw_output or row.explanation or "").lower()
            if "mock vlm" in text:
                mocks.add(int(row.artifact_id))
        out: list[int] = []
        for a in session.exec(
            select(UMLArtifact).where(UMLArtifact.render_status == "success")
        ).all():
            if a.id is None:
                continue
            if a.id in mocks or not (a.composite_score and a.composite_score > 0):
                out.append(int(a.id))
    return out


def _collect_ids(*, unscored_only: bool) -> list[int]:
    ids: list[int] = []
    offset = 0
    while True:
        d = api("GET", f"/api/artifacts/library?render_status=success&limit=100&offset={offset}")
        items = d.get("items") or []
        if not items:
            break
        for it in items:
            if it.get("render_status") != "success":
                continue
            aid = int(it["id"])
            if not unscored_only:
                ids.append(aid)
                continue
            score = it.get("composite_score")
            if score is None or float(score) <= 0:
                ids.append(aid)
        offset += len(items)
        if offset >= int(d.get("total") or 0):
            break
    if unscored_only:
        ids = sorted(set(ids) | set(_db_unscored_ids()))
    else:
        ids.sort()
    return ids


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--unscored-only",
        action="store_true",
        help="Only POST /rescore for success renders lacking a real composite_score",
    )
    args = ap.parse_args()

    if not _token():
        raise SystemExit(
            "API_ACCESS_TOKEN missing in .env — required for POST /rescore on this server"
        )
    health = api("GET", "/api/settings/health")
    print(
        f"api mock={health.get('mock_providers')} provider={health.get('provider_summary')} "
        f"adapter={health.get('finetuned_adapter_path')}",
        flush=True,
    )
    if health.get("mock_providers"):
        raise SystemExit("API is still in MOCK mode — refuse to score")

    ids = _collect_ids(unscored_only=args.unscored_only)
    print(
        f"to_rescore={len(ids)} unscored_only={args.unscored_only}",
        flush=True,
    )
    if not ids:
        print("DONE ok=0 fail=0 (nothing pending)", flush=True)
        return
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
