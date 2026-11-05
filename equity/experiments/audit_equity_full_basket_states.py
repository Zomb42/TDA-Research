"""Independent full-return geometry, diagram transport, forecast and calendar audit."""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
import pandas as pd
from persim import wasserstein
from ripser import ripser
from scipy.spatial.distance import squareform
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import minimum_spanning_tree
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"experiments/equity_full_basket_states"
PREV = ROOT/"experiments/equity_persistence_regimes"
DATA = ROOT/"market_data/datasets/equity_daily_expanded_2016_2026-10-27"


def transport_lp(a, b):
    """Bipartite match/delete/insert LP; independent of square assignment padding."""
    n, m = len(a), len(b)
    deletion = np.diff(a, axis=1).ravel()/np.sqrt(2)
    insertion = np.diff(b, axis=1).ravel()/np.sqrt(2)
    if not n or not m: return float(deletion.sum()+insertion.sum())
    pair_costs = np.linalg.norm(a[:, None, :]-b[None, :, :], axis=2).ravel()
    cost = np.r_[pair_costs, deletion, insertion]
    rows = np.r_[np.repeat(np.arange(n), m), n+np.tile(np.arange(m), n), np.arange(n), n+np.arange(m)]
    columns = np.r_[np.arange(n*m), np.arange(n*m), n*m+np.arange(n), n*m+n+np.arange(m)]
    constraint = coo_matrix((np.ones(len(rows)), (rows, columns)), shape=(n+m, len(cost))).tocsr()
    solved = linprog(cost, A_eq=constraint, b_eq=np.ones(n+m), bounds=(0, None), method="highs")
    assert solved.success
    return float(solved.fun)


