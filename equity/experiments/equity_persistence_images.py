"""Bounded stock-diagram vectorization comparison; no portfolio or gate changes.

The specification is written before new forecasts. Saved normalized diagrams are
reused. Grid calibration uses only the first forecast's completed training set.
"""
from pathlib import Path
import hashlib
import importlib.util
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.special import ndtr
from scipy.spatial.distance import pdist

ROOT = Path(__file__).resolve().parents[1]
PREV = ROOT/"experiments/equity_persistence_regimes"
OUT = ROOT/"experiments/equity_persistence_images"
DATA = ROOT/"market_data/datasets/equity_daily_expanded_2016_2026-10-27"
spec = importlib.util.spec_from_file_location("previous_regimes", ROOT/"experiments/equity_persistence_regimes.py")
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
BASIC, SUMMARY = previous.BASIC, previous.STOCK
H0 = [f"H0_bin_{k}" for k in range(4)]
H1 = [f"H1_birth{i}_persistence{j}" for i in range(4) for j in range(4)]
QUANTILES = np.arange(.05, 1., .1)
ORDINARY = [f"loading_distance_q{k:02}" for k in range(10)]+[f"residual_correlation_q{k:02}" for k in range(10)]
MODELS = {"HistoryMean": [], "Simple": BASIC, "SimplePlusStockPD": BASIC+SUMMARY,
          "Ordinary20": BASIC+ORDINARY, "PersistenceImage20": BASIC+H0+H1}
