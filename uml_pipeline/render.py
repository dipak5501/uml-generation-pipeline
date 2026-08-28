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

    for jvm_home in (
        "/usr/lib/jvm/java-21-openjdk-amd64",
        "/usr/lib/jvm/java-17-openjdk-amd64",
        "/usr/lib/jvm/java-21-openjdk",
    ):
        candidates.append(Path(jvm_home) / "bin" / "java")

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


def _validate_plantuml_server_url(base: str) -> str | None:
    """Allow only http(s) PlantUML endpoints (blocks file:// and other schemes)."""
    base = (base or "").strip().rstrip("/")
    if not base.startswith(("https://", "http://")):
        return None
    # Reject obvious SSRF-ish userinfo tricks and local file schemes already blocked.
    if "@" in base.split("://", 1)[-1].split("/", 1)[0]:
        return None
    return base


def render_plantuml_remote(code: str, out_path: Path, fmt: str = "png") -> tuple[Path | None, str | None]:
    """Render via PlantUML HTTP server (used when local Java is unavailable)."""
    allow = os.getenv("PLANTUML_REMOTE", "true").lower() in ("1", "true", "yes")
    if not allow:
        return None, "Remote PlantUML disabled (set PLANTUML_REMOTE=true)"

    base = _validate_plantuml_server_url(
        os.getenv("PLANTUML_SERVER_URL", DEFAULT_PLANTUML_SERVER)
    )
    if base is None:
        return None, "Invalid PLANTUML_SERVER_URL (must be http:// or https://)"
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
        if not data:
            return None, "PlantUML server returned empty body"
        return None, "PlantUML server returned a non-PNG body"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    if fmt == "png" and _looks_like_graphviz_error_png(out_path):
        return None, "PlantUML server returned a Graphviz/dot error image"
    return out_path, None


