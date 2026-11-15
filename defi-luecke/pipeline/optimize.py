"""Site optimizer: greedy Maximal Covering Location Problem (SPEC section 5).

Existing AEDs of the scenario already cover some cells; the demand weight of a cell is its
population if it is NOT yet covered, else 0. Candidate sites cover all demand cells within the
radius (straight-line equivalent ``R / detour_factor``). Greedy is run once up to ``k_max``;
because greedy is nested, rank k of that run is the greedy solution for every k' <= k_max.
"""

from __future__ import annotations

import heapq
import itertools
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy import sparse
from scipy.spatial import cKDTree

from pipeline.config import Params, RegionConfig
from pipeline.coverage import (
    Layers,
    _area_index,
    coords,
    processed_dir,
    read_layers,
    scenario_distances,
)

MILESTONE = "M3"
OUTPUT_COLUMNS = [
    "scope_id",
    "radius_m",
    "scenario",
    "rank",
    "x",
    "y",
    "lon",
    "lat",
    "label",
    "added_population",
    "cumulative_covered",
    "cumulative_rate",
]
# relative slack so that "distance == R" is covered despite R / detour rounding
_EPS = 1e-9


def build_cover_matrix(
    cand_xy: np.ndarray, demand_xy: np.ndarray, radius_m: float, detour_factor: float
) -> sparse.csr_matrix:
    """Sparse boolean-like matrix (candidates x demand cells); 1 if the cell is covered."""
    cand_xy = np.asarray(cand_xy, dtype=float).reshape(-1, 2)
    demand_xy = np.asarray(demand_xy, dtype=float).reshape(-1, 2)
    n_c, n_d = len(cand_xy), len(demand_xy)
    if n_c == 0 or n_d == 0:
        return sparse.csr_matrix((n_c, n_d), dtype=np.int8)
    r = radius_m / detour_factor * (1 + _EPS)
    neighbours = cKDTree(demand_xy).query_ball_point(cand_xy, r)
    lengths = np.fromiter((len(x) for x in neighbours), dtype=np.int64, count=n_c)
    indices = np.fromiter(
        itertools.chain.from_iterable(neighbours), dtype=np.int32, count=int(lengths.sum())
    )
    indptr = np.concatenate([[0], np.cumsum(lengths)])
    matrix = sparse.csr_matrix(
        (np.ones(len(indices), dtype=np.int8), indices, indptr), shape=(n_c, n_d)
    )
    matrix.sort_indices()
    return matrix


def greedy(cover: sparse.csr_matrix, weights: np.ndarray, k: int) -> list[tuple[int, float]]:
    """Exact greedy for maximum coverage with lazy gain updates.

    Returns ``(candidate index, gain)`` per step; ties are broken by the lowest index. Stops
    early when no candidate adds weight. Stale gains are upper bounds (submodularity), so the
    first entry popped with an up-to-date gain is the exact greedy choice.
    """
    cover = sparse.csr_matrix(cover)
    remaining = np.asarray(weights, dtype=float).copy()
    if cover.shape[1] != len(remaining):
        raise ValueError("weights passen nicht zur Abdeckungsmatrix.")
    indptr, indices = cover.indptr, cover.indices
    gains = cover @ remaining
    heap = [(-g, i, 0) for i, g in enumerate(gains) if g > 0]
    heapq.heapify(heap)
    result: list[tuple[int, float]] = []
    step = 0
    while heap and len(result) < k:
        neg_gain, i, stamp = heapq.heappop(heap)
        if stamp == step:
            cols = indices[indptr[i] : indptr[i + 1]]
            result.append((i, -neg_gain))
            remaining[cols] = 0.0
            step += 1
            continue
        gain = float(remaining[indices[indptr[i] : indptr[i + 1]]].sum())
        if gain > 0:
            heapq.heappush(heap, (-gain, i, step))
    return result


def exact_max_cover(
    cover: sparse.csr_matrix, weights: np.ndarray, k: int
) -> tuple[float, tuple[int, ...]]:
    """Brute-force optimum for tiny instances (tests only)."""
    cover = sparse.csr_matrix(cover)
    w = np.asarray(weights, dtype=float)
    n = cover.shape[0]
    best, best_set = -1.0, ()
    for combo in itertools.combinations(range(n), min(k, n)):
        covered = np.asarray(cover[list(combo)].sum(axis=0)).ravel() > 0
        value = float(w[covered].sum())
        if value > best:
            best, best_set = value, combo
    return max(best, 0.0), best_set


def _rank_table(
    scope_id: str,
    radius: float,
    scenario: str,
    picks: list[tuple[int, float]],
    cand_xy: np.ndarray,
    labels: np.ndarray,
    base_covered: float,
    scope_pop: float,
    transformer: Transformer,
) -> pd.DataFrame:
    if not picks:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    idx = np.array([i for i, _ in picks])
    added = np.array([g for _, g in picks])
    x, y = cand_xy[idx, 0], cand_xy[idx, 1]
    lon, lat = transformer.transform(x, y)
    cumulative = base_covered + np.cumsum(added)
    return pd.DataFrame(
        {
            "scope_id": scope_id,
            "radius_m": radius,
            "scenario": scenario,
            "rank": np.arange(1, len(idx) + 1),
            "x": x,
            "y": y,
            "lon": lon,
            "lat": lat,
            "label": labels[idx],
            "added_population": added.astype(int),
            "cumulative_covered": cumulative.astype(int),
            "cumulative_rate": cumulative / scope_pop,
        }
    )


