#!/usr/bin/env python3
"""Generate 200 more gallery artifacts from the NEW eval corpora (all 4 UML types).

Sources (not sample_data/requirements.txt):
  - data/eval/scenarios_1000.jsonl  → 100 requirement artifacts
  - data/eval/code_langs_1000.jsonl → 100 source_code artifacts
Balanced: 25 per diagram type per mode (class/object/component/package).

Then optionally rescores those new IDs with live VLMs (--rescore).
Does not wipe data/uml_app.db or data/artifacts/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=True)

from sqlmodel import Session, select

from app.db import get_engine, init_db
from app.models import ModelScore, UMLArtifact
from app.services.orchestration import (
    apply_verification,
    get_or_create_default_project,
    run_single_generation,
    score_image,
)
from app.services.scoring import verify_scores
from app.security import resolve_artifact_image
from app.settings import get_settings

TYPES = ["class", "object", "component", "package"]
SCENARIOS = ROOT / "data" / "eval" / "scenarios_1000.jsonl"
CODES = ROOT / "data" / "eval" / "code_langs_1000.jsonl"
ID_LIST = ROOT / "data" / "run" / "batch_new_eval_200_ids.json"


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
            raise SystemExit(
                f"{path.name}: need {per_type} × {t}, got {len(buckets[t])} "
                f"(try lower --offset)"
            )
        out.extend(buckets[t][:per_type])
    return out


def _has_mock_scores(session: Session, artifact_id: int) -> bool:
    rows = session.exec(
        select(ModelScore).where(ModelScore.artifact_id == artifact_id)
    ).all()
    return any(
        "mock vlm" in ((row.raw_output or row.explanation or "").lower())
        for row in rows
    )


def generate(per_type: int, offset: int, skip_vlm: bool, max_repair: int) -> list[int]:
    scenarios = _load_balanced(SCENARIOS, per_type, offset)
    codes = _load_balanced(CODES, per_type, offset)
    print(
        f"Loaded scenarios={len(scenarios)} codes={len(codes)} "
        f"(per_type={per_type} offset={offset})",
        flush=True,
    )

    get_settings.cache_clear()
    settings = get_settings().model_copy(update={"max_repair_attempts": max_repair})
    print(
        f"provider={settings.provider_summary} mock={settings.mock_providers} "
        f"finetuned={settings.use_finetuned_code} skip_vlm={skip_vlm}",
        flush=True,
    )
    if settings.mock_providers:
        raise SystemExit("Refusing: MOCK_PROVIDERS=true — use live LoRA stack")

    init_db()
    ids: list[int] = []
    ok = 0
    t0 = time.time()
    total = 0
    with Session(get_engine()) as session:
        project = get_or_create_default_project(session)
        jobs = (
            [("requirement", r) for r in scenarios]
            + [("source_code", r) for r in codes]
        )
        for mode, row in jobs:
            dtype = row["diagram_type"]
            text = row["source_requirement"]
            total += 1
            try:
                art = run_single_generation(
                    session,
                    requirement=text,
                    diagram_type=dtype,
                    project_id=project.id,
                    settings=settings,
                    input_mode=mode,
                    skip_vlm=skip_vlm,
                )
                ids.append(int(art.id))
                if art.render_status == "success":
                    ok += 1
                print(
                    f"[{total}/{len(jobs)}] id={art.id} type={dtype} mode={mode} "
                    f"render={art.render_status} S={float(art.composite_score or 0):.2f} "
                    f"src={row.get('id')}",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[{total}/{len(jobs)}] FAIL type={dtype} mode={mode} "
                    f"err={type(exc).__name__}:{exc}",
                    flush=True,
                )

    ID_LIST.parent.mkdir(parents=True, exist_ok=True)
    ID_LIST.write_text(
        json.dumps(
            {
                "ids": ids,
                "per_type": per_type,
                "offset": offset,
                "skip_vlm": skip_vlm,
                "elapsed_s": round(time.time() - t0, 1),
                "render_ok": ok,
                "total": total,
                "scenarios": str(SCENARIOS),
                "codes": str(CODES),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"GENERATE DONE total={total} render_ok={ok} ids_file={ID_LIST} "
        f"elapsed_s={time.time() - t0:.1f}",
        flush=True,
    )
    return ids


def rescore(ids: list[int]) -> dict:
    get_settings.cache_clear()
    settings = get_settings()
    if settings.mock_providers:
        raise SystemExit("Refusing to score: MOCK_PROVIDERS is still true")

    stats = {
        "ok": 0,
        "fail": 0,
        "skip": 0,
        "by_type": {t: {"n": 0, "sum_s": 0.0, "majority": 0, "dataset": 0} for t in TYPES},
        "mean_composite": 0.0,
        "majority_rate": 0.0,
        "dataset_rate": 0.0,
    }
    scored_s: list[float] = []
    majority_n = dataset_n = 0

    for i, aid in enumerate(ids, 1):
        with Session(get_engine()) as session:
            a = session.get(UMLArtifact, aid)
            if not a or a.render_status != "success" or not a.image_path:
                print(f"[{i}/{len(ids)}] id={aid} skip (no render)", flush=True)
                stats["skip"] += 1
                continue
            img = resolve_artifact_image(a.image_path, settings.artifact_dir)
            if img is None:
                print(f"[{i}/{len(ids)}] id={aid} missing image", flush=True)
                stats["fail"] += 1
                continue
            if (
                a.composite_score
                and a.composite_score > 0
                and a.affirmative_votes
                and not _has_mock_scores(session, a.id)
            ):
                print(
                    f"[{i}/{len(ids)}] id={aid} already S={a.composite_score:.2f}",
                    flush=True,
                )
                stats["skip"] += 1
                s = float(a.composite_score)
                scored_s.append(s)
                bt = stats["by_type"].setdefault(
                    a.diagram_type, {"n": 0, "sum_s": 0.0, "majority": 0, "dataset": 0}
                )
                bt["n"] += 1
                bt["sum_s"] += s
                if a.majority_accepted:
                    bt["majority"] += 1
                    majority_n += 1
                if a.dataset_accepted:
                    bt["dataset"] += 1
                    dataset_n += 1
                continue

            t0 = time.time()
            try:
                scores, meta, _ = score_image(img, a.technical_spec, settings)
                verification = verify_scores(
                    scores,
                    settings.vlm_weight_map,
                    render_ok=True,
                    tau=settings.acceptance_tau,
                    min_composite=settings.min_composite_for_dataset,
                )
                apply_verification(
                    a, scores, meta, verification, session, clear_existing=True
                )
                session.add(a)
                session.commit()
                s = float(a.composite_score or 0)
                scored_s.append(s)
                bt = stats["by_type"][a.diagram_type]
                bt["n"] += 1
                bt["sum_s"] += s
                if a.majority_accepted:
                    bt["majority"] += 1
                    majority_n += 1
                if a.dataset_accepted:
                    bt["dataset"] += 1
                    dataset_n += 1
                stats["ok"] += 1
                print(
                    f"[{i}/{len(ids)}] id={aid} type={a.diagram_type} "
                    f"S={s:.2f} A={a.majority_accepted} D={a.dataset_accepted} "
                    f"{time.time() - t0:.0f}s",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001
                stats["fail"] += 1
                print(f"[{i}/{len(ids)}] id={aid} ERROR {exc}", flush=True)

    n = len(scored_s) or 1
    stats["mean_composite"] = sum(scored_s) / n if scored_s else 0.0
    stats["majority_rate"] = majority_n / n if scored_s else 0.0
    stats["dataset_rate"] = dataset_n / n if scored_s else 0.0
    for t, bt in stats["by_type"].items():
        bt["mean_s"] = (bt["sum_s"] / bt["n"]) if bt["n"] else 0.0
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-type", type=int, default=25, help="Per type per mode (25→200)")
    ap.add_argument("--offset", type=int, default=200, help="Skip first N matching rows")
    ap.add_argument("--skip-vlm", action="store_true", default=True)
    ap.add_argument("--with-vlm", action="store_true", help="Score during generate")
    ap.add_argument("--max-repair", type=int, default=1)
    ap.add_argument("--rescore", action="store_true", help="Live-VLM rescore after gen")
    ap.add_argument("--rescore-only", action="store_true", help="Only rescore id list")
    args = ap.parse_args()

    skip_vlm = not args.with_vlm
    if args.rescore_only:
        if not ID_LIST.is_file():
            raise SystemExit(f"Missing {ID_LIST}")
        ids = json.loads(ID_LIST.read_text(encoding="utf-8"))["ids"]
        stats = rescore(ids)
        out = ROOT / "data" / "run" / "batch_new_eval_200_accuracy.json"
        out.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        print(json.dumps(stats, indent=2), flush=True)
        print(f"Wrote {out}", flush=True)
        return 0

    ids = generate(args.per_type, args.offset, skip_vlm, args.max_repair)
    if args.rescore:
        print("=== RESCORE live VLMs ===", flush=True)
        stats = rescore(ids)
        out = ROOT / "data" / "run" / "batch_new_eval_200_accuracy.json"
        out.write_text(json.dumps({"ids": ids, **stats}, indent=2), encoding="utf-8")
        print(json.dumps(stats, indent=2), flush=True)
        print(f"Wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
