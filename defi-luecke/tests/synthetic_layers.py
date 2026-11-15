"""SYNTHETIC test data (hand-made, not real-world). Mirrors the layers of the interim GeoPackage.

Coordinates are offsets from an origin in Germany in EPSG:3035 so that lon/lat conversion
gives plausible values. Hand-computed expectations are in the tests.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, box

from pipeline.config import Params
from pipeline.coverage import classify_access

X0, Y0 = 4_100_000.0, 3_000_000.0
CRS = "EPSG:3035"


def pts(rows: list[tuple[float, float]]) -> list[Point]:
    return [Point(X0 + x, Y0 + y) for x, y in rows]


def make_params(**coverage) -> Params:
    cov = {
        "detour_factor": 1.3,
        "radii_m": [100, 200, 300, 500],
        "scenarios": ["all", "night_strict", "night_optimistic"],
        "excluded_access_values": ["private", "no"],
    }
    cov.update(coverage)
    return Params(
        crs={"compute": "EPSG:3035", "web": "EPSG:4326"},
        coverage=cov,
        optimize={
            "k_max_district": 3,
            "k_max_municipality": 3,
            "candidate_variants": ["A", "B"],
        },
    )


def make_aeds() -> gpd.GeoDataFrame:
    df = pd.DataFrame(
        {
            # AED 0: 24/7, access missing; AED 1: restricted hours; AED 2: private (not public)
            "access": [None, "yes", "private"],
            "opening_hours": ["24/7", "Mo-Fr 08:00-18:00", "24/7"],
            "indoor": [None, "yes", None],
            "is_public": [True, True, False],
        }
    )
    df["access_class"] = classify_access(df["opening_hours"])
    return gpd.GeoDataFrame(df, geometry=pts([(0, 0), (1000, 300), (0, 1000)]), crs=CRS)


def make_cells() -> gpd.GeoDataFrame:
    xy = [(0, 0), (100, 0), (1000, 0), (0, 1000), (500, 1000)]
    df = pd.DataFrame(
        {
            "cell_id": [f"c{i}" for i in range(5)],
            "population": [10, 20, 30, 40, 5],
            "municipality_ags": ["07231001"] * 3 + ["07231002"] * 2,
            "vg_ars": ["072310001000"[:9]] * 3 + [None] * 2,
        }
    )
    return gpd.GeoDataFrame(df, geometry=pts(xy), crs=CRS)


def _box(x0, y0, x1, y1):
    return box(X0 + x0, Y0 + y0, X0 + x1, Y0 + y1)


def make_layers():
    from pipeline.coverage import Layers

    muni = gpd.GeoDataFrame(
        {"ags": ["07231001", "07231002"], "name": ["Alpha", "Beta"]},
        geometry=[_box(-100, -100, 1100, 500), _box(-100, 700, 1100, 1500)],
        crs=CRS,
    )
    vg = gpd.GeoDataFrame(
        {"ars": ["072310001"], "name": ["VG Alpha"]},
        geometry=[_box(-100, -100, 1100, 500)],
        crs=CRS,
    )
    district = gpd.GeoDataFrame(
        {"ags": ["07231"], "name": ["Testkreis"]},
        geometry=[_box(-100, -100, 1100, 1500)],
        crs=CRS,
    )
    candidates = gpd.GeoDataFrame(
        {"name": ["Rathaus Beta", None], "category": ["amenity=townhall", "amenity=pharmacy"]},
        geometry=pts([(480, 1000), (950, 50)]),
        crs=CRS,
    )
    cells = make_cells()
    cells["vg_ars"] = ["072310001"] * 3 + [None] * 2
    return Layers(make_aeds(), cells, muni, vg, district, candidates)
