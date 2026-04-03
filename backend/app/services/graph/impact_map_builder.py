from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from app.models.schemas import (
    ImpactEdge,
    ImpactGraph,
    ImpactLoop,
    ImpactMapSelectedItem,
    ImpactNode,
    PolymarketCorrelation,
    SourceLink,
)
from app.services.rag.gemini_embedder import GeminiChat

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a macro finance and geopolitics analyst.
Given the user's event, output an "event impact map" as JSON only (no prose outside JSON).

Strict JSON schema:

{
  "nodes": [
    {
      "id": "snake_case id",
      "label": "short human-readable label in English",
      "type": "event | market | macro | policy | other",
      "direction": "+ | - | neutral",
      "confidence": 0.0~1.0,
      "polymarket_ids": ["matching market_id from list below, or empty"]
    }
  ],
  "edges": [
    {
      "id": "e1",
      "source": "node id",
      "target": "node id",
      "effect": "+ | - | uncertain",
      "strength": 0.0~1.0,
      "description": "one-sentence explanation in English"
    }
  ],
  "loops": [
    {
      "id": "loop1",
      "kind": "R or B",
      "nodes": ["node ids in this loop"],
      "description": "loop explanation in English"
    }
  ]
}

Rules:
1. Exactly one node with type="event" as the center for the input event.
2. Add 3–8 additional nodes (market/macro/policy/other).
3. Every edge source/target must exist in nodes.
4. Loop node ids must exist; loops may be empty or 1–3 items.
5. direction: main expected move after the event (+ up, - down, neutral). Center event node uses "neutral".
6. confidence 0–1; lower if uncertain; do not fabricate.
7. Cover equities, oil, gold, USD, inflation, rates, major indices where relevant.
8. For each node, fill polymarket_ids from the Polymarket list below when relevant; multiple ids allowed.
"""

ELABORATE_PROMPT = """\
You are a macro finance and geopolitics analyst.

The user already has an impact map and wants to expand one node into sub-impacts.

Current nodes (context):
{existing_nodes}

Node to expand:
- ID: {node_id}
- Label: {node_label}
- Type: {node_type}

Produce 3–6 new child-impact nodes and edges from {node_id} to each child. Do not duplicate existing node ids.

Return JSON only:
{{
  "nodes": [
    {{
      "id": "new unique snake_case id",
      "label": "English label",
      "type": "event | market | macro | policy | other",
      "direction": "+ | - | neutral",
      "confidence": 0.0~1.0,
      "polymarket_ids": ["matching market_id"]
    }}
  ],
  "edges": [
    {{
      "id": "e_xxx",
      "source": "{node_id}",
      "target": "new node id",
      "effect": "+ | - | uncertain",
      "strength": 0.0~1.0,
      "description": "one sentence in English"
    }}
  ],
  "loops": []
}}

