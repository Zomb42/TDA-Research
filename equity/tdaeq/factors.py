"""Remove common movement from stock returns and measure what is left.

`history` is always a block of past returns, days x stocks. `market` is SPY's
return on the same days.
"""
from dataclasses import dataclass

import numpy as np

SIGMA_FLOOR = 1e-4   # daily; stops division by ~0 for a near-constant series


@dataclass
class Geometry:
    """How the stocks in one window relate to each other once SPY is removed."""
    alpha: np.ndarray        # stocks, intercept of the SPY fit
    beta: np.ndarray         # stocks, slope on SPY
    residual: np.ndarray     # days x stocks, return minus the SPY fit
    sigma: np.ndarray        # stocks, standard deviation of the residual
    z: np.ndarray            # days x stocks, residual standardised to mean 0, sd 1
    corr: np.ndarray         # stocks x stocks, correlation of residuals
    distance: np.ndarray     # stocks x stocks, sqrt(2 * (1 - corr)); 0 = identical


def remove_market(history, market):
    """Fit each stock on SPY and return (residual, alpha, beta)."""
    design = np.column_stack([np.ones(len(market)), market])
    coef = np.linalg.lstsq(design, history, rcond=None)[0]
    return history - design @ coef, coef[0], coef[1]


def corr_to_distance(corr):
    """Correlation 1 gives distance 0, correlation 0 gives 1.41, correlation -1 gives 2."""
    distance = np.sqrt(np.maximum(2 * (1 - corr), 0))
    np.fill_diagonal(distance, 0)
    return distance


def geometry(history, market):
    residual, alpha, beta = remove_market(history, market)
    sigma = np.maximum(residual.std(axis=0, ddof=1), SIGMA_FLOOR)
    z = (residual - residual.mean(axis=0)) / sigma
    corr = z.T @ z / (len(z) - 1)
    return Geometry(alpha, beta, residual, sigma, z, corr, corr_to_distance(corr))


def principal_directions(geo, count):
    """Top `count` PCA directions of the standardised residuals, in raw-return units.

    Each column says how much each stock moves when that common pattern moves.
    """
    _, _, vt = np.linalg.svd(geo.z, full_matrices=False)
    return geo.sigma[:, None] * vt[:count].T


def factor_exposures(history, market, n_pcs=3):
    """Exposure columns for the neutral book: dollars, SPY beta, then `n_pcs` PCA patterns.

    Also returns the regression weights (1 / total return variance) and the geometry.
    """
    geo = geometry(history, market)
    columns = [np.ones(history.shape[1]), geo.beta]
    if n_pcs:
        columns.append(principal_directions(geo, n_pcs))
    total_sigma = np.maximum(history.std(axis=0, ddof=1), SIGMA_FLOOR)
    return np.column_stack(columns), 1 / total_sigma**2, geo


def group_exposures(labels, beta):
    """Exposure columns that make the book neutral inside every group, plus SPY beta."""
    groups = np.unique(labels)
    indicators = (labels[:, None] == groups[None, :]).astype(float)
    return np.column_stack([indicators, beta])
