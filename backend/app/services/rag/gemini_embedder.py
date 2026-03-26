from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.config import settings


class GeminiEmbedder:
    def __init__(
        self,
        api_key: str | None = None,
        embedding_model: str | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self.api_key = api_key or settings.gemini_api_key
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

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.embedding_model}:embedContent"
            r = await client.post(url, params=params, json=payload)
            if r.status_code == 429:
                await asyncio.sleep(2)
                r = await client.post(url, params=params, json=payload)
            if r.status_code == 429:
                raise RuntimeError("Gemini API rate limit exceeded. Please wait a moment and try again.")
            if r.status_code >= 400:
                raise RuntimeError(f"Gemini embedContent failed ({r.status_code}): {r.text}")
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
        self.api_key = api_key or settings.gemini_api_key
        model = chat_model or settings.gemini_chat_model
        self.chat_model = model.removeprefix("models/")
        self.timeout_s = timeout_s

    async def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is missing")

        params = {"key": self.api_key}
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            for model in dict.fromkeys([self.chat_model, "gemini-2.5-flash"]):
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                r = await client.post(url, params=params, json=payload)
                if r.status_code == 429:
                    await asyncio.sleep(2)
                    r = await client.post(url, params=params, json=payload)
                if r.status_code != 429:
                    break
            if r.status_code == 429:
                raise RuntimeError("Gemini API rate limit exceeded. Please wait a moment and try again.")
            r.raise_for_status()
            data = r.json()

        candidates = (data or {}).get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini generateContent returned no candidates")

        content = (candidates[0] or {}).get("content") or {}
        parts = content.get("parts") or []
        text_parts = [p.get("text", "") for p in parts if isinstance(p, dict)]
        out = "".join(text_parts).strip()
        if not out:
            raise RuntimeError("Gemini generateContent returned empty text")
        return out

