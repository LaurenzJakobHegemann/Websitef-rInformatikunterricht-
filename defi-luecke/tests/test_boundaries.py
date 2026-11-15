"""Boundary loading tests with a SYNTHETIC GeoPackage (VG250 layout), no network."""

import geopandas as gpd
import pytest
from shapely.geometry import box

from pipeline.config import RegionConfig, load_params
from pipeline.fetch_boundaries import BoundaryError, load_boundaries

PARAMS = load_params()


def _make_gpkg(tmp_path):
    crs = "EPSG:25832"

    def layer(name, rows, geoms):
        gpd.GeoDataFrame(rows, geometry=geoms, crs=crs).to_file(
            tmp_path / "t.gpkg", layer=name, driver="GPKG", mode="a"
        )

    layer(
        "vg250_krs",
        {"AGS": ["99999", "88888"], "ARS": ["99999", "88888"], "GF": [4, 4],
         "GEN": ["Testkreis", "Anderer"], "BEZ": ["Landkreis"] * 2, "EWZ": [300, 5]},
        [box(0, 0, 3000, 1000), box(9000, 0, 9100, 100)],
    )  # fmt: skip
    layer(
        "vg250_vwg",
        {"ARS": ["999990001", "999990002"], "GF": [4, 4], "GEN": ["VG1", "VG2"],
         "BEZ": ["Verbandsgemeinde"] * 2, "EWZ": [100, 200]},
        [box(0, 0, 1000, 1000), box(1000, 0, 3000, 1000)],
    )  # fmt: skip
    layer(
        "vg250_gem",
        {"AGS": ["99999001", "99999002", "99999003"],
         "ARS": ["999990001001", "999990002002", "999990002003"],
         "GF": [4, 4, 4], "GEN": ["G1", "G2", "G3"], "BEZ": ["Gemeinde"] * 3,
         "EWZ": [100, 100, 100]},
        [box(0, 0, 1000, 1000), box(1000, 0, 2000, 1000), box(2000, 0, 3000, 1000)],
    )  # fmt: skip
    return tmp_path / "t.gpkg"


def _region(key="99999", pop=300):
    return RegionConfig("t", "Testkreis", "X", key, True, pop)


def test_load_boundaries_synthetic(tmp_path):
    b = load_boundaries(_region(), PARAMS, gpkg=_make_gpkg(tmp_path))
    assert b.district.crs.to_epsg() == 3035
    assert len(b.municipalities) == 3 and len(b.vg) == 2
    assert set(b.municipalities["vg_ars"]) == {"999990001", "999990002"}
    assert b.warnings == []
    assert b.district["name"].iloc[0] == "Testkreis"


def test_unknown_district_is_german_error(tmp_path):
    with pytest.raises(BoundaryError, match="nicht in VG250 gefunden"):
        load_boundaries(_region("77777"), PARAMS, gpkg=_make_gpkg(tmp_path))


def test_ewz_mismatch_warns(tmp_path):
    b = load_boundaries(_region(pop=999), PARAMS, gpkg=_make_gpkg(tmp_path))
    assert any("weicht" in w for w in b.warnings)


def test_invalid_key_rejected(tmp_path):
    with pytest.raises(BoundaryError):
        load_boundaries(_region("0' OR 1=1"), PARAMS, gpkg=_make_gpkg(tmp_path))
