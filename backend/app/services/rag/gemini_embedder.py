from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.config import settings

_GEMINI_MAX_CONCURRENCY = 2
_GEMINI_SEMAPHORE = asyncio.Semaphore(_GEMINI_MAX_CONCURRENCY)


def _read_dotenv_value(path: str, key: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                if k.strip() == key:
                    return v.strip().strip("'").strip('"')
    except Exception:
        return ""
    return ""


def _load_gemini_api_key() -> str:
    key = (settings.gemini_api_key or "").strip()
    env_path = str(getattr(getattr(settings, "Config", object()), "env_file", "") or "")
    if env_path:
        from_file = _read_dotenv_value(env_path, "GEMINI_API_KEY")
        if from_file:
            return from_file
    return key


class GeminiEmbedder:
    def __init__(
        self,
        api_key: str | None = None,
        embedding_model: str | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self.api_key = api_key or _load_gemini_api_key()
        model = embedding_model or settings.gemini_embedding_model
        self.embedding_model = model.removeprefix("models/")
        self.timeout_s = timeout_s

    async def embed_text(self, text: str) -> list[float]:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is missing")

        text = (text or "").strip()
        if not text:
            return [0.0] * 768

        params = {"key": self.api_key}
        payload: dict[str, Any] = {
            "content": {"parts": [{"text": text}]},
        }

        async with _GEMINI_SEMAPHORE:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.embedding_model}:embedContent"
                r: httpx.Response | None = None
                for attempt in range(5):
                    r = await client.post(url, params=params, json=payload)
                    if r.status_code != 429:
                        break
                    await asyncio.sleep(min(12.0, 1.5 * (2**attempt)))
                if r is None or r.status_code == 429:
                    raise RuntimeError("Gemini API rate limit exceeded. Please wait a moment and try again.")
                if r.status_code >= 400:
                    key_len = len(self.api_key or "")
                    raise RuntimeError(f"Gemini embedContent failed ({r.status_code}) [key_len={key_len}]: {r.text}")
                data = r.json()
            values = (((data or {}).get("embedding") or {}).get("values")) or []
            if not isinstance(values, list) or not values:
                raise RuntimeError("Gemini embedContent returned empty embedding")
            return [float(v) for v in values]


class GeminiChat:
    def __init__(
        self,
        api_key: str | None = None,
        chat_model: str | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self.api_key = api_key or _load_gemini_api_key()
        model = chat_model or settings.gemini_chat_model
        self.chat_model = model.removeprefix("models/")
        self.timeout_s = timeout_s

    async def generate(self, prompt: str, use_grounding: bool = False) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is missing")

        params = {"key": self.api_key}
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
            },
        }
        if use_grounding:
            payload["tools"] = [{"google_search": {}}]

        async with _GEMINI_SEMAPHORE:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.chat_model}:generateContent"
                r: httpx.Response | None = None
                for attempt in range(5):
                    r = await client.post(url, params=params, json=payload)
                    if r.status_code != 429:
                        break
                    await asyncio.sleep(min(12.0, 1.5 * (2**attempt)))
                if r is None or r.status_code == 429:
                    raise RuntimeError("Gemini API rate limit exceeded. Please wait a moment and try again.")
                r.raise_for_status()
                data = r.json()

        candidates = (data or {}).get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini generateContent returned no candidates")

        candidate = candidates[0] or {}
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        text_parts = [p.get("text", "") for p in parts if isinstance(p, dict)]
        out = "".join(text_parts).strip()
        if not out:
            raise RuntimeError("Gemini generateContent returned empty text")
        return out

    async def generate_with_sources(self, prompt: str) -> tuple[str, list[dict[str, str]]]:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is missing")

        params = {"key": self.api_key}
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
            "tools": [{"google_search": {}}],
        }

        async with _GEMINI_SEMAPHORE:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.chat_model}:generateContent"
                r: httpx.Response | None = None
                for attempt in range(5):
                    r = await client.post(url, params=params, json=payload)
                    if r.status_code != 429:
                        break
                    await asyncio.sleep(min(12.0, 1.5 * (2**attempt)))
                if r is None or r.status_code == 429:
                    raise RuntimeError("Gemini API rate limit exceeded.")
                r.raise_for_status()
                data = r.json()

        candidates = (data or {}).get("candidates") or []
        if not candidates:
            return "", []

        candidate = candidates[0] or {}
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        text_parts = [p.get("text", "") for p in parts if isinstance(p, dict)]
        text = "".join(text_parts).strip()

        sources: list[dict[str, str]] = []
        grounding = candidate.get("groundingMetadata") or {}
        for chunk in grounding.get("groundingChunks", []):
            web = chunk.get("web") or {}
            uri = web.get("uri", "")
            title = web.get("title", "")
            if uri:
                sources.append({"title": title, "url": uri})

        return text, sources

