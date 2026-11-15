"""Tests for OSM parsing and snapshot handling. SYNTHETIC data, no network."""

import json

import pytest

from pipeline import fetch_osm
from pipeline.config import load_params

PARAMS = load_params()
KEEP = PARAMS.osm["aed_tags_to_keep"]
EXCL = PARAMS.coverage["excluded_access_values"]

# SYNTHETIC elements, not real OSM data
ELEMENTS = [
    {
        "type": "node",
        "id": 1,
        "lat": 49.9,
        "lon": 6.9,
        "tags": {"emergency": "defibrillator", "opening_hours": "24/7", "access": "yes"},
    },
    {
        "type": "way",
        "id": 2,
        "center": {"lat": 49.91, "lon": 6.91},
        "tags": {
            "emergency": "defibrillator",
            "opening_hours": "Mo-Fr 08:00-16:00",
            "access": "private",
            "defibrillator:location": "Foyer",
        },
    },
    {"type": "node", "id": 3, "lat": 49.92, "lon": 6.92, "tags": {"emergency": "defibrillator"}},
    {"type": "relation", "id": 4, "tags": {"emergency": "defibrillator"}},  # no coordinates
]


def test_parse_aed_elements():
    gdf = fetch_osm.parse_aed_elements(ELEMENTS, KEEP, EXCL)
    assert list(gdf["osm_id"]) == [1, 2, 3]  # element without coordinates skipped
    assert gdf.crs.to_epsg() == 4326
    way = gdf[gdf.osm_id == 2].iloc[0]
    assert (way.geometry.x, way.geometry.y) == (6.91, 49.91)  # center of way
    assert way["defibrillator_location"] == "Foyer"
    assert way["osm_url"] == "https://www.openstreetmap.org/way/2"


def test_access_class_and_is_public():
    gdf = fetch_osm.parse_aed_elements(ELEMENTS, KEEP, EXCL).set_index("osm_id")
    assert gdf.loc[1, "access_class"] == "24/7"
    assert gdf.loc[2, "access_class"] == "restricted"
    assert gdf.loc[3, "access_class"] == "unknown"
    assert bool(gdf.loc[1, "is_public"]) is True
    assert bool(gdf.loc[2, "is_public"]) is False  # access=private
    assert bool(gdf.loc[3, "is_public"]) is True  # access missing
    assert fetch_osm.is_public({"access": "no"}, EXCL) is False


def test_parse_empty():
    gdf = fetch_osm.parse_aed_elements([], KEEP, EXCL)
    assert len(gdf) == 0 and "access_class" in gdf.columns


def test_parse_candidates_category_and_center():
    tags = PARAMS.optimize["candidate_osm_tags"]
    els = [
        {"type": "node", "id": 10, "lat": 49.9, "lon": 6.9, "tags": {"amenity": "pharmacy"}},
        {
            "type": "way",
            "id": 11,
            "center": {"lat": 49.8, "lon": 6.8},
            "tags": {"amenity": "school", "name": "Testschule"},
        },
        {"type": "node", "id": 12, "lat": 49.7, "lon": 6.7, "tags": {"amenity": "cafe"}},
    ]
    gdf = fetch_osm.parse_candidate_elements(els, tags)
    assert list(gdf["category"]) == ["amenity=pharmacy", "amenity=school"]
    assert gdf.iloc[1]["name"] == "Testschule"


def test_queries_match_contract():
    bbox = (49.655, 6.6534, 50.1495, 7.2916)
    aed = fetch_osm.build_aed_query(bbox, 180)
    assert 'nwr["emergency"="defibrillator"](49.6550,6.6534,50.1495,7.2916);' in aed
    assert aed.startswith("[out:json][timeout:180];") and aed.rstrip().endswith("out center tags;")
    cand = fetch_osm.build_candidates_query(bbox, 180, PARAMS.optimize["candidate_osm_tags"])
    assert 'nwr["amenity"~"^(townhall|' in cand
    assert 'nwr["leisure"="sports_hall"]' in cand
    assert 'node["highway"="bus_stop"]' in cand
    assert fetch_osm.overpass_get_link(aed).startswith(fetch_osm.OVERPASS_GET_PREFIX + "%5Bout")


