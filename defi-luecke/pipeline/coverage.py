"""Coverage metrics (SPEC section 4, contract: docs/schnittstellen.md).

Nearest-AED distance per populated 100 m cell (straight line in EPSG:3035 times the detour
factor), coverage per radius and scenario, aggregated per municipality, Verbandsgemeinde and
district in long format.

Handling of unreachable cells: if a scenario has no AED at all, every distance is ``inf`` and no
cell is covered. Mean and median distance are computed over cells with a finite distance only and
are NaN if an area has none (i.e. only when the scenario has no AED anywhere).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
from scipy.spatial import cKDTree

from pipeline.config import PROJECT_ROOT, ConfigError, Params, RegionConfig

MILESTONE = "M2"

METRIC_COLUMNS = [
    "level",
    "id",
    "name",
    "radius_m",
    "scenario",
    "population",
    "covered_population",
    "coverage_rate",
    "mean_distance_m",
    "median_distance_m",
    "aeds_in_area",
    "aeds_per_10k",
    "share_aeds_missing_info",
    "share_access_unknown",
]

# level -> (polygon layer, id column in the layer, key column in the cells layer or None)
LEVELS: dict[str, tuple[str, str, str | None]] = {
    "municipality": ("municipalities", "ags", "municipality_ags"),
    "vg": ("vg", "ars", "vg_ars"),
    "district": ("district", "ags", None),
}


@dataclass
class Layers:
    """The layers of ``data/interim/<region>.gpkg`` (all EPSG:3035)."""

    aeds: gpd.GeoDataFrame
    cells: gpd.GeoDataFrame
    municipalities: gpd.GeoDataFrame
    vg: gpd.GeoDataFrame
    district: gpd.GeoDataFrame
    candidates: gpd.GeoDataFrame


def interim_path(region_cfg: RegionConfig) -> Path:
    return PROJECT_ROOT / "data" / "interim" / f"{region_cfg.key}.gpkg"


def processed_dir(region_cfg: RegionConfig) -> Path:
    return PROJECT_ROOT / "data" / "processed" / region_cfg.key


def read_layers(region_cfg: RegionConfig) -> Layers:
    """Read the interim GeoPackage; German error if it does not exist."""
    path = interim_path(region_cfg)
    if not path.is_file():
        raise ConfigError(
            f"Zwischendatei {path} nicht gefunden. Bitte zuerst 'fetch' ausführen "
            f"(python -m pipeline.cli fetch --region {region_cfg.key})."
        )
    available = {name for name, _ in pyogrio.list_layers(path)}
    required = ["aeds", "cells", "municipalities", "vg", "district"]
    missing = [n for n in required if n not in available]
    if missing:
        raise ConfigError(
            f"In {path} fehlen die Ebenen: {', '.join(missing)}. Bitte 'fetch' erneut ausführen."
        )
    data = {n: gpd.read_file(path, layer=n) for n in required}
    if "candidates" in available:
        data["candidates"] = gpd.read_file(path, layer="candidates")
    else:
        data["candidates"] = gpd.GeoDataFrame(
            {"name": [], "category": []}, geometry=[], crs=data["aeds"].crs
        )
    return Layers(**data)


def radius_from_round_trip(max_round_trip_s: float, walking_speed_m_per_s: float) -> float:
    """One-way distance in metres for a maximum round trip time.

    The person walks to the AED and back, so the one-way distance is
    ``speed * time / 2``.
    """
    if max_round_trip_s <= 0:
        raise ValueError("max_round_trip_s muss positiv sein.")
    if walking_speed_m_per_s <= 0:
        raise ValueError("walking_speed_m_per_s muss positiv sein.")
    return walking_speed_m_per_s * max_round_trip_s / 2


def effective_distance(straight_line_m: float, detour_factor: float) -> float:
    """Estimated walking distance: straight-line distance times the detour factor."""
    if straight_line_m < 0:
        raise ValueError("straight_line_m darf nicht negativ sein.")
    if detour_factor < 1:
        raise ValueError("detour_factor muss mindestens 1 sein.")
    return straight_line_m * detour_factor


# ---------------------------------------------------------------- scenarios


def _missing(series: pd.Series) -> pd.Series:
    """True where a tag is absent (NaN/None) or empty."""
    return series.isna() | (series.astype("string").str.strip() == "")


def _column(aeds: pd.DataFrame, name: str) -> pd.Series:
    if name in aeds.columns:
        return aeds[name]
    return pd.Series(pd.NA, index=aeds.index, dtype="object")


def classify_access(opening_hours: pd.Series) -> pd.Series:
    """Access class per AED: ``24/7``, ``restricted`` (other hours) or ``unknown``."""
    missing = _missing(opening_hours)
    out = pd.Series("restricted", index=opening_hours.index, dtype="object")
    out[opening_hours.astype("string").str.strip() == "24/7"] = "24/7"
    out[missing] = "unknown"
    return out


def filter_scenario(aeds: pd.DataFrame, scenario: str) -> pd.DataFrame:
    """AEDs that count in a scenario (contract: Szenariofilter)."""
    public = _column(aeds, "is_public").fillna(False).astype(bool)
    if scenario == "all":
        mask = public
    else:
        strict = public & (_column(aeds, "access_class") == "24/7")
        if scenario == "night_strict":
            mask = strict
        elif scenario == "night_optimistic":
            outdoor_no_hours = (
                public & _missing(_column(aeds, "opening_hours")) & (_column(aeds, "indoor") == "no")
            )
            mask = strict | outdoor_no_hours
        else:
            raise ValueError(f"Unbekanntes Szenario: {scenario}")
    return aeds[mask]


# ---------------------------------------------------------------- distances


def nearest_effective_distance(
    cell_xy: np.ndarray, aed_xy: np.ndarray, detour_factor: float
) -> np.ndarray:
    """Effective distance (straight line * detour factor) to the nearest AED per cell.

    Coordinates in a metric CRS (EPSG:3035). No AEDs -> ``inf`` for every cell.
    """
    if detour_factor < 1:
        raise ValueError("detour_factor muss mindestens 1 sein.")
    cell_xy = np.asarray(cell_xy, dtype=float).reshape(-1, 2)
    aed_xy = np.asarray(aed_xy, dtype=float).reshape(-1, 2)
    if len(aed_xy) == 0:
        return np.full(len(cell_xy), np.inf)
    dist, _ = cKDTree(aed_xy).query(cell_xy)
    return dist * detour_factor


def coords(gdf: gpd.GeoDataFrame) -> np.ndarray:
    return np.column_stack([gdf.geometry.x.to_numpy(), gdf.geometry.y.to_numpy()])


def scenario_distances(
    cells: gpd.GeoDataFrame, aeds: gpd.GeoDataFrame, scenarios: list[str], detour_factor: float
) -> dict[str, np.ndarray]:
    cell_xy = coords(cells)
    return {
        s: nearest_effective_distance(cell_xy, coords(filter_scenario(aeds, s)), detour_factor)
        for s in scenarios
    }


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    """Weighted median. Non-finite values and zero weights are ignored.

    The median is the value at which the cumulative weight reaches half of the total weight; if
    it hits exactly half, the mean of that value and the next one is returned (like numpy for an
    even count). NaN if no weight remains.
    """
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    keep = np.isfinite(v) & (w > 0)
    v, w = v[keep], w[keep]
    if len(v) == 0:
        return float("nan")
    order = np.argsort(v, kind="stable")
    v, w = v[order], w[order]
    cum = np.cumsum(w)
    half = cum[-1] / 2
    idx = int(np.searchsorted(cum, half, side="left"))
    if np.isclose(cum[idx], half) and idx + 1 < len(v):
        return float((v[idx] + v[idx + 1]) / 2)
    return float(v[idx])


# ---------------------------------------------------------------- metrics


def _area_index(points: gpd.GeoDataFrame, polygons: gpd.GeoDataFrame) -> np.ndarray:
    """Index of the containing polygon per point (-1 if none; first match on boundaries)."""
    pts = gpd.GeoDataFrame(geometry=points.geometry.values, crs=points.crs)
    polys = gpd.GeoDataFrame(geometry=polygons.geometry.values, crs=polygons.crs)
    joined = gpd.sjoin(pts, polys, how="inner", predicate="intersects")
    joined = joined[~joined.index.duplicated(keep="first")]
    out = np.full(len(points), -1, dtype=int)
    out[joined.index.to_numpy()] = joined["index_right"].to_numpy()
    return out


def compute_metrics(
    layers: Layers,
    params: Params,
    level: str,
    distances: dict[str, np.ndarray] | None = None,
) -> pd.DataFrame:
    """Metrics for one level in long format (contract: Kennzahlen-CSV)."""
    layer_name, id_col, cell_key = LEVELS[level]
    polygons = getattr(layers, layer_name).reset_index(drop=True)
    cfg = params.coverage
    scenarios = list(cfg["scenarios"])
    radii = list(cfg["radii_m"])
    n = len(polygons)
    ids = polygons[id_col].astype(str).to_numpy()
    names = polygons["name"].to_numpy() if "name" in polygons else ids

    cells = layers.cells.reset_index(drop=True)
    aeds = layers.aeds.reset_index(drop=True)
    if distances is None:
        distances = scenario_distances(cells, aeds, scenarios, cfg["detour_factor"])

    if cell_key is None:
        group = np.zeros(len(cells), dtype=int) if n else np.full(len(cells), -1)
    else:
        group = pd.Index(ids).get_indexer(cells[cell_key].astype("string").astype(object))
    pop = cells["population"].to_numpy(dtype=float)
    valid = group >= 0
    g, p = group[valid], pop[valid]
    population = np.bincount(g, weights=p, minlength=n)

    # cell positions per group, for the median
    order = np.argsort(g, kind="stable")
    bounds = np.concatenate([[0], np.cumsum(np.bincount(g, minlength=n))])

    aed_area = _area_index(aeds, polygons) if len(aeds) else np.zeros(0, dtype=int)
    frames = []
    for scenario in scenarios:
        d = distances[scenario][valid]
        finite = np.isfinite(d)
        wf = np.where(finite, p, 0.0)
        wsum = np.bincount(g, weights=wf, minlength=n)
        dsum = np.bincount(g, weights=wf * np.where(finite, d, 0.0), minlength=n)
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = np.where(wsum > 0, dsum / wsum, np.nan)
        median = np.full(n, np.nan)
        d_sorted, p_sorted = d[order], p[order]
        for i in range(n):
            lo, hi = bounds[i], bounds[i + 1]
            if hi > lo:
                median[i] = weighted_median(d_sorted[lo:hi], p_sorted[lo:hi])

        in_scn = filter_scenario(aeds, scenario).index.to_numpy()
        areas = aed_area[in_scn]
        areas = areas[areas >= 0]
        count = np.bincount(areas, minlength=n).astype(float)
        scn_aeds = aeds.loc[in_scn]
        scn_area = aed_area[in_scn]
        has = scn_area >= 0
        missing = (
            (_missing(_column(scn_aeds, "access")) | _missing(_column(scn_aeds, "opening_hours")))
            .to_numpy()[has]
            .astype(float)
        )
        unknown = (_column(scn_aeds, "access_class") == "unknown").to_numpy()[has].astype(float)
        with np.errstate(invalid="ignore", divide="ignore"):
            share_missing = np.where(
                count > 0, np.bincount(scn_area[has], weights=missing, minlength=n) / count, np.nan
            )
            share_unknown = np.where(
                count > 0, np.bincount(scn_area[has], weights=unknown, minlength=n) / count, np.nan
            )
            per10k = np.where(population > 0, count / population * 10_000, np.nan)

        for radius in radii:
            covered = np.bincount(g, weights=p * (d <= radius), minlength=n)
            with np.errstate(invalid="ignore", divide="ignore"):
                rate = np.where(population > 0, covered / population, np.nan)
            frames.append(
                pd.DataFrame(
                    {
                        "level": level,
                        "id": ids,
                        "name": names,
                        "radius_m": radius,
                        "scenario": scenario,
                        "population": population.astype(int),
                        "covered_population": covered.astype(int),
                        "coverage_rate": rate,
                        "mean_distance_m": mean,
                        "median_distance_m": median,
                        "aeds_in_area": count.astype(int),
                        "aeds_per_10k": per10k,
                        "share_aeds_missing_info": share_missing,
                        "share_access_unknown": share_unknown,
                    }
                )
            )
    if not frames:
        return pd.DataFrame(columns=METRIC_COLUMNS)
    return pd.concat(frames, ignore_index=True)[METRIC_COLUMNS]


def compute_cell_coverage(
    cells: gpd.GeoDataFrame, distances: dict[str, np.ndarray]
) -> pd.DataFrame:
    xy = coords(cells)
    out = pd.DataFrame(
        {
            "cell_id": cells["cell_id"].to_numpy(),
            "x": xy[:, 0],
            "y": xy[:, 1],
            "population": cells["population"].to_numpy(),
            "municipality_ags": cells["municipality_ags"].to_numpy(),
        }
    )
    for scenario, d in distances.items():
        out[f"distance_m_{scenario}"] = d
    return out


def run(region_cfg: RegionConfig, params: Params) -> None:
    """Compute metrics for all levels and write the CSVs to ``data/processed/<region>/``."""
    layers = read_layers(region_cfg)
    cfg = params.coverage
    distances = scenario_distances(
        layers.cells, layers.aeds, list(cfg["scenarios"]), cfg["detour_factor"]
    )
    out_dir = processed_dir(region_cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    for level in LEVELS:
        compute_metrics(layers, params, level, distances).to_csv(
            out_dir / f"metrics_{level}.csv", index=False
        )
    compute_cell_coverage(layers.cells, distances).to_csv(out_dir / "cell_coverage.csv", index=False)
    print(f"Abdeckung berechnet: {out_dir}")
