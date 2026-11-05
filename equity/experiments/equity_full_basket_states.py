"""Full-basket day states: raw/residual, diagram levels/changes, fixed forecasts."""
from pathlib import Path
import hashlib
import importlib.util
import json
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from ripser import ripser
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist, pdist, squareform
from scipy.sparse.csgraph import minimum_spanning_tree

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/"market_data/datasets/equity_daily_expanded_2016_2026-10-27"
PREV = ROOT/"experiments/equity_persistence_regimes"
OUT = ROOT/"experiments/equity_full_basket_states"
loader = importlib.util.spec_from_file_location("regimes", ROOT/"experiments/equity_persistence_regimes.py")
previous = importlib.util.module_from_spec(loader); loader.loader.exec_module(previous)
OBJECTS = ["raw", "residual"]
ORDINARY_SUFFIXES = ["log_scale", "distance_cv", "distance_q10", "distance_q90", "MST_q90", "MST_sum_squared",
                    "effective_rank", "mean_stock_corr", "covariance_change5", "log_scale_change5"]
BASE = previous.BASIC+["strategy_trailing20_logRMS", "basket_vol20_RMS", "basket_vol20_dispersion"]
BASE += [obj+"_"+suffix for obj in OBJECTS for suffix in ORDINARY_SUFFIXES]
ADDITIONS = {
    "RawLevel": ["raw_H1_count", "raw_H1_max_bps", "raw_H1_sum_squared_bps2"],
    "RawChange": ["raw_H1_W1_bps", "raw_H1_W1_shape", "raw_H1_delta_shape_squared"],
    "ResidualLevel": ["residual_H1_count", "residual_H1_max_shape", "residual_H1_sum_squared_shape"],
    "ResidualChange": ["residual_H1_W1_shape", "residual_H1_delta_shape_squared"],
}
MODELS = {"HistoryMean": [], "Controls": BASE, **{k: BASE+v for k, v in ADDITIONS.items()}}
TARGETS = {"risk": "target_logRMS", "mean": "target_mean_bps"}
CONFIG = {
    "decision_date": "2026-10-29", "status": "exploratory; examined history and current-survivor candidate universe",
    "question": "do the full traded basket's day states, or changes in their topology, forecast strategy risk/mean beyond conventional controls?",
    "point": "one historical day, coordinates = that day's 182 reference-stock daily log returns; no SPY coordinate",
    "cohort": "reuse reference names fixed by 272 complete returns at initial formation; no future-completeness selection; no changing dimensions",
    "cloud": "120 prior days ending t-1; 182 coordinates; no PCA truncation or downsampling",
    "raw": "raw log-return vectors divided by sqrt(182), so Euclidean distance is RMS stock-return difference; broad market retained",
    "residual": "regress each stock on intercept and SPY over the same prior120, standardize residual columns by sample SD, divide vectors by sqrt(182)",
    "distance": "complete Euclidean Vietoris-Rips H0/H1; compute after dividing distances by their median; raw diagram scales restored when using amplitude features",
    "changes": "compare current diagram with five-sessions-earlier window (115 shared days); representations refit on their own past windows",
    "Wasserstein": "order1 sum of Euclidean birth/death matching costs, with diagonal cost lifetime/sqrt(2); exact assignment, finite H1 only; empty diagram cost sum of diagonal costs",
    "H0": "one essential interval excluded; finite deaths equal MST edges; MST quantile and squared sum included as ordinary controls, no H0-only alpha claim",
    "ordinary_controls": BASE, "augmentations": ADDITIONS, "models": MODELS,
    "primary_target": "risk: log(next20 RMS gross daily strategy return measured in bps); primary loss = squared log error; exp(prediction) is a positive RMS estimate, not an arithmetic conditional-mean claim",
    "secondary_target": "mean of next20 daily gross strategy returns in bps; same target and gates as earlier studies",
    "strategy": "unchanged expanded200 120-session SPY_PCA3 daily raw next-open to close, unit gross, flat nightly; no recomputation",
    "training": "exact original 379 decision dates and expanding completed prior target memberships, minimum104; each target fitted separately; feature means/SD from training only; ridge lambda1 (sklearn alpha=n)",
    "gate": "secondary mean forecast >0 activates original daily portfolio for next5 sessions, else zero; no risk-based gate; every calendar day included",
    "periods": "entry before2024 development; otherwise later; complete targets crossing boundary excluded from period forecast scores, not from P&L",
    "uncertainty": "1000 circular block draws; 12 five-session anchors for prediction loss, 60 daily trades for gate means; conditional on saved forecasts, not full refitting",
    "families": "four augmentation-minus-Controls comparisons, simultaneous approximate95 bands separately per period and metric; risk primary, mean/gates secondary; not a correction across project history",
    "controls": "first prior window: day permutation, stock permutation, raw returns x3, residual unit invariance; H0/MST equivalence; exact PCA isometry with all nonzero components",
    "selection": "one 120-day cloud, one lag5, four declared augmentations; no image, window/component search, threshold tuning, or new downloads",
    "fees": "excluded entirely", "seed": 2026102951,
}
COLORS = {"AlwaysOn": "#777777", "Controls": "#222222", "RawLevel": "#277da1", "RawChange": "#e58a20",
          "ResidualLevel": "#7b2cbf", "ResidualChange": "#228b64"}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def wasserstein(a, b):
    n, m = len(a), len(b)
    if not n: return float(np.diff(b, axis=1).sum()/np.sqrt(2))
    if not m: return float(np.diff(a, axis=1).sum()/np.sqrt(2))
    cost = np.zeros((n+m, n+m))
    cost[:n, :m] = cdist(a, b)
    cost[:n, m:] = np.inf
    cost[n:, :m] = np.inf
    cost[np.arange(n), m+np.arange(n)] = np.diff(a, axis=1).ravel()/np.sqrt(2)
    cost[n+np.arange(m), np.arange(m)] = np.diff(b, axis=1).ravel()/np.sqrt(2)
    rows, columns = linear_sum_assignment(cost)
    return float(cost[rows, columns].sum())


