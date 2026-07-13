"""Mock provider for offline thesis demos."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


def _slug(text: str, n: int = 4) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9]+", text)
    uniq: list[str] = []
    for w in words:
        title = w[:1].upper() + w[1:]
        if title not in uniq and len(title) > 2:
            uniq.append(title)
        if len(uniq) >= n:
            break
    while len(uniq) < n:
        uniq.append(f"Entity{len(uniq)+1}")
    return uniq


class MockProvider:
    name = "mock"

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        lower = (system + "\n" + user).lower()
        if "repair" in lower or "broken plantuml" in lower:
            return self._repair(user)
        if "plantuml" in lower or "@startuml" in lower or "uml expert" in lower:
            return self._plantuml(user, lower)
        return self._spec(user)

    def vision_score(self, image_path: Path, prompt: str) -> int:
        # Deterministic 3–5 based on image bytes
        data = image_path.read_bytes() if image_path.is_file() else b"0"
        h = int(hashlib.sha256(data + prompt.encode()).hexdigest(), 16)
        return 3 + (h % 3)

    def _spec(self, user: str) -> str:
        entities = _slug(user)
        return (
            f"## Technical Specification\n"
            f"### Entities\n"
            + "\n".join(f"- {e}: id, name, status" for e in entities)
            + "\n### Relationships\n"
            f"- {entities[0]} associates with {entities[1]}\n"
            f"- {entities[0]} composition of {entities[2]}\n"
            f"- {entities[3]} depends on {entities[1]}\n"
            "### Modules / Packages\n"
            "- core: domain entities\n"
            "- api: interfaces and controllers\n"
            "- infra: persistence adapters\n"
        )

    def _plantuml(self, user: str, lower: str) -> str:
        entities = _slug(user)
        a, b, c, d = entities[:4]
        if "object" in lower:
            return (
                "@startuml\n"
                f"object {a.lower()}_1:{a} {{\n  name = \"demo\"\n}}\n"
                f"object {b.lower()}_1:{b} {{\n  status = \"active\"\n}}\n"
                f"{a.lower()}_1 --> {b.lower()}_1 : uses\n"
                "@enduml"
            )
        if "component" in lower:
            return (
                "@startuml\n"
                f"[{a}] as {a}\n"
                f"[{b}] as {b}\n"
                f"() \"I{c}\" as I{c}\n"
                f"{a} --> I{c}\n"
                f"{b} ..> I{c} : use\n"
                "@enduml"
            )
        if "package" in lower:
            return (
                "@startuml\n"
                "package core {\n"
                f"  package domain {{\n    class {a}\n    class {b}\n  }}\n"
                "}\n"
                "package api {\n"
                f"  class {c}\n"
                "}\n"
                "package infra {\n"
                f"  class {d}\n"
                "}\n"
                "api ..> core : uses\n"
                "infra ..> core : persists\n"
                "@enduml"
            )
        return (
            "@startuml\n"
            f"class {a} {{\n  +id: int\n  +name: string\n}}\n"
            f"class {b} {{\n  +status: string\n}}\n"
            f"class {c} {{\n  +value: float\n}}\n"
            f"{a} \"1\" --> \"*\" {b} : has\n"
            f"{a} *-- {c}\n"
            "@enduml"
        )

    def _repair(self, user: str) -> str:
        # Prefer regenerating a safe package diagram if package context
        if "package" in user.lower():
            return (
                "@startuml\n"
                "package core {\n  class DomainService\n}\n"
                "package api {\n  class ApiController\n}\n"
                "api ..> core : uses\n"
                "@enduml"
            )
        m = re.search(r"@startuml.*?@enduml", user, flags=re.I | re.S)
        if m:
            code = m.group(0)
            # Strip self-deps like foo ..> foo
            code = re.sub(r"(?m)^\s*(\w+)\s+\.\.>\s*\1\s*.*$", "", code)
            return code
        return (
            "@startuml\nclass FixedEntity {\n  +id: int\n}\n@enduml"
        )
