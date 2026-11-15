import pytest

from pipeline.config import (
    ConfigError,
    available_regions,
    load_config,
    load_params,
    load_region,
)


def test_load_real_region():
    region = load_region("bernkastel-wittlich")
    assert region.name == "Landkreis Bernkastel-Wittlich"
    assert region.district_key == "07231"
    assert region.district_key_verified is True
    assert region.official_population == 112751


def test_load_real_params():
    params = load_params()
    assert params.crs["compute"] == "EPSG:3035"
    assert params.coverage["radii_m"] == [100, 200, 300, 500]
    assert params.coverage["detour_factor"] >= 1


def test_load_config_returns_both():
    region, params = load_config("bernkastel-wittlich")
    assert region.key == "bernkastel-wittlich"
    assert params.optimize["k_max_district"] == 20


def test_available_regions_lists_all():
    assert available_regions() == ["bernkastel-wittlich", "region-b"]


def test_unknown_region_lists_available():
    with pytest.raises(ConfigError) as exc:
        load_region("nirgendwo")
    msg = str(exc.value)
    assert "Unbekannte Region 'nirgendwo'" in msg
    assert "bernkastel-wittlich" in msg
    assert "region-b" in msg


def test_unconfigured_region_error():
    with pytest.raises(ConfigError, match="noch nicht konfiguriert"):
        load_region("region-b")


def test_missing_config_dir(tmp_path):
    with pytest.raises(ConfigError, match="nicht gefunden"):
        load_region("x", tmp_path)


def test_params_missing_section(tmp_path):
    (tmp_path / "params.yaml").write_text("crs: {compute: x}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="fehlende Abschnitte"):
        load_params(tmp_path)
