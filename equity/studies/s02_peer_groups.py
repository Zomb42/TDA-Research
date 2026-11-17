"""A3. Does reading the H0 tree by its long-lived branches fix the chaining problem?

The old experiments cut the H0 (single-linkage) tree at one height to get 11
groups, and almost every stock fell into one giant group. HDBSCAN uses the
same tree but keeps the branches that survive longest, and leaves stocks with
no close peer ungrouped.

Groups are formed from the past 252 days and scored on the NEXT 20 days:

  peer correlation   for each stock, the correlation between its own move and
                     the average move of the other stocks in its group
                     (both after removing SPY). Higher = better peers.

Settings for HDBSCAN are chosen on dates before 2024 only.

    conda run -n tda python equity/studies/s02_peer_groups.py
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tdaeq import clusters, data, evaluate, factors, plots

STUDY = "s02_peer_groups"
WINDOW, HORIZON = 252, 20
TREE_CUTS = [6, 11, 20, 40, 60, 80, 100, 120]
HDBSCAN_GRID = [(size, samples) for size in (2, 3, 5) for samples in (1, 3, 5)]
# Plain competitors, each scored on exactly the stocks a method managed to group.
RIVALS = ["Sectors", "Average linkage K=11", "Average linkage K=40", "Average linkage K=80",
          "Average linkage K=100", "Nearest 3 stocks"]


def peer_correlation(labels, future):
    """For each stock: correlation of its future move with its group's average (itself left out).
    NaN for a stock that is alone or ungrouped."""
    out = np.full(len(labels), np.nan)
    for g in np.unique(labels[labels >= 0]):
        members = np.flatnonzero(labels == g)
        if len(members) < 2:
            continue
        total = future[:, members].sum(axis=1)
        for i in members:
            peers = (total - future[:, i]) / (len(members) - 1)
            out[i] = np.corrcoef(future[:, i], peers)[0, 1]
    return out


def nearest_peer_correlation(distance, future, k=3):
    """No grouping at all: each stock's peers are simply its k closest stocks in the past."""
    order = np.argsort(distance + np.eye(len(distance)) * 9, axis=1)[:, :k]
    return np.array([np.corrcoef(future[:, i], future[:, order[i]].mean(axis=1))[0, 1]
                     for i in range(len(distance))])


def all_groupings(distance, sectors):
    found = {"Sectors": clusters.factorize(sectors)}
    for method, name in (("single", "H0 cut"), ("average", "Average linkage")):
        tree = clusters.tree(distance, method)
        for k in TREE_CUTS:
            found[f"{name} K={k}"] = clusters.cut_tree(tree, n_clusters=[k])[:, 0]
    for size, samples in HDBSCAN_GRID:
        found[f"HDBSCAN size={size} samples={samples}"] = clusters.hdbscan_labels(distance, size, samples)
    return found


