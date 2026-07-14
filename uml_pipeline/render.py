from __future__ import annotations

import hashlib
import os
import string
import subprocess
import urllib.error
import urllib.request
import zlib
from pathlib import Path

PLANTUML_JAR_URL = "https://github.com/plantuml/plantuml/releases/download/v1.2024.7/plantuml-1.2024.7.jar"
DEFAULT_PLANTUML_SERVER = "https://www.plantuml.com/plantuml"


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


def java_runtime_ok() -> bool:
    """True only if a real JDK/JRE can execute (Apple's stub returns false)."""
    try:
        result = subprocess.run(["java", "-version"], capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    combined = (result.stderr or "") + (result.stdout or "")
    if "Unable to locate a Java Runtime" in combined:
        return False
    return result.returncode == 0 or "version" in combined.lower()


def _plantuml_encode(text: str) -> str:
    compressed = zlib.compress(text.encode("utf-8"))[2:-4]
    alphabet = string.digits + string.ascii_uppercase + string.ascii_lowercase + "-_"
    out: list[str] = []
    for i in range(0, len(compressed), 3):
        b1 = compressed[i]
        b2 = compressed[i + 1] if i + 1 < len(compressed) else 0
        b3 = compressed[i + 2] if i + 2 < len(compressed) else 0
        n = (b1 << 16) + (b2 << 8) + b3
        out.append(alphabet[(n >> 18) & 63])
        out.append(alphabet[(n >> 12) & 63])
        out.append(alphabet[(n >> 6) & 63])
        out.append(alphabet[n & 63])
    return "".join(out)


def render_plantuml_remote(code: str, out_path: Path, fmt: str = "png") -> tuple[Path | None, str | None]:
    """Render via PlantUML HTTP server (used when local Java is unavailable)."""
    allow = os.getenv("PLANTUML_REMOTE", "true").lower() in ("1", "true", "yes")
    if not allow:
        return None, "Remote PlantUML disabled (set PLANTUML_REMOTE=true)"

    base = os.getenv("PLANTUML_SERVER_URL", DEFAULT_PLANTUML_SERVER).rstrip("/")
    if fmt not in ("png", "svg"):
        fmt = "png"
    url = f"{base}/{fmt}/{_plantuml_encode(code)}"
    req = urllib.request.Request(url, headers={"User-Agent": "uml-generation-pipeline/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        return None, f"PlantUML server HTTP {exc.code}"
    except Exception as exc:
        return None, f"PlantUML server error: {exc}"

    if not data or (fmt == "png" and data[:8] != b"\x89PNG\r\n\x1a\n"):
        # PlantUML returns an error image sometimes; still accept non-empty PNG
        if not data:
            return None, "PlantUML server returned empty body"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return out_path, None


def render_plantuml(
    uml_code: str,
    out_dir: Path,
    jar_path: Path,
    fmt: str = "png",
) -> tuple[Path | None, str | None]:
    """Render PlantUML to image. Local Java first, then remote server fallback."""
    code = extract_plantuml_block(uml_code)
    digest = hashlib.sha256(code.encode()).hexdigest()[:16]
    out_dir.mkdir(parents=True, exist_ok=True)
    puml_file = out_dir / f"{digest}.puml"
    puml_file.write_text(code, encoding="utf-8")
    img_path = puml_file.with_suffix(f".{fmt}")

    local_err: str | None = None
    if java_runtime_ok():
        ensure_plantuml_jar(jar_path)
        cmd = ["java", "-jar", str(jar_path), f"-t{fmt}", str(puml_file)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            local_err = "PlantUML render timeout"
        except FileNotFoundError:
            local_err = "Java not found; install JDK to render diagrams"
        else:
            if result.returncode == 0 and img_path.is_file():
                return img_path, None
            local_err = (result.stderr or result.stdout or "PlantUML failed").strip()[:500]
    else:
        local_err = "No usable Java Runtime (PlantUML jar needs a JDK/JRE)"

    remote_img, remote_err = render_plantuml_remote(code, img_path, fmt=fmt)
    if remote_img is not None:
        return remote_img, None

    return None, f"{local_err}; remote fallback: {remote_err}"
