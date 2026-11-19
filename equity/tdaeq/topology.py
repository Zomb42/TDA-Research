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


def path_bars(levels):
    """Valley barcode of ONE series (0-dimensional sublevel-set persistence).

    Picture water rising from the bottom of the chart. Every valley (local low)
    starts its own pool at the valley's level: its birth. When the water reaches
    the peak between two pools they join, and the pool with the higher floor
    ends there: its death. The deepest pool never ends and is left out.

    Returns a list of (birth, death, position of the valley), one per pool that
    ends. death - birth is the size of a dip that was fully recovered inside the
    window. Call with the negated series to get the same for peaks.
    """
    x = [float(v) for v in levels]
    n = len(x)
    root, floor, bars = [-1] * n, [0] * n, []      # floor = position of a pool's lowest point
    for i in sorted(range(n), key=x.__getitem__):
        root[i], floor[i] = i, i
        for j in (i - 1, i + 1):
            if 0 <= j < n and root[j] >= 0:
                a, b = i, j
                while root[a] != a:
                    a = root[a]
                while root[b] != b:
                    b = root[b]
                if a == b:
                    continue
                young, old = (a, b) if x[floor[a]] >= x[floor[b]] else (b, a)
                if x[i] > x[floor[young]]:
                    bars.append((x[floor[young]], x[i], floor[young]))
                root[young] = old
    return bars


def path_pairs(levels):
    """Same sweep as path_bars, returning positions instead of levels:
    (position of the valley floor, position of the peak where it was recovered).

    For a series x, each bar is (x[birth], x[death]). Written this way a bar's
    length x[death] - x[birth] can be differentiated with respect to x: the
    positions are found from the current values, and the length is then a
    plain difference of two entries. Used by study 14 to learn the filter.
    """
    x = [float(v) for v in levels]
    n = len(x)
    root, floor, pairs = [-1] * n, [0] * n, []
    for i in sorted(range(n), key=x.__getitem__):
        root[i], floor[i] = i, i
        for j in (i - 1, i + 1):
            if 0 <= j < n and root[j] >= 0:
                a, b = i, j
                while root[a] != a:
                    a = root[a]
                while root[b] != b:
                    b = root[b]
                if a == b:
                    continue
                young, old = (a, b) if x[floor[a]] >= x[floor[b]] else (b, a)
                if x[i] > x[floor[young]]:
                    pairs.append((floor[young], i))
                root[young] = old
    return pairs
