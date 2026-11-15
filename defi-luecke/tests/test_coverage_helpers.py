import pytest

from pipeline.coverage import effective_distance, radius_from_round_trip


def test_radius_from_round_trip():
    # 180 s round trip at 1.4 m/s -> 90 s one way -> 126 m
    assert radius_from_round_trip(180, 1.4) == pytest.approx(126.0)


@pytest.mark.parametrize(("t", "v"), [(0, 1.4), (-1, 1.4), (180, 0), (180, -1)])
def test_radius_rejects_non_positive(t, v):
    with pytest.raises(ValueError):
        radius_from_round_trip(t, v)


def test_effective_distance():
    assert effective_distance(100, 1.3) == pytest.approx(130.0)
    assert effective_distance(0, 1.3) == 0
    assert effective_distance(50, 1) == 50


def test_effective_distance_rejects_invalid():
    with pytest.raises(ValueError):
        effective_distance(-1, 1.3)
    with pytest.raises(ValueError):
        effective_distance(10, 0.9)