def main():
    warnings.filterwarnings("ignore", category=FutureWarning)
    panel = data.load_panel()
    rows, examples = [], {}
    for t in range(data.MIN_HISTORY, len(panel.dates) - HORIZON, HORIZON):
        if panel.is_later(t + 1) != panel.is_later(t + HORIZON):
            continue
        cols = panel.eligible(t)
        past = factors.geometry(panel.returns[t - WINDOW:t, cols], panel.market[t - WINDOW:t])
        future = (panel.returns[t + 1:t + 1 + HORIZON, cols] - past.alpha
                  - np.outer(panel.market[t + 1:t + 1 + HORIZON], past.beta))
        future_corr = np.corrcoef(future, rowvar=False)
        groupings = all_groupings(past.distance, panel.sectors[cols])
        scores = {name: peer_correlation(labels, future) for name, labels in groupings.items()}
        scores["Nearest 3 stocks"] = nearest_peer_correlation(past.distance, future)
        for name, labels in groupings.items():
            covered = np.isfinite(scores[name])
            rows.append({"block": t, "later": panel.is_later(t + 1), "method": name,
                         "stocks": len(cols), **clusters.describe(labels),
                         "covered": covered.mean(),
                         "peer_corr": np.nanmean(scores[name]),
                         "gap": clusters.correlation_gap(labels, future_corr),
                         # the same stocks, scored with each plain competitor's peers
                         **{f"same stocks: {rival}": np.nanmean(scores[rival][covered]) for rival in RIVALS},
                         "left out: Sectors": np.nanmean(scores["Sectors"][~covered]) if (~covered).any() else np.nan,
                         "left out: Nearest 3 stocks": np.nanmean(scores["Nearest 3 stocks"][~covered]) if (~covered).any() else np.nan})
        rows.append({"block": t, "later": panel.is_later(t + 1), "method": "Nearest 3 stocks",
                     "stocks": len(cols), "covered": 1.0, "peer_corr": scores["Nearest 3 stocks"].mean()})
        examples[t] = (np.array(panel.symbols)[cols], groupings)
    table = pd.DataFrame(rows)

    out = plots.folder(STUDY)
    table.to_csv(out / "by_block.csv", index=False)
    summary = table.drop(columns=["block", "stocks", "ungrouped", "in_pairs_or_more"]).groupby(
        ["later", "method"]).mean().reset_index()
    summary.to_csv(out / "summary.csv", index=False)

    # Choose the HDBSCAN setting on the early period only: best peer correlation
    # among settings that still place at least half the stocks in a group.
    early = summary[(~summary.later) & summary.method.str.startswith("HDBSCAN") & (summary.covered >= 0.5)]
    chosen = early.sort_values("peer_corr").method.iloc[-1]
    print("HDBSCAN setting chosen on pre-2024 dates:", chosen)
    pd.set_option("display.width", 250)
    print(summary.round(3).to_string(index=False))

    # Paired difference with its interval: chosen HDBSCAN groups versus each rival, same stocks.
    paired = []
    for later in (False, True):
        part = table[(table.later == later) & (table.method == chosen)]
        for rival in RIVALS:
            mean, low, high = evaluate.mean_ci(part.peer_corr - part[f"same stocks: {rival}"], block=6)
            paired.append({"period": "2024 on" if later else "before 2024", "rival": rival,
                           "hdbscan": part.peer_corr.mean(), "rival_same_stocks": part[f"same stocks: {rival}"].mean(),
                           "difference": mean, "low": low, "high": high})
    paired = pd.DataFrame(paired)
    paired.to_csv(out / "paired_vs_rivals.csv", index=False)
    print(paired.round(3).to_string(index=False))

    last = max(examples)
    names, groupings = examples[last]
    labels = groupings[chosen]
    lines = [" ".join(names[labels == g]) for g in np.unique(labels[labels >= 0])]
    (out / "latest_groups.txt").write_text(
        f"{chosen}, formed from the 252 days ending {panel.dates[last - 1].date()}\n\n"
        + "\n".join(sorted(lines, key=lambda s: -len(s.split())))
        + "\n\nNo close peer: " + " ".join(names[labels < 0]) + "\n")

    figure(summary, chosen, out)


def figure(summary, chosen, out):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True, layout="constrained")
    for ax, later in zip(axes, (False, True)):
        part = summary[summary.later == later].set_index("method")
        for name, color in (("H0 cut", plots.GRAY), ("Average linkage", plots.ORANGE)):
            rows = part.loc[[f"{name} K={k}" for k in TREE_CUTS]]
            ax.plot(rows.covered * 100, rows.peer_corr, "o-", color=color, label=f"{name}, K = 6 to 120")
        ax.plot(part.loc["Sectors", "covered"] * 100, part.loc["Sectors", "peer_corr"], "s",
                color=plots.AQUA, ms=8, label="Sectors")
        ax.plot(100, part.loc["Nearest 3 stocks", "peer_corr"], "^", color=plots.YELLOW, ms=8,
                label="Nearest 3 stocks (no groups)")
        rows = part[part.index.str.startswith("HDBSCAN")]
        ax.plot(rows.covered * 100, rows.peer_corr, "D", color=plots.BLUE, ms=6,
                label="HDBSCAN (long-lived H0 branches)")
        best = part.loc[chosen]
        ax.annotate("chosen", (best.covered * 100, best.peer_corr), textcoords="offset points",
                    xytext=(8, 6), fontsize=8.5, color=plots.INK_SOFT)
        ax.set(xlabel="Stocks placed in a group of two or more, %",
               title=("2017–2023 (used to choose settings)" if not later else "2024 – Nov 2026 (check)"))
    axes[0].set_ylabel("Peer correlation over the next 20 days")
    axes[0].legend(loc="lower left")
    fig.suptitle("How well do a stock's peers track it afterwards? Up and to the right is better",
                 x=0.01, ha="left", fontweight="bold")
    plots.save(fig, STUDY, "1_peer_quality.png")


if __name__ == "__main__":
    main()
