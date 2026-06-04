from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Literal

import httpx

Provider = Literal["openai", "ollama"]


class LLMClient:
    def __init__(
        self,
        model: str,
        provider: Provider = "openai",
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        self.model = model
        self.provider = provider
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        if self.provider == "ollama":
            return self._ollama_chat(system, user, temperature)
        return self._openai_chat(system, user, temperature)

    def vision_score(self, image_path: Path, prompt: str) -> int:
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

    def _openai_vision(self, image_path: Path, prompt: str) -> int:
        b64 = base64.b64encode(image_path.read_bytes()).decode()
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
        return _parse_score(text)

    def _ollama_vision(self, image_path: Path, prompt: str) -> int:
        b64 = base64.b64encode(image_path.read_bytes()).decode()
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [b64],
                }
            ],
        }
        with httpx.Client(timeout=600) as client:
            r = client.post(f"{self.ollama_url}/api/chat", json=payload)
            r.raise_for_status()
            text = r.json()["message"]["content"].strip()
        return _parse_score(text)


def _parse_score(text: str) -> int:
    for token in text.replace(".", " ").split():
        if token.isdigit():
            val = int(token)
            if 0 <= val <= 6:
                return val
    return 0


def provider_from_env() -> Provider:
    return "ollama" if os.getenv("USE_OLLAMA", "").lower() in ("1", "true", "yes") else "openai"
