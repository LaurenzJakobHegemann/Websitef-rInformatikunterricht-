"""Load census (stub).

Load the Zensus 2022 100 m population grid, check the expected columns against the dataset
description, and clip it to the region.

See SPEC section 3. Planned for milestone M1; currently a stub.
"""

from __future__ import annotations

from typing import Any

from pipeline.config import Params, RegionConfig

MILESTONE = "M1"


def run(region_cfg: RegionConfig, params: Params) -> Any:
    """Not implemented yet."""
    raise NotImplementedError(f"load_census ist noch nicht implementiert (Meilenstein {MILESTONE})")
