"""Causal formation, frozen exposures, gross residual-response event study.

Exploratory follow-up: the time period and basket have already been examined.
No network, orders, cost model, best-horizon selection, or strategy compounding.
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
from scipy.spatial.distance import squareform

from equity_h0_peers import geometry, group_exposures
from equity_residual_backtest import DATA, construct, load_data

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/equity_reversal_response"
MODELS = ["Manual6", "Average6", "PCA5"]
HORIZONS = [1, 5, 20]
PERIODS = ["development", "evaluation"]
BINS = np.array([-np.inf, -2, -1, -.5, 0, .5, 1, 2, np.inf])
BIN_NAMES = ["<-2", "-2 to -1", "-1 to -0.5", "-0.5 to 0",
             "0 to 0.5", "0.5 to 1", "1 to 2", ">=2"]
CONFIG = {
    "status": "exploratory on already examined history; no untouched holdout",
    "models": MODELS, "horizons_sessions": HORIZONS, "base_lookback": 120,
    "first_signal_index": 140, "exposure_rank": 7,
    "signal": "adjusted one-session close-to-close log return, residualized by frozen prior X and W",
    "normalization": "signal residual / prior total daily sigma, floor 0.0001",
    "weights": "inverse prior total variance; holdings proportional to minus W times residual, unit gross",
    "entry": "next vendor daily-bar open; ideal fractional-dollar targets",
    "exit": "close of entry session or fifth or twentieth session including entry session",
    "return_prices": "all-adjusted open/close for every horizon; vendor total-return proxy, no action-level ledger",
    "holding": "initial dollar sleeves buy and hold; no intermediate rebalance; exposures may drift",
    "future_relative_return": "cumulative simple open-to-close stock return residualized cross-sectionally with formation X,W",
    "slope": "pooled through-origin slope of future residual/sigma on signal residual/sigma; negative means reversal",
    "signal_bin_edges_finite": [-2, -1, -.5, 0, .5, 1, 2],
    "bin_edges": "left inclusive, right exclusive; outer bins unbounded",
    "exclude_zero_signal": "abs(signal residual / sigma) <= 1e-10; includes constrained singleton stocks",
    "stability": "Average6 stock-level mean Jaccard overlap of peer sets across 100,140,120-shifted-5 past-session fits",
    "stability_high": ">=0.75; complementary lower group; no outcome-selected threshold",
    "stability_manual": "fixed by construction, not an empirical stability test",
    "stability_PCA": "not defined: no discrete peer assignment",
    "date_sample": "same dates for all horizons; omit any 20-session outcome crossing 2024 boundary",
    "split": "entry before 2024-01-01 development, otherwise evaluation",
    "uncertainty": "1000 circular moving-block date resamples; block 60 sessions; all stocks together",
    "intervals": "approximate 95% pointwise percentile; pooled ratios recomputed per resample; no multiplicity correction",
    "bootstrap_repetitions": 1000, "bootstrap_block_sessions": 60,
    "seed": 2026102807,
    "fees": "excluded entirely", "parameter_selection_by_profit": False,
    "outputs": "event responses, not daily returns of an overlapping-cohort trading strategy",
}
COLORS = {"Manual6": "#6c757d", "Average6": "#e58a20", "PCA5": "#277da1"}
NAMES = {"Manual6": "Manual peers", "Average6": "Average-linkage peers", "PCA5": "5 residual PCs"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def average_labels(distance):
    return cut_tree(linkage(squareform(distance), method="average"), n_clusters=[6])[:, 0]


def project(values, exposure, weights):
    # Same WLS residual projection as the frozen portfolio constructor.
    scaled = exposure / np.sqrt(np.mean(exposure ** 2, axis=0))
    fit = np.linalg.lstsq(np.sqrt(weights)[:, None] * scaled,
                          np.sqrt(weights) * values, rcond=None)[0]
    return values - scaled @ fit


def peer_stability(base, altered):
    peers = base[:, None] == base[None, :]
    np.fill_diagonal(peers, False)
    scores = []
    for labels in altered:
        other = labels[:, None] == labels[None, :]
        np.fill_diagonal(other, False)
        union = (peers | other).sum(axis=1)
        scores.append(np.divide((peers & other).sum(axis=1), union,
                                out=np.ones(len(base)), where=union > 0))
    return np.mean(scores, axis=0)


def bootstrap_indices(length):
    rng = np.random.default_rng(CONFIG["seed"] + length)
    block = CONFIG["bootstrap_block_sessions"]
    starts = rng.integers(length, size=(CONFIG["bootstrap_repetitions"], int(np.ceil(length / block))))
    return ((starts[:, :, None] + np.arange(block)) % length).reshape(len(starts), -1)[:, :length]


def ratio_interval(numerator, denominator, indices):
    numerator, denominator = np.asarray(numerator), np.asarray(denominator)
    point = numerator.sum() / denominator.sum()
    dn = denominator[indices].sum(axis=1)
    boot = np.divide(numerator[indices].sum(axis=1), dn,
                     out=np.full(len(indices), np.nan), where=dn > 1e-14)
    lo, hi = np.nanquantile(boot, [.025, .975])
    return float(point), float(lo), float(hi), boot


def controls():
    rng = np.random.default_rng(73)
    exposure = np.column_stack([np.ones(30), rng.normal(size=(30, 6))])
    sigma = np.exp(rng.normal(size=30))
    weights = 1 / sigma ** 2
    signal = rng.normal(size=30)
    h, e, _, _ = construct(signal, exposure, weights)
    assert np.allclose(e, project(signal, exposure, weights))
    for response, sign in [(-.3 * e, -1), (.3 * e, 1)]:
        y = project(response, exposure, weights)
        slope = (e / sigma) @ (y / sigma) / np.sum((e / sigma) ** 2)
        assert np.sign(slope) == sign
        assert np.sign(h @ response) == -sign
        assert np.allclose(h @ response, h @ y)
    labels = np.repeat(np.arange(6), 5)
    assert np.allclose(peer_stability(labels, [labels + 9] * 3), 1)
    # Price endpoint convention: fifth exit includes entry session (index 1..5).
    op = np.arange(10, 40, dtype=float)[:, None]
    cl = op + 1
    t = 3
    assert np.isclose((cl[t + 5] / op[t + 1] - 1)[0], 5 / 14)
    return {"synthetic_reversal_negative_slope_positive_gross": True,
            "synthetic_continuation_positive_slope_negative_gross": True,
            "future_projection_preserves_neutral_portfolio_pnl": True,
            "peer_stability_label_invariant": True,
            "horizon_includes_entry_session": True}


def estimate_tables(daily, sufficient):
    rows, bins, stability = [], [], []
    for period in PERIODS:
        frame = daily.loc[daily.period.eq(period)]
        dates = sorted(frame.signal_date.unique())
        indices = bootstrap_indices(len(dates))
        for model in MODELS:
            for horizon in HORIZONS:
                g = frame.loc[frame.model.eq(model) & frame.horizon.eq(horizon)].sort_values("signal_date")
                assert list(g.signal_date) == dates
                slope, sl, sh, _ = ratio_interval(g.cross_product, g.signal_squared, indices)
                gross, gl, gh, _ = ratio_interval(g.gross_return, np.ones(len(g)), indices)
                rows.append({"period": period, "model": model, "horizon": horizon,
                             "signal_dates": len(g), "stock_events": int(g.active_stocks.sum()),
                             "response_slope": slope, "slope_low": sl, "slope_high": sh,
                             "mean_gross_event_bps": gross * 1e4,
                             "gross_low": gl * 1e4, "gross_high": gh * 1e4})
                for b in range(8):
                    a = sufficient[(period, model, horizon, b)]
                    if not a[:, 1].sum():
                        continue
                    v, lo, hi, _ = ratio_interval(a[:, 0], a[:, 1], indices)
                    bins.append({"period": period, "model": model, "horizon": horizon,
                                 "bin": b, "bin_label": BIN_NAMES[b], "stock_events": int(a[:, 1].sum()),
                                 "dates_with_events": int((a[:, 1] > 0).sum()),
                                 "mean_signal_z": float(a[:, 2].sum() / a[:, 1].sum()),
                                 "future_relative_bps": v * 1e4, "low": lo * 1e4, "high": hi * 1e4})
                if model == "Average6":
                    boot_slopes = []
                    for label in ["lower", "high"]:
                        v, lo, hi, boot = ratio_interval(g[f"{label}_cross_product"],
                                                       g[f"{label}_signal_squared"], indices)
                        boot_slopes.append(boot)
                        stability.append({"period": period, "horizon": horizon, "stability_group": label,
                                          "response_slope": v, "low": lo, "high": hi,
                                          "stock_events": int(g[f"{label}_count"].sum()),
                                          "signal_dates": int((g[f"{label}_count"] > 0).sum())})
                    diff = boot_slopes[1] - boot_slopes[0]
                    hi_row, lo_row = stability[-1], stability[-2]
                    low, high = np.nanquantile(diff, [.025, .975])
                    stability.append({"period": period, "horizon": horizon,
                                      "stability_group": "high_minus_lower", "response_slope": hi_row["response_slope"] - lo_row["response_slope"],
                                      "low": float(low), "high": float(high),
                                      "stock_events": int(g.active_stocks.sum()), "signal_dates": len(g)})
    return pd.DataFrame(rows), pd.DataFrame(bins), pd.DataFrame(stability)


def plots(summary, bins, stability):
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 3, figsize=(15, 9), layout="constrained")
    for row, period in enumerate(PERIODS):
        for col, horizon in enumerate(HORIZONS):
            ax = axes[row, col]
            for model in MODELS:
                f = bins.loc[bins.period.eq(period) & bins.horizon.eq(horizon) & bins.model.eq(model)].sort_values("bin")
                ax.errorbar(f.mean_signal_z, f.future_relative_bps,
                            yerr=[f.future_relative_bps - f.low, f.high - f.future_relative_bps],
                            fmt="o-", ms=4, capsize=2, lw=1.3, color=COLORS[model], label=NAMES[model])
            ax.axhline(0, color="black", lw=.7); ax.axvline(0, color="black", lw=.7)
            ax.set_title(f"{period.title()} | {horizon}-session response")
            ax.set_xlabel("Signal residual / prior daily sigma")
            ax.set_ylabel("Future factor-relative return (bps)")
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Residual response: reversal slopes down; continuation slopes up\nNext-bar open entry; formation exposures frozen; pointwise 95% date-block intervals")
    fig.savefig(OUT / "01_residual_response_bins.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), layout="constrained")
    for row, period in enumerate(PERIODS):
        for j, model in enumerate(MODELS):
            f = summary.loc[summary.period.eq(period) & summary.model.eq(model)].sort_values("horizon")
            positions = np.arange(3) + (j - 1) * .15
            for col, value, lower, upper in [(0, "response_slope", "slope_low", "slope_high"),
                                             (1, "mean_gross_event_bps", "gross_low", "gross_high")]:
                axes[row, col].errorbar(positions, f[value], yerr=[f[value] - f[lower], f[upper] - f[value]],
                                       fmt="o", capsize=3, color=COLORS[model], label=NAMES[model])
        for col in range(2):
            axes[row, col].axhline(0, color="black", lw=.8)
            axes[row, col].set_xticks(np.arange(3), HORIZONS)
            axes[row, col].set_xlabel("Holding sessions (including entry session)")
            axes[row, col].set_title(period.title())
        axes[row, 0].set_ylabel("Normalized response slope\nnegative = reversal")
        axes[row, 1].set_ylabel("Mean gross return per event (bps)\npositive = contrarian position earns")
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("All declared models and horizons | approximate pointwise 95% intervals\nOverlapping events are not compounded or annualized")
    fig.savefig(OUT / "02_slopes_and_gross_event_returns.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    for ax, period in zip(axes, PERIODS):
        for j, (label, color) in enumerate([("lower", "#bc6c25"), ("high", "#2a9d8f")]):
            f = stability.loc[stability.period.eq(period) & stability.stability_group.eq(label)].sort_values("horizon")
            ax.errorbar(np.arange(3) + (j - .5) * .12, f.response_slope,
                        yerr=[f.response_slope - f.low, f.high - f.response_slope], fmt="o", capsize=4,
                        color=color, label=f"{label.title()} peer stability")
        ax.axhline(0, color="black", lw=.7)
        ax.set_xticks(np.arange(3), HORIZONS); ax.set_xlabel("Holding sessions")
        ax.set_ylabel("Normalized response slope (negative = reversal)"); ax.set_title(period.title())
    axes[0].legend(fontsize=8)
    fig.suptitle("Do stable average-linkage peers show stronger reversal?\nPast-only mean peer-set Jaccard >= 0.75; descriptive subsets, no filtered portfolio")
    fig.savefig(OUT / "03_stability_and_reversal.png", dpi=160); plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "specification.json"
    if path.exists() and json.loads(path.read_text()) != CONFIG:
        raise ValueError("Existing specification differs; use a new experiment")
    # Persist the full design before inspecting any new outcome.
    path.write_text(json.dumps(CONFIG, indent=2) + "\n")
    checks = controls()
    protected = [ROOT / "experiments/equity_residual_backtest.py",
                 ROOT / "experiments/equity_h0_peers.py",
                 ROOT / "experiments/equity_h0_scale_robustness.py",
                 ROOT / "experiments/equity_residual_backtest/evaluated/summary.json",
                 DATA / "returns_log.csv", DATA / "bars_all.csv", DATA / "bars_raw.csv"]
    before = {str(p.relative_to(ROOT)): digest(p) for p in protected}
    symbols, panel, raw_open, raw_close = load_data(False)
    bars = pd.read_csv(DATA / "bars_all.csv", parse_dates=["date"])
    opening = bars.pivot(index="date", columns="symbol", values="o").reindex(index=panel.index, columns=symbols).to_numpy()
    closing = bars.pivot(index="date", columns="symbol", values="c").reindex(index=panel.index, columns=symbols).to_numpy()
    assert np.isfinite(opening).all() and np.isfinite(closing).all() and (opening > 0).all() and (closing > 0).all()
    raw_return = (raw_close / raw_open - 1).to_numpy()
    universe = pd.read_csv(DATA / "universe.csv").set_index("symbol").loc[symbols]
    group_names = list(dict.fromkeys(universe.research_group))
    manual = np.array([group_names.index(g) for g in universe.research_group])
    x, market = panel[symbols].to_numpy(), panel.SPY.to_numpy()
    daily, stock_rows, date_rows = [], [], []
    sufficient = {(p, m, h, b): [] for p in PERIODS for m in MODELS for h in HORIZONS for b in range(8)}
    max_error, max_identity, max_raw_difference = 0., 0., 0.
    cache = {}
    def geom(end, length):
        key = (end, length)
        if key not in cache:
            cache[key] = geometry(x[end-length:end], market[end-length:end])
        return cache[key]
    for t in range(140, len(panel) - 20):
        entry, final = panel.index[t+1], panel.index[t+20]
        if (entry < pd.Timestamp("2024-01-01")) != (final < pd.Timestamp("2024-01-01")):
            continue
        period = "development" if entry < pd.Timestamp("2024-01-01") else "evaluation"
        distance, _, residual_sigma, _, vec, fit = geom(t, 120)
        labels = average_labels(distance)
        altered = [average_labels(geom(t, 100)[0]), average_labels(geom(t, 140)[0]),
                   average_labels(geom(t-5, 120)[0])]
        stability = peer_stability(labels, altered)
        sigma = np.maximum(x[t-120:t].std(axis=0, ddof=1), .0001)
        weights = 1 / sigma ** 2
        matrices = {"Manual6": group_exposures(manual, fit[1]),
                    "Average6": group_exposures(labels, fit[1]),
                    "PCA5": np.column_stack([np.ones(30), fit[1], residual_sigma[:, None] * vec[:, :5]])}
        assert panel.index[t-1] < panel.index[t] < entry <= final
        date_rows.append({"signal_date": panel.index[t], "training_start": panel.index[t-120],
                          "training_end": panel.index[t-1], "entry": entry, "last_exit": final, "period": period})
        for model, exposure in matrices.items():
            assert np.linalg.matrix_rank(exposure) == 7
            holdings, residual, error, _ = construct(x[t], exposure, weights)
            max_error = max(max_error, error)
            z = residual / sigma
            active = abs(z) > 1e-10
            bin_index = np.digitize(z, BINS[1:-1])
            signal_denom = np.sum(z ** 2)
            for horizon in HORIZONS:
                future = closing[t+horizon] / opening[t+1] - 1
                relative = project(future, exposure, weights)
                y = relative / sigma
                gross = float(holdings @ future)
                max_identity = max(max_identity, abs(gross - holdings @ relative))
                assert np.allclose(gross, -(z @ y) / np.abs(weights * residual).sum(), atol=1e-10)
                row = {"signal_date": panel.index[t], "entry": entry, "exit": panel.index[t+horizon],
                       "period": period, "model": model, "horizon": horizon,
                       "gross_return": gross, "cross_product": float(z @ y),
                       "signal_squared": float(signal_denom), "active_stocks": int(active.sum()),
                       "max_abs_initial_position": float(abs(holdings).max()), "initial_exposure_error": error}
                if horizon == 1:
                    row["raw_bar_gross_control"] = float(holdings @ raw_return[t+1])
                    max_raw_difference = max(max_raw_difference, abs(gross - row["raw_bar_gross_control"]))
                for b in range(8):
                    select = active & (bin_index == b)
                    sufficient[(period, model, horizon, b)].append([float(relative[select].sum()),
                                                                  int(select.sum()), float(z[select].sum())])
                if model == "Average6":
                    for label, select in [("high", active & (stability >= .75)), ("lower", active & (stability < .75))]:
                        row[f"{label}_cross_product"] = float(z[select] @ y[select])
                        row[f"{label}_signal_squared"] = float(np.sum(z[select] ** 2))
                        row[f"{label}_count"] = int(select.sum())
                daily.append(row)
                stock_rows.extend({"signal_date": panel.index[t], "period": period, "model": model,
                                   "horizon": horizon, "symbol": symbol, "signal_z": float(z[j]),
                                   "signal_residual": float(residual[j]), "prior_total_sigma": float(sigma[j]),
                                   "future_relative_return": float(relative[j]), "future_simple_return": float(future[j]),
                                   "initial_dollars": float(holdings[j]), "signal_bin": int(bin_index[j]),
                                   "active": bool(active[j]),
                                   "peer_stability": float(stability[j]) if model == "Average6" else None}
                                  for j, symbol in enumerate(symbols))
        # Bound cache size while retaining the shifted historical geometry.
        cache = {k: v for k, v in cache.items() if k[0] >= t-5}
        if len(date_rows) % 400 == 0:
            print(f"Computed {len(date_rows)} formation dates", flush=True)
    daily = pd.DataFrame(daily)
    daily.to_csv(OUT / "daily_event_statistics.csv", index=False)
    stock = pd.DataFrame(stock_rows)
    stock.to_csv(OUT / "stock_events.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    pd.DataFrame(date_rows).to_csv(OUT / "formation_dates.csv", index=False)
    sufficient = {k: np.array(v) for k, v in sufficient.items()}
    summary, bins, stability = estimate_tables(daily, sufficient)
    summary.to_csv(OUT / "response_summary.csv", index=False)
    bins.to_csv(OUT / "binned_response.csv", index=False)
    stability.to_csv(OUT / "stability_response.csv", index=False)
    plots(summary, bins, stability)
    # Compare the unchanged one-session raw-bar implementation to the earlier pilot.
    prior = pd.read_csv(ROOT / "experiments/equity_h0_peers/daily_gross_and_structure.csv", parse_dates=["signal_date"])
    comparison = daily.loc[daily.horizon.eq(1)].merge(prior[["signal_date", "model", "gross_return"]],
                                                    on=["signal_date", "model"], suffixes=("", "_pilot"))
    assert len(comparison) == len(date_rows) * 3
    pilot_error = float(abs(comparison.raw_bar_gross_control - comparison.gross_return_pilot).max())
    assert pilot_error < 1e-10
    checks.update(formation_inputs_precede_signal_and_entry=True,
                  same_dates_for_all_models_and_horizons=True,
                  full_twenty_session_targets_do_not_cross_split=True,
                  seven_independent_exposures_every_formation=True,
                  interval_resampling_keeps_all_stocks_together=True,
                  original_sources_and_data_unchanged=all(digest(p) == before[str(p.relative_to(ROOT))] for p in protected),
                  raw_one_session_reproduces_prior_pilot=True)
    audit = {"checks": checks, "max_initial_scaled_exposure_error": max_error,
             "max_pnl_projection_identity_error": max_identity,
             "max_raw_one_session_pilot_error": pilot_error,
             "max_adjusted_minus_raw_one_session_event_return": max_raw_difference,
             "protected_sha256": before,
             "source_sha256": digest(Path(__file__)),
             "formation_dates": len(date_rows), "stock_events": len(stock),
             "dates_by_period": pd.Series([r["period"] for r in date_rows]).value_counts().to_dict()}
    assert all(checks.values())
    (OUT / "implementation_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (OUT / "summary.json").write_text(json.dumps({"configuration": CONFIG,
        "response": json.loads(summary.to_json(orient="records")),
        "stability": json.loads(stability.to_json(orient="records")), "audit": audit}, indent=2) + "\n")
    print(summary.round(5).to_string(index=False), flush=True)
    print("STABILITY", stability.round(5).to_string(index=False), sep="\n", flush=True)


if __name__ == "__main__":
    main()
