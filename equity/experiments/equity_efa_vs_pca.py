"""Matched SPY + three statistical factors: EFA versus PCA, gross/pre-fee."""
from pathlib import Path
import hashlib
import json
import time
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.linalg import subspace_angles
from sklearn.decomposition import FactorAnalysis
from sklearn.exceptions import ConvergenceWarning
import sklearn

from equity_residual_backtest import construct

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/"market_data/datasets/equity_daily_expanded_2016_2026-10-27"
BASE = ROOT/"experiments/equity_expanded_pca_reversal"
OUT = ROOT/"experiments/equity_efa_vs_pca"
MODELS = ["PCA3", "EFA3"]
CONFIG = {
    "decision_date": "2026-10-29", "status": "exploratory comparison on previously examined history/current-survivor candidate universe",
    "hypothesis": "explicit heterogeneous unique variances may estimate shared factors better than PCA; whether the resulting residuals reverse is a separate test",
    "universe": "same expanded200 candidates and daily admission: 272 complete prior contiguous log returns, no future availability filter",
    "fit": "120 prior observations ending t-1; stockwise intercept+SPY fit; demean/standardize residuals with sample SD floor0.0001",
    "PCA": "top3 right singular vectors of the standardized residual matrix",
    "EFA": "sklearn FactorAnalysis, three factors, lapack SVD, no rotation, tol0.001, max_iter1000, default all-ones unique variance initialization, no warm start or outcome-based model selection",
    "raw_exposures": "residual_sigma[:,None] times PCA vectors or EFA loading matrix; add ones and past SPY beta; rank5",
    "signal": "same one-day vendor-adjusted close-close log return at t",
    "portfolio": "same cross-sectional WLS and holdings -W*residual / sum(abs(W*residual)); W=inverse prior total-return variance, sigma floor0.0001; no caps",
    "not_changed": "do not replace portfolio W by EFA unique variances or use posterior factor scores as a different trading signal",
    "execution": "next vendor raw daily-bar open to same-day raw close, ideal fractional dollars, unit gross, flat nightly, no gate",
    "primary": "paired EFA3 minus PCA3 daily gross mean, 1000 circular60-day bootstrap, approximate95 interval separately per period",
    "horizon_secondary": "same common complete20 dates as previous study; frozen initial sleeves, cumulative all-adjusted next-open to 1/5/20-close; mean profit and e'W R/e'W e response slope",
    "structural_secondary": "every20 formation dates with complete next20 returns and no split crossing; future WLS residual mean absolute pair correlation using past-fixed exposures/W, and raw loading-subspace overlap with previous diagnostic block on common stocks",
    "structure_interpretation": "future common-return coefficients are ex-post decompositions only, never used in trading; raw subspace overlap = ||Qprev'Qcurrent||F^2/3, rotation-invariant, not economic-factor identification",
    "uncertainty_secondary": "60-day blocks for overlapping daily horizon events; three diagnostic-block draws for structural summaries; simultaneous two-metric structural bands, three-horizon bands separately for event means/slopes; no correction across project history",
    "periods": "entry before2024 development, otherwise later; later already examined, not untouched holdout",
    "checks": "full saved PCA holdings/returns/events reconciliation; EFA convergence/likelihood/uniqueness logs; rotation/column-scale invariance; independent WLS and EM likelihood audit",
    "fees": "excluded entirely", "seed": 2026102961,
}
COLORS = {"PCA3": "#277da1", "EFA3": "#e58a20"}


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def fit(history, market):
    design = np.c_[np.ones(len(market)), market]
    market_fit = np.linalg.lstsq(design, history, rcond=None)[0]
    residual = history-design@market_fit
    scale = np.maximum(residual.std(axis=0, ddof=1), .0001)
    z = (residual-residual.mean(axis=0))/scale
    _, _, vt = np.linalg.svd(z, full_matrices=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        fa = FactorAnalysis(n_components=3, svd_method="lapack", tol=.001, max_iter=1000, rotation=None, random_state=0).fit(z)
    if caught or fa.n_iter_ >= 1000: raise RuntimeError("EFA failed convergence: "+str([str(w.message) for w in caught]))
    assert np.all(np.diff(fa.loglike_) > -1e-6) and (fa.noise_variance_ > 0).all()
    raw = {"PCA3": scale[:, None]*vt[:3].T, "EFA3": scale[:, None]*fa.components_.T}
    exposure = {k: np.c_[np.ones(len(scale)), market_fit[1], v] for k, v in raw.items()}
    weights = 1/np.maximum(history.std(axis=0, ddof=1), .0001)**2
    info = {"iterations": int(fa.n_iter_), "last_loglike_gain": float(fa.loglike_[-1]-fa.loglike_[-2]),
        "training_loglike": float(fa.loglike_[-1]), "unique_variance_min": float(fa.noise_variance_.min()),
        "unique_variance_median": float(np.median(fa.noise_variance_)), "unique_variance_max": float(fa.noise_variance_.max()),
        "common_variance_mean": float(np.mean(np.sum(fa.components_**2, axis=0))),
        "PCA_EFA_raw_subspace_overlap": overlap(raw["PCA3"], raw["EFA3"])}
    return exposure, weights, raw, market_fit[1], fa.noise_variance_, scale, info


def overlap(a, b):
    qa = np.linalg.qr(a, mode="reduced")[0]; qb = np.linalg.qr(b, mode="reduced")[0]
    return float(np.sum((qa.T@qb)**2)/3)


def future_corr(future, exposure, weights):
    scaled = exposure/np.sqrt(np.mean(exposure**2, axis=0))
    design = np.sqrt(weights)[:, None]*scaled
    beta = np.linalg.lstsq(design, np.sqrt(weights)[:, None]*future.T, rcond=None)[0]
    e = future.T-scaled@beta
    c = np.corrcoef(e)
    upper = c[np.triu_indices(len(c), 1)]
    assert np.isfinite(upper).all()
    return float(abs(upper).mean()), float(np.sqrt(np.mean(upper**2))), float(upper.mean())


def resamples(n, block, seed):
    rng = np.random.default_rng(seed)
    starts = rng.integers(n, size=(1000, int(np.ceil(n/block))))
    return ((starts[:, :, None]+np.arange(block)) % n).reshape(1000, -1)[:, :n]


def bands(values, indices):
    center = values.mean(axis=0); boot = values[indices].mean(axis=1); sd = boot.std(axis=0, ddof=1)
    z = np.divide(boot-center, sd, out=np.zeros_like(boot), where=sd > 1e-12)
    radius = np.quantile(abs(z).max(axis=1), .95)
    return center, np.quantile(boot, .025, axis=0), np.quantile(boot, .975, axis=0), center-radius*sd, center+radius*sd


def summarize(daily, events, diagnostics):
    performance, comparison, event_summary, structural = [], [], [], []
    for pi, period in enumerate(["development", "later"]):
        p = daily.loc[daily.period.eq(period)].pivot(index="date", columns="model", values="gross_return").sort_index()
        ix = resamples(len(p), 60, CONFIG["seed"]+pi)
        difference = (p.EFA3-p.PCA3).to_numpy()*1e4; boot = difference[ix].mean(axis=1)
        comparison.append({"period": period, "metric": "daily_mean_bps", "count": len(p), "difference": float(difference.mean()),
            "point95_low": float(np.quantile(boot, .025)), "point95_high": float(np.quantile(boot, .975)),
            "sim95_low": np.nan, "sim95_high": np.nan, "better_direction": "positive", "role": "primary"})
        for model in MODELS:
            r = p[model].to_numpy(); curve = np.cumprod(1+r); vol = r.std(ddof=1); means = r[ix].mean(axis=1)*1e4
            extra = daily.loc[daily.period.eq(period) & daily.model.eq(model)]
            performance.append({"period": period, "model": model, "days": len(p), "mean_daily_bps": float(r.mean()*1e4),
                "mean_low": float(np.quantile(means, .025)), "mean_high": float(np.quantile(means, .975)),
                "gross_CAGR": float(curve[-1]**(252/len(r))-1), "annualized_volatility": float(vol*np.sqrt(252)),
                "sharpe_vs_zero": float(r.mean()/vol*np.sqrt(252)), "total_gross_return": float(curve[-1]-1),
                "max_drawdown": float((curve/np.maximum.accumulate(np.r_[1., curve])[1:]-1).min()),
                "mean_effective_breadth": float(extra.effective_breadth.mean()), "max_position": float(extra.max_abs_position.max())})
        event_period = events.loc[events.period.eq(period)]
        dates = sorted(event_period.signal_date.unique()); ix = resamples(len(dates), 60, CONFIG["seed"]+10+pi)
        event_differences, slope_differences = [], []
        for horizon in [1, 5, 20]:
            frames = {}
            for model in MODELS:
                e = event_period.loc[event_period.model.eq(model) & event_period.horizon.eq(horizon)].sort_values("signal_date")
                assert e.signal_date.tolist() == dates
                r = e.gross_event_return.to_numpy()*1e4; boot = r[ix].mean(axis=1)
                a, b = e.cross_product.to_numpy(), e.signal_squared.to_numpy()
                slopes = a[ix].sum(axis=1)/b[ix].sum(axis=1)
                event_summary.append({"period": period, "model": model, "horizon": horizon, "events": len(e),
                    "mean_event_bps": float(r.mean()), "mean_low": float(np.quantile(boot, .025)), "mean_high": float(np.quantile(boot, .975)),
                    "response_slope": float(a.sum()/b.sum()), "slope_low": float(np.quantile(slopes, .025)), "slope_high": float(np.quantile(slopes, .975))})
                frames[model] = (r, a, b, slopes)
            event_differences.append(frames["EFA3"][0]-frames["PCA3"][0])
            slope_differences.append((frames["EFA3"][1].sum()/frames["EFA3"][2].sum()-frames["PCA3"][1].sum()/frames["PCA3"][2].sum(),
                frames["EFA3"][3]-frames["PCA3"][3]))
        stats = bands(np.column_stack(event_differences), ix)
        for j, horizon in enumerate([1, 5, 20]):
            comparison.append({"period": period, "metric": f"event{horizon}_mean_bps", "count": len(dates), "difference": stats[0][j],
                "point95_low": stats[1][j], "point95_high": stats[2][j], "sim95_low": stats[3][j], "sim95_high": stats[4][j], "better_direction": "positive", "role": "secondary"})
        center = np.array([v[0] for v in slope_differences]); boot = np.column_stack([v[1] for v in slope_differences]); sd = boot.std(axis=0, ddof=1)
        radius = np.quantile(abs((boot-center)/sd).max(axis=1), .95)
        for j, horizon in enumerate([1, 5, 20]):
            comparison.append({"period": period, "metric": f"event{horizon}_slope", "count": len(dates), "difference": center[j],
                "point95_low": np.quantile(boot[:, j], .025), "point95_high": np.quantile(boot[:, j], .975),
                "sim95_low": center[j]-radius*sd[j], "sim95_high": center[j]+radius*sd[j], "better_direction": "negative", "role": "secondary"})
        diag = diagnostics.loc[diagnostics.period.eq(period)]
        complete = diag.loc[diag.raw_subspace_stability.notna()]
        tables = {key: diag.pivot(index="signal_date", columns="model", values=key).sort_index() for key in ["future_mean_abs_corr", "future_RMS_corr"]}
        stable = complete.pivot(index="signal_date", columns="model", values="raw_subspace_stability").sort_index()
        for model in MODELS:
            structural.append({"period": period, "model": model, "future_blocks": len(tables["future_mean_abs_corr"]),
                "future_mean_abs_corr": float(tables["future_mean_abs_corr"][model].mean()), "future_RMS_corr": float(tables["future_RMS_corr"][model].mean()),
                "stability_blocks": len(stable), "mean_raw_subspace_stability": float(stable[model].mean())})
        # All diagnostic rows except the very first have a past comparison.
        common = tables["future_mean_abs_corr"].index.intersection(stable.index)
        values = np.c_[(tables["future_mean_abs_corr"].loc[common, "EFA3"]-tables["future_mean_abs_corr"].loc[common, "PCA3"]).to_numpy(),
                       (stable.loc[common, "EFA3"]-stable.loc[common, "PCA3"]).to_numpy()]
        ix = resamples(len(common), 3, CONFIG["seed"]+20+pi); stats = bands(values, ix)
        for j, metric in enumerate(["future_abs_corr", "subspace_stability"]):
            comparison.append({"period": period, "metric": metric, "count": len(common), "difference": stats[0][j],
                "point95_low": stats[1][j], "point95_high": stats[2][j], "sim95_low": stats[3][j], "sim95_high": stats[4][j],
                "better_direction": "negative" if j == 0 else "positive", "role": "secondary"})
    return pd.DataFrame(performance), pd.DataFrame(event_summary), pd.DataFrame(structural), pd.DataFrame(comparison)


def plots(daily, performance, events, diagnostics, fitting, comparison):
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), layout="constrained")
    for ax, period in zip(axes, ["development", "later"]):
        for model in MODELS:
            f = daily.loc[daily.model.eq(model) & daily.period.eq(period)].sort_values("date")
            ax.plot(f.date, 100*(np.cumprod(1+f.gross_return)-1), label=model, color=COLORS[model])
        ax.set(title=period.capitalize(), ylabel="Gross compounded return (%)"); ax.legend(); ax.axhline(0, color="black", lw=.5)
    fig.suptitle("Identical signal, weights and execution | SPY plus three factors | pre-fee")
    fig.savefig(OUT/"01_gross_profit.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), layout="constrained")
    for j, metric in enumerate(["daily_mean_bps", "future_abs_corr", "subspace_stability"]):
        rows = comparison.loc[comparison.metric.eq(metric)]
        for i, r in enumerate(rows.itertuples()):
            lo = r.point95_low if j == 0 else r.sim95_low; hi = r.point95_high if j == 0 else r.sim95_high
            axes[j].plot([lo, hi], [i, i], color="#e58a20", lw=3); axes[j].scatter(r.difference, i, color="black", zorder=3)
        axes[j].axvline(0, color="black", lw=.7)
        axes[j].set(yticks=range(2), yticklabels=rows.period.tolist(), xlabel="EFA minus PCA", title=["Daily mean (bps); positive favors EFA", "Future absolute correlation; negative favors EFA", "Subspace stability; positive favors EFA"][j])
    fig.suptitle("Primary paired95 daily intervals | secondary simultaneous95 structural bands")
    fig.savefig(OUT/"02_paired_comparisons.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), layout="constrained")
    for i, period in enumerate(["development", "later"]):
        for j, metric in enumerate(["mean_event_bps", "response_slope"]):
            for model in MODELS:
                f = events.loc[events.period.eq(period) & events.model.eq(model)]
                lower, upper = ("mean_low", "mean_high") if j == 0 else ("slope_low", "slope_high")
                x = f.horizon.to_numpy()+(-.12 if model == "PCA3" else .12)
                axes[i, j].errorbar(x, f[metric], yerr=np.c_[f[metric]-f[lower], f[upper]-f[metric]].T, fmt="o", label=model, color=COLORS[model])
            axes[i, j].axhline(0, color="black", lw=.7); axes[i, j].set(xticks=[1, 5, 20], xlabel="Frozen initial sleeve hold (sessions)", title=period+" | "+metric); axes[i, j].legend()
    fig.suptitle("Secondary direct 1/5/20-session response | common dates, pointwise95 bands")
    fig.savefig(OUT/"03_horizon_response.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(3, 1, figsize=(12, 8), layout="constrained")
    for model in MODELS:
        f = diagnostics.loc[diagnostics.model.eq(model)]
        axes[0].plot(f.signal_date, f.future_mean_abs_corr, label=model, color=COLORS[model])
        axes[1].plot(f.signal_date, f.raw_subspace_stability, label=model, color=COLORS[model])
    axes[0].set(ylabel="Mean absolute pair correlation", title="Next20 residuals, past-fixed exposures (ex-post diagnosis)"); axes[0].legend()
    axes[1].set(ylabel="Subspace overlap (0 to 1)", title="Past-only loading-space stability across diagnostic dates"); axes[1].legend()
    axes[2].plot(fitting.signal_date, fitting.iterations, color="#e58a20")
    axes[2].set(ylabel="EFA iterations", title="Convergence recorded on every daily fit")
    fig.savefig(OUT/"04_factor_diagnostics.png", dpi=160); plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    spec = OUT/"specification.json"
    if spec.exists() and json.loads(spec.read_text()) != CONFIG: raise ValueError("Existing specification differs")
    spec.write_text(json.dumps(CONFIG, indent=2)+"\n")
    protected_paths = [DATA/p for p in ["returns_log.csv", "universe.csv", "bars_raw.csv", "bars_all.csv"]]
    protected_paths += [BASE/p for p in ["daily_gross_returns.csv", "horizon_events.csv", "positions.npz", "summary.json"]]
    protected_paths += [ROOT/"experiments/equity_expanded_pca_reversal.py", ROOT/"experiments/equity_residual_backtest.py"]
    protected = {str(p.relative_to(ROOT)): sha(p) for p in protected_paths}
    symbols = pd.read_csv(DATA/"universe.csv").query("role == 'equity'").symbol.tolist()
    panel = pd.read_csv(DATA/"returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    x = panel[symbols].to_numpy(); m = panel.SPY.to_numpy()
    prices = {}
    for mode in ["raw", "all"]:
        bars = pd.read_csv(DATA/f"bars_{mode}.csv", parse_dates=["date"])
        prices[mode] = {field: bars.pivot(index="date", columns="symbol", values=field).reindex(index=panel.index, columns=symbols).to_numpy() for field in ["o", "c"]}
    ts = list(range(272, len(panel)-1)); n = len(ts)
    holdings = np.zeros((n, 2, len(symbols))); loadings = np.zeros((n, 2, len(symbols), 3))
    admitted = np.zeros((n, len(symbols)), dtype=bool); betas = np.zeros((n, len(symbols))); unique = np.full((n, len(symbols)), np.nan)
    residual_scales = np.full((n, len(symbols)), np.nan)
    daily, events, fitting, diagnostics = [], [], [], []
    previous_diagnostic = None; checks = {}; begin = time.monotonic()
    for di, t in enumerate(ts):
        idx = np.flatnonzero(np.isfinite(x[t-272:t]).all(axis=0)); admitted[di, idx] = True
        exposure, weights, raw, beta, psi, scales, info = fit(x[t-120:t, idx], m[t-120:t])
        betas[di, idx] = beta; unique[di, idx] = psi; residual_scales[di, idx] = scales
        fitting.append({"signal_date": panel.index[t], "training_end": panel.index[t-1], "stocks": len(idx), **info})
        period = "development" if panel.index[t+1] < pd.Timestamp("2024-01-01") else "later"
        event_ok = t+20 < len(panel) and ((panel.index[t+1] < pd.Timestamp("2024-01-01")) == (panel.index[t+20] < pd.Timestamp("2024-01-01")))
        future = prices["raw"]["c"][t+1, idx]/prices["raw"]["o"][t+1, idx]-1; assert np.isfinite(future).all()
        for mi, model in enumerate(MODELS):
            X = exposure[model]; assert np.linalg.matrix_rank(X) == 5
            h, e, error, condition = construct(x[t, idx], X, weights)
            holdings[di, mi, idx] = h; loadings[di, mi, idx] = raw[model]
            daily.append({"signal_date": panel.index[t], "date": panel.index[t+1], "training_end": panel.index[t-1], "period": period,
                "model": model, "stocks": len(idx), "gross_return": float(h@future), "max_exposure_error": error,
                "effective_breadth": float(1/np.sum(h**2)), "max_abs_position": float(abs(h).max()), "regression_condition": condition})
            if event_ok:
                for horizon in [1, 5, 20]:
                    response = prices["all"]["c"][t+horizon, idx]/prices["all"]["o"][t+1, idx]-1
                    assert np.isfinite(response).all()
                    events.append({"signal_date": panel.index[t], "entry": panel.index[t+1], "exit": panel.index[t+horizon], "period": period,
                        "model": model, "horizon": horizon, "gross_event_return": float(h@response),
                        "cross_product": float((e*weights)@response), "signal_squared": float((e*weights)@e)})
            if di % 20 == 0 and event_ok:
                abs_corr, rms_corr, signed_corr = future_corr(x[t+1:t+21, idx], X, weights)
                stability = np.nan; angle = np.nan; common_n = 0
                if previous_diagnostic is not None:
                    past_di = previous_diagnostic; common = np.flatnonzero(admitted[di] & admitted[past_di]); common_n = len(common)
                    a = loadings[past_di, mi, common]; b = loadings[di, mi, common]
                    stability = overlap(a, b); angle = float(np.degrees(subspace_angles(a, b).max()))
                diagnostics.append({"signal_date": panel.index[t], "entry": panel.index[t+1], "target_end": panel.index[t+20], "period": period,
                    "model": model, "stocks": len(idx), "future_mean_abs_corr": abs_corr, "future_RMS_corr": rms_corr, "future_signed_corr": signed_corr,
                    "raw_subspace_stability": stability, "largest_principal_angle_degrees": angle, "stability_common_stocks": common_n})
            if di == 0:
                rng = np.random.default_rng(9061); q = np.linalg.qr(rng.normal(size=(3, 3)))[0]
                rotated = X.copy(); rotated[:, 2:] = rotated[:, 2:]@q
                rescaled = X*np.array([1., 1., .2, 3., 17.])
                assert np.allclose(h, construct(x[t, idx], rotated, weights)[0], atol=1e-10)
                assert np.allclose(h, construct(x[t, idx], rescaled, weights)[0], atol=1e-10)
        if di % 20 == 0 and event_ok: previous_diagnostic = di
        if (di+1) % 200 == 0: print(f"Fitted {di+1}/{n} dates in {time.monotonic()-begin:.1f}s; EFA iterations={info['iterations']}", flush=True)
    daily, events, fitting, diagnostics = map(pd.DataFrame, [daily, events, fitting, diagnostics])
    for name, frame in [("daily_gross_returns", daily), ("horizon_events", events), ("fit_diagnostics", fitting), ("structural_blocks", diagnostics)]: frame.to_csv(OUT/(name+".csv"), index=False)
    np.savez_compressed(OUT/"positions_and_loadings.npz", holdings=holdings, raw_loadings=loadings, admitted=admitted,
        SPY_beta=betas, EFA_unique_variance=unique, residual_scale=residual_scales, symbols=np.array(symbols), signal_indices=np.array(ts), dates=np.array(panel.index[ts].astype(str)))
    performance, horizon_summary, structural, comparison = summarize(daily, events, diagnostics)
    for name, frame in [("gross_performance", performance), ("horizon_summary", horizon_summary), ("structural_summary", structural), ("paired_comparisons", comparison)]: frame.to_csv(OUT/(name+".csv"), index=False)
    old_daily = pd.read_csv(BASE/"daily_gross_returns.csv").query("universe == 'expanded200' and window == 120 and model == 'SPY_PCA3'")
    old_events = pd.read_csv(BASE/"horizon_events.csv").query("universe == 'expanded200' and window == 120 and model == 'SPY_PCA3'")
    saved_positions = np.load(BASE/"positions.npz")["expanded"][:, 0, 1]
    checks.update(full_PCA_positions_match_previous=bool(np.allclose(holdings[:, 0], saved_positions, atol=1e-10)),
        full_PCA_daily_returns_match_previous=bool(np.allclose(daily.loc[daily.model.eq("PCA3"), "gross_return"], old_daily.gross_return, atol=1e-12)),
        full_PCA_horizon_events_match_previous=bool(np.allclose(events.loc[events.model.eq("PCA3"), "gross_event_return"], old_events.gross_event_return, atol=1e-12)),
        all_EFA_fits_converged=True, raw_return_exposure_rank5_and_neutrality=True, orthogonal_rotation_and_column_scale_invariance=True,
        protected_inputs_unchanged=all(sha(p) == protected[str(p.relative_to(ROOT))] for p in protected_paths))
    assert all(checks.values()), checks
    plots(daily, performance, horizon_summary, diagnostics, fitting, comparison)
    summary = {"configuration": CONFIG, "checks": checks, "daily_dates": n, "daily_dates_by_period": daily.loc[daily.model.eq("PCA3")].groupby("period").size().to_dict(),
        "structural_blocks_by_period": diagnostics.loc[diagnostics.model.eq("PCA3")].groupby("period").size().to_dict(),
        "EFA_iterations": {"min": int(fitting.iterations.min()), "median": float(fitting.iterations.median()), "max": int(fitting.iterations.max())},
        "sklearn_version": sklearn.__version__, "source_sha256": sha(Path(__file__)), "protected_sha256": protected}
    (OUT/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print("CHECKS", checks, flush=True)
    for title, frame in [("GROSS", performance), ("STRUCTURAL", structural), ("HORIZON", horizon_summary), ("PAIRED", comparison)]: print(title+"\n"+frame.round(6).to_string(index=False), flush=True)
    print("ITERATIONS", summary["EFA_iterations"], flush=True)


if __name__ == "__main__": main()
