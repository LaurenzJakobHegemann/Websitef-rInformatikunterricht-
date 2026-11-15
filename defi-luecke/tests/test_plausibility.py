"""Plausibility check tests. SYNTHETIC data."""

import numpy as np

from pipeline import plausibility as pl


def test_population_deviation_pass_and_fail():
    ok = pl.check_population(11_000, 11_100, 3.0)
    assert ok.passed and round(ok.details["deviation_pct"], 2) == -0.9
    bad = pl.check_population(10_000, 11_100, 3.0)
    assert not bad.passed
    assert not pl.check_population(1, None, 3.0).passed


def test_aed_count():
    assert pl.check_aed_count(1).passed
    assert not pl.check_aed_count(0).passed


def test_in_query_area():
    bbox = (49.0, 6.0, 50.0, 7.0)  # s, w, n, e
    assert pl.check_in_query_area(np.array([6.5]), np.array([49.5]), bbox).passed
    res = pl.check_in_query_area(np.array([6.5, 8.0]), np.array([49.5, 49.5]), bbox)
    assert not res.passed and res.details["n_outside"] == 1


def test_find_duplicates_keeps_first():
    x = np.array([0.0, 3.0, 100.0, 101.0, 500.0])
    y = np.zeros(5)
    keep, recs = pl.find_duplicates(x, y, ["a", "b", "c", "d", "e"], 5)
    assert list(keep) == [True, False, True, False, True]
    assert [(r["kept"], r["dropped"]) for r in recs] == [("a", "b"), ("c", "d")]
    assert not pl.check_duplicates(recs, 5).passed


def test_no_duplicates():
    keep, recs = pl.find_duplicates(np.array([0.0, 50.0]), np.array([0.0, 0.0]), ["a", "b"], 5)
    assert keep.all() and recs == [] and pl.check_duplicates(recs, 5).passed
    keep, recs = pl.find_duplicates(np.array([]), np.array([]), [], 5)
    assert len(keep) == 0