def optimize_scope(
    scope_id: str,
    cells_xy: np.ndarray,
    cells_pop: np.ndarray,
    cells_dist: np.ndarray,
    cand_xy: np.ndarray,
    cand_labels: np.ndarray,
    radius: float,
    scenario: str,
    detour_factor: float,
    k_max: int,
    transformer: Transformer,
) -> pd.DataFrame:
    """Greedy ranking for one scope (cells and candidates already restricted to it)."""
    scope_pop = float(cells_pop.sum())
    if scope_pop <= 0 or len(cand_xy) == 0:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    uncovered = cells_dist > radius
    base_covered = float(cells_pop[~uncovered].sum())
    demand_xy, weights = cells_xy[uncovered], cells_pop[uncovered].astype(float)
    cover = build_cover_matrix(cand_xy, demand_xy, radius, detour_factor)
    picks = greedy(cover, weights, k_max)
    return _rank_table(
        scope_id,
        radius,
        scenario,
        picks,
        cand_xy,
        cand_labels,
        base_covered,
        scope_pop,
        transformer,
    )


def _candidate_labels(candidates: gpd.GeoDataFrame) -> np.ndarray:
    name = candidates["name"] if "name" in candidates else pd.Series(None, index=candidates.index)
    cat = candidates["category"] if "category" in candidates else name
    empty = name.isna() | (name.astype("string").str.strip() == "")
    return name.where(~empty, cat).astype(object).to_numpy()


def optimize_layers(
    layers: Layers, params: Params, scenario: str = "all"
) -> dict[tuple[str, str], pd.DataFrame]:
    """Run all variants and scopes. Keys: (variant, scope)."""
    cov, opt = params.coverage, params.optimize
    detour = cov["detour_factor"]
    transformer = Transformer.from_crs(params.crs["compute"], params.crs["web"], always_xy=True)
    cells = layers.cells.reset_index(drop=True)
    cells_xy = coords(cells)
    pop = cells["population"].to_numpy(dtype=float)
    dist = scenario_distances(cells, layers.aeds.reset_index(drop=True), [scenario], detour)[
        scenario
    ]
    ags = cells["municipality_ags"].astype(str).to_numpy()
    muni = layers.municipalities.reset_index(drop=True)
    muni_ids = muni["ags"].astype(str).to_numpy()
    muni_names = dict(zip(muni_ids, muni["name"].astype(str), strict=True))
    cell_labels = np.array([muni_names.get(a, a) for a in ags], dtype=object)
    district_id = str(layers.district["ags"].iloc[0])

    candidates = layers.candidates.reset_index(drop=True)
    variants: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None] = {}
    for variant in opt["candidate_variants"]:
        if variant == "A":
            variants["A"] = (cells_xy, cell_labels, ags, np.ones(len(cells), dtype=bool))
        elif variant == "B":
            if len(candidates) == 0:
                warnings.warn(
                    "Kandidatenebene 'candidates' ist leer: Variante B wird übersprungen.",
                    UserWarning,
                    stacklevel=2,
                )
                variants["B"] = None
                continue
            in_muni = _area_index(candidates, muni)
            in_district = _area_index(candidates, layers.district.reset_index(drop=True)) >= 0
            c_ags = np.where(in_muni >= 0, muni_ids[np.clip(in_muni, 0, None)], "")
            variants["B"] = (coords(candidates), _candidate_labels(candidates), c_ags, in_district)
        else:
            raise ValueError(f"Unbekannte Kandidatenvariante: {variant}")

    out: dict[tuple[str, str], pd.DataFrame] = {}
    for variant, spec in variants.items():
        if spec is None:
            continue
        c_xy, c_labels, c_ags, c_in_district = spec
        for scope, k_max in (
            ("district", opt["k_max_district"]),
            ("municipality", opt["k_max_municipality"]),
        ):
            if scope == "district":
                scopes = [(district_id, np.ones(len(cells), dtype=bool), c_in_district)]
            else:
                scopes = [(m, ags == m, c_ags == m) for m in muni_ids]
            frames = []
            for scope_id, cell_mask, cand_mask in scopes:
                if not cell_mask.any() or not cand_mask.any():
                    continue
                for radius in cov["radii_m"]:
                    frames.append(
                        optimize_scope(
                            scope_id,
                            cells_xy[cell_mask],
                            pop[cell_mask],
                            dist[cell_mask],
                            c_xy[cand_mask],
                            c_labels[cand_mask],
                            radius,
                            scenario,
                            detour,
                            k_max,
                            transformer,
                        )
                    )
            frames = [f for f in frames if len(f)]
            out[(variant, scope)] = (
                pd.concat(frames, ignore_index=True)
                if frames
                else pd.DataFrame(columns=OUTPUT_COLUMNS)
            )
    return out


def run(region_cfg: RegionConfig, params: Params) -> None:
    """Write ``optimize_<variant>_<scope>.csv`` to ``data/processed/<region>/``."""
    layers = read_layers(region_cfg)
    results = optimize_layers(layers, params)
    out_dir = processed_dir(region_cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    for (variant, scope), table in results.items():
        table.to_csv(out_dir / f"optimize_{variant}_{scope}.csv", index=False)
    print(f"Optimierung abgeschlossen: {out_dir}")
