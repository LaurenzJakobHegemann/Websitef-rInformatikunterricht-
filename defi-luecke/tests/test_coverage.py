"""Coverage tests. All data is SYNTHETIC (see tests/synthetic_layers.py)."""

import math

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest

from pipeline import coverage
from pipeline.config import ConfigError, RegionConfig
from pipeline.coverage import (
    METRIC_COLUMNS,
    compute_metrics,
    filter_scenario,
    nearest_effective_distance,
    weighted_median,
)
from tests.synthetic_layers import make_layers, make_params


def test_nearest_distance_with_detour():
    cells = np.array([[0.0, 0.0], [300.0, 400.0]])
    aeds = np.array([[0.0, 0.0], [300.0, 0.0]])
    d = nearest_effective_distance(cells, aeds, 1.3)
    assert d == pytest.approx([0.0, 400 * 1.3])


def test_empty_aed_set_is_inf():
    d = nearest_effective_distance(np.array([[0.0, 0.0]]), np.empty((0, 2)), 1.3)
    assert np.isinf(d).all()


def test_detour_below_one_rejected():
    with pytest.raises(ValueError):
        nearest_effective_distance(np.zeros((1, 2)), np.zeros((1, 2)), 0.9)


def test_boundary_distance_equal_radius_is_covered():
    layers = make_layers()
    cells = layers.cells.iloc[:2].copy()
    # cell 1 is 100 m from the AED at the origin; detour 1.0 -> effective 100 == R
    params = make_params(detour_factor=1.0, radii_m=[100], scenarios=["all"])
    m = compute_metrics(
        coverage.Layers(
            layers.aeds, cells, layers.municipalities, layers.vg, layers.district, layers.candidates
        ),
        params,
        "district",
    )
    assert m.loc[0, "covered_population"] == 30


def test_filter_scenarios():
    aeds = pd.DataFrame(
        {
            "is_public": [True, True, True, True, False, True],
            "access_class": ["24/7", "restricted", "unknown", "unknown", "24/7", "unknown"],
            "opening_hours": ["24/7", "Mo-Fr", None, None, "24/7", ""],
            "indoor": [None, None, "no", "yes", None, "no"],
        }
    )
    assert list(filter_scenario(aeds, "all").index) == [0, 1, 2, 3, 5]
    assert list(filter_scenario(aeds, "night_strict").index) == [0]
    assert list(filter_scenario(aeds, "night_optimistic").index) == [0, 2, 5]
    with pytest.raises(ValueError):
        filter_scenario(aeds, "bogus")


def test_classify_access():
    s = pd.Series(["24/7", "Mo-Fr 8-18", None, ""])
    assert list(coverage.classify_access(s)) == ["24/7", "restricted", "unknown", "unknown"]


def test_weighted_median():
    assert weighted_median([1, 2, 3], [1, 1, 1]) == 2
    assert weighted_median([1, 2], [1, 1]) == 1.5  # exactly half -> mean of neighbours
    assert weighted_median([5, 1, 3], [1, 10, 1]) == 1  # heavy weight dominates, order-free
    assert weighted_median([1, 2, 3], [0, 0, 5]) == 3  # zero weights ignored
    assert weighted_median([1, math.inf], [1, 5]) == 1  # inf ignored
    assert math.isnan(weighted_median([math.inf], [3]))
    assert math.isnan(weighted_median([], []))


def _row(m, **kw):
    sel = m
    for k, v in kw.items():
        sel = sel[sel[k] == v]
    assert len(sel) == 1
    return sel.iloc[0]