def test_select_snapshot_newest_and_configured(tmp_path):
    for d in ("2026-01-01", "2026-03-05"):
        (tmp_path / f"osm_aed_x_{d}.json").write_text("{}")
    assert fetch_osm.select_snapshot(tmp_path, "aed", "x", None)[0] == "2026-03-05"
    assert fetch_osm.select_snapshot(tmp_path, "aed", "x", "2026-01-01")[0] == "2026-01-01"
    assert fetch_osm.select_snapshot(tmp_path, "aed", "x", "2025-01-01") is None
    assert fetch_osm.select_snapshot(tmp_path, "candidates", "x", None) is None


def _failing_post(*args, **kwargs):
    raise fetch_osm.requests.ConnectionError("synthetic: unreachable")


def test_get_snapshot_failure_gives_german_manual_step(tmp_path):
    with pytest.raises(fetch_osm.OsmUnavailableError) as exc:
        fetch_osm.get_snapshot("aed", "QUERY", "x", PARAMS, tmp_path, post=_failing_post)
    msg = str(exc.value)
    assert "Manueller Schritt" in msg and "overpass-turbo.eu" in msg and "QUERY" in msg
    assert (tmp_path / "overpass_query_aed_x.overpassql").read_text() == "QUERY"


def test_get_snapshot_download_saves_raw_unchanged(tmp_path):
    body = b'{"elements": [], "osm3s": {"timestamp_osm_base": "T"}}'

    class Resp:
        content = body

        def raise_for_status(self):
            pass

    import datetime as dt

    snap = fetch_osm.get_snapshot(
        "aed", "Q", "x", PARAMS, tmp_path, today=dt.date(2026, 5, 1), post=lambda *a, **k: Resp()
    )
    saved = tmp_path / "osm_aed_x_2026-05-01.json"
    assert saved.read_bytes() == body and snap.source == "downloaded"
    assert snap.osm_base_timestamp == "T"
    # second call the same day: no download
    snap2 = fetch_osm.get_snapshot(
        "aed", "Q", "x", PARAMS, tmp_path, today=dt.date(2026, 5, 1), post=_failing_post
    )
    assert snap2.source == "existing"


def test_get_snapshot_falls_back_to_older(tmp_path):
    (tmp_path / "osm_aed_x_2026-01-01.json").write_text(json.dumps({"elements": []}))
    snap = fetch_osm.get_snapshot("aed", "Q", "x", PARAMS, tmp_path, post=_failing_post)
    assert snap.date == "2026-01-01"


def test_geojson_to_elements_overpass_turbo_export():
    """SYNTHETIC overpass-turbo GeoJSON export (node point and way polygon)."""
    from pipeline.fetch_osm import geojson_to_elements

    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "node/1",
                "properties": {"@id": "node/1", "emergency": "defibrillator", "access": "yes"},
                "geometry": {"type": "Point", "coordinates": [7.0, 50.0]},
            },
            {
                "type": "Feature",
                "id": "way/2",
                "properties": {"@id": "way/2", "emergency": "defibrillator"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[7.0, 50.0], [7.1, 50.0], [7.1, 50.1], [7.0, 50.1], [7.0, 50.0]]
                    ],
                },
            },
        ],
    }
    els = geojson_to_elements(fc)
    assert els[0] == {
        "type": "node",
        "id": 1,
        "tags": {"emergency": "defibrillator", "access": "yes"},
        "lat": 50.0,
        "lon": 7.0,
    }
    assert els[1]["type"] == "way" and "center" in els[1] and "@id" not in els[1]["tags"]
