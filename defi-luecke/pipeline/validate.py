"""Validate the completeness of the OSM AED data against a field survey (SPEC section 6).

Per surveyed sub-area the surveyed AEDs are matched one-to-one to the OSM AEDs within a
tolerance. Recall (share of real AEDs that are in OSM) and precision (share of OSM AEDs that
were confirmed on site) are reported with Wilson score intervals. If a second independent list
exists, the Chapman estimator gives an estimate of the true number of AEDs.

Decision on non-public AEDs: survey rows with ``access_type == "nicht öffentlich"`` are not
counted as real public AEDs, because the model and OSM (``is_public``) only describe publicly
accessible devices. They are excluded from recall and listed in the matches CSV. Likewise only
OSM AEDs with ``is_public`` enter precision.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.optimize import linear_sum_assignment
from scipy.stats import norm

from pipeline.config import PROJECT_ROOT, Params, RegionConfig

SURVEY_COLUMNS = [
    "region",
    "lat",
    "lon",
    "location_description",
    "access_type",
    "found_on",
    "method",
    "photo_ref",
    "notes",
]
NON_PUBLIC = "nicht öffentlich"
LIST2_SUFFIX = "_list2"
_BIG = 1e9


class ValidationError(Exception):
    """Problem with survey input. The message is German."""


# ---------------------------------------------------------------- statistics


def wilson_interval(k: int, n: int, confidence: float = 0.95) -> tuple[float, float, float]:
    """Wilson score interval for a proportion k/n. Returns (estimate, low, high).

    For n == 0 the proportion is undefined: (nan, nan, nan).
    """
    if n <= 0:
        return (math.nan, math.nan, math.nan)
    if not 0 <= k <= n:
        raise ValueError("k muss zwischen 0 und n liegen")
    z = float(norm.ppf(0.5 + confidence / 2))
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def chapman_estimate(
    n1: int, n2: int, m: int, confidence: float = 0.95
) -> dict[str, float | int]:
    """Chapman estimator for capture-recapture with two independent lists.

    N = (n1+1)(n2+1)/(m+1) - 1,
    Var = (n1+1)(n2+1)(n1-m)(n2-m) / ((m+1)^2 (m+2)).
    The interval is a normal approximation, truncated below at the number of distinct
    known AEDs n1 + n2 - m.
    """
    if m > min(n1, n2):
        raise ValueError("Überschneidung m darf nicht größer als n1 oder n2 sein")
    n_hat = (n1 + 1) * (n2 + 1) / (m + 1) - 1
    var = (n1 + 1) * (n2 + 1) * (n1 - m) * (n2 - m) / ((m + 1) ** 2 * (m + 2))
    se = math.sqrt(var)
    z = float(norm.ppf(0.5 + confidence / 2))
    known = n1 + n2 - m
    return {
        "n1": n1,
        "n2": n2,
        "m": m,
        "estimate": n_hat,
        "variance": var,
        "std_error": se,
        "ci_low": max(float(known), n_hat - z * se),
        "ci_high": n_hat + z * se,
        "known_distinct": known,
    }


# ------------------------------------------------------------------ matching


def to_laea(lon: Any, lat: Any) -> np.ndarray:
    """WGS84 lon/lat -> EPSG:3035 (x, y), shape (n, 2)."""
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3035", always_xy=True)
    x, y = transformer.transform(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))
    return np.column_stack([np.atleast_1d(x), np.atleast_1d(y)])


def match_points(
    a_xy: np.ndarray, b_xy: np.ndarray, tolerance_m: float
) -> list[tuple[int, int, float]]:
    """Optimal one-to-one assignment of points a to points b within a tolerance.

    Pairs farther apart than the tolerance are infeasible. Among all assignments the one with
    the most feasible pairs wins, then the smallest total distance.
    Returns (index_a, index_b, distance_m) triples.
    """
    a_xy = np.asarray(a_xy, dtype=float).reshape(-1, 2)
    b_xy = np.asarray(b_xy, dtype=float).reshape(-1, 2)
    if len(a_xy) == 0 or len(b_xy) == 0:
        return []
    dist = np.hypot(a_xy[:, None, 0] - b_xy[None, :, 0], a_xy[:, None, 1] - b_xy[None, :, 1])
    cost = np.where(dist <= tolerance_m, dist, _BIG)
    rows, cols = linear_sum_assignment(cost)
    return [(int(r), int(c), float(dist[r, c])) for r, c in zip(rows, cols) if cost[r, c] < _BIG]


# ------------------------------------------------------------------ reading


def read_survey(path: Path | str) -> pd.DataFrame:
    """Read a survey CSV and check the columns (template: validation/field_survey_template.csv)."""
    path = Path(path)
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    missing = [c for c in SURVEY_COLUMNS if c not in df.columns]
    if missing:
        raise ValidationError(
            f"Erhebungsdatei {path.name}: fehlende Spalten: {', '.join(missing)}. "
            f"Erwartet werden: {', '.join(SURVEY_COLUMNS)}"
        )
    for col in ("lat", "lon"):
        converted = pd.to_numeric(df[col].str.replace(",", ".", regex=False), errors="coerce")
        bad = df.index[converted.isna()].tolist()
        if bad:
            rows = ", ".join(str(i + 2) for i in bad[:10])
            raise ValidationError(
                f"Erhebungsdatei {path.name}: Spalte '{col}' enthält ungültige Werte "
                f"(Zeile(n) {rows} in der Datei)."
            )
        df[col] = converted
    return df


def find_survey_files(survey_dir: Path | str, region: str) -> dict[str, Path]:
    """Survey files ``<region>_<area>.csv`` as {area: path}; ``*_list2.csv`` are excluded."""
    survey_dir = Path(survey_dir)
    found: dict[str, Path] = {}
    if not survey_dir.is_dir():
        return found
    prefix = f"{region}_"
    for path in sorted(survey_dir.glob(f"{prefix}*.csv")):
        area = path.stem[len(prefix) :]
        if area and not area.endswith(LIST2_SUFFIX):
            found[area] = path
    return found


def load_osm_aeds(gpkg: Path | str, municipality_ags: list[str]):
    """Public OSM AEDs (EPSG:3035) inside the given municipalities."""
    import geopandas as gpd

    aeds = gpd.read_file(gpkg, layer="aeds")
    munis = gpd.read_file(gpkg, layer="municipalities")
    selected = munis[munis["ags"].astype(str).isin([str(a) for a in municipality_ags])]
    if selected.empty:
        raise ValidationError(
            "Keine der konfigurierten Gemeinden (validation.areas) im GeoPackage gefunden: "
            + ", ".join(map(str, municipality_ags))
        )
    area = selected.geometry.union_all()
    if "is_public" in aeds.columns:
        aeds = aeds[aeds["is_public"].astype(bool)]
    return aeds[aeds.geometry.intersects(area)].reset_index(drop=True)


# ------------------------------------------------------------------ core run


def _interval_dict(k: int, n: int, confidence: float) -> dict[str, Any]:
    p, lo, hi = wilson_interval(k, n, confidence)
    return {
        "k": k,
        "n": n,
        "value": None if math.isnan(p) else p,
        "ci_low": None if math.isnan(lo) else lo,
        "ci_high": None if math.isnan(hi) else hi,
    }


def validate_area(
    survey: pd.DataFrame,
    osm_aeds,
    tolerance_m: float,
    confidence: float,
    list2: pd.DataFrame | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Compute the validation result for one area. ``osm_aeds`` is a GeoDataFrame (EPSG:3035)."""
    public = survey[survey["access_type"].str.strip() != NON_PUBLIC].reset_index(drop=True)
    excluded = survey[survey["access_type"].str.strip() == NON_PUBLIC]
    s_xy = to_laea(public["lon"], public["lat"])
    o_xy = np.column_stack([osm_aeds.geometry.x, osm_aeds.geometry.y]) if len(osm_aeds) else None
    pairs = match_points(s_xy, o_xy if o_xy is not None else np.empty((0, 2)), tolerance_m)
    pair_by_s = {i: (j, d) for i, j, d in pairs}
    matched_osm = {j for _, j, _ in pairs}

    def osm_id(j: int) -> str:
        row = osm_aeds.iloc[j]
        return f"{row.get('osm_type', '')}/{row.get('osm_id', '')}"

    rows: list[dict[str, Any]] = []
    for i, srow in public.iterrows():
        j, d = pair_by_s.get(int(i), (None, None))
        rows.append(
            {
                "status": "zugeordnet" if j is not None else "nur_erhebung",
                "survey_row": int(i),
                "lat": srow["lat"],
                "lon": srow["lon"],
                "location_description": srow["location_description"],
                "access_type": srow["access_type"],
                "osm_ref": osm_id(j) if j is not None else "",
                "distance_m": round(d, 1) if d is not None else None,
            }
        )
    for j in range(len(osm_aeds)):
        if j not in matched_osm:
            wgs = osm_aeds.iloc[[j]].to_crs(4326).geometry.iloc[0]
            rows.append(
                {
                    "status": "nur_osm",
                    "survey_row": None,
                    "lat": wgs.y,
                    "lon": wgs.x,
                    "location_description": "",
                    "access_type": "",
                    "osm_ref": osm_id(j),
                    "distance_m": None,
                }
            )
    for _, srow in excluded.iterrows():
        rows.append(
            {
                "status": "ausgeschlossen_nicht_oeffentlich",
                "survey_row": None,
                "lat": srow["lat"],
                "lon": srow["lon"],
                "location_description": srow["location_description"],
                "access_type": srow["access_type"],
                "osm_ref": "",
                "distance_m": None,
            }
        )

    n_match = len(pairs)
    result: dict[str, Any] = {
        "tolerance_m": tolerance_m,
        "confidence_level": confidence,
        "n_surveyed_total": int(len(survey)),
        "n_surveyed_public": int(len(public)),
        "n_surveyed_excluded_non_public": int(len(excluded)),
        "n_osm_public_in_area": int(len(osm_aeds)),
        "n_matched": n_match,
        "recall": _interval_dict(n_match, len(public), confidence),
        "precision": _interval_dict(n_match, len(osm_aeds), confidence),
        "chapman": None,
    }
    if list2 is not None:
        l2 = list2[list2["access_type"].str.strip() != NON_PUBLIC].reset_index(drop=True)
        l2_xy = to_laea(l2["lon"], l2["lat"])
        m = len(match_points(s_xy, l2_xy, tolerance_m))
        result["chapman"] = chapman_estimate(len(public), len(l2), m, confidence)
        result["chapman"]["note"] = (
            "Annahme: zwei unabhängige Listen (Erhebung und Liste 2), gleiche Fangwahrscheinlichkeit"
        )
    return result, pd.DataFrame(rows)


