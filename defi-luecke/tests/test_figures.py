"""Tests for pipeline.figures on tiny SYNTHETIC processed outputs (not real results)."""

import json

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from pipeline.figures import (
    coverage_rate_from_distances,
    make_all,
    normalize_cell_coverage,
)


def _metrics(level, ids, scenarios=("all", "night_strict", "night_optimistic")):
    rows = []
    for i in ids:
        for r in (100, 300):
            for s in scenarios:
                rows.append(
                    {
                        "level": level,
                        "id": i,
                        "name": f"SYNTH {i}",
                        "radius_m": r,
                        "scenario": s,
                        "population": 1000,
                        "covered_population": 400 + r,
                        "coverage_rate": (400 + r) / 1000,
                    }
                )
    return pd.DataFrame(rows)


@pytest.fixture
def processed(tmp_path):
    p = tmp_path / "proc"
    p.mkdir()
    _metrics("municipality", ["99999001", "99999002", "99999003"]).to_csv(
        p / "metrics_municipality.csv", index=False
    )
    _metrics("district", ["99999"]).to_csv(p / "metrics_district.csv", index=False)
    cells = pd.DataFrame(
        {
            "cell_id": ["a", "b", "c"],
            "population": [10, 20, 30],
            "scenario": "all",
            "effective_distance_m": [100.0, 250.0, float("nan")],
        }
    )
    cells.to_csv(p / "cell_coverage.csv", index=False)
    for v in "AB":
        pd.DataFrame(
            {
                "scope_id": "99999",
                "radius_m": 300,
                "scenario": "all",
                "rank": [1, 2, 3],
                "cumulative_rate": [0.5, 0.6, 0.7],
            }
        ).to_csv(p / f"optimize_{v}_district.csv", index=False)
    (p / "validation_testgebiet.json").write_text(
        json.dumps(
            {
                "area": "testgebiet",
                "confidence_level": 0.95,
                "recall": {"value": 0.5, "ci_low": 0.3, "ci_high": 0.7},
                "precision": {"value": 0.8, "ci_low": 0.6, "ci_high": 0.9},
            }
        ),
        encoding="utf-8",
    )
    gpkg = tmp_path / "synth.gpkg"
    gpd.GeoDataFrame(
        {"ags": ["99999001", "99999002", "99999003"], "area_km2": [1.0, 10.0, 100.0]},
        geometry=[box(0, 0, 1, 1)] * 3,
        crs=3035,
    ).to_file(gpkg, layer="municipalities", driver="GPKG")
    gpd.GeoDataFrame(geometry=[Point(0, 0)], crs=3035).to_file(gpkg, layer="aeds", driver="GPKG")
    return p, gpkg


def test_make_all_creates_files(processed):
    p, gpkg = processed
    written = make_all(p, gpkg, 1.3)
    names = {w.name for w in written}
    for stem in (
        "a_verteilung_abdeckung_gemeinden",
        "b_abdeckung_vs_bevoelkerungsdichte",
        "c_szenarien_tag_nacht",
        "d_sensitivitaet_radius_umwegfaktor",
        "e_optimierer_abdeckungskurve",
        "f_validierung_recall_precision",
    ):
        assert f"{stem}.png" in names and f"{stem}.svg" in names
    assert (p / "figures" / "kennzahlen_gemeinden.csv").is_file()
    header = (p / "figures" / "kennzahlen_gemeinden.csv").read_text(encoding="utf-8-sig")
    assert "Abdeckungsquote" in header.splitlines()[0]


def test_missing_inputs_skip_gracefully(tmp_path, capsys):
    written = make_all(tmp_path, tmp_path / "none.gpkg", 1.3)
    assert written == []
    assert "übersprungen" in capsys.readouterr().out


def test_detour_recompute():
    cells = pd.DataFrame({"population": [10, 20, 30], "distance_m": [100.0, 250.0, float("nan")]})
    assert coverage_rate_from_distances(cells, 300, 1.0) == pytest.approx(30 / 60)
    assert coverage_rate_from_distances(cells, 300, 1.3) == pytest.approx(10 / 60)
    assert coverage_rate_from_distances(cells, 300, 0.5) == pytest.approx(30 / 60)


def test_normalize_wide_cell_coverage():
    df = pd.DataFrame(
        {"cell_id": ["a"], "population": [5], "dist_all": [10.0], "dist_night_strict": [None]}
    )
    out = normalize_cell_coverage(df)
    assert set(out["scenario"]) == {"all", "night_strict"}
