"""Optimizer tests. All data is SYNTHETIC (see tests/synthetic_layers.py)."""

import math

import numpy as np
import pytest
from pyproj import Transformer
from scipy import sparse

from pipeline import coverage, optimize
from pipeline.optimize import build_cover_matrix, exact_max_cover, greedy, optimize_layers
from tests.synthetic_layers import make_layers, make_params


def cover_from_sets(sets, n_elements):
    rows = [i for i, s in enumerate(sets) for _ in s]
    cols = [e for s in sets for e in s]
    return sparse.csr_matrix(
        (np.ones(len(rows), dtype=np.int8), (rows, cols)), shape=(len(sets), n_elements)
    )


def naive_greedy(cover, w, k):
    dense = cover.toarray() > 0
    w = np.asarray(w, dtype=float).copy()
    out = []
    for _ in range(k):
        gains = dense @ w
        i = int(np.argmax(gains))  # argmax picks the lowest index on ties
        if gains[i] <= 0:
            break
        out.append((i, float(gains[i])))
        w[dense[i]] = 0
    return out


def test_greedy_matches_known_optimum():
    # disjoint sets: greedy is optimal. weights 5,4,3 | 2,2 | 1
    cover = cover_from_sets([[0, 1], [2, 3], [4], [5]], 6)
    w = np.array([5, 4, 3, 2, 2, 1])
    picks = greedy(cover, w, 2)
    assert picks == [(0, 9.0), (1, 5.0)]
    opt, opt_set = exact_max_cover(cover, w, 2)
    assert opt == 14 and set(opt_set) == {0, 1}
    assert sum(g for _, g in picks) == opt


def test_greedy_suboptimal_counterexample():
    # classic: greedy takes the big middle set first and ends with 5 of the optimal 6
    sets = [[0, 1, 3, 4], [0, 1, 2], [3, 4, 5], [2], [5]]
    cover = cover_from_sets(sets, 6)
    w = np.ones(6)
    picks = greedy(cover, w, 2)
    assert picks[0] == (0, 4.0)
    value = sum(g for _, g in picks)
    opt, opt_set = exact_max_cover(cover, w, 2)
    assert opt == 6 and set(opt_set) == {1, 2}
    assert value == 5 < opt
    assert value >= (1 - 1 / math.e) * opt


def test_greedy_tie_break_lowest_index():
    cover = cover_from_sets([[0], [1], [0], [1]], 2)
    assert greedy(cover, np.array([3.0, 3.0]), 2) == [(0, 3.0), (1, 3.0)]


def test_greedy_stops_without_gain_and_handles_empty():
    cover = cover_from_sets([[0]], 2)
    assert greedy(cover, np.array([1.0, 0.0]), 5) == [(0, 1.0)]
    assert greedy(sparse.csr_matrix((3, 0)), np.zeros(0), 2) == []


def test_lazy_greedy_equals_naive_and_bounds_on_random_instances():
    rng = np.random.default_rng(0)
    for _ in range(40):
        n_c, n_e, k = 8, 14, 3
        dense = (rng.random((n_c, n_e)) < 0.3).astype(np.int8)
        cover = sparse.csr_matrix(dense)
        w = rng.integers(0, 6, n_e).astype(float)
        picks = greedy(cover, w, k)
        assert picks == naive_greedy(cover, w, k)
        opt, _ = exact_max_cover(cover, w, k)
        value = sum(g for _, g in picks)
        assert value <= opt + 1e-9
        assert value >= (1 - 1 / math.e) * opt - 1e-9


def test_cover_matrix_boundary_inclusive():
    # R = 130 m effective, detour 1.3 -> 100 m straight line, boundary covered
    cand = np.array([[0.0, 0.0]])
    demand = np.array([[100.0, 0.0], [100.5, 0.0], [0.0, -99.0]])
    m = build_cover_matrix(cand, demand, 130, 1.3)
    assert m.toarray().tolist() == [[1, 0, 1]]


def test_cover_matrix_empty():
    assert build_cover_matrix(np.empty((0, 2)), np.zeros((2, 2)), 100, 1.3).shape == (0, 2)
    assert build_cover_matrix(np.zeros((2, 2)), np.empty((0, 2)), 100, 1.3).shape == (2, 0)


def test_optimize_layers_district_variant_a():
    layers, params = make_layers(), make_params(radii_m=[200])
    res = optimize_layers(layers, params)
    a = res[("A", "district")]
    # existing (scenario all) cover pop 30 of 105; uncovered cells: 30 (Alpha east), 40, 5
    assert list(a["rank"]) == [1, 2, 3]
    assert list(a["added_population"]) == [40, 30, 5]
    assert list(a["cumulative_covered"]) == [70, 100, 105]
    assert a["cumulative_rate"].iloc[-1] == pytest.approx(1.0)
    assert a["cumulative_rate"].iloc[0] == pytest.approx(70 / 105)
    assert list(a["label"]) == ["Beta", "Alpha", "Beta"]
    assert (a["scope_id"] == "07231").all() and (a["scenario"] == "all").all()
    # lon/lat consistent with EPSG:3035 -> 4326
    lon, lat = Transformer.from_crs(3035, 4326, always_xy=True).transform(a["x"], a["y"])
    assert np.allclose(lon, a["lon"]) and np.allclose(lat, a["lat"])
    assert a["lon"].between(5, 15).all() and a["lat"].between(45, 55).all()


def test_optimize_layers_municipality_and_variant_b():
    layers, params = make_layers(), make_params(radii_m=[200])
    res = optimize_layers(layers, params)
    a_m = res[("A", "municipality")]
    beta = a_m[a_m["scope_id"] == "07231002"]
    assert list(beta["added_population"]) == [40, 5]
    assert beta["cumulative_rate"].iloc[-1] == pytest.approx(1.0)  # scope population 45
    alpha = a_m[a_m["scope_id"] == "07231001"]
    assert list(alpha["added_population"]) == [30]
    assert alpha["cumulative_rate"].iloc[0] == pytest.approx(1.0)  # 30 already + 30 added of 60

    # variant B: candidates (480,1000) "Rathaus Beta" covers cell (500,1000)=5 within 153.8 m;
    # (950,50) unnamed -> category label, covers cell (1000,0)=30
    b = res[("B", "district")]
    assert list(b["added_population"]) == [30, 5]
    assert list(b["label"]) == ["amenity=pharmacy", "Rathaus Beta"]


def test_variant_b_skipped_with_warning_when_no_candidates():
    layers, params = make_layers(), make_params(radii_m=[200])
    layers.candidates = layers.candidates.iloc[0:0]
    with pytest.warns(UserWarning, match="Variante B"):
        res = optimize_layers(layers, params)
    assert ("B", "district") not in res and ("A", "district") in res


def test_run_writes_csvs(tmp_path, monkeypatch):
    from pipeline.config import RegionConfig

    monkeypatch.setattr(coverage, "PROJECT_ROOT", tmp_path)
    region = RegionConfig(key="synthetic", name="T", state="T", district_key="07231")
    layers = make_layers()
    path = coverage.interim_path(region)
    path.parent.mkdir(parents=True)
    for name in ("aeds", "cells", "municipalities", "vg", "district", "candidates"):
        getattr(layers, name).to_file(path, layer=name, driver="GPKG")
    optimize.run(region, make_params(radii_m=[200]))
    out = coverage.processed_dir(region)
    for variant in "AB":
        for scope in ("district", "municipality"):
            assert (out / f"optimize_{variant}_{scope}.csv").is_file()
