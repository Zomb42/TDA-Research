"""Ways of putting stocks into peer groups, and one score for how good the groups are.

All methods take the stock-by-stock distance matrix from `factors.geometry`.
Labels are integers, one per stock. A label of -1 means "belongs to no group".
"""
import numpy as np
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.spatial.distance import squareform
from sklearn.cluster import HDBSCAN


def tree(distance, method):
    """Build the merge tree. method='single' is exactly H0 of the Rips filtration."""
    return linkage(squareform(distance, checks=False), method=method)


def tree_labels(distance, method, k):
    """Cut the tree where exactly k groups remain."""
    return cut_tree(tree(distance, method), n_clusters=[k])[:, 0]


def hdbscan_labels(distance, min_cluster_size=3, min_samples=None, selection="eom"):
    """Single linkage made robust to 'bridge' stocks.

    A stock only counts as close to another if both sit in a dense
    neighbourhood, so one stray link cannot chain two groups together. Groups
    are then kept by how long they survive as the distance threshold grows
    (their persistence), not by asking for a fixed number of groups.
    """
    model = HDBSCAN(metric="precomputed", min_cluster_size=min_cluster_size,
                    min_samples=min_samples, cluster_selection_method=selection,
                    allow_single_cluster=False, copy=True)
    return model.fit_predict(distance.astype(float))


def factorize(names):
    """Turn sector names into integer labels."""
    _, labels = np.unique(names, return_inverse=True)
    return labels


def same_group(labels):
    """Stock x stock table: True where two different stocks share a real group."""
    same = (labels[:, None] == labels[None, :]) & (labels[:, None] >= 0)
    np.fill_diagonal(same, False)
    return same


def correlation_gap(labels, corr):
    """Average correlation of pairs inside a group minus pairs in different groups.

    Feed it a correlation matrix from days AFTER the groups were formed. A big
    positive number means the groups kept moving together.
    """
    upper = np.triu_indices(len(labels), 1)
    inside = same_group(labels)[upper]
    values = corr[upper]
    if inside.all() or not inside.any():
        return np.nan
    return values[inside].mean() - values[~inside].mean()


def describe(labels):
    """Group count, size of the largest group, and how many stocks have no group."""
    real = labels[labels >= 0]
    sizes = np.bincount(real) if len(real) else np.array([0])
    return {"groups": int((sizes > 0).sum()), "largest": int(sizes.max()),
            "ungrouped": int((labels < 0).sum()), "in_pairs_or_more": int(sizes[sizes > 1].sum())}