def main():
    result = json.loads((OUT/"summary.json").read_text()); config = result["configuration"]
    f = pd.read_csv(OUT/"state_features_and_targets.csv", parse_dates=["formation_date", "history_end", "target_start", "target_end"])
    p = pd.read_csv(OUT/"walk_forward_predictions.csv", parse_dates=["formation_date", "target_start", "target_end", "latest_training_target_end"])
    pnl = pd.read_csv(OUT/"daily_gate_returns.csv", parse_dates=["date", "formation_date"])
    intervals = pd.read_csv(OUT/"day_cloud_intervals.csv.gz")
    members = pd.read_csv(OUT/"training_membership.csv.gz")
    coefficients = pd.read_csv(OUT/"coefficient_history.csv")
    panel = pd.read_csv(DATA/"returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    names = pd.read_csv(PREV/"reference_stocks.csv").symbol.tolist()
    universe = pd.read_csv(DATA/"universe.csv").query("role == 'equity'").symbol.tolist()
    initial = panel[universe].iloc[:272]
    assert names == initial.columns[initial.notna().all()].tolist() and len(names) == 182
    assert panel[names].notna().all().all()
    h = panel[names].to_numpy(); market = panel.SPY.to_numpy()
    models = config["models"]; augmentations = list(config["augmentations"])
    targets = {"risk": "target_logRMS", "mean": "target_mean_bps"}
    diagrams = {(int(a), obj, int(dim)): g.dropna(subset=["death"])[["birth", "death"]].to_numpy()
                for (a, obj, dim), g in intervals.groupby(["anchor", "object", "dimension"])}
    scales = intervals.groupby(["anchor", "object"]).scale.first().to_dict()
    f_idx = f.set_index("anchor")
    sample = set(np.unique(np.linspace(0, len(f)-1, 9).astype(int)).tolist())
    max_geometry_error, max_transport_error, max_PH_error = 0., 0., 0.
    old_cov = {}; old_log_scale = {}
    for anchor, t in [(-1, int(f.iloc[0].signal_index)-5)]+list(zip(f.anchor, f.signal_index)):
        history = h[t-120:t]; m = market[t-120:t]; mc = m-m.mean()
        centered = history-history.mean(axis=0)
        beta = mc@centered/(mc@mc)
        e = centered-mc[:, None]*beta
        objects = {"raw": history/np.sqrt(182), "residual": e/e.std(axis=0, ddof=1)/np.sqrt(182)}
        for obj, points in objects.items():
            # Gram identity for distances, independent of source's pdist.
            norm = (points**2).sum(axis=1)
            d = np.sqrt(np.maximum(norm[:, None]+norm[None, :]-2*points@points.T, 0))
            np.fill_diagonal(d, 0.)
            upper = d[np.triu_indices(120, 1)]; scale = np.median(upper)
            assert np.isclose(scale, scales[(anchor, obj)], atol=1e-12)
            normalized = d/scale
            mst = minimum_spanning_tree(normalized).data
            saved_h0 = diagrams[(anchor, obj, 0)]
            assert len(saved_h0) == 119 and (saved_h0[:, 0] == 0).all()
            assert intervals.loc[intervals.anchor.eq(anchor) & intervals.object.eq(obj) & intervals.dimension.eq(0), "death"].isna().sum() == 1
            assert np.allclose(np.sort(mst), np.sort(saved_h0[:, 1]), atol=2e-6)
            h1 = diagrams.get((anchor, obj, 1), np.empty((0, 2)))
            if anchor in sample:
                computed = ripser(normalized, distance_matrix=True, maxdim=1)["dgms"][1]
                err = wasserstein(computed, h1)
                max_PH_error = max(max_PH_error, err)
            covariance = np.cov(points, rowvar=False)
            sd = np.sqrt(np.diag(covariance)); corr = covariance/np.outer(sd, sd)
            ordinary = {"log_scale": np.log(scale), "distance_cv": upper.std()/upper.mean(),
                "distance_q10": np.quantile(upper, .1)/scale, "distance_q90": np.quantile(upper, .9)/scale,
                "MST_q90": np.quantile(saved_h0[:, 1], .9), "MST_sum_squared": np.sum(saved_h0[:, 1]**2),
                "effective_rank": np.trace(covariance)**2/np.sum(covariance**2), "mean_stock_corr": corr[np.triu_indices(182, 1)].mean()}
            if anchor >= 0:
                row = f_idx.loc[anchor]
                ordinary["covariance_change5"] = np.linalg.norm(covariance-old_cov[obj])/np.linalg.norm(old_cov[obj])
                ordinary["log_scale_change5"] = np.log(scale)-old_log_scale[obj]
                for suffix, value in ordinary.items():
                    err = abs(float(row[obj+"_"+suffix])-value)
                    max_geometry_error = max(max_geometry_error, err)
                lifetime = np.diff(h1, axis=1).ravel()
                prior = diagrams.get((anchor-1, obj, 1), np.empty((0, 2)))
                prior_life = np.diff(prior, axis=1).ravel()
                assert row[obj+"_H1_count"] == len(h1)
                assert np.isclose(row[obj+"_H1_max_shape"], lifetime.max() if len(lifetime) else 0.)
                assert np.isclose(row[obj+"_H1_sum_squared_shape"], lifetime@lifetime)
                assert np.isclose(row[obj+"_H1_max_bps"], (lifetime.max() if len(lifetime) else 0.)*scale*1e4)
                assert np.isclose(row[obj+"_H1_sum_squared_bps2"], (lifetime@lifetime)*(scale*1e4)**2)
                assert np.isclose(row[obj+"_H1_delta_shape_squared"], lifetime@lifetime-prior_life@prior_life)
                for suffix, first_diagram, second_diagram in [
                    ("W1_shape", h1, prior),
                    ("W1_bps", h1*scale*1e4, prior*scales[(anchor-1, obj)]*1e4)]:
                    measured = transport_lp(first_diagram, second_diagram)
                    err = abs(measured-row[obj+"_H1_"+suffix])
                    max_transport_error = max(max_transport_error, err)
                    assert np.isclose(measured, row[obj+"_H1_"+suffix], rtol=1e-9, atol=1e-7), (anchor, obj, suffix, measured, row[obj+"_H1_"+suffix], err)
            old_cov[obj] = covariance; old_log_scale[obj] = np.log(scale)
    assert max_geometry_error < 1e-8 and max_PH_error < 1e-4
    print("Geometry and every diagram-change transport checked", flush=True)
    source = pd.read_csv(ROOT/"experiments/equity_expanded_pca_reversal/daily_gross_returns.csv", parse_dates=["date"])
    strategy = source.loc[source.universe.eq("expanded200") & source.window.eq(120) & source.model.eq("SPY_PCA3")].set_index("date").sort_index().gross_return
    for row in f.itertuples():
        t = row.signal_index
        assert panel.index[t] == row.formation_date and panel.index[t-1] == row.history_end
        assert row.history_end < row.formation_date < row.target_start
        trailing = strategy.loc[:row.formation_date].tail(20).to_numpy()*1e4
        if len(trailing) == 20: assert np.isclose(row.strategy_trailing20_logRMS, np.log(np.linalg.norm(trailing)/np.sqrt(20)))
        else: assert pd.isna(row.strategy_trailing20_logRMS)
        vols = h[t-20:t].std(axis=0, ddof=1)
        assert np.isclose(row.basket_vol20_RMS, np.linalg.norm(vols)/np.sqrt(182))
        assert np.isclose(row.basket_vol20_dispersion, vols.std())
        if pd.notna(row.target_end):
            assert panel.index[t+20] == row.target_end
            y = strategy.loc[row.target_start:row.target_end].to_numpy()*1e4
            assert len(y) == 20 and np.isclose(y.mean(), row.target_mean_bps)
            assert np.isclose(np.linalg.norm(y)/np.sqrt(20), row.target_RMS_bps)
            assert np.isclose(np.log(np.linalg.norm(y)/np.sqrt(20)), row.target_logRMS)
        else: assert pd.isna(row.target_RMS_bps) and pd.isna(row.target_logRMS)
    valid_columns = models["Controls"]+["stock_H0_q90", "stock_H1_max_lifetime", "stock_H1_total_squared_lifetime", "lag_H0_q90", "lag_H1_max_lifetime", "lag_H1_total_squared_lifetime"]
    valid = np.isfinite(f[valid_columns].to_numpy()).all(axis=1)
    member_groups = {int(a): g.training_anchor.to_numpy() for a, g in members.groupby("prediction_anchor")}
    coef_groups = {(int(a), t, m): g.set_index("feature") for (a, t, m), g in coefficients.groupby(["anchor", "target", "model"])}
    max_prediction_error = 0.
    for row in p.itertuples():
        train = f.loc[valid & f.formation_date.lt(row.formation_date) & f.target_end.le(row.formation_date) & f.target_mean_bps.notna()]
        assert np.array_equal(train.anchor, member_groups[row.anchor])
        assert train.target_end.max() == row.latest_training_target_end <= row.formation_date
        assert len(train) == row.training_labels and len(train) >= 104
        current = f_idx.loc[row.anchor]
        for target, column in targets.items():
            y = train[column].to_numpy()
            for model, columns in models.items():
                if not columns: expected = y.mean()
                else:
                    scaler = StandardScaler().fit(train[columns]); z = scaler.transform(train[columns])
                    fit = Ridge(alpha=len(train), fit_intercept=True, solver="svd").fit(z, y)
                    expected = fit.predict(scaler.transform(pd.DataFrame([current[columns].to_dict()])))[0]
                    saved = coef_groups[(row.anchor, target, model)].loc[columns]
                    assert np.allclose(saved.training_mean, scaler.mean_)
                    assert np.allclose(saved.training_scale, scaler.scale_)
                    assert np.allclose(saved.coefficient_standardized, fit.coef_)
                    assert np.allclose(saved.intercept, fit.intercept_)
                max_prediction_error = max(max_prediction_error, abs(expected-getattr(row, target+"_"+model)))
    assert max_prediction_error < 1e-8
    assert members.equals(pd.read_csv(PREV/"training_membership.csv.gz"))
    old = pd.read_csv(PREV/"walk_forward_predictions.csv")
    assert np.allclose(p.mean_HistoryMean, old.HistoryMean)
    assert pnl.date.is_unique and pd.DatetimeIndex(pnl.date).equals(strategy.loc[pnl.date.min():pnl.date.max()].index)
    assert np.allclose(pnl.AlwaysOn, strategy.loc[pnl.date], atol=1e-15)
    for row in p.itertuples():
        days = pnl.loc[pnl.prediction_anchor.eq(row.anchor)]
        assert days.date.tolist() == list(panel.index[row.signal_index+1:min(row.signal_index+6, len(panel))])
    for model in models:
        active = pnl.prediction_anchor.map(p.set_index("anchor")["mean_"+model]).gt(0)
        assert np.array_equal(active, pnl[model+"_active"])
        assert np.allclose(pnl[model], np.where(active, pnl.AlwaysOn, 0.), atol=1e-15)
    metrics = pd.read_csv(OUT/"forecast_metrics.csv").set_index(["period", "target", "model"])
    comparisons = pd.read_csv(OUT/"paired_incremental_comparisons.csv").set_index(["period", "metric", "model"])
    performance = pd.read_csv(OUT/"gate_performance.csv").set_index(["period", "model"])
    max_metric_error = 0.

    def verify(table, key, values):
        nonlocal max_metric_error
        for field, value in values.items():
            error = abs(float(table.loc[key, field])-float(value)); max_metric_error = max(max_metric_error, error)
            assert np.isclose(table.loc[key, field], value, rtol=1e-10, atol=1e-10), (key, field, error)

    def draws(n, block, seed):
        rng = np.random.default_rng(seed); start = rng.integers(n, size=(1000, math.ceil(n/block)))
        return ((start[:, :, None]+np.arange(block)) % n).reshape(1000, -1)[:, :n]

    def bands(period, metric, differences, ix):
        center = differences.mean(axis=0); boot = differences[ix].mean(axis=1); sd = boot.std(axis=0, ddof=1)
        z = np.divide(boot-center, sd, out=np.zeros_like(boot), where=sd > 1e-12)
        radius = np.quantile(abs(z).max(axis=1), .95)
        for j, model in enumerate(augmentations):
            verify(comparisons, (period, metric, model), {"difference": center[j], "point95_low": np.quantile(boot[:, j], .025),
                "point95_high": np.quantile(boot[:, j], .975), "sim95_low": center[j]-radius*sd[j], "sim95_high": center[j]+radius*sd[j]})

    for pi, period in enumerate(["development", "later"]):
        scored = p.loc[p.score_period.eq(period) & p.target_mean_bps.notna()].sort_values("formation_date")
        ix = draws(len(scored), 12, config["seed"]+pi)
        for target, column in targets.items():
            y = scored[column].to_numpy(); errors = {}
            for model in models:
                estimates = scored[target+"_"+model].to_numpy(); error = (estimates-y)**2; errors[model] = error
                boot = error[ix].mean(axis=1)
                values = {"MSE": error.mean(), "MSE_low": np.quantile(boot, .025), "MSE_high": np.quantile(boot, .975), "MAE_native": abs(estimates-y).mean()}
                if target == "risk": values["RMS_MAE_bps"] = abs(np.exp(estimates)-np.exp(y)).mean()
                verify(metrics, (period, target, model), values)
            for model in models: verify(metrics, (period, target, model), {"skill_vs_Controls": 1-errors[model].mean()/errors["Controls"].mean()})
            diff = np.column_stack([errors[m]-errors["Controls"] for m in augmentations])
            bands(period, "logRMS_MSE" if target == "risk" else "mean_MSE_bps_squared", diff, ix)
        days = pnl.loc[pnl.period.eq(period)].sort_values("date"); ix = draws(len(days), 60, config["seed"]+50+pi)
        for model in ["AlwaysOn", *models]:
            r = days[model].to_numpy(); curve = np.cumprod(1+r); sd = r.std(ddof=1); boot = r[ix].mean(axis=1)*1e4
            verify(performance, (period, model), {"mean_daily_bps": r.mean()*1e4, "mean_low": np.quantile(boot, .025), "mean_high": np.quantile(boot, .975),
                "active_fraction": 1. if model == "AlwaysOn" else days[model+"_active"].mean(), "gross_CAGR": curve[-1]**(252/len(r))-1,
                "annualized_volatility": sd*np.sqrt(252), "sharpe_vs_zero": r.mean()/sd*np.sqrt(252), "total_gross_return": curve[-1]-1,
                "max_drawdown": (curve/np.maximum.accumulate(np.r_[1., curve])[1:]-1).min()})
        bands(period, "gate_mean_bps_per_calendar_day", np.column_stack([(days[m]-days.Controls).to_numpy()*1e4 for m in augmentations]), ix)
    protected_ok = all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == value for path, value in result["protected_sha256"].items())
    checks = {"reference_membership_initial_past_only_and_complete": True, "every_full_dimension_distance_and_control_reconstructed": True,
        "all_H0_MST_pairs_match": True, "selected_H1_diagrams_independently_recomputed": True,
        "every_Wasserstein_distance_matches_independent_transport_LP": True, "every_risk_and_mean_label_matches_actual_daily_trades": True,
        "every_forecast_and_coefficient_matches_sklearn": True, "exact_completed_label_memberships_and_calendar": True,
        "all_gate_returns_and_reported_statistics_reproduced": True, "all_pointwise_and_simultaneous_intervals_reproduced": True,
        "protected_original_inputs_unchanged": protected_ok}
    assert all(checks.values())
    audit = {"checks": checks, "state_anchors_checked": 491, "forecast_dates_checked": len(p), "target_model_fits_checked": len(p)*len(models)*2,
        "max_geometry_error": max_geometry_error, "max_H1_recomputation_W1": max_PH_error, "max_transport_error": max_transport_error,
        "max_prediction_error": max_prediction_error, "max_metric_error": max_metric_error,
        "audit_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/"independent_audit.json").write_text(json.dumps(audit, indent=2)+"\n")
    print(json.dumps(audit, indent=2), flush=True)


if __name__ == "__main__": main()
