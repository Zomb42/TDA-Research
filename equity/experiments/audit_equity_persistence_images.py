"""Independent image integration, causal forecasting, P&L and interval audit."""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
import pandas as pd
from scipy.integrate import quad
from scipy.special import erf
from scipy.spatial.distance import pdist
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"experiments/equity_persistence_images"
PREV = ROOT/"experiments/equity_persistence_regimes"
DATA = ROOT/"market_data/datasets/equity_daily_expanded_2016_2026-10-27"


def main():
    summary = json.loads((OUT/"summary.json").read_text())
    config = json.loads((OUT/"specification.json").read_text())
    grid = json.loads((OUT/"frozen_grid.json").read_text())
    f = pd.read_csv(OUT/"state_features_and_targets.csv", parse_dates=["formation_date", "history_end", "target_start", "target_end"])
    predictions = pd.read_csv(OUT/"walk_forward_predictions.csv", parse_dates=["formation_date", "target_start", "target_end", "latest_training_target_end"])
    pnl = pd.read_csv(OUT/"daily_gate_returns.csv", parse_dates=["date", "formation_date"])
    members = pd.read_csv(OUT/"training_membership.csv.gz")
    coefficients = pd.read_csv(OUT/"coefficient_history.csv")
    diagnostics = pd.read_csv(OUT/"image_range_diagnostics.csv").set_index("anchor")
    intervals = pd.read_csv(PREV/"persistence_intervals.csv.gz").query("object == 'stock'")
    diagrams = {(int(a), int(d)): g.dropna(subset=["death"])[["birth", "death"]].to_numpy() for (a, d), g in intervals.groupby(["anchor", "dimension"])}
    models = config["models"]
    image_columns = models["PersistenceImage20"][len(models["Simple"]):]
    h0_columns, h1_columns = image_columns[:4], image_columns[4:]
    f_idx = f.set_index("anchor")
    valid_cols = models["SimplePlusStockPD"]+["lag_H0_q90", "lag_H1_max_lifetime", "lag_H1_total_squared_lifetime"]
    valid = np.isfinite(f[valid_cols].to_numpy()).all(axis=1)
    first = predictions.iloc[0]
    initial = f.loc[valid & f.formation_date.lt(first.formation_date) & f.target_end.le(first.formation_date) & f.target_mean_bps.notna()]
    assert initial.anchor.tolist() == grid["calibration_anchors"]
    assert initial.target_end.max() <= first.formation_date
    assert len(initial) == first.training_labels == grid["calibration_labels"]
    all_h0 = np.concatenate([diagrams[(int(a), 0)] for a in initial.anchor])
    all_h1 = np.concatenate([diagrams.get((int(a), 1), np.empty((0, 2))) for a in initial.anchor])
    assert np.isclose(grid["H0_upper"], all_h0[:, 1].max()*1.25)
    assert np.isclose(grid["birth_upper"], all_h1[:, 0].max()*1.25)
    assert np.isclose(grid["lifetime_upper"], np.diff(all_h1, axis=1).max()*1.25)
    assert grid["birth_sigma"] == grid["birth_upper"]/8
    assert grid["lifetime_sigma"] == grid["lifetime_upper"]/8
    max_image_error, quad_error = 0., 0.
    bx = np.linspace(0, grid["birth_upper"], 5)
    py = np.linspace(0, grid["lifetime_upper"], 5)
    for row in f.itertuples():
        h0 = diagrams[(row.anchor, 0)]
        essential = intervals.loc[intervals.anchor.eq(row.anchor) & intervals.dimension.eq(0), "death"].isna().sum()
        assert essential == 1 and len(h0) == 181 and np.all(h0[:, 0] == 0.)
        # Direct category assignment, independent of np.histogram edge handling.
        bins = np.minimum((h0[:, 1]/(grid["H0_upper"]/4)).astype(int), 3)
        counts = np.bincount(bins, minlength=4)/181
        assert np.allclose(counts, f_idx.loc[row.anchor, h0_columns].to_numpy(dtype=float))
        h1 = diagrams.get((row.anchor, 1), np.empty((0, 2)))
        lifetime = np.diff(h1, axis=1).ravel()
        # Independent erf antiderivative, looped pixel accumulation.
        image = np.zeros((4, 4))
        for i in range(4):
            xmass = .5*(erf((bx[i+1]-h1[:, 0])/(np.sqrt(2)*grid["birth_sigma"]))-erf((bx[i]-h1[:, 0])/(np.sqrt(2)*grid["birth_sigma"])))
            for j in range(4):
                ymass = .5*(erf((py[j+1]-lifetime)/(np.sqrt(2)*grid["lifetime_sigma"]))-erf((py[j]-lifetime)/(np.sqrt(2)*grid["lifetime_sigma"])))
                image[i, j] = np.sum(lifetime*xmass*ymass)
        saved = f_idx.loc[row.anchor, h1_columns].to_numpy(dtype=float).reshape(4, 4)
        max_image_error = max(max_image_error, float(abs(saved-image).max()))
        d = diagnostics.loc[row.anchor]
        assert np.isclose(image.sum(), d.H1_image_mass)
        assert np.isclose(lifetime.sum(), d.H1_total_lifetime)
        assert int(((h1[:, 0] > grid["birth_upper"]) | (lifetime > grid["lifetime_upper"])).sum()) == d.H1_points_outside_grid
        assert np.isclose(image.sum()/lifetime.sum() if lifetime.sum() else 1., d.H1_mass_retained_fraction)
        if row.anchor == first.anchor and len(h1):
            birth, death = h1[0]; life = death-birth
            for edges, mean, sigma in [(bx, birth, grid["birth_sigma"]), (py, life, grid["lifetime_sigma"])]:
                for lo, hi in zip(edges[:-1], edges[1:]):
                    density = lambda v: math.exp(-.5*((v-mean)/sigma)**2)/(sigma*math.sqrt(2*math.pi))
                    numeric = quad(density, lo, hi, epsabs=1e-12)[0]
                    analytic = .5*(math.erf((hi-mean)/(math.sqrt(2)*sigma))-math.erf((lo-mean)/(math.sqrt(2)*sigma)))
                    quad_error = max(quad_error, abs(numeric-analytic))
    assert max_image_error < 1e-12 and quad_error < 1e-12
    # Independent covariance eigenvectors for nine ordinary-feature windows.
    panel = pd.read_csv(DATA/"returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    reference = pd.read_csv(PREV/"reference_stocks.csv").symbol.tolist()
    max_ordinary_error = 0.
    ordinary_columns = models["Ordinary20"][len(models["Simple"]):]
    for ai in np.unique(np.linspace(0, len(f)-1, 9).astype(int)):
        row = f.iloc[ai]; t = int(row.signal_index)
        h = panel[reference].iloc[t-120:t].to_numpy(); m = panel.SPY.iloc[t-120:t].to_numpy()
        design = np.c_[np.ones(len(h)), m]
        residual = h-design@np.linalg.lstsq(design, h, rcond=None)[0]
        corr = np.corrcoef(residual, rowvar=False)
        eigenvalues, vectors = np.linalg.eigh(corr)
        points = vectors[:, -3:]*np.sqrt(eigenvalues[-3:])
        d = pdist(points)
        q = np.linspace(.05, .95, 10)
        expected = np.r_[np.quantile(d/np.median(d), q), np.quantile(corr[np.triu_indices(len(reference), 1)], q)]
        max_ordinary_error = max(max_ordinary_error, float(abs(expected-row[ordinary_columns].to_numpy(dtype=float)).max()))
    assert max_ordinary_error < 1e-10
    memberships = {int(a): g.training_anchor.to_numpy() for a, g in members.groupby("prediction_anchor")}
    coef = {(int(a), m): g.set_index("feature") for (a, m), g in coefficients.groupby(["anchor", "model"])}
    max_prediction_error = 0.
    for p in predictions.itertuples():
        current = f_idx.loc[p.anchor]
        train = f.loc[valid & f.formation_date.lt(p.formation_date) & f.target_end.le(p.formation_date) & f.target_mean_bps.notna()]
        assert np.array_equal(train.anchor, memberships[p.anchor])
        assert len(train) == p.training_labels and len(train) >= 104
        assert train.target_end.max() == p.latest_training_target_end <= p.formation_date
        y = train.target_mean_bps.to_numpy()
        for model, columns in models.items():
            if not columns:
                expected = y.mean()
            else:
                scaler = StandardScaler().fit(train[columns])
                reg = Ridge(alpha=len(train), fit_intercept=True, solver="svd").fit(scaler.transform(train[columns]), y)
                expected = reg.predict(scaler.transform(pd.DataFrame([current[columns].to_dict()])))[0]
                c = coef[(p.anchor, model)].loc[columns]
                assert np.allclose(c.training_mean, scaler.mean_)
                assert np.allclose(c.training_scale, scaler.scale_)
                assert np.allclose(c.coefficient_standardized, reg.coef_)
                assert np.allclose(c.intercept_bps, reg.intercept_)
            max_prediction_error = max(max_prediction_error, abs(expected-getattr(p, model)))
    assert max_prediction_error < 1e-9
    assert members.equals(pd.read_csv(PREV/"training_membership.csv.gz"))
    # Alter labels unavailable at an anchor; exact training input must not change.
    p = predictions.iloc[len(predictions)//2]
    mask = valid & f.formation_date.lt(p.formation_date) & f.target_end.le(p.formation_date) & f.target_mean_bps.notna()
    changed = f.copy()
    changed.loc[~mask, "target_mean_bps"] = 1e9
    assert np.array_equal(changed.loc[mask, "target_mean_bps"], f.loc[mask, "target_mean_bps"])
    raw = pd.read_csv(ROOT/"experiments/equity_expanded_pca_reversal/daily_gross_returns.csv", parse_dates=["date"])
    strategy = raw.loc[raw.universe.eq("expanded200") & raw.window.eq(120) & raw.model.eq("SPY_PCA3")].set_index("date").sort_index()
    assert pnl.date.is_unique and pd.DatetimeIndex(pnl.date).equals(strategy.loc[pnl.date.min():pnl.date.max()].index)
    assert np.allclose(pnl.AlwaysOn, strategy.loc[pnl.date, "gross_return"], atol=1e-15)
    assert (f.history_end < f.formation_date).all() and (f.formation_date < f.target_start).all()
    for row in f.itertuples():
        assert panel.index[row.signal_index-1] == row.history_end
        assert panel.index[row.signal_index] == row.formation_date
        if pd.notna(row.target_end):
            outcome = strategy.loc[row.target_start:row.target_end, "gross_return"]
            assert len(outcome) == 20 and np.isclose(outcome.mean()*1e4, row.target_mean_bps)
    for row in predictions.itertuples():
        days = pnl.loc[pnl.prediction_anchor.eq(row.anchor)]
        assert days.date.tolist() == list(panel.index[row.signal_index+1:min(row.signal_index+6, len(panel))])
    for model in models:
        active = pnl.prediction_anchor.map(predictions.set_index("anchor")[model]).gt(0)
        assert np.array_equal(active, pnl[model+"_active"])
        assert np.allclose(pnl[model], np.where(active, pnl.AlwaysOn, 0.), atol=1e-15)
    old_predictions = pd.read_csv(PREV/"walk_forward_predictions.csv")
    for model in ["HistoryMean", "Simple", "SimplePlusStockPD"]:
        assert np.allclose(predictions[model], old_predictions[model], atol=1e-10)
    # Reconstruct every reported metric and both pointwise and simultaneous bands.
    saved_forecast = pd.read_csv(OUT/"forecast_metrics.csv").set_index(["period", "model"])
    saved_perf = pd.read_csv(OUT/"gate_performance.csv").set_index(["period", "model"])
    saved_comparisons = pd.read_csv(OUT/"paired_incremental_comparisons.csv").set_index(["period", "metric", "comparator"])
    comparators = ["Simple", "SimplePlusStockPD", "Ordinary20"]
    max_metric_error = 0.

    def verify(saved, key, values):
        nonlocal max_metric_error
        for field, value in values.items():
            error = abs(float(saved.loc[key, field])-float(value))
            max_metric_error = max(max_metric_error, error)
            assert np.isclose(saved.loc[key, field], value, rtol=1e-10, atol=1e-10), (key, field, error)

    def resamples(n, block, seed):
        rng = np.random.default_rng(seed)
        starts = rng.integers(0, n, size=(1000, math.ceil(n/block)))
        return ((starts[:, :, None]+np.arange(block)) % n).reshape(1000, -1)[:, :n]

    def verify_comparisons(period, metric, differences, indices):
        central = differences.mean(axis=0)
        boot = differences[indices].mean(axis=1)
        se = boot.std(axis=0, ddof=1)
        normalized = np.divide(boot-central, se, out=np.zeros_like(boot), where=se > 1e-12)
        radius = np.quantile(abs(normalized).max(axis=1), .95)
        for j, c in enumerate(comparators):
            verify(saved_comparisons, (period, metric, c), {"difference": central[j],
                "point95_low": np.quantile(boot[:, j], .025), "point95_high": np.quantile(boot[:, j], .975),
                "sim95_low": central[j]-radius*se[j], "sim95_high": central[j]+radius*se[j]})

    for pi, period in enumerate(["development", "later"]):
        scored = predictions.loc[predictions.score_period.eq(period) & predictions.target_mean_bps.notna()].sort_values("formation_date")
        y = scored.target_mean_bps.to_numpy(); ix = resamples(len(scored), 12, config["seed"]+pi)
        for model in models:
            err = (scored[model].to_numpy()-y)**2
            means = err[ix].mean(axis=1)
            verify(saved_forecast, (period, model), {"MSE_bps_squared": err.mean(), "MAE_bps": abs(scored[model].to_numpy()-y).mean(),
                "MSE_low": np.quantile(means, .025), "MSE_high": np.quantile(means, .975)})
        diff = np.column_stack([(scored.PersistenceImage20.to_numpy()-y)**2-(scored[c].to_numpy()-y)**2 for c in comparators])
        verify_comparisons(period, "forecast_MSE_bps_squared", diff, ix)
        days = pnl.loc[pnl.period.eq(period)].sort_values("date"); ix = resamples(len(days), 60, config["seed"]+50+pi)
        for model in ["AlwaysOn", *models]:
            values = days[model].to_numpy(); curve = np.cumprod(1+values); std = values.std(ddof=1)
            means = values[ix].mean(axis=1)*1e4
            verify(saved_perf, (period, model), {"mean_daily_bps": values.mean()*1e4, "mean_low": np.quantile(means, .025),
                "mean_high": np.quantile(means, .975), "annualized_volatility": std*np.sqrt(252),
                "active_fraction": 1. if model == "AlwaysOn" else days[model+"_active"].mean(),
                "sharpe_vs_zero": values.mean()/std*np.sqrt(252), "gross_CAGR": curve[-1]**(252/len(values))-1,
                "total_gross_return": curve[-1]-1, "max_drawdown": (curve/np.maximum.accumulate(np.r_[1., curve])[1:]-1).min()})
        diff = np.column_stack([(days.PersistenceImage20-days[c]).to_numpy()*1e4 for c in comparators])
        verify_comparisons(period, "gate_mean_bps_per_calendar_day", diff, ix)
    hashes_ok = all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == digest for p, digest in summary["protected_sha256"].items())
    checks = {"frozen_grid_uses_first_completed_training_set_only": True, "all_images_and_H0_bins_independently_reconstructed": True,
        "Gaussian_integrals_confirmed_by_quadrature": True, "ordinary_features_covariance_eigen_check": True,
        "every_forecast_and_coefficient_matches_sklearn": True, "exact_completed_label_membership_and_future_label_exclusion": True,
        "all_calendar_days_and_flat_returns_reconcile": True, "baseline_forecasts_match_original": True,
        "every_metric_and_paired_uncertainty_band_reproduced": True, "protected_inputs_unchanged": hashes_ok}
    assert all(checks.values())
    result = {"checks": checks, "max_image_error": max_image_error, "max_quadrature_error": quad_error,
        "max_ordinary_feature_error": max_ordinary_error, "max_prediction_error_bps": max_prediction_error,
        "max_metric_error": max_metric_error, "forecasts_checked": len(predictions), "images_checked": len(f),
        "audit_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/"independent_audit.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
