"""Evaluation figures for the written report (SPEC section 8).

Reads the processed outputs in ``data/processed/<region>/`` and writes PNG (200 dpi) and SVG
with German labels to ``figures/``. Every figure is skipped with a German message when its
input is missing.

Assumed format of ``cell_coverage`` (the contract only says "distance per cell and scenario"):
long format with ``cell_id``, ``population``, ``scenario`` and an effective-distance column
(``effective_distance_m``, ``distance_m``, ``dist_m`` or ``nearest_distance_m``), or wide format
with one column ``<prefix>_<scenario>`` per scenario (prefix as above, or ``dist``).
Distance = straight line x current detour factor; missing/NaN = no AED reachable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from pipeline.config import PROJECT_ROOT, Params, RegionConfig  # noqa: E402

# Okabe-Ito colour-blind-safe palette
OI = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "green": "#009E73",
    "vermillion": "#D55E00",
    "sky": "#56B4E9",
    "purple": "#CC79A7",
    "yellow": "#F0E442",
    "black": "#000000",
}
SCENARIO_LABELS = {
    "all": "Alle öffentlichen AEDs",
    "night_strict": "Nachts (strikt, 24/7)",
    "night_optimistic": "Nachts (optimistisch)",
}
SCENARIO_COLORS = {
    "all": OI["blue"],
    "night_strict": OI["vermillion"],
    "night_optimistic": OI["orange"],
}
RADIUS_COLORS = [OI["blue"], OI["orange"], OI["green"], OI["vermillion"], OI["purple"], OI["sky"]]
DISTANCE_COLUMNS = ("effective_distance_m", "distance_m", "dist_m", "nearest_distance_m")
DETOUR_FACTORS = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6]
DEFAULT_RADIUS = 300

CSV_HEADERS_DE = {
    "level": "Ebene",
    "id": "Gemeindeschlüssel",
    "name": "Name",
    "radius_m": "Radius (m)",
    "scenario": "Szenario",
    "population": "Einwohner (Zensus 2022)",
    "covered_population": "Versorgte Einwohner",
    "coverage_rate": "Abdeckungsquote",
    "mean_distance_m": "Mittlere Distanz (m)",
    "median_distance_m": "Mediane Distanz (m)",
    "aeds_in_area": "AEDs im Gebiet",
    "aeds_per_10k": "AEDs je 10.000 Einwohner",
    "share_aeds_missing_info": "Anteil AEDs ohne Zugangsangabe",
    "share_access_unknown": "Anteil AEDs mit unbekanntem Zugang",
}


def _skip(name: str, reason: str) -> list[Path]:
    print(f"Info: Grafik '{name}' übersprungen: {reason}")
    return []


def _save(fig, fig_dir: Path, name: str) -> list[Path]:
    fig_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in ("png", "svg"):
        path = fig_dir / f"{name}.{ext}"
        fig.savefig(path, dpi=200, bbox_inches="tight")
        paths.append(path)
    plt.close(fig)
    return paths


def _read_csv(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path, dtype={"id": str}) if path.is_file() else None


def _scenario_label(s: str) -> str:
    return SCENARIO_LABELS.get(s, s)


def _pct_axis(ax, axis: str = "y") -> None:
    from matplotlib.ticker import PercentFormatter

    getattr(ax, f"{axis}axis").set_major_formatter(PercentFormatter(1.0, decimals=0))


# ------------------------------------------------------------------ figures


def fig_histogram(processed: Path, fig_dir: Path) -> list[Path]:
    name = "a_verteilung_abdeckung_gemeinden"
    df = _read_csv(processed / "metrics_municipality.csv")
    if df is None:
        return _skip(name, "metrics_municipality.csv fehlt")
    df = df[df["scenario"] == "all"]
    radii = sorted(df["radius_m"].unique())
    if not radii:
        return _skip(name, "keine Daten für Szenario 'all'")
    ncols = min(2, len(radii))
    nrows = -(-len(radii) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 3.6 * nrows), squeeze=False)
    bins = np.linspace(0, 1, 11)
    for ax, r in zip(axes.flat, radii, strict=False):
        sub = df[df["radius_m"] == r]["coverage_rate"].dropna()
        ax.hist(sub, bins=bins, color=OI["blue"], edgecolor="white")
        ax.set_title(f"Radius {int(r)} m (n = {len(sub)} Gemeinden)")
        ax.set_xlabel("Abdeckungsquote")
        ax.set_ylabel("Anzahl Gemeinden")
        _pct_axis(ax, "x")
    for ax in list(axes.flat)[len(radii) :]:
        ax.axis("off")
    fig.suptitle("Verteilung der Abdeckungsquoten über die Gemeinden (alle öffentlichen AEDs)")
    fig.tight_layout()
    return _save(fig, fig_dir, name)


def fig_density(processed: Path, fig_dir: Path, gpkg: Path, radius_m: int | None = None):
    name = "b_abdeckung_vs_bevoelkerungsdichte"
    df = _read_csv(processed / "metrics_municipality.csv")
    if df is None:
        return _skip(name, "metrics_municipality.csv fehlt")
    if not Path(gpkg).is_file():
        return _skip(name, f"{Path(gpkg).name} fehlt (Fläche der Gemeinden)")
    import geopandas as gpd

    munis = gpd.read_file(gpkg, layer="municipalities")[["ags", "area_km2"]]
    munis["ags"] = munis["ags"].astype(str)
    df = df[df["scenario"] == "all"]
    radii = sorted(df["radius_m"].unique())
    if not radii:
        return _skip(name, "keine Daten für Szenario 'all'")
    radius = (
        radius_m
        if radius_m in radii
        else (DEFAULT_RADIUS if DEFAULT_RADIUS in radii else radii[len(radii) // 2])
    )
    sub = df[df["radius_m"] == radius].merge(munis, left_on="id", right_on="ags", how="inner")
    sub = sub[(sub["area_km2"] > 0) & (sub["population"] > 0)]
    if sub.empty:
        return _skip(name, "keine Gemeinden mit Fläche und Einwohnern")
    density = sub["population"] / sub["area_km2"]
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.scatter(
        density,
        sub["coverage_rate"],
        s=20 + 80 * sub["population"] / sub["population"].max(),
        color=OI["blue"],
        alpha=0.7,
        edgecolor="white",
    )
    ax.set_xscale("log")
    ax.set_xlabel("Bevölkerungsdichte (Einwohner je km², logarithmisch)")
    ax.set_ylabel(f"Abdeckungsquote (Radius {int(radius)} m)")
    _pct_axis(ax)
    ax.set_ylim(-0.02, 1.02)
    ax.set_title(
        "Abdeckungsquote und Bevölkerungsdichte der Gemeinden\n(Punktgröße ~ Einwohnerzahl)"
    )
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return _save(fig, fig_dir, name)


def fig_scenarios(processed: Path, fig_dir: Path) -> list[Path]:
    name = "c_szenarien_tag_nacht"
    df = _read_csv(processed / "metrics_district.csv")
    if df is None:
        return _skip(name, "metrics_district.csv fehlt")
    radii = sorted(df["radius_m"].unique())
    scenarios = [s for s in SCENARIO_LABELS if s in set(df["scenario"])]
    if not radii or not scenarios:
        return _skip(name, "keine Szenariodaten")
    fig, ax = plt.subplots(figsize=(7, 4.5))
    width = 0.8 / len(scenarios)
    for i, s in enumerate(scenarios):
        vals = [
            df[(df["radius_m"] == r) & (df["scenario"] == s)]["coverage_rate"].mean() for r in radii
        ]
        xs = np.arange(len(radii)) + (i - (len(scenarios) - 1) / 2) * width
        ax.bar(xs, vals, width, label=_scenario_label(s), color=SCENARIO_COLORS[s])
    ax.set_xticks(np.arange(len(radii)), [f"{int(r)} m" for r in radii])
    ax.set_xlabel("Radius")
    ax.set_ylabel("Abdeckungsquote (Landkreis)")
    _pct_axis(ax)
    ax.set_ylim(0, 1)
    ax.set_title("Abdeckung tagsüber und nachts im Vergleich")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return _save(fig, fig_dir, name)


def read_cell_coverage(processed: Path) -> pd.DataFrame | None:
    """Read cell_coverage (parquet or csv) and normalise it to long format."""
    path = None
    for ext in ("parquet", "csv"):
        if (processed / f"cell_coverage.{ext}").is_file():
            path = processed / f"cell_coverage.{ext}"
            break
    if path is None:
        return None
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    return normalize_cell_coverage(df)


def normalize_cell_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """Return columns cell_id, population, scenario, distance_m."""
    if "scenario" in df.columns:
        col = next((c for c in DISTANCE_COLUMNS if c in df.columns), None)
        if col is None:
            raise ValueError("cell_coverage: keine Distanzspalte gefunden")
        out = df.rename(columns={col: "distance_m"})
    else:
        parts = []
        for c in df.columns:
            for prefix in (*DISTANCE_COLUMNS, "dist"):
                if c.startswith(prefix + "_") and c[len(prefix) + 1 :] in SCENARIO_LABELS:
                    parts.append((c, c[len(prefix) + 1 :]))
                    break
        if not parts:
            raise ValueError(
                "cell_coverage: weder Spalte 'scenario' noch Distanzspalten je Szenario"
            )
        frames = [
            df[["cell_id", "population", c]].rename(columns={c: "distance_m"}).assign(scenario=s)
            for c, s in parts
        ]
        out = pd.concat(frames, ignore_index=True)
    return out[["cell_id", "population", "scenario", "distance_m"]]


def coverage_rate_from_distances(
    cells: pd.DataFrame, radius_m: float, factor_ratio: float = 1.0
) -> float:
    """Population share with (distance x factor_ratio) <= radius. NaN distance = uncovered."""
    total = cells["population"].sum()
    if total <= 0:
        return float("nan")
    eff = cells["distance_m"].to_numpy(dtype=float) * factor_ratio
    covered = cells["population"].to_numpy()[np.nan_to_num(eff, nan=np.inf) <= radius_m]
    return float(covered.sum() / total)


def fig_sensitivity(processed: Path, fig_dir: Path, current_factor: float) -> list[Path]:
    name = "d_sensitivitaet_radius_umwegfaktor"
    metrics = _read_csv(processed / "metrics_district.csv")
    if metrics is None:
        return _skip(name, "metrics_district.csv fehlt")
    cells = None
    try:
        cells = read_cell_coverage(processed)
    except ValueError as exc:
        print(f"Info: {exc}")
    m = metrics[metrics["scenario"] == "all"].sort_values("radius_m")
    if m.empty:
        return _skip(name, "keine Daten für Szenario 'all'")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    ax1.plot(m["radius_m"], m["coverage_rate"], marker="o", color=OI["blue"])
    ax1.set_xlabel("Radius (m)")
    ax1.set_ylabel("Abdeckungsquote (Landkreis)")
    ax1.set_title(f"Radius (Umwegfaktor {current_factor:g})")
    _pct_axis(ax1)
    ax1.set_ylim(0, 1)
    ax1.grid(alpha=0.3)
    if cells is None or cells[cells["scenario"] == "all"].empty:
        ax2.text(0.5, 0.5, "cell_coverage fehlt", ha="center", transform=ax2.transAxes)
        ax2.axis("off")
        print("Info: Umwegfaktor-Panel in Grafik d ohne cell_coverage leer.")
    else:
        sub = cells[cells["scenario"] == "all"]
        for color, r in zip(RADIUS_COLORS, sorted(m["radius_m"].unique()), strict=False):
            rates = [
                coverage_rate_from_distances(sub, r, f / current_factor) for f in DETOUR_FACTORS
            ]
            ax2.plot(DETOUR_FACTORS, rates, marker="o", color=color, label=f"{int(r)} m")
        ax2.set_xlabel("Umwegfaktor")
        ax2.set_ylabel("Abdeckungsquote (Landkreis)")
        ax2.set_title("Umwegfaktor (Radius als Linie)")
        _pct_axis(ax2)
        ax2.set_ylim(0, 1)
        ax2.grid(alpha=0.3)
        ax2.legend(title="Radius")
    fig.suptitle("Sensitivität der Abdeckung gegenüber Radius und Umwegfaktor")
    fig.tight_layout()
    return _save(fig, fig_dir, name)


def fig_optimizer(processed: Path, fig_dir: Path) -> list[Path]:
    name = "e_optimierer_abdeckungskurve"
    frames = {}
    for variant in ("A", "B"):
        df = _read_csv(processed / f"optimize_{variant}_district.csv")
        if df is not None:
            if "scenario" in df.columns:
                df = df[df["scenario"] == "all"]
            frames[variant] = df
    if not frames:
        return _skip(name, "optimize_A_district.csv / optimize_B_district.csv fehlen")
    radii = sorted(set().union(*[set(d["radius_m"]) for d in frames.values()]))
    ncols = min(2, len(radii))
    nrows = -(-len(radii) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 3.8 * nrows), squeeze=False)
    style = {
        "A": (OI["blue"], "o", "Variante A (Gemeindezentren)"),
        "B": (OI["orange"], "s", "Variante B (OSM-Orte)"),
    }
    for ax, r in zip(axes.flat, radii, strict=False):
        for variant, df in frames.items():
            sub = df[df["radius_m"] == r].sort_values("rank")
            if sub.empty:
                continue
            color, marker, label = style[variant]
            ax.plot(
                sub["rank"], sub["cumulative_rate"], marker=marker, ms=4, color=color, label=label
            )
        ax.set_title(f"Radius {int(r)} m")
        ax.set_xlabel("Anzahl zusätzlicher AEDs (k)")
        ax.set_ylabel("Abdeckungsquote")
        _pct_axis(ax)
        ax.grid(alpha=0.3)
        ax.legend()
    for ax in list(axes.flat)[len(radii) :]:
        ax.axis("off")
    fig.suptitle("Abdeckungskurve des Optimierers (Landkreis, Greedy)")
    fig.tight_layout()
    return _save(fig, fig_dir, name)


def fig_validation(processed: Path, fig_dir: Path) -> list[Path]:
    name = "f_validierung_recall_precision"
    results = []
    for path in sorted(processed.glob("validation_*.json")):
        results.append(json.loads(path.read_text(encoding="utf-8")))
    if not results:
        return _skip(name, "keine validation_<gebiet>.json vorhanden (keine Erhebung)")
    fig, ax = plt.subplots(figsize=(7, 1.6 + 1.1 * len(results)))
    ypos = np.arange(len(results))
    for key, label, color, off in (
        ("recall", "Recall (in OSM vorhanden)", OI["blue"], -0.12),
        ("precision", "Precision (vor Ort bestätigt)", OI["orange"], 0.12),
    ):
        ys, vals, lo, hi = [], [], [], []
        for y, res in zip(ypos, results, strict=True):
            d = res.get(key) or {}
            if d.get("value") is None:
                continue
            ys.append(y + off)
            vals.append(d["value"])
            lo.append(d["value"] - d["ci_low"])
            hi.append(d["ci_high"] - d["value"])
        ax.errorbar(vals, ys, xerr=[lo, hi], fmt="o", capsize=4, color=color, label=label)
    ax.set_yticks(ypos, [r.get("area", "?") for r in results])
    ax.set_xlim(0, 1.02)
    _pct_axis(ax, "x")
    ax.set_xlabel(f"Anteil (mit Wilson-Intervall, {results[0].get('confidence_level', 0.95):.0%})")
    ax.set_title("Vollständigkeit der OSM-AED-Daten gegenüber eigener Erhebung")
    ax.legend(loc="lower left")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    return _save(fig, fig_dir, name)


def write_municipality_csv(processed: Path, fig_dir: Path) -> list[Path]:
    src = processed / "metrics_municipality.csv"
    if not src.is_file():
        return _skip("kennzahlen_gemeinden.csv", "metrics_municipality.csv fehlt")
    df = pd.read_csv(src, dtype={"id": str})
    df = df.rename(columns=CSV_HEADERS_DE)
    fig_dir.mkdir(parents=True, exist_ok=True)
    out = fig_dir / "kennzahlen_gemeinden.csv"
    df.to_csv(out, index=False, sep=";", decimal=",", encoding="utf-8-sig")
    return [out]


# --------------------------------------------------------------------- run


def make_all(
    processed: Path | str,
    gpkg: Path | str,
    detour_factor: float,
    fig_dir: Path | str | None = None,
) -> list[Path]:
    """Create all figures. Returns the written files."""
    processed = Path(processed)
    fig_dir = Path(fig_dir) if fig_dir else processed / "figures"
    written: list[Path] = []
    for func in (
        lambda: fig_histogram(processed, fig_dir),
        lambda: fig_density(processed, fig_dir, Path(gpkg)),
        lambda: fig_scenarios(processed, fig_dir),
        lambda: fig_sensitivity(processed, fig_dir, detour_factor),
        lambda: fig_optimizer(processed, fig_dir),
        lambda: fig_validation(processed, fig_dir),
        lambda: write_municipality_csv(processed, fig_dir),
    ):
        written += func()
    print(f"{len(written)} Dateien in {fig_dir} geschrieben.")
    return written


def run(region_cfg: RegionConfig, params: Params) -> Any:
    return make_all(
        PROJECT_ROOT / "data" / "processed" / region_cfg.key,
        PROJECT_ROOT / "data" / "interim" / f"{region_cfg.key}.gpkg",
        float(params.coverage.get("detour_factor", 1.3)),
    )
