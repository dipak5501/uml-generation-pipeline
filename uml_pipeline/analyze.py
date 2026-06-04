from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from uml_pipeline.scoring import score_distribution


def plot_score_distributions(df: pd.DataFrame, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    score_col = "scores" if "scores" in df.columns else "scores_recomputed"
    for diagram_type, group in df.groupby("diagram_type"):
        fig, ax = plt.subplots(figsize=(8, 4))
        dist = score_distribution(group[score_col].dropna())
        ax.bar(dist.keys(), dist.values(), color="#4C72B0")
        ax.set_xlabel("Composite score")
        ax.set_ylabel("Count")
        ax.set_title(f"{diagram_type.title()} diagram — score distribution")
        path = out_dir / f"scores_{diagram_type}.png"
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved.append(path)

    vlm_cols = ["qwen25vl3b", "llama32vl11b", "aya_vision_8b"]
    present = [c for c in vlm_cols if c in df.columns]
    if present:
        fig, axes = plt.subplots(1, len(present), figsize=(4 * len(present), 4), sharey=True)
        if len(present) == 1:
            axes = [axes]
        for ax, col in zip(axes, present):
            dist = score_distribution(df[col].dropna())
            ax.bar(dist.keys(), dist.values())
            ax.set_title(col)
            ax.set_xlabel("Score")
        fig.suptitle("VLM score distributions (all diagram types)")
        path = out_dir / "vlm_scores_all.png"
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved.append(path)

    return saved


def summary_stats(df: pd.DataFrame) -> dict[str, Any]:
    score_col = "scores" if "scores" in df.columns else "scores_recomputed"
    stats: dict[str, Any] = {"total": len(df), "by_type": {}}
    for diagram_type, group in df.groupby("diagram_type"):
        s = group[score_col].dropna()
        stats["by_type"][diagram_type] = {
            "count": len(group),
            "mean_score": float(s.mean()) if len(s) else None,
            "render_failures": int((group[score_col].fillna(0) == 0).sum())
            if score_col in group
            else None,
        }
    return stats