def point_objects(history, market):
    n = history.shape[1]
    design = np.c_[np.ones(len(history)), market]
    e = history-design@np.linalg.lstsq(design, history, rcond=None)[0]
    residual = (e-e.mean(axis=0))/e.std(axis=0, ddof=1)
    return {"raw": history/np.sqrt(n), "residual": residual/np.sqrt(n)}


def state(points):
    distances = pdist(points); scale = float(np.median(distances))
    d = squareform(distances/scale)
    # Keep diagram coordinates in double precision for rescaling and matching.
    diagrams = [a.astype(np.float64) for a in ripser(d, distance_matrix=True, maxdim=1)["dgms"]]
    h0 = diagrams[0][np.isfinite(diagrams[0][:, 1])]
    h1 = diagrams[1]
    centered = points-points.mean(axis=0)
    covariance = centered.T@centered/(len(points)-1)
    trace = np.trace(covariance)
    sigma = np.sqrt(np.diag(covariance))
    corr = covariance/np.outer(sigma, sigma)
    lifetime = np.diff(h1, axis=1).ravel()
    ordinary = {"log_scale": float(np.log(scale)), "distance_cv": float(distances.std()/distances.mean()),
        "distance_q10": float(np.quantile(distances, .1)/scale), "distance_q90": float(np.quantile(distances, .9)/scale),
        "MST_q90": float(np.quantile(h0[:, 1], .9)), "MST_sum_squared": float(np.sum(h0[:, 1]**2)),
        "effective_rank": float(trace**2/np.sum(covariance**2)), "mean_stock_corr": float(corr[np.triu_indices(len(sigma), 1)].mean())}
    return {"scale": scale, "dgm": diagrams, "cov": covariance, "distance": d, "ordinary": ordinary,
        "lifetime": lifetime, "points": points}


