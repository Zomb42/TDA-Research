"""Descriptive frozen-universe update; no strategy retuning or new profit claim."""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.spatial.distance import pdist, squareform
from scipy.sparse.csgraph import connected_components
from sklearn.metrics import adjusted_rand_score

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {
    "decision_date": "2026-11-10", "status": "descriptive extension; not an independent regime or forecasting test",
    "dataset": "equity_daily_expanded_2016_2026-11-09",
    "old_cutoff": "2026-10-27", "new_cutoff": "2026-11-09",
    "universe": "frozen original 200 stocks plus SPY; no holdings refresh",
    "eligibility": "272 consecutive observed returns through old cutoff; freeze those names for both snapshots; assert subsequent completeness, never fill",
    "histories": [120, 252], "groups": 11,
    "snapshots": "descriptive after-close fits, include cutoff close; no forward-return interpretation of in-sample coherence",
    "geometry": "separately fit intercept and SPY, standardize residual histories; stock vector z_i/sqrt(L-1); Euclidean distance sqrt(2*(1-rho))",
    "methods": ["single", "average", "centroid"],
    "centroid": "Euclidean mean of fixed stock vectors, size-weighted after merging; no centroid renormalization; cut by merge count because heights can invert",
    "comparisons": "snapshot correlation/PC shares, K11 group balance, old-to-new ARI; no winning window or method selection",
    "short_extension": "post-cutoff cumulative returns and future residual-correlation gap with old-cutoff labels and frozen old 252-session SPY coefficients; descriptive only, shorter than original 20-session target",
    "uncertainty": "no confidence interval or significance test on this short extension; dates share most training data",
    "economic_context": "verify dates from primary releases; no causal assignment of price moves to an event",
    "strategy": "none; prior gross trading ledgers remain on their original data and dates",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fit_geometry(history, market):
    design = np.c_[np.ones(len(market)), market]
    beta = np.linalg.lstsq(design, history, rcond=None)[0]
    residual = history - design @ beta
    z = (residual - residual.mean(axis=0)) / residual.std(axis=0, ddof=1)
    assert np.isfinite(z).all()
    points = z.T / np.sqrt(len(z)-1)
    corr = z.T @ z / (len(z)-1)
    distances = squareform(pdist(points))
    correlation_distances = np.sqrt(np.maximum(2*(1-corr), 0))
    np.fill_diagonal(correlation_distances, 0)
    assert np.allclose(distances, correlation_distances, atol=1e-10)
    return points, corr, distances, beta


def coherence(labels, corr):
    i, j = np.triu_indices(len(labels), 1)
    same = labels[i] == labels[j]
    return float(corr[i[same], j[same]].mean() - corr[i[~same], j[~same]].mean())


def merge_count_labels(tree, n, k):
    """Stop after n-k chronological merges, including nonmonotone centroids.

    scipy.cut_tree orders nodes by height, which can give the wrong count for
    a centroid tree with inversions. Preserve actual agglomeration order here.
    """
    nodes = {i: [i] for i in range(n)}
    for step, (left, right, _, _) in enumerate(tree[:n-k]):
        nodes[n+step] = nodes.pop(int(left)) + nodes.pop(int(right))
    labels = np.empty(n, dtype=int)
    for group, members in enumerate(nodes.values()):
        labels[members] = group
    assert len(nodes) == k
    return labels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    out = ROOT / "experiments/equity_recent_refresh_2026_11_10"
    out.mkdir(exist_ok=True)
    specification = out / "specification.json"
    if specification.exists():
        assert json.loads(specification.read_text()) == CONFIG
    specification.write_text(json.dumps(CONFIG, indent=2) + "\n")
    if args.prepare_only:
        print("Descriptive specification saved before outcome analysis")
        return
    data = ROOT / "market_data/datasets" / CONFIG["dataset"]
    universe = pd.read_csv(data / "universe.csv")
    panel = pd.read_csv(data / "returns_log.csv", index_col="date", parse_dates=True)
    symbols = universe.loc[universe.role.eq("equity"), "symbol"].tolist()
    old_history = panel.loc[:CONFIG["old_cutoff"]].tail(272)[symbols]
    names = old_history.columns[old_history.notna().all()].tolist()
    future = panel.loc[panel.index > CONFIG["old_cutoff"], names]
    assert len(old_history) == 272 and np.isfinite(future).all().all()
    assert panel.index[-1] == pd.Timestamp(CONFIG["new_cutoff"])
    assert panel.loc[:CONFIG["new_cutoff"]].tail(272)[names].notna().all().all()
    labels_by_cell, rows, corr_rows, assignments = {}, [], [], []
    for cutoff in [CONFIG["old_cutoff"], CONFIG["new_cutoff"]]:
        for window in CONFIG["histories"]:
            past = panel.loc[:cutoff].tail(window)
            points, corr, distances, beta = fit_geometry(past[names].to_numpy(), past.SPY.to_numpy())
            raw_corr = past[names].corr().to_numpy()
            i, j = np.triu_indices(len(names), 1)
            eig = np.linalg.eigvalsh(corr)
            raw_eig = np.linalg.eigvalsh(raw_corr)
            corr_rows.append({"cutoff": cutoff, "window": window, "stocks": len(names),
                "mean_raw_correlation": float(raw_corr[i, j].mean()),
                "mean_SPY_residual_correlation": float(corr[i, j].mean()),
                "raw_PC1_share": float(raw_eig[-1]/raw_eig.sum()),
                "residual_PC1_share": float(eig[-1]/eig.sum()),
                "residual_PC3_share": float(eig[-3:].sum()/eig.sum())})
            if cutoff == CONFIG["old_cutoff"] and window == 252:
                frozen_future = future.to_numpy() - np.c_[np.ones(len(future)), panel.loc[future.index, "SPY"]] @ beta
                future_corr = np.corrcoef(frozen_future, rowvar=False)
            for method in CONFIG["methods"]:
                tree = linkage(points, method=method, metric="euclidean")
                labels = merge_count_labels(tree, len(names), CONFIG["groups"])
                if method != "centroid":
                    assert adjusted_rand_score(labels, cut_tree(tree, n_clusters=[CONFIG["groups"]])[:, 0]) == 1
                labels_by_cell[cutoff, window, method] = labels
                assert len(set(labels)) == CONFIG["groups"]
                sizes = np.bincount(labels)
                if method == "single":
                    # Verify exact threshold connectivity away from merge ties.
                    k = CONFIG["groups"]
                    lower, upper = tree[len(names)-k-1, 2], tree[len(names)-k, 2]
                    assert lower < upper
                    count, connected = connected_components(distances <= (lower+upper)/2, directed=False)
                    assert count == k and adjusted_rand_score(labels, connected) == 1
                if method == "centroid":
                    # Audit every saved centroid merge height directly from original vectors.
                    centers = list(points.copy()); counts = [1] * len(points)
                    for a, b, height, size in tree:
                        a, b = int(a), int(b)
                        assert np.isclose(np.linalg.norm(centers[a]-centers[b]), height)
                        assert size == counts[a]+counts[b]
                        centers.append((counts[a]*centers[a]+counts[b]*centers[b])/size)
                        counts.append(size)
                rows.append({"cutoff": cutoff, "window": window, "method": method,
                    "stocks": len(names), "groups": len(sizes), "largest_group": int(sizes.max()),
                    "singleton_stocks": int((sizes == 1).sum()),
                    "in_sample_residual_correlation_gap": coherence(labels, corr),
                    "decreasing_merge_heights": int((np.diff(tree[:, 2]) < -1e-10).sum())})
                assignments.extend({"cutoff": cutoff, "window": window, "method": method,
                    "symbol": name, "group": int(label)} for name, label in zip(names, labels))
    changes, short = [], []
    for window in CONFIG["histories"]:
        for method in CONFIG["methods"]:
            old_labels = labels_by_cell[CONFIG["old_cutoff"], window, method]
            new_labels = labels_by_cell[CONFIG["new_cutoff"], window, method]
            changes.append({"window": window, "method": method,
                "old_to_new_partition_ARI": adjusted_rand_score(old_labels, new_labels)})
            short.append({"window": window, "method": method,
                "future_start": str(future.index[0].date()), "future_end": str(future.index[-1].date()),
                "sessions": len(future), "frozen_label_future_residual_correlation_gap": coherence(old_labels, future_corr)})
    returns = np.expm1(future.sum()).rename("extension_adjusted_return").to_frame()
    returns.to_csv(out / "extension_stock_returns.csv", index_label="symbol")
    frames = {"correlation_snapshots": pd.DataFrame(corr_rows), "group_balance": pd.DataFrame(rows),
        "partition_changes": pd.DataFrame(changes), "short_extension_coherence": pd.DataFrame(short),
        "stock_groups": pd.DataFrame(assignments)}
    for name, frame in frames.items():
        frame.to_csv(out / f"{name}.csv", index=False)
    spy_return = float(np.expm1(panel.loc[future.index, "SPY"].sum()))
    summary = {"configuration": CONFIG, "stocks": len(names), "added_sessions": len(future),
        "extension_start": str(future.index[0].date()), "extension_end": str(future.index[-1].date()),
        "SPY_extension_adjusted_return": spy_return,
        "median_stock_extension_adjusted_return": float(returns.iloc[:, 0].median()),
        "checks": {"past_only_cohort": True, "complete_unfilled_extension": True,
            "Euclidean_and_correlation_distances_match": True, "single_matches_Rips_H0_connectivity": True,
            "every_centroid_merge_reconstructed": True},
        "input_sha256": {name: sha(data/name) for name in ["returns_log.csv", "universe.csv", "manifest.json"]},
        "source_sha256": sha(Path(__file__))}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), layout="constrained")
    dates = [CONFIG["old_cutoff"], CONFIG["new_cutoff"]]
    colors = {"single": "#43aa8b", "average": "#e58a20", "centroid": "#277da1"}
    for method in CONFIG["methods"]:
        for w, style in [(120, "-"), (252, "--")]:
            selected = frames["group_balance"].query("method == @method and window == @w")
            axes[0].plot(dates, selected.largest_group/len(names)*100, style, marker="o", color=colors[method], label=f"{method}, {w}")
    axes[0].set(ylabel="Largest group (% of fixed cohort)", title="Eleven groups; descriptive snapshots", ylim=(0, 103))
    axes[0].legend(ncol=2, fontsize=8)
    cum = np.expm1(panel.loc[future.index, names+['SPY']].cumsum()) * 100
    axes[1].plot(cum.index, cum[names].median(axis=1), color="#277da1", label="Median stock cumulative return")
    axes[1].plot(cum.index, cum.SPY, color="#333333", label="SPY adjusted return")
    axes[1].axhline(0, color="grey", linewidth=.6)
    axes[1].set(ylabel="Adjusted close-to-close return (%)", title="Extension since October 27; no strategy P&L")
    axes[1].tick_params(axis="x", rotation=25); axes[1].legend(fontsize=8)
    fig.suptitle("Frozen equity universe update | overlapping histories; no event-causation claim")
    fig.savefig(out / "01_recent_refresh.png", dpi=160); plt.close(fig)
    print(json.dumps({k: v for k, v in summary.items() if k not in ['configuration', 'input_sha256']}, indent=2))


if __name__ == "__main__":
    main()
