#!/usr/bin/env python3
"""
Import UML-in-the-Wild (Zenodo DOI 10.5281/zenodo.18952372) into training parquet.

Reads:
  data/raw/uml_in_the_wild/uml_metadata_enriched.json
  data/raw/uml_in_the_wild/puml_files.zip  (or extracted puml_files/)

Writes:
  data/training/uml_in_the_wild.parquet
  data/training/uml_in_the_wild_app.parquet  (class/object/component/package)
  data/training/uml_in_the_wild_import_manifest.json

Does NOT download PNGs. Does NOT touch live .env adapter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

PAPER_TYPES = frozenset({"class", "object", "component", "package"})
TYPE_MAP = {
    "class": "class",
    "object": "object",
    "component": "component",
    "package": "package",
    "activity": "flowchart",
    "sequence": "sequence",
    "state": "state",
    "deployment": "deployment",
    "usecase": "usecase",
    "use_case": "usecase",
    "timing": "sequence",
}

SOURCE = "zenodo:uml-in-the-wild:10.5281/zenodo.18952372"


def _code_hash(uml_code: str) -> str:
    return hashlib.sha1((uml_code or "").strip().encode("utf-8")).hexdigest()


def _extract_plantuml(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    m = re.search(r"@startuml[\s\S]*?@enduml", text, flags=re.I)
    if m:
        return m.group(0).strip()
    if "@startuml" in text.lower():
        return text
    # wrap bare PlantUML
    return f"@startuml\n{text}\n@enduml"


def _infer_package(uml: str, primary: str) -> str:
    c = (uml or "").lower()
    if primary in PAPER_TYPES:
        return primary
    # Heuristic: package-heavy diagrams sometimes labeled class/component
    if c.count("package ") >= 2 and "class " not in c and "component " not in c:
        return "package"
    return primary


def _build_spec(meta: dict[str, Any], dtype: str, filename: str) -> str:
    repo = str(meta.get("repository") or "unknown")
    path = str(meta.get("original_path") or filename)
    reasoning = str(meta.get("reasoning") or "").strip()
    elements = meta.get("elements") or {}
    connections = meta.get("connections") or {}
    el_bits = ", ".join(f"{k}={v}" for k, v in sorted(elements.items()) if v) or "n/a"
    conn_bits = ", ".join(f"{k}={v}" for k, v in sorted(connections.items()) if v) or "n/a"
    parts = [
        "## Technical Specification",
        f"### Target diagram type\n{dtype}",
        "### Source\nUML-in-the-Wild open-source PlantUML diagram "
        f"(Zenodo DOI 10.5281/zenodo.18952372).",
        f"### Repository\n{repo}",
        f"### Path\n{path}",
        f"### Structure summary\nElements: {el_bits}. Connections: {conn_bits}.",
    ]
    if reasoning:
        parts.append(f"### Classification note\n{reasoning}")
    parts.append(
        "### Task\nProduce valid black-and-white PlantUML for this diagram type "
        "matching the structural intent above."
    )
    return "\n".join(parts)


def _load_puml_from_zip(zip_path: Path, name: str) -> str:
    member = f"puml_files/{name}"
    with zipfile.ZipFile(zip_path, "r") as zf:
        try:
            return zf.read(member).decode("utf-8", errors="replace")
        except KeyError:
            # try bare name
            try:
                return zf.read(name).decode("utf-8", errors="replace")
            except KeyError:
                return ""


def _load_puml_from_dir(puml_dir: Path, name: str) -> str:
    path = puml_dir / name
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--raw-dir",
        type=Path,
        default=ROOT / "data" / "raw" / "uml_in_the_wild",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "training" / "uml_in_the_wild.parquet",
    )
    ap.add_argument(
        "--out-app",
        type=Path,
        default=ROOT / "data" / "training" / "uml_in_the_wild_app.parquet",
    )
    ap.add_argument(
        "--app-types-only",
        action="store_true",
        default=True,
        help="Also write app-types parquet (class/object/component/package).",
    )
    ap.add_argument("--min-uml-chars", type=int, default=30)
    ap.add_argument("--max-uml-chars", type=int, default=8000)
    ap.add_argument("--limit", type=int, default=0, help="Debug: stop after N kept rows")
    args = ap.parse_args()

    meta_path = args.raw_dir / "uml_metadata_enriched.json"
    zip_path = args.raw_dir / "puml_files.zip"
    puml_dir = args.raw_dir / "puml_files"
    if not meta_path.is_file():
        raise SystemExit(f"Missing {meta_path}")

    use_zip = zip_path.is_file()
    use_dir = puml_dir.is_dir()
    if not use_zip and not use_dir:
        raise SystemExit(f"Need {zip_path} or extracted {puml_dir}")

    print(f"Loading metadata {meta_path} …", flush=True)
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    classifications: dict[str, Any] = payload.get("classifications") or {}
    print(f"classifications={len(classifications)} use_zip={use_zip} use_dir={use_dir}", flush=True)

    # Keep zip handle open for speed
    zf = zipfile.ZipFile(zip_path, "r") if use_zip else None

    rows: list[dict[str, Any]] = []
    drop_reasons: Counter[str] = Counter()
    type_raw: Counter[str] = Counter()
    type_kept: Counter[str] = Counter()
    seen_hash: set[str] = set()

    try:
        for i, (fname, meta) in enumerate(classifications.items()):
            if not isinstance(meta, dict):
                drop_reasons["bad_meta"] += 1
                continue
            if meta.get("extraction_error"):
                drop_reasons["extraction_error"] += 1
                continue
            primary = str(meta.get("primary_type") or "").strip().lower()
            type_raw[primary or "missing"] += 1
            dtype = TYPE_MAP.get(primary, primary or "unknown")
            if dtype == "unknown" or not dtype:
                drop_reasons["unknown_type"] += 1
                continue

            if use_dir:
                raw = _load_puml_from_dir(puml_dir, fname)
            else:
                assert zf is not None
                member = f"puml_files/{fname}"
                try:
                    raw = zf.read(member).decode("utf-8", errors="replace")
                except KeyError:
                    try:
                        raw = zf.read(fname).decode("utf-8", errors="replace")
                    except KeyError:
                        drop_reasons["missing_puml"] += 1
                        continue

            uml = _extract_plantuml(raw)
            if len(uml) < args.min_uml_chars:
                drop_reasons["uml_too_short"] += 1
                continue
            if len(uml) > args.max_uml_chars:
                uml = uml[: args.max_uml_chars - 20].rstrip() + "\n@enduml"
            dtype = _infer_package(uml, dtype)

            h = _code_hash(uml)
            if h in seen_hash:
                drop_reasons["dedupe"] += 1
                continue
            seen_hash.add(h)

            spec = _build_spec(meta, dtype, fname)
            if len(spec) < 40:
                drop_reasons["spec_too_short"] += 1
                continue

            rows.append(
                {
                    "id": h[:12],
                    "diagram_type": dtype,
                    "source_requirement": spec,
                    "technical_spec": spec,
                    "uml_code": uml,
                    "reasoning_private": str(meta.get("reasoning") or ""),
                    "qwen25vl3b": None,
                    "llama32vl11b": None,
                    "aya_vision_8b": None,
                    "composite_score": 0.0,
                    "majority_accepted": False,
                    "affirmative_votes": 0,
                    "dataset_accepted": False,
                    "source_dataset": SOURCE,
                    "input_mode": "requirement",
                    "source_language": "",
                    "wild_blob_id": str(meta.get("blob_id") or ""),
                    "wild_repository": str(meta.get("repository") or ""),
                    "wild_primary_type": primary,
                    "wild_elements_total": int(meta.get("elements_total") or 0),
                    "wild_connections_total": int(meta.get("connections_total") or 0),
                }
            )
            type_kept[dtype] += 1
            if args.limit and len(rows) >= args.limit:
                break
            if (i + 1) % 20000 == 0:
                print(f"  scanned {i+1}/{len(classifications)} kept={len(rows)}", flush=True)
    finally:
        if zf is not None:
            zf.close()

    df = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"Wrote {len(df)} rows → {args.out}", flush=True)

    app_df = df[df["diagram_type"].isin(PAPER_TYPES)].copy() if len(df) else df
    app_df.to_parquet(args.out_app, index=False)
    print(f"Wrote {len(app_df)} app-type rows → {args.out_app}", flush=True)

    manifest = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "doi": "10.5281/zenodo.18952372",
        "source": SOURCE,
        "raw_classifications": len(classifications),
        "kept_all_types": int(len(df)),
        "kept_app_types": int(len(app_df)),
        "by_diagram_type_kept": dict(type_kept),
        "by_primary_type_raw": dict(type_raw),
        "drop_reasons": dict(drop_reasons),
        "parquet_all": str(args.out),
        "parquet_app": str(args.out_app),
        "claim_hygiene": (
            "PlantUML text + metadata only; PNGs not downloaded. "
            "Specs are synthesized from Wild classification metadata (not human requirements). "
            "No VLM scores; dataset_accepted=false. Live API adapter not modified."
        ),
    }
    man_path = args.out.parent / "uml_in_the_wild_import_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
