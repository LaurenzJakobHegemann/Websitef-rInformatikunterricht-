"""Export the pipeline results as static data files for the web app (SPEC section 7, M4).

Reads (see docs/schnittstellen.md)::

    <interim>/<region>.gpkg                 layers municipalities, vg, district, aeds, cells
    <interim>/<region>_fetch_report.json
    <processed>/<region>/metrics_<level>.csv
    <processed>/<region>/cell_coverage.(csv|parquet)
    <processed>/<region>/optimize_<variant>_<scope>.csv

Writes to ``<out>/<region>/`` (all coordinates WGS84, 5 decimals)::

    municipalities.geojson, aeds.geojson, metrics.json, recommendations.json,
    meta.json, gaps_<scenario>_<radius>.json

and the index ``<out>/regions.json`` (one level above the region folder).

Gaps are written as one small file per scenario and radius (``[lon, lat, population]``
triples) so the web app can load only the combination the user is looking at.
"""

from __future__ import annotations

import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import mapping

from pipeline.config import PROJECT_ROOT, Params, RegionConfig

MILESTONE = "M4"

LEVELS = ("municipality", "vg", "district")
VARIANTS = ("A", "B")
CENSUS_DATE = "15.05.2022"
DEFAULT_BOUNDARIES_DATE = "31.12.2025"  # VG250-EW Stand, docs/schnittstellen.md
OSM_ATTRIBUTION = "© OpenStreetMap-Mitwirkende (ODbL)"
DEFAULT_SCENARIOS = ("all", "night_strict", "night_optimistic")
COORD_DECIMALS = 5
SIMPLIFY_TOLERANCE_M = 20.0
EXCLUDED_ACCESS_DEFAULT = ("private", "no")
METRIC_FIELDS = (
    "population",
    "covered_population",
    "coverage_rate",
    "mean_distance_m",
    "median_distance_m",
    "aeds_in_area",
    "aeds_per_10k",
    "share_aeds_missing_info",
    "share_access_unknown",
)
DIST_COLUMN_CANDIDATES = (
    "effective_distance_m",
    "eff_distance_m",
    "distance_m",
    "dist_m",
    "distance",
    "dist",
)


class ExportError(Exception):
    """Problem while exporting. The message is German and shown to the user."""


# ----------------------------------------------------------------------------- helpers


