#!/usr/bin/env python3
"""Enqueue remaining new-eval UML generations through the live API (skip_vlm).

Uses data/eval/scenarios_1000.jsonl + code_langs_1000.jsonl (not sample_data).
Does not wipe the live DB. Reads API_ACCESS_TOKEN via read_env_key (never prints it).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
TYPES = ["class", "object", "component", "package"]
SCENARIOS = ROOT / "data" / "eval" / "scenarios_1000.jsonl"
CODES = ROOT / "data" / "eval" / "code_langs_1000.jsonl"
STATE = ROOT / "data" / "run" / "batch_new_eval_200_api_state.json"
ID_LIST = ROOT / "data" / "run" / "batch_new_eval_200_ids.json"


def _token() -> str:
    out = subprocess.check_output(
        ["bash", str(ROOT / "scripts" / "read_env_key.sh"), "API_ACCESS_TOKEN", str(ROOT / ".env")],
        text=True,
    ).strip()
    if not out:
        raise SystemExit("API_ACCESS_TOKEN missing in .env")
    return out


def _load_balanced(path: Path, per_type: int, offset: int) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    skipped = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            dtype = (row.get("diagram_type") or "").strip()
            if dtype not in TYPES:
                continue
            text = (row.get("source_requirement") or "").strip()
            if len(text) < 3:
                continue
            if skipped < offset:
                skipped += 1
                continue
            if len(buckets[dtype]) >= per_type:
                if all(len(buckets[t]) >= per_type for t in TYPES):
                    break
                continue
            buckets[dtype].append(row)
    out: list[dict] = []
    for t in TYPES:
        if len(buckets[t]) < per_type:
            raise SystemExit(f"{path.name}: need {per_type} × {t}, got {len(buckets[t])}")
        out.extend(buckets[t][:per_type])
    return out


def _wait_job(client: httpx.Client, job_id: int, timeout_s: float = 180.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        r = client.get(f"/api/jobs/{job_id}")
        r.raise_for_status()
        job = r.json()
        if job.get("status") in ("completed", "failed"):
            return job
        time.sleep(1.5)
    return {"id": job_id, "status": "timeout", "error": f"waited {timeout_s}s"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-type", type=int, default=25)
    ap.add_argument("--offset", type=int, default=50)
    ap.add_argument("--skip-first", type=int, default=0, help="Skip first N planned items")
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--timeout", type=float, default=180.0)
    args = ap.parse_args()

    scenarios = _load_balanced(SCENARIOS, args.per_type, args.offset)
    codes = _load_balanced(CODES, args.per_type, args.offset)
    jobs = (
        [("requirement", r) for r in scenarios]
        + [("source_code", r) for r in codes]
    )
    jobs = jobs[args.skip_first :]
    print(f"API batch remaining={len(jobs)} (skipped_first={args.skip_first})", flush=True)

    token = _token()
    headers = {"Authorization": f"Bearer {token}"}
    results: list[dict] = []
    ids: list[int] = []

    with httpx.Client(base_url=args.base, headers=headers, timeout=60.0) as client:
        health = client.get("/api/settings/health")
        health.raise_for_status()
        h = health.json()
        print(
            f"health provider={h.get('provider')} mock={h.get('mock_providers')}",
            flush=True,
        )
        if h.get("mock_providers"):
            raise SystemExit("API is in mock mode")

        for i, (mode, row) in enumerate(jobs, 1):
            payload = {
                "requirement": row["source_requirement"],
                "diagram_type": row["diagram_type"],
                "input_mode": mode,
                "skip_vlm": True,
                "async_mode": True,
            }
            try:
                r = client.post("/api/generate", json=payload)
                r.raise_for_status()
                body = r.json()
                job_id = body.get("job_id") or (body.get("job") or {}).get("id")
                job = _wait_job(client, int(job_id), args.timeout)
                art = None
                if job.get("status") == "completed":
                    # fetch newest matching artifact via job artifacts if available
                    arts = client.get("/api/artifacts", params={"limit": 1, "job_id": job_id})
                    if arts.status_code == 200 and arts.json():
                        art = arts.json()[0]
                    elif body.get("artifact"):
                        art = body["artifact"]
                aid = (art or {}).get("id")
                if aid:
                    ids.append(int(aid))
                rec = {
                    "i": i,
                    "src": row.get("id"),
                    "type": row["diagram_type"],
                    "mode": mode,
                    "job_id": job_id,
                    "job_status": job.get("status"),
                    "artifact_id": aid,
                    "render": (art or {}).get("render_status"),
                    "error": job.get("error"),
                }
                results.append(rec)
                print(
                    f"[{i}/{len(jobs)}] job={job_id} status={job.get('status')} "
                    f"id={aid} type={row['diagram_type']} mode={mode} "
                    f"render={(art or {}).get('render_status')}",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "i": i,
                        "src": row.get("id"),
                        "type": row["diagram_type"],
                        "mode": mode,
                        "error": f"{type(exc).__name__}:{exc}",
                    }
                )
                print(f"[{i}/{len(jobs)}] FAIL {type(exc).__name__}:{exc}", flush=True)

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"results": results, "ids": ids}, indent=2), encoding="utf-8")
    # merge with any prior ids file
    prior: list[int] = []
    if ID_LIST.is_file():
        try:
            prior = list(json.loads(ID_LIST.read_text(encoding="utf-8")).get("ids") or [])
        except Exception:  # noqa: BLE001
            prior = []
    merged = prior + [i for i in ids if i not in prior]
    ID_LIST.write_text(
        json.dumps(
            {
                "ids": merged,
                "via": "api",
                "skip_first": args.skip_first,
                "offset": args.offset,
                "per_type": args.per_type,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    ok = sum(1 for r in results if r.get("job_status") == "completed")
    print(f"DONE submitted={len(results)} completed={ok} ids={len(merged)} -> {ID_LIST}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
