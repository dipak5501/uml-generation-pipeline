from __future__ import annotations

import base64
import io
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

Provider = Literal["openai", "ollama"]


@dataclass(frozen=True)
class VisionAssessment:
    score: int
    explanation: str | None
    raw_output: str


class LLMClient:
    def __init__(
        self,
        model: str,
        provider: Provider = "openai",
        base_url: str | None = None,
        api_key: str | None = None,
        ollama_url: str | None = None,
    ):
        self.model = model
        self.provider = provider
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.ollama_url = (
            ollama_url
            or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ).rstrip("/")

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        if self.provider == "ollama":
            return self._ollama_chat(system, user, temperature)
        return self._openai_chat(system, user, temperature)

    def vision_score(self, image_path: Path, prompt: str) -> int:
        return self.vision_assess(image_path, prompt).score

    def vision_assess(self, image_path: Path, prompt: str) -> VisionAssessment:
        if self.provider == "ollama":
            return self._ollama_vision(image_path, prompt)
        return self._openai_vision(image_path, prompt)

    def _openai_chat(self, system: str, user: str, temperature: float) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        with httpx.Client(timeout=300) as client:
            r = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()

    def _ollama_chat(self, system: str, user: str, temperature: float) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": temperature},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        with httpx.Client(timeout=600) as client:
            r = client.post(f"{self.ollama_url}/api/chat", json=payload)
            r.raise_for_status()
            return r.json()["message"]["content"].strip()

    def _openai_vision(self, image_path: Path, prompt: str) -> VisionAssessment:
        b64 = _image_b64(image_path)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
        }
        with httpx.Client(timeout=300) as client:
            r = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
        score, explanation = _score_from_vlm_text(text)
        return VisionAssessment(score=score, explanation=explanation, raw_output=text)

    def _ollama_vision(self, image_path: Path, prompt: str) -> VisionAssessment:
        b64 = _image_b64(image_path)
        payload = {
            "model": self.model,
            "stream": False,
            # Unload after scoring so the next large VLM can fit in VRAM.
            "keep_alive": "0",
            "options": {"temperature": 0, "num_predict": 256},
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [b64],
                }
            ],
        }
        last_exc: Exception | None = None
        text = ""
        with httpx.Client(timeout=600) as client:
            for attempt in range(2):
                try:
                    r = client.post(f"{self.ollama_url}/api/chat", json=payload)
                    if r.status_code >= 400:
                        detail = _ollama_error_detail(r)
                        # Retry once on generic server errors (load races); architecture
                        # mismatches like unsupported 'mllama' will fail again immediately.
                        if r.status_code >= 500 and attempt == 0 and "architecture" not in detail.lower():
                            time.sleep(2.0)
                            continue
                        raise RuntimeError(f"Ollama model {self.model!r} failed: {detail}")
                    text = (r.json().get("message") or {}).get("content") or ""
                    text = text.strip()
                    break
                except httpx.HTTPStatusError as exc:
                    last_exc = exc
                    detail = _ollama_error_detail(exc.response) if exc.response is not None else str(exc)
                    if (
                        exc.response is not None
                        and exc.response.status_code >= 500
                        and attempt == 0
                        and "architecture" not in detail.lower()
                    ):
                        time.sleep(2.0)
                        continue
                    raise RuntimeError(f"Ollama model {self.model!r} failed: {detail}") from exc
            else:
                if last_exc:
                    raise last_exc
        score, explanation = _score_from_vlm_text(text)
        return VisionAssessment(score=score, explanation=explanation, raw_output=text)


def _ollama_error_detail(response: httpx.Response | None) -> str:
    if response is None:
        return "unknown Ollama error"
    try:
        data = response.json()
        if isinstance(data, dict) and data.get("error"):
            return str(data["error"])
    except Exception:
        pass
    text = (response.text or "").strip()
    return text[:500] if text else f"HTTP {response.status_code}"


