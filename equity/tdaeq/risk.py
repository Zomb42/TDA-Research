"""Ways of estimating how stocks' risks combine (the covariance matrix),
and two portfolios that depend on getting it right.

With about 200 stocks and 252 days there are ~20,000 pairwise covariances to
estimate from little data, so the raw estimate is noisy. Each method below
simplifies it in a different way.
"""
import numpy as np
from scipy.cluster.hierarchy import cophenet, leaves_list, linkage
from scipy.spatial.distance import squareform
from sklearn.covariance import LedoitWolf

from .factors import remove_market


def sample(history):
    """The raw estimate: no simplification."""
    return np.cov(history, rowvar=False)


def shrunk(history):
    """Ledoit-Wolf: pull the raw estimate part-way toward 'all stocks unrelated'."""
    return LedoitWolf().fit(history).covariance_


def pca_factors(history, count=10):
    """Keep the `count` strongest common patterns; treat everything else as stock-specific."""
    cov = sample(history)
    values, vectors = np.linalg.eigh(cov)
    top = vectors[:, -count:] * np.sqrt(values[-count:])
    common = top @ top.T
    return common + np.diag(np.maximum(np.diag(cov) - np.diag(common), 1e-10))


def _make_valid(corr):
    """Clip tiny negative eigenvalues so the matrix is a usable correlation matrix."""
    values, vectors = np.linalg.eigh(corr)
    fixed = (vectors * np.maximum(values, 1e-6)) @ vectors.T
    scale = np.sqrt(np.diag(fixed))
    return fixed / np.outer(scale, scale)


def tree_filtered(history, method):
    """Replace each pair's correlation by the level at which the two stocks join in a merge tree.

    method='single' is the H0 tree: a pair gets the weakest link on the strongest
    chain connecting them. method='average' gives the average correlation
    between the two branches that merge.
    """
    sd = history.std(axis=0, ddof=1)
    corr = np.corrcoef(history, rowvar=False)
    gap = 1 - corr
    np.fill_diagonal(gap, 0)
    tree = linkage(squareform(gap, checks=False), method=method)
    filtered = 1 - squareform(cophenet(tree))
    np.fill_diagonal(filtered, 1)
    return _make_valid(filtered) * np.outer(sd, sd)


def market_plus_groups(history, market, labels):
    """SPY explains the common part; inside each peer group the leftover moves share
    one average correlation; stocks in different groups (or in none) are unrelated."""
    residual, _, beta = remove_market(history, market)
    sd = residual.std(axis=0, ddof=1)
    corr = np.corrcoef(residual, rowvar=False)
    block = np.eye(len(sd))
    for g in np.unique(labels[labels >= 0]):
        members = np.flatnonzero(labels == g)
        if len(members) < 2:
            continue
        pairs = corr[np.ix_(members, members)][np.triu_indices(len(members), 1)]
        block[np.ix_(members, members)] = max(pairs.mean(), 0)
        block[members, members] = 1
    return np.outer(beta, beta) * market.var(ddof=1) + block * np.outer(sd, sd)


def min_variance(cov):
    """Fully invested weights (sum to 1, shorts allowed) with the lowest predicted risk."""
    raw = np.linalg.pinv(cov) @ np.ones(len(cov))
    return raw / raw.sum()


def risk_parity_tree(cov, method="single", order=None):
    """Hierarchical risk parity (long only). Order stocks by a merge tree so
    similar ones sit together, then split the list in halves again and again,
    giving each half a share inversely proportional to its risk.

    Pass `order` to skip the tree and use any ordering (used as a control:
    a random order tests whether the tree itself is doing the work)."""
    if order is None:
        sd = np.sqrt(np.diag(cov))
        gap = 1 - cov / np.outer(sd, sd)
        np.fill_diagonal(gap, 0)
        order = leaves_list(linkage(squareform(np.maximum(gap, 0), checks=False), method=method))

    def cluster_variance(items):
        part = cov[np.ix_(items, items)]
        w = 1 / np.diag(part)
        w /= w.sum()
        return w @ part @ w

    weights = np.ones(len(cov))
    stack = [order]
    while stack:
        items = stack.pop()
        if len(items) < 2:
            continue
        left, right = items[:len(items) // 2], items[len(items) // 2:]
        var_left, var_right = cluster_variance(left), cluster_variance(right)
        share_left = 1 - var_left / (var_left + var_right)
        weights[left] *= share_left
        weights[right] *= 1 - share_left
        stack += [left, right]
    return weights