def feature_pair(current, old):
    features = {}; rows = []
    for obj in OBJECTS:
        a, b = current[obj], old[obj]; life = a["lifetime"]
        for key, value in a["ordinary"].items(): features[obj+"_"+key] = value
        features[obj+"_covariance_change5"] = float(np.linalg.norm(a["cov"]-b["cov"])/np.linalg.norm(b["cov"]))
        features[obj+"_log_scale_change5"] = float(np.log(a["scale"]/b["scale"]))
        features[obj+"_H1_count"] = len(life)
        features[obj+"_H1_max_shape"] = float(life.max()) if len(life) else 0.
        features[obj+"_H1_sum_squared_shape"] = float(life@life)
        features[obj+"_H1_max_bps"] = features[obj+"_H1_max_shape"]*a["scale"]*1e4
        features[obj+"_H1_sum_squared_bps2"] = float((life@life)*(a["scale"]*1e4)**2)
        features[obj+"_H1_W1_shape"] = wasserstein(a["dgm"][1], b["dgm"][1])
        features[obj+"_H1_W1_bps"] = wasserstein(a["dgm"][1]*a["scale"]*1e4, b["dgm"][1]*b["scale"]*1e4)
        features[obj+"_H1_delta_shape_squared"] = float(life@life-b["lifetime"]@b["lifetime"])
        rows.append({"object": obj, "points": len(a["points"]), "coordinates": a["points"].shape[1],
            "median_distance": a["scale"], "distance_cv": a["ordinary"]["distance_cv"], "effective_rank": a["ordinary"]["effective_rank"],
            "finite_H0": len(a["dgm"][0])-1, "H1_count": len(life), "H1_max_shape": features[obj+"_H1_max_shape"]})
    return features, rows


def representation_controls(history, market):
    clouds = point_objects(history, market)
    rng = np.random.default_rng(5501); permutation = rng.permutation(len(history))
    baseline = {k: state(v) for k, v in clouds.items()}
    variants = {"day_permutation": point_objects(history[permutation], market[permutation]),
        "stock_permutation": point_objects(history[:, ::-1], market), "returns_times3": point_objects(history*3, market*3)}
    checks = {}; rows = []
    for obj in OBJECTS:
        base = baseline[obj]
        assert np.allclose(np.sort(minimum_spanning_tree(base["distance"]).data), np.sort(base["dgm"][0][:-1, 1]), atol=2e-6)
        _, s, vt = np.linalg.svd(clouds[obj]-clouds[obj].mean(axis=0), full_matrices=False)
        exact = (clouds[obj]-clouds[obj].mean(axis=0))@vt.T
        assert np.allclose(pdist(exact), pdist(clouds[obj]), atol=1e-12)
        for name, transformed in variants.items():
            measured = state(transformed[obj])
            distance = wasserstein(base["dgm"][1], measured["dgm"][1])
            if name in ["day_permutation", "stock_permutation"]:
                assert distance < 2e-5
                assert np.isclose(base["scale"], measured["scale"])
            else:
                assert distance < 2e-5
                assert np.isclose(measured["scale"]/base["scale"], 3. if obj == "raw" else 1.)
            rows.append({"object": obj, "transformation": name, "normalized_H1_W1": distance,
                "scale_ratio": measured["scale"]/base["scale"]})
    checks.update(H0_deaths_equal_MST=True, full_coordinate_PCA_isometry=True, day_and_stock_order_invariance=True,
        normalized_shape_uniform_scale_invariance=True, raw_scale_homogeneity_and_residual_scale_invariance=True)
    return pd.DataFrame(rows), checks


