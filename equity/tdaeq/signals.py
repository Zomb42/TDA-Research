"""Daily building blocks for trading signals.

Everything here is "causal": the numbers for day t use only a fit made on
days before t. The fit (SPY beta, residual volatility, peer groups) is redone
every `refit` days and reused in between.
"""
import warnings
from dataclasses import dataclass

import numpy as np

from . import clusters, factors
from .data import MIN_HISTORY

NOT_USED = -2    # stock not eligible on that day
NO_GROUP = -1    # eligible, but has no close peer


@dataclass
class DailyState:
    beta: np.ndarray      # days x stocks, SPY beta from the past window
    sigma: np.ndarray     # days x stocks, daily volatility of the non-SPY part
    surprise: np.ndarray  # days x stocks, (return - beta * SPY return) / sigma
    group: np.ndarray     # days x stocks, peer-group label (HDBSCAN on the past window)
    group_plain: np.ndarray  # days x stocks, average-linkage groups cut equally fine (plain competitor)
    sector: np.ndarray    # stocks, sector label
    corr_top5: np.ndarray # days x stocks, average past correlation with the 5 closest stocks
    join: np.ndarray      # days x stocks, distance to the single closest stock (H0 join height)


def drop_singletons(labels):
    """Relabel groups that contain a single stock as NO_GROUP."""
    sizes = np.bincount(labels)
    return np.where(sizes[labels] > 1, labels, NO_GROUP)


def build_state(panel, window=252, refit=5, plain_groups=100):
    days, stocks = panel.returns.shape
    blank = lambda: np.full((days, stocks), np.nan)
    state = DailyState(blank(), blank(), blank(), np.full((days, stocks), NOT_USED),
                       np.full((days, stocks), NOT_USED),
                       clusters.factorize(panel.sectors), blank(), blank())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        for start in range(MIN_HISTORY, days, refit):
            cols = panel.eligible(start)
            geo = factors.geometry(panel.returns[start - window:start, cols],
                                   panel.market[start - window:start])
            labels = clusters.hdbscan_labels(geo.distance, min_cluster_size=2, min_samples=1)
            plain = drop_singletons(clusters.tree_labels(geo.distance, "average", plain_groups))
            nearest = np.sort(geo.distance + np.eye(len(cols)) * 9, axis=1)
            top5 = 1 - nearest[:, :5] ** 2 / 2          # distance back to correlation
            for t in range(start, min(start + refit, days)):
                state.beta[t, cols] = geo.beta
                state.sigma[t, cols] = geo.sigma
                state.surprise[t, cols] = (panel.returns[t, cols] - geo.beta * panel.market[t]) / geo.sigma
                state.group[t, cols] = labels
                state.group_plain[t, cols] = plain
                state.corr_top5[t, cols] = top5.mean(axis=1)
                state.join[t, cols] = nearest[:, 0]
    return state


def minus_group_mean(values, labels):
    """Each stock's value minus the average of the OTHER stocks in its group.
    NaN where the stock has no group or is the only usable member."""
    out = np.full(values.shape, np.nan)
    usable = np.isfinite(values) & (labels >= 0)
    for g in np.unique(labels[usable]):
        members = np.flatnonzero(usable & (labels == g))
        if len(members) < 2:
            continue
        total = values[members].sum()
        out[members] = values[members] - (total - values[members]) / (len(members) - 1)
    return out


def rolling_sum(table, n):
    """Sum of the last n rows (including today), scaled so a random walk keeps unit size.

    The table must have no NaN: one NaN makes every later row of that column NaN.
    Fill missing values with 0 first (np.nan_to_num) and mask the result afterwards.
    """
    if np.isnan(table).any():
        raise ValueError("rolling_sum needs a table without NaN; fill missing values first")
    padded = np.vstack([np.zeros((1, table.shape[1])), np.cumsum(table, axis=0)])
    out = np.full(table.shape, np.nan)
    out[n - 1:] = (padded[n:] - padded[:-n]) / np.sqrt(n)
    return out
