"""Fetch boundaries (stub).

Download the administrative boundaries (BKG VG250) and select the district and its
municipalities; verify the configured district key (AGS).

See SPEC section 3. Planned for milestone M1; currently a stub.
"""

from __future__ import annotations

from typing import Any

from pipeline.config import Params, RegionConfig

MILESTONE = "M1"


def run(region_cfg: RegionConfig, params: Params) -> Any:
    """Not implemented yet."""
    raise NotImplementedError(
        f"fetch_boundaries ist noch nicht implementiert (Meilenstein {MILESTONE})"
    )
