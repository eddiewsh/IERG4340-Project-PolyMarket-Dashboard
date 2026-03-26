from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.core.config import settings


@dataclass(frozen=True)
class RagChunk:
    source: str
    title: str
    content: str
    url: str | None = None
    source_id: str | None = None
    metadata: dict[str, Any] | None = None
    embedding: list[float] | None = None


class SupabaseRagStore:
    def __init__(
        self,
        url: str | None = None,
        service_role_key: str | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self.url = (url or settings.supabase_url).rstrip("/")
        self.key = service_role_key or settings.supabase_service_role_key
        self.timeout_s = timeout_s
        if not self.url:
            raise RuntimeError("SUPABASE_URL is missing")
        if not self.key:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is missing")

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def upsert_documents(self, chunks: list[RagChunk]) -> None:
        rows: list[dict[str, Any]] = []
        for c in chunks:
            if not c.embedding:
                raise RuntimeError("chunk embedding is missing")
            embedding_str = "[" + ",".join(str(float(x)) for x in c.embedding) + "]"
            rows.append(
                {
                    "source": c.source,
                    "source_id": c.source_id,
                    "title": c.title,
                    "content": c.content,
                    "url": c.url,
                    "metadata": c.metadata or {},
                    "embedding": embedding_str,
                }
            )
        if not rows:
            return
        endpoint = f"{self.url}/rest/v1/rag_documents"
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(endpoint, headers={**self._headers(), "Prefer": "return=minimal"}, json=rows)
            if r.status_code >= 400:
                raise RuntimeError(f"Supabase insert failed ({r.status_code}): {r.text}")

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 8,
        source_filter: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        args: dict[str, Any] = {
            "query_embedding": query_embedding,
            "match_count": int(top_k),
            "filter_source": source_filter,
        }
        endpoint = f"{self.url}/rest/v1/rpc/match_rag_documents"
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(endpoint, headers=self._headers(), json=args)
            if r.status_code >= 400:
                raise RuntimeError(f"Supabase RPC failed ({r.status_code}): {r.text}")
            data = r.json()
        return data if isinstance(data, list) else []

