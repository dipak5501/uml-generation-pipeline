#!/usr/bin/env python3
"""
Build a large training corpus from open Hugging Face UML / PlantUML datasets.

Default paper-scale target was 8000; for ≥50k web training use:
  python scripts/build_training_corpus.py --target 50000 --include-flowchart

Sources include nguyenvanviet UMLCode sets plus external open PlantUML corpora
(the-stack PlantUML filtered, class-diagram chat, instruction sets, etc.).
Rows are deduped on uml_code. Prefer unique web data; scenario-corpus can top up.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from datasets import load_dataset

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from app.services.scoring import majority_vote_accept, paper_composite, verify_scores
from uml_pipeline.config import ensure_dirs, load_config

load_dotenv()

# Open (non-gated) Hugging Face sources used for the thesis / finetune corpus.
OPEN_SOURCES: list[dict[str, Any]] = [
    {
        "repo": "nguyenvanviet/UMLCode-ClassDiagram-DeepSeek-32B-Reasoning-RAW",
        "forced_type": "class",
        "priority": 10,
        "adapter": "umlcode",
    },
    {
        "repo": "nguyenvanviet/UMLCode_ObjectDiagram_Scored",
        "forced_type": "object",
        "priority": 20,
        "adapter": "umlcode",
    },
    {
        "repo": "nguyenvanviet/UMLCode_ComponentDiagram_Scored",
        "forced_type": "component",
        "priority": 20,
        "adapter": "umlcode",
    },
    {
        "repo": "nguyenvanviet/UMLCode_PackageDiagram_Scored",
        "forced_type": "package",
        "priority": 20,
        "adapter": "umlcode",
    },
    {
        "repo": "nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-UC-Class-Sequence-Scored",
        "forced_type": None,
        "priority": 5,
        "allow_types": {
            "class",
            "object",
            "component",
            "package",
            "flowchart",
            "usecase",
            "sequence",
        },
        "adapter": "umlcode",
    },
]

FLOWCHART_SOURCES: list[dict[str, Any]] = [
    {
        "repo": "nguyenvanviet/UMLCode_Activity_Final",
        "forced_type": "flowchart",
        "priority": 15,
        "adapter": "umlcode",
    },
]

# Extra open rows: more UMLCode types + large web PlantUML corpora.
TOPUP_SOURCES: list[dict[str, Any]] = [
    {
        "repo": "nguyenvanviet/UMLCode_DeploymentDiagram",
        "forced_type": "deployment",
        "priority": 8,
        "adapter": "umlcode",
    },
    {
        "repo": "nguyenvanviet/UMLCode_Sequence_Reasoning-RAW",
        "forced_type": "sequence",
        "priority": 8,
        "adapter": "umlcode",
    },
    {
        "repo": "nguyenvanviet/UMLCode_Sequence_scores",
        "forced_type": "sequence",
        "priority": 9,
        "adapter": "umlcode",
    },
    {
        "repo": "nguyenvanviet/UMLCode_StateDiagram",
        "forced_type": "state",
        "priority": 8,
        "adapter": "umlcode",
    },
    {
        "repo": "nguyenvanviet/UMLCode_StateDiagram_Scored",
        "forced_type": "state",
        "priority": 9,
        "adapter": "umlcode",
    },
    {
        "repo": "nguyenvanviet/UMLCode_Activity",
        "forced_type": "flowchart",
        "priority": 7,
        "adapter": "umlcode",
    },
    {
        "repo": "nguyenvanviet/UMLCode_ObjectDiagram",
        "forced_type": "object",
        "priority": 6,
        "adapter": "umlcode",
    },
    {
        "repo": "nguyenvanviet/UMLCode_ComponentDiagram",
        "forced_type": "component",
        "priority": 6,
        "adapter": "umlcode",
    },
    {
        "repo": "nguyenvanviet/UMLCode_PackageDiagram",
        "forced_type": "package",
        "priority": 6,
        "adapter": "umlcode",
    },
    {
        "repo": "nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-RAW",
        "forced_type": None,
        "priority": 4,
        "allow_types": {
            "class",
            "object",
            "component",
            "package",
            "flowchart",
            "usecase",
            "sequence",
            "state",
            "deployment",
        },
        "adapter": "umlcode",
    },
    {
        "repo": "nguyenvanviet/UMLCode_Reasoning_Class_UseCase_Scored",
        "forced_type": None,
        "priority": 4,
        "allow_types": {
            "class",
            "object",
            "component",
            "package",
            "flowchart",
            "usecase",
            "sequence",
            "state",
            "deployment",
        },
        "adapter": "umlcode",
    },
    # Large open web PlantUML (The Stack v2 filtered)
    {
        "repo": "devgpt-aimotion/the-stack-v2_PlantUML_filtered",
        "forced_type": None,
        "priority": 3,
        "adapter": "stack_plantuml",
        "allow_types": {
            "class",
            "object",
            "component",
            "package",
            "flowchart",
            "usecase",
            "sequence",
            "state",
            "deployment",
            "unknown",
        },
    },
    {
        "repo": "ThePeaceLovingGhost/ClassDiagram_PlantUML_Text",
        "forced_type": "class",
        "priority": 12,
        "adapter": "messages_chat",
    },
    {
        "repo": "coai/plantuml_generation",
        "forced_type": None,
        "priority": 5,
        "adapter": "inst_text",
        "allow_types": {
            "class",
            "object",
            "component",
            "package",
            "flowchart",
            "usecase",
            "sequence",
            "state",
            "deployment",
        },
    },
    {
        "repo": "ibivibiv/plantuml-training",
        "forced_type": None,
        "priority": 5,
        "adapter": "instruction_text",
        "allow_types": {
            "class",
            "object",
            "component",
            "package",
            "flowchart",
            "usecase",
            "sequence",
            "state",
            "deployment",
        },
    },
    {
        "repo": "prashant182/plantuml-json",
        "forced_type": None,
        "priority": 5,
        "adapter": "input_output",
        "allow_types": {
            "class",
            "object",
            "component",
            "package",
            "flowchart",
            "usecase",
            "sequence",
            "state",
            "deployment",
        },
    },
    {
        "repo": "vinzur/Prompt-to-PlantUML",
        "forced_type": None,
        "priority": 5,
        "adapter": "input_output",
        "allow_types": {
            "class",
            "object",
            "component",
            "package",
            "flowchart",
            "usecase",
            "sequence",
            "state",
            "deployment",
        },
    },
    {
        "repo": "vinzur/softw-desc-to-plantuml-usecase-diagram",
        "forced_type": "usecase",
        "priority": 7,
        "adapter": "input_output",
    },
    {
        "repo": "vinzur/user-stories-to-plantuml-usecase-diagram",
        "forced_type": "usecase",
        "priority": 7,
        "adapter": "input_output",
    },
    {
        "repo": "Seym0n/cas2uml_hand-drawn_to_plantuml_dataset",
        "forced_type": None,
        "priority": 6,
        "adapter": "cas2uml",
        "allow_types": {
            "class",
            "object",
            "component",
            "package",
            "flowchart",
            "usecase",
            "sequence",
            "state",
            "deployment",
        },
    },
]

PAPER_TYPES = ("class", "object", "component", "package")
EXTENDED_TYPES = PAPER_TYPES + (
    "flowchart",
    "usecase",
    "sequence",
    "state",
    "deployment",
)
WEIGHTS = {"qwen25vl3b": 53.1, "llama32vl11b": 50.7, "aya_vision_8b": 39.9}

STACK_SUBTYPE_MAP = {
    "class": "class",
    "object": "object",
    "component": "component",
    "package": "package",
    "activity": "flowchart",
    "flowchart": "flowchart",
    "usecase": "usecase",
    "use_case": "usecase",
    "sequence": "sequence",
    "state": "state",
    "deployment": "deployment",
    "timing": "sequence",
    "communication": "sequence",
}


def infer_diagram_type(uml_code: str) -> str:
    c = (uml_code or "").lower()
    if "usecase" in c or re.search(r"\bactor\s+", c):
        return "usecase"
    if re.search(r"\bobject\s+\w+", c) or 'object "' in c:
        return "object"
    if "package " in c or 'package "' in c:
        return "package"
    if re.search(r"\bcomponent\s+", c) or re.search(r"\[.+\]\s+as\s+", c):
        return "component"
    if "[*]" in c or re.search(r"\bstate\s+", c):
        return "state"
    if re.search(r"\bnode\s+", c) or "cloud " in c:
        return "deployment"
    if "participant " in c:
        return "sequence"
    if (
        re.search(r"(?m)^\s*start\s*$", c)
        or re.search(r"(?m)^\s*stop\s*$", c)
        or "if (" in c
        or re.search(r"(?m)^\s*:[^;]+;", c)
    ) and "class " not in c:
        return "flowchart"
    if "class " in c or "abstract " in c or "interface " in c or "enum " in c:
        return "class"
    return "unknown"


def _code_hash(uml_code: str) -> str:
    return hashlib.sha1((uml_code or "").strip().encode("utf-8")).hexdigest()


def _to_int_score(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _extract_plantuml(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    m = re.search(r"@startuml[\s\S]*?@enduml", text, flags=re.I)
    if m:
        return m.group(0).strip()
    if "@startuml" in text.lower():
        return text
    return ""


def normalize_row(row: dict[str, Any], *, source: str, diagram_type: str) -> dict[str, Any]:
    scores = {
        "qwen25vl3b": _to_int_score(row.get("qwen25vl3b")),
        "llama32vl11b": _to_int_score(row.get("llama32vl11b")),
        "aya_vision_8b": _to_int_score(row.get("aya_vision_8b")),
    }
    has_any = any(v is not None for v in scores.values())
    render_ok = True
    if has_any:
        verification = verify_scores(scores, WEIGHTS, render_ok=render_ok, tau=4.0, min_composite=3.0)
        composite = verification.composite
        majority = verification.majority_accepted
        votes = verification.affirmative_votes
        dataset_ok = verification.dataset_accepted
    else:
        existing = row.get("scores")
        composite = float(existing) if existing not in (None, "") else paper_composite(
            {k: 0 for k in WEIGHTS}, WEIGHTS, render_ok=False
        )
        majority, votes, _ = majority_vote_accept({k: 0 for k in WEIGHTS}, tau=4.0)
        dataset_ok = False

    spec = str(row.get("input") or row.get("technical_spec") or "")
    src_req = str(row.get("source_requirement") or spec)
    return {
        "id": _code_hash(str(row.get("uml_code", "")))[:12],
        "diagram_type": diagram_type,
        "source_requirement": src_req,
        "technical_spec": spec,
        "uml_code": str(row.get("uml_code") or ""),
        "reasoning_private": str(row.get("reasoning") or ""),
        "qwen25vl3b": scores["qwen25vl3b"],
        "llama32vl11b": scores["llama32vl11b"],
        "aya_vision_8b": scores["aya_vision_8b"],
        "composite_score": float(composite) if composite is not None else 0.0,
        "majority_accepted": bool(majority) if has_any else False,
        "affirmative_votes": int(votes) if has_any else 0,
        "dataset_accepted": bool(dataset_ok) if has_any else False,
        "source_dataset": source,
    }


def adapter_umlcode(item: dict[str, Any]) -> dict[str, Any] | None:
    code = str(item.get("uml_code") or "")
    if len(code.strip()) < 20:
        return None
    return {
        "input": item.get("input") or "",
        "reasoning": item.get("reasoning") or "",
        "uml_code": code,
        "qwen25vl3b": item.get("qwen25vl3b"),
        "llama32vl11b": item.get("llama32vl11b"),
        "aya_vision_8b": item.get("aya_vision_8b"),
        "scores": item.get("scores"),
    }


def adapter_stack_plantuml(item: dict[str, Any]) -> dict[str, Any] | None:
    code = _extract_plantuml(str(item.get("code") or ""))
    if len(code) < 20:
        return None
    # Prefer filtered uml==True when present
    if "uml" in item and item.get("uml") is False:
        return None
    subtype = str(item.get("uml_subtype") or "").strip().lower()
    dtype = STACK_SUBTYPE_MAP.get(subtype) or infer_diagram_type(code)
    repo = str(item.get("repo_name") or "unknown")
    path = str(item.get("path") or "")
    spec = (
        f"## Technical Specification\n"
        f"### Source\nOpen-source PlantUML file from The Stack v2 ({repo}).\n"
        f"### Path\n{path}\n"
        f"### Target diagram type\n{dtype}\n"
        f"### Task\nRegenerate equivalent PlantUML for a {dtype} diagram matching this file's structure.\n"
    )
    return {
        "input": spec,
        "reasoning": "",
        "uml_code": code,
        "forced_inferred_type": dtype,
    }


def adapter_messages_chat(item: dict[str, Any]) -> dict[str, Any] | None:
    msgs = item.get("messages")
    if isinstance(msgs, str):
        try:
            msgs = json.loads(msgs.replace("'", '"'))
        except Exception:
            return None
    if not isinstance(msgs, list):
        return None
    user = ""
    assistant = ""
    for m in msgs:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "")
        content = str(m.get("content") or "")
        if role == "user":
            user = content
        elif role == "assistant":
            assistant = content
    code = _extract_plantuml(assistant)
    if len(code) < 20 or len(user) < 40:
        return None
    return {"input": user, "reasoning": "", "uml_code": code}


def adapter_inst_text(item: dict[str, Any]) -> dict[str, Any] | None:
    text = str(item.get("text") or "")
    code = _extract_plantuml(text)
    if len(code) < 20:
        return None
    # Strip llama-style tags; keep description before plantuml
    before = text.split("@startuml")[0]
    before = re.sub(r"</?s>", "", before)
    before = re.sub(r"\[/?INST\]", "", before)
    before = before.strip()
    if len(before) < 40:
        before = f"Generate PlantUML for the following diagram:\n{before or 'diagram from corpus'}"
    return {"input": before[:4000], "reasoning": "", "uml_code": code}


def adapter_instruction_text(item: dict[str, Any]) -> dict[str, Any] | None:
    text = str(item.get("text") or "")
    code = _extract_plantuml(text)
    if len(code) < 20:
        return None
    m = re.search(r"Instruction:\s*(.*?)(?:Response:|Output:|@startuml)", text, flags=re.I | re.S)
    inp = (m.group(1).strip() if m else text.split("@startuml")[0]).strip()
    if len(inp) < 40:
        inp = "Generate a PlantUML diagram for the described system."
    return {"input": inp[:4000], "reasoning": "", "uml_code": code}


def adapter_input_output(item: dict[str, Any]) -> dict[str, Any] | None:
    code = _extract_plantuml(str(item.get("output") or item.get("uml_code") or ""))
    inp = str(item.get("input") or item.get("prompt") or "").strip()
    if len(code) < 20 or len(inp) < 20:
        return None
    return {"input": inp[:4000], "reasoning": "", "uml_code": code}


def adapter_cas2uml(item: dict[str, Any]) -> dict[str, Any] | None:
    code = _extract_plantuml(str(item.get("code") or ""))
    if len(code) < 20:
        return None
    t = str(item.get("type") or "").lower()
    if "class" in t:
        dtype = "class"
    elif "seq" in t:
        dtype = "sequence"
    elif "use" in t:
        dtype = "usecase"
    elif "act" in t or "flow" in t:
        dtype = "flowchart"
    elif "state" in t:
        dtype = "state"
    else:
        dtype = infer_diagram_type(code)
    spec = (
        f"## Technical Specification\n"
        f"### Source\nHand-drawn UML → PlantUML (cas2uml).\n"
        f"### Type\n{t or dtype}\n"
        f"### Task\nProduce clean PlantUML for a {dtype} diagram.\n"
    )
    return {
        "input": spec,
        "reasoning": "",
        "uml_code": code,
        "forced_inferred_type": dtype,
    }


ADAPTERS: dict[str, Callable[[dict[str, Any]], dict[str, Any] | None]] = {
    "umlcode": adapter_umlcode,
    "stack_plantuml": adapter_stack_plantuml,
    "messages_chat": adapter_messages_chat,
    "inst_text": adapter_inst_text,
    "instruction_text": adapter_instruction_text,
    "input_output": adapter_input_output,
    "cas2uml": adapter_cas2uml,
}


def load_open_frames(include_flowchart: bool, allow_topup_sources: bool) -> pd.DataFrame:
    sources = list(OPEN_SOURCES)
    if include_flowchart:
        sources.extend(FLOWCHART_SOURCES)
    if allow_topup_sources:
        sources.extend(TOPUP_SOURCES)

    frames: list[pd.DataFrame] = []
    for meta in sorted(sources, key=lambda m: -m["priority"]):
        repo = meta["repo"]
        adapter_name = meta.get("adapter") or "umlcode"
        adapter = ADAPTERS[adapter_name]
        print(f"Loading {repo} [{adapter_name}] ...")
        try:
            ds = load_dataset(repo, split="train")
        except Exception as exc:
            print(f"  SKIP {repo}: {type(exc).__name__}: {str(exc).splitlines()[0][:160]}")
            continue
        rows: list[dict[str, Any]] = []
        allow = meta.get("allow_types")
        for item in ds:
            adapted = adapter(dict(item))
            if not adapted:
                continue
            code = str(adapted.get("uml_code") or "")
            inferred = adapted.get("forced_inferred_type") or infer_diagram_type(code)
            dtype = meta.get("forced_type") or inferred
            if allow is not None and dtype not in allow:
                # Remap unknown stack files to class if they still have plantuml
                if dtype == "unknown" and "unknown" in allow:
                    dtype = "class"
                else:
                    continue
            if dtype == "unknown":
                continue
            if meta.get("forced_type") is None and adapted.get("forced_inferred_type") is None:
                if inferred != dtype and inferred not in {dtype, "unknown"}:
                    # keep inferred when forced_type unset
                    dtype = inferred if inferred != "unknown" else dtype
            if meta.get("forced_type") and inferred not in {dtype, "unknown"} and inferred in {
                "usecase",
                "sequence",
                "state",
                "deployment",
            }:
                # only skip hard mismatches for typed UMLCode repos
                if adapter_name == "umlcode":
                    continue
            rows.append(normalize_row(adapted, source=repo, diagram_type=dtype))
        df = pd.DataFrame(rows)
        if df.empty:
            print("  kept 0 rows")
            continue
        print(f"  kept {len(df)} rows (types={dict(Counter(df['diagram_type']))})")
        frames.append(df)

    if not frames:
        raise RuntimeError("No open datasets loaded")
    merged = pd.concat(frames, ignore_index=True)
    before = len(merged)
    merged = merged.drop_duplicates(subset=["uml_code"], keep="first")
    print(f"Deduped {before} → {len(merged)} unique uml_code rows")
    return merged


def select_corpus(
    df: pd.DataFrame,
    *,
    target: int,
    per_type: int,
    seed: int,
    include_flowchart: bool,
    include_extended_types: bool,
) -> pd.DataFrame:
    rng = __import__("random").Random(seed)
    selected: list[pd.DataFrame] = []
    remaining_target = target

    types = list(PAPER_TYPES)
    if include_flowchart:
        types.append("flowchart")
    if include_extended_types:
        for t in ("usecase", "sequence", "state", "deployment"):
            if t not in types:
                types.append(t)

    leftovers: dict[str, pd.DataFrame] = {}
    for dtype in types:
        pool = df[df["diagram_type"] == dtype].copy()
        idxs = list(pool.index)
        rng.shuffle(idxs)
        take_n = min(per_type, len(idxs), remaining_target)
        chosen = pool.loc[idxs[:take_n]]
        leftovers[dtype] = pool.loc[idxs[take_n:]]
        selected.append(chosen)
        remaining_target -= len(chosen)
        print(f"  {dtype}: selected {len(chosen)} (available {len(pool)})")

    if remaining_target > 0:
        topup_order = list(types)
        # Prefer abundant class / stack leftovers
        for dtype in topup_order:
            if remaining_target <= 0:
                break
            pool = leftovers.get(dtype)
            if pool is None or pool.empty:
                continue
            idxs = list(pool.index)
            rng.shuffle(idxs)
            take_n = min(remaining_target, len(idxs))
            extra = pool.loc[idxs[:take_n]]
            selected.append(extra)
            remaining_target -= len(extra)
            print(f"  top-up {dtype}: +{len(extra)}")

    # Final sweep: any leftover types not yet considered
    if remaining_target > 0:
        used_idx = set()
        for part in selected:
            used_idx.update(part.index.tolist())
        rest = df[~df.index.isin(used_idx)]
        if not rest.empty:
            idxs = list(rest.index)
            rng.shuffle(idxs)
            take_n = min(remaining_target, len(idxs))
            extra = rest.loc[idxs[:take_n]]
            selected.append(extra)
            remaining_target -= len(extra)
            print(f"  top-up any: +{len(extra)}")

    out = pd.concat(selected, ignore_index=True) if selected else pd.DataFrame()
    out = out.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build open-source UML training artifacts")
    parser.add_argument("--target", type=int, default=8000, help="Total rows to select")
    parser.add_argument(
        "--per-type",
        type=int,
        default=None,
        help="Preferred max per diagram type (default: max(2000, target//4))",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--no-flowchart",
        action="store_true",
        help="Exclude flowchart/activity rows",
    )
    parser.add_argument(
        "--include-flowchart",
        action="store_true",
        help="Explicitly include flowchart (default already includes unless --no-flowchart)",
    )
    parser.add_argument(
        "--no-topup-sources",
        action="store_true",
        help="Do not use extra open repos / the-stack for fill",
    )
    parser.add_argument(
        "--no-extended-types",
        action="store_true",
        help="Only paper types (+ flowchart if enabled)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: data/training)",
    )
    args = parser.parse_args()
    include_flowchart = False if args.no_flowchart else True
    per_type = args.per_type if args.per_type is not None else max(2000, args.target // 4)

    cfg = load_config()
    ensure_dirs(cfg)
    out_dir = args.out_dir or (Path(cfg["data_dir"]) / "training")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Downloading / caching open Hugging Face UML sources …")
    pool = load_open_frames(
        include_flowchart=include_flowchart,
        allow_topup_sources=not args.no_topup_sources,
    )
    print(f"Deduped pool size: {len(pool)}")
    print("Pool by type:", dict(Counter(pool["diagram_type"])))

    corpus = select_corpus(
        pool,
        target=args.target,
        per_type=per_type,
        seed=args.seed,
        include_flowchart=include_flowchart,
        include_extended_types=not args.no_extended_types,
    )
    if len(corpus) < args.target:
        print(
            f"WARNING: only {len(corpus)} unique open-source rows available "
            f"(requested {args.target}). Use scenario-corpus / merges to top up."
        )

    parquet_path = out_dir / "uml_training_8000.parquet"
    jsonl_path = out_dir / "uml_training_8000.jsonl"
    corpus.to_parquet(parquet_path, index=False)
    corpus.to_json(jsonl_path, orient="records", lines=True, force_ascii=False)

    by_type = corpus["diagram_type"].value_counts().to_dict()
    accepted = int(corpus["dataset_accepted"].sum()) if "dataset_accepted" in corpus else 0
    scored = int(corpus["qwen25vl3b"].notna().sum()) if "qwen25vl3b" in corpus else 0
    by_source = corpus["source_dataset"].value_counts().to_dict()
    sources_list = [s["repo"] for s in OPEN_SOURCES]
    if include_flowchart:
        sources_list += [s["repo"] for s in FLOWCHART_SOURCES]
    if not args.no_topup_sources:
        sources_list += [s["repo"] for s in TOPUP_SOURCES]
    manifest = {
        "total_rows": len(corpus),
        "unique_pool_size": len(pool),
        "target": args.target,
        "per_type_preferred": per_type,
        "by_diagram_type": by_type,
        "by_source_dataset": by_source,
        "scored_rows": scored,
        "dataset_accepted_rows": accepted,
        "seed": args.seed,
        "sources": sources_list,
        "outputs": {
            "parquet": str(parquet_path),
            "jsonl": str(jsonl_path),
        },
        "notes": [
            "Assembled from open Hugging Face UMLCode + PlantUML web corpora (non-gated).",
            "Includes the-stack-v2_PlantUML_filtered when --no-topup-sources is not set.",
            "Deduped on uml_code; prefer unique web rows before synthetic scenario top-up.",
            "Filenames keep uml_training_8000.* for pipeline compatibility even when N≠8000.",
            "reasoning_private may contain model CoT; strip before UI display.",
        ],
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\nWrote {len(corpus)} artifacts → {parquet_path}")
    print(f"Wrote JSONL → {jsonl_path}")
    print(f"Manifest → {manifest_path}")
    print("By type:", by_type)


if __name__ == "__main__":
    main()
