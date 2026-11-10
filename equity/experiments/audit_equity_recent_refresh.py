"""Independent reconstruction of saved snapshot groups and short-block metrics."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import adjusted_rand_score

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/equity_recent_refresh_2026_11_10"


def main():
    specification = json.loads((OUT / "specification.json").read_text())
    data = ROOT / "market_data/datasets" / specification["dataset"]
    panel = pd.read_csv(data / "returns_log.csv", index_col="date")
    saved = pd.read_csv(OUT / "stock_groups.csv")
    balance = pd.read_csv(OUT / "group_balance.csv")
    changes = pd.read_csv(OUT / "partition_changes.csv")
    future_metrics = pd.read_csv(OUT / "short_extension_coherence.csv")
    names = sorted(saved.symbol.unique())
    assert len(names) == 200
    assert panel.loc[:specification["old_cutoff"], names].tail(272).notna().all().all()
    future = panel.loc[panel.index > specification["old_cutoff"]]
    reconstructed = {}
    for (cutoff, window, method), group in saved.groupby(["cutoff", "window", "method"]):
        history = panel.loc[:cutoff].tail(window)
        design = np.column_stack([np.ones(window), history.SPY])
        fit = np.linalg.pinv(design) @ history[names].to_numpy()
        residual = history[names].to_numpy() - design @ fit
        z = (residual-residual.mean(0))/residual.std(0, ddof=1)
        points = z.T/np.sqrt(window-1)
        if method == "centroid":
            # Independent greedy implementation; no scipy linkage/cut_tree calls.
            centers, members = list(points), [[i] for i in range(len(names))]
            for _ in range(len(names)-11):
                distance = cdist(np.array(centers), np.array(centers))
                np.fill_diagonal(distance, np.inf)
                a, b = np.unravel_index(distance.argmin(), distance.shape)
                a, b = sorted([a, b])
                joined = members[a]+members[b]
                new_center = points[joined].mean(axis=0)
                for index in [b, a]:
                    centers.pop(index); members.pop(index)
                centers.append(new_center); members.append(joined)
            labels = np.empty(len(names), dtype=int)
            for label, indices in enumerate(members):
                labels[indices] = label
        else:
            labels = AgglomerativeClustering(n_clusters=11, linkage=method).fit_predict(points)
        observed = group.set_index("symbol").loc[names, "group"].to_numpy()
        assert adjusted_rand_score(labels, observed) == 1
        sizes = np.bincount(labels)
        row = balance.query("cutoff == @cutoff and window == @window and method == @method").iloc[0]
        assert sizes.max() == row.largest_group and (sizes == 1).sum() == row.singleton_stocks
        reconstructed[cutoff, window, method] = labels
        if cutoff == specification["old_cutoff"]:
            common = panel.loc[:cutoff].tail(252)
            d = np.column_stack([np.ones(252), common.SPY])
            frozen = np.linalg.pinv(d) @ common[names].to_numpy()
            target = future[names].to_numpy() - np.column_stack([np.ones(len(future)), future.SPY]) @ frozen
            correlation = np.corrcoef(target.T)
            same = labels[:, None] == labels[None, :]
            triangle = np.triu(np.ones_like(same, dtype=bool), 1)
            gap = correlation[triangle & same].mean()-correlation[triangle & ~same].mean()
            stored = future_metrics.query("window == @window and method == @method").iloc[0]
            assert np.isclose(gap, stored.frozen_label_future_residual_correlation_gap)
    for row in changes.itertuples():
        ari = adjusted_rand_score(reconstructed[specification["old_cutoff"], row.window, row.method],
                                  reconstructed[specification["new_cutoff"], row.window, row.method])
        assert np.isclose(ari, row.old_to_new_partition_ARI)
    simple = pd.read_csv(data / "returns_simple.csv", index_col="date")
    compounded = (1+simple.loc[future.index, names]).prod()-1
    reported = pd.read_csv(OUT / "extension_stock_returns.csv", index_col="symbol").loc[names].iloc[:, 0]
    assert np.allclose(compounded, reported)
    checks = {"all_12_snapshot_partitions_independently_reconstructed": True,
        "centroid_groups_match_direct_greedy_center_merging": True,
        "single_average_groups_match_separate_clustering_implementation": True,
        "group_balance_and_all_partition_changes_reproduced": True,
        "all_six_short_future_correlation_gaps_reproduced": True,
        "stock_log_returns_match_independent_simple_compounding": True}
    report = {"checks": checks, "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT / "independent_audit.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