def summarize(predictions, pnl):
    metrics, comparisons, performance = [], [], []
    for pi, period in enumerate(["development", "later"]):
        f = predictions.loc[predictions.score_period.eq(period) & predictions.target_mean_bps.notna()].sort_values("formation_date")
        ix = previous.block_indices(len(f), 12, CONFIG["seed"]+pi)
        for target, column in TARGETS.items():
            y = f[column].to_numpy()
            errors = {m: (f[target+"_"+m].to_numpy()-y)**2 for m in MODELS}
            diff = np.column_stack([errors[m]-errors["Controls"] for m in ADDITIONS])
            values = previous.comparison_bands(diff, ix)
            metric = "logRMS_MSE" if target == "risk" else "mean_MSE_bps_squared"
            for j, model in enumerate(ADDITIONS):
                comparisons.append({"period": period, "metric": metric, "model": model, "count": len(f),
                    "difference": values[0][j], "point95_low": values[1][j], "point95_high": values[2][j],
                    "sim95_low": values[3][j], "sim95_high": values[4][j], "better_direction": "negative"})
            for model in MODELS:
                boot = errors[model][ix].mean(axis=1)
                estimate = f[target+"_"+model].to_numpy()
                metrics.append({"period": period, "target": target, "model": model, "forecasts": len(f),
                    "MSE": float(errors[model].mean()), "MSE_low": float(np.quantile(boot, .025)), "MSE_high": float(np.quantile(boot, .975)),
                    "MAE_native": float(abs(estimate-y).mean()),
                    "RMS_MAE_bps": float(abs(np.exp(estimate)-np.exp(y)).mean()) if target == "risk" else np.nan,
                    "skill_vs_Controls": float(1-errors[model].mean()/errors["Controls"].mean())})
        p = pnl.loc[pnl.period.eq(period)].sort_values("date")
        ix = previous.block_indices(len(p), 60, CONFIG["seed"]+50+pi)
        diff = np.column_stack([(p[m]-p.Controls).to_numpy()*1e4 for m in ADDITIONS])
        values = previous.comparison_bands(diff, ix)
        for j, model in enumerate(ADDITIONS):
            comparisons.append({"period": period, "metric": "gate_mean_bps_per_calendar_day", "model": model, "count": len(p),
                "difference": values[0][j], "point95_low": values[1][j], "point95_high": values[2][j],
                "sim95_low": values[3][j], "sim95_high": values[4][j], "better_direction": "positive"})
        for model in ["AlwaysOn", *MODELS]:
            r = p[model].to_numpy(); curve = np.cumprod(1+r); std = r.std(ddof=1); boot = r[ix].mean(axis=1)*1e4
            performance.append({"period": period, "model": model, "calendar_days": len(p),
                "active_fraction": 1. if model == "AlwaysOn" else float(p[model+"_active"].mean()),
                "mean_daily_bps": float(r.mean()*1e4), "mean_low": float(np.quantile(boot, .025)), "mean_high": float(np.quantile(boot, .975)),
                "gross_CAGR": float(curve[-1]**(252/len(r))-1), "annualized_volatility": float(std*np.sqrt(252)),
                "sharpe_vs_zero": float(r.mean()/std*np.sqrt(252)), "total_gross_return": float(curve[-1]-1),
                "max_drawdown": float((curve/np.maximum.accumulate(np.r_[1., curve])[1:]-1).min())})
    return pd.DataFrame(metrics), pd.DataFrame(comparisons), pd.DataFrame(performance)