Rules:
1. source must be {node_id}; target must be a newly created node id.
2. Add extra edges between new nodes only if clearly linked.
3. Fill polymarket_ids from the Polymarket list when relevant.
"""


def build_event_text(
    selected_item: Optional[ImpactMapSelectedItem],
    chat_event_text: Optional[str],
) -> str:
    if chat_event_text and chat_event_text.strip():
        return chat_event_text.strip()

    if not selected_item:
        return ""

    parts: list[str] = [f"Event: {selected_item.title}"]
    if selected_item.description:
        parts.append(f"Description: {selected_item.description[:600]}")
    if selected_item.kind:
        parts.append(f"Kind: {selected_item.kind}")
    if selected_item.symbol:
        parts.append(f"Symbol: {selected_item.symbol}")
    if selected_item.probability is not None:
        parts.append(f"Probability: {selected_item.probability*100:.1f}%")
    if selected_item.volume_24h is not None:
        parts.append(f"24h volume: ${selected_item.volume_24h:,.0f}")
    if selected_item.category:
        parts.append(f"Category: {selected_item.category}")
    return "\n".join(parts)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    if text.startswith("{"):
        return json.loads(text)
    raise ValueError(f"Cannot extract JSON from model output: {text[:200]}")


def _build_polymarket_context(markets: list[dict]) -> str:
    if not markets:
        return "(No Polymarket market data available.)"
    lines: list[str] = []
    for m in markets[:60]:
        prob = m.get("probability")
        prob_s = f" prob={prob*100:.0f}%" if prob is not None else ""
        cat = m.get("category", "")
        lines.append(f"- [{m.get('market_id','')}] {m.get('title','')}{prob_s} cat={cat}")
    return "\n".join(lines)


async def _fetch_grounding_sources(event_text: str, node_labels: list[str]) -> list[SourceLink]:
    try:
        topics = ", ".join(node_labels[:8])
        query = f"Find latest news and analysis sources about: {event_text[:200]}. Related topics: {topics}. Return the most relevant source links."
        chat = GeminiChat(timeout_s=30.0)
        _, raw_sources = await chat.generate_with_sources(query)
        seen: set[str] = set()
        sources: list[SourceLink] = []
        for s in raw_sources:
            url = s.get("url", "")
            if url and url not in seen:
                seen.add(url)
                sources.append(SourceLink(title=s.get("title", ""), url=url))
        return sources[:10]
    except Exception as e:
        logger.warning("Grounding sources fetch failed: %s", e)
        return []


def _attach_polymarket_correlations(
    nodes: list[ImpactNode],
    pm_ids_map: dict[str, list[str]],
    markets_by_id: dict[str, dict],
) -> None:
    for node in nodes:
        raw_ids = pm_ids_map.get(node.id, [])
        corrs: list[PolymarketCorrelation] = []
        for mid in raw_ids:
            m = markets_by_id.get(mid)
            if not m:
                continue
            corrs.append(PolymarketCorrelation(
                market_id=mid,
                title=m.get("title", mid),
                probability=m.get("probability"),
                volume_24h=m.get("volume_24h"),
                relevance="",
            ))
        node.polymarket_correlations = corrs


async def build_impact_map(
    event_text: str,
    selected_item: Optional[ImpactMapSelectedItem] = None,
    polymarket_markets: Optional[list[dict]] = None,
) -> ImpactGraph:
    if not event_text.strip():
        return ImpactGraph(
            generated_at=datetime.now(timezone.utc),
            error="No event text provided",
        )

    pm = polymarket_markets or []
    pm_context = _build_polymarket_context(pm)
    markets_by_id = {m.get("market_id", ""): m for m in pm if m.get("market_id")}

    chat = GeminiChat(timeout_s=60.0)
    prompt = f"{SYSTEM_PROMPT}\n\n## Polymarket markets (for polymarket_ids)\n{pm_context}\n\nEvent:\n{event_text}"

    try:
        raw = await chat.generate(prompt)
        data = _extract_json(raw)
    except Exception as e:
        logger.exception("Impact map generation failed")
        return ImpactGraph(
            nodes=[ImpactNode(id="event_center", label=event_text[:80], type="event")],
            edges=[],
            loops=[],
            generated_at=datetime.now(timezone.utc),
            error=str(e),
        )

    nodes = [ImpactNode(**{k: v for k, v in n.items() if k != "polymarket_ids"}) for n in data.get("nodes", [])]
    edges = [ImpactEdge(**e) for e in data.get("edges", [])]
    loops = [ImpactLoop(**lp) for lp in data.get("loops", [])]

    pm_ids_map: dict[str, list[str]] = {}
    for n in data.get("nodes", []):
        pm_ids_map[n.get("id", "")] = n.get("polymarket_ids", [])
    _attach_polymarket_correlations(nodes, pm_ids_map, markets_by_id)

    sources = await _fetch_grounding_sources(event_text, [n.label for n in nodes])

    return ImpactGraph(
        nodes=nodes,
        edges=edges,
        loops=loops,
        sources=sources,
        generated_at=datetime.now(timezone.utc),
    )


async def elaborate_node(
    existing_graph: ImpactGraph,
    node_id: str,
    polymarket_markets: Optional[list[dict]] = None,
) -> ImpactGraph:
    target_node = next((n for n in existing_graph.nodes if n.id == node_id), None)
    if not target_node:
        return existing_graph

    existing_ids = {n.id for n in existing_graph.nodes}
    existing_nodes_desc = "\n".join(
        f"- [{n.id}] {n.label} (type={n.type}, dir={n.direction})"
        for n in existing_graph.nodes
    )

    pm = polymarket_markets or []
    pm_context = _build_polymarket_context(pm)
    markets_by_id = {m.get("market_id", ""): m for m in pm if m.get("market_id")}

    prompt_text = ELABORATE_PROMPT.format(
        existing_nodes=existing_nodes_desc,
        node_id=node_id,
        node_label=target_node.label,
        node_type=target_node.type,
    )
    prompt = f"{prompt_text}\n\n## Polymarket markets\n{pm_context}"

    chat = GeminiChat(timeout_s=60.0)
    try:
        raw = await chat.generate(prompt)
        data = _extract_json(raw)
    except Exception as e:
        logger.exception("Elaborate node failed")
        return existing_graph

    new_nodes_raw = [n for n in data.get("nodes", []) if n.get("id") not in existing_ids]
    new_edges = [ImpactEdge(**e) for e in data.get("edges", [])]
    new_nodes = [ImpactNode(**{k: v for k, v in n.items() if k != "polymarket_ids"}) for n in new_nodes_raw]

    pm_ids_map: dict[str, list[str]] = {}
    for n in new_nodes_raw:
        pm_ids_map[n.get("id", "")] = n.get("polymarket_ids", [])
    _attach_polymarket_correlations(new_nodes, pm_ids_map, markets_by_id)

    merged_nodes = list(existing_graph.nodes) + new_nodes
    existing_edge_ids = {e.id for e in existing_graph.edges}
    merged_edges = list(existing_graph.edges) + [e for e in new_edges if e.id not in existing_edge_ids]

    return ImpactGraph(
        nodes=merged_nodes,
        edges=merged_edges,
        loops=existing_graph.loops,
        generated_at=datetime.now(timezone.utc),
    )
