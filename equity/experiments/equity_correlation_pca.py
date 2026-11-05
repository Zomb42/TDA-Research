"""Descriptive daily equity correlations/PCA. Uses local files; no network calls.

Run with the tda Python environment. Analysis ends in 2023; 2024+ is held out.
"""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import squareform

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "market_data/datasets/equity_daily_30_2016_2026-10-27"
OUT = ROOT / "experiments/equity_correlation_pca"
DEV_END = "2023-12-31"
COLORS = ["#277da1", "#f8961e", "#43aa8b", "#d1495b", "#7b61a8", "#6c757d"]


def load_development_data():
    universe = pd.read_csv(DATA / "universe.csv")
    universe = universe.loc[universe.role.eq("equity")].reset_index(drop=True)
    panel = pd.read_csv(DATA / "returns_log.csv", index_col="date", parse_dates=True)
    # Discard held-out rows before computing any descriptive statistic or fit.
    panel = panel.loc[:DEV_END].iloc[1:]
    returns = panel[universe.symbol.tolist()]
    spy = panel.SPY
    assert returns.shape[1] == 30 and returns.notna().all().all()
    assert returns.index.max() < pd.Timestamp("2024-01-01")
    return returns, spy, universe


def correlation_pca(values):
    z = (values - values.mean(axis=0)) / values.std(axis=0, ddof=1)
    corr = z.T @ z / (len(z) - 1)
    eigenvalues, eigenvectors = np.linalg.eigh(corr)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues, eigenvectors = eigenvalues[order], eigenvectors[:, order]
    assert eigenvalues.min() > -1e-9
    assert np.allclose(np.diag(corr), 1)
    assert np.allclose(eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T, corr)
    assert np.isclose(eigenvalues.sum(), values.shape[1])
    for j in range(values.shape[1]):
        # PC1 points toward broad positive equity exposure. Other signs are
        # reproducible conventions only, not economic positive/negative labels.
        anchor = eigenvectors[:, j].sum() if j == 0 else eigenvectors[np.argmax(abs(eigenvectors[:, j])), j]
        if anchor < 0:
            eigenvectors[:, j] *= -1
    scores = z @ eigenvectors
    loadings = eigenvectors * np.sqrt(np.maximum(eigenvalues, 0))
    return corr, eigenvalues, eigenvectors, scores, loadings


def remove_market(values, market):
    design = np.column_stack([np.ones(len(market)), market])
    coefficients = np.linalg.lstsq(design, values, rcond=None)[0]
    residuals = values - design @ coefficients
    assert np.allclose(design.T @ residuals, 0, atol=1e-9)
    return residuals


