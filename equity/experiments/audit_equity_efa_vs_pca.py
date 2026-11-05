"""Independent WLS, Gaussian factor likelihood, EM-step and ledger audit."""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
import pandas as pd
from sklearn.decomposition import FactorAnalysis

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/"market_data/datasets/equity_daily_expanded_2016_2026-10-27"
BASE = ROOT/"experiments/equity_expanded_pca_reversal"
OUT = ROOT/"experiments/equity_efa_vs_pca"


def gaussian_loglike(z, loading, psi):
    # Matrix determinant lemma and Woodbury precision: no N-by-N inverse.
    inverse_noise = 1/psi
    small = np.eye(3)+loading.T@(inverse_noise[:, None]*loading)
    logdet = np.log(psi).sum()+np.linalg.slogdet(small)[1]
    adjusted = z*inverse_noise
    precision_z = adjusted-(adjusted@loading)@np.linalg.solve(small, loading.T*inverse_noise)
    return float(-.5*(len(z)*(z.shape[1]*np.log(2*np.pi)+logdet)+np.sum(z*precision_z)))


def em_step(z, loading, psi):
    posterior_cov = np.linalg.inv(np.eye(3)+loading.T@(loading/psi[:, None]))
    scores = z@(loading/psi[:, None])@posterior_cov
    second = posterior_cov+scores.T@scores/len(z)
    cross = z.T@scores/len(z)
    new_loading = np.linalg.solve(second, cross.T).T
    new_noise = np.maximum(np.mean(z*z, axis=0)-np.sum(new_loading*cross, axis=1), 1e-12)
    return new_loading, new_noise


