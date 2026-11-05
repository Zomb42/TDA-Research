"""Independently reconstruct features, causal fits, gates and comparisons."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist, squareform
from scipy.sparse.csgraph import minimum_spanning_tree
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from ripser import ripser

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"experiments/equity_persistence_regimes"
DATA = ROOT/"market_data/datasets/equity_daily_expanded_2016_2026-10-27"
BASE = ROOT/"experiments/equity_expanded_pca_reversal"


def main():
    result = json.loads((OUT/"summary.json").read_text()); spec = result["configuration"]
    f = pd.read_csv(OUT/"state_features_and_targets.csv", parse_dates=["formation_date", "history_end", "target_start", "target_end"])
    predictions = pd.read_csv(OUT/"walk_forward_predictions.csv", parse_dates=["formation_date", "target_start", "target_end", "latest_training_target_end"])
    memberships = pd.read_csv(OUT/"training_membership.csv.gz")
    coefficients = pd.read_csv(OUT/"coefficient_history.csv")
    pnl = pd.read_csv(OUT/"daily_gate_returns.csv", parse_dates=["date", "formation_date"])
    intervals = pd.read_csv(OUT/"persistence_intervals.csv.gz")
    forecast_metrics = pd.read_csv(OUT/"forecast_metrics.csv")
    gate_metrics = pd.read_csv(OUT/"gate_performance.csv")
    comparisons = pd.read_csv(OUT/"paired_incremental_comparisons.csv")
    calibration = pd.read_csv(OUT/"sign_calibration.csv")
    panel = pd.read_csv(DATA/"returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    symbols = pd.read_csv(DATA/"universe.csv").query("role == 'equity'").symbol.tolist()
    expected_reference = panel[symbols].iloc[:272].columns[panel[symbols].iloc[:272].notna().all()].tolist()
    reference = pd.read_csv(OUT/"reference_stocks.csv").symbol.tolist()
    assert expected_reference == reference
    raw = pd.read_csv(BASE/"daily_gross_returns.csv", parse_dates=["date", "signal_date"])
    strategy = raw.loc[raw.universe.eq("expanded200") & raw.window.eq(120) & raw.model.eq("SPY_PCA3")].set_index("date").sort_index()
    basic, stock, lag = spec["basic_features"], spec["stock_features"], spec["lag_features"]
    models = {"HistoryMean": [], "Simple": basic, "SimplePlusStockPD": basic+stock, "SimplePlusLagPD": basic+lag}
    assert (f.history_end < f.formation_date).all() and (f.formation_date < f.target_start).all()
    assert set(f.reference_stocks) == {len(reference)} and set(f.lag_points) == {119}
    for row in f.itertuples():
        t = row.signal_index
        assert panel.index[t] == row.formation_date and panel.index[t-1] == row.history_end
        assert panel.index[t+1] == row.target_start
        available = panel[symbols].iloc[t-272:t].notna().all().sum()
        assert available == row.strategy_stock_count
        trailing = strategy.loc[:row.formation_date].tail(20).gross_return
        if len(trailing) == 20: assert np.isclose(trailing.mean()*1e4, row.strategy_trailing20_bps)
        else: assert pd.isna(row.strategy_trailing20_bps)
        if pd.notna(row.target_end):
            assert panel.index[t+20] == row.target_end
            outcome = strategy.loc[row.target_start:row.target_end].gross_return
            assert len(outcome) == 20 and np.isclose(outcome.mean()*1e4, row.target_mean_bps)
            crossing = (row.target_start < pd.Timestamp("2024-01-01")) != (row.target_end < pd.Timestamp("2024-01-01"))
            assert (row.score_period == "boundary") == crossing
        else: assert pd.isna(row.target_mean_bps) and t+20 >= len(panel)
    # Reconstruct nine feature windows via covariance eigenvectors, Pearson
    # residual normalization and a separately implemented diagram summarizer.
    max_feature_error = 0.
    for ai in np.unique(np.linspace(0, len(f)-1, 9).astype(int)):
        row = f.iloc[ai]; t = int(row.signal_index)
        h = panel[reference].iloc[t-120:t].to_numpy(); m = panel.SPY.iloc[t-120:t].to_numpy()
        design = np.c_[np.ones(120), m]
        residual = h-design@np.linalg.lstsq(design, h, rcond=None)[0]
        z = (residual-residual.mean(axis=0))/residual.std(axis=0, ddof=1)
        values, vectors = np.linalg.eigh(z.T@z/119); order = np.argsort(values)[::-1]
        values, vectors = values[order], vectors[:, order]
        g = z@vectors[:, :3]/np.sqrt(values[:3])
        assert np.allclose(np.cov(g, rowvar=False), np.eye(3), atol=1e-8)
        objects = {"stock": vectors[:, :3]*np.sqrt(values[:3]), "lag": np.c_[g[1:], g[:-1]]/np.sqrt(2)}
        checked = {"residual_mean_corr": np.corrcoef(residual, rowvar=False)[np.triu_indices(len(reference), 1)].mean(),
            "residual_pc1_share": values[0]/values.sum(), "residual_pc3_share": values[:3].sum()/values.sum(),
            "factor_lag1_acf_mean": np.mean([np.corrcoef(g[1:, k], g[:-1, k])[0, 1] for k in range(3)]),
            "SPY_vol20": panel.SPY.iloc[t-20:t].std(ddof=1)*np.sqrt(252)}
        power = abs(np.fft.rfft(g-g.mean(axis=0), axis=0)[1:])**2
        checked["factor_dominant_power_share_mean"] = (power.max(axis=0)/power.sum(axis=0)).mean()
        for obj, points in objects.items():
            distances = pdist(points); scale = np.median(distances)
            d = squareform(distances/scale)
            diagrams = ripser(d, distance_matrix=True, maxdim=1)["dgms"]
            finite_h0 = diagrams[0][np.isfinite(diagrams[0][:, 1])]
            assert np.isinf(diagrams[0][:, 1]).sum() == 1
            assert np.allclose(np.sort(minimum_spanning_tree(d).data), np.sort(finite_h0[:, 1]), atol=2e-6)
            lifetime = np.diff(diagrams[1], axis=1).ravel()
            checked[obj+"_H0_q90"] = np.quantile(finite_h0[:, 1], .9)
            checked[obj+"_H1_max_lifetime"] = lifetime.max() if len(lifetime) else 0.
            checked[obj+"_H1_total_squared_lifetime"] = lifetime@lifetime
            checked["loading_cloud_median_distance" if obj == "stock" else "lag_cloud_median_distance"] = scale
        for key, measured in checked.items(): max_feature_error = max(max_feature_error, abs(measured-row[key]))
    assert max_feature_error < 2e-5
    # Every saved diagram's scalar summaries must match its feature record;
    # essential intervals are not included in finite norms or quantiles.
    for (anchor, obj, dimension), group in intervals.groupby(["anchor", "object", "dimension"]):
        row = f.set_index("anchor").loc[anchor]
        finite = group.dropna(subset=["death"])
        if dimension == 0:
            assert group.death.isna().sum() == 1
            assert len(finite) == (len(reference)-1 if obj == "stock" else 118)
            assert np.isclose(np.quantile(finite.death-finite.birth, .9), row[obj+"_H0_q90"])
        else:
            assert group.death.notna().all()
            lifetimes = finite.death-finite.birth
            assert np.isclose(lifetimes.max(), row[obj+"_H1_max_lifetime"])
            assert np.isclose(np.sum(lifetimes**2), row[obj+"_H1_total_squared_lifetime"])
    finite_features = np.isfinite(f[basic+stock+lag].to_numpy()).all(axis=1)
    member_groups = {int(k): v.training_anchor.to_numpy() for k, v in memberships.groupby("prediction_anchor")}
    coefficient_groups = {(int(a), m): g.set_index("feature") for (a, m), g in coefficients.groupby(["anchor", "model"])}
    max_prediction_error = 0.
    for prediction in predictions.itertuples():
        row = f.set_index("anchor").loc[prediction.anchor]
        mask = (f.formation_date < prediction.formation_date) & f.target_end.le(prediction.formation_date) & f.target_mean_bps.notna() & finite_features
        train = f.loc[mask]
        assert np.array_equal(train.anchor, member_groups[prediction.anchor])
        assert len(train) >= 104 and len(train) == prediction.training_labels
        assert train.target_end.max() == prediction.latest_training_target_end
        assert (train.target_end <= prediction.formation_date).all()
        y = train.target_mean_bps.to_numpy()
        for model, columns in models.items():
            if not columns: measured = y.mean()
            else:
                scaler = StandardScaler().fit(train[columns])
                reg = Ridge(alpha=len(train), fit_intercept=True, solver="svd").fit(scaler.transform(train[columns]), y)
                measured = float(reg.predict(scaler.transform(pd.DataFrame([row[columns].to_dict()])))[0])
                saved = coefficient_groups[(prediction.anchor, model)].loc[columns]
                assert np.allclose(scaler.mean_, saved.training_mean)
                assert np.allclose(scaler.scale_, saved.training_scale)
                assert np.allclose(reg.coef_, saved.coefficient_standardized)
                assert np.allclose(reg.intercept_, saved.intercept_bps)
            max_prediction_error = max(max_prediction_error, abs(measured-getattr(prediction, model)))
    assert max_prediction_error < 1e-8
    # Alter every uncompleted label: a causal training set and its prediction
    # must stay unchanged. This includes the current anchor's future target.
    for row in predictions.iloc[[0, len(predictions)//2, -1]].itertuples():
        altered = f.copy()
        unavailable = altered.target_end.gt(row.formation_date) | altered.target_end.isna()
        altered.loc[unavailable, "target_mean_bps"] = 1e9
        mask = (altered.formation_date < row.formation_date) & altered.target_end.le(row.formation_date) & finite_features
        train = altered.loc[mask]
        assert np.array_equal(train.anchor, member_groups[row.anchor])
        scaler = StandardScaler().fit(train[basic])
        model = Ridge(alpha=len(train), solver="svd").fit(scaler.transform(train[basic]), train.target_mean_bps)
        current = f.set_index("anchor").loc[row.anchor, basic]
        assert np.isclose(model.predict(scaler.transform(pd.DataFrame([current.to_dict()])))[0], row.Simple)
    expected_daily = strategy.loc[pnl.date.min():pnl.date.max()].index
    assert pd.DatetimeIndex(pnl.date).equals(expected_daily) and pnl.date.is_unique
    predictions_by_anchor = predictions.set_index("anchor")
    for row in pnl.itertuples():
        prediction = predictions_by_anchor.loc[row.prediction_anchor]
        t = panel.index.get_loc(row.date)
        assert int(prediction.signal_index)+1 <= t <= int(prediction.signal_index)+5
        raw_return = strategy.loc[row.date, "gross_return"]
        assert np.isclose(row.AlwaysOn, raw_return)
        for model in models:
            active = prediction[model] > 0
            assert getattr(row, model+"_active") == active
            assert np.isclose(getattr(row, model), raw_return if active else 0.)
    # Separate implementation of both moving-block bootstrap families.
    def indices(n, length, seed):
        generator = np.random.default_rng(seed)
        starts = generator.integers(n, size=(1000, int(np.ceil(n/length))))
        return ((starts[:, :, None]+np.arange(length)) % n).reshape(1000, -1)[:, :n]
    def check_comparison(values, sample, expected):
        center = np.mean(values, axis=0); draws = np.mean(values[sample], axis=1)
        point = np.quantile(draws, [.025, .975], axis=0)
        se = np.std(draws, axis=0, ddof=1)
        standardized = np.divide(draws-center, se, out=np.zeros_like(draws), where=se > 1e-12)
        critical = np.quantile(np.max(abs(standardized), axis=1), .95)
        assert np.allclose(expected.difference, center)
        assert np.allclose(expected.point95_low, point[0]) and np.allclose(expected.point95_high, point[1])
        assert np.allclose(expected.sim95_low, center-critical*se)
        assert np.allclose(expected.sim95_high, center+critical*se)
    augmented = ["SimplePlusStockPD", "SimplePlusLagPD"]
    for pi, period in enumerate(["development", "later"]):
        pred = predictions.loc[predictions.score_period.eq(period) & predictions.target_mean_bps.notna()].sort_values("formation_date")
        y = pred.target_mean_bps.to_numpy(); sample = indices(len(pred), 12, spec["seed"]+pi)
        for model in models:
            mse = (pred[model].to_numpy()-y)**2
            saved = forecast_metrics.loc[forecast_metrics.period.eq(period) & forecast_metrics.model.eq(model)].iloc[0]
            assert np.isclose(saved.MSE_bps_squared, mse.mean())
            assert np.allclose(np.quantile(mse[sample].mean(axis=1), [.025, .975]), [saved.MSE_low, saved.MSE_high])
            for sign, mask in [("positive", pred[model].to_numpy()>0), ("nonpositive", pred[model].to_numpy()<=0)]:
                saved = calibration.loc[calibration.period.eq(period) & calibration.model.eq(model) & calibration.forecast_sign.eq(sign)].iloc[0]
                assert saved.forecasts == int(mask.sum())
                if mask.any():
                    assert np.isclose(saved.mean_future_target_bps, y[mask].mean())
                    assert np.isclose(saved.mean_prediction_bps, pred[model].to_numpy()[mask].mean())
                    denominator = mask[sample].sum(axis=1)
                    numerator = (mask*y)[sample].sum(axis=1)
                    conditional = np.divide(numerator, denominator, out=np.full(1000, np.nan), where=denominator>0)
                    assert np.allclose(np.nanquantile(conditional, [.025,.975]), [saved.target_low, saved.target_high])
        difference = np.column_stack([(pred[m].to_numpy()-y)**2-(pred.Simple.to_numpy()-y)**2 for m in augmented])
        expected = comparisons.loc[comparisons.period.eq(period) & comparisons.metric.eq("forecast_MSE_bps_squared")].set_index("comparison").loc[[m+"_minus_Simple" for m in augmented]]
        check_comparison(difference, sample, expected)
        calendar = pnl.loc[pnl.period.eq(period)].sort_values("date")
        sample = indices(len(calendar), 60, spec["seed"]+50+pi)
        for model in ["AlwaysOn", *models]:
            values = calendar[model].to_numpy()
            saved = gate_metrics.loc[gate_metrics.period.eq(period) & gate_metrics.model.eq(model)].iloc[0]
            assert np.isclose(saved.mean_daily_bps, values.mean()*1e4)
            assert np.allclose(np.quantile(values[sample].mean(axis=1)*1e4, [.025, .975]), [saved.mean_low, saved.mean_high])
            assert np.isclose(saved.total_gross_return, np.prod(1+values)-1)
            assert np.isclose(saved.active_fraction, 1. if model == "AlwaysOn" else calendar[model+"_active"].mean())
        difference = np.column_stack([(calendar[m]-calendar.Simple).to_numpy()*1e4 for m in augmented])
        expected = comparisons.loc[comparisons.period.eq(period) & comparisons.metric.eq("gate_mean_bps_per_calendar_day")].set_index("comparison").loc[[m+"_minus_Simple" for m in augmented]]
        check_comparison(difference, sample, expected)
    for path, digest in result["protected_sha256"].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest
    report = {"checks": {"reference_membership_formed_at_first_past_window": True,
        "all_features_targets_and_trailing_strategy_chronology_checked": True,
        "nine_feature_windows_reconstructed_from_covariance_eigenvectors": True,
        "H0_summaries_match_MST_and_essential_intervals_excluded": True,
        "all_saved_diagram_summaries_reconciled": True,
        "all_training_memberships_use_only_completed_prior_labels": True,
        "all_forecasts_scalers_and_coefficients_match_independent_sklearn_ridge": True,
        "uncompleted_future_label_perturbations_do_not_change_predictions": True,
        "all_daily_gates_and_zero_flat_days_reproduce": True,
        "all_forecast_and_gate_intervals_and_paired_simultaneous_bands_reproduce": True,
        "all_sign_calibration_counts_means_and_conditional_intervals_reproduce": True,
        "prior_inputs_and_results_unchanged": True},
        "max_independent_feature_error": max_feature_error, "max_independent_forecast_error_bps": max_prediction_error,
        "forecast_rows_checked": len(predictions), "daily_calendar_rows_checked": len(pnl),
        "source_sha256": result["source_sha256"], "audit_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/"independent_audit.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
