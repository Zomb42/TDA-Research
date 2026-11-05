"""Independent reconstruction of expanded structural results and chronology."""
from pathlib import Path
import hashlib
import inspect
import json

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.spatial.distance import pdist
from scipy.sparse.csgraph import connected_components
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import adjusted_rand_score

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "market_data/datasets/equity_daily_expanded_2016_2026-10-27"
OUT = ROOT / "experiments/equity_expanded_structure"


def main():
    specification = json.loads((OUT / "specification.json").read_text())
    saved_summary = json.loads((OUT / "summary.json").read_text())
    anchors = pd.read_csv(OUT / "anchors.csv", parse_dates=["formation_date", "eligibility_start", "training_end", "future_start", "future_end"])
    rows = pd.read_csv(OUT / "scored_cut_measurements.csv")
    summary = pd.read_csv(OUT / "cut_summary.csv")
    paired = pd.read_csv(OUT / "paired_method_differences.csv")
    balance = pd.read_csv(OUT / "all_cut_balance.csv")
    branches = pd.read_csv(OUT / "all_internal_branches.csv.gz")
    overlap = pd.read_csv(OUT / "branch_overlap.csv")
    sector = pd.read_csv(OUT / "sector_reference.csv")
    counts = pd.read_csv(OUT / "stable_branch_counts.csv")
    random = np.load(OUT / "size_matched_random_curves.npz")["gaps"]
    universe = pd.read_csv(DATA / "universe.csv").query("role == 'equity'").set_index("symbol")
    symbols = universe.index.tolist()
    panel = pd.read_csv(DATA / "returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    x = panel[symbols].to_numpy()
    market = panel.SPY.to_numpy()
    assert (anchors.training_end < anchors.formation_date).all()
    assert (anchors.formation_date < anchors.future_start).all()
    assert ((anchors.future_start < pd.Timestamp("2024-01-01")) == (anchors.future_end < pd.Timestamp("2024-01-01"))).all()
    assert (anchors.future_end.iloc[:-1].to_numpy() < anchors.future_start.iloc[1:].to_numpy()).all()
    assert (anchors.original_30_count == 30).all()
    for a in anchors.itertuples():
        t = a.signal_index
        expected = np.array(symbols)[np.isfinite(x[t-272:t]).all(axis=0)].tolist()
        assert expected == a.symbols.split("|") and len(expected) == a.stocks
        assert panel.index[t+1] == a.future_start and panel.index[t+20] == a.future_end
        assert panel.index[t-1] == a.training_end and panel.index[t-272] == a.eligibility_start
    assert len(rows) == len(anchors) * 16
    assert random.shape == (len(anchors), 2, 2, 250, 4)
    # Every hierarchy has all balance cuts and exactly N-2 nonroot branches.
    for key, f in balance.groupby(["anchor", "window", "method"]):
        n = int(anchors.set_index("anchor").loc[key[0], "stocks"])
        f = f.sort_values("groups")
        assert list(f.groups) == list(range(1, n+1))
        assert f.iloc[0].largest_group == n and f.iloc[-1].largest_group == 1
        assert f.iloc[0].singleton_stocks == 0 and f.iloc[-1].singleton_stocks == n
        assert (np.diff(f.largest_group) <= 0).all() and (np.diff(f.singleton_stocks) >= 0).all()
        assert (np.diff(f.within_pairs) <= 0).all()
    by_tree = branches.groupby(["anchor", "window", "method"]).size()
    for key, count in by_tree.items():
        assert count == anchors.set_index("anchor").loc[key[0], "stocks"] - 2
    assert np.allclose(branches.exact_bootstrap_recovery * 40, np.round(branches.exact_bootstrap_recovery * 40))
    flags = branches["size"].between(3, 8) & branches.exact_bootstrap_recovery.ge(.75) & branches.window_recovery.ge(2/3 - 1e-12)
    assert np.array_equal(flags, branches.stable_local_candidate)
    branch_lookup = {(a, w, m): f for (a, w, m), f in branches.groupby(["anchor", "window", "method"])}
    for r in overlap.itertuples():
        h0 = branch_lookup[(r.anchor, r.window, "Single_H0")]
        avg = branch_lookup[(r.anchor, r.window, "Average")]
        selected = set(h0.loc[h0.stable_local_candidate, "stocks"])
        assert r.stable_H0_occurrences == len(selected)
        assert r.also_in_average == len(selected & set(avg.stocks))
        assert r.also_stable_in_average == len(selected & set(avg.loc[avg.stable_local_candidate, "stocks"]))
    for r in counts.itertuples():
        b = branch_lookup[(r.anchor, r.window, r.method)]
        assert r.local_branches == b["size"].between(3, 8).sum()
        assert r.stable_local_branches == b.stable_local_candidate.sum()
        union = set()
        for members in b.loc[b.stable_local_candidate, "stocks"]: union.update(members.split("|"))
        assert len(union) == r.stocks_in_stable_branch_union
    # Separate normalization implementation using Pearson distances directly.
    def geometry(t, length, columns):
        h = panel[columns].iloc[t-length:t].to_numpy()
        m = market[t-length:t]
        fit = np.linalg.lstsq(np.c_[np.ones(length), m], h, rcond=None)[0]
        residual = h - np.c_[np.ones(length), m] @ fit
        # scipy correlation distance is 1-rho, so convert to sqrt(2*(1-rho)).
        condensed = np.sqrt(np.maximum(2 * pdist(residual.T, metric="correlation"), 0))
        from scipy.spatial.distance import squareform
        return squareform(condensed), fit
    errors = []
    sampled = anchors.iloc[np.unique(np.linspace(0, len(anchors)-1, 11).astype(int))]
    parameters = inspect.signature(AgglomerativeClustering).parameters
    metric_parameter = "metric" if "metric" in parameters else "affinity"
    for a in sampled.itertuples():
        names = a.symbols.split("|"); n = len(names); t = a.signal_index
        _, fit = geometry(t, 252, names)
        future = panel[names].iloc[t+1:t+21].to_numpy() - np.c_[np.ones(20), market[t+1:t+21]] @ fit
        corr = np.corrcoef(future, rowvar=False)
        ii, jj = np.triu_indices(n, 1)
        reference = sector.loc[sector.anchor.eq(a.anchor)].iloc[0]
        labels = pd.factorize(universe.loc[names, "sector_snapshot"])[0]
        same = labels[ii] == labels[jj]
        assert np.isclose(corr[ii, jj][same].mean()-corr[ii, jj][~same].mean(), reference.future_gap)
        for window in [120, 252]:
            d, _ = geometry(t, window, names)
            single_tree = linkage(d[np.triu_indices(n, 1)], method="single")
            for method in ["Single_H0", "Average"]:
                base_tree = linkage(d[np.triu_indices(n, 1)], method="single" if method == "Single_H0" else "average")
                nodes = [frozenset([name]) for name in names]
                expected_branches = set()
                for left, right, _, size in base_tree:
                    combined = nodes[int(left)] | nodes[int(right)]; nodes.append(combined)
                    if size < n: expected_branches.add("|".join(sorted(combined)))
                assert expected_branches == set(branch_lookup[(a.anchor, window, method)].stocks)
                for k in [6, 11, 20, 40]:
                    if method == "Single_H0":
                        low, high = single_tree[n-k-1, 2], single_tree[n-k, 2]
                        assert low < high  # All sampled cuts are genuine distance thresholds.
                        count, labels = connected_components(d <= (low+high)/2, directed=False)
                        assert count == k
                    else:
                        labels = AgglomerativeClustering(n_clusters=k, linkage="average", **{metric_parameter: "precomputed"}).fit_predict(d)
                    same = labels[ii] == labels[jj]
                    measured = float(corr[ii, jj][same].mean()-corr[ii, jj][~same].mean())
                    saved = rows.loc[rows.anchor.eq(a.anchor) & rows.window.eq(window) & rows.method.eq(method) & rows.groups.eq(k)].iloc[0]
                    errors.append(abs(measured-saved.future_gap))
                    sizes = np.bincount(labels)
                    assert sizes.max() == saved.largest_group and (sizes==1).sum() == saved.singleton_stocks
                    assert same.sum() == saved.within_pairs
    assert max(errors) < 1e-9
    # Recreate all 250 matched random relabelings for the first anchor. Frozen
    # labels can be independently obtained with scikit-learn for both methods.
    a = anchors.iloc[0]; names = a.symbols.split("|"); n = len(names); t = int(a.signal_index)
    rng = np.random.default_rng(specification["seed"] + t)
    permutations = np.array([rng.permutation(n) for _ in range(250)])
    _, fit = geometry(t, 252, names)
    future = panel[names].iloc[t+1:t+21].to_numpy()-np.c_[np.ones(20), market[t+1:t+21]] @ fit
    ii, jj = np.triu_indices(n, 1); target = np.corrcoef(future, rowvar=False)[ii, jj]
    for wi, window in enumerate([120, 252]):
        d, _ = geometry(t, window, names)
        for mi, method in enumerate(["single", "average"]):
            for ki, k in enumerate([6, 11, 20, 40]):
                labels = AgglomerativeClustering(n_clusters=k, linkage=method, **{metric_parameter: "precomputed"}).fit_predict(d)
                mask = labels[permutations][:, ii] == labels[permutations][:, jj]
                pair_counts = mask.sum(axis=1)
                assert np.all(pair_counts == (labels[ii] == labels[jj]).sum())
                sums = mask @ target
                measured = sums/pair_counts - (target.sum()-sums)/(len(target)-pair_counts)
                assert np.allclose(measured, random[0, mi, wi, :, ki], atol=1e-9)
    # Reproduce actual history/window perturbations for the first anchor,
    # including exact branch membership; synthetic ARI checks alone are not enough.
    def tree_members(distance, method):
        tr = linkage(distance[np.triu_indices(len(distance), 1)], method=method)
        labels = cut_tree(tr, n_clusters=[6, 11, 20, 40]).T
        nodes = [frozenset([name]) for name in names]
        present = set()
        for left, right, _, size in tr:
            combined = nodes[int(left)] | nodes[int(right)]; nodes.append(combined)
            if size < len(names): present.add("|".join(sorted(combined)))
        return labels, present
    for window in [120, 252]:
        base_distance, _ = geometry(t, window, names)
        references = {method: tree_members(base_distance, method) for method in ["single", "average"]}
        totals = {method: {s: 0 for s in references[method][1]} for method in references}
        ari = {method: np.zeros(4) for method in references}
        starts = rng.integers(window, size=(40, int(np.ceil(window/5))))
        samples = ((starts[:, :, None] + np.arange(5)) % window).reshape(40, -1)[:, :window]
        history = panel[names].iloc[t-window:t].to_numpy()
        m = market[t-window:t]
        for sample in samples:
            design = np.c_[np.ones(window), m[sample]]
            residual = history[sample] - design @ np.linalg.lstsq(design, history[sample], rcond=None)[0]
            from scipy.spatial.distance import squareform
            distance = squareform(np.sqrt(np.maximum(2*pdist(residual.T, metric="correlation"), 0)))
            for method in references:
                lab, present = tree_members(distance, method)
                ari[method] += [adjusted_rand_score(a, b)/40 for a, b in zip(references[method][0], lab)]
                for members in totals[method]: totals[method][members] += members in present
        window_totals = {method: {s: 0 for s in references[method][1]} for method in references}
        for perturbation, (end, length) in zip(["shorter", "longer", "older"], [(t, window-20), (t, window+20), (t-5, window)]):
            distance, _ = geometry(end, length, names)
            for method in references:
                lab, present = tree_members(distance, method)
                name = "Single_H0" if method == "single" else "Average"
                saved = rows.loc[rows.anchor.eq(0) & rows.window.eq(window) & rows.method.eq(name)].set_index("groups").loc[[6, 11, 20, 40]]
                assert np.allclose([adjusted_rand_score(a, b) for a, b in zip(references[method][0], lab)], saved[f"ARI_{perturbation}"])
                for members in window_totals[method]: window_totals[method][members] += members in present
        for method in references:
            name = "Single_H0" if method == "single" else "Average"
            saved = rows.loc[rows.anchor.eq(0) & rows.window.eq(window) & rows.method.eq(name)].set_index("groups").loc[[6, 11, 20, 40]]
            assert np.allclose(ari[method], saved.ARI_bootstrap)
            for b in branch_lookup[(0, window, name)].itertuples():
                assert np.isclose(totals[method][b.stocks]/40, b.exact_bootstrap_recovery)
                assert np.isclose(window_totals[method][b.stocks]/3, b.window_recovery)
    # Summary means, paired means and random-array window/cut ordering.
    for r in summary.itertuples():
        f = rows.loc[rows.period.eq(r.period) & rows.method.eq(r.method) & rows.window.eq(r.window) & rows.groups.eq(r.groups)]
        assert np.isclose(f.future_gap.mean(), r.future_gap_mean)
        assert np.isclose(f.ARI_bootstrap.mean(), r.mean_bootstrap_ARI)
        ids = anchors.loc[anchors.period.eq(r.period), "anchor"].to_numpy()
        mi = ["Single_H0", "Average"].index(r.method); wi = [120, 252].index(r.window); ki = [6, 11, 20, 40].index(r.groups)
        assert np.isclose(random[ids, mi, wi, :, ki].mean(), r.random_mean)
    for r in paired.itertuples():
        f = summary.loc[summary.period.eq(r.period) & summary.window.eq(r.window) & summary.groups.eq(r.groups)].set_index("method")
        assert np.isclose(f.loc["Single_H0", "future_gap_mean"]-f.loc["Average", "future_gap_mean"], r.H0_minus_average_gap)
    # Reconstruct the uncertainty calculation from saved anchor-level outcomes,
    # including the shared paired resamples and eight-cell simultaneous family.
    cells = [(w, k) for w in [120, 252] for k in [6, 11, 20, 40]]
    for pi, period in enumerate(["development", "later"]):
        ids = anchors.loc[anchors.period.eq(period), "anchor"].to_numpy()
        n_dates = len(ids)
        brng = np.random.default_rng(501+pi)
        starts = brng.integers(n_dates, size=(1000, int(np.ceil(n_dates/6))))
        indices = ((starts[:, :, None]+np.arange(6)) % n_dates).reshape(1000, -1)[:, :n_dates]
        values = {}
        def independently_check_bands(array, expected, point_columns, simultaneous_columns):
            samples = np.stack([array[index].mean(axis=0) for index in indices])
            center = array.mean(axis=0)
            lower, upper = np.quantile(samples, [.025, .975], axis=0)
            se = np.std(samples, axis=0, ddof=1)
            studentized = (samples-center)/se
            radius = np.quantile(np.max(abs(studentized), axis=1), .95)
            assert np.allclose(expected[point_columns[0]], lower) and np.allclose(expected[point_columns[1]], upper)
            assert np.allclose(expected[simultaneous_columns[0]], center-radius*se)
            assert np.allclose(expected[simultaneous_columns[1]], center+radius*se)
        sector_vector = sector.set_index("anchor").loc[ids, "future_gap"].to_numpy()
        for method in ["Single_H0", "Average"]:
            f = rows.loc[rows.period.eq(period) & rows.method.eq(method)]
            values[method] = np.column_stack([f.loc[f.window.eq(w) & f.groups.eq(k)].set_index("anchor").loc[ids, "future_gap"] for w, k in cells])
            expected = summary.loc[summary.period.eq(period) & summary.method.eq(method)].set_index(["window", "groups"]).loc[cells]
            independently_check_bands(values[method], expected, ("point95_low", "point95_high"), ("sim95_low", "sim95_high"))
            independently_check_bands(values[method]-sector_vector[:, None], expected,
                                      ("sector_diff_point95_low", "sector_diff_point95_high"),
                                      ("sector_diff_sim95_low", "sector_diff_sim95_high"))
        expected = paired.loc[paired.period.eq(period)].set_index(["window", "groups"]).loc[cells]
        independently_check_bands(values["Single_H0"]-values["Average"], expected,
                                  ("point95_low", "point95_high"), ("sim95_low", "sim95_high"))
    for path, expected in saved_summary["protected_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected
    report = {"checks": {"all_anchor_memberships_use_only_prior_272_returns": True,
        "formation_and_target_chronology_and_nonoverlap": True, "original_30_present_at_every_anchor": True,
        "all_cut_balance_endpoints_and_monotonicity": True, "all_nonroot_branches_recorded": True,
        "branch_threshold_flags_counts_unions_and_overlap_reproduce": True,
        "eleven_sampled_anchors_reconstructed_with_independent_distance_and_clustering": True,
        "single_linkage_cuts_equal_threshold_connected_components": True,
        "common_future_target_and_sector_scores_reproduce": True,
        "first_anchor_all_250_size_matched_random_scores_reproduced": True,
        "first_anchor_all_history_and_window_perturbation_ARIs_and_branch_recoveries_reproduced": True,
        "summary_and_paired_means_and_null_cell_ordering_reproduce": True,
        "all_method_sector_and_paired_pointwise_and_simultaneous_bootstrap_intervals_reproduced": True,
        "protected_inputs_and_prior_experiments_unchanged": True},
        "sampled_anchor_ids": sampled.anchor.tolist(), "max_independent_gap_error": max(errors),
        "anchor_counts": anchors.groupby("period").size().to_dict(),
        "input_source_sha256": saved_summary["source_sha256"],
        "audit_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT / "independent_audit.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
