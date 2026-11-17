"""Check that the shared library reproduces the old headline numbers.

Run on the October 27 data vintage, because that is what the old experiments
used. If these match, the new code is a faithful replacement for the old
one-off scripts.

    conda run -n tda python equity/studies/s00_baseline_check.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from tdaeq import clusters, data, evaluate, factors, portfolio

# Old results, from the archived experiment tables.
EXPECTED = {
    "later mean (bps/day)": 1.343,
    "later CAGR (%)": 3.37,
    "full CAGR (%)": 0.68,
    "later gap, H0": 0.0625,
    "later gap, average linkage": 0.2098,
    "later gap, sectors": 0.1452,
}


def reversal_book(panel, window=120, n_pcs=3):
    """The original strategy: fit on the past `window` days, bet against today's surprise,
    hold from tomorrow's open to tomorrow's close."""
    days, returns = [], []
    for t in range(data.MIN_HISTORY, len(panel.dates) - 1):
        cols = panel.eligible(t)
        exposures, weights, _ = factors.factor_exposures(
            panel.returns[t - window:t, cols], panel.market[t - window:t], n_pcs)
        holdings, _ = portfolio.neutral_book(panel.returns[t, cols], exposures, weights)
        days.append(t + 1)
        returns.append(holdings @ portfolio.open_to_close(panel, t + 1, cols))
    return np.array(days), np.array(returns)


def structure_gaps(panel, window=252, k=11, horizon=20):
    """Form groups from the past, then score them on the next 20 days' correlations."""
    rows = []
    for t in range(data.MIN_HISTORY, len(panel.dates) - horizon, horizon):
        if panel.is_later(t + 1) != panel.is_later(t + horizon):
            continue                                   # block straddles the 2024 split
        cols = panel.eligible(t)
        past = factors.geometry(panel.returns[t - window:t, cols], panel.market[t - window:t])
        future = (panel.returns[t + 1:t + 1 + horizon, cols] - past.alpha
                  - np.outer(panel.market[t + 1:t + 1 + horizon], past.beta))
        future_corr = np.corrcoef(future, rowvar=False)
        rows.append((panel.is_later(t + 1),
                     clusters.correlation_gap(clusters.tree_labels(past.distance, "single", k), future_corr),
                     clusters.correlation_gap(clusters.tree_labels(past.distance, "average", k), future_corr),
                     clusters.correlation_gap(clusters.factorize(panel.sectors[cols]), future_corr)))
    return np.array(rows, dtype=float)


def main():
    panel = data.load_panel(data.OLD_VINTAGE)
    days, returns = reversal_book(panel)
    later = np.array([panel.is_later(t) for t in days])
    gaps = structure_gaps(panel)
    later_gaps = gaps[gaps[:, 0] == 1, 1:].mean(axis=0)

    got = {
        "later mean (bps/day)": evaluate.performance(returns[later])["mean_bps"],
        "later CAGR (%)": evaluate.performance(returns[later])["cagr_pct"],
        "full CAGR (%)": evaluate.performance(returns)["cagr_pct"],
        "later gap, H0": later_gaps[0],
        "later gap, average linkage": later_gaps[1],
        "later gap, sectors": later_gaps[2],
    }
    print(f"trading days: {len(returns)} (later: {later.sum()}), structure blocks: {len(gaps)}")
    ok = True
    for name, old in EXPECTED.items():
        match = abs(got[name] - old) < 0.006 * max(1, abs(old))
        ok &= match
        print(f"{name:30s} old {old:8.4f}   new {got[name]:8.4f}   {'match' if match else 'DIFFERENT'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
