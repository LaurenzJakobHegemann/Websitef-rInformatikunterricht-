"""Load and validate ``config/regions.yaml`` and ``config/params.yaml``."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"

REQUIRED_PARAM_SECTIONS = (
    "crs",
    "osm",
    "census",
    "boundaries",
    "coverage",
    "optimize",
    "validation",
    "plausibility",
)


class ConfigError(Exception):
    """Configuration problem. The message is German and shown to the user."""


@dataclass(frozen=True)
class RegionConfig:
    key: str
    name: str
    state: str
    district_key: str
    district_key_verified: bool = False
    official_population: int | None = None
    official_population_source: str | None = None


@dataclass(frozen=True)
class Params:
    crs: dict[str, Any] = field(default_factory=dict)
    osm: dict[str, Any] = field(default_factory=dict)
    census: dict[str, Any] = field(default_factory=dict)
    boundaries: dict[str, Any] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)
    optimize: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    plausibility: dict[str, Any] = field(default_factory=dict)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Konfigurationsdatei nicht gefunden: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Konfigurationsdatei {path} ist kein gültiges YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Konfigurationsdatei {path} hat kein gültiges Format.")
    return data


def available_regions(config_dir: Path | str | None = None) -> list[str]:
    """Return all region keys defined in regions.yaml."""
    directory = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    data = _read_yaml(directory / "regions.yaml")
    regions = data.get("regions")
    if not isinstance(regions, dict):
        raise ConfigError("regions.yaml enthält keinen Abschnitt 'regions'.")
    return list(regions)


def load_region(region: str, config_dir: Path | str | None = None) -> RegionConfig:
    """Load one region. Raises ConfigError for unknown or unconfigured regions."""
    directory = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    data = _read_yaml(directory / "regions.yaml")
    regions = data.get("regions")
    if not isinstance(regions, dict):
        raise ConfigError("regions.yaml enthält keinen Abschnitt 'regions'.")
    if region not in regions:
        names = ", ".join(regions) or "(keine)"
        raise ConfigError(f"Unbekannte Region '{region}'. Verfügbare Regionen: {names}")
    raw = regions[region] or {}
    missing = [k for k in ("name", "state", "district_key") if not raw.get(k)]
    if missing:
        raise ConfigError(
            f"Region '{region}' ist noch nicht konfiguriert "
            f"(fehlende Felder in config/regions.yaml: {', '.join(missing)})."
        )
    return RegionConfig(
        key=region,
        name=str(raw["name"]),
        state=str(raw["state"]),
        district_key=str(raw["district_key"]),
        district_key_verified=bool(raw.get("district_key_verified", False)),
        official_population=raw.get("official_population"),
        official_population_source=raw.get("official_population_source"),
    )


def load_params(config_dir: Path | str | None = None) -> Params:
    """Load params.yaml and check that all required sections exist."""
    directory = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    data = _read_yaml(directory / "params.yaml")
    missing = [s for s in REQUIRED_PARAM_SECTIONS if not isinstance(data.get(s), dict)]
    if missing:
        raise ConfigError(f"params.yaml: fehlende Abschnitte: {', '.join(missing)}")
    return Params(**{s: data[s] for s in REQUIRED_PARAM_SECTIONS})


def load_config(region: str, config_dir: Path | str | None = None) -> tuple[RegionConfig, Params]:
    """Load region and parameters together."""
    return load_region(region, config_dir), load_params(config_dir)
