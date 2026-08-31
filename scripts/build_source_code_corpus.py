#!/usr/bin/env python3
"""
Build ≥50k source-code-oriented UML training rows from open web/HF corpora.

Primary source: the-stack-v2 PlantUML full (~109k GitHub repo .puml files) with
repo path + gha_language metadata — deduped against existing training parquets.

Also ingests code→PlantUML HF sets (coai, ibivibiv, vinzur, PeaceLovingGhost, …)
from the local data/raw/hf mirror when present.

Outputs:
  data/training/uml_source_code_50k.parquet
  data/training/uml_training_combined_100k.parquet  (with --merge-existing)
  data/training/source_code_manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build_training_corpus import (  # noqa: E402
    ADAPTERS,
    STACK_SUBTYPE_MAP,
    _code_hash,
    _extract_plantuml,
    infer_diagram_type,
    normalize_row,
)

HF_MIRROR = ROOT / "data" / "raw" / "hf"

# Source-code / repo / instruction corpora (local mirror slug → adapter + meta).
SOURCE_CODE_SOURCES: list[dict[str, Any]] = [
    {
        "slug": "devgpt-aimotion__the-stack-v2_PlantUML_full",
        "repo": "devgpt-aimotion/the-stack-v2_PlantUML_full",
        "adapter": "stack_source",
        "priority": 100,
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
        "slug": "ThePeaceLovingGhost__ClassDiagram_PlantUML_Text",
        "repo": "ThePeaceLovingGhost/ClassDiagram_PlantUML_Text",
        "adapter": "messages_chat",
        "forced_type": "class",
        "priority": 40,
        "input_mode": "requirement",
    },
    {
        "slug": "coai__plantuml_generation",
        "repo": "coai/plantuml_generation",
        "adapter": "inst_text",
        "priority": 35,
        "input_mode": "requirement",
    },
    {
        "slug": "ibivibiv__plantuml-training",
        "repo": "ibivibiv/plantuml-training",
        "adapter": "instruction_text",
        "priority": 35,
        "input_mode": "requirement",
    },
    {
        "slug": "prashant182__plantuml-json",
        "repo": "prashant182/plantuml-json",
        "adapter": "input_output",
        "priority": 30,
        "input_mode": "requirement",
    },
    {
        "slug": "vinzur__Prompt-to-PlantUML",
        "repo": "vinzur/Prompt-to-PlantUML",
        "adapter": "input_output",
        "priority": 30,
        "input_mode": "requirement",
    },
    {
        "slug": "vinzur__softw-desc-to-plantuml-usecase-diagram",
        "repo": "vinzur/softw-desc-to-plantuml-usecase-diagram",
        "adapter": "input_output",
        "forced_type": "usecase",
        "priority": 28,
        "input_mode": "requirement",
    },
    {
        "slug": "vinzur__user-stories-to-plantuml-usecase-diagram",
        "repo": "vinzur/user-stories-to-plantuml-usecase-diagram",
        "adapter": "input_output",
        "forced_type": "usecase",
        "priority": 28,
        "input_mode": "requirement",
    },
    {
        "slug": "josoa-test__plantuml-datasets",
        "repo": "josoa-test/plantuml-datasets",
        "adapter": "input_output",
        "priority": 25,
        "input_mode": "requirement",
    },
    {
        "slug": "nguyenvanviet__UMLCode-ClassDiagram-DeepSeek-32B-Reasoning-RAW",
        "repo": "nguyenvanviet/UMLCode-ClassDiagram-DeepSeek-32B-Reasoning-RAW",
        "adapter": "umlcode",
        "forced_type": "class",
        "priority": 20,
        "input_mode": "requirement",
    },
    {
        "slug": "nguyenvanviet__UMLCode-DeepSeek-32B-Reasoning-RAW",
        "repo": "nguyenvanviet/UMLCode-DeepSeek-32B-Reasoning-RAW",
        "adapter": "umlcode",
        "priority": 18,
        "input_mode": "requirement",
    },
]

_LANG_MAP = {
    "typescript": "typescript",
    "javascript": "javascript",
    "java": "java",
    "python": "python",
    "c": "c",
    "c#": "csharp",
    "go": "go",
    "c++": "cpp",
    "php": "php",
    "kotlin": "kotlin",
    "shell": "shell",
    "html": "html",
    "css": "css",
}

DEFAULT_FOCUS_LANGS = ("java", "python", "c")


def _norm_lang(raw: str | None) -> str | None:
    if not raw:
        return None
    key = str(raw).strip().lower()
    return _LANG_MAP.get(key, key.replace(" ", "_")[:24] or None)


def adapter_stack_source(item: dict[str, Any]) -> dict[str, Any] | None:
    """The Stack v2: real GitHub repo PlantUML with language + path context."""
    code = _extract_plantuml(str(item.get("code") or ""))
    if len(code) < 20:
        return None
    if "uml" in item and item.get("uml") is False:
        return None
    subtype = str(item.get("uml_subtype") or "").strip().lower()
    dtype = STACK_SUBTYPE_MAP.get(subtype) or infer_diagram_type(code)
    repo = str(item.get("repo_name") or "unknown")
    path = str(item.get("path") or "")
    lang = _norm_lang(str(item.get("gha_language") or item.get("language") or ""))
    ext = str(item.get("extension") or "").strip().lower()
    branch = str(item.get("branch_name") or "main")
    spec = (
        f"## Technical Specification\n"
        f"### Source\nOpen-source repository on the web (The Stack v2).\n"
        f"### Repository\n{repo}\n"
        f"### Branch\n{branch}\n"
        f"### Path\n{path}\n"
        f"### Repository language\n{lang or 'unknown'}\n"
        f"### File extension\n{ext or 'puml'}\n"
        f"### Target diagram type\n{dtype}\n"
        f"### Task\nRegenerate equivalent black-and-white PlantUML for a {dtype} diagram "
        f"from this {lang or 'multi-language'} codebase artifact.\n"
    )
    src_ctx = (
        f"// Repository: {repo}\n"
        f"// Branch: {branch}\n"
        f"// Path: {path}\n"
        f"// Language: {lang or 'unknown'}\n"
    )
    return {
        "input": spec,
        "source_requirement": src_ctx,
        "reasoning": "",
        "uml_code": code,
        "forced_inferred_type": dtype,
        "input_mode": "source_code",
        "source_language": lang,
    }


# Register stack_source adapter
ADAPTERS["stack_source"] = adapter_stack_source


def _plantuml_entities(code: str, n: int = 6) -> list[str]:
    names = re.findall(r"(?m)^\s*(?:class|interface|enum|object)\s+[\"']?(\w+)", code, flags=re.I)
    out: list[str] = []
    for name in names:
        if name and name not in out:
            out.append(name)
        if len(out) >= n:
            break
    return out


def _minimal_code_from_plantuml(uml: str, lang: str) -> str:
    """Synthesize a small code sketch from PlantUML class names (web row enrichment)."""
    ents = _plantuml_entities(uml, 4)
    if len(ents) < 2:
        return ""
    a, b = ents[0], ents[1]
    c = ents[2] if len(ents) > 2 else f"{a}Link"
    lang = (lang or "java").lower()
    if lang == "python":
        return (
            f"class {a}:\n"
            f"    def process(self):\n"
            f"        return True\n\n"
            f"class {b}({a}):\n"
            f"    def validate(self):\n"
            f"        pass\n\n"
            f"class {c}:\n"
            f"    def link(self, other: '{b}'):\n"
            f"        self.ref = other\n"
        )
    if lang == "c":
        return (
            f"#include <stdio.h>\n\n"
            f"typedef struct {a} {{\n"
            f"    int id;\n"
            f"}} {a};\n\n"
            f"typedef struct {b} {{\n"
            f"    {a} base;\n"
            f"}} {b};\n\n"
            f"typedef struct {c} {{\n"
            f"    {b}* ref;\n"
            f"}} {c};\n"
        )
    return (
        f"package demo;\n"
        f"public class {a} {{\n"
        f"  public void process() {{}}\n"
        f"}}\n"
        f"public class {b} extends {a} {{\n"
        f"  public void validate() {{}}\n"
        f"}}\n"
        f"public class {c} {{\n"
        f"  private {b} ref;\n"
        f"}}\n"
    )


def _enrich_stack_row(row: dict[str, Any]) -> dict[str, Any]:
    """Replace repo-comment stubs with minimal code when language is Java/Python/C."""
    lang = str(row.get("source_language") or "").lower()
    if lang not in DEFAULT_FOCUS_LANGS:
        return row
    uml = str(row.get("uml_code") or "")
    code = _minimal_code_from_plantuml(uml, lang)
    if len(code) < 40:
        return row
    from app.services.code_analysis import structure_to_spec

    dtype = str(row.get("diagram_type") or "class")
    row = dict(row)
    row["source_requirement"] = code
    row["technical_spec"] = structure_to_spec(code, dtype)
    row["input_mode"] = "source_code"
    return row


def _sanitize_hf_row(item: dict[str, Any]) -> dict[str, Any]:
    """Coerce numpy/list fields from HF parquet into plain Python scalars."""
    out: dict[str, Any] = {}
    for key, val in item.items():
        mod = type(val).__module__
        if mod and mod.startswith("numpy"):
            try:
                import numpy as np

                if isinstance(val, np.ndarray):
                    val = val.tolist() if val.size > 1 else (val.item() if val.size == 1 else "")
            except Exception:
                val = str(val)
        if hasattr(val, "item") and not isinstance(val, (str, bytes, dict, list)):
            try:
                val = val.item()
            except Exception:
                pass
        if isinstance(val, (list, tuple)) and key in {"input", "prompt", "output", "code"}:
            val = "\n".join(str(x) for x in val if x is not None)
        out[key] = val
    return out


def _read_local_hf(slug: str) -> pd.DataFrame | None:
    base = HF_MIRROR / slug
    for name in ("train.parquet", "train.jsonl"):
        path = base / name
        if path.is_file():
            if path.suffix == ".parquet":
                return pd.read_parquet(path)
            return pd.read_json(path, lines=True)
    return None


def _existing_hashes(*paths: Path) -> set[str]:
    seen: set[str] = set()
    for p in paths:
        if not p.is_file():
            continue
        df = pd.read_parquet(p)
        col = "uml_code" if "uml_code" in df.columns else None
        if not col:
            continue
        for v in df[col].astype(str):
            h = _code_hash(v)
            if h:
                seen.add(h)
    return seen


def _row_from_adapted(
    adapted: dict[str, Any],
    *,
    repo: str,
    forced_type: str | None,
    allow_types: set[str] | None,
    input_mode: str,
) -> dict[str, Any] | None:
    code = str(adapted.get("uml_code") or "")
    inferred = adapted.get("forced_inferred_type") or infer_diagram_type(code)
    dtype = forced_type or inferred
    if allow_types is not None:
        if dtype not in allow_types:
            if dtype == "unknown" and "unknown" in allow_types:
                dtype = "class"
            else:
                return None
    if dtype == "unknown":
        return None
    row = normalize_row(adapted, source=repo, diagram_type=dtype)
    row["input_mode"] = adapted.get("input_mode") or input_mode
    row["source_language"] = adapted.get("source_language")
    if adapted.get("source_requirement"):
        row["source_requirement"] = str(adapted["source_requirement"])
    return row


def load_source_pool(*, skip_hf_download: bool) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for meta in sorted(SOURCE_CODE_SOURCES, key=lambda m: -m["priority"]):
        slug = meta["slug"]
        repo = meta["repo"]
        adapter_name = meta["adapter"]
        adapter = ADAPTERS[adapter_name]
        df = _read_local_hf(slug)
        if df is None:
            if skip_hf_download:
                print(f"  SKIP {repo}: no local mirror at {HF_MIRROR / slug}")
                continue
            print(f"  Loading {repo} from Hugging Face …")
            from datasets import load_dataset

            try:
                ds = load_dataset(repo, split="train")
                df = ds.to_pandas()
            except Exception as exc:
                print(f"  SKIP {repo}: {type(exc).__name__}: {str(exc).splitlines()[0][:120]}")
                continue
        print(f"  {repo}: {len(df)} raw rows [{adapter_name}]")
        allow = meta.get("allow_types")
        kept = 0
        for item in df.to_dict(orient="records"):
            adapted = adapter(_sanitize_hf_row(dict(item)))
            if not adapted:
                continue
            row = _row_from_adapted(
                adapted,
                repo=repo,
                forced_type=meta.get("forced_type"),
                allow_types=allow,
                input_mode=meta.get("input_mode") or "source_code",
            )
            if row:
                rows.append(row)
                kept += 1
        print(f"    kept {kept}")

    if not rows:
        raise RuntimeError("No source-code rows loaded — run download_all_corpora.py first")
    pool = pd.DataFrame(rows)
    before = len(pool)
    pool = pool.drop_duplicates(subset=["uml_code"], keep="first")
    print(f"Pool dedup: {before} → {len(pool)}")
    return pool


def select_source_corpus(
    pool: pd.DataFrame,
    *,
    target: int,
    exclude_hashes: set[str],
    seed: int,
    focus_langs: set[str] | None = None,
) -> pd.DataFrame:
    import random

    rng = random.Random(seed)
    if exclude_hashes:
        mask = ~pool["uml_code"].map(lambda c: _code_hash(str(c)) in exclude_hashes)
        pool = pool[mask].copy()
        print(f"After excluding existing training: {len(pool)} rows")

    if focus_langs:
        langs = {str(l).lower() for l in focus_langs}
        lang_mask = pool["source_language"].astype(str).str.lower().isin(langs)
        pool = pool[lang_mask].copy()
        print(f"After language filter {sorted(langs)}: {len(pool)} rows")
    if len(pool) < target:
        print(f"WARNING: only {len(pool)} unique rows (requested {target})")

    # Prefer stack repo rows (source_code + language metadata)
    stack = pool[pool["source_dataset"].astype(str).str.contains("the-stack-v2_PlantUML_full")].copy()
    other = pool[~pool.index.isin(stack.index)].copy()
    selected: list[pd.DataFrame] = []
    remaining = target

    # Stratify stack by language for diversity
    if not stack.empty and remaining > 0:
        by_lang: dict[str, list[int]] = {}
        for idx, row in stack.iterrows():
            lang = str(row.get("source_language") or "unknown")
            by_lang.setdefault(lang, []).append(idx)
        langs = list(by_lang.keys())
        rng.shuffle(langs)
        per_lang = max(1, min(remaining // max(1, len(langs)), 8000))
        chosen_idx: list[int] = []
        for lang in langs:
            idxs = by_lang[lang][:]
            rng.shuffle(idxs)
            take = min(per_lang, len(idxs), remaining - len(chosen_idx))
            chosen_idx.extend(idxs[:take])
        if len(chosen_idx) < remaining:
            rest_idx = [i for i in stack.index if i not in chosen_idx]
            rng.shuffle(rest_idx)
            need = remaining - len(chosen_idx)
            chosen_idx.extend(rest_idx[:need])
        part = stack.loc[chosen_idx[:remaining]]
        selected.append(part)
        remaining -= len(part)
        print(f"  stack full: {len(part)} (langs={len(by_lang)})")

    if remaining > 0 and not other.empty:
        idxs = list(other.index)
        rng.shuffle(idxs)
        part = other.loc[idxs[:remaining]]
        selected.append(part)
        remaining -= len(part)
        print(f"  other sources: +{len(part)}")

    if not selected:
        return pd.DataFrame()
    out = pd.concat(selected, ignore_index=True)
    out = out.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    if focus_langs:
        out = pd.DataFrame([_enrich_stack_row(r) for r in out.to_dict(orient="records")])
    return out


def top_up_focus_langs(
    corpus: pd.DataFrame,
    *,
    target: int,
    langs: list[str],
    seed: int,
) -> pd.DataFrame:
    """Honest synthetic top-up for Java/Python/C when web pool is short."""
    if len(corpus) >= target:
        return corpus.iloc[:target].copy()
    need = target - len(corpus)
    print(f"Top-up: {need} synthetic {langs} code samples (web pool short after filter/dedup)")
    from scripts.build_scenario_code_corpus import build_code_samples_for_langs

    per_lang = max(1, need // max(1, len(langs)))
    rows: list[dict[str, Any]] = []
    for i, lang in enumerate(langs):
        chunk = build_code_samples_for_langs(per_lang + (1 if i < need % len(langs) else 0), seed + i * 1000, [lang])
        for r in chunk:
            uid = r.get("id") or f"{lang}-{i}"
            r["source_dataset"] = "synthetic_code_langs_focused"
            r["uml_code"] = str(r["uml_code"]).replace(
                "@startuml", f"@startuml\n' training-id:{uid}", 1
            )
        rows.extend(chunk)
    topup_df = pd.DataFrame(rows)
    for col in corpus.columns:
        if col not in topup_df.columns:
            topup_df[col] = None
    for col in topup_df.columns:
        if col not in corpus.columns:
            corpus[col] = None
    combined = pd.concat([corpus, topup_df[corpus.columns]], ignore_index=True)
    combined = combined.drop_duplicates(subset=["uml_code"], keep="first")
    if len(combined) < target:
        extra = build_code_samples_for_langs(target - len(combined) + 500, seed + 777_000, langs)
        for r in extra:
            uid = r.get("id") or "x"
            r["source_dataset"] = "synthetic_code_langs_focused"
            r["uml_code"] = str(r["uml_code"]).replace(
                "@startuml", f"@startuml\n' training-id:{uid}", 1
            )
        extra_df = pd.DataFrame(extra)
        for col in combined.columns:
            if col not in extra_df.columns:
                extra_df[col] = None
        combined = pd.concat([combined, extra_df[combined.columns]], ignore_index=True)
        combined = combined.drop_duplicates(subset=["uml_code"], keep="first")
    if len(combined) > target:
        combined = combined.sample(n=target, random_state=seed).reset_index(drop=True)
    return combined


def merge_existing(
    new_df: pd.DataFrame,
    existing_path: Path,
    out_path: Path,
) -> pd.DataFrame:
    if not existing_path.is_file():
        combined = new_df
    else:
        base = pd.read_parquet(existing_path)
        for col in new_df.columns:
            if col not in base.columns:
                base[col] = None
        for col in base.columns:
            if col not in new_df.columns:
                new_df[col] = None
        combined = pd.concat([base[new_df.columns], new_df], ignore_index=True)
    before = len(combined)
    combined = combined.drop_duplicates(subset=["uml_code"], keep="first")
    print(f"Merged {existing_path.name}: {before} → {len(combined)} unique")
    combined.to_parquet(out_path, index=False)
    combined.to_json(
        out_path.with_suffix(".jsonl"),
        orient="records",
        lines=True,
        force_ascii=False,
    )
    return combined


def main() -> None:
    ap = argparse.ArgumentParser(description="Build source-code-oriented UML training corpus")
    ap.add_argument("--target", type=int, default=50000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--languages",
        default="",
        help="Comma-separated focus languages (e.g. java,python,c). Empty = all.",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output parquet path (default: uml_source_code_50k.parquet or _10k_jpc)",
    )
    ap.add_argument(
        "--exclude-parquet",
        action="append",
        default=[
            "data/training/uml_training_8000.parquet",
            "data/training/uml_training_supplement_merged.parquet",
        ],
        help="Parquet files whose uml_code hashes to exclude (dedup)",
    )
    ap.add_argument(
        "--merge-existing",
        type=Path,
        default=Path("data/training/uml_training_supplement_merged.parquet"),
        help="Merge new rows into this parquet → uml_training_combined_100k.parquet",
    )
    ap.add_argument(
        "--skip-hf-download",
        action="store_true",
        default=True,
        help="Only read local data/raw/hf mirror (default)",
    )
    ap.add_argument(
        "--allow-hf-download",
        action="store_true",
        help="Fetch missing corpora from Hugging Face",
    )
    args = ap.parse_args()
    skip_dl = args.skip_hf_download and not args.allow_hf_download
    focus_langs: set[str] | None = None
    if args.languages.strip():
        focus_langs = {l.strip().lower() for l in args.languages.split(",") if l.strip()}

    train_dir = ROOT / "data" / "training"
    train_dir.mkdir(parents=True, exist_ok=True)

    exclude_paths = [ROOT / p for p in args.exclude_parquet]
    exclude_hashes = _existing_hashes(*exclude_paths)
    print(f"Excluding {len(exclude_hashes)} existing uml_code hashes")

    pool = load_source_pool(skip_hf_download=skip_dl)
    if focus_langs:
        lang_mask = pool["source_language"].astype(str).str.lower().isin(focus_langs)
        pool_focus = pool[lang_mask].copy()
        print(f"Focus-language pool: {len(pool_focus)} / {len(pool)} rows")
    else:
        pool_focus = pool
    print("Pool by source:", dict(Counter(pool_focus["source_dataset"]).most_common(8)))
    print("Pool input_mode:", dict(Counter(pool_focus.get("input_mode", pd.Series(["?"])))))

    corpus = select_source_corpus(
        pool_focus,
        target=args.target,
        exclude_hashes=exclude_hashes,
        seed=args.seed,
        focus_langs=focus_langs,
    )

    # Honest synthetic code top-up when unique web pool is exhausted after dedup.
    if focus_langs:
        corpus = top_up_focus_langs(
            corpus,
            target=args.target,
            langs=sorted(focus_langs),
            seed=args.seed + 99_000,
        )
    elif len(corpus) < args.target:
        need = args.target - len(corpus)
        print(f"Top-up: {need} synthetic multi-language code samples (web pool exhausted after dedup)")
        from scripts.build_scenario_code_corpus import build_code_samples, to_training_frame

        codes = build_code_samples(need, args.seed + 99_000)
        for r in codes:
            r["source_dataset"] = "synthetic_code_web_topup"
            uid = r.get("id") or "x"
            r["uml_code"] = r["uml_code"].replace(
                "@startuml", f"@startuml\n' training-id:{uid}", 1
            )
        topup_df = to_training_frame(codes)
        topup_df["input_mode"] = "source_code"
        langs = [r.get("source_language") for r in codes]
        topup_df["source_language"] = langs
        for col in corpus.columns:
            if col not in topup_df.columns:
                topup_df[col] = None
        corpus = pd.concat([corpus, topup_df[corpus.columns]], ignore_index=True)
        corpus = corpus.drop_duplicates(subset=["uml_code"], keep="first")
        if len(corpus) > args.target:
            corpus = corpus.sample(n=args.target, random_state=args.seed).reset_index(drop=True)
        print(f"After top-up: {len(corpus)} rows")

    if args.output:
        out_sc = args.output if args.output.is_absolute() else ROOT / args.output
    elif focus_langs:
        out_sc = train_dir / "uml_source_code_10k_jpc.parquet"
    else:
        out_sc = train_dir / "uml_source_code_50k.parquet"
    corpus.to_parquet(out_sc, index=False)
    corpus.to_json(out_sc.with_suffix(".jsonl"), orient="records", lines=True, force_ascii=False)

    combined_path = train_dir / "uml_training_combined_100k.parquet"
    combined = merge_existing(corpus, args.merge_existing, combined_path)

    manifest = {
        "target_source_code_rows": args.target,
        "selected_source_code_rows": len(corpus),
        "combined_rows": len(combined),
        "excluded_hashes": len(exclude_hashes),
        "focus_languages": sorted(focus_langs) if focus_langs else None,
        "by_source": dict(Counter(corpus["source_dataset"])),
        "by_input_mode": dict(Counter(corpus.get("input_mode", pd.Series(["?"])))),
        "by_language": dict(Counter(corpus.get("source_language", pd.Series(["?"])))),
        "by_language_top": dict(
            Counter(corpus.get("source_language", pd.Series(["?"]))).most_common(20)
        ),
        "by_diagram_type": dict(Counter(corpus["diagram_type"])),
        "sources": [s["repo"] for s in SOURCE_CODE_SOURCES],
        "outputs": {
            "source_code_parquet": str(out_sc),
            "combined_parquet": str(combined_path),
        },
        "notes": [
            "Primary web source: the-stack-v2_PlantUML_full (GitHub repo .puml + gha_language).",
            "Deduped against existing 50k + supplement parquets by uml_code hash.",
            "Combined parquet merges with uml_training_supplement_merged for finetune JSONL.",
            "Java/Python/C focus: stack rows enriched with minimal code sketches from PlantUML entities.",
            "Synthetic top-up via build_code_samples_for_langs when web pool is short (documented).",
        ],
    }
    man_path = train_dir / "source_code_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