def run_validation(
    region: str,
    validation_params: dict[str, Any],
    gpkg: Path | str,
    survey_dir: Path | str,
    out_dir: Path | str,
) -> list[Path]:
    """Validate all surveyed areas of a region. Returns the written JSON paths."""
    files = find_survey_files(survey_dir, region)
    if not files:
        print(
            f"Info: Keine Erhebungsdateien (validation/surveys/{region}_<gebiet>.csv) gefunden. "
            "Validierung wird übersprungen."
        )
        return []
    areas_cfg = validation_params.get("areas") or {}
    tolerance = float(validation_params.get("match_tolerance_m", 50))
    confidence = float(validation_params.get("confidence_level", 0.95))
    if not Path(gpkg).is_file():
        print(f"Info: {gpkg} nicht vorhanden (zuerst 'fetch' ausführen). Validierung übersprungen.")
        return []
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for area, path in files.items():
        if area not in areas_cfg or not areas_cfg[area]:
            print(
                f"Warnung: Gebiet '{area}' ist in config/params.yaml unter validation.areas "
                "nicht (mit Gemeindeschlüsseln) definiert. Überspringe."
            )
            continue
        survey = read_survey(path)
        list2_path = Path(survey_dir) / f"{region}_{area}{LIST2_SUFFIX}.csv"
        list2 = read_survey(list2_path) if list2_path.is_file() else None
        osm = load_osm_aeds(gpkg, [str(a) for a in areas_cfg[area]])
        result, matches = validate_area(survey, osm, tolerance, confidence, list2)
        result = {
            "region": region,
            "area": area,
            "municipality_ags": [str(a) for a in areas_cfg[area]],
            **result,
        }
        json_path = out_dir / f"validation_{area}.json"
        json_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        matches.to_csv(out_dir / f"validation_{area}_matches.csv", index=False)
        rec, pre = result["recall"], result["precision"]
        print(
            f"Gebiet '{area}': Recall {_fmt(rec)}, Precision {_fmt(pre)} "
            f"({result['n_matched']} zugeordnet)"
        )
        written.append(json_path)
    return written


def _fmt(d: dict[str, Any]) -> str:
    if d["value"] is None:
        return "nicht berechenbar"
    return f"{d['value']:.0%} [{d['ci_low']:.0%}; {d['ci_high']:.0%}]"


def run(region_cfg: RegionConfig, params: Params) -> list[Path]:
    """CLI entry point. Never fails when no survey exists."""
    try:
        return run_validation(
            region_cfg.key,
            params.validation,
            PROJECT_ROOT / "data" / "interim" / f"{region_cfg.key}.gpkg",
            PROJECT_ROOT / "validation" / "surveys",
            PROJECT_ROOT / "data" / "processed" / region_cfg.key,
        )
    except ValidationError as exc:
        raise SystemExit(f"Fehler: {exc}") from exc
