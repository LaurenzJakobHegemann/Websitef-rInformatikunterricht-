"""Tests for pipeline.export_web with tiny SYNTHETIC inputs (not real data)."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from pipeline.export_web import ExportError, export_region

REGION = "testland"
CRS = "EPSG:3035"
X0, Y0 = 4_100_000, 2_900_000
RADII = [100, 300]
SCENARIOS = ["all", "night_strict", "night_optimistic"]


def _make_inputs(tmp_path: Path, wide: bool = False) -> tuple[Path, Path, Path]:
    interim, processed, out = tmp_path / "interim", tmp_path / "processed", tmp_path / "out"
    interim.mkdir()
    processed.mkdir()

    muni = gpd.GeoDataFrame(
        {
            "ags": ["07231001", "07231002"],
            "ars": ["072310000001", "072310000002"],
            "name": ["Alt-Dorf", "Neu-Stadt"],
            "type": ["Gemeinde", "Stadt"],
            "vg_ars": ["072310000", "072310000"],
            "ewz": [30, 20],
            "area_km2": [1.0, 1.0],
        },
        geometry=[box(X0, Y0, X0 + 1000, Y0 + 1000), box(X0 + 1000, Y0, X0 + 2000, Y0 + 1000)],
        crs=CRS,
    )
    vg = gpd.GeoDataFrame(
        {"ars": ["072310000"], "name": ["VG Test"], "type": ["VG"], "ewz": [50]},
        geometry=[box(X0, Y0, X0 + 2000, Y0 + 1000)],
        crs=CRS,
    )
    district = gpd.GeoDataFrame(
        {
            "ags": ["07231"],
            "name": ["Testkreis"],
            "type": ["Landkreis"],
            "ewz": [50],
            "area_km2": [2.0],
        },
        geometry=[box(X0, Y0, X0 + 2000, Y0 + 1000)],
        crs=CRS,
    )
    aeds = gpd.GeoDataFrame(
        {
            "osm_type": ["node", "way", "node", "node"],
            "osm_id": [1, 2, 3, 4],
            "osm_url": [f"https://www.openstreetmap.org/node/{i}" for i in (1, 2, 3, 4)],
            "defibrillator_location": ["Rathaus", None, "Kiosk", "Privat"],
            "opening_hours": ["24/7", "Mo-Fr 08:00-16:00", None, None],
            "indoor": [None, "yes", "no", None],
            "access_class": ["24/7", "restricted", "unknown", "unknown"],
            "is_public": [True, True, True, False],
            "in_region": [True, True, True, True],
        },
        geometry=[
            Point(X0 + 150, Y0 + 150),
            Point(X0 + 1500, Y0 + 500),
            Point(X0 + 1900, Y0 + 900),
            Point(X0 + 100, Y0 + 900),
        ],
        crs=CRS,
    )
    cells = gpd.GeoDataFrame(
        {
            "cell_id": ["c1", "c2", "c3"],
            "population": [10, 20, 5],
            "municipality_ags": ["07231001", "07231001", "07231002"],
            "vg_ars": ["072310000"] * 3,
        },
        geometry=[Point(X0 + 150, Y0 + 150), Point(X0 + 500, Y0 + 500), Point(X0 + 1500, Y0 + 500)],
        crs=CRS,
    )
    gpkg = interim / f"{REGION}.gpkg"
    for name, gdf in [
        ("municipalities", muni),
        ("vg", vg),
        ("district", district),
        ("aeds", aeds),
        ("cells", cells),
    ]:
        gdf.to_file(gpkg, layer=name, driver="GPKG")
    (interim / f"{REGION}_fetch_report.json").write_text(
        json.dumps(
            {
                "osm": {"snapshot_file": "osm_aed_testland_2026-11-01.json"},
                "attributions": {"census": "© Zensus-Test", "bkg": "© BKG-Test"},
            }
        ),
        encoding="utf-8",
    )

    def metric_rows(level: str, ids: list[tuple[str, str, int, float]]) -> pd.DataFrame:
        rows = []
        for ident, name, pop, base in ids:
            for radius in RADII:
                for si, scen in enumerate(SCENARIOS):
                    rate = min(1.0, base * (radius / 100) * (1 - 0.3 * si))
                    rows.append(
                        {
                            "level": level,
                            "id": ident,
                            "name": name,
                            "radius_m": radius,
                            "scenario": scen,
                            "population": pop,
                            "covered_population": round(rate * pop),
                            "coverage_rate": rate,
                            "mean_distance_m": 250.0,
                            "median_distance_m": 200.0,
                            "aeds_in_area": 1,
                            "aeds_per_10k": 3.3,
                            "share_aeds_missing_info": 0.5,
                            "share_access_unknown": 0.5,
                        }
                    )
        return pd.DataFrame(rows)

    metric_rows(
        "municipality", [("07231001", "Alt-Dorf", 30, 0.2), ("07231002", "Neu-Stadt", 20, 0.1)]
    ).to_csv(processed / "metrics_municipality.csv", index=False)
    metric_rows("vg", [("072310000", "VG Test", 50, 0.15)]).to_csv(
        processed / "metrics_vg.csv", index=False
    )
    metric_rows("district", [("07231", "Testkreis", 50, 0.15)]).to_csv(
        processed / "metrics_district.csv", index=False
    )

    if wide:
        pd.DataFrame(
            {
                "cell_id": ["c1", "c2", "c3"],
                "dist_all": [50.0, 400.0, 100.0],
                "dist_night_strict": [50.0, 400.0, float("nan")],
                "dist_night_optimistic": [50.0, 400.0, 900.0],
            }
        ).to_csv(processed / "cell_coverage.csv", index=False)
    else:
        rows = []
        for cid, d in [
            ("c1", [50.0, 50.0, 50.0]),
            ("c2", [400.0, 400.0, 400.0]),
            ("c3", [100.0, 900.0, 900.0]),
        ]:
            rows += [
                {"cell_id": cid, "scenario": s, "distance_m": v}
                for s, v in zip(SCENARIOS, d, strict=True)
            ]
        pd.DataFrame(rows).to_csv(processed / "cell_coverage.csv", index=False)

    def opt(variant: str, scope: str, ids: list[str], ks: int) -> None:
        rows = []
        for sid in ids:
            for radius in RADII:
                for k in range(1, ks + 1):
                    rows.append(
                        {
                            "scope_id": sid,
                            "radius_m": radius,
                            "scenario": "all",
                            "rank": k,
                            "x": X0,
                            "y": Y0,
                            "lon": 6.9 + k / 1000,
                            "lat": 49.9,
                            "label": f"Ort {k}",
                            "added_population": 10 - k,
                            "cumulative_covered": 10 * k,
                            "cumulative_rate": 0.1 * k,
                        }
                    )
        pd.DataFrame(rows).to_csv(processed / f"optimize_{variant}_{scope}.csv", index=False)

    opt("A", "district", ["07231"], 5)
    opt("A", "municipality", ["07231001", "07231002"], 3)
    opt("B", "district", ["07231"], 4)
    return interim, processed, out


def _export(tmp_path: Path, **kw: object) -> Path:
    interim, processed, out = _make_inputs(tmp_path, **kw)  # type: ignore[arg-type]
    return export_region(
        region_key=REGION,
        region_name="Testland",
        interim_dir=interim,
        processed_dir=processed,
        out_dir=out,
        detour_factor=1.3,
        attribution_defaults=["© Default-Test"],
        generated_at="2026-01-01T00:00:00Z",
    )


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_files_written(tmp_path: Path) -> None:
    region_dir = _export(tmp_path)
    names = {p.name for p in region_dir.iterdir()}
    assert {
        "municipalities.geojson",
        "aeds.geojson",
        "metrics.json",
        "recommendations.json",
        "meta.json",
    } <= names
    for scen in SCENARIOS:
        for radius in RADII:
            assert f"gaps_{scen}_{radius}.json" in names
    index = _load(region_dir.parent / "regions.json")
    assert index["regions"][0]["key"] == REGION


def test_municipalities_wgs84_rounded(tmp_path: Path) -> None:
    gj = _load(_export(tmp_path) / "municipalities.geojson")
    assert len(gj["features"]) == 2
    props = gj["features"][0]["properties"]
    assert props["ags"] == "07231001" and props["name"] == "Alt-Dorf"
    assert props["vg_ars"] == "072310000" and props["population"] == 30
    lon, lat = gj["features"][0]["geometry"]["coordinates"][0][0]
    assert 5 < lon < 10 and 47 < lat < 52  # WGS84, not metres
    assert lon == round(lon, 5) and lat == round(lat, 5)


def test_aeds_properties_and_scenarios(tmp_path: Path) -> None:
    feats = _load(_export(tmp_path) / "aeds.geojson")["features"]
    by_id = {f["properties"]["osm_id"]: f["properties"] for f in feats}
    assert by_id[1]["scenarios"] == ["all", "night_strict", "night_optimistic"]
    assert by_id[2]["scenarios"] == ["all"]
    assert by_id[3]["scenarios"] == ["all", "night_optimistic"]  # no hours, indoor=no
    assert by_id[4]["scenarios"] == [] and by_id[4]["is_public"] is False
    assert by_id[1]["osm_url"].endswith("/node/1") and by_id[2]["defibrillator_location"] is None
    assert set(by_id[1]) >= {
        "access_class",
        "opening_hours",
        "indoor",
        "level",
        "operator",
        "description",
        "check_date",
        "survey_date",
        "defibrillator_location",
    }


def test_metrics_nested_with_rank(tmp_path: Path) -> None:
    m = _load(_export(tmp_path) / "metrics.json")["levels"]
    alt = m["municipality"]["07231001"]
    assert alt["name"] == "Alt-Dorf"
    entry = alt["radii"]["100"]["all"]
    assert entry["coverage_rate"] == pytest.approx(0.2) and entry["rank"] == 1
    assert m["municipality"]["07231002"]["radii"]["100"]["all"]["rank"] == 2
    assert entry["rank_of"] == 2
    assert set(m) == {"municipality", "vg", "district"}
    assert "night_strict" in alt["radii"]["300"]


@pytest.mark.parametrize("wide", [False, True])
def test_gaps_uncovered_populated_cells(tmp_path: Path, wide: bool) -> None:
    region_dir = _export(tmp_path, wide=wide)
    g100 = _load(region_dir / "gaps_all_100.json")["cells"]
    assert [row[2] for row in g100] == [20]  # c2 only (400 m > 100 m)
    assert _load(region_dir / "gaps_all_300.json")["cells"][0][2] == 20
    strict = _load(region_dir / "gaps_night_strict_100.json")["cells"]
    assert sorted(row[2] for row in strict) == [5, 20]
    assert all(len(row) == 3 and 5 < row[0] < 10 for row in strict)


def test_recommendations_structure(tmp_path: Path) -> None:
    rec = _load(_export(tmp_path) / "recommendations.json")
    assert len(rec["district"]["A"]["07231"]["300"]["all"]) == 5
    assert len(rec["district"]["B"]["07231"]["100"]["all"]) == 4
    top3 = rec["municipality"]["A"]["07231001"]["100"]["all"]
    assert [r["rank"] for r in top3] == [1, 2, 3]
    assert top3[0]["added_population"] == 9 and top3[0]["label"] == "Ort 1"
    assert "B" not in rec["municipality"]  # no B municipality file in the fixture


def test_meta(tmp_path: Path) -> None:
    meta = _load(_export(tmp_path) / "meta.json")
    assert meta["region"] == REGION and meta["name"] == "Testland"
    assert meta["snapshot_date"] == "2026-11-01"
    assert meta["census_date"] == "15.05.2022"
    assert meta["radii_m"] == RADII and meta["scenarios"] == SCENARIOS
    assert meta["detour_factor"] == 1.3 and meta["generated_at"] == "2026-01-01T00:00:00Z"
    atts = " ".join(meta["attributions"])
    assert "OpenStreetMap-Mitwirkende" in atts and "Zensus-Test" in atts and "Default-Test" in atts
    stats = meta["aed_stats"]
    assert stats["public_in_region"] == 3
    assert stats["by_access_class"] == {"24/7": 1, "restricted": 1, "unknown": 1}
    assert stats["share_access_unknown"] == pytest.approx(1 / 3)


def test_missing_inputs_give_german_error(tmp_path: Path) -> None:
    with pytest.raises(ExportError, match="Eingabedateien fehlen"):
        export_region(
            region_key=REGION,
            region_name="X",
            interim_dir=tmp_path / "a",
            processed_dir=tmp_path / "b",
            out_dir=tmp_path / "c",
        )


def test_missing_metrics_give_german_error(tmp_path: Path) -> None:
    interim, processed, out = _make_inputs(tmp_path)
    (processed / "metrics_vg.csv").unlink()
    with pytest.raises(ExportError, match="Kennzahlen-Datei fehlt"):
        export_region(
            region_key=REGION,
            region_name="X",
            interim_dir=interim,
            processed_dir=processed,
            out_dir=out,
        )


def test_missing_optimize_gives_german_error(tmp_path: Path) -> None:
    interim, processed, out = _make_inputs(tmp_path)
    for p in processed.glob("optimize_*.csv"):
        p.unlink()
    with pytest.raises(ExportError, match="Optimierer"):
        export_region(
            region_key=REGION,
            region_name="X",
            interim_dir=interim,
            processed_dir=processed,
            out_dir=out,
        )
