from __future__ import annotations
import json
from typing import Optional, Tuple
from app.core.config import settings


class GeoResolver:
    def __init__(self):
        map_path = settings.data_dir / "location_map.json"
        with open(map_path, "r", encoding="utf-8") as f:
            self._map: dict[str, dict] = json.load(f)

    def resolve(self, keywords: list[str]) -> Optional[Tuple[float, float]]:
        for kw in keywords:
            key = kw.lower().strip()
            if key in self._map:
                loc = self._map[key]
                return loc["lat"], loc["lng"]
        return None


geo_resolver = GeoResolver()
