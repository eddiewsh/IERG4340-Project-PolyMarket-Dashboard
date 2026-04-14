from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx

from app.core.config import settings

_IS_VERCEL = bool(getattr(settings, "is_serverless", False))
_GEMINI_MAX_CONCURRENCY = 1 if _IS_VERCEL else 2
_GEMINI_SEMAPHORE = asyncio.Semaphore(_GEMINI_MAX_CONCURRENCY)

_GEMINI_MIN_INTERVAL_S = 0.9 if _IS_VERCEL else 0.0
_GEMINI_RATE_LOCK = asyncio.Lock()
_GEMINI_LAST_REQUEST_AT = 0.0

_GEMINI_CACHE_TTL_S = 15.0 if _IS_VERCEL else 0.0
_GEMINI_CACHE_MAX = 64
_GEMINI_CACHE: dict[str, tuple[float, str]] = {}
_GEMINI_CACHE_LOCK = asyncio.Lock()


async def _rate_limit_wait() -> None:
    global _GEMINI_LAST_REQUEST_AT
    if _GEMINI_MIN_INTERVAL_S <= 0:
        return
    async with _GEMINI_RATE_LOCK:
        now = time.monotonic()
        wait_s = (_GEMINI_LAST_REQUEST_AT + _GEMINI_MIN_INTERVAL_S) - now
        if wait_s > 0:
            await asyncio.sleep(wait_s)
        _GEMINI_LAST_REQUEST_AT = time.monotonic()


def _retry_attempts() -> int:
    return 2 if _IS_VERCEL else 5


def _cache_key(kind: str, model: str, use_grounding: bool, prompt: str) -> str:
    p = (prompt or "").strip()
    if len(p) > 2000:
        p = p[:2000]
    return f"{kind}|{model}|{int(bool(use_grounding))}|{p}"


async def _cache_get(key: str) -> str | None:
    if _GEMINI_CACHE_TTL_S <= 0:
        return None
    now = time.monotonic()
    async with _GEMINI_CACHE_LOCK:
        hit = _GEMINI_CACHE.get(key)
        if not hit:
            return None
        exp, val = hit
        if exp < now:
            _GEMINI_CACHE.pop(key, None)
            return None
        return val


async def _cache_set(key: str, val: str) -> None:
    if _GEMINI_CACHE_TTL_S <= 0:
        return
    now = time.monotonic()
    async with _GEMINI_CACHE_LOCK:
        if len(_GEMINI_CACHE) >= _GEMINI_CACHE_MAX:
            oldest_k = min(_GEMINI_CACHE.items(), key=lambda kv: kv[1][0])[0]
            _GEMINI_CACHE.pop(oldest_k, None)
        _GEMINI_CACHE[key] = (now + _GEMINI_CACHE_TTL_S, val)


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


def _norm_model_name(name: str) -> str:
    return (name or "").strip().removeprefix("models/")


def _parse_fallback_csv(csv: str) -> list[str]:
    out: list[str] = []
    for part in (csv or "").split(","):
        m = _norm_model_name(part)
        if m:
            out.append(m)
    return out


def _unique_model_chain(primary: str, fallbacks: list[str]) -> list[str]:
    seen: set[str] = set()
    chain: list[str] = []
    for m in [_norm_model_name(primary)] + fallbacks:
        if not m or m in seen:
            continue
        seen.add(m)
        chain.append(m)
    return chain


def _should_try_fallback_chat(status: int, body: str) -> bool:
    if status in (401, 403, 400):
        return False
    if status == 503:
        return True
    blob = (body or "").lower()
    if "high demand" in blob:
        return True
    try:
        err = (json.loads(body).get("error") or {}) if body else {}
        if err.get("status") == "UNAVAILABLE":
            return True
        if "high demand" in str(err.get("message", "")).lower():
            return True
    except Exception:
        pass
    return False


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
                for attempt in range(_retry_attempts()):
                    await _rate_limit_wait()
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
        self.chat_model = _norm_model_name(model)
        fb = _parse_fallback_csv(settings.gemini_chat_model_fallbacks)
        self._model_chain = _unique_model_chain(self.chat_model, fb)
        self.timeout_s = timeout_s

    async def _post_generate_content(self, client: httpx.AsyncClient, payload: dict[str, Any]) -> dict[str, Any]:
        params = {"key": self.api_key}
        last_rate_limited = False
        last_detail = ""
        for model in self._model_chain:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            r: httpx.Response | None = None
            for attempt in range(_retry_attempts()):
                await _rate_limit_wait()
                r = await client.post(url, params=params, json=payload)
                if r.status_code != 429:
                    break
                await asyncio.sleep(min(12.0, 1.5 * (2**attempt)))
            if r is None:
                continue
            if r.status_code == 429:
                last_rate_limited = True
                last_detail = r.text
                continue
            if r.status_code == 200:
                return r.json()
            if _should_try_fallback_chat(r.status_code, r.text):
                last_detail = r.text
                continue
            r.raise_for_status()
        if last_rate_limited:
            raise RuntimeError("Gemini API rate limit exceeded. Please wait a moment and try again.")
        raise RuntimeError(
            f"Gemini generateContent failed for all models in chain {self._model_chain!r}: {last_detail}"
        )

    async def generate(self, prompt: str, use_grounding: bool = False) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is missing")

        cache_key = _cache_key("gen", self.chat_model, use_grounding, prompt)
        cached = await _cache_get(cache_key)
        if cached is not None:
            return cached

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
                data = await self._post_generate_content(client, payload)

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
        await _cache_set(cache_key, out)
        return out

    async def generate_with_sources(self, prompt: str) -> tuple[str, list[dict[str, str]]]:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is missing")

        cache_key = _cache_key("src", self.chat_model, True, prompt)
        cached = await _cache_get(cache_key)
        if cached is not None:
            return cached, []

        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
            "tools": [{"google_search": {}}],
        }

        async with _GEMINI_SEMAPHORE:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                data = await self._post_generate_content(client, payload)

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

        if text:
            await _cache_set(cache_key, text)
        return text, sources

