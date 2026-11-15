"""Fetch administrative boundaries (BKG VG250-EW) and select the district.

Downloads the GeoPackage ZIP if missing (skipped if present), reads the layers ``vg250_krs``,
``vg250_vwg`` and ``vg250_gem`` restricted to land areas (``GF`` = boundaries.land_gf_value),
selects the configured district, verifies it exists and compares ``EWZ`` with the configured
official population. All outputs are reprojected to EPSG:3035.

See SPEC section 3.3 and docs/schnittstellen.md.
"""

from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import geopandas as gpd
import pyogrio

from pipeline.config import RAW_DIR, Params, RegionConfig
from pipeline.download import download_file

log = logging.getLogger(__name__)

LAYER_KRS, LAYER_VWG, LAYER_GEM = "vg250_krs", "vg250_vwg", "vg250_gem"


class BoundaryError(Exception):
    """Boundary problem; the message is German and shown to the user."""


@dataclass
class Boundaries:
    district: gpd.GeoDataFrame
    vg: gpd.GeoDataFrame
    municipalities: gpd.GeoDataFrame
    source_file: str = ""
    warnings: list[str] = field(default_factory=list)


def ensure_boundaries(params: Params, raw_dir: Path = RAW_DIR) -> Path:
    """Return the path of the VG250 GeoPackage; download and extract if missing."""
    cfg = params.boundaries
    out_dir = raw_dir / "vg250"
    gpkg = out_dir / cfg["gpkg_member"]
    if gpkg.is_file():
        log.info("VG250 vorhanden, Download übersprungen: %s", gpkg)
        return gpkg
    zip_path = out_dir / Path(cfg["zip_url"]).name
    if not zip_path.is_file():
        download_file(cfg["zip_url"], zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)
    if not gpkg.is_file():
        raise BoundaryError(
            f"Im ZIP {zip_path.name} fehlt {cfg['gpkg_member']}. "
            "Manueller Schritt: siehe data/raw/SOURCES.md, Abschnitt 3."
        )
    return gpkg


def _check_key(key: str) -> str:
    if not key.isdigit():
        raise BoundaryError(f"Ungültiger Kreisschlüssel '{key}' (nur Ziffern erlaubt).")
    return key


def _read_layer(gpkg: Path, layer: str, land_gf: int, field_name: str, prefix: str):
    where = f"GF = {int(land_gf)} AND {field_name} LIKE '{prefix}%'"
    return pyogrio.read_dataframe(gpkg, layer=layer, where=where)


def load_boundaries(
    region_cfg: RegionConfig, params: Params, raw_dir: Path = RAW_DIR, gpkg: Path | None = None
) -> Boundaries:
    """Read, filter and reproject the district, its VGs and municipalities."""
    gpkg = gpkg or ensure_boundaries(params, raw_dir)
    crs = params.crs["compute"]
    land_gf = params.boundaries["land_gf_value"]
    key = _check_key(region_cfg.district_key)

    krs = _read_layer(gpkg, LAYER_KRS, land_gf, "AGS", key)
    krs = krs[krs["AGS"] == key]
    if krs.empty:
        raise BoundaryError(
            f"Kreisschlüssel {key} ('{region_cfg.name}') nicht in VG250 gefunden "
            f"(Ebene {LAYER_KRS}, GF = {land_gf}). Bitte config/regions.yaml prüfen."
        )
    if len(krs) > 1:
        krs = krs.dissolve(by="AGS", aggfunc="first", as_index=False)
    row = krs.iloc[0]
    log.info("Kreis %s gefunden: %s (%s), EWZ %s", key, row["GEN"], row["BEZ"], row["EWZ"])
    warnings: list[str] = []
    if region_cfg.official_population is not None and int(row["EWZ"]) != int(
        region_cfg.official_population
    ):
        msg = (
            f"EWZ in VG250 ({int(row['EWZ'])}) weicht von official_population in "
            f"config/regions.yaml ({int(region_cfg.official_population)}) ab."
        )
        log.warning(msg)
        warnings.append(msg)

    gem = _read_layer(gpkg, LAYER_GEM, land_gf, "ARS", key)
    vwg = _read_layer(gpkg, LAYER_VWG, land_gf, "ARS", key)
    if gem.empty:
        raise BoundaryError(f"Keine Gemeinden für Kreis {key} in VG250 gefunden.")
    # One row per municipality / VG (several GF=4 parts would be merged).
    gem = gem.dissolve(by="AGS", aggfunc="first", as_index=False)
    vwg = vwg.dissolve(by="ARS", aggfunc="first", as_index=False)

    district = gpd.GeoDataFrame(
        {
            "ags": [row["AGS"]],
            "name": [row["GEN"]],
            "type": [row["BEZ"]],
            "ewz": [int(row["EWZ"])],
            "geometry": [row.geometry],
        },
        crs=krs.crs,
    ).to_crs(crs)
    district["area_km2"] = (district.area / 1e6).round(2)

    municipalities = gpd.GeoDataFrame(
        {
            "ags": gem["AGS"],
            "ars": gem["ARS"],
            "name": gem["GEN"],
            "type": gem["BEZ"],
            "vg_ars": gem["ARS"].str[:9],
            "ewz": gem["EWZ"].astype(int),
            "geometry": gem.geometry,
        },
        crs=gem.crs,
    ).to_crs(crs)
    municipalities["area_km2"] = (municipalities.area / 1e6).round(3)

    vg = gpd.GeoDataFrame(
        {
            "ars": vwg["ARS"],
            "name": vwg["GEN"],
            "type": vwg["BEZ"],
            "ewz": vwg["EWZ"].astype(int),
            "geometry": vwg.geometry,
        },
        crs=vwg.crs,
    ).to_crs(crs)

    missing_vg = set(municipalities["vg_ars"]) - set(vg["ars"])
    if missing_vg:
        msg = f"Gemeinden verweisen auf VG-ARS ohne Eintrag in {LAYER_VWG}: {sorted(missing_vg)}"
        log.warning(msg)
        warnings.append(msg)
    ewz_sum = int(municipalities["ewz"].sum())
    if ewz_sum != int(row["EWZ"]):
        msg = f"Summe der Gemeinde-EWZ ({ewz_sum}) weicht vom Kreis-EWZ ({int(row['EWZ'])}) ab."
        log.warning(msg)
        warnings.append(msg)
    log.info("%d Gemeinden, %d Verbandsgemeinden/VG", len(municipalities), len(vg))
    return Boundaries(district, vg, municipalities, gpkg.name, warnings)


def run(region_cfg: RegionConfig, params: Params) -> Any:
    return load_boundaries(region_cfg, params)
