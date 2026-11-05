"""Broader-universe structural generalization, no P&L or fee calculations.

All formation choices are fixed before outcome calculation. Current-survivor
universe, current sector labels, and already examined dates remain exploratory.
"""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.spatial.distance import pdist, squareform
from sklearn.metrics import adjusted_rand_score

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "market_data/datasets/equity_daily_expanded_2016_2026-10-27"
OUT = ROOT / "experiments/equity_expanded_structure"
KS = [6, 11, 20, 40]
WINDOWS = [120, 252]
METHODS = ["Single_H0", "Average"]
PERIODS = ["development", "later"]
CONFIG = {
    "decision_date": "2026-10-28", "status": "exploratory cross-sectional generalization, no fresh time holdout",
    "input_dataset": DATA.name, "input_equities": 200, "benchmark": "SPY",
    "eligibility": "272 contiguous finite prior adjusted daily log returns ending t-1; no future eligibility filter or history filling",
    "common_membership": "same eligible stocks at each anchor for both windows, methods, all cuts and sector baseline",
    "windows": WINDOWS, "scored_group_counts": KS,
    "all_cuts": "balance only at K=1..N; no outcome-based cut selection",
    "geometry": "sample correlation distance sqrt(2*(1-rho)) of separately fitted prior-window SPY residuals",
    "regularization": "none: distance geometry needs no inverse covariance; longer window and perturbations measure sensitivity",
    "future_target": "20 future daily log returns after anchor, residualized with the common frozen 252-session SPY fit; same target for both windows and sector reference",
    "first_signal_index": 272, "anchor_stride": 20, "future_sessions": 20,
    "boundary": "2024-01-01; exclude future blocks crossing boundary",
    "history_perturbations": {"120": [100, 140], "252": [232, 272], "older_shift_sessions": 5},
    "bootstrap_history_repetitions": 40, "bootstrap_history_block_sessions": 5,
    "random_label_repetitions": 250, "random_labels": "common random relabelings within anchor, preserving every partition's exact group sizes",
    "stable_local_branches": {"min_size": 3, "max_size": 8, "bootstrap_exact_recovery_min": .75, "window_exact_recovery_min": 2/3},
    "branch_recovery": "same exact stock set anywhere in perturbed tree, not restricted to scored K",
    "uncertainty": "1000 circular bootstrap resamples of six consecutive anchors; approximate pointwise and simultaneous bands",
    "simultaneous_family": "eight scored (window,K) cells per method and period; paired H0-minus-average same eight cells; sector comparisons analogous; not all research choices",
    "sector_baseline": "October 27, 2026 provider snapshot; eleven groups when all sectors represented; no empirical membership-stability claim",
    "seed": 2026102821, "anchor_bootstrap_repetitions": 1000, "anchor_bootstrap_block": 6,
    "fees": "no performance or fee calculations", "strategy_changes": False,
    "outcome_selected_settings": False,
}
COLORS = {"Single_H0": "#43aa8b", "Average": "#e58a20", "Sector": "#6c757d"}
NAMES = {"Single_H0": "Single linkage / H0", "Average": "Average linkage", "Sector": "Snapshot sectors"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def geometry(history, market):
    design = np.column_stack([np.ones(len(market)), market])
    fit = np.linalg.lstsq(design, history, rcond=None)[0]
    residual = history - design @ fit
    sigma = residual.std(axis=0, ddof=1)
    if np.min(sigma) < 1e-10:
        raise ValueError("Near-constant residual history")
    z = (residual - residual.mean(axis=0)) / sigma
    corr = z.T @ z / (len(z)-1)
    distance = np.sqrt(np.maximum(2 * (1-corr), 0))
    np.fill_diagonal(distance, 0)
    assert np.allclose(distance, distance.T)
    return distance, fit, residual


def tree_data(distance, method, balance=False):
    tree = linkage(squareform(distance, checks=True), method=method)
    labels = cut_tree(tree, n_clusters=KS).T
    assert [len(set(row)) for row in labels] == KS
    n = len(distance)
    bits = [1 << i for i in range(n)]
    branches = []
    largest, singletons, within_pairs = 1, n, 0
    sizes = [1] * n
    sizes_by_k = [{"groups": n, "largest_group": 1, "singleton_stocks": n, "within_pairs": 0}]
    for step, (left, right, height, size) in enumerate(tree):
        a, b, size = int(left), int(right), int(size)
        group = bits[a] | bits[b]
        bits.append(group)
        if size < n:
            branches.append((group, size, float(height)))
        if balance:
            largest = max(largest, size)
            singletons -= int(sizes[a] == 1) + int(sizes[b] == 1)
            within_pairs += sizes[a] * sizes[b]
            sizes_by_k.append({"groups": n-step-1, "largest_group": largest,
                               "singleton_stocks": singletons, "within_pairs": within_pairs})
        sizes.append(size)
    return tree, labels, branches, sizes_by_k if balance else []


def pair_masks(labels, ii, jj):
    return labels[..., ii] == labels[..., jj]


def agreement(a, b):
    total = a.shape[-1]
    ca, cb = a.sum(axis=-1), b.sum(axis=-1)
    expected = ca * cb / total
    denominator = .5 * (ca + cb) - expected
    return np.divide(np.logical_and(a, b).sum(axis=-1) - expected, denominator,
                     out=np.ones(np.shape(denominator)), where=abs(denominator) > 1e-12)


def gap(masks, correlation):
    count = masks.sum(axis=-1)
    within = np.einsum("...p,p->...", masks, correlation, optimize=False)
    if np.any(count == 0) or np.any(count == len(correlation)):
        raise ValueError("Degenerate partition coherence")
    return within / count - (correlation.sum() - within) / (len(correlation)-count)


def circular(rng, length, block, repetitions):
    starts = rng.integers(length, size=(repetitions, int(np.ceil(length/block))))
    return ((starts[:, :, None] + np.arange(block)) % length).reshape(repetitions, -1)[:, :length]


def bands(values, indices):
    center = values.mean(axis=0)
    boot = values[indices].mean(axis=1)
    lo, hi = np.quantile(boot, [.025, .975], axis=0)
    se = boot.std(axis=0, ddof=1)
    standardized = np.divide(boot-center, se, out=np.zeros_like(boot), where=se > 1e-12)
    radius = np.quantile(abs(standardized).max(axis=1), .95)
    return center, lo, hi, center-radius*se, center+radius*se


def null_envelope(null):
    # Each replicate relabels stocks independently at each anchor; common
    # replicate indices across the eight cells retain within-anchor dependence.
    simulated_means = null.mean(axis=0)
    center = simulated_means.mean(axis=0)
    se = simulated_means.std(axis=0, ddof=1)
    standardized = np.divide(simulated_means-center, se, out=np.zeros_like(simulated_means), where=se > 1e-12)
    radius = np.quantile(abs(standardized).max(axis=1), .95)
    return center, center-radius*se, center+radius*se


def eligible_indices(x, t):
    return np.flatnonzero(np.isfinite(x[t-272:t]).all(axis=0))


def controls():
    rng = np.random.default_rng(141)
    labels = rng.integers(0, 6, size=(4, 60))
    other = rng.integers(0, 6, size=(4, 60))
    ii, jj = np.triu_indices(60, 1)
    assert np.allclose(agreement(pair_masks(labels, ii, jj), pair_masks(other, ii, jj)),
                       [adjusted_rand_score(a, b) for a, b in zip(labels, other)])
    history = rng.normal(size=(120, 60)); market = rng.normal(size=120)
    distance, _, _ = geometry(history, market)
    normalized = history - np.column_stack([np.ones(120), market]) @ np.linalg.lstsq(np.column_stack([np.ones(120), market]), history, rcond=None)[0]
    normalized = (normalized-normalized.mean(axis=0))/normalized.std(axis=0, ddof=1)
    assert np.allclose(distance, squareform(pdist(normalized.T/np.sqrt(119))))
    shrunk = np.sqrt(.7 * distance**2 + .6); np.fill_diagonal(shrunk, 0)
    _, before, _, _ = tree_data(distance, "single")
    _, after, _, _ = tree_data(shrunk, "single")
    assert np.allclose(agreement(pair_masks(before, ii, jj), pair_masks(after, ii, jj)), 1)
    x = rng.normal(size=(400, 60)); x[:200, 5] = np.nan
    eligible = eligible_indices(x, 300)
    assert 5 not in eligible
    x[300:] = np.nan
    assert np.array_equal(eligible, eligible_indices(x, 300))
    return {"ARI_matches_sklearn": True, "correlation_distance_equals_normalized_return_geometry": True,
            "identity_correlation_shrinkage_preserves_single_linkage_cuts": True,
            "eligibility_uses_past_only": True}


def summarize(anchors, rows, null, sector, branch_counts, overlap):
    cells = [(window, k) for window in WINDOWS for k in KS]
    records, paired, sectors = [], [], []
    for p_index, period in enumerate(PERIODS):
        ids = anchors.loc[anchors.period.eq(period), "anchor"].to_numpy()
        indices = circular(np.random.default_rng(501+p_index), len(ids), 6, 1000)
        values = {}
        sector_values = sector.set_index("anchor").loc[ids, "future_gap"].to_numpy()
        sc, sl, sh, _, _ = bands(sector_values[:, None], indices)
        sectors.append({"period": period, "anchors": len(ids), "future_gap_mean": sc[0], "point95_low": sl[0], "point95_high": sh[0]})
        for m_index, method in enumerate(METHODS):
            frame = rows.loc[rows.period.eq(period) & rows.method.eq(method)]
            array = np.column_stack([frame.loc[frame.window.eq(w) & frame.groups.eq(k)].set_index("anchor").loc[ids, "future_gap"] for w, k in cells])
            values[method] = array
            center, lo, hi, slo, shi = bands(array, indices)
            nmean, nlo, nhi = null_envelope(null[ids, m_index].transpose(0, 2, 1, 3).reshape(len(ids), 250, 8))
            # Same future correlation target and anchors for paired method-sector comparisons.
            dc, dl, dh, dsl, dsh = bands(array-sector_values[:, None], indices)
            for j, (w, k) in enumerate(cells):
                sub = frame.loc[frame.window.eq(w) & frame.groups.eq(k)]
                records.append({"period": period, "method": method, "window": w, "groups": k,
                    "anchors": len(ids), "mean_stocks": sub.stocks.mean(),
                    "mean_largest_group": sub.largest_group.mean(), "mean_largest_fraction": sub.largest_fraction.mean(),
                    "mean_singleton_stocks": sub.singleton_stocks.mean(), "mean_within_pairs": sub.within_pairs.mean(),
                    "mean_bootstrap_ARI": sub.ARI_bootstrap.mean(), "mean_shorter_ARI": sub.ARI_shorter.mean(),
                    "mean_longer_ARI": sub.ARI_longer.mean(), "mean_older_ARI": sub.ARI_older.mean(),
                    "future_gap_mean": center[j], "point95_low": lo[j], "point95_high": hi[j],
                    "sim95_low": slo[j], "sim95_high": shi[j],
                    "random_mean": nmean[j], "random_sim95_low": nlo[j], "random_sim95_high": nhi[j],
                    "method_minus_sector_gap": dc[j], "sector_diff_point95_low": dl[j], "sector_diff_point95_high": dh[j],
                    "sector_diff_sim95_low": dsl[j], "sector_diff_sim95_high": dsh[j]})
        center, lo, hi, slo, shi = bands(values["Single_H0"]-values["Average"], indices)
        for j, (w, k) in enumerate(cells):
            paired.append({"period": period, "window": w, "groups": k, "H0_minus_average_gap": center[j],
                           "point95_low": lo[j], "point95_high": hi[j], "sim95_low": slo[j], "sim95_high": shi[j]})
    return pd.DataFrame(records), pd.DataFrame(paired), pd.DataFrame(sectors)


def plots(summary, paired, sector, balance, anchors, counts):
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), layout="constrained")
    for col, period in enumerate(PERIODS):
        for method in METHODS:
            sub = summary.loc[summary.period.eq(period) & summary.method.eq(method)]
            for window, style in [(120, "-"), (252, "--")]:
                f = sub.loc[sub.window.eq(window)].sort_values("groups")
                label = f"{NAMES[method]}, {window} sessions"
                axes[0, col].plot(f.groups, f.mean_largest_fraction, style, marker="o", color=COLORS[method], label=label)
                axes[1, col].plot(f.groups, f.mean_singleton_stocks, style, marker="o", color=COLORS[method])
        axes[0, col].set_title(period.title()); axes[0, col].set_ylabel("Largest group / eligible stocks")
        axes[0, col].set_ylim(0, 1.02); axes[1, col].set_ylabel("Singleton stocks (mean)")
        for ax in axes[:, col]: ax.set_xticks(KS); ax.set_xlabel("Declared group count K")
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Expanded basket: does single-linkage chaining persist?\nSame past-eligible stocks for both lookbacks at each anchor")
    fig.savefig(OUT / "01_group_balance.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), layout="constrained")
    for row, window in enumerate(WINDOWS):
        for col, period in enumerate(PERIODS):
            ax = axes[row, col]
            for method in METHODS:
                f = summary.loc[summary.period.eq(period) & summary.window.eq(window) & summary.method.eq(method)].sort_values("groups")
                ax.plot(f.groups, f.mean_bootstrap_ARI, "o-", color=COLORS[method], label=NAMES[method])
            ax.set_title(f"{period.title()} | {window} sessions"); ax.set_xlabel("Group count K")
            ax.set_ylabel("Mean block-resampling adjusted Rand index"); ax.set_ylim(0, 1)
            ax.set_xticks(KS)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Sampling robustness | 40 five-session-block resamples of each history\nAgreement is a partition property, not a forecast or significance level")
    fig.savefig(OUT / "02_partition_stability.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), layout="constrained")
    for row, window in enumerate(WINDOWS):
        for col, period in enumerate(PERIODS):
            ax = axes[row, col]
            for j, method in enumerate(METHODS):
                f = summary.loc[summary.period.eq(period) & summary.window.eq(window) & summary.method.eq(method)].sort_values("groups")
                pos = np.arange(4) + (j-.5)*.12
                ax.errorbar(pos, f.future_gap_mean, yerr=[f.future_gap_mean-f.sim95_low, f.sim95_high-f.future_gap_mean],
                            fmt="o-", capsize=3, color=COLORS[method], label=NAMES[method])
                ax.fill_between(pos, f.random_sim95_low, f.random_sim95_high, color=COLORS[method], alpha=.1)
            s = sector.loc[sector.period.eq(period)].iloc[0]
            ax.errorbar([1.], [s.future_gap_mean], yerr=[[s.future_gap_mean-s.point95_low], [s.point95_high-s.future_gap_mean]],
                        fmt="s", capsize=5, color=COLORS["Sector"], label="Snapshot sectors, K=11")
            ax.axhline(0, color="black", lw=.7); ax.set_xticks(np.arange(4), KS)
            ax.set_xlabel("Declared group count K"); ax.set_ylabel("Future within-minus-between correlation")
            ax.set_title(f"{period.title()} | {window}-session geometry")
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Future peer coherence | identical next-20-session target for all methods\nMethod intervals simultaneous across eight (window,K) cells; sector interval pointwise; shading = size-matched random reference")
    fig.savefig(OUT / "03_future_coherence.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout="constrained")
    for ax, period in zip(axes, PERIODS):
        for j, window in enumerate(WINDOWS):
            f = paired.loc[paired.period.eq(period) & paired.window.eq(window)].sort_values("groups")
            ax.errorbar(np.arange(4)+(j-.5)*.12, f.H0_minus_average_gap,
                        yerr=[f.H0_minus_average_gap-f.sim95_low, f.sim95_high-f.H0_minus_average_gap],
                        fmt="o-", capsize=3, label=f"{window} sessions", color=["#277da1", "#9c6ba8"][j])
        ax.axhline(0, color="black", lw=.7); ax.set_title(period.title()); ax.set_xticks(np.arange(4), KS)
        ax.set_xlabel("Group count K"); ax.set_ylabel("H0 minus average future correlation gap")
    axes[0].legend(fontsize=8)
    fig.suptitle("Incremental H0 comparison: below zero favors average linkage\nPaired approximate 95% simultaneous intervals across the eight declared cells")
    fig.savefig(OUT / "04_paired_method_differences.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout="constrained")
    for ax, period in zip(axes, PERIODS):
        for j, window in enumerate(WINDOWS):
            for z, method in enumerate(METHODS):
                f = counts.loc[counts.period.eq(period) & counts.window.eq(window) & counts.method.eq(method)]
                ax.bar(j*3+z, f.stable_local_branches.mean(), color=COLORS[method], label=NAMES[method] if j==0 else None)
        ax.set_xticks([.5, 3.5], [120, 252]); ax.set_xlabel("Historical sessions")
        ax.set_ylabel("Mean stable local branches per anchor"); ax.set_title(period.title())
    axes[0].legend(fontsize=8)
    fig.suptitle("Local peer branches | sizes 3–8, >=75% exact bootstrap recovery and >=2/3 window recovery\nBranches may overlap or nest; counts are not independent discoveries")
    fig.savefig(OUT / "05_stable_local_branches.png", dpi=160); plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "specification.json"
    if path.exists() and json.loads(path.read_text()) != CONFIG:
        raise ValueError("Existing specification differs")
    path.write_text(json.dumps(CONFIG, indent=2) + "\n")
    checks = controls()
    protected_paths = [DATA / "returns_log.csv", DATA / "universe.csv", DATA / "manifest.json",
        ROOT / "experiments/equity_h0_scale_robustness.py", ROOT / "experiments/equity_h0_scale_robustness/summary.json",
        ROOT / "experiments/equity_reversal_response.py", ROOT / "experiments/equity_reversal_response/summary.json",
        ROOT / "experiments/equity_residual_backtest.py", ROOT / "experiments/equity_residual_backtest/evaluated/summary.json"]
    protected = {str(p.relative_to(ROOT)): sha(p) for p in protected_paths}
    universe = pd.read_csv(DATA / "universe.csv")
    symbols = universe.loc[universe.role.eq("equity"), "symbol"].tolist()
    metadata = universe.set_index("symbol").loc[symbols]
    panel = pd.read_csv(DATA / "returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    x, market = panel[symbols].to_numpy(), panel.SPY.to_numpy()
    assert np.isfinite(market).all()
    anchors, rows, sector_rows, branches_rows, balance_rows, count_rows, overlap_rows = [], [], [], [], [], [], []
    nulls = []
    for t in range(272, len(panel)-20, 20):
        first, last = panel.index[t+1], panel.index[t+20]
        if (first < pd.Timestamp("2024-01-01")) != (last < pd.Timestamp("2024-01-01")):
            continue
        eligible = eligible_indices(x, t)
        names = np.array(symbols)[eligible]
        n = len(names)
        if n < max(KS)+1: raise ValueError("Insufficient past-eligible stocks")
        ii, jj = np.triu_indices(n, 1)
        history = x[:, eligible]
        rng = np.random.default_rng(CONFIG["seed"] + t)
        permutations = np.array([rng.permutation(n) for _ in range(250)])
        period = "development" if first < pd.Timestamp("2024-01-01") else "later"
        anchor = len(anchors)
        anchors.append({"anchor": anchor, "signal_index": t, "period": period, "formation_date": panel.index[t],
                        "eligibility_start": panel.index[t-272], "training_end": panel.index[t-1],
                        "future_start": first, "future_end": last, "stocks": n,
                        "symbols": "|".join(names), "original_30_count": int(metadata.loc[names, "in_original_30"].sum())})
        _, common_fit, _ = geometry(history[t-252:t], market[t-252:t])
        future = history[t+1:t+21] - np.column_stack([np.ones(20), market[t+1:t+21]]) @ common_fit
        # No member was admitted based on future availability. A missing outcome
        # is an explicit failure requiring a declared missing-target policy.
        assert np.isfinite(future).all()
        target_corr = np.corrcoef(future, rowvar=False)
        corr_pairs = target_corr[ii, jj]
        sector = pd.factorize(metadata.loc[names, "sector_snapshot"], sort=False)[0]
        assert len(set(sector)) == 11
        sector_mask = pair_masks(sector, ii, jj)
        sector_null = gap(pair_masks(sector[permutations], ii, jj), corr_pairs)
        sector_rows.append({"anchor": anchor, "period": period, "stocks": n, "groups": 11,
                            "future_gap": float(gap(sector_mask, corr_pairs)), "random_mean": float(sector_null.mean()),
                            "largest_group": int(np.bincount(sector).max()), "within_pairs": int(sector_mask.sum())})
        anchor_null = np.zeros((2, 2, 250, 4))
        base_branch_records = {}
        for window_index, window in enumerate(WINDOWS):
            d, _, residual = geometry(history[t-window:t], market[t-window:t])
            rank = int(np.linalg.matrix_rank(residual))
            base = {}
            for method, scipy_name in [("Single_H0", "single"), ("Average", "average")]:
                tree, labels, branches, balance = tree_data(d, scipy_name, balance=True)
                masks = pair_masks(labels, ii, jj)
                base[method] = {"labels": labels, "masks": masks, "branches": branches, "scipy": scipy_name,
                    "boot_ari": np.zeros(4), "window_ari": [], "boot_count": {b[0]: 0 for b in branches},
                    "window_count": {b[0]: 0 for b in branches}, "rank": rank}
                balance_rows.extend({"anchor": anchor, "period": period, "window": window, "method": method,
                                     "stocks": n, **b} for b in balance)
            altered = [(t, window-20), (t, window+20), (t-5, window)]
            for end, length in altered:
                altered_d, _, _ = geometry(history[end-length:end], market[end-length:end])
                for method, b in base.items():
                    _, altered_labels, altered_branches, _ = tree_data(altered_d, b["scipy"])
                    b["window_ari"].append(agreement(b["masks"], pair_masks(altered_labels, ii, jj)))
                    present = {v[0] for v in altered_branches}
                    for membership in b["window_count"]: b["window_count"][membership] += membership in present
            indices = circular(rng, window, 5, 40)
            for selection in indices:
                boot_d, _, _ = geometry(history[t-window:t][selection], market[t-window:t][selection])
                for method, b in base.items():
                    _, other_labels, other_branches, _ = tree_data(boot_d, b["scipy"])
                    b["boot_ari"] += agreement(b["masks"], pair_masks(other_labels, ii, jj)) / 40
                    present = {v[0] for v in other_branches}
                    for membership in b["boot_count"]: b["boot_count"][membership] += membership in present
            for method_index, method in enumerate(METHODS):
                b = base[method]
                random = gap(pair_masks(b["labels"][:, permutations].transpose(1, 0, 2), ii, jj), corr_pairs)
                anchor_null[method_index, window_index] = random
                scores = gap(b["masks"], corr_pairs)
                window_ari = np.stack(b["window_ari"])
                for j, k in enumerate(KS):
                    sizes = np.bincount(b["labels"][j])
                    rows.append({"anchor": anchor, "period": period, "window": window, "method": method,
                        "groups": k, "stocks": n, "residual_history_rank": rank,
                        "largest_group": int(sizes.max()), "largest_fraction": float(sizes.max()/n),
                        "singleton_stocks": int((sizes==1).sum()), "within_pairs": int(b["masks"][j].sum()),
                        "ARI_bootstrap": float(b["boot_ari"][j]), "ARI_shorter": float(window_ari[0, j]),
                        "ARI_longer": float(window_ari[1, j]), "ARI_older": float(window_ari[2, j]),
                        "future_gap": float(scores[j]), "random_mean": float(random[:, j].mean()),
                        "random_q025": float(np.quantile(random[:, j], .025)), "random_q975": float(np.quantile(random[:, j], .975))})
                local, stable, coverage_bits, branch_info = 0, 0, 0, {}
                for membership, size, height in b["branches"]:
                    boot = b["boot_count"][membership] / 40
                    win = b["window_count"][membership] / 3
                    is_local = 3 <= size <= 8
                    is_stable = is_local and boot >= .75 and win >= 2/3
                    local += is_local; stable += is_stable
                    if is_stable: coverage_bits |= membership
                    branch_info[membership] = is_stable
                    member_idx = [j for j in range(n) if (membership >> j) & 1]
                    local_gap = None
                    if is_local:
                        inside = np.array([(membership >> j) & 1 for j in range(n)], dtype=bool)
                        within = inside[ii] & inside[jj]
                        cross = inside[ii] != inside[jj]
                        local_gap = float(corr_pairs[within].mean()-corr_pairs[cross].mean())
                    branches_rows.append({"anchor": anchor, "period": period, "window": window, "method": method,
                        "stocks": "|".join(names[member_idx]), "size": size, "merge_distance": height,
                        "exact_bootstrap_recovery": boot, "window_recovery": win,
                        "local_size_3_to_8": is_local, "stable_local_candidate": is_stable,
                        "future_local_gap": local_gap})
                base_branch_records[(window, method)] = branch_info
                count_rows.append({"anchor": anchor, "period": period, "window": window, "method": method,
                    "stocks": n, "local_branches": local, "stable_local_branches": stable,
                    "stocks_in_stable_branch_union": coverage_bits.bit_count()})
            h0 = base_branch_records[(window, "Single_H0")]
            average = base_branch_records[(window, "Average")]
            selected = {b for b, is_stable in h0.items() if is_stable}
            overlap_rows.append({"anchor": anchor, "period": period, "window": window,
                "stable_H0_occurrences": len(selected), "also_in_average": sum(b in average for b in selected),
                "also_stable_in_average": sum(average.get(b, False) for b in selected)})
        nulls.append(anchor_null)
        if (anchor+1) % 5 == 0: print(f"Completed {anchor+1} anchors; eligible stocks={n}", flush=True)
    anchors = pd.DataFrame(anchors); rows = pd.DataFrame(rows); sector = pd.DataFrame(sector_rows)
    branches = pd.DataFrame(branches_rows); balance = pd.DataFrame(balance_rows)
    counts = pd.DataFrame(count_rows); overlap = pd.DataFrame(overlap_rows); null = np.stack(nulls)
    summary, paired, sector_summary = summarize(anchors, rows, null, sector, counts, overlap)
    tables = {"anchors": anchors, "scored_cut_measurements": rows, "sector_reference": sector,
        "all_cut_balance": balance, "stable_branch_counts": counts, "branch_overlap": overlap,
        "cut_summary": summary, "paired_method_differences": paired, "sector_summary": sector_summary}
    for name, frame in tables.items(): frame.to_csv(OUT / f"{name}.csv", index=False)
    branches.to_csv(OUT / "all_internal_branches.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    catalogue = branches.loc[branches.local_size_3_to_8].groupby(["period", "window", "method", "stocks", "size"]).agg(
        observed_anchors=("anchor", "size"), stable_candidate_anchors=("stable_local_candidate", "sum"),
        mean_bootstrap_recovery=("exact_bootstrap_recovery", "mean"), mean_window_recovery=("window_recovery", "mean"),
        mean_future_local_gap=("future_local_gap", "mean")).reset_index()
    catalogue.to_csv(OUT / "named_local_branch_catalogue.csv", index=False)
    np.savez_compressed(OUT / "size_matched_random_curves.npz", gaps=null)
    plots(summary, paired, sector_summary, balance, anchors, counts)
    checks.update(common_past_eligible_membership_across_windows=True,
        no_future_missingness_member_selection=True, common_frozen_future_target=True,
        sector_count_eleven_every_anchor=True, all_scored_cuts_have_requested_group_count=True,
        all_source_inputs_and_prior_experiments_unchanged=all(sha(p)==protected[str(p.relative_to(ROOT))] for p in protected_paths))
    assert all(checks.values())
    result = {"configuration": CONFIG, "checks": checks, "anchors_by_period": anchors.groupby("period").size().to_dict(),
        "eligible_stock_range": [int(anchors.stocks.min()), int(anchors.stocks.max())],
        "future_blocks": len(anchors), "branch_overlap_totals": json.loads(overlap.groupby(["period", "window"])[["stable_H0_occurrences", "also_in_average", "also_stable_in_average"]].sum().reset_index().to_json(orient="records")),
        "stable_branch_means": json.loads(counts.groupby(["period", "window", "method"])[["local_branches", "stable_local_branches", "stocks_in_stable_branch_union"]].mean().reset_index().to_json(orient="records")),
        "source_sha256": sha(Path(__file__)), "protected_sha256": protected}
    (OUT / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print("ANCHORS", result["anchors_by_period"], "ELIGIBLE", result["eligible_stock_range"])
    print(summary.loc[summary.groups.eq(11), ["period", "window", "method", "mean_largest_group", "mean_singleton_stocks", "mean_bootstrap_ARI", "future_gap_mean", "sim95_low", "sim95_high"]].round(4).to_string(index=False))
    print("PAIRED\n", paired.round(4).to_string(index=False))
    print("BRANCH OVERLAP\n", pd.DataFrame(result["branch_overlap_totals"]).to_string(index=False))


if __name__ == "__main__":
    main()
