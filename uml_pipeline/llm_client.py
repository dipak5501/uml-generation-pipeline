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
        if not text or not score_response_parsed(text):
            raise RuntimeError(
                f"Vision model returned unparseable score output "
                f"({len(text)} chars): {text[:240]!r}"
            )
        score, explanation = parse_score_response(text)
        return VisionAssessment(score=score, explanation=explanation, raw_output=text)

    def _ollama_vision(self, image_path: Path, prompt: str) -> VisionAssessment:
        b64 = _image_b64(image_path)
        payload = {
            "model": self.model,
            "stream": False,
            # Unload after scoring so the next large VLM can fit in VRAM.
            "keep_alive": "0",
            # Slight temp + longer budget: reduces rubber-stamp SCORE:5 under greedy.
            "options": {"temperature": 0.2, "num_predict": 384},
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
        if not text or not score_response_parsed(text):
            raise RuntimeError(
                f"Ollama vision model {self.model!r} returned unparseable score "
                f"output ({len(text)} chars): {text[:240]!r}"
            )
        score, explanation = parse_score_response(text)
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


_CRITERION_LABEL = r"(?:SEMANTIC|STRUCTURAL|SYNTACTIC|COHERENCE|OVERALL|RATING|FINAL)"
_SCORE_LABEL = r"(?:SCORE|OVERALL(?:\s+SCORE)?|FINAL(?:\s+SCORE)?|RATING)"
_PLACEHOLDER_RANGE = r"[<\[]\s*0\s*[-–—]\s*6\s*[>\]]"


def parse_score_response(text: str) -> tuple[int, str | None]:
    """Extract overall SCORE (0–6) and optional EXPLANATION from a VLM reply.

    Prefers an explicit ``SCORE:`` / ``OVERALL:`` line over criterion labels
    (``SEMANTIC:``, ``STRUCTURAL:``, …) so multi-axis replies do not leak the
    first criterion into the composite score. Also accepts markdown bold,
    ``5/6`` forms, and ignores instructional placeholders like ``<0-6>``.
    Unparseable text returns score ``0`` (callers should treat empty raw
    output as unavailable separately).
    """
    score: int | None = None
    explanation: str | None = None
    scrubbed = re.sub(r"\*+", "", text or "")

    # Drop instructional placeholders such as SCORE: <0-6> or SEMANTIC: [0-6].
    scrubbed_for_score = re.sub(
        rf"(?im)\b(?:SCORE|SEMANTIC|STRUCTURAL|SYNTACTIC|COHERENCE|OVERALL|RATING|FINAL)\s*[:\-]\s*{_PLACEHOLDER_RANGE}",
        "",
        scrubbed,
    )

    # 1) Prefer overall SCORE / OVERALL / RATING / FINAL (last wins if repeated).
    overall_hits = list(
        re.finditer(
            rf"(?im)\b{_SCORE_LABEL}\s*[:\-]\s*([0-6])(?:\s*/\s*6)?\b",
            scrubbed_for_score,
        )
    )
    # Exclude criterion-only lines that matched via OVERALL SCORE already handled;
    # if label was SEMANTIC-only it won't match _SCORE_LABEL.
    if overall_hits:
        score = int(overall_hits[-1].group(1))

    # 2) Average criterion lines when present and no overall SCORE.
    if score is None:
        crit_vals = [
            int(m.group(1))
            for m in re.finditer(
                rf"(?im)\b(?:SEMANTIC|STRUCTURAL|SYNTACTIC|COHERENCE)\s*[:\-]\s*([0-6])\b",
                scrubbed_for_score,
            )
        ]
        if len(crit_vals) >= 2:
            score = int(round(sum(crit_vals) / len(crit_vals)))
            score = max(0, min(6, score))
        elif len(crit_vals) == 1:
            # Legacy single-label SEMANTIC: N (or one criterion only).
            score = crit_vals[0]

    # 3) Forms like "score 5/6" or "rated 4 out of 6".
    if score is None:
        m_frac = re.search(
            r"(?im)\b(?:score|rated|rating)\s*(?:is\s*|of\s*|:\s*)?([0-6])\s*(?:/\s*6|out\s+of\s+6)\b",
            scrubbed_for_score,
        )
        if m_frac:
            score = int(m_frac.group(1))

    m_exp = re.search(
        rf"(?is)^\s*EXPLANATION\s*[:\-]\s*(.+?)(?=\n\s*(?:{_SCORE_LABEL}|{_CRITERION_LABEL}|EXPLANATION)\s*[:\-]|\Z)",
        scrubbed,
    )
    if m_exp:
        explanation = " ".join(m_exp.group(1).strip().split())
        if not explanation:
            explanation = None

    if score is None:
        # Last-resort: first bare 0–6 digit not inside a leftover placeholder.
        fallback_text = re.sub(_PLACEHOLDER_RANGE, " ", scrubbed_for_score)
        # Strip criterion labels' digits so "SEMANTIC: 5" leftovers don't dominate
        # when they were already considered above; still allow prose "scores 4".
        for token in re.split(r"[^\d]+", fallback_text):
            if token.isdigit():
                val = int(token)
                if 0 <= val <= 6:
                    score = val
                    break
    if score is None:
        score = 0

    if explanation is None:
        cleaned = re.sub(
            rf"(?im)^\s*(?:{_SCORE_LABEL}|{_CRITERION_LABEL})\s*[:\-]\s*[0-6](?:\s*/\s*6)?\s*$",
            "",
            scrubbed_for_score,
        ).strip()
        cleaned = re.sub(r"(?im)^\s*EXPLANATION\s*[:\-]\s*", "", cleaned).strip()
        cleaned = " ".join(cleaned.split())
        if cleaned and cleaned != str(score):
            explanation = cleaned[:800] or None

    return score, explanation


def score_response_parsed(text: str) -> bool:
    """True when the reply contains an explicit overall or criterion score label."""
    scrubbed = re.sub(r"\*+", "", text or "")
    if re.search(rf"(?im)\b{_SCORE_LABEL}\s*[:\-]\s*[0-6]\b", scrubbed):
        return True
    if re.search(rf"(?im)\bSEMANTIC\s*[:\-]\s*[0-6]\b", scrubbed):
        return True
    if re.search(
        rf"(?im)\b(?:SEMANTIC|STRUCTURAL|SYNTACTIC|COHERENCE)\s*[:\-]\s*[0-6]\b",
        scrubbed,
    ):
        return True
    if re.search(
        r"(?im)\b(?:score|rated|rating)\s*(?:is\s*|of\s*|:\s*)?[0-6]\s*(?:/\s*6|out\s+of\s+6)\b",
        scrubbed,
    ):
        return True
    return False


def _parse_score(text: str) -> int:
    score, _ = parse_score_response(text)
    return score


def provider_from_env() -> Provider:
    return "ollama" if os.getenv("USE_OLLAMA", "").lower() in ("1", "true", "yes") else "openai"
