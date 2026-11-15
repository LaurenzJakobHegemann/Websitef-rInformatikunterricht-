"""M1 orchestration: boundaries + census + OSM -> data/interim/<region>.gpkg and fetch report.

Boundaries and census are always processed first. If OSM snapshots are missing and cannot be
downloaded, everything else is still written (without the OSM layers) and
:class:`pipeline.fetch_osm.OsmUnavailableError` is raised at the end.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from typing import Any

import geopandas as gpd

from pipeline import fetch_osm, plausibility
from pipeline.config import INTERIM_DIR, RAW_DIR, Params, RegionConfig
from pipeline.fetch_boundaries import Boundaries, load_boundaries
from pipeline.fetch_osm import OsmSnapshot, OsmUnavailableError
from pipeline.load_census import Census, load_census

log = logging.getLogger(__name__)


def _prepare_aeds(
    snap: OsmSnapshot, bounds: Boundaries, params: Params, bbox: fetch_osm.Bbox
) -> tuple[gpd.GeoDataFrame, list[plausibility.CheckResult], list[dict[str, Any]]]:
    crs = params.crs["compute"]
    aeds = fetch_osm.parse_aed_elements(
        snap.elements or [],
        list(params.osm["aed_tags_to_keep"]),
        list(params.coverage["excluded_access_values"]),
    )
    checks = [plausibility.check_aed_count(len(aeds))]
    checks.append(plausibility.check_in_query_area(aeds.geometry.x, aeds.geometry.y, bbox))
    aeds = aeds.to_crs(crs)
    dist = float(params.plausibility["duplicate_distance_m"])
    ids = [f"{t}/{i}" for t, i in zip(aeds["osm_type"], aeds["osm_id"], strict=True)]
    keep, dups = plausibility.find_duplicates(aeds.geometry.x, aeds.geometry.y, ids, dist)
    if dups:
        log.warning("%d doppelte AEDs entfernt (Abstand ≤ %s m)", len(dups), dist)
    checks.append(plausibility.check_duplicates(dups, dist))
    aeds = aeds[keep].reset_index(drop=True)
    aeds["in_region"] = aeds.within(bounds.district.geometry.union_all()).to_numpy()
    return aeds, checks, dups


def _prepare_candidates(snap: OsmSnapshot, bounds: Boundaries, params: Params):
    cand = fetch_osm.parse_candidate_elements(
        snap.elements or [], params.optimize["candidate_osm_tags"]
    ).to_crs(params.crs["compute"])
    cand["in_region"] = cand.within(bounds.district.geometry.union_all()).to_numpy()
    return cand


def _snapshot_info(snap: OsmSnapshot | None) -> dict[str, Any]:
    if snap is None:
        return {"status": "missing"}
    return {
        "status": snap.source,
        "file": snap.path.name if snap.path else None,
        "snapshot_date": snap.date,
        "overpass_url": snap.url_used,
        "osm_base_timestamp": snap.osm_base_timestamp,
        "n_elements": len(snap.elements or []),
    }


def write_gpkg(path: Path, layers: dict[str, gpd.GeoDataFrame]) -> None:
    tmp = path.with_name(path.stem + ".tmp.gpkg")
    tmp.unlink(missing_ok=True)
    for name, gdf in layers.items():
        gdf.to_file(tmp, layer=name, driver="GPKG", engine="pyogrio", mode="a")
    path.unlink(missing_ok=True)
    tmp.replace(path)


def run(
    region_cfg: RegionConfig,
    params: Params,
    raw_dir: Path = RAW_DIR,
    interim_dir: Path = INTERIM_DIR,
) -> dict[str, Any]:
    region = region_cfg.key
    bounds: Boundaries = load_boundaries(region_cfg, params, raw_dir)
    census: Census = load_census(region_cfg, params, bounds, raw_dir)

    timeout_s = int(params.osm["timeout_s"])
    bbox = fetch_osm.compute_query_bbox(bounds.district, float(params.osm["query_buffer_m"]))
    log.info("Abfragegebiet (s,w,n,e): %s", ",".join(f"{v:.4f}" for v in bbox))
    queries = {
        "aed": fetch_osm.build_aed_query(bbox, timeout_s),
        "candidates": fetch_osm.build_candidates_query(
            bbox, timeout_s, params.optimize["candidate_osm_tags"]
        ),
    }
    snaps: dict[str, OsmSnapshot | None] = {}
    errors: list[OsmUnavailableError] = []
    for kind in fetch_osm.KINDS:
        try:
            snaps[kind] = fetch_osm.get_snapshot(kind, queries[kind], region, params, raw_dir)
        except OsmUnavailableError as exc:
            snaps[kind] = None
            errors.append(exc)

    checks = [
        plausibility.check_population(
            census.population_sum,
            region_cfg.official_population or int(bounds.district["ewz"].iloc[0]),
            float(params.plausibility["max_population_deviation_pct"]),
            reference=(
                "Zensus 2022 vs. amtliche Einwohnerzahl "
                f"{region_cfg.official_population_source or 'VG250 EWZ'}; Stichtage verschieden"
            ),
        )
    ]
    layers: dict[str, gpd.GeoDataFrame] = {
        "district": bounds.district,
        "municipalities": bounds.municipalities,
        "vg": bounds.vg,
        "cells": census.cells,
    }
    duplicates: list[dict[str, Any]] = []
    if snaps["aed"] is not None:
        layers["aeds"], aed_checks, duplicates = _prepare_aeds(snaps["aed"], bounds, params, bbox)
        checks += aed_checks
    if snaps["candidates"] is not None:
        layers["candidates"] = _prepare_candidates(snaps["candidates"], bounds, params)

    for c in checks:
        (log.info if c.passed else log.warning)(
            "Plausibilität %s: %s", "OK" if c.passed else "FEHLER", c.message
        )

    interim_dir.mkdir(parents=True, exist_ok=True)
    gpkg = interim_dir / f"{region}.gpkg"
    write_gpkg(gpkg, layers)
    report = {
        "region": region,
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "complete": not errors,
        "gpkg": gpkg.name,
        "layers": {k: len(v) for k, v in layers.items()},
        "snapshots": {k: _snapshot_info(v) for k, v in snaps.items()},
        "query_bbox_swne": list(bbox),
        "attributions": {
            "osm": fetch_osm.OSM_ATTRIBUTION,
            "census": params.census["attribution"],
            "boundaries": params.boundaries["attribution"],
        },
        "census": {
            "population_column_used": census.population_column,
            "csv": census.csv_name,
            "rows_read": census.n_rows_read,
            "n_cells": len(census.cells),
            "population_sum": census.population_sum,
        },
        "boundaries": {
            "source_file": bounds.source_file,
            "district": bounds.district["name"].iloc[0],
            "district_ags": bounds.district["ags"].iloc[0],
            "district_ewz": int(bounds.district["ewz"].iloc[0]),
            "n_municipalities": len(bounds.municipalities),
            "n_vg": len(bounds.vg),
            "warnings": bounds.warnings,
        },
        "plausibility": [c.to_dict() for c in checks],
        "duplicates_dropped": duplicates,
    }
    (interim_dir / f"{region}_fetch_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    log.info("Geschrieben: %s", gpkg)
    if errors:
        raise OsmUnavailableError(
            "\n\n".join(str(e) for e in errors) + "\n\nBevölkerung und Grenzen wurden verarbeitet "
            f"({gpkg.name}, ohne OSM-Ebenen).",
            missing=[k for e in errors for k in e.missing],
        )
    return report
