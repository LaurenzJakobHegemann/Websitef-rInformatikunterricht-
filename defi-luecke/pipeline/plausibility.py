"""Plausibility checks for the fetched data (SPEC section 10).

All functions are pure: they return :class:`CheckResult` objects and never raise on a failed
check. The caller logs and reports them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
from scipy.spatial import cKDTree


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_population(
    census_sum: int, official: int | None, max_deviation_pct: float, *, reference: str = ""
) -> CheckResult:
    """Census population sum vs. official population (deviation in percent of official)."""
    if not official:
        return CheckResult(
            "population_deviation",
            False,
            "Keine amtliche Einwohnerzahl vorhanden, Abweichung nicht prüfbar.",
            {"census_sum": int(census_sum)},
        )
    deviation = (census_sum - official) / official * 100
    passed = abs(deviation) <= max_deviation_pct
    ref = f" ({reference})" if reference else ""
    msg = (
        f"Zensus-Summe {census_sum} vs. amtlich {official}{ref}: "
        f"Abweichung {deviation:+.2f} % (Schwelle ±{max_deviation_pct} %)"
    )
    return CheckResult(
        "population_deviation",
        passed,
        msg,
        {
            "census_sum": int(census_sum),
            "official": int(official),
            "deviation_pct": round(deviation, 3),
            "threshold_pct": max_deviation_pct,
            "reference": reference,
        },
    )


def check_aed_count(n_aeds: int) -> CheckResult:
    return CheckResult(
        "aed_count_positive",
        n_aeds > 0,
        f"{n_aeds} AEDs im Snapshot" + ("" if n_aeds > 0 else " (erwartet: mehr als null)"),
        {"n_aeds": int(n_aeds)},
    )


def check_in_query_area(
    lon: np.ndarray, lat: np.ndarray, bbox: tuple[float, float, float, float]
) -> CheckResult:
    """All coordinates must lie inside the query bbox ``(south, west, north, east)``."""
    south, west, north, east = bbox
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    inside = (lon >= west) & (lon <= east) & (lat >= south) & (lat <= north)
    n_out = int((~inside).sum())
    return CheckResult(
        "coordinates_in_query_area",
        n_out == 0,
        f"{n_out} von {len(lon)} AED-Koordinaten außerhalb des Abfragegebiets",
        {"n_outside": n_out, "n_total": int(len(lon)), "bbox_swne": list(bbox)},
    )


def find_duplicates(
    x: np.ndarray, y: np.ndarray, ids: list[str], max_distance_m: float
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Find points closer than ``max_distance_m`` (projected metres).

    Keeps the first point (input order) and drops later ones. Returns a boolean keep mask and
    one record per dropped point.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    keep = np.ones(len(x), dtype=bool)
    if len(x) < 2:
        return keep, []
    tree = cKDTree(np.column_stack([x, y]))
    pairs = sorted(tree.query_pairs(max_distance_m))
    records: list[dict[str, Any]] = []
    for i, j in pairs:
        if not keep[i] or not keep[j]:
            continue
        keep[j] = False
        dist = float(np.hypot(x[i] - x[j], y[i] - y[j]))
        records.append({"kept": ids[i], "dropped": ids[j], "distance_m": round(dist, 2)})
    return keep, records


def check_duplicates(records: list[dict[str, Any]], max_distance_m: float) -> CheckResult:
    return CheckResult(
        "duplicate_aeds",
        len(records) == 0,
        f"{len(records)} doppelte AEDs (Abstand ≤ {max_distance_m} m) entfernt",
        {"n_dropped": len(records), "threshold_m": max_distance_m},
    )
