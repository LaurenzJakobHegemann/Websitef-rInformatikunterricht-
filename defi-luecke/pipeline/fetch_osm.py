"""Fetch osm (stub).

Fetch AED locations (emergency=defibrillator) and optional candidate places from OpenStreetMap
via Overpass for the region, keep the tags listed in params.osm.aed_tags_to_keep, and store a
dated snapshot in data/raw.

See SPEC section 3. Planned for milestone M1; currently a stub.
"""

from __future__ import annotations

from typing import Any

from pipeline.config import Params, RegionConfig

MILESTONE = "M1"


def run(region_cfg: RegionConfig, params: Params) -> Any:
    """Not implemented yet."""
    raise NotImplementedError(f"fetch_osm ist noch nicht implementiert (Meilenstein {MILESTONE})")
