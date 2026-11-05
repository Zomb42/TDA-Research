"""PCA and frozen-rule residual reversal on the existing 200-stock panel.

Exploratory follow-up, gross/pre-fee only. No downloads, orders, regime filter,
parameter selection by profit, or changes to earlier frozen experiments.
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
from ripser import ripser

from equity_residual_backtest import construct, exposures as original_exposures

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "market_data/datasets/equity_daily_expanded_2016_2026-10-27"
OUT = ROOT / "experiments/equity_expanded_pca_reversal"
MODELS = ["SPY_only", "SPY_PCA3", "Sector11", "Average11", "SPY_PCA10"]
WINDOWS = [120, 252]
PERIODS = ["development", "later"]
CONFIG = {
    "decision_date": "2026-10-29", "status": "exploratory on previously examined dates and current-survivor selected securities",
    "data": DATA.name, "stocks": 200, "benchmark": "SPY", "no_additional_download": True,
    "primary_models": ["SPY_only", "SPY_PCA3"], "additional_comparators": ["Sector11", "Average11", "SPY_PCA10"],
    "primary_lookback": 120, "sensitivity_lookback": 252,
    "eligibility": "272 complete contiguous prior log returns ending t-1; same admitted stocks across windows/models; no future availability filtering",
    "signal": "one-session vendor-adjusted close-to-close log return at t",
    "training": "prior observations t-lookback:t, exclusive of signal day",
    "weights": "inverse prior total-return variance; daily sigma floor 0.0001",
    "holdings": "minus W times cross-sectional WLS residual, normalized to unit gross; no caps",
    "exposures": "SPY_only: dollars+SPY beta; PCA3/PCA10: additional raw-return-scaled residual PCs; sectors/average: 11 group indicators+SPY beta",
    "pca_scaling": "standardize prior SPY residual histories; raw exposure basis = residual_sigma[:,None] * right_singular_vectors",
    "primary_execution": "next vendor raw daily-bar open to same session raw close; ideal fractional-dollar targets, flat nightly",
    "horizon_response": "1/5/20-session cumulative all-adjusted next-open-to-exit-close returns of frozen initial sleeves; common complete 20-session dates, omit split-crossing events; not a funded overlapping-cohort strategy",
    "horizon_slope": "pooled e'W R / e'W e; equivalent to future formation-exposure residual/sigma on signal residual/sigma; negative indicates reversal",
    "universe_control": "rerun original30 SPY_only and PCA3 on identical dates/windows; groups/PCA10 comparators only expanded200",
    "split": "entry before 2024-01-01 development, otherwise later; not untouched holdout",
    "descriptive_PCA": "2016-2023 only, balance using availability in that period only; original30 and expanded200; standardized raw log returns; full-panel membership is not used for backtest admission",
    "uncertainty": "1000 circular moving-block resamples of 60 formation dates per period; pointwise approximate 95%; paired broad-minus-original control uses identical resamples",
    "reported_selection": "all declared models/windows/periods; no winning setting selected",
    "state_features": "save past-fit mean residual correlation, residual PC1 share, H0 death quantiles, prior SPY volatility as potential regime inputs; no state-to-profit model fitted",
    "representation_snapshot": "formation 2023-12-29, prior 252 sessions, current admitted stocks; stock residual-history geometry, full weighted loadings identity control, top3 weighted loading geometry, and day points in top3 factor-score space",
    "snapshot_scaling": "each non-control distance matrix divided by its own positive median pair distance for diagram comparison; raw scale saved separately",
    "persistence": "snapshot H0/H1 Vietoris-Rips, finite intervals saved; no interpretation as economic cycles, significance, calendar duration, or profitable regimes",
    "fees": "excluded entirely", "regime_filter": False, "seed": 2026102901,
}
COLORS = dict(zip(MODELS, ["#6c757d", "#277da1", "#8c6bb1", "#e58a20", "#43aa8b"]))
NAMES = {"SPY_only": "SPY only", "SPY_PCA3": "SPY + 3 residual PCs", "Sector11": "11 sectors + SPY",
         "Average11": "11 average-linkage groups + SPY", "SPY_PCA10": "SPY + 10 residual PCs"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fit(history, market, groups, extended):
    sigma = np.maximum(history.std(axis=0, ddof=1), .0001)
    design = np.column_stack([np.ones(len(market)), market])
    market_fit = np.linalg.lstsq(design, history, rcond=None)[0]
    residual = history - design @ market_fit
    residual_sigma = np.maximum(residual.std(axis=0, ddof=1), .0001)
    z = (residual-residual.mean(axis=0))/residual_sigma
    _, singular, vt = np.linalg.svd(z, full_matrices=False)
    values = singular**2/(len(z)-1)
    vectors = vt.T
    beta = market_fit[1]
    matrices = {"SPY_only": np.column_stack([np.ones(len(sigma)), beta]),
                "SPY_PCA3": np.column_stack([np.ones(len(sigma)), beta, residual_sigma[:, None]*vectors[:, :3]])}
    distance = np.sqrt(np.maximum(2*(1-z.T@z/(len(z)-1)), 0)); np.fill_diagonal(distance, 0)
    if extended:
        labels = cut_tree(linkage(squareform(distance), method="average"), n_clusters=[11])[:, 0]
        assert len(set(groups)) == 11
        matrices.update(Sector11=np.column_stack([np.eye(11)[groups], beta]),
                        Average11=np.column_stack([np.eye(11)[labels], beta]),
                        SPY_PCA10=np.column_stack([np.ones(len(sigma)), beta, residual_sigma[:, None]*vectors[:, :10]]))
    deaths = linkage(squareform(distance), method="single")[:, 2]
    pairs = distance[np.triu_indices(len(distance), 1)]
    return matrices, 1/sigma**2, {"z": z, "eigenvalues": values, "vectors": vectors,
        "market_fit": market_fit, "distance": distance, "residual_sigma": residual_sigma,
        "mean_residual_correlation": float(np.mean(1-pairs**2/2)),
        "residual_pc1_share": float(values[0]/values.sum()),
        "residual_pc3_share": float(values[:3].sum()/values.sum()),
        "residual_pc10_share": float(values[:10].sum()/values.sum()),
        "H0_death_median": float(np.median(deaths)), "H0_death_q90": float(np.quantile(deaths, .9))}


def descriptive(panel, symbols, universe):
    frame = panel.loc[:"2023-12-31", symbols]
    admitted = frame.columns[frame.notna().all()].tolist()
    frame = frame[admitted]
    z = ((frame-frame.mean())/frame.std(ddof=1)).to_numpy()
    _, singular, vt = np.linalg.svd(z, full_matrices=False)
    values = singular**2/(len(z)-1); vectors = vt.T
    scores = z @ vectors
    for k in range(len(values)):
        sign = np.sign(np.corrcoef(scores[:, k], panel.loc[frame.index, "SPY"])[0, 1]) if k == 0 else np.sign(vectors[np.argmax(abs(vectors[:, k])), k])
        if sign < 0: vectors[:, k] *= -1; scores[:, k] *= -1
    variance = pd.DataFrame({"component": np.arange(1, len(values)+1), "eigenvalue": values,
        "variance_fraction": values/values.sum(), "cumulative_fraction": np.cumsum(values)/values.sum()})
    variance.to_csv(OUT/f"descriptive_variance_{universe}.csv", index=False)
    loading = pd.DataFrame(vectors[:, :10]*np.sqrt(values[:10]), index=admitted, columns=[f"PC{k}" for k in range(1, 11)])
    loading.index.name = "symbol"; loading.to_csv(OUT/f"descriptive_loadings_{universe}.csv")
    pd.DataFrame(scores[:, :10], index=frame.index, columns=loading.columns).to_csv(OUT/f"descriptive_scores_{universe}.csv")
    return {"universe": universe, "stocks": len(admitted), "omitted_short_histories": sorted(set(symbols)-set(admitted)),
        "return_observations": len(frame), "first_date": str(frame.index[0].date()), "last_date": str(frame.index[-1].date()),
        "PC1_fraction": float(values[0]/values.sum()), "PC3_cumulative": float(values[:3].sum()/values.sum()),
        "PC10_cumulative": float(values[:10].sum()/values.sum()),
        "PC1_SPY_correlation": float(np.corrcoef(scores[:, 0], panel.loc[frame.index, "SPY"])[0, 1])}


def resamples(n, seed):
    rng = np.random.default_rng(seed)
    starts = rng.integers(n, size=(1000, int(np.ceil(n/60))))
    return ((starts[:, :, None]+np.arange(60)) % n).reshape(1000, -1)[:, :n]


def ratio(numerator, denominator, indices):
    a, b = np.asarray(numerator), np.asarray(denominator)
    boot = a[indices].sum(axis=1)/b[indices].sum(axis=1)
    return float(a.sum()/b.sum()), *map(float, np.quantile(boot, [.025, .975]))


def summaries(daily, events):
    records, event_records, differences = [], [], []
    for pi, period in enumerate(PERIODS):
        dates = sorted(daily.loc[daily.period.eq(period), "signal_date"].unique())
        indices = resamples(len(dates), CONFIG["seed"]+pi)
        for (universe, window, model), frame in daily.loc[daily.period.eq(period)].groupby(["universe", "window", "model"]):
            frame = frame.sort_values("signal_date"); assert list(frame.signal_date) == dates
            values = frame.gross_return.to_numpy()
            center, lo, hi = ratio(values, np.ones(len(values)), indices)
            equity = np.cumprod(1+values); peaks = np.maximum.accumulate(np.r_[1., equity])[1:]
            assert (1+values > 0).all()
            records.append({"period": period, "universe": universe, "window": window, "model": model,
                "days": len(values), "mean_daily_bps": center*1e4, "mean_low": lo*1e4, "mean_high": hi*1e4,
                "sharpe_vs_zero": center/values.std(ddof=1)*np.sqrt(252),
                "annualized_volatility": values.std(ddof=1)*np.sqrt(252),
                "gross_CAGR": equity[-1]**(252/len(values))-1, "total_gross_return": equity[-1]-1,
                "max_drawdown": float(np.min(equity/peaks-1)), "mean_stocks": frame.stocks.mean(),
                "mean_effective_breadth": frame.effective_breadth.mean(), "max_position": frame.max_abs_position.max()})
        for window in WINDOWS:
            for model in MODELS[:2]:
                select = daily.loc[daily.period.eq(period) & daily.window.eq(window) & daily.model.eq(model)]
                pivot = select.pivot(index="signal_date", columns="universe", values="gross_return").loc[dates]
                center, lo, hi = ratio(pivot.expanded200-pivot.original30, np.ones(len(pivot)), indices)
                differences.append({"period": period, "window": window, "model": model,
                    "expanded_minus_original_mean_bps": center*1e4, "low": lo*1e4, "high": hi*1e4})
        event_dates = sorted(events.loc[events.period.eq(period), "signal_date"].unique())
        indices = resamples(len(event_dates), CONFIG["seed"]+100+pi)
        for (universe, window, model, horizon), frame in events.loc[events.period.eq(period)].groupby(["universe", "window", "model", "horizon"]):
            frame = frame.sort_values("signal_date"); assert list(frame.signal_date) == event_dates
            center, lo, hi = ratio(frame.gross_event_return, np.ones(len(frame)), indices)
            slope, sl, sh = ratio(frame.cross_product, frame.signal_squared, indices)
            event_records.append({"period": period, "universe": universe, "window": window, "model": model, "horizon": horizon,
                "events": len(frame), "mean_event_bps": center*1e4, "mean_low": lo*1e4, "mean_high": hi*1e4,
                "response_slope": slope, "slope_low": sl, "slope_high": sh})
    return pd.DataFrame(records), pd.DataFrame(event_records), pd.DataFrame(differences)


def representation_snapshot(snapshot, names):
    z, vectors, values = snapshot["z"], snapshot["vectors"], snapshot["eigenvalues"]
    full_loadings = vectors*np.sqrt(values)
    original = snapshot["distance"]
    rebuilt = squareform(pdist(full_loadings))
    error = float(np.max(abs(original-rebuilt)))
    assert error < 1e-7
    loading3 = full_loadings[:, :3]
    states = z @ vectors[:, :3]
    geometries = {"Stocks_return_history": original,
                  "Stocks_top3_loadings": squareform(pdist(loading3)),
                  "Days_top3_scores": squareform(pdist(states))}
    labels = {"Stocks_return_history": names, "Stocks_top3_loadings": names,
              "Days_top3_scores": [f"history_day_{i+1}" for i in range(len(states))]}
    records, intervals = [], []
    for name, distance in geometries.items():
        scale = float(np.median(distance[np.triu_indices(len(distance), 1)]))
        normalized = distance/scale
        diagrams = ripser(normalized, distance_matrix=True, maxdim=1)["dgms"]
        for dimension, diagram in enumerate(diagrams):
            for birth, death in diagram:
                intervals.append({"representation": name, "dimension": dimension, "birth": float(birth),
                                  "death": float(death) if np.isfinite(death) else None})
        finite_h1 = diagrams[1][np.isfinite(diagrams[1][:, 1])]
        lifetime = finite_h1[:, 1]-finite_h1[:, 0]
        records.append({"representation": name, "points": len(distance), "original_median_distance": scale,
                        "finite_H0_bars": len(diagrams[0])-1, "finite_H1_bars": len(lifetime),
                        "H1_max_lifetime_normalized": float(lifetime.max()) if len(lifetime) else 0})
        np.savez_compressed(OUT/f"snapshot_{name}.npz", distance=distance, labels=np.array(labels[name]), H0=diagrams[0], H1=diagrams[1])
    pd.DataFrame(records).to_csv(OUT/"representation_snapshot_summary.csv", index=False)
    pd.DataFrame(intervals).to_csv(OUT/"representation_snapshot_intervals.csv", index=False)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), layout="constrained")
    titles = ["Stocks: full residual histories", "Stocks: top-3 weighted loadings", "Days: top-3 factor scores"]
    for ax, (name, title) in zip(axes, zip(geometries, titles)):
        saved = np.load(OUT/f"snapshot_{name}.npz")
        finite = [saved[f"H{i}"][np.isfinite(saved[f"H{i}"][:, 1])] for i in [0, 1]]
        limit = max(1., *(float(v.max()) if len(v) else 0. for v in finite))*1.08
        ax.plot([0, limit], [0, limit], color="gray", lw=.7)
        for i, color in [(0, "#277da1"), (1, "#e58a20")]:
            if len(finite[i]): ax.scatter(finite[i][:, 0], finite[i][:, 1], s=12, alpha=.6, color=color, label=f"H{i}")
        ax.set(xlim=(-.03, limit), ylim=(-.03, limit), xlabel="Birth (median-distance units)", ylabel="Death", title=title)
    axes[0].legend()
    fig.suptitle("Representation illustration: formation 2023-12-29, prior 252 sessions\nFinite intervals only; each geometry scaled by its own median distance; no regime/profitability test")
    fig.savefig(OUT/"06_representation_diagrams.png", dpi=160); plt.close(fig)
    return {"full_weighted_loading_distance_identity_max_error": error, "snapshot_results": records}


def plots(daily, performance, events_summary, descriptive_results, metadata):
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
    for universe, color in [("original30", "#6c757d"), ("expanded200", "#277da1")]:
        f = pd.read_csv(OUT/f"descriptive_variance_{universe}.csv").iloc[:20]
        axes[0].plot(f.component, f.variance_fraction*100, "o-", color=color, label=universe)
        axes[1].plot(f.component, f.cumulative_fraction*100, "o-", color=color)
    axes[0].set(ylabel="Share of standardized variance (%)", xlabel="Component", title="Individual components")
    axes[1].set(ylabel="Cumulative standardized variance (%)", xlabel="Components retained", title="Reconstruction, not forecasting")
    axes[0].legend(); fig.suptitle("Descriptive PCA: 2016–2023 balanced availability within that period")
    fig.savefig(OUT/"01_descriptive_pca.png", dpi=160); plt.close(fig)
    loading = pd.read_csv(OUT/"descriptive_loadings_expanded200.csv", index_col="symbol")
    sector_loadings = loading.join(metadata.sector_snapshot).groupby("sector_snapshot").mean()
    fig, ax = plt.subplots(figsize=(9, 5.5), layout="constrained")
    limit = np.max(abs(sector_loadings.iloc[:, :5].to_numpy()))
    im = ax.imshow(sector_loadings.iloc[:, :5], cmap="RdBu_r", vmin=-limit, vmax=limit, aspect="auto")
    ax.set_xticks(np.arange(5), sector_loadings.columns[:5]); ax.set_yticks(np.arange(len(sector_loadings)), sector_loadings.index)
    ax.set_title("Mean stock/component correlations by current sector\nArbitrary PC signs; observed patterns, not identified economic causes")
    fig.colorbar(im, ax=ax, label="Correlation with fitted component score")
    fig.savefig(OUT/"02_descriptive_sector_loadings.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), layout="constrained")
    for row, window in enumerate(WINDOWS):
        for col, period in enumerate(["all", "later"]):
            ax = axes[row, col]
            for model in MODELS:
                f = daily.loc[daily.universe.eq("expanded200") & daily.window.eq(window) & daily.model.eq(model)].sort_values("date")
                if period == "later": f = f.loc[f.period.eq("later")]
                equity = (1+f.gross_return).cumprod()
                ax.plot(pd.to_datetime(f.date), 100000*(equity-1), color=COLORS[model], label=NAMES[model])
            ax.axhline(0, color="black", lw=.7); ax.set_ylabel("Simulated gross profit on initial $100,000")
            ax.set_title(f"{window}-session fit | {'full run' if period=='all' else 'later period reset to $100,000'}")
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Expanded-universe one-session strategy | raw next-bar open to close | pre-fee")
    fig.savefig(OUT/"03_gross_profit.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout="constrained")
    for ax, period in zip(axes, PERIODS):
        for j, window in enumerate(WINDOWS):
            f = performance.loc[performance.period.eq(period) & performance.universe.eq("expanded200") & performance.window.eq(window)].set_index("model").loc[MODELS]
            ax.errorbar(np.arange(5)+(j-.5)*.12, f.mean_daily_bps,
                yerr=[f.mean_daily_bps-f.mean_low, f.mean_high-f.mean_daily_bps], fmt="o", capsize=3, label=f"{window} sessions")
        ax.set_xticks(np.arange(5), ["SPY", "+3 PCs", "Sectors", "Average", "+10 PCs"])
        ax.axhline(0, color="black", lw=.7); ax.set_ylabel("Mean gross bps/day"); ax.set_title(period.title())
    axes[0].legend(); fig.suptitle("All declared expanded-universe models | approximate pointwise 95% date-block intervals")
    fig.savefig(OUT/"04_daily_mean_intervals.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    for row, window in enumerate(WINDOWS):
        for col, period in enumerate(PERIODS):
            ax = axes[row, col]
            for j, model in enumerate(MODELS):
                f = events_summary.loc[events_summary.universe.eq("expanded200") & events_summary.window.eq(window) & events_summary.period.eq(period) & events_summary.model.eq(model)].sort_values("horizon")
                ax.errorbar(np.arange(3)+(j-2)*.06, f.mean_event_bps,
                    yerr=[f.mean_event_bps-f.mean_low, f.mean_high-f.mean_event_bps], fmt="o-", ms=3, lw=1, capsize=2, color=COLORS[model], label=NAMES[model])
            ax.set_xticks(np.arange(3), [1, 5, 20]); ax.axhline(0, color="black", lw=.7)
            ax.set(xlabel="Holding sessions including entry", ylabel="Mean gross bps/event", title=f"{period.title()} | {window}-session fit")
    axes[0, 0].legend(fontsize=7)
    fig.suptitle("Frozen-sleeve horizon responses from adjusted prices\nOverlapping events, not compounded portfolio returns; approximate pointwise 95% intervals")
    fig.savefig(OUT/"05_horizon_event_returns.png", dpi=160); plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    spec = OUT/"specification.json"
    if spec.exists() and json.loads(spec.read_text()) != CONFIG: raise ValueError("Existing specification differs")
    spec.write_text(json.dumps(CONFIG, indent=2)+"\n")
    protected_paths = [DATA/"returns_log.csv", DATA/"bars_raw.csv", DATA/"bars_all.csv", DATA/"universe.csv",
        ROOT/"experiments/equity_residual_backtest.py", ROOT/"experiments/equity_residual_backtest/evaluated/summary.json",
        ROOT/"experiments/equity_expanded_structure.py", ROOT/"experiments/equity_expanded_structure/summary.json",
        ROOT/"experiments/equity_reversal_response.py", ROOT/"experiments/equity_reversal_response/summary.json"]
    protected = {str(p.relative_to(ROOT)): sha(p) for p in protected_paths}
    universe = pd.read_csv(DATA/"universe.csv").query("role == 'equity'").set_index("symbol")
    symbols = universe.index.tolist(); original_names = universe.index[universe.in_original_30].tolist()
    panel = pd.read_csv(DATA/"returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    x, market = panel[symbols].to_numpy(), panel.SPY.to_numpy()
    price = {}
    for mode in ["raw", "all"]:
        bars = pd.read_csv(DATA/f"bars_{mode}.csv", parse_dates=["date"])
        price[mode] = {field: bars.pivot(index="date", columns="symbol", values=field).reindex(index=panel.index, columns=symbols).to_numpy() for field in ["o", "c"]}
    descriptives = [descriptive(panel, original_names, "original30"), descriptive(panel, symbols, "expanded200")]
    ts = list(range(272, len(panel)-1))
    positions = np.zeros((len(ts), 2, 5, len(symbols)))
    old_positions = np.zeros((len(ts), 2, 2, len(original_names)))
    original_idx = np.array([symbols.index(s) for s in original_names])
    daily, events, features, formations = [], [], [], []
    max_error, max_original_error = 0., 0.; snapshot = None
    for di, t in enumerate(ts):
        available = np.flatnonzero(np.isfinite(x[t-272:t]).all(axis=0))
        assert set(original_idx) <= set(available)
        formations.append({"signal_date": panel.index[t], "entry": panel.index[t+1], "training_end": panel.index[t-1],
                           "eligibility_start": panel.index[t-272], "stocks": len(available), "symbols": "|".join(np.array(symbols)[available])})
        event_ok = t+20 < len(panel) and ((panel.index[t+1] < pd.Timestamp("2024-01-01")) == (panel.index[t+20] < pd.Timestamp("2024-01-01")))
        period = "development" if panel.index[t+1] < pd.Timestamp("2024-01-01") else "later"
        for wi, window in enumerate(WINDOWS):
            for name, idx in [("expanded200", available), ("original30", original_idx)]:
                history = x[t-window:t, idx]
                labels = pd.factorize(universe.iloc[idx].sector_snapshot, sort=False)[0]
                matrices, weights, fitted = fit(history, market[t-window:t], labels, name == "expanded200")
                if name == "expanded200":
                    features.append({"signal_date": panel.index[t], "training_end": panel.index[t-1], "window": window,
                        "stocks": len(idx), "prior_SPY_vol20": float(market[t-20:t].std(ddof=1)*np.sqrt(252)),
                        **{k: fitted[k] for k in ["mean_residual_correlation", "residual_pc1_share", "residual_pc3_share", "residual_pc10_share", "H0_death_median", "H0_death_q90"]}})
                    if str(panel.index[t].date()) == "2023-12-29" and window == 252:
                        snapshot = (fitted, np.array(symbols)[idx].tolist())
                for mi, (model, exposure) in enumerate(matrices.items()):
                    holding, residual, error, condition = construct(x[t, idx], exposure, weights)
                    max_error = max(max_error, error)
                    if name == "expanded200": positions[di, wi, MODELS.index(model), idx] = holding
                    else: old_positions[di, wi, mi] = holding
                    rank = np.linalg.matrix_rank(exposure)
                    expected_rank = 2 if model == "SPY_only" else 5 if model == "SPY_PCA3" else 12
                    assert rank == expected_rank
                    future = price["raw"]["c"][t+1, idx]/price["raw"]["o"][t+1, idx]-1
                    assert np.isfinite(future).all()
                    daily.append({"signal_date": panel.index[t], "date": panel.index[t+1], "training_end": panel.index[t-1],
                        "period": period, "universe": name, "window": window, "model": model, "stocks": len(idx),
                        "gross_return": float(holding@future), "exposure_rank": int(rank), "max_exposure_error": error,
                        "max_abs_position": float(abs(holding).max()), "effective_breadth": float(1/np.sum(holding**2)),
                        "regression_condition": condition, "signal_residual_rms": float(np.sqrt(np.mean(residual**2)))})
                    if name == "original30" and window == 120 and di % 200 == 0:
                        old_x, old_w, _ = original_exposures(history, market[t-window:t])
                        key = "SPY_only" if model == "SPY_only" else "SPY_plus_3_residual_PCs"
                        old_h = construct(x[t, idx], old_x[key], old_w)[0]
                        max_original_error = max(max_original_error, float(np.max(abs(old_h-holding))))
                    if event_ok:
                        denom = float((residual*weights)@residual)
                        for horizon in [1, 5, 20]:
                            response = price["all"]["c"][t+horizon, idx]/price["all"]["o"][t+1, idx]-1
                            assert np.isfinite(response).all()
                            events.append({"signal_date": panel.index[t], "entry": panel.index[t+1], "exit": panel.index[t+horizon],
                                "period": period, "universe": name, "window": window, "model": model, "horizon": horizon,
                                "gross_event_return": float(holding@response), "cross_product": float((residual*weights)@response),
                                "signal_squared": denom})
        if (di+1) % 400 == 0: print(f"Completed {di+1} formation dates; current eligible={len(available)}", flush=True)
    daily, events = pd.DataFrame(daily), pd.DataFrame(events)
    pd.DataFrame(formations).to_csv(OUT/"formation_dates.csv", index=False)
    pd.DataFrame(features).to_csv(OUT/"past_state_features.csv", index=False)
    daily.to_csv(OUT/"daily_gross_returns.csv", index=False); events.to_csv(OUT/"horizon_events.csv", index=False)
    np.savez_compressed(OUT/"positions.npz", expanded=positions, original=old_positions,
                        symbols=np.array(symbols), original_symbols=np.array(original_names), dates=np.array([str(panel.index[t].date()) for t in ts]))
    performance, event_summary, differences = summaries(daily, events)
    performance.to_csv(OUT/"gross_performance.csv", index=False)
    event_summary.to_csv(OUT/"horizon_summary.csv", index=False)
    differences.to_csv(OUT/"paired_universe_differences.csv", index=False)
    pd.DataFrame(descriptives).to_csv(OUT/"descriptive_summary.csv", index=False)
    assert snapshot is not None
    representation = representation_snapshot(*snapshot)
    plots(daily, performance, event_summary, descriptives, universe)
    assert max_original_error < 1e-9
    checks = {"causal_training_and_entry": True, "common_past_only_admission": True,
        "expected_full_exposure_ranks": True, "no_missing_target_member_filtering": True,
        "original30_SVD_matches_frozen_eigendecomposition": True,
        "protected_artifacts_unchanged": all(sha(p)==protected[str(p.relative_to(ROOT))] for p in protected_paths)}
    assert all(checks.values())
    result = {"configuration": CONFIG, "checks": checks, "descriptive_PCA": descriptives,
        "representation_control": representation, "max_initial_scaled_exposure_error": max_error,
        "max_original30_SVD_eigendecomposition_holdings_error": max_original_error,
        "daily_dates_by_period": daily.loc[daily.universe.eq("expanded200") & daily.window.eq(120) & daily.model.eq("SPY_only")].groupby("period").size().to_dict(),
        "source_sha256": sha(Path(__file__)), "protected_sha256": protected}
    (OUT/"summary.json").write_text(json.dumps(result, indent=2)+"\n")
    print("PCA\n", pd.DataFrame(descriptives).drop(columns="omitted_short_histories").round(5).to_string(index=False))
    print("DAILY GROSS\n", performance.loc[performance.universe.eq("expanded200")].round(5).to_string(index=False))
    print("PAIRED UNIVERSE\n", differences.round(5).to_string(index=False))
    print("LATER EVENTS\n", event_summary.loc[event_summary.universe.eq("expanded200") & event_summary.period.eq("later")].round(5).to_string(index=False))


if __name__ == "__main__":
    main()
