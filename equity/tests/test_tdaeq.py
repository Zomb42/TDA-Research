"""Small checks that the building blocks do what their names say.

    conda run -n tda python equity/tests/test_tdaeq.py

(pytest is not installed in the tda environment, so the file runs itself.)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from scipy.spatial.distance import pdist, squareform

from tdaeq import clusters, evaluate, factors, portfolio, topology


def fake_returns(days=300, groups=4, per_group=10, seed=0):
    """Returns with a market move, a group move and stock-specific noise."""
    rng = np.random.default_rng(seed)
    market = rng.normal(0, 0.01, days)
    labels = np.repeat(np.arange(groups), per_group)
    group_moves = rng.normal(0, 0.008, (days, groups))
    noise = rng.normal(0, 0.008, (days, groups * per_group))
    return market[:, None] + group_moves[:, labels] + noise, market, labels


def test_h0_deaths_equal_single_linkage_heights():
    history, market, _ = fake_returns()
    distance = factors.geometry(history, market).distance
    h0 = topology.diagrams(distance)[0]
    heights = clusters.tree(distance, "single")[:, 2]
    assert np.allclose(np.sort(h0[:, 1]), np.sort(heights)[:len(h0)], atol=1e-6)


def test_circle_has_one_long_ring():
    angles = np.linspace(0, 2 * np.pi, 40, endpoint=False)
    points = np.column_stack([np.cos(angles), np.sin(angles)])
    life = np.sort(topology.lifetimes(topology.diagrams(squareform(pdist(points)))[1]))
    assert life[-1] > 1.0 and (len(life) == 1 or life[-2] < 0.1)


def test_neutral_book_cancels_every_exposure():
    history, market, _ = fake_returns()
    exposures, weights, _ = factors.factor_exposures(history[:-1], market[:-1], n_pcs=3)
    holdings, _ = portfolio.neutral_book(history[-1], exposures, weights)
    assert np.isclose(np.abs(holdings).sum(), 1)
    assert np.max(np.abs(exposures.T @ holdings)) < 1e-9


def test_planted_groups_are_recovered_and_score_well():
    history, market, truth = fake_returns(days=600)
    past = factors.geometry(history[:300], market[:300])
    future_corr = factors.geometry(history[300:], market[300:]).corr
    found = clusters.tree_labels(past.distance, "average", 4)
    assert clusters.correlation_gap(found, future_corr) > 0.3
    scrambled = np.random.default_rng(1).permutation(found)
    assert abs(clusters.correlation_gap(scrambled, future_corr)) < 0.1
    dense = clusters.hdbscan_labels(past.distance, min_cluster_size=5)
    assert clusters.describe(dense)["groups"] == 4
    assert clusters.correlation_gap(dense, future_corr) > 0.3


def test_scrambling_removes_group_structure():
    history, market, _ = fake_returns()
    rng = np.random.default_rng(2)
    real = factors.geometry(history, market).corr
    fake = factors.geometry(topology.market_only(history, market, rng), market).corr
    off = ~np.eye(len(real), dtype=bool)
    assert np.abs(real[off]).mean() > 3 * np.abs(fake[off]).mean()


def test_rank_ic_and_bootstrap():
    x = np.arange(50.0)
    assert np.isclose(evaluate.rank_ic(x, 2 * x + 1), 1)
    assert np.isclose(evaluate.rank_ic(x, -x), -1)
    mean, low, high = evaluate.mean_ci(np.random.default_rng(3).normal(1, 1, 2000))
    assert low < 1 < high and abs(mean - 1) < 0.1


def test_path_bars():
    # the worked example in Zeng et al. (2021), Figure 2: x1 < x3 < x2 < x5 < x4
    bars = topology.path_bars([0, 2, 1, 4, 3])
    assert sorted(b[:2] for b in bars) == [(1, 2), (3, 4)]
    # for any path: distance travelled = range + total length of all valley and peak bars
    rng = np.random.default_rng(4)
    for _ in range(200):
        path = np.cumsum(rng.normal(size=61))
        total = sum(d - b for b, d, _ in topology.path_bars(path) + topology.path_bars(-path))
        assert np.isclose(np.abs(np.diff(path)).sum(), np.ptp(path) + total)


if __name__ == "__main__":
    for name, check in list(globals().items()):
        if name.startswith("test_"):
            check()
            print("ok  ", name)
