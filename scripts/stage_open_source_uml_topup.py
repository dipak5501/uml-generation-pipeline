#!/usr/bin/env python3
"""
Stage open-source UML/PlantUML top-up for the next industrial CONTINUOUS pass.

Loads on-disk HF corpora under data/raw/hf/ (prefer local), optionally harvests
public GitHub .puml via code search, filters to app types only
(class/object/component/package), dedupes against the current enriched mix,
and refreshes finetune_industrial JSONL for the *next* pass (does not kill
training; live adapter path is untouched).

Does not delete data/uml_app.db or data/artifacts/. Never prints tokens.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_training_corpus import (  # noqa: E402
    ADAPTERS,
    OPEN_SOURCES,
    PAPER_TYPES,
    TOPUP_SOURCES,
    infer_diagram_type,
    normalize_row,
    _extract_plantuml,
)

APP_TYPES = set(PAPER_TYPES)
HF_DIR = ROOT / "data" / "raw" / "hf"
OUT_TOPUP = ROOT / "data" / "training" / "uml_open_source_uml_topup.parquet"
OUT_TOPUP_JSONL = ROOT / "data" / "training" / "uml_open_source_uml_topup.jsonl"
OUT_MIX = ROOT / "data" / "training" / "uml_industrial_enriched_mix.parquet"
OUT_MIX_MANIFEST = ROOT / "data" / "training" / "industrial_enriched_mix_manifest.json"
OUT_TOPUP_MANIFEST = ROOT / "data" / "training" / "open_source_uml_topup_manifest.json"
SWAP_NOTE = ROOT / "data" / "finetune_industrial" / "enriched_swap_note.json"
FINETUNE_DIR = ROOT / "data" / "finetune_industrial"

# Prefer UMLCode + PlantUML web sources that map to app types.
PREFERRED_REPOS = [
    "nguyenvanviet/UMLCode-ClassDiagram-DeepSeek-32B-Reasoning-RAW",
    "nguyenvanviet/UMLCode_ObjectDiagram_Scored",
    "nguyenvanviet/UMLCode_ComponentDiagram_Scored",
    "nguyenvanviet/UMLCode_PackageDiagram_Scored",
    "nguyenvanviet/UMLCode_ObjectDiagram",
    "nguyenvanviet/UMLCode_ComponentDiagram",
    "nguyenvanviet/UMLCode_PackageDiagram",
    "nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-UC-Class-Sequence-Scored",
    "nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-RAW",
    "nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-Scored",
    "nguyenvanviet/UMLCode_Reasoning_Class_UseCase_Scored",
    "devgpt-aimotion/the-stack-v2_PlantUML_full",
    "devgpt-aimotion/the-stack-v2_PlantUML_filtered",
    "ThePeaceLovingGhost/ClassDiagram_PlantUML_Text",
    "coai/plantuml_generation",
    "ibivibiv/plantuml-training",
    "prashant182/plantuml-json",
    "vinzur/Prompt-to-PlantUML",
    "Seym0n/cas2uml_hand-drawn_to_plantuml_dataset",
]


def _slug(repo: str) -> str:
    return repo.replace("/", "__")


def _read_env_key(key: str) -> str:
    script = ROOT / "scripts" / "read_env_key.sh"
    if not script.is_file():
        return os.getenv(key) or ""
    try:
        out = subprocess.check_output(
            ["bash", str(script), key, str(ROOT / ".env")],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return (out or "").strip()
    except Exception:
        return os.getenv(key) or ""


def _source_meta() -> dict[str, dict[str, Any]]:
    meta: dict[str, dict[str, Any]] = {}
    for src in OPEN_SOURCES + TOPUP_SOURCES:
        meta[src["repo"]] = src
    # Full stack not in TOPUP by default (filtered is); allow local full.
    meta.setdefault(
        "devgpt-aimotion/the-stack-v2_PlantUML_full",
        {
            "repo": "devgpt-aimotion/the-stack-v2_PlantUML_full",
            "forced_type": None,
            "adapter": "stack_plantuml",
            "allow_types": set(APP_TYPES) | {"unknown"},
        },
    )
    return meta


def _load_local_frame(repo: str) -> pd.DataFrame | None:
    dest = HF_DIR / _slug(repo)
    for name in ("train.parquet", "train.jsonl"):
        path = dest / name
        if not path.is_file():
            continue
        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        return pd.read_json(path, lines=True)
    return None


def _adapt_repo(repo: str, df: pd.DataFrame, meta: dict[str, Any]) -> list[dict[str, Any]]:
    adapter_name = meta.get("adapter") or "umlcode"
    adapter = ADAPTERS.get(adapter_name)
    if adapter is None:
        return []
    allow = meta.get("allow_types")
    if allow is not None:
        allow = set(allow)
    forced = meta.get("forced_type")
    rows: list[dict[str, Any]] = []
    for item in df.to_dict(orient="records"):
        adapted = adapter(dict(item))
        if not adapted:
            continue
        code = str(adapted.get("uml_code") or "")
        if "@startuml" not in code.lower() or len(code) < 80:
            continue
        inferred = adapted.get("forced_inferred_type") or infer_diagram_type(code)
        dtype = forced or inferred
        if dtype == "unknown" and allow and "unknown" in allow:
            dtype = "class"
        if dtype not in APP_TYPES:
            continue
        if allow is not None and dtype not in allow and "unknown" not in allow:
            continue
        row = normalize_row(adapted, source=repo, diagram_type=dtype)
        row["input_mode"] = "requirement"
        row["source_language"] = ""
        row["scores"] = row.get("composite_score")
        rows.append(row)
    return rows


def harvest_github_puml(max_files: int = 400) -> list[dict[str, Any]]:
    """Public GitHub code search for PlantUML class/object/component/package files."""
    token = _read_env_key("GH_TOKEN") or _read_env_key("GITHUB_TOKEN")
    if not token:
        print("GitHub harvest skipped: no GH_TOKEN")
        return []

    queries = [
        "extension:puml class @startuml",
        "extension:plantuml class @startuml",
        "extension:puml package @startuml",
        "extension:puml component @startuml",
        "extension:puml object @startuml",
        "filename:class.puml @startuml",
        "path:docs extension:puml @startuml class",
    ]
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "uml-generation-pipeline-corpus-builder",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    seen_urls: set[str] = set()
    rows: list[dict[str, Any]] = []
    rate_limited = False

    for q in queries:
        if len(rows) >= max_files or rate_limited:
            break
        for page in range(1, 6):
            if len(rows) >= max_files or rate_limited:
                break
            params = urllib.parse.urlencode(
                {"q": q, "per_page": 30, "page": page}
            )
            url = f"https://api.github.com/search/code?{params}"
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")[:200]
                print(f"  GitHub search HTTP {exc.code} for query page={page}: {body}")
                if exc.code in (403, 429):
                    rate_limited = True
                break
            except Exception as exc:
                print(f"  GitHub search error: {type(exc).__name__}")
                break

            items = payload.get("items") or []
            if not items:
                break
            for it in items:
                if len(rows) >= max_files:
                    break
                html_url = str(it.get("html_url") or "")
                raw_url = html_url.replace("github.com/", "raw.githubusercontent.com/").replace(
                    "/blob/", "/"
                )
                if not raw_url or raw_url in seen_urls:
                    continue
                seen_urls.add(raw_url)
                repo = str((it.get("repository") or {}).get("full_name") or "unknown")
                path = str(it.get("path") or "")
                try:
                    rreq = urllib.request.Request(
                        raw_url,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "User-Agent": "uml-generation-pipeline-corpus-builder",
                            "Accept": "application/vnd.github.raw",
                        },
                    )
                    with urllib.request.urlopen(rreq, timeout=30) as rresp:
                        text = rresp.read().decode("utf-8", errors="replace")
                except Exception:
                    continue
                code = _extract_plantuml(text)
                if len(code) < 80 or "@startuml" not in code.lower():
                    continue
                dtype = infer_diagram_type(code)
                if dtype not in APP_TYPES:
                    continue
                spec = (
                    f"## Technical Specification\n"
                    f"### Source\nPublic GitHub PlantUML ({repo}).\n"
                    f"### Path\n{path}\n"
                    f"### Target diagram type\n{dtype}\n"
                    f"### Task\nRegenerate equivalent PlantUML for a {dtype} diagram.\n"
                )
                adapted = {"input": spec, "reasoning": "", "uml_code": code}
                row = normalize_row(
                    adapted, source=f"github_code_search/{repo}", diagram_type=dtype
                )
                row["input_mode"] = "requirement"
                row["source_language"] = ""
                row["scores"] = row.get("composite_score")
                rows.append(row)
                time.sleep(0.35)  # be polite on contents API
            time.sleep(2.0)  # search secondary rate limit

    print(f"GitHub harvest kept {len(rows)} UML rows (rate_limited={rate_limited})")
    return rows


def _uml_hash(code: str) -> str:
    return hashlib.sha1((code or "").strip().encode("utf-8")).hexdigest()


def _to_mix_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "diagram_type",
        "input_mode",
        "source_language",
        "source_requirement",
        "technical_spec",
        "uml_code",
        "dataset_accepted",
        "majority_accepted",
        "scores",
        "source_dataset",
    ]
    out = pd.DataFrame()
    out["diagram_type"] = df["diagram_type"].astype(str)
    out["input_mode"] = df.get("input_mode", pd.Series(["requirement"] * len(df))).fillna(
        "requirement"
    )
    out["source_language"] = df.get("source_language", pd.Series([""] * len(df))).fillna("")
    out["source_requirement"] = df["source_requirement"].astype(str)
    out["technical_spec"] = df["technical_spec"].astype(str)
    out["uml_code"] = df["uml_code"].astype(str)
    out["dataset_accepted"] = df.get("dataset_accepted", False).fillna(False).astype(bool)
    out["majority_accepted"] = df.get("majority_accepted", False).fillna(False).astype(bool)
    if "scores" in df.columns:
        out["scores"] = df["scores"]
    elif "composite_score" in df.columns:
        out["scores"] = df["composite_score"]
    else:
        out["scores"] = 0.0
    out["source_dataset"] = df["source_dataset"].astype(str)
    # quality gates
    mask = (
        out["diagram_type"].isin(APP_TYPES)
        & out["uml_code"].str.lower().str.contains("@startuml", na=False)
        & (out["technical_spec"].str.len() >= 40)
        & (out["uml_code"].str.len() >= 80)
    )
    return out.loc[mask, cols].reset_index(drop=True)


def main() -> None:
    meta_by_repo = _source_meta()
    all_rows: list[dict[str, Any]] = []
    load_stats: list[dict[str, Any]] = []

    for repo in PREFERRED_REPOS:
        meta = meta_by_repo.get(repo) or {
            "repo": repo,
            "adapter": "umlcode",
            "forced_type": None,
            "allow_types": APP_TYPES,
        }
        # Tighten allow_types to app UML when present
        if meta.get("allow_types"):
            meta = dict(meta)
            meta["allow_types"] = set(meta["allow_types"]) & (APP_TYPES | {"unknown"})
        df = _load_local_frame(repo)
        if df is None or df.empty:
            load_stats.append({"repo": repo, "local": False, "raw": 0, "kept": 0})
            print(f"SKIP missing local: {repo}")
            continue
        rows = _adapt_repo(repo, df, meta)
        load_stats.append({"repo": repo, "local": True, "raw": int(len(df)), "kept": len(rows)})
        print(f"LOCAL {repo}: raw={len(df)} kept_uml={len(rows)}")
        all_rows.extend(rows)

    gh_rows = harvest_github_puml(max_files=400)
    all_rows.extend(gh_rows)

    if not all_rows:
        raise SystemExit("No open-source UML rows assembled")

    open_df = _to_mix_columns(pd.DataFrame(all_rows))
    before = len(open_df)
    open_df = open_df.drop_duplicates(subset=["uml_code"], keep="first").reset_index(drop=True)
    print(f"Open pool dedupe {before} → {len(open_df)}")

    existing = pd.read_parquet(OUT_MIX) if OUT_MIX.is_file() else pd.DataFrame()
    existing_hashes = set()
    if not existing.empty:
        existing_hashes = {_uml_hash(c) for c in existing["uml_code"].astype(str)}
    open_df["_h"] = open_df["uml_code"].map(_uml_hash)
    novel = open_df[~open_df["_h"].isin(existing_hashes)].drop(columns=["_h"]).reset_index(drop=True)
    print(f"Novel vs enriched mix: {len(novel)} / {len(open_df)}")

    # Cap novel top-up so mix stays balanced (prefer diversity by type)
    cap = 12000
    parts = []
    per = max(500, cap // 4)
    for dtype in PAPER_TYPES:
        pool = novel[novel["diagram_type"] == dtype]
        parts.append(pool.sample(n=min(per, len(pool)), random_state=42) if len(pool) else pool)
    topup = pd.concat(parts, ignore_index=True) if parts else novel.iloc[0:0]
    if len(topup) < cap:
        rest = novel[~novel.index.isin(topup.index)]
        need = cap - len(topup)
        if not rest.empty and need > 0:
            topup = pd.concat(
                [topup, rest.sample(n=min(need, len(rest)), random_state=42)],
                ignore_index=True,
            )
    topup = topup.drop_duplicates(subset=["uml_code"], keep="first").reset_index(drop=True)

    OUT_TOPUP.parent.mkdir(parents=True, exist_ok=True)
    topup.to_parquet(OUT_TOPUP, index=False)
    topup.to_json(OUT_TOPUP_JSONL, orient="records", lines=True, force_ascii=False)

    if existing.empty:
        merged = topup.copy()
    else:
        merged = pd.concat([existing, topup], ignore_index=True)
        merged = merged.drop_duplicates(subset=["uml_code"], keep="first").reset_index(drop=True)
    merged.to_parquet(OUT_MIX, index=False)

    # Refresh finetune JSONL for next CONTINUOUS pass (same dir training uses).
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    prep = subprocess.run(
        [
            str(ROOT / ".venv" / "bin" / "python"),
            str(ROOT / "scripts" / "prepare_finetune_data.py"),
            "--input",
            str(OUT_MIX),
            "--out-dir",
            str(FINETUNE_DIR),
            "--max-spec-chars",
            "2800",
            "--max-uml-chars",
            "3500",
            "--valid-ratio",
            "0.04",
            "--test-ratio",
            "0.03",
            "--prefer-accepted",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    print(prep.stdout[-2000:] if prep.stdout else "")
    if prep.returncode != 0:
        print(prep.stderr[-2000:] if prep.stderr else "")
        raise SystemExit(f"prepare_finetune_data failed rc={prep.returncode}")

    train_n = sum(1 for _ in open(FINETUNE_DIR / "train.jsonl", encoding="utf-8"))
    valid_n = sum(1 for _ in open(FINETUNE_DIR / "valid.jsonl", encoding="utf-8"))
    test_n = sum(1 for _ in open(FINETUNE_DIR / "test.jsonl", encoding="utf-8"))

    now = datetime.now(timezone.utc).isoformat()
    topup_manifest = {
        "updated_at": now,
        "purpose": "open-source UML top-up (GitHub + HF) for next industrial CONTINUOUS pass",
        "app_types": list(PAPER_TYPES),
        "excluded": ["flowchart", "sequence", "activity", "usecase", "state", "deployment"],
        "open_pool_unique": int(len(open_df)),
        "novel_vs_prior_mix": int(len(novel)),
        "topup_rows_added": int(len(topup)),
        "by_diagram_type": topup["diagram_type"].value_counts().to_dict(),
        "by_source_dataset": topup["source_dataset"].value_counts().head(40).to_dict(),
        "load_stats": load_stats,
        "github_rows": len(gh_rows),
        "parquet": str(OUT_TOPUP),
        "merged_mix": str(OUT_MIX),
        "merged_mix_rows": int(len(merged)),
    }
    OUT_TOPUP_MANIFEST.write_text(json.dumps(topup_manifest, indent=2), encoding="utf-8")

    mix_manifest = {
        "updated_at": now,
        "row_count": int(len(merged)),
        "prior_enriched_rows": int(len(existing)),
        "open_source_topup_added": int(len(topup)),
        "by_diagram_type": merged["diagram_type"].value_counts().to_dict(),
        "by_input_mode": merged["input_mode"].value_counts().to_dict()
        if "input_mode" in merged
        else {},
        "by_source_dataset": merged["source_dataset"].value_counts().head(50).to_dict(),
        "policy": {
            "diagram_types": list(PAPER_TYPES),
            "require_startuml": True,
            "excluded": ["flowchart", "sequence", "activity", "usecase", "state", "deployment"],
        },
        "purpose": "industrial KeepAlive next-pass DATA — UML-only enriched mix + open-source top-up",
        "parquet": str(OUT_MIX),
        "topup_manifest": str(OUT_TOPUP_MANIFEST),
    }
    OUT_MIX_MANIFEST.write_text(json.dumps(mix_manifest, indent=2), encoding="utf-8")

    (FINETUNE_DIR / "manifest.json").write_text(
        json.dumps(
            {
                "source": str(OUT_MIX),
                "total_usable": train_n + valid_n + test_n,
                "train": train_n,
                "valid": valid_n,
                "test": test_n,
                "max_spec_chars": 2800,
                "max_uml_chars": 3500,
                "seed": 42,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    SWAP_NOTE.write_text(
        json.dumps(
            {
                "updated_at": now,
                "note": (
                    "Open-source UML top-up merged into enriched mix; finetune_industrial "
                    "refreshed for next CONTINUOUS pass. Current training process undisturbed "
                    "(no hard-kill)."
                ),
                "adapter": "models/uml-plantuml-lora-industrial-complete",
                "data": "data/finetune_industrial",
                "train_rows": train_n,
                "total_usable": train_n + valid_n + test_n,
                "open_source_topup_rows": int(len(topup)),
                "merged_mix_rows": int(len(merged)),
                "sources_manifest": str(OUT_MIX_MANIFEST),
                "topup_manifest": str(OUT_TOPUP_MANIFEST),
                "live_adapter_unchanged": "models/uml-plantuml-lora-sourcecode-30k",
                "dropped": {
                    "flowchart": True,
                    "non_app_uml_types": True,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "topup_added": int(len(topup)),
                "merged_mix": int(len(merged)),
                "finetune_train": train_n,
                "finetune_total": train_n + valid_n + test_n,
                "by_type": topup["diagram_type"].value_counts().to_dict(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
