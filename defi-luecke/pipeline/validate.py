"""Validate (stub).

Validate completeness of the OSM AED data against a field survey (matching within tolerance,
confidence interval).

See SPEC section 6. Planned for milestone M5; currently a stub.
"""

from __future__ import annotations

from typing import Any

from pipeline.config import Params, RegionConfig

MILESTONE = "M5"


def run(region_cfg: RegionConfig, params: Params) -> Any:
    """Not implemented yet."""
    raise NotImplementedError(f"validate ist noch nicht implementiert (Meilenstein {MILESTONE})")