COMPARATORS = ["Simple", "SimplePlusStockPD", "Ordinary20"]
CONFIG = {
    "decision_date": "2026-10-29", "status": "exploratory follow-up on already examined history, current-survivor universe",
    "hypothesis": "diagram birth/lifetime distributions contain useful information discarded by the three existing scalar summaries",
    "fixed_strategy_and_gate": "reuse previous expanded200 SPY_PCA3 120-session daily raw open-close gross returns; next20 mean target, positive forecast activates next5 daily trades",
    "point_object": "stock loading cloud only; same fixed 182 reference names, prior120 standardized SPY residuals, three eigenvalue-weighted PCA coordinates, median-normalized pair distances",
    "H0": "four finite merge-distance frequency bins; upper internal edges at .25,.5,.75 times 1.25 times initial calibration maximum death; fourth bin includes overflow; essential interval excluded",
    "H1": "4x4 birth-persistence image, lifetime weights, separable Gaussian integrated exactly per pixel; finite grid retains raw weighted mass without renormalization",
    "grid_calibration": "first prediction's completed valid training anchors only, selected by date not outcomes; upper birth and lifetime = 1.25 times respective calibration maxima; frozen thereafter",
    "kernel_sigma": "half a pixel width on each axis; no outcome-based selection",
    "out_of_grid": "no clipping or grid expansion for H1; report point counts and fraction of lifetime-weighted Gaussian mass retained, including ordinary boundary truncation",
    "ordinary_control": "20 new coordinates: ten 5th,15th,...95th quantiles each of normalized truncated-loading pair distances and full residual correlations, from the same prior120 reference-stock returns",
    "models": MODELS, "minimum_training_labels": 104,
    "training": "identical expanding completed-label memberships and train-only standardization as original; fixed ridge mean-square objective penalty lambda=1; no feature selection",
    "threshold": 0., "forecast_stride_sessions": 5, "target_sessions": 20, "gate_sessions": 5,
    "periods": "entry before 2024 development, 2024 onward later; boundary targets omitted from forecast scoring, never from daily gate P&L",
    "primary_comparisons": "PersistenceImage20 minus Simple, three-summary model, and Ordinary20; simultaneous bands across these three comparisons within each period and metric",
    "uncertainty": "1000 circular block resamples, 12 forecast anchors for MSE and 60 calendar days for P&L; conditional on causal saved forecasts, not refit bootstrap",
    "other_diagnostics": "baseline forecasts reconcile original; image range coverage; representation tests; all return means and secondary model statistics",
    "fees": "all excluded; gross/pre-fee only", "seed": 2026102941,
    "selection": "one fixed image resolution/bandwidth, no lag-image variant or outcome-based parameter search",
    "reference": "Adams et al. 2017 https://www.jmlr.org/papers/volume18/16-337/16-337.pdf",
}
COLORS = {"AlwaysOn": "#777777", "HistoryMean": "#aa88aa", "Simple": "#277da1",
          "SimplePlusStockPD": "#e58a20", "Ordinary20": "#7b2cbf", "PersistenceImage20": "#228b64"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vectorize(h0, h1, grid):
    edges = np.r_[0., np.arange(1, 4)*grid["H0_upper"]/4, np.inf]
    frequencies = np.histogram(h0[:, 1], edges)[0]/len(h0)
    birth_edges = np.linspace(0, grid["birth_upper"], 5)
    life_edges = np.linspace(0, grid["lifetime_upper"], 5)
    lifetime = h1[:, 1]-h1[:, 0]
    bx = np.diff(ndtr((birth_edges[None, :]-h1[:, 0, None])/grid["birth_sigma"]), axis=1)
    py = np.diff(ndtr((life_edges[None, :]-lifetime[:, None])/grid["lifetime_sigma"]), axis=1)
    image = np.einsum("n,ni,nj->ij", lifetime, bx, py)
    outside = (h1[:, 0] > grid["birth_upper"]) | (lifetime > grid["lifetime_upper"])
    total_weight = float(lifetime.sum())
    diagnostic = {"H1_points": len(h1), "H1_points_outside_grid": int(outside.sum()),
        "H1_total_lifetime": total_weight, "H1_image_mass": float(image.sum()),
        "H1_mass_retained_fraction": float(image.sum()/total_weight) if total_weight else 1.,
        "H0_upper_overflows": int((h0[:, 1] > grid["H0_upper"]).sum())}
    return np.r_[frequencies, image.ravel()], diagnostic


def ordinary_features(panel, reference, t):
    h = panel[reference].iloc[t-120:t].to_numpy()
    m = panel.SPY.iloc[t-120:t].to_numpy()
    design = np.c_[np.ones(len(h)), m]
    residual = h-design@np.linalg.lstsq(design, h, rcond=None)[0]
    z = (residual-residual.mean(axis=0))/residual.std(axis=0, ddof=1)
    _, singular, vt = np.linalg.svd(z, full_matrices=False)
    loading = vt[:3].T*(singular[:3]/np.sqrt(len(h)-1))
    distances = pdist(loading)
    correlations = (z.T@z/(len(h)-1))[np.triu_indices(len(reference), 1)]
    return np.r_[np.quantile(distances/np.median(distances), QUANTILES), np.quantile(correlations, QUANTILES)]


def summarize(predictions, pnl):
    metrics, performance, comparisons = [], [], []
    for pi, period in enumerate(["development", "later"]):
        f = predictions.loc[predictions.score_period.eq(period) & predictions.target_mean_bps.notna()].sort_values("formation_date")
        idx = previous.block_indices(len(f), 12, CONFIG["seed"]+pi)
        y = f.target_mean_bps.to_numpy()
        image_error = (f.PersistenceImage20.to_numpy()-y)**2
        differences = np.column_stack([image_error-(f[c].to_numpy()-y)**2 for c in COMPARATORS])
        stats = previous.comparison_bands(differences, idx)
        for j, comparator in enumerate(COMPARATORS):
            comparisons.append({"period": period, "comparator": comparator, "metric": "forecast_MSE_bps_squared", "count": len(f),
                "difference": stats[0][j], "point95_low": stats[1][j], "point95_high": stats[2][j],
                "sim95_low": stats[3][j], "sim95_high": stats[4][j], "better_direction": "negative"})
        for model in MODELS:
            error = (f[model].to_numpy()-y)**2
            boot = error[idx].mean(axis=1)
            metrics.append({"period": period, "model": model, "forecasts": len(f),
                "MSE_bps_squared": float(error.mean()), "MSE_low": float(np.quantile(boot, .025)),
                "MSE_high": float(np.quantile(boot, .975)), "MAE_bps": float(abs(f[model].to_numpy()-y).mean())})
        p = pnl.loc[pnl.period.eq(period)].sort_values("date")
        idx = previous.block_indices(len(p), 60, CONFIG["seed"]+50+pi)
        differences = np.column_stack([(p.PersistenceImage20-p[c]).to_numpy()*1e4 for c in COMPARATORS])
        stats = previous.comparison_bands(differences, idx)
        for j, comparator in enumerate(COMPARATORS):
            comparisons.append({"period": period, "comparator": comparator, "metric": "gate_mean_bps_per_calendar_day", "count": len(p),
                "difference": stats[0][j], "point95_low": stats[1][j], "point95_high": stats[2][j],
                "sim95_low": stats[3][j], "sim95_high": stats[4][j], "better_direction": "positive"})
        for model in ["AlwaysOn", *MODELS]:
            r = p[model].to_numpy(); equity = np.cumprod(1+r); std = r.std(ddof=1)
            boot = r[idx].mean(axis=1)*1e4
            performance.append({"period": period, "model": model, "calendar_days": len(p),
                "active_fraction": 1. if model == "AlwaysOn" else float(p[model+"_active"].mean()),
                "mean_daily_bps": float(r.mean()*1e4), "mean_low": float(np.quantile(boot, .025)), "mean_high": float(np.quantile(boot, .975)),
                "annualized_volatility": float(std*np.sqrt(252)), "sharpe_vs_zero": float(r.mean()/std*np.sqrt(252)) if std else 0.,
                "gross_CAGR": float(equity[-1]**(252/len(r))-1), "total_gross_return": float(equity[-1]-1),
                "max_drawdown": float((equity/np.maximum.accumulate(np.r_[1., equity])[1:]-1).min())})
    return pd.DataFrame(metrics), pd.DataFrame(performance), pd.DataFrame(comparisons)


def plots(features, pnl, intervals, grid, diagnostics, comparisons):
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    # Fixed first forecast's diagram illustrates the representation, not a selected profitable day.
    a = grid["first_prediction_anchor"]
    h1 = intervals.loc[intervals.anchor.eq(a) & intervals.dimension.eq(1), ["birth", "death"]].to_numpy()
    row = features.set_index("anchor").loc[a]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), layout="constrained")
    axes[0].scatter(h1[:, 0], h1[:, 1]-h1[:, 0], s=20, alpha=.7)
    axes[0].set(xlabel="Birth distance scale", ylabel="Lifetime in distance scale", title="H1 diagram in birth/lifetime coordinates")
    axes[0].set_xlim(0, max(grid["birth_upper"], h1[:, 0].max()*1.05) if len(h1) else grid["birth_upper"])
    axes[0].set_ylim(0, grid["lifetime_upper"])
    im = axes[1].imshow(row[H1].to_numpy(dtype=float).reshape(4, 4).T, origin="lower", aspect="auto",
        extent=[0, grid["birth_upper"], 0, grid["lifetime_upper"]], cmap="viridis")
    axes[1].set(xlabel="Birth distance scale", ylabel="Lifetime in distance scale", title="4 x 4 integrated weighted image")
    fig.colorbar(im, ax=axes[1], label="Lifetime-weighted mass")
    axes[2].bar(range(4), row[H0].to_numpy(dtype=float), color="#277da1")
    axes[2].set(xlabel="H0 merge-distance bin (last includes overflow)", ylabel="Fraction of finite merges", title="H0 has birth zero: four 1D bins", xticks=range(4))
    fig.suptitle(f"Fixed example: first forecast {row.formation_date.date()} | scales are not elapsed time")
    fig.savefig(OUT/"01_diagram_to_image.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), layout="constrained")
    for ax, period in zip(axes, ["development", "later"]):
        p = pnl.loc[pnl.period.eq(period)]
        for model in ["AlwaysOn", "Simple", "SimplePlusStockPD", "Ordinary20", "PersistenceImage20"]:
            ax.plot(p.date, (np.cumprod(1+p[model])-1)*100, label=model, color=COLORS[model], lw=1.5)
        ax.axhline(0, color="black", lw=.5); ax.set(title=period.capitalize(), ylabel="Gross compounded return (%)")
        ax.legend(ncol=3, fontsize=8)
    fig.suptitle("Same daily portfolio, different on/off forecasts | gross/pre-fee, flat days included")
    fig.savefig(OUT/"02_gross_gate_profit.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(13, 7), layout="constrained")
    for i, period in enumerate(["development", "later"]):
        for j, metric in enumerate(["forecast_MSE_bps_squared", "gate_mean_bps_per_calendar_day"]):
            ax = axes[i, j]; rows = comparisons.loc[comparisons.period.eq(period) & comparisons.metric.eq(metric)]
            for k, r in enumerate(rows.itertuples()):
                ax.plot([r.sim95_low, r.sim95_high], [k, k], lw=3, color=COLORS["PersistenceImage20"])
                ax.scatter(r.difference, k, color="black", zorder=3)
            ax.axvline(0, color="black", lw=.7)
            ax.set(yticks=range(len(rows)), yticklabels=["Image minus "+c for c in rows.comparator], title=period.capitalize(),
                xlabel="MSE difference (bps squared); negative favors image" if j == 0 else "Calendar mean difference (bps/day); positive favors image")
    fig.suptitle("Paired approximate 95% simultaneous bands across three comparisons per period/metric")
    fig.savefig(OUT/"03_incremental_comparisons.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(12, 6), layout="constrained")
    dates = features.formation_date
    axes[0].plot(dates, diagnostics.H1_mass_retained_fraction, color=COLORS["PersistenceImage20"])
    axes[0].set(ylabel="Retained weighted mass fraction", ylim=(0, 1.02), title="Finite image grid: includes Gaussian boundary truncation")
    axes[1].plot(dates, diagnostics.H1_points_outside_grid, label="H1 points outside fixed grid")
    axes[1].plot(dates, diagnostics.H0_upper_overflows, label="H0 merges beyond calibration upper (retained in last bin)")
    axes[1].set(ylabel="Count"); axes[1].legend()
    fig.suptitle("Range diagnostics for all anchors | image axes frozen from first training set")
    fig.savefig(OUT/"04_image_coverage.png", dpi=160); plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    spec_path = OUT/"specification.json"
    if spec_path.exists() and json.loads(spec_path.read_text()) != CONFIG:
        raise ValueError("Existing specification differs; use a new experiment")
    spec_path.write_text(json.dumps(CONFIG, indent=2)+"\n")
    protected_paths = [PREV/p for p in ["specification.json", "summary.json", "state_features_and_targets.csv",
        "persistence_intervals.csv.gz", "walk_forward_predictions.csv", "daily_gate_returns.csv", "training_membership.csv.gz"]]
    protected_paths += [DATA/"returns_log.csv", ROOT/"experiments/equity_expanded_pca_reversal/daily_gross_returns.csv",
        ROOT/"experiments/equity_persistence_regimes.py", ROOT/"equity_persistence_regimes.ipynb"]
    protected = {str(p.relative_to(ROOT)): sha(p) for p in protected_paths}
    f = pd.read_csv(PREV/"state_features_and_targets.csv", parse_dates=["formation_date", "history_end", "target_start", "target_end"])
    old = pd.read_csv(PREV/"walk_forward_predictions.csv", parse_dates=["formation_date", "target_end"])
    intervals = pd.read_csv(PREV/"persistence_intervals.csv.gz").query("object == 'stock'")
    diagrams = {(int(a), int(d)): g.dropna(subset=["death"])[["birth", "death"]].to_numpy() for (a, d), g in intervals.groupby(["anchor", "dimension"])}
    valid = np.isfinite(f[BASIC+SUMMARY+previous.LAG].to_numpy()).all(axis=1)
    first = old.iloc[0]
    initial = f.loc[valid & f.formation_date.lt(first.formation_date) & f.target_end.le(first.formation_date) & f.target_mean_bps.notna()]
    assert len(initial) == int(first.training_labels) and len(initial) >= 104
    calibration_h0 = np.concatenate([diagrams[(int(a), 0)] for a in initial.anchor])
    calibration_h1 = np.concatenate([diagrams.get((int(a), 1), np.empty((0, 2))) for a in initial.anchor])
    assert len(calibration_h1) > 0
    grid = {"first_prediction_anchor": int(first.anchor), "first_prediction_date": str(first.formation_date.date()),
        "calibration_anchors": initial.anchor.astype(int).tolist(), "calibration_labels": len(initial),
        "latest_calibration_target_end": str(initial.target_end.max().date()),
        "H0_upper": float(1.25*calibration_h0[:, 1].max()), "birth_upper": float(1.25*calibration_h1[:, 0].max()),
        "lifetime_upper": float(1.25*np.diff(calibration_h1, axis=1).max())}
    grid.update(birth_sigma=grid["birth_upper"]/8, lifetime_sigma=grid["lifetime_upper"]/8)
    (OUT/"frozen_grid.json").write_text(json.dumps(grid, indent=2)+"\n")
    panel = pd.read_csv(DATA/"returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    reference = pd.read_csv(PREV/"reference_stocks.csv").symbol.tolist()
    images, ordinary, diagnostics = [], [], []
    for row in f.itertuples():
        h0 = diagrams[(row.anchor, 0)]; h1 = diagrams.get((row.anchor, 1), np.empty((0, 2)))
        values, diagnostic = vectorize(h0, h1, grid)
        images.append(values); diagnostics.append({"anchor": row.anchor, **diagnostic})
        ordinary.append(ordinary_features(panel, reference, row.signal_index))
    f[H0+H1] = np.array(images); f[ORDINARY] = np.array(ordinary)
    diagnostics = pd.DataFrame(diagnostics)
    f.to_csv(OUT/"state_features_and_targets.csv", index=False)
    diagnostics.to_csv(OUT/"image_range_diagnostics.csv", index=False)
    predictions, memberships, coefficients = [], [], []
    for row in old.itertuples():
        current = f.loc[f.anchor.eq(row.anchor)].iloc[0]
        train = f.loc[valid & f.formation_date.lt(row.formation_date) & f.target_end.le(row.formation_date) & f.target_mean_bps.notna()]
        assert len(train) == row.training_labels
        record = {k: getattr(row, k) for k in ["anchor", "signal_index", "formation_date", "target_start", "target_end", "target_mean_bps", "score_period", "training_labels", "latest_training_target_end"]}
        y = train.target_mean_bps.to_numpy()
        for model, columns in MODELS.items():
            if not columns:
                record[model] = float(y.mean()); continue
            pred, mean, scale, beta, intercept = previous.ridge(train[columns].to_numpy(), y, current[columns].to_numpy(dtype=float))
            record[model] = pred
            coefficients.extend({"anchor": row.anchor, "model": model, "feature": c, "training_mean": mu, "training_scale": sd,
                "coefficient_standardized": b, "intercept_bps": intercept} for c, mu, sd, b in zip(columns, mean, scale, beta))
        predictions.append(record)
        memberships.extend({"prediction_anchor": row.anchor, "training_anchor": int(a)} for a in train.anchor)
    predictions = pd.DataFrame(predictions)
    old_pnl = pd.read_csv(PREV/"daily_gate_returns.csv", parse_dates=["date", "formation_date"])
    pnl = old_pnl[["date", "prediction_anchor", "formation_date", "period", "AlwaysOn"]].copy()
    for model in MODELS:
        active = pnl.prediction_anchor.map(predictions.set_index("anchor")[model]).gt(0)
        pnl[model] = np.where(active, pnl.AlwaysOn, 0.)
        pnl[model+"_active"] = active
    predictions.to_csv(OUT/"walk_forward_predictions.csv", index=False)
    pd.DataFrame(memberships).to_csv(OUT/"training_membership.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    pd.DataFrame(coefficients).to_csv(OUT/"coefficient_history.csv", index=False)
    pnl.to_csv(OUT/"daily_gate_returns.csv", index=False)
    metrics, performance, comparisons = summarize(predictions, pnl)
    for name, frame in [("forecast_metrics", metrics), ("gate_performance", performance), ("paired_incremental_comparisons", comparisons)]:
        frame.to_csv(OUT/f"{name}.csv", index=False)
    plots(f, pnl, intervals, grid, diagnostics, comparisons)
    # Representation controls independent of any strategy labels.
    h0 = diagrams[(grid["first_prediction_anchor"], 0)]
    h1 = diagrams[(grid["first_prediction_anchor"], 1)]
    original, _ = vectorize(h0, h1, grid)
    shuffled, _ = vectorize(h0[::-1], h1[::-1], grid)
    empty, _ = vectorize(h0, np.empty((0, 2)), grid)
    zero, _ = vectorize(h0, np.array([[.5, .5]]), grid)
    # Equal scalar lifetime summaries, different birth scales; controlled hypothetical diagrams.
    early, _ = vectorize(h0, np.array([[.25, .35], [.4, .6]]), grid)
    late, _ = vectorize(h0, np.array([[.75, .85], [.9, 1.1]]), grid)
    checks = {"baseline_predictions_reconcile": all(np.allclose(predictions[m], old[m], atol=1e-10) for m in ["HistoryMean", "Simple", "SimplePlusStockPD"]),
        "baseline_gates_reconcile": all(np.allclose(pnl[m], old_pnl[m], atol=1e-15) for m in ["AlwaysOn", "HistoryMean", "Simple", "SimplePlusStockPD"]),
        "exact_training_memberships_preserved": pd.DataFrame(memberships).equals(pd.read_csv(PREV/"training_membership.csv.gz")),
        "all_features_finite": bool(np.isfinite(f[H0+H1+ORDINARY].to_numpy()).all()),
        "H0_frequencies_sum_one": bool(np.allclose(f[H0].sum(axis=1), 1)),
        "diagram_point_order_invariant": bool(np.allclose(original, shuffled)),
        "empty_and_zero_persistence_H1_zero": bool(np.allclose(empty[4:], 0) and np.allclose(zero[4:], 0)),
        "birth_shift_detected_despite_same_lifetimes": bool(not np.allclose(early[4:], late[4:])),
        "original_artifacts_unchanged": all(sha(p) == protected[str(p.relative_to(ROOT))] for p in protected_paths)}
    assert all(checks.values()), checks
    summary = {"configuration": CONFIG, "checks": checks, "grid": grid, "feature_anchors": len(f), "predictions": len(predictions),
        "first_prediction": str(predictions.formation_date.min().date()), "last_prediction": str(predictions.formation_date.max().date()),
        "forecast_scores_by_period": predictions.loc[predictions.target_mean_bps.notna()].groupby("score_period").size().to_dict(),
        "calendar_days_by_period": pnl.groupby("period").size().to_dict(),
        "range_diagnostics": {"H1_outside_points_total": int(diagnostics.H1_points_outside_grid.sum()),
            "H1_total_points": int(diagnostics.H1_points.sum()), "minimum_mass_retained_fraction": float(diagnostics.H1_mass_retained_fraction.min()),
            "median_mass_retained_fraction": float(diagnostics.H1_mass_retained_fraction.median()), "H0_upper_overflows_total": int(diagnostics.H0_upper_overflows.sum())},
        "protected_sha256": protected, "source_sha256": sha(Path(__file__))}
    (OUT/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print("CHECKS", checks, flush=True)
    print("FORECAST\n", metrics.round(5).to_string(index=False), flush=True)
    print("GATES\n", performance.round(5).to_string(index=False), flush=True)
    print("INCREMENTAL\n", comparisons.round(5).to_string(index=False), flush=True)
    print("IMAGE COVERAGE", summary["range_diagnostics"], flush=True)


if __name__ == "__main__":
    main()
