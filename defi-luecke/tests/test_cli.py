import subprocess
import sys

from pipeline.cli import main


def test_check_config_exit_zero(capsys):
    assert main(["check-config", "--region", "bernkastel-wittlich"]) == 0
    out = capsys.readouterr().out
    assert "07231" in out


def test_not_implemented_module_gives_german_message(monkeypatch, capsys):
    """A module raising NotImplementedError is reported as a German step message (exit 3).

    Uses a patched module so the test does not run real steps or write into data/.
    """
    from pipeline import cli

    class _Stub:
        @staticmethod
        def run(region_cfg, params):
            raise NotImplementedError

    monkeypatch.setitem(cli.STEPS, "validate", ("M5", (_Stub,)))
    assert main(["validate", "--region", "bernkastel-wittlich"]) == 3
    err = capsys.readouterr().err
    assert "Schritt 'validate' ist noch nicht implementiert (Meilenstein M5)" in err


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