def find_dot_executable() -> str | None:
    """Locate Graphviz ``dot`` if installed."""
    candidates: list[Path] = []
    for key in ("GRAPHVIZ_DOT", "DOT_PATH", "PLANTUML_DOT_PATH"):
        raw = os.getenv(key)
        if raw:
            candidates.append(Path(raw))
    for path in (
        Path("/opt/homebrew/bin/dot"),
        Path("/usr/local/bin/dot"),
        Path("/opt/local/bin/dot"),
        Path(REPO_ROOT / "tools" / "graphviz" / "bin" / "dot"),
        Path.home() / "micromamba" / "envs" / "uml-openmpi" / "bin" / "dot",
        Path.home() / "micromamba" / "envs" / "uml-mpi" / "bin" / "dot",
    ):
        candidates.append(path)
    which = subprocess.run(["/usr/bin/which", "dot"], capture_output=True, text=True)
    if which.returncode == 0 and which.stdout.strip():
        candidates.append(Path(which.stdout.strip()))

    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _looks_like_graphviz_error_png(img_path: Path) -> bool:
    """Detect PlantUML's neon-green Graphviz error page (text is drawn, not embedded)."""
    try:
        data = img_path.read_bytes()
    except OSError:
        return True
    if len(data) < 256 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return True
    text = data.decode("latin1", errors="ignore").lower()
    if "cannot find graphviz" in text or "dot executable does not exist" in text:
        return True
    # Sample neon-green pixels typical of PlantUML's Graphviz error image
    try:
        from PIL import Image

        with Image.open(img_path) as im:
            rgb = im.convert("RGB")
            w, h = rgb.size
            if w * h == 0:
                return True
            step = max(1, (w * h) // 4000)
            pixels = list(rgb.getdata())
            green = sum(
                1
                for i in range(0, len(pixels), step)
                if pixels[i][1] > 200 and pixels[i][0] < 90 and pixels[i][2] < 90
            )
            samples = max(1, (len(pixels) + step - 1) // step)
            if green / samples >= 0.02:
                return True
    except Exception:
        pass
    return False


def _ensure_renderable_layout(code: str, *, has_dot: bool) -> str:
    """When Graphviz is missing, force PlantUML's built-in Smetana layout."""
    from app.services.plantuml_validate import apply_publication_plantuml_style

    code = apply_publication_plantuml_style(code)
    if has_dot:
        return code
    low = code.lower()
    if "pragma layout" in low:
        return code
    marker = "@startuml"
    idx = low.find(marker)
    if idx < 0:
        return f"@startuml\n!pragma layout smetana\n{code}\n@enduml"
    insert_at = idx + len(marker)
    # Keep any @startuml args on the same first line
    nl = code.find("\n", insert_at)
    if nl < 0:
        return code + "\n!pragma layout smetana\n"
    return code[: nl + 1] + "!pragma layout smetana\n" + code[nl + 1 :]


def _plantuml_render_succeeded(result: subprocess.CompletedProcess[str], img_path: Path) -> bool:
    """True when PlantUML wrote a real diagram, not a Graphviz/dot error image."""
    if not img_path.is_file():
        return False
    combined = f"{result.stderr or ''}\n{result.stdout or ''}".lower()
    error_markers = (
        "cannot find graphviz",
        "dot executable does not exist",
        "cannot run program",
        "no such file or directory",
        "error line",
        "syntax error",
        "some diagram description contains errors",
    )
    if any(marker in combined for marker in error_markers):
        # Still allow success when Smetana/ELK rendered a real image despite dot probe noise
        if _looks_like_graphviz_error_png(img_path):
            return False
    if _looks_like_graphviz_error_png(img_path):
        return False
    try:
        data = img_path.read_bytes()
    except OSError:
        return False
    return len(data) >= 256


def _local_plantuml_env(dot: str | None = None) -> dict[str, str]:
    """Drop broken Graphviz paths that make PlantUML embed error text in PNGs."""
    env = dict(os.environ)
    for key in ("GRAPHVIZ_DOT", "DOT_PATH", "PLANTUML_DOT_PATH"):
        path = env.get(key)
        if path and not Path(path).is_file():
            env.pop(key, None)
    if dot:
        env["GRAPHVIZ_DOT"] = dot
    return env


def check_plantuml_syntax(
    uml_code: str,
    jar_path: Path,
    *,
    work_dir: Path | None = None,
) -> tuple[bool, str | None]:
    """Compile-only PlantUML syntax gate (no image).

    Returns (ok, error). If Java/jar is unavailable, returns (False, reason)
    so callers do not treat a missing compiler as success.
    """
    java_exe = find_java_executable()
    if not java_exe:
        return False, "No usable Java Runtime for PlantUML -checkonly"
    try:
        ensure_plantuml_jar(jar_path)
    except Exception as exc:
        return False, f"PlantUML jar unavailable: {exc}"

    dot = find_dot_executable()
    code = _ensure_renderable_layout(extract_plantuml_block(uml_code), has_dot=bool(dot))
    base = work_dir or (REPO_ROOT / "data" / "tmp_syntax")
    base.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(code.encode()).hexdigest()[:16]
    puml_file = base / f"{digest}_check.puml"
    puml_file.write_text(code, encoding="utf-8")
    cmd = [java_exe, "-jar", str(jar_path), "-checkonly", str(puml_file)]
    if dot:
        cmd[3:3] = ["-graphvizdot", dot]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            env=_local_plantuml_env(dot),
        )
    except subprocess.TimeoutExpired:
        return False, "PlantUML syntax check timeout"
    except FileNotFoundError:
        return False, "Java not found for PlantUML syntax check"

    combined = f"{result.stdout or ''}\n{result.stderr or ''}"
    low = combined.lower()
    hard_fail = (
        "syntax error",
        "error line",
        "some diagram description contains errors",
        "syntax error in diagram",
    )
    if any(m in low for m in hard_fail) or result.returncode != 0:
        # Graphviz probe noise is not a syntax failure if no "error line"
        if "dot executable" in low or "cannot find graphviz" in low:
            if not any(m in low for m in ("syntax error", "error line")):
                return True, None
        snippet = combined.strip().splitlines()
        err = " | ".join(snippet[-6:])[:500] or f"PlantUML -checkonly exit {result.returncode}"
        return False, err
    return True, None


def render_plantuml(
    uml_code: str,
    out_dir: Path,
    jar_path: Path,
    fmt: str = "png",
) -> tuple[Path | None, str | None]:
    """Render PlantUML to image.

    Prefer local Java when available (more reliable than the public PlantUML
    HTTP server). Fall back to remote when enabled and local fails/missing.
    """
    dot = find_dot_executable()
    code = _ensure_renderable_layout(extract_plantuml_block(uml_code), has_dot=bool(dot))
    digest = hashlib.sha256(code.encode()).hexdigest()[:16]
    out_dir.mkdir(parents=True, exist_ok=True)
    puml_file = out_dir / f"{digest}.puml"
    puml_file.write_text(code, encoding="utf-8")
    img_path = puml_file.with_suffix(f".{fmt}")

    use_remote = os.getenv("PLANTUML_REMOTE", "true").lower() in ("1", "true", "yes")
    prefer_local = os.getenv("PLANTUML_PREFER_LOCAL", "true").lower() in ("1", "true", "yes")

    local_err: str | None = None
    java_exe = find_java_executable()

    def _try_local() -> Path | None:
        nonlocal local_err
        if not java_exe:
            local_err = "No usable Java Runtime (PlantUML jar needs a JDK/JRE)"
            return None
        ensure_plantuml_jar(jar_path)
        cmd = [java_exe, "-jar", str(jar_path), f"-t{fmt}"]
        if dot:
            cmd.extend(["-graphvizdot", dot])
        cmd.append(str(puml_file))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                env=_local_plantuml_env(dot),
            )
        except subprocess.TimeoutExpired:
            local_err = "PlantUML render timeout"
            return None
        except FileNotFoundError:
            local_err = "Java not found; install JDK to render diagrams"
            return None
        if _plantuml_render_succeeded(result, img_path):
            return img_path
        local_err = (result.stderr or result.stdout or "PlantUML produced an error image").strip()[:500]
        return None

    remote_err: str | None = None

    # Local-first when Java exists (avoids intermittent public-server failures).
    if prefer_local and java_exe:
        local_img = _try_local()
        if local_img is not None:
            return local_img, None
        if use_remote:
            remote_img, remote_err = render_plantuml_remote(code, img_path, fmt=fmt)
            if remote_img is not None:
                return remote_img, None
        return None, f"{local_err}; remote fallback: {remote_err}"

    # Legacy order: remote then local
    if use_remote:
        remote_img, remote_err = render_plantuml_remote(code, img_path, fmt=fmt)
        if remote_img is not None:
            return remote_img, None

    local_img = _try_local()
    if local_img is not None:
        return local_img, None

    if use_remote and remote_err is None:
        remote_img, remote_err = render_plantuml_remote(code, img_path, fmt=fmt)
        if remote_img is not None:
            return remote_img, None

    return None, f"{local_err}; remote fallback: {remote_err}"
