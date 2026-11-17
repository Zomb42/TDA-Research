"""B1. Does knowing the shape of stock relationships give a better risk estimate?

Every 20 days, estimate the covariance of all eligible stocks from the past
window in several ways, build the lowest-risk portfolio each estimate implies,
and measure the volatility that portfolio ACTUALLY has over the next 20 days.
A better estimate gives a lower realized volatility.

Two portfolios:
  minimum variance   weights sum to 1, shorts allowed; very sensitive to estimation noise
  risk parity tree   long only (hierarchical risk parity); uses a merge tree directly.
                     The same method with stocks in RANDOM order is the control that
                     shows whether the tree itself matters.

    conda run -n tda python equity/studies/s06_risk_estimates.py
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tdaeq import clusters, data, evaluate, factors, plots, risk

STUDY = "s06_risk_estimates"
WINDOWS, HOLD = [120, 252], 20
MIN_VAR = ["Raw estimate", "Shrunk (Ledoit-Wolf)", "10 PCA factors", "H0 tree", "Average-linkage tree",
           "Market + TDA peer groups", "Market + sectors"]
LONG_ONLY = ["Equal weight", "Inverse volatility", "Risk parity, H0 tree", "Risk parity, average tree",
             "Risk parity, random order"]


def estimates(history, market, sectors):
    geo = factors.geometry(history, market)
    peers = clusters.hdbscan_labels(geo.distance, min_cluster_size=2, min_samples=1)
    return {"Raw estimate": risk.sample(history),
            "Shrunk (Ledoit-Wolf)": risk.shrunk(history),
            "10 PCA factors": risk.pca_factors(history, 10),
            "H0 tree": risk.tree_filtered(history, "single"),
            "Average-linkage tree": risk.tree_filtered(history, "average"),
            "Market + TDA peer groups": risk.market_plus_groups(history, market, peers),
            "Market + sectors": risk.market_plus_groups(history, market, clusters.factorize(sectors))}


def volatility_ratio_ci(a, b, block=40, repetitions=1000, seed=0):
    """Realized volatility of a divided by that of b, with a 95% block-bootstrap interval."""
    rows = evaluate.block_resamples(len(a), block, repetitions, seed)
    ratios = a[rows].std(axis=1, ddof=1) / b[rows].std(axis=1, ddof=1)
    return a.std(ddof=1) / b.std(ddof=1), *np.quantile(ratios, [0.025, 0.975])


def main():
    warnings.filterwarnings("ignore", category=FutureWarning)
    panel = data.load_panel()
    rng = np.random.default_rng(20261116)
    simple = np.expm1(panel.returns)
    names = [f"Min variance: {m}" for m in MIN_VAR] + [f"Long only: {m}" for m in LONG_ONLY]
    series = {(w, n): [] for w in WINDOWS for n in names}
    leverage = {(w, n): [] for w in WINDOWS for n in names}
    dates = []
    for t in range(data.MIN_HISTORY, len(panel.dates) - HOLD, HOLD):
        cols = panel.eligible(t)
        future = simple[t:t + HOLD, cols]
        dates += list(panel.dates[t:t + HOLD])
        for window in WINDOWS:
            history, market = panel.returns[t - window:t, cols], panel.market[t - window:t]
            covs = estimates(history, market, panel.sectors[cols])
            weights = {f"Min variance: {m}": risk.min_variance(covs[m]) for m in MIN_VAR}
            raw = covs["Raw estimate"]
            inverse_vol = 1 / np.sqrt(np.diag(raw))
            weights["Long only: Equal weight"] = np.full(len(cols), 1 / len(cols))
            weights["Long only: Inverse volatility"] = inverse_vol / inverse_vol.sum()
            weights["Long only: Risk parity, H0 tree"] = risk.risk_parity_tree(covs["Shrunk (Ledoit-Wolf)"], "single")
            weights["Long only: Risk parity, average tree"] = risk.risk_parity_tree(covs["Shrunk (Ledoit-Wolf)"], "average")
            weights["Long only: Risk parity, random order"] = risk.risk_parity_tree(
                covs["Shrunk (Ledoit-Wolf)"], order=rng.permutation(len(cols)))
            for name, w in weights.items():
                series[window, name].append(future @ w)
                leverage[window, name].append(np.abs(w).sum())
    dates = pd.DatetimeIndex(dates)
    later = dates >= data.SPLIT
    series = {key: np.concatenate(value) for key, value in series.items()}

    rows = []
    for (window, name), r in series.items():
        base = series[window, "Min variance: Shrunk (Ledoit-Wolf)" if name.startswith("Min") else "Long only: Inverse volatility"]
        for label, mask in (("before 2024", ~later), ("2024 on", later)):
            ratio, low, high = volatility_ratio_ci(r[mask], base[mask])
            rows.append({"window": window, "portfolio": name, "period": label,
                         "realized_vol_pct": r[mask].std(ddof=1) * np.sqrt(252) * 100,
                         "vs_benchmark": ratio, "low": low, "high": high,
                         "total_long_plus_short": np.mean(leverage[window, name])})
    table = pd.DataFrame(rows)
    out = plots.folder(STUDY)
    table.to_csv(out / "realized_volatility.csv", index=False)
    pd.set_option("display.width", 200)
    print(table.round(3).to_string(index=False))
    figure(table)


def figure(table):
    """One panel, 252-day window. (At 120 days the raw estimate's bar is so long it hides the rest.)"""
    part = table[table.portfolio.str.startswith("Min variance") & (table.window == 252)]
    order = [f"Min variance: {m}" for m in MIN_VAR][::-1]
    fig, ax = plt.subplots(figsize=(8, 4.4), layout="constrained")
    for offset, (period, color) in enumerate((("before 2024", plots.BLUE), ("2024 on", plots.ORANGE))):
        rows = part[part.period == period].set_index("portfolio").loc[order]
        y = np.arange(len(order)) + (0.17 if offset == 0 else -0.17)
        ax.barh(y, rows.realized_vol_pct, height=0.3, color=color, label=period)
        for yi, value in zip(y, rows.realized_vol_pct):
            ax.text(value + 0.2, yi, f"{value:.1f}", va="center", fontsize=8.5, color=plots.INK_SOFT)
    ax.set_yticks(np.arange(len(order)), [o.split(": ")[1] for o in order])
    ax.set_xlabel("Realized volatility, % per year (lower is better)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    ax.set_title("Which risk estimate gives the calmest minimum-variance portfolio?\nEstimated from the past 252 days, measured over the next 20")
    plots.save(fig, STUDY, "1_min_variance.png")


if __name__ == "__main__":
    main()