def _image_b64(image_path: Path, max_side: int = 1280) -> str:
    """Encode image as PNG base64, downscaling large diagrams for VLM stability."""
    raw = image_path.read_bytes()
    try:
        from PIL import Image

        with Image.open(io.BytesIO(raw)) as img:
            img = img.convert("RGB")
            w, h = img.size
            longest = max(w, h)
            if longest > max_side:
                scale = max_side / float(longest)
                img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            raw = buf.getvalue()
    except Exception:
        pass
    return base64.b64encode(raw).decode()


# Unfilled prompt templates such as "SEMANTIC: <0-6>" must not become score 0.
_SCORE_PLACEHOLDER_RE = re.compile(
    r"<\s*(?:integer\s+)?0\s*[-–to/]+\s*6\s*>|<\s*int(?:eger)?\s*>",
    re.IGNORECASE,
)


def _strip_score_markup(text: str) -> str:
    return (text or "").replace("**", "").replace("__", "").replace("`", "")


def extract_vlm_score(text: str) -> tuple[int | None, str | None]:
    """Parse a VLM reply into (score, explanation).

    Returns ``score=None`` when no real 0–6 value is present (including replies
    that only echo ``<0-6>`` placeholders). Callers that need a numeric default
    should use :func:`parse_score_response`.
    """
    raw = text or ""
    scrubbed = _SCORE_PLACEHOLDER_RE.sub(" ", raw)
    scrubbed = _strip_score_markup(scrubbed)

    score: int | None = None
    explanation: str | None = None

    m_score = re.search(r"(?im)^\s*SCORE\s*[:\-]\s*([0-6])\b", scrubbed)
    if m_score:
        score = int(m_score.group(1))
    if score is None:
        m_sem = re.search(r"(?i)\bSEMANTIC\s*[:\-]\s*([0-6])\b", scrubbed)
        if m_sem:
            score = int(m_sem.group(1))

    m_exp = re.search(
        r"(?is)^\s*EXPLANATION\s*[:\-]\s*(.+?)(?=\n\s*(?:SCORE|EXPLANATION|SEMANTIC)\s*[:\-]|\Z)",
        _strip_score_markup(raw),
    )
    if m_exp:
        explanation = " ".join(m_exp.group(1).strip().split())
        if not explanation:
            explanation = None

    if score is None:
        for token in scrubbed.replace(".", " ").replace("/", " ").split():
            token = token.strip("()[]{},;:")
            if token.isdigit():
                val = int(token)
                if 0 <= val <= 6:
                    score = val
                    break

    if explanation is None:
        cleaned = re.sub(r"(?im)^\s*SCORE\s*[:\-]\s*[0-6]\s*$", "", _strip_score_markup(raw)).strip()
        cleaned = re.sub(r"(?im)^\s*EXPLANATION\s*[:\-]\s*", "", cleaned).strip()
        cleaned = _SCORE_PLACEHOLDER_RE.sub(" ", cleaned)
        cleaned = " ".join(cleaned.split())
        if cleaned and cleaned != str(score):
            explanation = cleaned[:800] or None

    return score, explanation


def parse_score_response(text: str) -> tuple[int, str | None]:
    """Extract SCORE (0–6) and optional EXPLANATION from a VLM reply.

    Unparseable replies (markdown-stripped placeholders with no integer) default
    to 0. Live scorers should use :func:`extract_vlm_score` and treat ``None``
    as unavailable rather than a genuine zero.
    """
    score, explanation = extract_vlm_score(text)
    return (0 if score is None else score), explanation


def _score_from_vlm_text(text: str) -> tuple[int, str | None]:
    """Require a real 0–6 parse so placeholder ``<0-6>`` is not a fake zero."""
    score, explanation = extract_vlm_score(text)
    if score is None:
        snippet = (text or "").strip().replace("\n", " ")[:220]
        raise RuntimeError(
            "VLM score unparseable (markdown/placeholder, no integer 0-6): "
            f"{snippet!r}"
        )
    return score, explanation


def _parse_score(text: str) -> int:
    score, _ = parse_score_response(text)
    return score


def provider_from_env() -> Provider:
    return "ollama" if os.getenv("USE_OLLAMA", "").lower() in ("1", "true", "yes") else "openai"
