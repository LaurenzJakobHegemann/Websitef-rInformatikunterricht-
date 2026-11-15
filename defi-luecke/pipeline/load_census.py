"""Load the Zensus 2022 100 m population grid and clip it to the district.

The CSV is stream-read in chunks directly from the ZIP. Cells are pre-filtered by the district
bounding box, empty cells dropped, and only cells whose centre lies inside the district polygon
are kept. Municipality and VG are attached by spatial join.

See SPEC section 3.2 and docs/schnittstellen.md.
"""

from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

from pipeline.config import RAW_DIR, Params, RegionConfig
from pipeline.download import download_file
from pipeline.fetch_boundaries import Boundaries, load_boundaries

log = logging.getLogger(__name__)

ID_COL, X_COL, Y_COL = "GITTER_ID_100m", "x_mp_100m", "y_mp_100m"
ZERO_MARKERS = {"–", "-", "—", "−"}
CHUNK_ROWS = 1_000_000
BBOX_MARGIN_M = 150


class CensusError(Exception):
    """Census problem; the message is German and shown to the user."""


@dataclass
class Census:
    cells: gpd.GeoDataFrame
    population_column: str
    population_sum: int
    n_rows_read: int
    csv_name: str


def ensure_census_zip(params: Params, raw_dir: Path = RAW_DIR) -> Path:
    cfg = params.census
    zip_path = raw_dir / "zensus2022" / Path(cfg["zip_url"]).name
    if zip_path.is_file():
        log.info("Zensus-ZIP vorhanden, Download übersprungen: %s", zip_path)
        return zip_path
    return download_file(cfg["zip_url"], zip_path)


def detect_population_column(columns: list[str], candidates: list[str]) -> str:
    """First candidate name present in ``columns``; German error if none is."""
    for name in candidates:
        if name in columns:
            return name
    raise CensusError(
        f"Keine Bevölkerungsspalte gefunden. Erwartet: {', '.join(candidates)}; "
        f"vorhanden: {', '.join(columns)}. Bitte die Datensatzbeschreibung im ZIP prüfen und "
        "census.population_columns in config/params.yaml anpassen."
    )


def check_columns(columns: list[str], candidates: list[str]) -> str:
    missing = [c for c in (ID_COL, X_COL, Y_COL) if c not in columns]
    if missing:
        raise CensusError(
            f"Spalten fehlen in der Zensus-CSV: {', '.join(missing)}; "
            f"vorhanden: {', '.join(columns)}"
        )
    return detect_population_column(columns, candidates)


def parse_population(values: pd.Series) -> pd.Series:
    """Parse strings to int; '–' (exactly zero / set to zero) becomes 0, other junk raises."""
    s = values.astype("string").str.strip()
    s = s.mask(s.isin(ZERO_MARKERS), "0")
    try:
        return pd.to_numeric(s, errors="raise").astype("int64")
    except (ValueError, TypeError) as exc:
        raise CensusError(f"Unerwarteter Wert in der Bevölkerungsspalte: {exc}") from exc


def read_cells(
    csv_stream: Any, candidates: list[str], bbox: tuple[float, float, float, float]
) -> tuple[pd.DataFrame, str, int]:
    """Stream the CSV, keep populated cells inside ``bbox`` (xmin, ymin, xmax, ymax, EPSG:3035).

    Returns (frame with cell_id, x, y, population), the column used and the rows read.
    """
    xmin, ymin, xmax, ymax = bbox
    parts, used, n_rows = [], None, 0
    for chunk in pd.read_csv(csv_stream, sep=";", dtype=str, chunksize=CHUNK_ROWS):
        if used is None:
            used = check_columns(list(chunk.columns), candidates)
            log.info("Bevölkerungsspalte in der CSV: '%s'", used)
        n_rows += len(chunk)
        x = pd.to_numeric(chunk[X_COL], errors="coerce")
        y = pd.to_numeric(chunk[Y_COL], errors="coerce")
        sel = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
        sub = chunk.loc[sel]
        if sub.empty:
            continue
        pop = parse_population(sub[used])
        part = pd.DataFrame(
            {
                "cell_id": sub[ID_COL].to_numpy(),
                "x": x[sel].to_numpy(),
                "y": y[sel].to_numpy(),
                "population": pop.to_numpy(),
            }
        )
        parts.append(part[part["population"] > 0])
    if used is None:
        raise CensusError("Die Zensus-CSV ist leer.")
    frame = (
        pd.concat(parts, ignore_index=True)
        if parts
        else pd.DataFrame(columns=["cell_id", "x", "y", "population"])
    )
    return frame, used, n_rows


def assign_cells(frame: pd.DataFrame, boundaries: Boundaries, crs: str) -> gpd.GeoDataFrame:
    """Keep cells with centre inside the district; attach municipality and VG."""
    pts = gpd.GeoDataFrame(
        frame.copy(), geometry=gpd.points_from_xy(frame["x"], frame["y"]), crs=crs
    )
    district_geom = boundaries.district.geometry.union_all()
    pts = pts[pts.within(district_geom)]
    muni = boundaries.municipalities[["ags", "vg_ars", "geometry"]]
    joined = gpd.sjoin(pts, muni, how="inner", predicate="within")
    joined = joined.drop_duplicates("cell_id")
    lost = len(pts) - len(joined)
    if lost:
        log.warning("%d Zellen im Kreis ohne Gemeinde-Zuordnung verworfen", lost)
    out = joined.rename(columns={"ags": "municipality_ags"})[
        ["cell_id", "population", "municipality_ags", "vg_ars", "geometry"]
    ]
    out = out.sort_values("cell_id").reset_index(drop=True)
    out["population"] = out["population"].astype("int64")
    return gpd.GeoDataFrame(out, geometry="geometry", crs=crs)


def load_census(
    region_cfg: RegionConfig,
    params: Params,
    boundaries: Boundaries | None = None,
    raw_dir: Path = RAW_DIR,
) -> Census:
    boundaries = boundaries or load_boundaries(region_cfg, params, raw_dir)
    cfg = params.census
    zip_path = ensure_census_zip(params, raw_dir)
    xmin, ymin, xmax, ymax = boundaries.district.total_bounds
    bbox = (xmin - BBOX_MARGIN_M, ymin - BBOX_MARGIN_M, xmax + BBOX_MARGIN_M, ymax + BBOX_MARGIN_M)
    log.info("Lese Zensus-CSV (streaming): %s", cfg["csv_name"])
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as exc:
        raise CensusError(f"{zip_path} ist keine gültige ZIP-Datei: {exc}") from exc
    with zf:
        if cfg["csv_name"] not in zf.namelist():
            raise CensusError(f"{cfg['csv_name']} nicht im ZIP {zip_path.name} gefunden.")
        with zf.open(cfg["csv_name"]) as fh:
            frame, used, n_rows = read_cells(fh, list(cfg["population_columns"]), bbox)
    cells = assign_cells(frame, boundaries, params.crs["compute"])
    total = int(cells["population"].sum())
    log.info("%d Zellen eingelesen, %d bewohnt im Kreis, Einwohner %d", n_rows, len(cells), total)
    return Census(cells, used, total, n_rows, cfg["csv_name"])


def run(region_cfg: RegionConfig, params: Params) -> Any:
    return load_census(region_cfg, params)
