"""Scoring helpers: performance numbers, confidence intervals, rank correlation."""
import numpy as np
from scipy.stats import rankdata

DAYS_PER_YEAR = 252


def performance(returns):
    """Standard summary of a daily return series (simple returns, before costs)."""
    r = np.asarray(returns, dtype=float)
    equity = np.cumprod(1 + r)
    peak = np.maximum.accumulate(np.r_[1.0, equity])[1:]
    sd = r.std(ddof=1)
    return {
        "days": len(r),
        "mean_bps": r.mean() * 1e4,
        "vol_pct": sd * np.sqrt(DAYS_PER_YEAR) * 100,
        "sharpe": r.mean() / sd * np.sqrt(DAYS_PER_YEAR) if sd > 0 else np.nan,
        "cagr_pct": (equity[-1] ** (DAYS_PER_YEAR / len(r)) - 1) * 100,
        "max_drawdown_pct": float(np.min(equity / peak - 1)) * 100,
    }


def block_resamples(n, block=60, repetitions=1000, seed=0):
    """Row indices for a circular block bootstrap.

    Days close together are not independent, so we resample whole runs of
    `block` consecutive days instead of single days.
    """
    rng = np.random.default_rng(seed)
    starts = rng.integers(n, size=(repetitions, int(np.ceil(n / block))))
    return ((starts[:, :, None] + np.arange(block)) % n).reshape(repetitions, -1)[:, :n]


def mean_ci(values, block=60, repetitions=1000, seed=0):
    """Mean with an approximate 95% interval from the block bootstrap."""
    v = np.asarray(values, dtype=float)
    boot = v[block_resamples(len(v), block, repetitions, seed)].mean(axis=1)
    low, high = np.quantile(boot, [0.025, 0.975])
    return float(v.mean()), float(low), float(high)


def rank_ic(signal, outcome):
    """Rank correlation between a signal and what happened next, across stocks on one day.

    +1 means the ranking was perfect, 0 means no relation, -1 means backwards.
    """
    ok = np.isfinite(signal) & np.isfinite(outcome)
    if ok.sum() < 10:
        return np.nan
    a, b = rankdata(signal[ok]), rankdata(outcome[ok])
    a, b = a - a.mean(), b - b.mean()
    denom = np.sqrt((a @ a) * (b @ b))
    return float(a @ b / denom) if denom > 0 else np.nan
