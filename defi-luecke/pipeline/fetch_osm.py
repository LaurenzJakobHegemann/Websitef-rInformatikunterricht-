"""Fetch AEDs (emergency=defibrillator) and candidate places from OpenStreetMap via Overpass.

The raw Overpass response is stored unchanged as a dated snapshot in ``data/raw``. If no
Overpass server can be reached, :class:`OsmUnavailableError` explains the manual step
(German message, documented in ``data/raw/SOURCES.md``).

Parsing functions are pure (elements -> GeoDataFrame) and do not touch the network.

See SPEC section 3.1 and docs/schnittstellen.md.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import requests
from shapely.geometry import Point, shape

from pipeline.config import RAW_DIR, Params, RegionConfig

log = logging.getLogger(__name__)

OSM_ATTRIBUTION = "© OpenStreetMap-Mitwirkende (ODbL)"
KINDS = ("aed", "candidates")
OVERPASS_GET_PREFIX = "https://overpass-api.de/api/interpreter?data="
CONNECT_TIMEOUT_S = 8
_DATE_RE = re.compile(r"_(\d{4}-\d{2}-\d{2})\.(?:geo)?json$")


class OsmUnavailableError(Exception):
    """No OSM snapshot available and no Overpass server reachable (message is German)."""

    def __init__(self, message: str, missing: list[str] | None = None):
        super().__init__(message)
        self.missing = missing or []


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
Bbox = tuple[float, float, float, float]  # south, west, north, east (WGS84)


def compute_query_bbox(district_3035: gpd.GeoDataFrame, buffer_m: float) -> Bbox:
    """District polygon buffered by ``buffer_m`` in EPSG:3035, reprojected, total bounds, 4 dp."""
    geom = district_3035.geometry.union_all().buffer(buffer_m)
    wgs = gpd.GeoSeries([geom], crs=district_3035.crs).to_crs(4326)
    west, south, east, north = wgs.total_bounds
    return (round(south, 4), round(west, 4), round(north, 4), round(east, 4))


def _bbox_str(bbox: Bbox) -> str:
    return ",".join(f"{v:.4f}" for v in bbox)


def build_aed_query(bbox: Bbox, timeout_s: int) -> str:
    return (
        f"[out:json][timeout:{timeout_s}];\n"
        f'nwr["emergency"="defibrillator"]({_bbox_str(bbox)});\n'
        "out center tags;\n"
    )


def build_candidates_query(bbox: Bbox, timeout_s: int, candidate_tags: dict[str, list[str]]) -> str:
    """Union over the configured tags; highway=bus_stop is a node-only feature."""
    b = _bbox_str(bbox)
    lines = []
    for key, values in candidate_tags.items():
        elem = "node" if key == "highway" else "nwr"
        if len(values) == 1:
            lines.append(f'  {elem}["{key}"="{values[0]}"]({b});')
        else:
            lines.append(f'  {elem}["{key}"~"^({"|".join(values)})$"]({b});')
    body = "\n".join(lines)
    return f"[out:json][timeout:{timeout_s}];\n(\n{body}\n);\nout center tags;\n"


def overpass_get_link(query: str) -> str:
    """Direct download link for the query (works in any browser)."""
    return OVERPASS_GET_PREFIX + urllib.parse.quote(query, safe="")


# ---------------------------------------------------------------------------
# Parsing (pure)
# ---------------------------------------------------------------------------
def _element_point(el: dict[str, Any]) -> tuple[float, float] | None:
    """(lon, lat) of a node, or the ``center`` of a way/relation."""
    if el.get("type") == "node" and "lat" in el and "lon" in el:
        return float(el["lon"]), float(el["lat"])
    center = el.get("center")
    if center and "lat" in center and "lon" in center:
        return float(center["lon"]), float(center["lat"])
    return None


def access_class(tags: dict[str, str]) -> str:
    opening = (tags.get("opening_hours") or "").strip()
    if opening == "24/7":
        return "24/7"
    return "restricted" if opening else "unknown"


def is_public(tags: dict[str, str], excluded_access: list[str]) -> bool:
    access = (tags.get("access") or "").strip().lower()
    return access not in {str(v).lower() for v in excluded_access}


def tag_column(tag: str) -> str:
    return tag.replace(":", "_")


def parse_aed_elements(
    elements: list[dict[str, Any]], tags_to_keep: list[str], excluded_access: list[str]
) -> gpd.GeoDataFrame:
    """Overpass elements -> AED GeoDataFrame in EPSG:4326 (contract: ``aeds`` layer).

    ``in_region`` is set later (needs the district polygon) and starts as False.
    """
    rows, geoms = [], []
    for el in elements:
        pt = _element_point(el)
        if pt is None:
            log.warning("Element %s/%s ohne Koordinaten übersprungen", el.get("type"), el.get("id"))
            continue
        tags = el.get("tags") or {}
        row: dict[str, Any] = {
            "osm_type": el["type"],
            "osm_id": int(el["id"]),
            "osm_url": f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
        }
        for tag in tags_to_keep:
            row[tag_column(tag)] = tags.get(tag)
        row["access_class"] = access_class(tags)
        row["is_public"] = is_public(tags, excluded_access)
        row["in_region"] = False
        rows.append(row)
        geoms.append(Point(*pt))
    columns = ["osm_type", "osm_id", "osm_url", *[tag_column(t) for t in tags_to_keep]]
    columns += ["access_class", "is_public", "in_region"]
    return gpd.GeoDataFrame(rows, columns=columns, geometry=geoms, crs=4326)


def parse_candidate_elements(
    elements: list[dict[str, Any]], candidate_tags: dict[str, list[str]]
) -> gpd.GeoDataFrame:
    """Overpass elements -> candidate GeoDataFrame in EPSG:4326 with ``category`` (key=value)."""
    rows, geoms = [], []
    for el in elements:
        pt = _element_point(el)
        tags = el.get("tags") or {}
        category = next(
            (f"{k}={tags[k]}" for k, vals in candidate_tags.items() if tags.get(k) in vals), None
        )
        if pt is None or category is None:
            continue
        rows.append(
            {
                "osm_type": el["type"],
                "osm_id": int(el["id"]),
                "name": tags.get("name"),
                "category": category,
            }
        )
        geoms.append(Point(*pt))
    return gpd.GeoDataFrame(
        rows, columns=["osm_type", "osm_id", "name", "category"], geometry=geoms, crs=4326
    )


# ---------------------------------------------------------------------------
# Snapshots and download
# ---------------------------------------------------------------------------
def snapshot_path(raw_dir: Path, kind: str, region: str, date: str) -> Path:
    return raw_dir / f"osm_{kind}_{region}_{date}.json"


def query_path(raw_dir: Path, kind: str, region: str) -> Path:
    return raw_dir / f"overpass_query_{kind}_{region}.overpassql"


def list_snapshots(raw_dir: Path, kind: str, region: str) -> list[tuple[str, Path]]:
    """All snapshots as (date, path), oldest first."""
    found = []
    for path in raw_dir.glob(f"osm_{kind}_{region}_*"):
        m = _DATE_RE.search(path.name)
        if m and path.name in (
            f"osm_{kind}_{region}_{m.group(1)}.json",
            f"osm_{kind}_{region}_{m.group(1)}.geojson",
        ):
            found.append((m.group(1), path))
    return sorted(found)


def select_snapshot(
    raw_dir: Path, kind: str, region: str, snapshot_date: str | None
) -> tuple[str, Path] | None:
    """``snapshot_date`` if configured, else the newest snapshot; None if not available."""
    snaps = list_snapshots(raw_dir, kind, region)
    if snapshot_date:
        return next((s for s in snaps if s[0] == str(snapshot_date)), None)
    return snaps[-1] if snaps else None


def _validate_response(data: Any) -> None:
    if not isinstance(data, dict) or "elements" not in data:
        raise ValueError("Antwort enthält kein 'elements'")
    remark = str(data.get("remark", ""))
    if (
        remark
        and not data["elements"]
        and re.search(r"error|timed out|out of memory", remark, re.I)
    ):
        raise ValueError(f"Overpass-Hinweis: {remark}")


def download_overpass(
    query: str, urls: list[str], timeout_s: int, post=requests.post
) -> tuple[bytes, str]:
    """Try the servers in order, once each. Returns (raw response bytes, url used)."""
    errors = []
    for url in urls:
        try:
            resp = post(url, data={"data": query}, timeout=(CONNECT_TIMEOUT_S, timeout_s + 30))
            resp.raise_for_status()
            _validate_response(json.loads(resp.content))
            return resp.content, url
        except (requests.RequestException, ValueError) as exc:
            log.warning("Overpass-Server %s nicht nutzbar: %s", url, exc)
            errors.append(f"{url}: {exc}")
    raise ConnectionError("; ".join(errors))


@dataclass
class OsmSnapshot:
    kind: str
    path: Path | None
    date: str | None
    source: str  # "downloaded", "existing", "missing"
    url_used: str | None = None
    elements: list[dict[str, Any]] | None = None
    osm_base_timestamp: str | None = None


def manual_step_message(kind: str, query: str, region: str, raw_dir: Path, date: str) -> str:
    label = "AEDs" if kind == "aed" else "Kandidatenorte (Variante B)"
    return (
        f"OSM-Snapshot '{kind}' fehlt und kein Overpass-Server war erreichbar ({label}).\n"
        "Manueller Schritt:\n"
        "  1. Abfrage ausführen, entweder\n"
        f"     a) per Direktlink im Browser: {overpass_get_link(query)}\n"
        f"     b) oder die Datei {query_path(raw_dir, kind, region)} auf https://overpass-turbo.eu "
        "einfügen, ausführen und über Export > Rohdaten (JSON) speichern.\n"
        f"  2. Antwort unverändert speichern als {snapshot_path(raw_dir, kind, region, date)} "
        "(Datum = Abruftag, JJJJ-MM-TT).\n"
        "  3. `python -m pipeline.cli fetch --region " + region + "` erneut ausführen.\n"
        "Abfrage:\n" + query
    )


def get_snapshot(
    kind: str,
    query: str,
    region: str,
    params: Params,
    raw_dir: Path = RAW_DIR,
    *,
    today: dt.date | None = None,
    post=requests.post,
) -> OsmSnapshot:
    """Return the snapshot for ``kind``; download it if needed. Raises OsmUnavailableError."""
    today_s = (today or dt.date.today()).isoformat()
    cfg_date = params.osm.get("snapshot_date")
    cfg_date = str(cfg_date) if cfg_date else None
    qpath = query_path(raw_dir, kind, region)
    raw_dir.mkdir(parents=True, exist_ok=True)
    qpath.write_text(query, encoding="utf-8")

    chosen = select_snapshot(raw_dir, kind, region, cfg_date)
    # Reuse a configured snapshot, or today's snapshot; otherwise try to refresh first.
    if chosen and (cfg_date or chosen[0] == today_s):
        return _load(kind, chosen, "existing")
    if not cfg_date:
        try:
            body, url = download_overpass(
                query, list(params.osm["overpass_urls"]), int(params.osm["timeout_s"]), post
            )
        except ConnectionError as exc:
            log.warning("Overpass-Abruf '%s' gescheitert: %s", kind, exc)
        else:
            path = snapshot_path(raw_dir, kind, region, today_s)
            path.write_bytes(body)
            log.info("OSM-Snapshot gespeichert: %s", path)
            return _load(kind, (today_s, path), "downloaded", url)
    if chosen:
        log.warning("Verwende vorhandenen Snapshot %s (Abruf nicht möglich).", chosen[1].name)
        return _load(kind, chosen, "existing")
    date_hint = cfg_date or today_s
    raise OsmUnavailableError(
        manual_step_message(kind, query, region, raw_dir, date_hint), missing=[kind]
    )


def geojson_to_elements(fc: dict[str, Any]) -> list[dict[str, Any]]:
    """overpass-turbo GeoJSON export -> Overpass-like elements (``type``, ``id``, ``tags``).

    overpass-turbo stores the OSM id as feature id ``node/123`` and adds meta keys starting
    with ``@``, which are dropped. Non-point geometries (ways/relations exported as shapes)
    get a ``center`` from the geometry's representative point.
    """
    elements = []
    for feat in fc.get("features", []):
        props = feat.get("properties") or {}
        fid = str(feat.get("id") or props.get("@id") or "")
        if "/" not in fid:
            log.warning("GeoJSON-Feature ohne OSM-ID übersprungen: %r", fid)
            continue
        osm_type, osm_id = fid.split("/", 1)
        tags = {k: v for k, v in props.items() if not k.startswith("@")}
        el: dict[str, Any] = {"type": osm_type, "id": int(osm_id), "tags": tags}
        geom = feat.get("geometry")
        if geom and geom.get("type") == "Point":
            lon, lat = geom["coordinates"][:2]
            if osm_type == "node":
                el["lat"], el["lon"] = lat, lon
            else:
                el["center"] = {"lat": lat, "lon": lon}
        elif geom:
            pt = shape(geom).representative_point()
            el["center"] = {"lat": pt.y, "lon": pt.x}
        elements.append(el)
    return elements


def _load(kind: str, chosen: tuple[str, Path], source: str, url: str | None = None) -> OsmSnapshot:
    date, path = chosen
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        log.info("OSM-Snapshot '%s' liegt als GeoJSON (overpass-turbo) vor.", kind)
        data = {
            "elements": geojson_to_elements(data),
            "osm3s": {"timestamp_osm_base": data.get("timestamp")},
        }
    _validate_response(data)
    ts = (data.get("osm3s") or {}).get("timestamp_osm_base")
    log.info("OSM-Snapshot '%s': %s (%d Elemente)", kind, path.name, len(data["elements"]))
    return OsmSnapshot(kind, path, date, source, url, data["elements"], ts)


def run(region_cfg: RegionConfig, params: Params) -> Any:
    """Standalone use is via build_interim (needs the district bbox)."""
    from pipeline import build_interim

    return build_interim.run(region_cfg, params)
