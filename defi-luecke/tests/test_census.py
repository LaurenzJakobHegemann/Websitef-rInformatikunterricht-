"""Census loading tests. SYNTHETIC data, no network."""

import io

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from pipeline import load_census as lc
from pipeline.fetch_boundaries import Boundaries

CANDS = ["Bevoelkerungszahl", "Einwohner"]


def _csv(value_col: str) -> io.StringIO:
    return io.StringIO(
        f"GITTER_ID_100m;x_mp_100m;y_mp_100m;{value_col}\n"
        "A;4337050;2689150;4\n"
        "B;4337150;2689150;–\n"  # dash = zero
        "C;4337250;2689150;12\n"
        "D;9999950;9999950;7\n"  # outside bbox
    )


@pytest.mark.parametrize("col", ["Einwohner", "Bevoelkerungszahl"])
def test_column_detection_both_names(col):
    frame, used, n = lc.read_cells(_csv(col), CANDS, (4337000, 2689000, 4338000, 2690000))
    assert used == col and n == 4
    assert list(frame["cell_id"]) == ["A", "C"]  # dash cell dropped (0), D outside bbox
    assert list(frame["population"]) == [4, 12]


def test_no_population_column_is_german_error():
    with pytest.raises(lc.CensusError, match="Keine Bevölkerungsspalte"):
        lc.read_cells(_csv("Anzahl"), CANDS, (0, 0, 1e8, 1e8))


def test_missing_id_column():
    with pytest.raises(lc.CensusError, match="Spalten fehlen"):
        lc.check_columns(["x_mp_100m", "y_mp_100m", "Einwohner"], CANDS)


def test_parse_population_dash_and_junk():
    s = pd.Series(["5", "–", " 7 "])
    assert list(lc.parse_population(s)) == [5, 0, 7]
    with pytest.raises(lc.CensusError):
        lc.parse_population(pd.Series(["5", "abc"]))


def test_assign_cells_inside_district_only():
    crs = "EPSG:3035"
    district = gpd.GeoDataFrame({"ags": ["1"]}, geometry=[box(0, 0, 200, 100)], crs=crs)
    muni = gpd.GeoDataFrame(
        {"ags": ["m1", "m2"], "vg_ars": ["v1", "v2"]},
        geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100)],
        crs=crs,
    )
    frame = pd.DataFrame(
        {
            "cell_id": ["a", "b", "c"],
            "x": [50.0, 150.0, 350.0],
            "y": [50.0, 50.0, 50.0],
            "population": [3, 4, 9],
        }
    )
    b = Boundaries(district, gpd.GeoDataFrame(), muni)
    cells = lc.assign_cells(frame, b, crs)
    assert list(cells["cell_id"]) == ["a", "b"]
    assert list(cells["municipality_ags"]) == ["m1", "m2"]
    assert list(cells["vg_ars"]) == ["v1", "v2"]
