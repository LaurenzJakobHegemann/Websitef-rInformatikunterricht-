"""Coverage (stub).

Compute coverage metrics (share of population within radius of an AED) per municipality for all
radii and scenarios.

See SPEC section 4. Planned for milestone M2; currently a stub.
"""

from __future__ import annotations

from typing import Any

from pipeline.config import Params, RegionConfig

MILESTONE = "M2"


def radius_from_round_trip(max_round_trip_s: float, walking_speed_m_per_s: float) -> float:
    """One-way distance in metres for a maximum round trip time.

    The person walks to the AED and back, so the one-way distance is
    ``speed * time / 2``.
    """
    if max_round_trip_s <= 0:
        raise ValueError("max_round_trip_s muss positiv sein.")
    if walking_speed_m_per_s <= 0:
        raise ValueError("walking_speed_m_per_s muss positiv sein.")
    return walking_speed_m_per_s * max_round_trip_s / 2


def effective_distance(straight_line_m: float, detour_factor: float) -> float:
    """Estimated walking distance: straight-line distance times the detour factor."""
    if straight_line_m < 0:
        raise ValueError("straight_line_m darf nicht negativ sein.")
    if detour_factor < 1:
        raise ValueError("detour_factor muss mindestens 1 sein.")
    return straight_line_m * detour_factor


def run(region_cfg: RegionConfig, params: Params) -> Any:
    """Not implemented yet."""
    raise NotImplementedError(f"coverage ist noch nicht implementiert (Meilenstein {MILESTONE})")