def test_metrics_municipality_hand_computed():
    layers, params = make_layers(), make_params()
    m = compute_metrics(layers, params, "municipality")
    assert list(m.columns) == METRIC_COLUMNS
    assert len(m) == 2 * 4 * 3  # municipalities x radii x scenarios

    # Alpha, scenario all: effective distances 0, 130, 390 for pops 10, 20, 30
    a200 = _row(m, id="07231001", radius_m=200, scenario="all")
    assert a200["name"] == "Alpha"
    assert a200["population"] == 60
    assert a200["covered_population"] == 30
    assert a200["coverage_rate"] == pytest.approx(0.5)
    assert a200["mean_distance_m"] == pytest.approx((20 * 130 + 30 * 390) / 60)
    assert a200["median_distance_m"] == pytest.approx(260)  # exactly half -> (130+390)/2
    assert a200["aeds_in_area"] == 2
    assert a200["aeds_per_10k"] == pytest.approx(2 / 60 * 10_000)
    assert a200["share_aeds_missing_info"] == pytest.approx(0.5)  # AED0 has no access tag
    assert a200["share_access_unknown"] == 0
    assert _row(m, id="07231001", radius_m=500, scenario="all")["coverage_rate"] == 1.0
    # boundary: 130 <= 130 covered at R=130? radii are 100/200 -> 100 covers only the 0-cell
    assert _row(m, id="07231001", radius_m=100, scenario="all")["covered_population"] == 10

    # Alpha, night_strict: only AED0 (24/7 and public): distances 0, 130, 1300
    s = _row(m, id="07231001", radius_m=500, scenario="night_strict")
    assert s["covered_population"] == 30
    assert s["mean_distance_m"] == pytest.approx((20 * 130 + 30 * 1300) / 60)
    assert s["aeds_in_area"] == 1
    assert s["share_aeds_missing_info"] == 1.0

    # Beta, scenario all: AED2 is private -> no AED inside Beta
    b = _row(m, id="07231002", radius_m=500, scenario="all")
    assert b["aeds_in_area"] == 0
    assert b["aeds_per_10k"] == 0
    assert math.isnan(b["share_aeds_missing_info"])
    d_b1 = 1000 * 1.3  # nearest public AED for (0,1000) is AED0 at 1000 m
    d_b2 = min(math.hypot(500, 1000), math.hypot(500, 700)) * 1.3
    assert b["mean_distance_m"] == pytest.approx((40 * d_b1 + 5 * d_b2) / 45)
    assert b["covered_population"] == 0


def test_metrics_district_and_vg():
    layers, params = make_layers(), make_params(radii_m=[200], scenarios=["all"])
    d = compute_metrics(layers, params, "district")
    assert len(d) == 1
    assert d.loc[0, "id"] == "07231"
    assert d.loc[0, "population"] == 105
    assert d.loc[0, "covered_population"] == 30
    assert d.loc[0, "aeds_in_area"] == 2
    vg = compute_metrics(layers, params, "vg")
    assert vg.loc[0, "id"] == "072310001"
    assert vg.loc[0, "population"] == 60  # cells without vg_ars are excluded


def test_no_aeds_gives_inf_and_nan():
    layers = make_layers()
    layers.aeds = layers.aeds.iloc[0:0]
    params = make_params(radii_m=[500], scenarios=["all"])
    m = compute_metrics(layers, params, "district")
    assert m.loc[0, "covered_population"] == 0
    assert m.loc[0, "coverage_rate"] == 0
    assert math.isnan(m.loc[0, "mean_distance_m"])
    assert math.isnan(m.loc[0, "median_distance_m"])
    assert m.loc[0, "aeds_in_area"] == 0


def test_cell_coverage_table():
    layers, params = make_layers(), make_params()
    dist = coverage.scenario_distances(layers.cells, layers.aeds, params.coverage["scenarios"], 1.3)
    table = coverage.compute_cell_coverage(layers.cells, dist)
    assert list(table.columns) == [
        "cell_id",
        "x",
        "y",
        "population",
        "municipality_ags",
        "distance_m_all",
        "distance_m_night_strict",
        "distance_m_night_optimistic",
    ]
    assert table["distance_m_all"].iloc[1] == pytest.approx(130)


def _region():
    return RegionConfig(key="synthetic", name="Test", state="Test", district_key="07231")


def test_run_missing_gpkg_german_error(tmp_path, monkeypatch):
    monkeypatch.setattr(coverage, "PROJECT_ROOT", tmp_path)
    with pytest.raises(ConfigError, match="zuerst 'fetch' ausführen"):
        coverage.run(_region(), make_params())


def test_run_writes_csvs(tmp_path, monkeypatch):
    monkeypatch.setattr(coverage, "PROJECT_ROOT", tmp_path)
    layers = make_layers()
    path = coverage.interim_path(_region())
    path.parent.mkdir(parents=True)
    for name in ("aeds", "cells", "municipalities", "vg", "district", "candidates"):
        gdf: gpd.GeoDataFrame = getattr(layers, name)
        gdf.to_file(path, layer=name, driver="GPKG")
    coverage.run(_region(), make_params())
    out = coverage.processed_dir(_region())
    for level in ("municipality", "vg", "district"):
        assert (out / f"metrics_{level}.csv").is_file()
    cc = pd.read_csv(out / "cell_coverage.csv", dtype={"municipality_ags": str})
    assert len(cc) == 5
    m = pd.read_csv(out / "metrics_municipality.csv", dtype={"id": str})
    assert set(m["id"]) == {"07231001", "07231002"}
