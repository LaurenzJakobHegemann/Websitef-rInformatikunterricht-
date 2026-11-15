"""Optimize (stub).

Greedy site optimizer for new AED locations (candidate variants A and B), producing a ranking
and coverage curve.

See SPEC section 5. Planned for milestone M3; currently a stub.
"""

from __future__ import annotations

from typing import Any

from pipeline.config import Params, RegionConfig

MILESTONE = "M3"


def run(region_cfg: RegionConfig, params: Params) -> Any:
    """Not implemented yet."""
    raise NotImplementedError(f"optimize ist noch nicht implementiert (Meilenstein {MILESTONE})")
