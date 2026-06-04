from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm

from uml_pipeline.llm_client import LLMClient, provider_from_env
from uml_pipeline.prompts import (
    PLANTUML_CODE_PROMPT,
    PLANTUML_DIAGRAM_HINTS,
    SPEC_USER_PROMPT,
    SYSTEM_ARCHITECT_PROMPT,
    VLM_SCORING_PROMPT,
)
from uml_pipeline.render import render_plantuml
from uml_pipeline.scoring import weighted_composite


def generate_spec(
    client: LLMClient,
    diagram_type: str,
    mode: str = "architect",
) -> str:
    if mode == "user":
        return client.chat(
            "You generate realistic software feature descriptions.",
            SPEC_USER_PROMPT,
            temperature=0.8,
        )
    user = (
        f"Create a technical specification for a {diagram_type} UML diagram "
        f"for a realistic software system feature."
    )
    return client.chat(SYSTEM_ARCHITECT_PROMPT, user, temperature=0.8)


def generate_plantuml(client: LLMClient, specification: str, diagram_type: str) -> str:
    hint = PLANTUML_DIAGRAM_HINTS[diagram_type]
    prompt = PLANTUML_CODE_PROMPT.format(diagram_hint=hint, specification=specification)
    return client.chat(
        "You output only valid PlantUML code.",
        prompt,
        temperature=0.2,
    )


def validate_with_vlms(
    image_path: Path,
    specification: str,
    vlm_clients: dict[str, LLMClient],
    weights: dict[str, float],
) -> dict[str, Any]:
    prompt = VLM_SCORING_PROMPT.format(specification=specification)
    scores: dict[str, int] = {}
    for name, client in vlm_clients.items():
        try:
            scores[name] = client.vision_score(image_path, prompt)
        except Exception:
            scores[name] = 0
    composite = weighted_composite(scores, weights)
    return {**scores, "scores": composite}


def run_generation_batch(
    cfg: dict[str, Any],
    diagram_type: str,
    n_samples: int,
    spec_mode: str = "architect",
) -> pd.DataFrame:
    provider = provider_from_env()
    spec_model = __import__("os").environ.get("SPEC_MODEL", "llama3.2:1b")
    code_model = __import__("os").environ.get("CODE_MODEL", "deepseek-r1:32b")

    spec_client = LLMClient(spec_model, provider=provider)
    code_client = LLMClient(code_model, provider=provider)

    jar = Path(cfg["plantuml"]["jar_path"])
    if not jar.is_absolute():
        jar = Path(cfg["root"]) / jar
    img_dir = Path(cfg["data_dir"]) / "images" / diagram_type
    img_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for _ in tqdm(range(n_samples), desc=f"generate-{diagram_type}"):
        record_id = str(uuid.uuid4())[:8]
        try:
            spec = generate_spec(spec_client, diagram_type, spec_mode)
            reasoning = ""  # optional: parse from code model if using CoT tags
            uml_code = generate_plantuml(code_client, spec, diagram_type)
            img_path, err = render_plantuml(uml_code, img_dir, jar)

            row: dict[str, Any] = {
                "id": record_id,
                "diagram_type": diagram_type,
                "input": spec,
                "reasoning": reasoning,
                "uml_code": uml_code,
                "render_error": err,
            }

            if img_path:
                row["image_path"] = str(img_path)
                vlm_names = __import__("os").environ.get(
                    "VLM_MODELS", "qwen2.5vl:3b,llama3.2-vision:11b,aya-vision:8b"
                ).split(",")
                weight_keys = list(cfg["vlm_weights"].keys())
                vlm_clients = {
                    weight_keys[i]: LLMClient(vlm_names[i].strip(), provider=provider)
                    for i in range(min(len(weight_keys), len(vlm_names)))
                }
                validated = validate_with_vlms(
                    img_path, spec, vlm_clients, cfg["vlm_weights"]
                )
                row.update(validated)
            else:
                row["scores"] = 0.0
                for k in cfg["vlm_weights"]:
                    row[k] = 0

            rows.append(row)
        except Exception as exc:
            rows.append(
                {
                    "id": record_id,
                    "diagram_type": diagram_type,
                    "error": str(exc),
                    "scores": 0,
                }
            )

    return pd.DataFrame(rows)


def save_batch(df: pd.DataFrame, cfg: dict[str, Any], diagram_type: str) -> Path:
    out = Path(cfg["output_dir"]) / f"generated_{diagram_type}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    jsonl = out.with_suffix(".jsonl")
    df.to_json(jsonl, orient="records", lines=True, force_ascii=False)
    return out
