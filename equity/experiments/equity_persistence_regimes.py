"""Past-only regime forecasts for a fixed daily equity residual strategy.

Compare ordinary state predictors with the same predictors plus three diagram
summaries. No forecast/threshold tuning, fees, downloads, or strategy changes.
"""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from ripser import ripser
from scipy.spatial.distance import pdist, squareform

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/"market_data/datasets/equity_daily_expanded_2016_2026-10-27"
BASE = ROOT/"experiments/equity_expanded_pca_reversal"
OUT = ROOT/"experiments/equity_persistence_regimes"
BASIC = ["SPY_vol20", "residual_mean_corr", "residual_pc1_share", "residual_pc3_share",
         "factor_lag1_acf_mean", "factor_dominant_power_share_mean", "strategy_trailing20_bps",
         "strategy_stock_count", "lag_cloud_median_distance", "loading_cloud_median_distance"]
STOCK = ["stock_H0_q90", "stock_H1_max_lifetime", "stock_H1_total_squared_lifetime"]
LAG = ["lag_H0_q90", "lag_H1_max_lifetime", "lag_H1_total_squared_lifetime"]
MODELS = {"HistoryMean": [], "Simple": BASIC, "SimplePlusStockPD": BASIC+STOCK, "SimplePlusLagPD": BASIC+LAG}
GATES = ["AlwaysOn", *MODELS]
PERIODS = ["development", "later"]
CONFIG = {
    "decision_date": "2026-10-29", "status": "exploratory on already examined dates and current-survivor universe",
    "fixed_strategy": "expanded200, 120-session SPY_PCA3, raw next-bar open to close, unit gross, flat nightly, pre-fee",
    "strategy_source": str(BASE.name), "recompute_strategy": False,
    "reference_stocks": "freeze names with 272 complete prior returns at first formation; no later additions or future-completeness filter",
    "first_formation_index": 272, "feature_fit_sessions": 120, "forecast_stride_sessions": 5,
    "decision_time": "after anchor close t; feature histories end t-1; trailing strategy outcomes and completed training labels may end t",
    "forecast_target": "mean gross bps/day of next twenty actual daily strategy trades, not twenty-day frozen initial positions",
    "target_sessions": 20, "gate_holding_sessions": 5,
    "latest_partial_targets": "predict and trade available days without scoring incomplete twenty-session labels",
    "history_object": "fit SPY residuals on fixed reference stocks; standardize each stock, retain top three residual PCs",
    "lag_object": "119 points (whitened factor scores at s, scores at s-1)/sqrt(2), six coordinates",
    "stock_object": "fixed reference-stock points in top-three eigenvalue-weighted correlation loading coordinates",
    "scaling": "each cloud's pair distances divided by its own positive median; both raw median distances included in all simple models",
    "persistence": "complete Vietoris-Rips H0/H1 with ripser; infinite H0 excluded from finite summaries, separately counted",
    "basic_features": BASIC, "stock_features": STOCK, "lag_features": LAG,
    "minimum_completed_training_labels": 104,
    "training": "expanding prior anchors only; training target end <= decision date; no own/future label; no validation-selected settings",
    "ridge": "unpenalized intercept; training-only mean/std; objective average squared bps error + 1*sum(beta^2); fixed lambda=1, equivalent sklearn alpha=n",
    "forecast_models": list(MODELS), "gate_rule": "predicted next20 daily mean > 0 => unit-gross original daily strategy for next five sessions, else flat",
    "calendar": "all eligible post-warmup trading days, flat days recorded as zero; five-session allocations do not overlap",
    "mean_baseline": "HistoryMean uses completed historical target mean; AlwaysOn supplies raw strategy and shares its forecast diagnostic with HistoryMean",
    "period_split": "entry before 2024-01-01 development, otherwise later; forecast labels crossing boundary excluded only from period forecast scoring",
    "online_later_training": "completed later labels enter expanding training as time passes; not a fixed 2023-trained model or untouched holdout",
    "uncertainty": "1000 circular block resamples, 60 daily executions for P&L and 12 five-session forecast anchors for loss; conditional on saved causal forecasts, not a model-refit bootstrap",
    "primary_comparisons": "each PD augmentation minus Simple, paired; approximate simultaneous 95% bands across two augmentations per period, separately for forecast loss and gate mean",
    "secondary": "all model metrics, sign calibration, active fraction, and pointwise intervals; no winning state, threshold or feature selected",
    "controls": "first prior-history window only: common row shuffle, time reversal, uniform return scaling; target outcomes not involved",
    "fees": "excluded entirely", "seed": 2026102931,
}
COLORS = {"AlwaysOn": "#6c757d", "HistoryMean": "#9467bd", "Simple": "#277da1", "SimplePlusStockPD": "#e58a20", "SimplePlusLagPD": "#43aa8b"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diagram_features(points, prefix):
    condensed = pdist(points)
    scale = float(np.median(condensed))
    if scale <= 1e-12: raise ValueError("Degenerate cloud scale")
    distance = squareform(condensed/scale)
    diagrams = ripser(distance, distance_matrix=True, maxdim=1)["dgms"]
    h0 = diagrams[0][np.isfinite(diagrams[0][:, 1])]
    h1 = diagrams[1][np.isfinite(diagrams[1][:, 1])]
    lifetime = h1[:, 1]-h1[:, 0]
    return {f"{prefix}_H0_q90": float(np.quantile(h0[:, 1]-h0[:, 0], .9)),
            f"{prefix}_H1_max_lifetime": float(lifetime.max()) if len(lifetime) else 0.,
            f"{prefix}_H1_total_squared_lifetime": float(lifetime@lifetime)}, scale, diagrams


def geometry_features(history, market):
    length = len(history)
    design = np.c_[np.ones(length), market]
    residual = history-design@np.linalg.lstsq(design, history, rcond=None)[0]
    sigma = residual.std(axis=0, ddof=1)
    assert (sigma > 1e-10).all()
    z = (residual-residual.mean(axis=0))/sigma
    _, singular, vt = np.linalg.svd(z, full_matrices=False)
    eigenvalues = singular**2/(length-1)
    v3 = vt[:3].T
    scores = z@v3/np.sqrt(eigenvalues[:3])
    lag_points = np.c_[scores[1:], scores[:-1]]/np.sqrt(2)
    loading_points = v3*np.sqrt(eigenvalues[:3])
    lag, lag_scale, lag_dgm = diagram_features(lag_points, "lag")
    stock, stock_scale, stock_dgm = diagram_features(loading_points, "stock")
    power = abs(np.fft.rfft(scores-scores.mean(axis=0), axis=0)[1:])**2
    corr = z.T@z/(length-1)
    features = {"residual_mean_corr": float(corr[np.triu_indices(len(sigma), 1)].mean()),
        "residual_pc1_share": float(eigenvalues[0]/eigenvalues.sum()),
        "residual_pc3_share": float(eigenvalues[:3].sum()/eigenvalues.sum()),
        "factor_lag1_acf_mean": float(np.mean([np.corrcoef(scores[1:, k], scores[:-1, k])[0, 1] for k in range(3)])),
        "factor_dominant_power_share_mean": float(np.mean(power.max(axis=0)/power.sum(axis=0))),
        "lag_cloud_median_distance": lag_scale, "loading_cloud_median_distance": stock_scale,
        **lag, **stock}
    return features, {"lag": lag_dgm, "stock": stock_dgm}


def controls(history, market):
    base, _ = geometry_features(history, market)
    rng = np.random.default_rng(997)
    perm = rng.permutation(len(history))
    changed = {"original": base,
        "joint_rows_shuffled": geometry_features(history[perm], market[perm])[0],
        "time_reversed": geometry_features(history[::-1], market[::-1])[0],
        "returns_times_three": geometry_features(history*3, market*3)[0]}
    for key in STOCK+LAG:
        assert np.isclose(base[key], changed["returns_times_three"][key], atol=2e-5)
        assert np.isclose(base[key], changed["time_reversed"][key], atol=2e-5)
    for key in STOCK+["residual_mean_corr", "residual_pc1_share", "residual_pc3_share"]:
        assert np.isclose(base[key], changed["joint_rows_shuffled"][key], atol=2e-5)
    assert any(abs(base[key]-changed["joint_rows_shuffled"][key]) > 1e-4 for key in LAG)
    return pd.DataFrame([{"control": name, **f} for name, f in changed.items()]), {
        "stock_diagram_invariant_to_common_time_shuffle": True,
        "lag_diagram_responds_to_altered_transition_order": True,
        "both_diagrams_invariant_to_uniform_return_scaling": True,
        "lag_diagram_does_not_distinguish_time_reversal": True}


def ridge(train_x, train_y, current):
    mean = train_x.mean(axis=0)
    scale = train_x.std(axis=0, ddof=0)
    scale = np.where(scale > 1e-10, scale, 1.)
    z = (train_x-mean)/scale
    intercept = float(train_y.mean())
    beta = np.linalg.solve(z.T@z+len(train_y)*np.eye(z.shape[1]), z.T@(train_y-intercept))
    return float(intercept+(current-mean)/scale@beta), mean, scale, beta, intercept


def block_indices(n, block, seed):
    rng = np.random.default_rng(seed)
    starts = rng.integers(n, size=(1000, int(np.ceil(n/block))))
    return ((starts[:, :, None]+np.arange(block)) % n).reshape(1000, -1)[:, :n]


def comparison_bands(values, indices):
    center = values.mean(axis=0)
    boot = values[indices].mean(axis=1)
    low, high = np.quantile(boot, [.025, .975], axis=0)
    se = boot.std(axis=0, ddof=1)
    standardized = np.divide(boot-center, se, out=np.zeros_like(boot), where=se > 1e-12)
    radius = float(np.quantile(abs(standardized).max(axis=1), .95))
    return center, low, high, center-radius*se, center+radius*se


def summarize(predictions, pnl):
    forecast_rows, performance_rows, comparisons, calibration = [], [], [], []
    augmentations = ["SimplePlusStockPD", "SimplePlusLagPD"]
    for pi, period in enumerate(PERIODS):
        f = predictions.loc[predictions.score_period.eq(period) & predictions.target_mean_bps.notna()].sort_values("formation_date")
        idx = block_indices(len(f), 12, CONFIG["seed"]+pi)
        y = f.target_mean_bps.to_numpy()
        reference_error = (f.HistoryMean.to_numpy()-y)**2
        simple_error = (f.Simple.to_numpy()-y)**2
        diffs = np.column_stack([(f[m].to_numpy()-y)**2-simple_error for m in augmentations])
        stats = comparison_bands(diffs, idx)
        for j, model in enumerate(augmentations):
            comparisons.append({"period": period, "comparison": model+"_minus_Simple", "metric": "forecast_MSE_bps_squared",
                "count": len(f), "difference": stats[0][j], "point95_low": stats[1][j], "point95_high": stats[2][j],
                "sim95_low": stats[3][j], "sim95_high": stats[4][j], "better_direction": "negative"})
        for model in MODELS:
            prediction = f[model].to_numpy(); error = (prediction-y)**2
            boot_error = error[idx].mean(axis=1)
            forecast_rows.append({"period": period, "model": model, "forecasts": len(f), "MSE_bps_squared": float(error.mean()),
                "MSE_low": float(np.quantile(boot_error, .025)), "MSE_high": float(np.quantile(boot_error, .975)),
                "MAE_bps": float(abs(prediction-y).mean()), "MSE_skill_vs_HistoryMean": float(1-error.mean()/reference_error.mean()),
                "mean_forecast_bps": float(prediction.mean()), "mean_target_bps": float(y.mean())})
            for label, mask in [("positive", prediction > 0), ("nonpositive", prediction <= 0)]:
                counts = mask[idx].sum(axis=1)
                numerator = (mask*y)[idx].sum(axis=1)
                boot_mean = np.divide(numerator, counts, out=np.full(1000, np.nan), where=counts > 0)
                calibration.append({"period": period, "model": model, "forecast_sign": label, "forecasts": int(mask.sum()),
                    "mean_prediction_bps": float(prediction[mask].mean()) if mask.any() else None,
                    "mean_future_target_bps": float(y[mask].mean()) if mask.any() else None,
                    "target_low": float(np.nanquantile(boot_mean, .025)) if mask.any() else None,
                    "target_high": float(np.nanquantile(boot_mean, .975)) if mask.any() else None})
        p = pnl.loc[pnl.period.eq(period)].sort_values("date")
        idx = block_indices(len(p), 60, CONFIG["seed"]+50+pi)
        differences = np.column_stack([(p[m]-p.Simple).to_numpy()*1e4 for m in augmentations])
        stats = comparison_bands(differences, idx)
        for j, model in enumerate(augmentations):
            comparisons.append({"period": period, "comparison": model+"_minus_Simple", "metric": "gate_mean_bps_per_calendar_day",
                "count": len(p), "difference": stats[0][j], "point95_low": stats[1][j], "point95_high": stats[2][j],
                "sim95_low": stats[3][j], "sim95_high": stats[4][j], "better_direction": "positive"})
        for model in GATES:
            values = p[model].to_numpy(); equity = np.cumprod(1+values)
            boot = values[idx].mean(axis=1)*1e4
            std = values.std(ddof=1)
            performance_rows.append({"period": period, "model": model, "calendar_days": len(p),
                "active_fraction": 1. if model == "AlwaysOn" else float(p[model+"_active"].mean()),
                "mean_daily_bps": float(values.mean()*1e4), "mean_low": float(np.quantile(boot, .025)),
                "mean_high": float(np.quantile(boot, .975)), "annualized_volatility": float(std*np.sqrt(252)),
                "sharpe_vs_zero": float(values.mean()/std*np.sqrt(252)) if std > 0 else None,
                "gross_CAGR": float(equity[-1]**(252/len(values))-1), "total_gross_return": float(equity[-1]-1),
                "max_drawdown": float(np.min(equity/np.maximum.accumulate(np.r_[1., equity])[1:]-1))})
    return pd.DataFrame(forecast_rows), pd.DataFrame(performance_rows), pd.DataFrame(comparisons), pd.DataFrame(calibration)


def plots(features, predictions, pnl, forecast_summary, performance, comparisons):
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), layout="constrained")
    for ax, period in zip(axes, ["all", "later"]):
        f = pnl if period == "all" else pnl.loc[pnl.period.eq("later")]
        for model in GATES:
            equity = (1+f[model]).cumprod()
            ax.plot(pd.to_datetime(f.date), 100000*(equity-1), color=COLORS[model], label=model)
        ax.axhline(0, color="black", lw=.7)
        ax.set_ylabel("Simulated gross profit on $100,000")
        ax.set_title("Post-warmup matched calendar" if period == "all" else "Later period reset to $100,000")
    axes[0].legend(fontsize=8)
    fig.suptitle("Fixed daily strategy, gated every five sessions | flat days included | pre-fee")
    fig.savefig(OUT/"01_gross_gate_profit.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), layout="constrained")
    for row, metric in enumerate(["forecast_MSE_bps_squared", "gate_mean_bps_per_calendar_day"]):
        for col, period in enumerate(PERIODS):
            f = comparisons.loc[comparisons.metric.eq(metric) & comparisons.period.eq(period)]
            center = f.difference.to_numpy(); lo = f.sim95_low.to_numpy(); hi = f.sim95_high.to_numpy()
            axes[row, col].errorbar([0, 1], center, yerr=[center-lo, hi-center], fmt="o", capsize=5, color="#277da1")
            axes[row, col].axhline(0, color="black", lw=.7)
            axes[row, col].set_xticks([0, 1], ["+ stock-loading PD", "+ lag-state PD"])
            axes[row, col].set_title(period.title())
            axes[row, col].set_ylabel("Change in MSE (bps squared)\nnegative = better" if row == 0 else "Change in gross bps/calendar day\npositive = better")
    fig.suptitle("Does persistence add value beyond simple state predictors?\nPaired approximate 95% simultaneous bands across the two augmentations per period/metric")
    fig.savefig(OUT/"02_incremental_comparisons.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), layout="constrained")
    f = predictions.loc[predictions.score_period.eq("later") & predictions.target_mean_bps.notna()]
    dates = pd.to_datetime(f.formation_date)
    axes[0].plot(dates, f.target_mean_bps, color="black", lw=1.2, label="Realized next20 daily-strategy mean")
    for model in MODELS:
        axes[0].plot(dates, f[model], color=COLORS[model], lw=1, label=model)
    axes[0].axhline(0, color="black", lw=.7); axes[0].set_ylabel("Gross bps/day"); axes[0].legend(fontsize=8)
    for j, model in enumerate(MODELS):
        axes[1].step(pd.to_datetime(predictions.formation_date), (predictions[model]>0).astype(float)+j*1.4, where="post", color=COLORS[model], label=model)
    axes[1].set_yticks(np.arange(4)*1.4+.5, list(MODELS)); axes[1].set_ylabel("Gate off/on within each row")
    fig.suptitle("Causal five-session forecast updates | next20 target displayed afterward\nThe models are trained only on target windows completed by each decision")
    fig.savefig(OUT/"03_forecasts_and_gate_states.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout="constrained")
    labels = ["Always", "Mean gate", "Simple", "+ Stock PD", "+ Lag PD"]
    for ax, period in zip(axes, PERIODS):
        f = performance.loc[performance.period.eq(period)].set_index("model").loc[GATES]
        ax.errorbar(np.arange(5), f.mean_daily_bps, yerr=[f.mean_daily_bps-f.mean_low, f.mean_high-f.mean_daily_bps], fmt="o", capsize=4)
        ax.axhline(0, color="black", lw=.7); ax.set_xticks(np.arange(5), labels)
        ax.set_title(period.title()); ax.set_ylabel("Mean gross bps per calendar day")
    fig.suptitle("Calendar returns including flat days | approximate pointwise 95% date-block intervals")
    fig.savefig(OUT/"04_calendar_mean_returns.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(3, 1, figsize=(13, 8), layout="constrained")
    for ax, suffix in zip(axes, ["H0_q90", "H1_max_lifetime", "H1_total_squared_lifetime"]):
        for prefix, color in [("stock", "#e58a20"), ("lag", "#43aa8b")]:
            ax.plot(pd.to_datetime(features.formation_date), features[prefix+"_"+suffix], color=color, label=prefix)
        ax.set_ylabel(suffix); ax.legend(fontsize=8)
    fig.suptitle("Past-only diagram features | normalized distances, fixed point counts\nThe two objects have different geometry; raw feature magnitudes are not a quality ranking")
    fig.savefig(OUT/"05_persistence_features.png", dpi=160); plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    spec = OUT/"specification.json"
    if spec.exists() and json.loads(spec.read_text()) != CONFIG: raise ValueError("Existing specification differs")
    spec.write_text(json.dumps(CONFIG, indent=2)+"\n")
    protected_paths = [DATA/"returns_log.csv", DATA/"universe.csv", BASE/"daily_gross_returns.csv", BASE/"summary.json",
        ROOT/"experiments/equity_expanded_pca_reversal.py", ROOT/"experiments/equity_expanded_structure/summary.json"]
    protected = {str(p.relative_to(ROOT)): sha(p) for p in protected_paths}
    panel = pd.read_csv(DATA/"returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    universe = pd.read_csv(DATA/"universe.csv").query("role == 'equity'")
    symbols = universe.symbol.tolist(); x = panel[symbols].to_numpy(); market = panel.SPY.to_numpy()
    reference_idx = np.flatnonzero(np.isfinite(x[0:272]).all(axis=0))
    reference_names = np.array(symbols)[reference_idx].tolist()
    assert len(reference_names) >= 100
    pd.DataFrame({"symbol": reference_names, "selection": "complete first 272 observed returns at initial formation"}).to_csv(OUT/"reference_stocks.csv", index=False)
    source = pd.read_csv(BASE/"daily_gross_returns.csv", parse_dates=["signal_date", "date"])
    strategy = source.loc[source.universe.eq("expanded200") & source.window.eq(120) & source.model.eq("SPY_PCA3")].set_index("date").sort_index()
    assert strategy.index.is_unique
    assert strategy.index.equals(panel.index[273:])
    control_table, checks = controls(x[272-120:272, reference_idx], market[272-120:272])
    control_table.to_csv(OUT/"representation_controls.csv", index=False)
    features, intervals = [], []
    for anchor, t in enumerate(range(272, len(panel)-1, 5)):
        history = x[t-120:t, reference_idx]
        assert np.isfinite(history).all()
        values, diagrams = geometry_features(history, market[t-120:t])
        trailing = strategy.loc[:panel.index[t]].tail(20).gross_return
        # The earliest feature anchors predate twenty strategy trades; this is
        # an honest unavailable predictor and those anchors are not fit inputs.
        past_strategy = float(trailing.mean()*1e4) if len(trailing) == 20 else np.nan
        available = np.isfinite(x[t-272:t]).all(axis=0).sum()
        target_end = panel.index[t+20] if t+20 < len(panel) else pd.NaT
        target = float(strategy.loc[panel.index[t+1]:target_end].gross_return.mean()*1e4) if pd.notna(target_end) else np.nan
        start = panel.index[t+1]
        crosses = pd.notna(target_end) and (start < pd.Timestamp("2024-01-01")) != (target_end < pd.Timestamp("2024-01-01"))
        features.append({"anchor": anchor, "signal_index": t, "formation_date": panel.index[t], "history_end": panel.index[t-1],
            "target_start": start, "target_end": target_end, "target_mean_bps": target,
            "score_period": "boundary" if crosses else "development" if start < pd.Timestamp("2024-01-01") else "later",
            "SPY_vol20": float(market[t-20:t].std(ddof=1)*np.sqrt(252)), "strategy_trailing20_bps": past_strategy,
            "strategy_stock_count": int(available), "reference_stocks": len(reference_names), "lag_points": 119, **values})
        for obj, dgms in diagrams.items():
            for dimension, dgm in enumerate(dgms):
                for birth, death in dgm:
                    intervals.append({"anchor": anchor, "object": obj, "dimension": dimension, "birth": float(birth),
                                      "death": float(death) if np.isfinite(death) else None})
        if (anchor+1) % 100 == 0: print(f"Computed {anchor+1} state anchors", flush=True)
    features = pd.DataFrame(features)
    features.to_csv(OUT/"state_features_and_targets.csv", index=False)
    pd.DataFrame(intervals).to_csv(OUT/"persistence_intervals.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    # Predict only after enough labels are complete. No outcome at this anchor
    # or a later date is passed to fitting, scaling, or gating.
    predictions, train_rows, coefficient_rows = [], [], []
    complete_features = np.isfinite(features[BASIC+STOCK+LAG].to_numpy()).all(axis=1)
    for i, row in features.iterrows():
        if not complete_features[i]: continue
        train_mask = (features.formation_date < row.formation_date) & features.target_end.le(row.formation_date) & features.target_mean_bps.notna() & complete_features
        train = features.loc[train_mask]
        if len(train) < 104: continue
        record = {k: row[k] for k in ["anchor", "signal_index", "formation_date", "target_start", "target_end", "target_mean_bps", "score_period"]}
        record.update(training_labels=len(train), latest_training_target_end=train.target_end.max())
        assert record["latest_training_target_end"] <= row.formation_date
        y = train.target_mean_bps.to_numpy()
        for model, columns in MODELS.items():
            if not columns:
                record[model] = float(y.mean())
                continue
            pred, mean, scale, beta, intercept = ridge(train[columns].to_numpy(), y, row[columns].to_numpy(dtype=float))
            record[model] = pred
            coefficient_rows.extend({"anchor": int(row.anchor), "model": model, "feature": key,
                "training_mean": float(mu), "training_scale": float(sd), "coefficient_standardized": float(b), "intercept_bps": intercept}
                for key, mu, sd, b in zip(columns, mean, scale, beta))
        predictions.append(record)
        train_rows.extend({"prediction_anchor": int(row.anchor), "training_anchor": int(a)} for a in train.anchor)
    predictions = pd.DataFrame(predictions)
    assert len(predictions) > 0
    pnl_rows = []
    for prediction in predictions.itertuples():
        t = prediction.signal_index
        for execution_index in range(t+1, min(t+6, len(panel))):
            execution_date = panel.index[execution_index]
            raw = float(strategy.loc[execution_date, "gross_return"])
            record = {"date": execution_date, "prediction_anchor": prediction.anchor, "formation_date": prediction.formation_date,
                "period": "development" if execution_date < pd.Timestamp("2024-01-01") else "later", "AlwaysOn": raw}
            for model in MODELS:
                active = getattr(prediction, model) > 0
                record[model] = raw if active else 0.
                record[model+"_active"] = active
            pnl_rows.append(record)
    pnl = pd.DataFrame(pnl_rows)
    assert pnl.date.is_unique
    expected_dates = strategy.loc[pnl.date.min():pnl.date.max()].index
    assert pd.DatetimeIndex(pnl.date).equals(expected_dates)
    predictions.to_csv(OUT/"walk_forward_predictions.csv", index=False)
    pd.DataFrame(train_rows).to_csv(OUT/"training_membership.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    pd.DataFrame(coefficient_rows).to_csv(OUT/"coefficient_history.csv", index=False)
    pnl.to_csv(OUT/"daily_gate_returns.csv", index=False)
    forecast_summary, performance, comparisons, calibration = summarize(predictions, pnl)
    for name, frame in [("forecast_metrics", forecast_summary), ("gate_performance", performance), ("paired_incremental_comparisons", comparisons), ("sign_calibration", calibration)]:
        frame.to_csv(OUT/f"{name}.csv", index=False)
    plots(features, predictions, pnl, forecast_summary, performance, comparisons)
    checks.update(fixed_reference_membership_formed_from_initial_past_only=True,
        forecast_training_uses_only_completed_prior_labels=True, transforms_fit_on_training_only=True,
        five_session_allocations_nonoverlapping_and_all_calendar_days_recorded=True,
        incomplete_latest_targets_not_used_for_training_or_forecast_scores=True,
        original_strategy_and_protected_artifacts_unchanged=all(sha(p)==protected[str(p.relative_to(ROOT))] for p in protected_paths))
    assert all(checks.values())
    summary = {"configuration": CONFIG, "checks": checks, "reference_stock_count": len(reference_names),
        "feature_anchors": len(features), "predictions": len(predictions), "first_prediction": str(predictions.formation_date.min().date()),
        "last_prediction": str(predictions.formation_date.max().date()),
        "forecast_scores_by_period": predictions.loc[predictions.target_mean_bps.notna()].groupby("score_period").size().to_dict(),
        "calendar_days_by_period": pnl.groupby("period").size().to_dict(),
        "protected_sha256": protected, "source_sha256": sha(Path(__file__))}
    (OUT/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print("SUMMARY", {k: summary[k] for k in ["reference_stock_count", "feature_anchors", "predictions", "first_prediction", "forecast_scores_by_period", "calendar_days_by_period"]})
    print("FORECAST\n", forecast_summary.round(5).to_string(index=False))
    print("GATES\n", performance.round(5).to_string(index=False))
    print("INCREMENTAL\n", comparisons.round(5).to_string(index=False))


if __name__ == "__main__":
    main()
