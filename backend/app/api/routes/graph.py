from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.models.schemas import ImpactGraph, ImpactMapRequest
from app.services.graph.impact_map_builder import build_event_text, build_impact_map, elaborate_node
from app.services.polymarket.client import get_cached_monitor_markets

logger = logging.getLogger(__name__)
router = APIRouter()


def _sb_url() -> str:
    return settings.supabase_url.rstrip("/")

def _sb_headers() -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


@router.post("/impact-map/generate", response_model=ImpactGraph)
async def generate_impact_map(body: ImpactMapRequest):
    pm = get_cached_monitor_markets()

    if body.elaborate_node_id and body.existing_graph:
        graph = await elaborate_node(body.existing_graph, body.elaborate_node_id, pm)
        return graph

    event_text = build_event_text(body.selected_item, body.chat_event_text)
    graph = await build_impact_map(event_text, body.selected_item, pm)
    return graph


class SaveMapRequest(BaseModel):
    map_id: Optional[str] = None
    title: str = ""
    graph: ImpactGraph
    event_kind: Optional[str] = None
    event_id: Optional[str] = None

class SaveMapResponse(BaseModel):
    map_id: str

class MapSummary(BaseModel):
    map_id: str
    title: str
    updated_at: str
    event_kind: Optional[str] = None
    event_id: Optional[str] = None


@router.post("/impact-map/save", response_model=SaveMapResponse)
async def save_impact_map(body: SaveMapRequest):
    mid = body.map_id or str(uuid.uuid4())
    title = body.title.strip() or "Untitled map"
    now = datetime.now(timezone.utc).isoformat()
    graph_json = body.graph.model_dump(mode="json")
    base = _sb_url()
    headers = _sb_headers()

    with httpx.Client(timeout=10) as c:
        r = c.get(
            f"{base}/rest/v1/impact_maps",
            headers=headers,
            params={"map_id": f"eq.{mid}", "select": "map_id"},
        )
        exists = bool(r.status_code == 200 and r.json())

    row = {
        "map_id": mid,
        "title": title,
        "graph_data": json.dumps(graph_json, ensure_ascii=False),
        "updated_at": now,
        "event_kind": body.event_kind or "",
        "event_id": body.event_id or "",
    }
    with httpx.Client(timeout=10) as c:
        if exists:
            resp = c.patch(
                f"{base}/rest/v1/impact_maps",
                headers={**headers, "Prefer": "return=minimal"},
                params={"map_id": f"eq.{mid}"},
                json={k: v for k, v in row.items() if k != "map_id"},
            )
        else:
            resp = c.post(
                f"{base}/rest/v1/impact_maps",
                headers={**headers, "Prefer": "return=minimal"},
                json=row,
            )
        if resp.status_code >= 400:
            logger.error("Supabase save error %s: %s", resp.status_code, resp.text)
            raise HTTPException(status_code=502, detail=f"Supabase save failed: {resp.text}")
    return SaveMapResponse(map_id=mid)


@router.get("/impact-map/list", response_model=list[MapSummary])
async def list_impact_maps():
    base = _sb_url()
    headers = _sb_headers()
    with httpx.Client(timeout=10) as c:
        r = c.get(
            f"{base}/rest/v1/impact_maps",
            headers=headers,
            params={"select": "map_id,title,updated_at,event_kind,event_id", "order": "updated_at.desc", "limit": "50"},
        )
        if r.status_code >= 400:
            logger.error("Supabase list error %s: %s", r.status_code, r.text)
        data = r.json() if r.status_code == 200 else []
    return [MapSummary(**d) for d in data] if isinstance(data, list) else []


@router.get("/impact-map/{map_id}")
async def get_impact_map(map_id: str):
    base = _sb_url()
    headers = _sb_headers()
    with httpx.Client(timeout=10) as c:
        r = c.get(
            f"{base}/rest/v1/impact_maps",
            headers=headers,
            params={"map_id": f"eq.{map_id}", "select": "*", "limit": "1"},
        )
    rows = r.json() if r.status_code == 200 else []
    if not rows:
        raise HTTPException(status_code=404, detail="Map not found")
    row = rows[0]
    graph = json.loads(row["graph_data"]) if isinstance(row["graph_data"], str) else row["graph_data"]
    return {"map_id": row["map_id"], "title": row["title"], "updated_at": row["updated_at"], "graph": graph}


@router.delete("/impact-map/{map_id}")
async def delete_impact_map(map_id: str):
    base = _sb_url()
    headers = _sb_headers()
    with httpx.Client(timeout=10) as c:
        r = c.delete(
            f"{base}/rest/v1/impact_maps",
            headers=headers,
            params={"map_id": f"eq.{map_id}"},
        )
    if r.status_code >= 400 and r.status_code != 404:
        raise HTTPException(status_code=502, detail=f"Delete failed: {r.text}")
    return {"ok": True, "map_id": map_id}
