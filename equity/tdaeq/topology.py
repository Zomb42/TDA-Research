"""Persistence diagrams from a distance matrix, plus scrambled data to compare against.

Reading a diagram here: imagine a threshold rising from 0. Two stocks are
linked once their distance is below the threshold.
  H0 bar: a separate group of stocks. It ends ("dies") when the group links to another.
  H1 bar: a ring of stocks, each linked to the next but not across the ring.
          It is born when the ring closes and dies when links across fill it in.
A long bar is a feature that survives over a wide range of thresholds.
"""
import numpy as np
from persim import wasserstein
from ripser import ripser

from .factors import remove_market


def diagrams(distance, maxdim=1):
    """[H0, H1] arrays of (birth, death). The one never-ending H0 bar is dropped."""
    out = ripser(distance, distance_matrix=True, maxdim=maxdim)["dgms"]
    return [d[np.isfinite(d[:, 1])] for d in out]


def lifetimes(diagram):
    return diagram[:, 1] - diagram[:, 0]


def summarize(dgms):
    """A few plain numbers describing one window's diagrams."""
    h0, h1 = dgms[0], dgms[1]
    life = lifetimes(h1)
    return {
        "h0_mean_death": float(h0[:, 1].mean()),        # typical distance to nearest group
        "h0_max_death": float(h0[:, 1].max()),          # the most isolated stock or group
        "h1_count": int(len(life)),                      # number of rings
        "h1_total": float(life.sum()),                   # summed ring lifetimes
        "h1_max": float(life.max()) if len(life) else 0.0,   # longest-lived ring
    }


def diagram_distance(a, b):
    """How much one diagram must be moved to become the other (Wasserstein distance)."""
    if len(a) == 0 and len(b) == 0:
        return 0.0
    return float(wasserstein(a, b))


# ---- scrambled versions of a return window, used as "what would noise give us?" ----

def shuffle_each_stock(history, rng):
    """Every stock keeps its own returns but in a random order: no shared movement at all."""
    return np.column_stack([rng.permutation(column) for column in history.T])


def market_only(history, market, rng):
    """Keep each stock's link to SPY; scramble everything else."""
    residual, alpha, beta = remove_market(history, market)
    fitted = history - residual
    return fitted + shuffle_each_stock(residual, rng)


def market_and_groups(history, market, labels, rng):
    """Keep the link to SPY and to the stock's own group average; scramble the rest.

    If real data shows more structure than this, the structure is finer than
    "market plus sectors".
    """
    residual, alpha, beta = remove_market(history, market)
    kept = np.zeros_like(residual)
    for g in np.unique(labels):
        members = np.flatnonzero(labels == g)
        if len(members) < 2:
            continue
        for i in members:
            others = members[members != i]
            factor = residual[:, others].mean(axis=1)
            factor = factor - factor.mean()
            slope = factor @ residual[:, i] / (factor @ factor)
            kept[:, i] = slope * factor
    leftover = residual - kept
    return (history - residual) + kept + shuffle_each_stock(leftover, rng)