def plots(features, geometry, predictions, pnl, metrics, comparisons):
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(3, 1, figsize=(12, 8), layout="constrained")
    for obj in OBJECTS:
        g = geometry.loc[geometry.object.eq(obj)]
        for ax, column in zip(axes, ["distance_cv", "effective_rank", "H1_max_shape"]):
            ax.plot(g.formation_date, g[column], label=obj, lw=1.2)
            ax.set_ylabel(column.replace("_", " ")); ax.legend()
    fig.suptitle("120 day points, 182 stock-return coordinates | dispersion, effective rank and loops")
    fig.savefig(OUT/"01_full_dimension_geometry.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(16, 8), layout="constrained")
    for i, period in enumerate(["development", "later"]):
        for j, metric in enumerate(["logRMS_MSE", "mean_MSE_bps_squared", "gate_mean_bps_per_calendar_day"]):
            rows = comparisons.loc[comparisons.period.eq(period) & comparisons.metric.eq(metric)]
            ax = axes[i, j]
            for k, r in enumerate(rows.itertuples()):
                ax.plot([r.sim95_low, r.sim95_high], [k, k], lw=3, color=COLORS[r.model]); ax.scatter(r.difference, k, color="black", zorder=3)
            ax.axvline(0, color="black", lw=.7)
            ax.set(yticks=range(len(rows)), yticklabels=rows.model.tolist(), title=period.capitalize()+" | "+["Risk (primary)", "Mean (secondary)", "Gate (secondary)"][j],
                xlabel="Added minus Controls; negative is better" if j < 2 else "Added minus Controls (bps/day); positive is better")
    fig.suptitle("Paired approximate 95% simultaneous bands | four comparisons within each panel")
    fig.savefig(OUT/"02_incremental_comparisons.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), layout="constrained")
    for ax, period in zip(axes, ["development", "later"]):
        p = pnl.loc[pnl.period.eq(period)]
        for model in ["AlwaysOn", "Controls", *ADDITIONS]:
            ax.plot(p.date, (np.cumprod(1+p[model])-1)*100, label=model, color=COLORS[model], lw=1.3)
        ax.set(title=period.capitalize(), ylabel="Gross compounded return (%)"); ax.axhline(0, color="black", lw=.5); ax.legend(ncol=3, fontsize=8)
    fig.suptitle("Secondary mean-forecast gates | same portfolio, gross/pre-fee, all flat days included")
    fig.savefig(OUT/"03_gross_gate_profit.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(13, 7), layout="constrained")
    for i, obj in enumerate(OBJECTS):
        axes[i, 0].plot(features.formation_date, features[obj+"_H1_sum_squared_shape"], color=COLORS["RawLevel" if obj == "raw" else "ResidualLevel"])
        axes[i, 0].set(title=obj.capitalize()+" | current shape", ylabel="Sum of squared normalized lifetimes")
        axes[i, 1].plot(features.formation_date, features[obj+"_H1_W1_shape"], color=COLORS["RawChange" if obj == "raw" else "ResidualChange"])
        axes[i, 1].set(title=obj.capitalize()+" | change over five sessions", ylabel="Normalized H1 Wasserstein distance")
    fig.suptitle("A shape's current summary and its change are different measurements")
    fig.savefig(OUT/"04_levels_and_changes.png", dpi=160); plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    spec_path = OUT/"specification.json"
    if spec_path.exists() and json.loads(spec_path.read_text()) != CONFIG: raise ValueError("Specification differs; use a separate experiment")
    spec_path.write_text(json.dumps(CONFIG, indent=2)+"\n")
    protected_paths = [DATA/"returns_log.csv", PREV/"state_features_and_targets.csv", PREV/"walk_forward_predictions.csv",
        PREV/"training_membership.csv.gz", PREV/"daily_gate_returns.csv", PREV/"reference_stocks.csv",
        ROOT/"experiments/equity_expanded_pca_reversal/daily_gross_returns.csv", ROOT/"experiments/equity_persistence_regimes.py",
        ROOT/"experiments/equity_persistence_images/summary.json", ROOT/"equity_persistence_regimes.ipynb", ROOT/"equity_persistence_images.ipynb"]
    protected = {str(p.relative_to(ROOT)): sha(p) for p in protected_paths}
    f = pd.read_csv(PREV/"state_features_and_targets.csv", parse_dates=["formation_date", "history_end", "target_start", "target_end"])
    old_predictions = pd.read_csv(PREV/"walk_forward_predictions.csv", parse_dates=["formation_date"])
    old_members = pd.read_csv(PREV/"training_membership.csv.gz")
    panel = pd.read_csv(DATA/"returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    names = pd.read_csv(PREV/"reference_stocks.csv").symbol.tolist(); assert len(names) == 182
    assert panel[names].iloc[:272].notna().all().all(), "Initial reference history incomplete"
    source = pd.read_csv(ROOT/"experiments/equity_expanded_pca_reversal/daily_gross_returns.csv", parse_dates=["date"])
    strategy = source.loc[source.universe.eq("expanded200") & source.window.eq(120) & source.model.eq("SPY_PCA3")].set_index("date").sort_index().gross_return
    h = panel[names].to_numpy(); m = panel.SPY.to_numpy()
    control_table, checks = representation_controls(h[152:272], m[152:272]); control_table.to_csv(OUT/"representation_controls.csv", index=False)
    prior_index = int(f.iloc[0].signal_index)-5
    old_state = {obj: state(points) for obj, points in point_objects(h[prior_index-120:prior_index], m[prior_index-120:prior_index]).items()}
    features, intervals, geometry = [], [], []

    def save_diagrams(anchor, t, states):
        for obj in OBJECTS:
            for dimension, dgm in enumerate(states[obj]["dgm"]):
                for birth, death in dgm:
                    intervals.append({"anchor": anchor, "signal_index": t, "object": obj, "dimension": dimension,
                        "birth": float(birth), "death": float(death) if np.isfinite(death) else None, "scale": states[obj]["scale"]})

    save_diagrams(-1, prior_index, old_state)
    start_time = time.monotonic()
    for row in f.itertuples():
        t = row.signal_index
        states = {obj: state(points) for obj, points in point_objects(h[t-120:t], m[t-120:t]).items()}
        values, diagnostic = feature_pair(states, old_state)
        trailing = strategy.loc[:row.formation_date].tail(20).to_numpy()*1e4
        values["strategy_trailing20_logRMS"] = float(np.log(np.sqrt(np.mean(trailing**2)))) if len(trailing) == 20 else np.nan
        vol20 = h[t-20:t].std(axis=0, ddof=1)
        values["basket_vol20_RMS"] = float(np.sqrt(np.mean(vol20**2)))
        values["basket_vol20_dispersion"] = float(vol20.std())
        future = strategy.loc[row.target_start:row.target_end].to_numpy()*1e4 if pd.notna(row.target_end) else np.array([])
        if len(future):
            assert len(future) == 20 and np.isclose(future.mean(), row.target_mean_bps)
        values["target_RMS_bps"] = float(np.sqrt(np.mean(future**2))) if len(future) else np.nan
        values["target_logRMS"] = float(np.log(values["target_RMS_bps"])) if len(future) else np.nan
        features.append(values); geometry.extend({"anchor": row.anchor, "formation_date": row.formation_date, **d} for d in diagnostic)
        save_diagrams(row.anchor, t, states); old_state = states
        if (row.anchor+1) % 100 == 0: print(f"Computed {row.anchor+1} full-basket states in {time.monotonic()-start_time:.1f}s", flush=True)
    extra = pd.DataFrame(features)
    for column in extra: f[column] = extra[column]
    geometry = pd.DataFrame(geometry)
    f.to_csv(OUT/"state_features_and_targets.csv", index=False)
    geometry.to_csv(OUT/"geometry_diagnostics.csv", index=False)
    pd.DataFrame(intervals).to_csv(OUT/"day_cloud_intervals.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    valid = np.isfinite(f[BASE+previous.STOCK+previous.LAG].to_numpy()).all(axis=1)
    for columns in ADDITIONS.values(): assert np.isfinite(f[columns].to_numpy()).all()
    predictions, memberships, coefficients = [], [], []
    for p in old_predictions.itertuples():
        current = f.loc[f.anchor.eq(p.anchor)].iloc[0]
        train = f.loc[valid & f.formation_date.lt(p.formation_date) & f.target_end.le(p.formation_date) & f.target_mean_bps.notna()]
        assert len(train) == p.training_labels and train.target_logRMS.notna().all()
        record = {k: getattr(p, k) for k in ["anchor", "signal_index", "formation_date", "target_start", "target_end", "target_mean_bps", "score_period", "training_labels", "latest_training_target_end"]}
        record.update(target_logRMS=current.target_logRMS, target_RMS_bps=current.target_RMS_bps)
        for target, column in TARGETS.items():
            y = train[column].to_numpy()
            for model, columns in MODELS.items():
                if not columns: record[target+"_"+model] = float(y.mean()); continue
                forecast, mu, sd, beta, intercept = previous.ridge(train[columns].to_numpy(), y, current[columns].to_numpy(dtype=float))
                record[target+"_"+model] = forecast
                coefficients.extend({"anchor": p.anchor, "target": target, "model": model, "feature": c,
                    "training_mean": a, "training_scale": b, "coefficient_standardized": v, "intercept": intercept}
                    for c, a, b, v in zip(columns, mu, sd, beta))
        predictions.append(record)
        memberships.extend({"prediction_anchor": p.anchor, "training_anchor": int(a)} for a in train.anchor)
    predictions = pd.DataFrame(predictions)
    old_pnl = pd.read_csv(PREV/"daily_gate_returns.csv", parse_dates=["date", "formation_date"])
    pnl = old_pnl[["date", "prediction_anchor", "formation_date", "period", "AlwaysOn"]].copy()
    for model in MODELS:
        active = pnl.prediction_anchor.map(predictions.set_index("anchor")["mean_"+model]).gt(0)
        pnl[model+"_active"] = active; pnl[model] = np.where(active, pnl.AlwaysOn, 0.)
    predictions.to_csv(OUT/"walk_forward_predictions.csv", index=False)
    pd.DataFrame(memberships).to_csv(OUT/"training_membership.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    pd.DataFrame(coefficients).to_csv(OUT/"coefficient_history.csv", index=False)
    pnl.to_csv(OUT/"daily_gate_returns.csv", index=False)
    metrics, comparisons, performance = summarize(predictions, pnl)
    for name, frame in [("forecast_metrics", metrics), ("paired_incremental_comparisons", comparisons), ("gate_performance", performance)]: frame.to_csv(OUT/(name+".csv"), index=False)
    plots(f, geometry, predictions, pnl, metrics, comparisons)
    checks.update(exact_original_completed_training_memberships=pd.DataFrame(memberships).equals(old_members),
        no_missing_or_changing_coordinates=bool(np.isfinite(panel[names].to_numpy()).all()),
        original_calendar_and_portfolio_preserved=bool(pnl.date.equals(old_pnl.date) and np.allclose(pnl.AlwaysOn, old_pnl.AlwaysOn)),
        risk_labels_complete_before_training=True,
        original_inputs_unchanged=all(sha(p) == protected[str(p.relative_to(ROOT))] for p in protected_paths))
    assert all(checks.values()), checks
    summary = {"configuration": CONFIG, "checks": checks, "reference_stocks": len(names), "point_count": 120,
        "feature_anchors": len(f), "predictions": len(predictions), "first_prediction": str(predictions.formation_date.min().date()),
        "forecast_scores_by_period": predictions.loc[predictions.target_mean_bps.notna()].groupby("score_period").size().to_dict(),
        "calendar_days_by_period": pnl.groupby("period").size().to_dict(),
        "geometry_medians_later": geometry.loc[geometry.formation_date.ge("2024-01-01")].groupby("object")[["distance_cv", "effective_rank", "H1_count", "H1_max_shape"]].median().to_dict(),
        "protected_sha256": protected, "source_sha256": sha(Path(__file__))}
    (OUT/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print("CHECKS", checks, flush=True)
    print("FORECAST\n", metrics.round(5).to_string(index=False), flush=True)
    print("GATES\n", performance.round(5).to_string(index=False), flush=True)
    print("INCREMENTAL\n", comparisons.round(5).to_string(index=False), flush=True)
    print("GEOMETRY", summary["geometry_medians_later"], flush=True)


if __name__ == "__main__": main()
