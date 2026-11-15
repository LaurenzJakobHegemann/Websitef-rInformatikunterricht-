"""Tests for pipeline.validate. All data is SYNTHETIC (tests/fixtures/survey_example.csv)."""

import json
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Point, box

from pipeline.validate import (
    ValidationError,
    chapman_estimate,
    match_points,
    read_survey,
    run_validation,
    to_laea,
    wilson_interval,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_wilson_known_values():
    # Reference: Wilson 1927 / standard tables, 95 %
    p, lo, hi = wilson_interval(8, 10, 0.95)
    assert p == 0.8
    assert lo == pytest.approx(0.4902, abs=1e-3)
    assert hi == pytest.approx(0.9433, abs=1e-3)
    _, lo, hi = wilson_interval(0, 10, 0.95)
    assert lo == 0.0
    assert hi == pytest.approx(0.2775, abs=1e-3)
    _, lo, hi = wilson_interval(50, 100, 0.95)
    assert (lo, hi) == pytest.approx((0.4038, 0.5962), abs=1e-3)
    assert math.isnan(wilson_interval(0, 0)[0])


def test_chapman_known_value():
    r = chapman_estimate(10, 10, 5)
    assert r["estimate"] == pytest.approx(11 * 11 / 6 - 1)
    assert r["variance"] == pytest.approx(11 * 11 * 5 * 5 / (36 * 7))
    assert r["ci_low"] >= r["known_distinct"]
    with pytest.raises(ValueError):
        chapman_estimate(3, 3, 4)


def test_match_one_to_one_conflict():
    # Survey points a0, a1 both near b0; b1 only reachable from a1.
    a = np.array([[0.0, 0.0], [30.0, 0.0]])
    b = np.array([[10.0, 0.0], [70.0, 0.0]])
    pairs = match_points(a, b, 50)
    assert {(i, j) for i, j, _ in pairs} == {(0, 0), (1, 1)}
    # Only one B point within reach of both A points: only one pair possible.
    pairs = match_points(a, np.array([[10.0, 0.0]]), 50)
    assert len(pairs) == 1
    assert match_points(a, np.empty((0, 2)), 50) == []


def test_match_tolerance_excludes_far():
    assert match_points(np.array([[0.0, 0.0]]), np.array([[60.0, 0.0]]), 50) == []


def test_read_survey_missing_columns(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("region,lat\na,1\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="fehlende Spalten"):
        read_survey(p)


def _synthetic_gpkg(path: Path) -> None:
    xy = to_laea([7.0, 7.0, 7.0, 7.0], [50.0, 50.0003, 50.0005, 50.0300])
    pts = [Point(*p) for p in xy]
    aeds = gpd.GeoDataFrame(
        {
            "osm_type": ["node"] * 4,
            "osm_id": [1, 2, 3, 4],
            "is_public": [True, True, True, True],
        },
        geometry=pts,
        crs=3035,
    )
    cx, cy = xy[0]
    munis = gpd.GeoDataFrame(
        {"ags": ["99999001"]}, geometry=[box(cx - 5000, cy - 1000, cx + 5000, cy + 1000)], crs=3035
    )
    # AED 4 (~3.3 km north) lies outside the municipality box.
    aeds.to_file(path, layer="aeds", driver="GPKG")
    munis.to_file(path, layer="municipalities", driver="GPKG")


def test_run_validation_end_to_end(tmp_path):
    surveys = tmp_path / "surveys"
    surveys.mkdir()
    (surveys / "synth_testgebiet.csv").write_text(
        (FIXTURES / "survey_example.csv").read_text(encoding="utf-8"), encoding="utf-8"
    )
    gpkg = tmp_path / "synth.gpkg"
    _synthetic_gpkg(gpkg)
    out = tmp_path / "out"
    written = run_validation(
        "synth",
        {"match_tolerance_m": 50, "confidence_level": 0.95, "areas": {"testgebiet": ["99999001"]}},
        gpkg,
        surveys,
        out,
    )
    assert len(written) == 1
    res = json.loads((out / "validation_testgebiet.json").read_text(encoding="utf-8"))
    # Public survey rows: 3; OSM in area: 3 (50.0, 50.0003, 50.0005); the survey row at
    # 50.0010 is ~111 m from the nearest OSM AED (50.0005 ~ 55 m): out of tolerance.
    assert res["n_surveyed_public"] == 3
    assert res["n_surveyed_excluded_non_public"] == 1
    assert res["n_osm_public_in_area"] == 3
    assert res["n_matched"] == 1
    assert res["recall"]["k"] == 1 and res["recall"]["n"] == 3
    assert res["precision"]["n"] == 3
    assert (out / "validation_testgebiet_matches.csv").is_file()


def test_run_validation_without_surveys(tmp_path, capsys):
    assert run_validation("synth", {}, tmp_path / "none.gpkg", tmp_path / "nodir", tmp_path) == []
    assert "Keine Erhebungsdateien" in capsys.readouterr().out
