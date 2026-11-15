"""Command line interface: ``python -m pipeline.cli <command> --region <key>``."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict
from types import ModuleType

from pipeline import (
    build_interim,
    coverage,
    export_web,
    figures,
    optimize,
    validate,
)
from pipeline.config import ConfigError, Params, RegionConfig, load_config
from pipeline.download import DownloadError
from pipeline.fetch_boundaries import BoundaryError
from pipeline.fetch_osm import OsmUnavailableError
from pipeline.load_census import CensusError

# CLI step name -> (milestone, modules executed in order)
STEPS: dict[str, tuple[str, tuple[ModuleType, ...]]] = {
    "fetch": ("M1", (build_interim,)),
    "coverage": ("M2", (coverage,)),
    "optimize": ("M3", (optimize,)),
    "validate": ("M5", (validate,)),
    "figures": ("M5", (figures,)),
    "export-web": ("M4", (export_web,)),
}
RUN_ORDER = ("fetch", "coverage", "optimize", "validate", "figures", "export-web")


class StepNotImplementedError(Exception):
    def __init__(self, step: str, milestone: str):
        super().__init__(f"Schritt '{step}' ist noch nicht implementiert (Meilenstein {milestone})")


def run_step(step: str, region_cfg: RegionConfig, params: Params) -> None:
    milestone, modules = STEPS[step]
    for module in modules:
        try:
            module.run(region_cfg, params)
        except NotImplementedError as exc:
            raise StepNotImplementedError(step, milestone) from exc


def _cmd_check_config(region_cfg: RegionConfig, params: Params) -> int:
    print(f"Region '{region_cfg.key}':")
    for key, value in asdict(region_cfg).items():
        print(f"  {key}: {value}")
    print("Parameter geladen: " + ", ".join(asdict(params)))
    return 0


def _cmd_run(region_cfg: RegionConfig, params: Params) -> int:
    for step in RUN_ORDER:
        run_step(step, region_cfg, params)
    return 0


def _make_step_cmd(step: str) -> Callable[[RegionConfig, Params], int]:
    def cmd(region_cfg: RegionConfig, params: Params) -> int:
        run_step(step, region_cfg, params)
        return 0

    return cmd


COMMANDS: dict[str, Callable[[RegionConfig, Params], int]] = {
    "check-config": _cmd_check_config,
    "run": _cmd_run,
    **{step: _make_step_cmd(step) for step in STEPS},
}

HELP = {
    "check-config": "Konfiguration laden und anzeigen",
    "run": "Alle Schritte nacheinander ausführen",
    "fetch": "Daten abrufen (AEDs, Grenzen, Zensusgitter)",
    "coverage": "Abdeckungskennzahlen berechnen",
    "optimize": "Neue Standorte optimieren",
    "validate": "Datenvollständigkeit validieren",
    "figures": "Grafiken erzeugen",
    "export-web": "Daten für die Web-App exportieren",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.cli", description="Defi-Lücke Pipeline"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in HELP.items():
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.add_argument("--region", required=True, help="Regionsschlüssel aus config/regions.yaml")
        p.add_argument("--config-dir", default=None, help="Alternatives Konfigurationsverzeichnis")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        region_cfg, params = load_config(args.region, args.config_dir)
        return COMMANDS[args.command](region_cfg, params)
    except ConfigError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    except StepNotImplementedError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 3
    except OsmUnavailableError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 4
    except (BoundaryError, CensusError, DownloadError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 5


if __name__ == "__main__":
    sys.exit(main())
