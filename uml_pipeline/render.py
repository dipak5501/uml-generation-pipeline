from __future__ import annotations

import hashlib
import os
import string
import subprocess
import urllib.error
import urllib.request
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLANTUML_JAR_URL = "https://github.com/plantuml/plantuml/releases/download/v1.2024.7/plantuml-1.2024.7.jar"
DEFAULT_PLANTUML_SERVER = "https://www.plantuml.com/plantuml"


def find_java_executable() -> str | None:
    """Resolve a working java binary: JAVA_HOME, bundled tools/jdk, then PATH."""
    candidates: list[Path] = []
    java_home = os.getenv("JAVA_HOME")
    if java_home:
        candidates.append(Path(java_home) / "bin" / "java")

    tools = REPO_ROOT / "tools"
    for pattern in ("jdk-17.jre/Contents/Home/bin/java", "jdk-17.jdk/Contents/Home/bin/java"):
        candidates.append(tools / pattern)
    for path in sorted(tools.glob("**/bin/java")):
        candidates.append(path)

    candidates.append(Path("java"))

    for candidate in candidates:
        exe = str(candidate)
        try:
            result = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=10)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
        combined = (result.stderr or "") + (result.stdout or "")
        if "Unable to locate a Java Runtime" in combined:
            continue
        if result.returncode == 0 or "version" in combined.lower():
            return exe
    return None


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
    return find_java_executable() is not None


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


def _plantuml_render_succeeded(result: subprocess.CompletedProcess[str], img_path: Path) -> bool:
    """True when PlantUML wrote a real diagram, not a Graphviz/dot error image."""
    if result.returncode != 0 or not img_path.is_file():
        return False
    combined = f"{result.stderr or ''}\n{result.stdout or ''}".lower()
    error_markers = (
        "cannot find graphviz",
        "dot executable does not exist",
        "error line",
        "syntax error",
        "some diagram description contains errors",
    )
    if any(marker in combined for marker in error_markers):
        return False
    try:
        data = img_path.read_bytes()
    except OSError:
        return False
    if len(data) < 256:
        return False
    text = data.decode("latin1", errors="ignore").lower()
    return "cannot find graphviz" not in text and "dot executable does not exist" not in text


def _local_plantuml_env() -> dict[str, str]:
    """Drop broken Graphviz paths that make PlantUML embed error text in PNGs."""
    env = dict(os.environ)
    for key in ("GRAPHVIZ_DOT", "DOT_PATH", "PLANTUML_DOT_PATH"):
        path = env.get(key)
        if path and not Path(path).is_file():
            env.pop(key, None)
    return env


def render_plantuml(
    uml_code: str,
    out_dir: Path,
    jar_path: Path,
    fmt: str = "png",
) -> tuple[Path | None, str | None]:
    """Render PlantUML to image. Remote server first when enabled, else local Java."""
    code = extract_plantuml_block(uml_code)
    digest = hashlib.sha256(code.encode()).hexdigest()[:16]
    out_dir.mkdir(parents=True, exist_ok=True)
    puml_file = out_dir / f"{digest}.puml"
    puml_file.write_text(code, encoding="utf-8")
    img_path = puml_file.with_suffix(f".{fmt}")

    use_remote = os.getenv("PLANTUML_REMOTE", "true").lower() in ("1", "true", "yes")
    remote_err: str | None = None
    if use_remote:
        remote_img, remote_err = render_plantuml_remote(code, img_path, fmt=fmt)
        if remote_img is not None:
            return remote_img, None

    local_err: str | None = None
    java_exe = find_java_executable()
    if java_exe:
        ensure_plantuml_jar(jar_path)
        cmd = [java_exe, "-jar", str(jar_path), f"-t{fmt}", str(puml_file)]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                env=_local_plantuml_env(),
            )
        except subprocess.TimeoutExpired:
            local_err = "PlantUML render timeout"
        except FileNotFoundError:
            local_err = "Java not found; install JDK to render diagrams"
        else:
            if _plantuml_render_succeeded(result, img_path):
                return img_path, None
            local_err = (result.stderr or result.stdout or "PlantUML produced an error image").strip()[:500]
    else:
        local_err = "No usable Java Runtime (PlantUML jar needs a JDK/JRE)"

    if not use_remote:
        remote_img, remote_err = render_plantuml_remote(code, img_path, fmt=fmt)
        if remote_img is not None:
            return remote_img, None

    return None, f"{local_err}; remote fallback: {remote_err}"
