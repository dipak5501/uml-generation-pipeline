"""Self-adaptation: remember which generators and repairs work, then prefer them.

This is not a second copy of the same prompt. After each run the pipeline records
(diagram type, failure category, strategy, success). Later runs reorder strategies
and may skip a generator that has been losing for that diagram type.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.settings import ROOT, get_settings

DEFAULT_MEMORY = ROOT / "data" / "adaptation_memory.json"
_LOCK = threading.Lock()

# Default repair order by failure class (thesis §7).
DEFAULT_STRATEGIES: dict[str, list[str]] = {
    "syntax": ["sanitize_syntax", "spec_rebuild", "llm_targeted"],
    "compile": ["sanitize_syntax", "spec_rebuild", "llm_targeted"],
    "uml_structure": ["sanitize_syntax", "spec_rebuild", "llm_targeted"],
    "missing_element": ["inject_missing", "spec_rebuild", "llm_targeted"],
    "hallucinated_entity": ["strip_hallucinations", "spec_rebuild"],
    "wrong_relationship": ["fix_relationships", "spec_rebuild"],
    "package_hierarchy": ["fix_package_hierarchy", "spec_rebuild"],
    "render": ["sanitize_syntax", "spec_rebuild"],
    "semantic_alignment": ["spec_rebuild", "inject_missing", "strip_hallucinations"],
}

MIN_SAMPLES_TO_ADAPT = 3


def _empty() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": None,
        "generators": {},
        "strategies": {},
        "recent": [],
    }


@dataclass
class Rate:
    ok: int = 0
    fail: int = 0

    @property
    def n(self) -> int:
        return self.ok + self.fail

    @property
    def rate(self) -> float:
        return (self.ok + 1) / (self.n + 2)


@dataclass
class AdaptationSession:
    """Per-generation log of policy choices and attempted strategies."""

    diagram_type: str
    events: list[dict[str, Any]] = field(default_factory=list)
    tried_strategies: list[str] = field(default_factory=list)
    generator: str | None = None
    generator_reason: str = ""

    def note(self, **event: Any) -> None:
        event.setdefault("at", datetime.now(timezone.utc).isoformat())
        self.events.append(event)

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagram_type": self.diagram_type,
            "generator": self.generator,
            "generator_reason": self.generator_reason,
            "tried_strategies": list(self.tried_strategies),
            "events": self.events,
        }


class AdaptationMemory:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else Path(get_settings().adaptation_memory_path)
        self._data = _empty()
        self.load()

    def load(self) -> None:
        if self.path.is_file():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._data = {**_empty(), **raw}
            except (OSError, json.JSONDecodeError):
                self._data = _empty()
        else:
            self._data = _empty()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data["updated_at"] = datetime.now(timezone.utc).isoformat()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _bucket(self, kind: str, key: str, name: str) -> dict[str, int]:
        root = self._data.setdefault(kind, {})
        group = root.setdefault(key, {})
        cell = group.setdefault(name, {"ok": 0, "fail": 0})
        cell.setdefault("ok", 0)
        cell.setdefault("fail", 0)
        return cell

    def rate(self, kind: str, key: str, name: str) -> Rate:
        cell = self._bucket(kind, key, name)
        return Rate(ok=int(cell.get("ok") or 0), fail=int(cell.get("fail") or 0))

    def record(self, kind: str, key: str, name: str, *, ok: bool, extra: dict[str, Any] | None = None) -> None:
        with _LOCK:
            self.load()
            cell = self._bucket(kind, key, name)
            cell["ok" if ok else "fail"] = int(cell.get("ok" if ok else "fail") or 0) + 1
            rec = {
                "at": datetime.now(timezone.utc).isoformat(),
                "kind": kind,
                "key": key,
                "name": name,
                "ok": ok,
                **(extra or {}),
            }
            recent = list(self._data.get("recent") or [])
            recent.append(rec)
            self._data["recent"] = recent[-80:]
            self.save()

    def snapshot(self) -> dict[str, Any]:
        self.load()
        generators: dict[str, dict[str, Any]] = {}
        for dtype, cells in (self._data.get("generators") or {}).items():
            generators[dtype] = {}
            for name, cell in (cells or {}).items():
                r = Rate(ok=int(cell.get("ok") or 0), fail=int(cell.get("fail") or 0))
                generators[dtype][name] = {"ok": r.ok, "fail": r.fail, "n": r.n, "rate": round(r.rate, 3)}
        strategies: dict[str, dict[str, Any]] = {}
        for key, cells in (self._data.get("strategies") or {}).items():
            strategies[key] = {}
            for name, cell in (cells or {}).items():
                r = Rate(ok=int(cell.get("ok") or 0), fail=int(cell.get("fail") or 0))
                strategies[key][name] = {"ok": r.ok, "fail": r.fail, "n": r.n, "rate": round(r.rate, 3)}
        return {
            "updated_at": self._data.get("updated_at"),
            "generators": generators,
            "strategies": strategies,
            "recent": list(self._data.get("recent") or [])[-20:],
            "policy": {
                "min_samples_to_adapt": MIN_SAMPLES_TO_ADAPT,
                "default_strategies": DEFAULT_STRATEGIES,
            },
        }


def choose_generator(
    diagram_type: str,
    *,
    settings=None,
    memory: AdaptationMemory | None = None,
) -> tuple[str, str]:
    """Pick lora / spec-builder / llm from empirical win rates."""
    settings = settings or get_settings()
    memory = memory or AdaptationMemory()
    dtype = (diagram_type or "class").lower()
    lora_ok = bool(settings.use_finetuned_code) and dtype in {
        "class",
        "object",
        "component",
        "package",
        "flowchart",
        "sequence",
        "usecase",
        "state",
        "deployment",
    }
    lora = memory.rate("generators", dtype, "lora")
    spec = memory.rate("generators", dtype, "spec-builder")

    # Component/package stay grounded until LoRA has a proven win rate on that type.
    if dtype in {"component", "package"} and lora.n < 8:
        return (
            "spec-builder",
            f"default: grounded {dtype} builder (LoRA n={lora.n} < 8 proven samples)",
        )

    spec_is_better = (
        lora_ok
        and lora.n >= MIN_SAMPLES_TO_ADAPT
        and spec.n >= 2
        and spec.rate > lora.rate + 0.08
    )
    lora_weak = lora_ok and lora.n >= 5 and lora.rate < 0.40
    if spec_is_better or lora_weak:
        # Occasional explore so LoRA can recover if it improves.
        if lora_ok and (lora.n + spec.n) % 4 == 0:
            return "lora", f"explore: retry LoRA on {dtype} despite lower rate {lora.rate:.2f}"
        why = (
            f"spec-builder {spec.rate:.2f} (n={spec.n}) > LoRA {lora.rate:.2f} (n={lora.n})"
            if spec_is_better
            else f"LoRA weak on {dtype} ({lora.rate:.2f}, n={lora.n})"
        )
        return "spec-builder", f"adapted: {why}"
    if lora_ok:
        return "lora", f"default: LoRA-first for {dtype} (rate {lora.rate:.2f}, n={lora.n})"
    if settings.mock_providers:
        return "llm", "default: mock provider then spec-builder"
    return "llm", "default: base LLM then spec-builder"


def choose_strategies(
    diagram_type: str,
    category: str,
    *,
    tried: list[str] | None = None,
    memory: AdaptationMemory | None = None,
) -> list[str]:
    """Return unused strategies, empirically successful ones first."""
    memory = memory or AdaptationMemory()
    dtype = (diagram_type or "class").lower()
    cat = (category or "syntax").strip() or "syntax"
    defaults = list(DEFAULT_STRATEGIES.get(cat, ["spec_rebuild", "sanitize_syntax"]))
    tried_set = {t for t in (tried or []) if t}
    key = f"{dtype}|{cat}"

    def sort_key(name: str) -> tuple[float, int]:
        r = memory.rate("strategies", key, name)
        default_idx = defaults.index(name) if name in defaults else 50
        # Enough evidence → rank by win rate; otherwise keep thesis default order.
        if r.n >= MIN_SAMPLES_TO_ADAPT:
            return (-r.rate, default_idx)
        return (0.0, default_idx)

    ordered = sorted(defaults, key=sort_key)
    return [s for s in ordered if s not in tried_set]


def record_generator(diagram_type: str, generator: str, *, ok: bool, memory: AdaptationMemory | None = None) -> None:
    mem = memory or AdaptationMemory()
    mem.record("generators", (diagram_type or "class").lower(), generator, ok=ok, extra={"diagram_type": diagram_type})


def record_strategy(
    diagram_type: str,
    category: str,
    strategy: str,
    *,
    ok: bool,
    memory: AdaptationMemory | None = None,
) -> None:
    mem = memory or AdaptationMemory()
    key = f"{(diagram_type or 'class').lower()}|{(category or 'syntax')}"
    mem.record(
        "strategies",
        key,
        strategy,
        ok=ok,
        extra={"diagram_type": diagram_type, "category": category},
    )


def write_adaptation_sidecar(artifact_dir: Path, session: AdaptationSession) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / "adaptation.json"
    path.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")
    return path
