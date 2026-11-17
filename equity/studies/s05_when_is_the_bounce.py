"""C1. When is the bounce stronger?

Takes the one signal that held up in s03 (a stock's 1-day surprise relative
to its TDA peer group) and splits the days and stocks three ways:

  by tightness   how close the stock sits to its nearest peer (H0 join distance),
                 and, as the plain competitor, its average correlation with its 5 closest stocks
  by VIX         yesterday's VIX level (low / middle / high third, cut-offs from before 2024)
  by size of move  how big today's relative move was

For each bucket: the next close-to-close return of buying the most-down fifth
and shorting the most-up fifth of that bucket, in basis points per day, before costs.

    conda run -n tda python equity/studies/s05_when_is_the_bounce.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tdaeq import data, evaluate, plots, signals

STUDY = "s05_when_is_the_bounce"
THIRDS = ["Low", "Middle", "High"]


def spread(signal, outcome):
    """Buy the lowest fifth of the signal, short the highest fifth; NaN if too few stocks."""
    ok = np.isfinite(signal) & np.isfinite(outcome)
    if ok.sum() < 25:
        return np.nan
    x, y = signal[ok], outcome[ok]
    low, high = np.quantile(x, [0.2, 0.8])
    return y[x <= low].mean() - y[x >= high].mean()


def thirds_within_day(values):
    """Label each stock 0/1/2 by which third of today's values it falls in (NaN stays -1)."""
    out = np.full(values.shape, -1)
    ok = np.isfinite(values)
    if ok.sum() >= 30:
        cuts = np.quantile(values[ok], [1 / 3, 2 / 3])
        out[ok] = np.searchsorted(cuts, values[ok])
    return out


def main():
    panel = data.load_panel()
    state = signals.build_state(panel)
    days, n = panel.returns.shape
    vs_peers = np.vstack([signals.minus_group_mean(state.surprise[t], state.group[t]) for t in range(days)])
    next_cc = np.vstack([panel.close_adj[1:] / panel.close_adj[:-1] - 1, np.full((1, n), np.nan)])
    spy_next = np.r_[panel.market_close[1:] / panel.market_close[:-1] - 1, np.nan]
    outcome = next_cc - state.beta * spy_next[:, None]

    later = panel.dates >= data.SPLIT
    vix_yesterday = np.r_[np.nan, panel.vix[:-1]]
    vix_cuts = np.nanquantile(vix_yesterday[~later], [1 / 3, 2 / 3])
    vix_bucket = np.where(np.isfinite(vix_yesterday), np.searchsorted(vix_cuts, vix_yesterday), -1)

    daily = {}                                   # (split, bucket) -> daily spread series
    for t in range(days - 1):
        if not np.isfinite(vs_peers[t]).any():
            continue
        splits = {"Tightness (H0 join distance)": 2 - thirds_within_day(np.where(np.isfinite(vs_peers[t]), state.join[t], np.nan)),
                  "Tightness (correlation with 5 closest)": thirds_within_day(np.where(np.isfinite(vs_peers[t]), state.corr_top5[t], np.nan)),
                  "Size of today's relative move": thirds_within_day(np.abs(vs_peers[t]))}
        for name, bucket in splits.items():
            for b in range(3):
                pick = bucket == b
                # for the join distance, "2 - third" makes High = tightest; ungrouped stocks give 3 and are skipped
                daily.setdefault((name, THIRDS[b]), np.full(days, np.nan))[t] = spread(
                    np.where(pick, vs_peers[t], np.nan), outcome[t])
        if vix_bucket[t] >= 0:
            daily.setdefault(("Yesterday's VIX", THIRDS[vix_bucket[t]]), np.full(days, np.nan))[t] = spread(
                vs_peers[t], outcome[t])
        daily.setdefault(("All", "All"), np.full(days, np.nan))[t] = spread(vs_peers[t], outcome[t])

    rows = []
    for (name, bucket), series in daily.items():
        for label, mask in (("before 2024", ~later), ("2024 on", later)):
            use = mask & np.isfinite(series)
            mean, low, high = evaluate.mean_ci(series[use], block=10)
            rows.append({"split": name, "bucket": bucket, "period": label, "days": int(use.sum()),
                         "spread_bps": mean * 1e4, "low": low * 1e4, "high": high * 1e4,
                         "sharpe": evaluate.sharpe(series[use])})
    table = pd.DataFrame(rows)
    out = plots.folder(STUDY)
    table.to_csv(out / "buckets.csv", index=False)
    print(f"VIX cut-offs (before 2024): {vix_cuts.round(1)}")
    print(table.round(2).to_string(index=False))
    figure(table)


def figure(table):
    names = [s for s in dict.fromkeys(table.split) if s != "All"]
    fig, axes = plt.subplots(1, len(names), figsize=(4 * len(names), 3.9), sharey=True, layout="constrained")
    for ax, name in zip(axes, names):
        for offset, (period, color) in enumerate((("before 2024", plots.BLUE), ("2024 on", plots.ORANGE))):
            part = table[(table.split == name) & (table.period == period)].set_index("bucket").loc[THIRDS]
            x = np.arange(3) + (-0.12 if offset == 0 else 0.12)
            ax.errorbar(x, part.spread_bps, yerr=[part.spread_bps - part.low, part.high - part.spread_bps],
                        fmt="o", color=color, elinewidth=2, capsize=0, label=period)
        ax.axhline(0, color=plots.INK_SOFT, lw=1)
        ax.set_xticks(np.arange(3), THIRDS)
        ax.set_xlim(-0.5, 2.5)
        ax.set_title(name)
    axes[0].set_ylabel("Bounce, bps per day before costs")
    axes[0].legend(loc="upper left")
    fig.suptitle("Where is the bounce stronger? Low / middle / high third of each condition, 95% intervals",
                 x=0.01, ha="left", fontweight="bold")
    plots.save(fig, STUDY, "1_buckets.png")


if __name__ == "__main__":
    main()
