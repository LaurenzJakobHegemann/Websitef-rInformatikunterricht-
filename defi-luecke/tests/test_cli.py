import subprocess
import sys

import pytest

from pipeline.cli import main

STEP_MILESTONES = {
    "coverage": "M2",
    "optimize": "M3",
    "validate": "M5",
    "figures": "M5",
    "export-web": "M4",
}


def test_check_config_exit_zero(capsys):
    assert main(["check-config", "--region", "bernkastel-wittlich"]) == 0
    out = capsys.readouterr().out
    assert "07231" in out


@pytest.mark.parametrize(("step", "milestone"), STEP_MILESTONES.items())
def test_stub_step_fails_with_german_message(step, milestone, capsys):
    code = main([step, "--region", "bernkastel-wittlich"])
    assert code != 0
    err = capsys.readouterr().err
    assert f"Schritt '{step}' ist noch nicht implementiert (Meilenstein {milestone})" in err


def test_run_stops_at_first_failing_step(monkeypatch, capsys):
    from pipeline import cli

    def fake_run_step(step, region_cfg, params):
        raise cli.StepNotImplementedError(step, "M1")

    monkeypatch.setattr(cli, "run_step", fake_run_step)
    assert main(["run", "--region", "bernkastel-wittlich"]) != 0
    assert "Schritt 'fetch' ist noch nicht implementiert" in capsys.readouterr().err


def test_fetch_osm_unavailable_exits_4(monkeypatch, capsys):
    from pipeline import cli
    from pipeline.fetch_osm import OsmUnavailableError

    def fake_run_step(step, region_cfg, params):
        raise OsmUnavailableError("Manueller Schritt: ...")

    monkeypatch.setattr(cli, "run_step", fake_run_step)
    assert main(["fetch", "--region", "bernkastel-wittlich"]) == 4
    assert "Manueller Schritt" in capsys.readouterr().err


def test_unknown_region_nonzero(capsys):
    assert main(["coverage", "--region", "nirgendwo"]) != 0
    assert "Verfügbare Regionen" in capsys.readouterr().err


def test_unconfigured_region_nonzero(capsys):
    assert main(["check-config", "--region", "region-b"]) != 0
    assert "noch nicht konfiguriert" in capsys.readouterr().err


def test_module_entrypoint_subprocess():
    result = subprocess.run(
        [sys.executable, "-m", "pipeline.cli", "check-config", "--region", "bernkastel-wittlich"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Landkreis Bernkastel-Wittlich" in result.stdout
