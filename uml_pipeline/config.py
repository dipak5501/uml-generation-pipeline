from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or ROOT / "config.yaml"
    with cfg_path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["root"] = str(ROOT)
    cfg["data_dir"] = str(ROOT / cfg.get("data_dir", "data"))
    cfg["output_dir"] = str(ROOT / cfg.get("output_dir", "output"))
    return cfg


def ensure_dirs(cfg: dict[str, Any]) -> None:
    for key in ("data_dir", "output_dir"):
        Path(cfg[key]).mkdir(parents=True, exist_ok=True)
    Path(cfg["data_dir"], "images").mkdir(parents=True, exist_ok=True)
    Path(cfg["data_dir"], "raw").mkdir(parents=True, exist_ok=True)
    Path(cfg["output_dir"], "figures").mkdir(parents=True, exist_ok=True)


def env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name, "").lower()
    if val in ("1", "true", "yes"):
        return True
    if val in ("0", "false", "no"):
        return False
    return default