def main():
    summary = json.loads((OUT/"summary.json").read_text()); config = summary["configuration"]
    saved = np.load(OUT/"positions_and_loadings.npz")
    symbols = saved["symbols"].tolist(); ts = saved["signal_indices"]
    positions = saved["holdings"]; loadings = saved["raw_loadings"]
    admitted = saved["admitted"]; betas = saved["SPY_beta"]
    noise = saved["EFA_unique_variance"]; residual_scales = saved["residual_scale"]
    daily = pd.read_csv(OUT/"daily_gross_returns.csv", parse_dates=["signal_date", "date", "training_end"])
    events = pd.read_csv(OUT/"horizon_events.csv", parse_dates=["signal_date", "entry", "exit"])
    diagnostics = pd.read_csv(OUT/"structural_blocks.csv", parse_dates=["signal_date", "entry", "target_end"])
    fitting = pd.read_csv(OUT/"fit_diagnostics.csv", parse_dates=["signal_date", "training_end"])
    panel = pd.read_csv(DATA/"returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    x = panel[symbols].to_numpy(); market = panel.SPY.to_numpy()
    price = {}
    for mode in ["raw", "all"]:
        bars = pd.read_csv(DATA/f"bars_{mode}.csv", parse_dates=["date"])
        price[mode] = {field: bars.pivot(index="date", columns="symbol", values=field).reindex(index=panel.index, columns=symbols).to_numpy() for field in ["o", "c"]}
    assert np.array_equal(ts, np.arange(272, len(panel)-1))
    assert np.allclose(positions[:, 0], np.load(BASE/"positions.npz")["expanded"][:, 0, 1], atol=1e-10)
    samples = set(np.unique(np.linspace(0, len(ts)-1, 13).astype(int)).tolist())
    max_position_error = 0.; max_likelihood_error = 0.; max_refit_cov_error = 0.; em_gains = []
    for di, t in enumerate(ts):
        expected = np.isfinite(x[t-272:t]).all(axis=0)
        assert np.array_equal(admitted[di], expected)
        idx = np.flatnonzero(expected); h = x[t-120:t, idx]; m = market[t-120:t]
        mc = m-m.mean(); centered = h-h.mean(axis=0)
        beta = mc@centered/(mc@mc)
        residual = centered-mc[:, None]*beta
        scale = np.maximum(residual.std(axis=0, ddof=1), .0001)
        z = (residual-residual.mean(axis=0))/scale
        assert np.allclose(betas[di, idx], beta) and np.allclose(residual_scales[di, idx], scale)
        weights = 1/np.maximum(h.std(axis=0, ddof=1), .0001)**2
        L = loadings[di, 1, idx]/scale[:, None]; psi = noise[di, idx]
        assert np.isfinite(psi).all() and (psi > 0).all()
        ll = gaussian_loglike(z, L, psi)
        max_likelihood_error = max(max_likelihood_error, abs(ll-fitting.iloc[di].training_loglike))
        assert fitting.iloc[di].training_end == panel.index[t-1] < panel.index[t]
        assert 1 < fitting.iloc[di].iterations < 1000
        if di in samples:
            covariance = z.T@z/119
            values, vectors = np.linalg.eigh(covariance); pca = scale[:, None]*vectors[:, np.argsort(values)[::-1][:3]]
            q1 = np.linalg.qr(pca)[0]; q2 = np.linalg.qr(loadings[di, 0, idx])[0]
            assert np.allclose(np.linalg.svd(q1.T@q2, compute_uv=False), 1., atol=1e-8)
            refit = FactorAnalysis(3, svd_method="lapack", tol=.001, max_iter=1000, rotation=None, random_state=0).fit(z)
            rebuilt = refit.components_.T@refit.components_+np.diag(refit.noise_variance_)
            measured = L@L.T+np.diag(psi)
            max_refit_cov_error = max(max_refit_cov_error, float(abs(rebuilt-measured).max()))
            next_loading, next_noise = em_step(z, L, psi)
            gain = gaussian_loglike(z, next_loading, next_noise)-ll
            assert gain >= -1e-6
            em_gains.append(float(gain))
        for mi in range(2):
            exposure = np.c_[np.ones(len(idx)), beta, loadings[di, mi, idx]]
            coefficient = np.linalg.solve(exposure.T@(weights[:, None]*exposure), exposure.T@(weights*x[t, idx]))
            e = x[t, idx]-exposure@coefficient
            holding = -weights*e/abs(weights*e).sum()
            max_position_error = max(max_position_error, float(abs(holding-positions[di, mi, idx]).max()))
            assert abs(exposure.T@holding).max() < 1e-9
            assert abs(positions[di, mi, ~admitted[di]]).sum() == 0
    assert max_position_error < 1e-9 and max_likelihood_error < 1e-5 and max_refit_cov_error < 1e-7
    print("Every WLS portfolio and EFA Gaussian likelihood reconstructed", flush=True)
    date_to_index = {d: i for i, d in enumerate(panel.index[ts])}
    max_ledger_error = 0.; max_structural_error = 0.
    for model, mi in [("PCA3", 0), ("EFA3", 1)]:
        rows = daily.loc[daily.model.eq(model)].sort_values("signal_date")
        assert np.array_equal(rows.signal_date, panel.index[ts]) and np.array_equal(rows.date, panel.index[ts+1])
        r = price["raw"]["c"][ts+1]/price["raw"]["o"][ts+1]-1
        for i in range(len(ts)): assert np.isfinite(r[i, admitted[i]]).all()
        expected = np.sum(positions[:, mi]*np.nan_to_num(r), axis=1)
        max_ledger_error = max(max_ledger_error, float(abs(expected-rows.gross_return.to_numpy()).max()))
        assert np.allclose(abs(positions[:, mi]).sum(axis=1), 1) and np.allclose(positions[:, mi].sum(axis=1), 0, atol=1e-10)
        for row in events.loc[events.model.eq(model)].itertuples():
            di = date_to_index[row.signal_date]; t = ts[di]; idx = np.flatnonzero(admitted[di])
            assert row.entry == panel.index[t+1] and row.exit == panel.index[t+row.horizon]
            assert (row.entry < pd.Timestamp("2024-01-01")) == (panel.index[t+20] < pd.Timestamp("2024-01-01"))
            response = price["all"]["c"][t+row.horizon, idx]/price["all"]["o"][t+1, idx]-1
            holding = positions[di, mi, idx]
            max_ledger_error = max(max_ledger_error, abs(holding@response-row.gross_event_return))
            h = x[t-120:t, idx]; weights = 1/np.maximum(h.std(axis=0, ddof=1), .0001)**2
            exposure = np.c_[np.ones(len(idx)), betas[di, idx], loadings[di, mi, idx]]
            coefficient = np.linalg.solve(exposure.T@(weights[:, None]*exposure), exposure.T@(weights*x[t, idx]))
            e = x[t, idx]-exposure@coefficient
            assert np.isclose((e*weights)@response, row.cross_product, atol=1e-8)
            assert np.isclose((e*weights)@e, row.signal_squared, atol=1e-8)
        previous_di = None
        for row in diagnostics.loc[diagnostics.model.eq(model)].sort_values("signal_date").itertuples():
            di = date_to_index[row.signal_date]; t = ts[di]; idx = np.flatnonzero(admitted[di])
            assert di % 20 == 0 and row.target_end == panel.index[t+20]
            weights = 1/np.maximum(x[t-120:t, idx].std(axis=0, ddof=1), .0001)**2
            exposure = np.c_[np.ones(len(idx)), betas[di, idx], loadings[di, mi, idx]]
            future = x[t+1:t+21, idx]
            coefficients_future = np.linalg.solve(exposure.T@(weights[:, None]*exposure), exposure.T@(weights[:, None]*future.T))
            e = future.T-exposure@coefficients_future
            covariance = np.cov(e); sd = np.sqrt(np.diag(covariance)); corr = covariance/np.outer(sd, sd)
            upper = corr[np.triu_indices(len(idx), 1)]
            for key, value in [("future_mean_abs_corr", abs(upper).mean()), ("future_RMS_corr", np.sqrt(np.mean(upper**2))), ("future_signed_corr", upper.mean())]:
                max_structural_error = max(max_structural_error, abs(value-getattr(row, key)))
            if previous_di is not None:
                common = np.flatnonzero(admitted[di] & admitted[previous_di])
                qa = np.linalg.qr(loadings[previous_di, mi, common])[0]; qb = np.linalg.qr(loadings[di, mi, common])[0]
                singular = np.linalg.svd(qa.T@qb, compute_uv=False)
                stable = np.mean(singular**2); angle = np.degrees(np.arccos(np.clip(singular.min(), -1, 1)))
                max_structural_error = max(max_structural_error, abs(stable-row.raw_subspace_stability), abs(angle-row.largest_principal_angle_degrees))
                assert row.stability_common_stocks == len(common)
            else: assert pd.isna(row.raw_subspace_stability)
            previous_di = di
    assert max_ledger_error < 1e-10 and max_structural_error < 1e-7
    performance = pd.read_csv(OUT/"gross_performance.csv").set_index(["period", "model"])
    event_summary = pd.read_csv(OUT/"horizon_summary.csv").set_index(["period", "model", "horizon"])
    structural = pd.read_csv(OUT/"structural_summary.csv").set_index(["period", "model"])
    comparisons = pd.read_csv(OUT/"paired_comparisons.csv").set_index(["period", "metric"])
    max_metric_error = 0.

    def verify(table, key, values):
        nonlocal max_metric_error
        for column, value in values.items():
            error = abs(float(table.loc[key, column])-float(value)); max_metric_error = max(max_metric_error, error)
            assert np.isclose(table.loc[key, column], value, atol=1e-9, rtol=1e-9), (key, column, error)

    def draws(n, block, seed):
        rng = np.random.default_rng(seed); starts = rng.integers(n, size=(1000, math.ceil(n/block)))
        return ((starts[:, :, None]+np.arange(block)) % n).reshape(1000, -1)[:, :n]

    def check_family(period, labels, center, boot):
        sd = boot.std(axis=0, ddof=1); standardized = np.divide(boot-center, sd, out=np.zeros_like(boot), where=sd > 1e-12)
        radius = np.quantile(abs(standardized).max(axis=1), .95)
        for j, label in enumerate(labels):
            verify(comparisons, (period, label), {"difference": center[j], "point95_low": np.quantile(boot[:, j], .025),
                "point95_high": np.quantile(boot[:, j], .975), "sim95_low": center[j]-radius*sd[j], "sim95_high": center[j]+radius*sd[j]})

    for pi, period in enumerate(["development", "later"]):
        p = daily.loc[daily.period.eq(period)].pivot(index="date", columns="model", values="gross_return").sort_index()
        ix = draws(len(p), 60, config["seed"]+pi)
        difference = (p.EFA3-p.PCA3).to_numpy()*1e4; boot = difference[ix].mean(axis=1)
        verify(comparisons, (period, "daily_mean_bps"), {"difference": difference.mean(), "point95_low": np.quantile(boot, .025), "point95_high": np.quantile(boot, .975)})
        for model in ["PCA3", "EFA3"]:
            r = p[model].to_numpy(); curve = np.cumprod(1+r); sd = r.std(ddof=1); boot = r[ix].mean(axis=1)*1e4
            rows = daily.loc[daily.period.eq(period) & daily.model.eq(model)]
            verify(performance, (period, model), {"mean_daily_bps": r.mean()*1e4, "mean_low": np.quantile(boot, .025), "mean_high": np.quantile(boot, .975),
                "gross_CAGR": curve[-1]**(252/len(r))-1, "annualized_volatility": sd*np.sqrt(252), "sharpe_vs_zero": r.mean()/sd*np.sqrt(252),
                "total_gross_return": curve[-1]-1, "max_drawdown": (curve/np.maximum.accumulate(np.r_[1., curve])[1:]-1).min(),
                "mean_effective_breadth": rows.effective_breadth.mean(), "max_position": rows.max_abs_position.max()})
        ep = events.loc[events.period.eq(period)]; dates = sorted(ep.signal_date.unique()); ix = draws(len(dates), 60, config["seed"]+10+pi)
        return_differences, slope_centers, slope_boots = [], [], []
        for horizon in [1, 5, 20]:
            records = {}
            for model in ["PCA3", "EFA3"]:
                e = ep.loc[ep.model.eq(model) & ep.horizon.eq(horizon)].sort_values("signal_date")
                assert e.signal_date.tolist() == dates
                r = e.gross_event_return.to_numpy()*1e4; a = e.cross_product.to_numpy(); b = e.signal_squared.to_numpy()
                boot_r = r[ix].mean(axis=1); boot_s = a[ix].sum(axis=1)/b[ix].sum(axis=1)
                verify(event_summary, (period, model, horizon), {"mean_event_bps": r.mean(), "mean_low": np.quantile(boot_r, .025), "mean_high": np.quantile(boot_r, .975),
                    "response_slope": a.sum()/b.sum(), "slope_low": np.quantile(boot_s, .025), "slope_high": np.quantile(boot_s, .975)})
                records[model] = (r, a.sum()/b.sum(), boot_s)
            return_differences.append(records["EFA3"][0]-records["PCA3"][0]); slope_centers.append(records["EFA3"][1]-records["PCA3"][1]); slope_boots.append(records["EFA3"][2]-records["PCA3"][2])
        diff = np.column_stack(return_differences)
        check_family(period, [f"event{h}_mean_bps" for h in [1, 5, 20]], diff.mean(axis=0), diff[ix].mean(axis=1))
        check_family(period, [f"event{h}_slope" for h in [1, 5, 20]], np.array(slope_centers), np.column_stack(slope_boots))
        dp = diagnostics.loc[diagnostics.period.eq(period)]
        for model in ["PCA3", "EFA3"]:
            rows = dp.loc[dp.model.eq(model)]
            verify(structural, (period, model), {"future_mean_abs_corr": rows.future_mean_abs_corr.mean(), "future_RMS_corr": rows.future_RMS_corr.mean(), "mean_raw_subspace_stability": rows.raw_subspace_stability.mean()})
        table = dp.pivot(index="signal_date", columns="model", values="future_mean_abs_corr").sort_index()
        stable = dp.dropna(subset=["raw_subspace_stability"]).pivot(index="signal_date", columns="model", values="raw_subspace_stability").sort_index()
        common = table.index.intersection(stable.index)
        diff = np.c_[(table.loc[common, "EFA3"]-table.loc[common, "PCA3"]).to_numpy(), (stable.loc[common, "EFA3"]-stable.loc[common, "PCA3"]).to_numpy()]
        ix = draws(len(common), 3, config["seed"]+20+pi)
        check_family(period, ["future_abs_corr", "subspace_stability"], diff.mean(axis=0), diff[ix].mean(axis=1))
    protected = all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == value for p, value in summary["protected_sha256"].items())
    checks = {"all_daily_admission_and_training_dates_causal": True, "all_raw_scaled_loadings_and_WLS_positions_reconstructed": True,
        "all_EFA_training_loglikelihoods_match_Gaussian_model": True, "selected_EFA_refits_match_saved_covariance": True,
        "independent_EM_step_likelihood_nondecrease": True, "all_raw_and_adjusted_return_ledgers_reconcile": True,
        "all_future_residual_correlations_and_rotation_invariant_stabilities_match": True,
        "all_metrics_and_paired_bootstrap_intervals_reproduced": True, "protected_prior_artifacts_unchanged": protected}
    assert all(checks.values())
    audit = {"checks": checks, "daily_formations_checked": len(ts), "independent_EFA_refits": len(samples),
        "max_position_error": max_position_error, "max_EFA_loglikelihood_error": max_likelihood_error,
        "max_EFA_refit_covariance_error": max_refit_cov_error, "maximum_additional_EM_step_loglike_gain": max(em_gains),
        "max_ledger_error": max_ledger_error, "max_structural_error": max_structural_error, "max_metric_error": max_metric_error,
        "audit_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/"independent_audit.json").write_text(json.dumps(audit, indent=2)+"\n")
    print(json.dumps(audit, indent=2), flush=True)


if __name__ == "__main__": main()