def _clean(value: Any) -> Any:
    """Convert pandas/numpy scalars to plain JSON values; NaN/None/NA -> None."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    return value


def _round_coords(obj: Any) -> Any:
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(float(v), COORD_DECIMALS) for v in obj]
        return [_round_coords(o) for o in obj]
    return obj


def _feature(geom: Any, props: dict[str, Any]) -> dict[str, Any]:
    g = mapping(geom)
    return {
        "type": "Feature",
        "properties": {k: _clean(v) for k, v in props.items()},
        "geometry": {"type": g["type"], "coordinates": _round_coords(g["coordinates"])},
    }


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    try:
        return pd.read_csv(path, **kwargs)
    except Exception as exc:  # noqa: BLE001 - re-raised as German message
        raise ExportError(f"Datei {path} konnte nicht gelesen werden: {exc}") from exc


def _require_columns(df: pd.DataFrame, columns: tuple[str, ...], where: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ExportError(
            f"{where}: erwartete Spalten fehlen: {', '.join(missing)} "
            f"(vorhanden: {', '.join(map(str, df.columns))})."
        )


def _read_layer(gpkg: Path, layer: str) -> gpd.GeoDataFrame:
    try:
        return gpd.read_file(gpkg, layer=layer)
    except Exception as exc:  # noqa: BLE001
        raise ExportError(
            f"Ebene '{layer}' in {gpkg} fehlt oder ist nicht lesbar ({exc}). "
            "Bitte zuerst `python -m pipeline.cli fetch` ausführen."
        ) from exc


def _find_key(obj: Any, names: tuple[str, ...]) -> Any:
    """Depth-first search for the first dict key (case-insensitive) in ``names``."""
    lowered = {n.lower() for n in names}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in lowered and value not in (None, "", [], {}):
                return value
        for value in obj.values():
            found = _find_key(value, names)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_key(value, names)
            if found is not None:
                return found
    return None


def _attributions(report: dict[str, Any], defaults: list[str]) -> list[str]:
    found = _find_key(report, ("attributions", "attribution", "quellenvermerke", "quellenvermerk"))
    items: list[str] = []
    if isinstance(found, str):
        items = [found]
    elif isinstance(found, list):
        items = [str(x) for x in found if x]
    elif isinstance(found, dict):
        items = [str(v) for v in found.values() if isinstance(v, str) and v]
    result: list[str] = []
    for text in [OSM_ATTRIBUTION, *items, *defaults]:
        if text and text not in result and not any(text in r for r in result):
            result.append(text)
    return result


def _german_date(value: Any) -> str | None:
    """YYYY-MM-DD -> DD.MM.YYYY; other strings are passed through."""
    if not value:
        return None
    text = str(value)
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}" if m else text


def _snapshot_date(report: dict[str, Any]) -> str | None:
    direct = _find_key(report, ("snapshot_date", "osm_snapshot_date", "datenstand"))
    if direct:
        return str(direct)[:10]
    for text in _iter_strings(report):
        m = re.search(r"osm_aed_.*?(\d{4}-\d{2}-\d{2})", text)
        if m:
            return m.group(1)
    return None


def _iter_strings(obj: Any):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_strings(v)


# ------------------------------------------------------------------------ geometries


def _simplify_polygons(gdf: gpd.GeoDataFrame, tolerance_m: float) -> gpd.GeoDataFrame:
    """Simplify polygons in a metric CRS; neighbours keep shared borders if possible."""
    gdf = gdf.copy()
    geoms = gdf.geometry.to_numpy()
    try:
        simplified = shapely.coverage_simplify(geoms, tolerance_m)
    except Exception:  # noqa: BLE001 - invalid coverage (overlaps): fall back per polygon
        simplified = shapely.simplify(geoms, tolerance_m, preserve_topology=True)
    gdf.geometry = gpd.GeoSeries(simplified, index=gdf.index, crs=gdf.crs)
    return gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]


def _municipalities_geojson(
    muni: gpd.GeoDataFrame, populations: dict[str, int], tolerance_m: float
) -> dict[str, Any]:
    _require_columns(muni, ("ags", "name"), "Ebene 'municipalities'")
    muni = _simplify_polygons(muni, tolerance_m).to_crs(4326)
    features = []
    for _, row in muni.iterrows():
        ags = str(row["ags"])
        features.append(
            _feature(
                row.geometry,
                {
                    "ags": ags,
                    "name": row["name"],
                    "vg_ars": row.get("vg_ars"),
                    "population": populations.get(ags, row.get("ewz")),
                    "ewz": row.get("ewz"),
                },
            )
        )
    return {"type": "FeatureCollection", "features": features}


def _scenario_flags(aeds: gpd.GeoDataFrame, excluded: tuple[str, ...]) -> list[list[str]]:
    """Scenario filter from docs/schnittstellen.md, evaluated per AED."""
    result: list[list[str]] = []
    for _, row in aeds.iterrows():
        public = bool(row.get("is_public", True))
        strict = public and row.get("access_class") == "24/7"
        indoor = str(row.get("indoor") or "").strip().lower()
        hours = row.get("opening_hours")
        no_hours = hours is None or (isinstance(hours, float) and math.isnan(hours)) or hours == ""
        optimistic = strict or (public and no_hours and indoor == "no")
        flags = []
        if public:
            flags.append("all")
        if strict:
            flags.append("night_strict")
        if optimistic:
            flags.append("night_optimistic")
        result.append(flags)
    return result


AED_TAG_COLUMNS = (
    "defibrillator_location",
    "opening_hours",
    "indoor",
    "level",
    "operator",
    "description",
    "check_date",
    "survey_date",
)


def _aeds_geojson(aeds: gpd.GeoDataFrame, excluded: tuple[str, ...]) -> dict[str, Any]:
    _require_columns(aeds, ("osm_id", "access_class", "is_public"), "Ebene 'aeds'")
    flags = _scenario_flags(aeds, excluded)
    wgs = aeds.to_crs(4326)
    features = []
    for (_, row), scen in zip(wgs.iterrows(), flags, strict=True):
        if row.geometry is None or row.geometry.is_empty:
            continue
        osm_id = _clean(row["osm_id"])
        osm_type = _clean(row.get("osm_type")) or "node"
        url = _clean(row.get("osm_url")) or f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
        props: dict[str, Any] = {
            "osm_id": int(osm_id) if osm_id is not None else None,
            "osm_url": url,
            "access_class": row["access_class"],
            "is_public": bool(row["is_public"]),
            "in_region": bool(row.get("in_region", True)),
            "scenarios": scen,
        }
        for col in AED_TAG_COLUMNS:
            val = row.get(col)
            props[col] = None if _clean(val) in (None, "") else str(val)
        features.append(_feature(row.geometry, props))
    return {"type": "FeatureCollection", "features": features}


# --------------------------------------------------------------------------- metrics


def _load_metrics(processed: Path) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for level in LEVELS:
        path = processed / f"metrics_{level}.csv"
        if not path.is_file():
            raise ExportError(
                f"Kennzahlen-Datei fehlt: {path}. Bitte zuerst `python -m pipeline.cli coverage` "
                "ausführen."
            )
        df = _read_csv(path, dtype={"id": str})
        _require_columns(df, ("id", "name", "radius_m", "scenario", *METRIC_FIELDS), path.name)
        frames[level] = df
    return frames


def _metrics_json(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for level, df in frames.items():
        df = df.copy()
        df["radius_m"] = df["radius_m"].astype(int)
        # Rank by coverage within (radius, scenario); 1 = best, ties share the lowest rank.
        df["rank"] = df.groupby(["radius_m", "scenario"])["coverage_rate"].rank(
            method="min", ascending=False
        )
        df["rank_of"] = df.groupby(["radius_m", "scenario"])["coverage_rate"].transform("count")
        entries: dict[str, Any] = {}
        for ident, grp in df.groupby("id", sort=False):
            radii: dict[str, Any] = {}
            for row in grp.itertuples(index=False):
                m = {f: _clean(getattr(row, f)) for f in METRIC_FIELDS}
                m["rank"] = int(row.rank) if _clean(row.rank) is not None else None
                m["rank_of"] = int(row.rank_of)
                radii.setdefault(str(int(row.radius_m)), {})[row.scenario] = m
            entries[str(ident)] = {"name": _clean(grp["name"].iloc[0]), "radii": radii}
        out[level] = entries
    return out


# -------------------------------------------------------------------- cell coverage


def _load_cell_coverage(processed: Path) -> pd.DataFrame:
    csv, parquet = processed / "cell_coverage.csv", processed / "cell_coverage.parquet"
    if csv.is_file():
        df = _read_csv(csv, dtype={"cell_id": str})
    elif parquet.is_file():
        try:
            df = pd.read_parquet(parquet)
        except Exception as exc:  # noqa: BLE001
            raise ExportError(f"Datei {parquet} konnte nicht gelesen werden: {exc}") from exc
        df["cell_id"] = df["cell_id"].astype(str)
    else:
        raise ExportError(
            f"Zellabdeckung fehlt: {csv} (oder .parquet). Bitte zuerst "
            "`python -m pipeline.cli coverage` ausführen."
        )
    _require_columns(df, ("cell_id",), "cell_coverage")
    return df


def _cell_distances(cc: pd.DataFrame, scenarios: tuple[str, ...]) -> dict[str, pd.Series]:
    """Effective distance per cell and scenario, indexed by cell_id.

    Accepts the long format (``scenario`` plus a distance column) and the wide format
    (one distance column per scenario, scenario name contained in the column name).
    """
    result: dict[str, pd.Series] = {}
    if "scenario" in cc.columns:
        col = next((c for c in DIST_COLUMN_CANDIDATES if c in cc.columns), None)
        if col is None:
            raise ExportError(
                "cell_coverage: keine Distanzspalte gefunden "
                f"(erwartet eine von: {', '.join(DIST_COLUMN_CANDIDATES)})."
            )
        for scen, grp in cc.groupby("scenario"):
            result[str(scen)] = grp.set_index("cell_id")[col].astype(float)
        return result
    for scen in scenarios:
        pattern = re.compile(rf"(^|_){re.escape(scen)}($|_)")
        cols = [c for c in cc.columns if pattern.search(str(c)) and "dist" in str(c).lower()]
        if not cols:
            cols = [c for c in cc.columns if pattern.search(str(c))]
        if cols:
            result[scen] = cc.set_index("cell_id")[cols[0]].astype(float)
    if not result:
        raise ExportError(
            "cell_coverage: weder Spalte 'scenario' noch Distanzspalten je Szenario gefunden "
            f"(Spalten: {', '.join(map(str, cc.columns))})."
        )
    return result


def _write_gaps(
    out_dir: Path,
    cells: gpd.GeoDataFrame,
    distances: dict[str, pd.Series],
    radii: list[int],
    scenarios: list[str],
) -> list[dict[str, Any]]:
    _require_columns(cells, ("cell_id", "population"), "Ebene 'cells'")
    wgs = cells.to_crs(4326)
    lon = wgs.geometry.x.to_numpy()
    lat = wgs.geometry.y.to_numpy()
    ids = cells["cell_id"].astype(str).to_numpy()
    pops = cells["population"].to_numpy()
    written: list[dict[str, Any]] = []
    for scen in scenarios:
        series = distances.get(scen)
        if series is None:
            continue
        dist = pd.Series(
            [series.get(cid, math.nan) for cid in ids], index=range(len(ids)), dtype=float
        )
        for radius in radii:
            uncovered = (dist.isna() | (dist > radius)) & (pops > 0)
            rows = [
                [
                    round(float(lon[i]), COORD_DECIMALS),
                    round(float(lat[i]), COORD_DECIMALS),
                    int(pops[i]),
                ]
                for i in dist.index[uncovered]
            ]
            name = f"gaps_{scen}_{radius}.json"
            _write_json(
                out_dir / name,
                {
                    "scenario": scen,
                    "radius_m": radius,
                    "columns": ["lon", "lat", "population"],
                    "cells": rows,
                },
            )
            written.append({"scenario": scen, "radius_m": radius, "file": name, "cells": len(rows)})
    return written


# ----------------------------------------------------------------- recommendations


def _recommendations(processed: Path) -> tuple[dict[str, Any], list[str]]:
    rec: dict[str, Any] = {"district": {}, "municipality": {}}
    variants: list[str] = []
    for variant in VARIANTS:
        for scope in ("district", "municipality"):
            path = processed / f"optimize_{variant}_{scope}.csv"
            if not path.is_file():
                continue
            df = _read_csv(path, dtype={"scope_id": str})
            _require_columns(
                df,
                (
                    "scope_id",
                    "radius_m",
                    "scenario",
                    "rank",
                    "lon",
                    "lat",
                    "label",
                    "added_population",
                    "cumulative_covered",
                    "cumulative_rate",
                ),
                path.name,
            )
            if variant not in variants:
                variants.append(variant)
            df = df.sort_values(["scope_id", "radius_m", "scenario", "rank"])
            if scope == "municipality":
                df = df[df["rank"] <= 3]
            for (sid, radius, scen), grp in df.groupby(["scope_id", "radius_m", "scenario"]):
                items = [
                    {
                        "rank": int(r.rank),
                        "lon": round(float(r.lon), COORD_DECIMALS),
                        "lat": round(float(r.lat), COORD_DECIMALS),
                        "label": _clean(r.label),
                        "added_population": _clean(r.added_population),
                        "cumulative_covered": _clean(r.cumulative_covered),
                        "cumulative_rate": _clean(r.cumulative_rate),
                    }
                    for r in grp.itertuples(index=False)
                ]
                node = rec[scope].setdefault(variant, {}).setdefault(str(sid), {})
                node.setdefault(str(int(radius)), {})[str(scen)] = items
    if not variants:
        raise ExportError(
            f"Keine Optimierer-Ergebnisse gefunden (optimize_<A|B>_<district|municipality>.csv "
            f"in {processed}). Bitte zuerst `python -m pipeline.cli optimize` ausführen."
        )
    return rec, variants


# ---------------------------------------------------------------------------- main


def export_region(
    *,
    region_key: str,
    region_name: str,
    interim_dir: Path | str,
    processed_dir: Path | str,
    out_dir: Path | str,
    detour_factor: float | None = None,
    attribution_defaults: list[str] | None = None,
    excluded_access: tuple[str, ...] = EXCLUDED_ACCESS_DEFAULT,
    simplify_tolerance_m: float = SIMPLIFY_TOLERANCE_M,
    generated_at: str | None = None,
) -> Path:
    """Write all web data files for one region. ``out_dir`` is the root (``…/data``).

    Returns the region folder ``out_dir/<region_key>``.
    """
    interim = Path(interim_dir)
    processed = Path(processed_dir)
    out_root = Path(out_dir)

    gpkg = interim / f"{region_key}.gpkg"
    report_path = interim / f"{region_key}_fetch_report.json"
    missing = [p for p in (gpkg, report_path) if not p.is_file()]
    if missing:
        raise ExportError(
            "Eingabedateien fehlen: "
            + ", ".join(str(p) for p in missing)
            + ". Bitte zuerst `python -m pipeline.cli fetch` ausführen."
        )
    if not processed.is_dir():
        raise ExportError(
            f"Ergebnisordner fehlt: {processed}. Bitte zuerst `python -m pipeline.cli coverage` "
            "und `optimize` ausführen."
        )
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExportError(f"Fetch-Report {report_path} ist nicht lesbar: {exc}") from exc

    frames = _load_metrics(processed)
    cc = _load_cell_coverage(processed)
    recs, variants = _recommendations(processed)

    muni = _read_layer(gpkg, "municipalities")
    district = _read_layer(gpkg, "district")
    aeds = _read_layer(gpkg, "aeds")
    cells = _read_layer(gpkg, "cells")
    _read_layer(gpkg, "vg")  # existence check; vg shapes are not needed by the web app

    region_dir = out_root / region_key
    region_dir.mkdir(parents=True, exist_ok=True)

    metrics = _metrics_json(frames)
    mdf = frames["municipality"]
    base = mdf[(mdf["scenario"] == "all")].sort_values("radius_m").drop_duplicates("id")
    populations = {str(r.id): _clean(r.population) for r in base.itertuples(index=False)}

    radii = sorted({int(r) for r in frames["district"]["radius_m"]})
    scenarios = [s for s in DEFAULT_SCENARIOS if s in set(frames["district"]["scenario"])]
    scenarios += sorted(set(frames["district"]["scenario"]) - set(scenarios))

    _write_json(
        region_dir / "municipalities.geojson",
        _municipalities_geojson(muni, populations, simplify_tolerance_m),
    )
    _write_json(region_dir / "aeds.geojson", _aeds_geojson(aeds, excluded_access))
    _write_json(region_dir / "metrics.json", {"levels": metrics})
    _write_json(region_dir / "recommendations.json", recs)
    gaps = _write_gaps(region_dir, cells, _cell_distances(cc, tuple(scenarios)), radii, scenarios)

    # AED statistics: public AEDs inside the district (the ones counted in scenario "all").
    inside = aeds[aeds.get("in_region", True) & aeds["is_public"].astype(bool)]
    by_class = {
        c: int((inside["access_class"] == c).sum()) for c in ("24/7", "restricted", "unknown")
    }
    total_public = int(len(inside))
    district_wgs = district.to_crs(4326)
    minx, miny, maxx, maxy = (round(float(v), COORD_DECIMALS) for v in district_wgs.total_bounds)
    district_row = district.iloc[0]
    district_id = str(district_row.get("ags", ""))

    snapshot = _snapshot_date(report)
    boundaries = _find_key(report, ("boundaries_date", "boundaries_stand", "vg250_stand"))
    meta = {
        "region": region_key,
        "name": region_name,
        "district_id": district_id,
        "district_name": _clean(district_row.get("name")),
        "snapshot_date": snapshot,
        "census_date": CENSUS_DATE,
        "boundaries_date": _german_date(boundaries) or DEFAULT_BOUNDARIES_DATE,
        "attributions": _attributions(report, list(attribution_defaults or [])),
        "radii_m": radii,
        "scenarios": scenarios,
        "variants": variants,
        "detour_factor": detour_factor,
        "k_max_district": max(
            (
                int(r["rank"])
                for v in recs["district"].values()
                for s in v.values()
                for rad in s.values()
                for items in rad.values()
                for r in items
            ),
            default=0,
        ),
        "aed_stats": {
            "public_in_region": total_public,
            "by_access_class": by_class,
            "share_access_unknown": (by_class["unknown"] / total_public) if total_public else None,
            "total_in_file": int(len(aeds)),
        },
        "bbox": [minx, miny, maxx, maxy],
        "gaps": gaps,
        "generated_at": generated_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _write_json(region_dir / "meta.json", meta)
    _write_regions_index(out_root)
    return region_dir


def _write_regions_index(out_root: Path) -> None:
    entries = []
    for meta_path in sorted(out_root.glob("*/meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        entries.append(
            {
                "key": meta.get("region", meta_path.parent.name),
                "name": meta.get("name"),
                "snapshot_date": meta.get("snapshot_date"),
                "generated_at": meta.get("generated_at"),
            }
        )
    _write_json(out_root / "regions.json", {"regions": entries})


def run(region_cfg: RegionConfig, params: Params) -> Path:
    """CLI entry point: export with the default project paths."""
    try:
        return export_region(
            region_key=region_cfg.key,
            region_name=region_cfg.name,
            interim_dir=PROJECT_ROOT / "data" / "interim",
            processed_dir=PROJECT_ROOT / "data" / "processed" / region_cfg.key,
            out_dir=PROJECT_ROOT / "web" / "public" / "data",
            detour_factor=params.coverage.get("detour_factor"),
            attribution_defaults=_param_attributions(),
            excluded_access=tuple(params.coverage.get("excluded_access_values", ["private", "no"])),
        )
    except ExportError as exc:
        raise SystemExit(f"Fehler: {exc}") from exc


def _param_attributions() -> list[str]:
    """Attribution strings from params.yaml (Params has no census/boundaries section)."""
    import yaml

    try:
        raw = yaml.safe_load((PROJECT_ROOT / "config" / "params.yaml").read_text("utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    return [
        a
        for a in (
            (raw.get("census") or {}).get("attribution"),
            (raw.get("boundaries") or {}).get("attribution"),
        )
        if a
    ]
