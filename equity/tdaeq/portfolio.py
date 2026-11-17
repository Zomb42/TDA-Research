"""Build the neutral long/short book."""
import numpy as np


def neutral_book(signal, exposures, weights):
    """Bet against `signal` while holding zero of every exposure column.

    Steps: (1) explain today's signal with the exposure columns by weighted
    regression, (2) keep the unexplained part (the "surprise"), (3) hold
    minus weight x surprise, scaled so the absolute positions add to 1.

    Returns (holdings, surprise). Because of step 3 the holdings are exactly
    neutral: exposures.T @ holdings is zero for every column.
    (Ported unchanged from the original `construct` function.)
    """
    scale = np.sqrt(np.mean(exposures * exposures, axis=0))
    if np.any(scale <= 0):
        raise ValueError("an exposure column is all zeros")
    x = exposures / scale
    root_w = np.sqrt(weights)
    coef, _, rank, _ = np.linalg.lstsq(root_w[:, None] * x, root_w * signal, rcond=None)
    if rank != x.shape[1]:
        raise ValueError("exposure columns are redundant")
    surprise = signal - x @ coef
    weighted = weights * surprise
    total = np.abs(weighted).sum()
    holdings = -weighted / total if total > 0 else np.zeros_like(signal)
    if np.max(np.abs(x.T @ holdings)) > 1e-9:
        raise ValueError("book is not neutral")
    return holdings, surprise


def open_to_close(panel, t, columns):
    """Simple return from day t's open to day t's close, unadjusted prices."""
    return panel.close_raw[t, columns] / panel.open_raw[t, columns] - 1