def save_figure(fig, out, name):
    fig.savefig(out / f"{name}.png", dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def run_analysis(out=OUT):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.titleweight": "bold"})
    returns, spy, universe = load_development_data()
    symbols = universe.symbol.tolist()
    groups = universe.research_group.tolist()
    group_names = list(dict.fromkeys(groups))
    palette = dict(zip(group_names, COLORS))
    n = len(symbols)
    upper = np.triu(np.ones((n, n), dtype=bool), k=1)
    same_group = np.equal.outer(groups, groups) & upper
    other_group = ~np.equal.outer(groups, groups) & upper
    matrix = returns.to_numpy()
    market = spy.to_numpy()
    rolling = []
    for window in (60, 120):
        for end in range(window, len(matrix) + 1):
            values = matrix[end-window:end]
            corr, eigenvalues, _, scores, _ = correlation_pca(values)
            residual = remove_market(values, market[end-window:end])
            residual_corr, residual_eigs, _, _, _ = correlation_pca(residual)
            rolling.append({
                "date": returns.index[end-1], "window": window,
                "average_correlation": corr[upper].mean(),
                "within_group_correlation": corr[same_group].mean(),
                "between_group_correlation": corr[other_group].mean(),
                "peer_correlation_gap": corr[same_group].mean() - corr[other_group].mean(),
                "pc1_variance_share": eigenvalues[0] / n,
                "top3_variance_share": eigenvalues[:3].sum() / n,
                "effective_dimension": eigenvalues.sum()**2 / (eigenvalues**2).sum(),
                "pc1_spy_correlation": np.corrcoef(scores[:, 0], market[end-window:end])[0, 1],
                "market_removed_average_correlation": residual_corr[upper].mean(),
                "market_removed_peer_gap": residual_corr[same_group].mean() - residual_corr[other_group].mean(),
                "market_removed_pc1_share": residual_eigs[0] / n,
            })
    rolling = pd.DataFrame(rolling)
    rolling.to_csv(out / "rolling_metrics.csv", index=False)

    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True, layout="constrained")
    for window, color in ((60, "#277da1"), (120, "#d1495b")):
        frame = rolling.loc[rolling.window.eq(window)]
        for ax, metric in zip(axes, ["average_correlation", "peer_correlation_gap", "pc1_variance_share"]):
            ax.plot(frame.date, frame[metric], label=f"{window} trading days", color=color, lw=1.25)
    for ax in axes:
        ax.grid(alpha=.2)
        ax.axvspan(pd.Timestamp("2020-02-20"), pd.Timestamp("2020-04-30"), color="#dddddd", alpha=.5)
    axes[0].set(title="How much do these stocks move together?", ylabel="Mean pair correlation")
    axes[1].set(title="Are manually labeled peers closer than stocks in different groups?",
                ylabel="Within minus between")
    axes[2].set(title="How much standardized variation fits into the first principal component?",
                ylabel="PC1 variance share", xlabel="Window end date (2016–2023 only)")
    axes[0].legend(loc="upper left", ncol=2)
    fig.suptitle("Rolling dependence: 60 days reacts faster; 120 days smooths more\nShading marks an illustrative early-2020 period; all statistics are backward-looking", fontsize=13)
    save_figure(fig, out, "01_rolling_structure")

    snapshot_dates = ["2019-12-31", "2020-03-31", "2023-12-29"]
    snapshots = []
    fig, axes = plt.subplots(2, 3, figsize=(16, 11), layout="constrained")
    for j, end_date in enumerate(snapshot_dates):
        frame = returns.loc[:end_date].tail(120)
        aligned_market = spy.loc[frame.index].to_numpy()
        raw = correlation_pca(frame.to_numpy())[0]
        residual = correlation_pca(remove_market(frame.to_numpy(), aligned_market))[0]
        for i, (corr, mode) in enumerate(((raw, "original"), (residual, "SPY removed"))):
            ax = axes[i, j]
            im = ax.imshow(corr, vmin=-1, vmax=1, cmap="RdBu_r")
            ax.set_title(f"{end_date} · {mode}\n120 trading days", fontsize=11)
            ax.set_xticks(range(n), symbols, rotation=90, fontsize=6)
            ax.set_yticks(range(n), symbols, fontsize=6)
            for boundary in np.arange(4.5, n-1, 5):
                ax.axvline(boundary, color="black", lw=.6)
                ax.axhline(boundary, color="black", lw=.6)
            pd.DataFrame(corr, index=symbols, columns=symbols).to_csv(out / f"correlation_{end_date}_{i}.csv")
        eigenvalues = correlation_pca(frame.to_numpy())[1]
        snapshots.append({"end_date": end_date, "start_date": str(frame.index[0].date()),
                          "sessions": len(frame), "average_correlation": float(raw[upper].mean()),
                          "within_group_correlation": float(raw[same_group].mean()),
                          "between_group_correlation": float(raw[other_group].mean()),
                          "pc1_variance_share": float(eigenvalues[0]/n),
                          "market_removed_within": float(residual[same_group].mean()),
                          "market_removed_between": float(residual[other_group].mean())})
    fig.colorbar(im, ax=axes, shrink=.65, label="Correlation (same color scale in all panels)")
    fig.suptitle("Peer blocks and broad market movement\nFixed stock order: technology | financials | health care | energy | staples | industrials", fontsize=14)
    save_figure(fig, out, "02_correlation_snapshots")

    # One retrospective reference PCA, fitted only on development dates.
    corr, eigs, vectors, scores, loadings = correlation_pca(matrix)
    shares = eigs / eigs.sum()
    pc_spy = float(np.corrcoef(scores[:, 0], market)[0, 1])
    loadings_frame = pd.DataFrame(loadings[:, :5], index=symbols, columns=[f"PC{i}" for i in range(1, 6)])
    loadings_frame.index.name = "symbol"
    loadings_frame.to_csv(out / "pca_stock_component_correlations.csv")
    pd.DataFrame({"component": np.arange(1, n+1), "eigenvalue": eigs,
                  "variance_share": shares, "cumulative_share": shares.cumsum()}).to_csv(out / "pca_variance.csv", index=False)
    pd.DataFrame(scores[:, :5], index=returns.index,
                 columns=[f"PC{i}" for i in range(1, 6)]).to_csv(out / "pca_daily_scores.csv", index_label="date")

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), layout="constrained")
    axes[0, 0].bar(np.arange(1, n+1), shares*100, color="#277da1")
    axes[0, 0].set(title="Each component's share", xlabel="Principal component", ylabel="Standardized variance (%)")
    axes[0, 1].plot(np.arange(1, n+1), shares.cumsum()*100, "o-", color="#43aa8b", ms=3)
    axes[0, 1].set(title="How quickly do components add up?", xlabel="Number of components", ylabel="Cumulative variance (%)", ylim=(0, 102))
    im = axes[1, 0].imshow(loadings[:, :3], cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    axes[1, 0].set_xticks(range(3), ["PC1", "PC2", "PC3"])
    axes[1, 0].set_yticks(range(n), symbols, fontsize=7)
    axes[1, 0].set_title("Which stocks move with each component?")
    fig.colorbar(im, ax=axes[1, 0], label="Correlation(stock return, PC score)", shrink=.75)
    for group in group_names:
        idx = np.array(groups) == group
        axes[1, 1].scatter(loadings[idx, 1], loadings[idx, 2], color=palette[group], label=group.replace("_", " "), s=32)
    label_offsets = {"PG": (-23, -10), "PEP": (-24, 5), "KO": (-23, -5), "PFE": (7, 8),
                     "JPM": (-15, -17), "BAC": (7, 7), "C": (14, -6), "CAT": (7, -13),
                     "DE": (-10, 11), "HON": (8, -10), "UNP": (-12, 9), "GS": (8, 10),
                     "MS": (-21, 9), "XOM": (5, -14), "CVX": (-30, 5), "COP": (8, -5),
                     "EOG": (22, 7), "SLB": (5, 22)}
    for k, symbol in enumerate(symbols):
        axes[1, 1].annotate(symbol, (loadings[k, 1], loadings[k, 2]),
                            xytext=label_offsets.get(symbol, (4, 4)), textcoords="offset points", fontsize=7,
                            arrowprops={"arrowstyle": "-", "lw": .4, "color": "#888888"})
    axes[1, 1].axhline(0, lw=.5, color="gray")
    axes[1, 1].axvline(0, lw=.5, color="gray")
    axes[1, 1].set(title="A view beyond PC1 (partial two-dimensional view)",
                   xlabel=f"PC2 correlation loading ({shares[1]:.1%} variance)",
                   ylabel=f"PC3 correlation loading ({shares[2]:.1%} variance)",
                   xlim=(-.6, .7), ylim=(-.5, .75))
    axes[1, 1].legend(fontsize=7, loc="best")
    for ax in axes[0]:
        ax.grid(axis="y", alpha=.2)
    fig.suptitle(f"PCA of standardized daily returns, 2016–2023\nPC1 explains {shares[0]:.1%}; its daily score correlates {pc_spy:.2f} with SPY", fontsize=14)
    save_figure(fig, out, "03_pca_intuition")

    last_frame = returns.tail(120)
    last_original = correlation_pca(last_frame.to_numpy())[0]
    last_residual = correlation_pca(remove_market(last_frame.to_numpy(), spy.loc[last_frame.index].to_numpy()))[0]
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), layout="constrained")
    peers = []
    for ax, mode, c in zip(axes, ("Original returns", "SPY-regression residual returns"), (last_original, last_residual)):
        distance = np.sqrt(np.maximum(2 * (1-c), 0))
        np.fill_diagonal(distance, 0)
        tree = linkage(squareform(distance, checks=True), method="average", optimal_ordering=True)
        dendrogram(tree, labels=symbols, ax=ax, leaf_rotation=90, leaf_font_size=9,
                   color_threshold=0, above_threshold_color="#526777")
        ax.set_title(mode)
        ax.set_ylabel("Average-linkage distance")
        for label in ax.get_xticklabels():
            label.set_color(palette[groups[symbols.index(label.get_text())]])
        for k, symbol in enumerate(symbols):
            rank = np.argsort(-c[k])
            top = [j for j in rank if j != k][:3]
            peers.append({"mode": mode, "symbol": symbol, "manual_group": groups[k],
                          **{f"peer_{i+1}": symbols[j] for i, j in enumerate(top)},
                          **{f"correlation_{i+1}": float(c[k, j]) for i, j in enumerate(top)}})
    handles = [Line2D([], [], marker="o", linestyle="", color=palette[g], label=g.replace("_", " ")) for g in group_names]
    fig.legend(handles=handles, ncol=6, loc="outside lower center", fontsize=9)
    fig.suptitle("Who looks like a peer? Last 120 development sessions ending 2023-12-29\nBranches merge at greater distance as similarity weakens; colors show manual labels", fontsize=13)
    save_figure(fig, out, "04_peer_hierarchies")
    pd.DataFrame(peers).to_csv(out / "nearest_peers_2023-12-29.csv", index=False)

    latest = rolling.loc[rolling.date.eq(rolling.date.max())].copy()
    summary = {
        "development_start": str(returns.index.min().date()),
        "development_end": str(returns.index.max().date()), "return_observations": len(returns),
        "equities": n, "held_out_from": "2024-01-01", "windows_sessions": [60, 120],
        "pca_variance_share": shares.tolist(), "pc1_spy_correlation": pc_spy,
        "components_for_50pct": int(np.searchsorted(shares.cumsum(), .5)+1),
        "components_for_80pct": int(np.searchsorted(shares.cumsum(), .8)+1),
        "latest_rolling": json.loads(latest.to_json(orient="records", date_format="iso")),
        "snapshots": snapshots,
        "method": "Pearson correlations and sample-correlation PCA of daily log returns; SPY residuals use same-window OLS with intercept.",
        "checks": {"input_no_missing": True, "held_out_excluded": True,
                   "pca_reconstruction_and_trace": True, "residual_market_orthogonality": True},
        "source_file_sha256": hashlib.sha256((DATA / "returns_log.csv").read_bytes()).hexdigest(),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    options = parser.parse_args()
    result = run_analysis(options.out)
    print(json.dumps({k: result[k] for k in ("development_start", "development_end", "return_observations", "components_for_50pct", "components_for_80pct", "pc1_spy_correlation", "checks")}, indent=2))
