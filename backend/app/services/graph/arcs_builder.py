from app.models.schemas import ArcEdge


def build_arcs(markets: list[dict]) -> list[ArcEdge]:
    edges: list[ArcEdge] = []
    seen = set()

    for i, m1 in enumerate(markets):
        kw1 = set(k.lower() for k in m1.get("keywords", []))
        for j, m2 in enumerate(markets):
            if i >= j:
                continue
            kw2 = set(k.lower() for k in m2.get("keywords", []))
            overlap = kw1 & kw2
            if not overlap:
                continue

            pair = tuple(sorted([m1["market_id"], m2["market_id"]]))
            if pair in seen:
                continue
            seen.add(pair)

            strength = round(len(overlap) / max(len(kw1 | kw2), 1), 4)
            if strength >= 0.15:
                edges.append(ArcEdge(
                    from_market_id=m1["market_id"],
                    to_market_id=m2["market_id"],
                    strength=strength,
                ))

    return edges
