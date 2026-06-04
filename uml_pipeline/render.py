from __future__ import annotations

import hashlib
import subprocess
import urllib.request
from pathlib import Path

PLANTUML_JAR_URL = "https://github.com/plantuml/plantuml/releases/download/v1.2024.7/plantuml-1.2024.7.jar"


def ensure_plantuml_jar(jar_path: Path) -> Path:
    jar_path.parent.mkdir(parents=True, exist_ok=True)
    if jar_path.is_file():
        return jar_path
    print(f"Downloading PlantUML jar to {jar_path} ...")
    urllib.request.urlretrieve(PLANTUML_JAR_URL, jar_path)
    return jar_path


def extract_plantuml_block(text: str) -> str:
    text = text.strip()
    if "@startuml" in text.lower():
        start = text.lower().index("@startuml")
        end = text.lower().rfind("@enduml")
        if end != -1:
            return text[start : end + len("@enduml")]
    return f"@startuml\n{text}\n@enduml"


def render_plantuml(
    uml_code: str,
    out_dir: Path,
    jar_path: Path,
    fmt: str = "png",
) -> tuple[Path | None, str | None]:
    """Render PlantUML to image. Returns (image_path, error_message)."""
    ensure_plantuml_jar(jar_path)
    code = extract_plantuml_block(uml_code)
    digest = hashlib.sha256(code.encode()).hexdigest()[:16]
    puml_file = out_dir / f"{digest}.puml"
    out_dir.mkdir(parents=True, exist_ok=True)
    puml_file.write_text(code, encoding="utf-8")

    cmd = [
        "java",
        "-jar",
        str(jar_path),
        f"-t{fmt}",
        str(puml_file),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return None, "PlantUML render timeout"
    except FileNotFoundError:
        return None, "Java not found; install JDK to render diagrams"

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "PlantUML failed").strip()
        return None, err[:500]

    img = puml_file.with_suffix(f".{fmt}")
    if img.is_file():
        return img, None
    return None, "Output image not produced"
