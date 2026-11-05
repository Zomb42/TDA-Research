"""Post-evaluation diagnostics, not new holdout evidence or a parameter search.

Preserves the frozen backtest. Uses gross returns to separate signal weakness
from cost assumptions. Timing diagnostics include unattainable same-close entry.
"""

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd

from equity_residual_backtest import DATA, OUT as ORIGINAL_OUT, SPEC, construct, load_data, performance

OUT = Path(__file__).resolve().parent / "equity_residual_diagnostics"
DIAGNOSTIC_SPEC = {
    "status": "exploratory follow-up after original evaluation was examined",
    "regimes": "SPY 60-session trailing log return >=0 or <0, crossed with 20-session sample volatility annualized >=20% or <20%",
    "regime_information_end": "signal day close; before next-bar entry",
    "regime_threshold_selection": "fixed round 20% and zero; not optimized against strategy returns",
    "component_counts": [0, 1, 3, 5, 10],
    "all_other_trading_choices": "same as frozen original experiment",
    "timing": "adjusted previous-close to next-open hypothetical attribution; actual original raw open-close PnL retained separately",
    "uncertainty": "approximate Newey-West 5-lag conditional mean intervals on full calendar with zeros outside regime",
    "profit_plot_initial_equity": 100000,
}


def conditional_interval(returns, mask):
    # Influence-series HAC for a conditional mean; do not concatenate separated
    # regime days as though they were consecutive trading sessions.
    values = np.asarray(returns)
    mask = np.asarray(mask, dtype=bool)
    count = int(mask.sum())
    if count < 2:
        return np.nan, np.nan
    mean = values[mask].mean()
    influence = np.where(mask, values-mean, 0.)
    variance_sum = float(influence@influence)
    for lag in range(1, 6):
        variance_sum += 2*(1-lag/6)*float(influence[lag:]@influence[:-lag])
    se = np.sqrt(max(0., variance_sum))/count
    return float((mean-1.96*se)*10000), float((mean+1.96*se)*10000)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "diagnostic_specification.json").write_text(json.dumps(DIAGNOSTIC_SPEC, indent=2)+"\n")
    source = ORIGINAL_OUT / "evaluated"
    original_summary = (source / "summary.json").read_bytes()
    daily = pd.read_csv(source / "daily_returns_and_diagnostics.csv", parse_dates=["date", "signal_date"])
    positions = pd.read_csv(source / "daily_positions.csv", parse_dates=["date"])
    symbols, panel, raw_open, raw_close = load_data(False)
    adjusted_bars = pd.read_csv(DATA / "bars_all.csv", parse_dates=["date"])
    adj_open = adjusted_bars.pivot(index="date", columns="symbol", values="o").reindex(index=panel.index, columns=symbols)
    adj_close = adjusted_bars.pivot(index="date", columns="symbol", values="c").reindex(index=panel.index, columns=symbols)
    spy_trend = panel.SPY.rolling(60).sum()
    spy_vol = panel.SPY.rolling(20).std(ddof=1)*np.sqrt(252)
    labels = pd.DataFrame({"signal_date": panel.index, "spy_trailing_60_log_return": spy_trend,
                           "spy_trailing_20_annual_vol": spy_vol})
    labels["regime"] = np.where(labels.spy_trailing_20_annual_vol.ge(.20), "High vol", "Low vol") + "/" + np.where(labels.spy_trailing_60_log_return.ge(0), "Up trend", "Down trend")
    daily = daily.merge(labels, on="signal_date", validate="many_to_one")
    assert daily.regime.notna().all()
    annual_rows = []
    for (model, year), frame in daily.groupby(["model", daily.date.dt.year]):
        low_cost = frame.gross_return-frame.traded_notional*.0001-frame.short_notional*.01/252
        annual_rows.append({"model": model, "year": int(year),
                            "gross_return": float(np.prod(1+frame.gross_return)-1),
                            "one_bp_side_plus_1pct_borrow_return": float(np.prod(1+low_cost)-1),
                            "gross_mean_bps": float(frame.gross_return.mean()*10000)})
    pd.DataFrame(annual_rows).to_csv(OUT / "annual_gross_and_low_cost.csv", index=False)
    regime_rows = []
    for (period, model), frame in daily.groupby(["period", "model"], sort=False):
        frame = frame.sort_values("date")
        for regime in ["Low vol/Up trend", "Low vol/Down trend", "High vol/Up trend", "High vol/Down trend"]:
            mask = frame.regime.eq(regime).to_numpy()
            if not mask.any():
                continue
            lo, hi = conditional_interval(frame.gross_return, mask)
            subset = frame.loc[mask]
            regime_rows.append({"period": period, "model": model, "regime": regime,
                                "days": len(subset), "gross_mean_daily_bps": subset.gross_return.mean()*10000,
                                "gross_mean_hac95_low_bps": lo, "gross_mean_hac95_high_bps": hi,
                                "primary_cost_mean_daily_bps": subset.primary_cost_adjusted_return.mean()*10000,
                                "positive_gross_day_fraction": subset.gross_return.gt(0).mean()})
    regimes = pd.DataFrame(regime_rows)
    regimes.to_csv(OUT / "conditional_regimes.csv", index=False)

    timing_rows = []
    # Each row of weights was formed at the preceding signal close. We do not
    # claim those same closing prices were available for executing that signal.
    for model, frame in daily.groupby("model"):
        w = positions.loc[positions.model.eq(model)].pivot(index="date", columns="symbol", values="unit_gross_target_dollars").reindex(index=frame.date, columns=symbols).to_numpy()
        next_dates = pd.DatetimeIndex(frame.date)
        signal_dates = pd.DatetimeIndex(frame.signal_date)
        previous_close = adj_close.reindex(signal_dates).to_numpy()
        next_open = adj_open.reindex(next_dates).to_numpy()
        next_close = adj_close.reindex(next_dates).to_numpy()
        gap = next_open/previous_close-1
        intraday = next_close/next_open-1
        whole = next_close/previous_close-1
        overnight_pnl = np.sum(w*gap, axis=1)
        daytime_fixed_signal_shares = np.sum(w*(1+gap)*intraday, axis=1)
        whole_pnl = np.sum(w*whole, axis=1)
        assert np.allclose(overnight_pnl+daytime_fixed_signal_shares, whole_pnl, atol=1e-12)
        for i, row in enumerate(frame.itertuples()):
            timing_rows.append({"date": row.date, "model": model, "period": row.period,
                                "overnight_hypothetical_return": overnight_pnl[i],
                                "intraday_contribution_fixed_signal_close_shares": daytime_fixed_signal_shares[i],
                                "close_to_close_hypothetical_return": whole_pnl[i],
                                "original_intraday_raw_return": row.gross_return,
                                "overnight_weighted_log_return": float(w[i]@np.log1p(gap[i])),
                                "intraday_weighted_log_return": float(w[i]@np.log1p(intraday[i]))})
    timing = pd.DataFrame(timing_rows)
    timing.to_csv(OUT / "timing_daily.csv", index=False)
    timing_summary = []
    for (period, model), frame in timing.groupby(["period", "model"]):
        for field in ["overnight_hypothetical_return", "original_intraday_raw_return", "close_to_close_hypothetical_return"]:
            stats = performance(frame[field])
            timing_summary.append({"period": period, "model": model, "interval": field, **stats})
        overnight = frame.overnight_weighted_log_return.to_numpy()
        intraday = frame.intraday_weighted_log_return.to_numpy()
        total_var = np.var(overnight+intraday, ddof=1)
        variance = {"overnight_variance": float(np.var(overnight, ddof=1)),
                    "intraday_variance": float(np.var(intraday, ddof=1)),
                    "twice_covariance": float(2*np.cov(overnight, intraday, ddof=1)[0,1]),
                    "total_variance": float(total_var)}
        assert np.isclose(sum(variance[k] for k in ["overnight_variance", "intraday_variance", "twice_covariance"]), total_var)
        (OUT / f"variance_decomposition_{period}_{model}.json").write_text(json.dumps(variance, indent=2)+"\n")
    timing_summary = pd.DataFrame(timing_summary)
    timing_summary.to_csv(OUT / "timing_summary.csv", index=False)

    # A fixed, disclosed sensitivity grid, not choosing the best backtest.
    # Compute the entire residual eigenbasis once per date; retain different spans.
    x = panel[symbols].to_numpy(); m = panel.SPY.to_numpy()
    future = (raw_close/raw_open-1).to_numpy()
    sensitivity, coverage = [], []
    for t in range(120, len(panel)-1):
        history = x[t-120:t]
        market = m[t-120:t]
        sigma = np.maximum(history.std(axis=0, ddof=1), SPEC["volatility_floor_daily"])
        design = np.column_stack([np.ones(120), market])
        coefficients = np.linalg.lstsq(design, history, rcond=None)[0]
        beta = coefficients[1]
        residual = history-design@coefficients
        residual_sigma = np.maximum(residual.std(axis=0, ddof=1), SPEC["volatility_floor_daily"])
        z = (residual-residual.mean(axis=0))/residual_sigma
        values, vectors = np.linalg.eigh(z.T@z/119)
        order = np.argsort(values)[::-1]
        values, vectors = values[order], vectors[:,order]
        total_energy = np.sum((history-history.mean(axis=0))**2)
        residual_energy = np.sum(residual**2)
        for k in DIAGNOSTIC_SPEC["component_counts"]:
            basis = residual_sigma[:,None]*vectors[:,:k]
            exposures = np.column_stack([np.ones(30), beta, basis])
            h, _, _, _ = construct(x[t], exposures, 1/sigma**2)
            ret = float(h@future[t+1])
            traded = float(np.sum(abs(h)*(2+future[t+1])))
            short = float(-h[h<0].sum())
            fitted_residual = (z@vectors[:,:k])@vectors[:,:k].T*residual_sigma
            retained_raw_share = float(1-np.sum((residual-fitted_residual)**2)/total_energy)
            period = "development" if panel.index[t+1] < pd.Timestamp("2024-01-01") else "evaluation"
            sensitivity.append({"date": panel.index[t+1], "period": period, "residual_pcs": k,
                                "gross_return": ret, "primary_cost_return": ret-traded*.0005-short*.01/252})
            coverage.append({"date": panel.index[t+1], "period": period, "residual_pcs": k,
                             "residual_standardized_variance_share": float(values[:k].sum()/values.sum()),
                             "combined_SPY_and_PCs_raw_training_variance_share": retained_raw_share,
                             "SPY_only_raw_training_variance_share": float(1-residual_energy/total_energy)})
    sensitivity = pd.DataFrame(sensitivity)
    coverage = pd.DataFrame(coverage)
    sensitivity.to_csv(OUT / "component_sensitivity_daily.csv", index=False)
    coverage.to_csv(OUT / "variance_coverage_daily.csv", index=False)
    for k, model in [(0, "SPY_only"), (3, "SPY_plus_3_residual_PCs")]:
        ref = daily.loc[daily.model.eq(model)].sort_values("date").gross_return.to_numpy()
        actual = sensitivity.loc[sensitivity.residual_pcs.eq(k)].sort_values("date").gross_return.to_numpy()
        assert np.allclose(ref, actual, atol=1e-12)
    grid_summary = []
    for (period, k), frame in sensitivity.groupby(["period", "residual_pcs"]):
        cov = coverage.loc[coverage.period.eq(period)&coverage.residual_pcs.eq(k)]
        stats = performance(frame.gross_return)
        grid_summary.append({"period": period, "residual_pcs": int(k),
                             "gross_mean_daily_bps": stats["mean_daily_bps"],
                             "gross_sharpe": stats["sharpe_vs_zero"],
                             "gross_mean_hac95_low_bps": stats["mean_daily_bps_hac95_low"],
                             "gross_mean_hac95_high_bps": stats["mean_daily_bps_hac95_high"],
                             "primary_cost_mean_bps": frame.primary_cost_return.mean()*10000,
                             "mean_residual_standardized_variance_share": cov.residual_standardized_variance_share.mean(),
                             "mean_combined_raw_variance_share": cov.combined_SPY_and_PCs_raw_training_variance_share.mean()})
    grid_summary = pd.DataFrame(grid_summary)
    grid_summary.to_csv(OUT / "component_sensitivity_summary.csv", index=False)
    plot_results(daily, timing, regimes, grid_summary)
    summary = {"specification": DIAGNOSTIC_SPEC, "regimes": json.loads(regimes.to_json(orient="records")),
               "timing": json.loads(timing_summary.to_json(orient="records")),
               "component_grid": json.loads(grid_summary.to_json(orient="records")),
               "original_summary_sha256": hashlib.sha256(original_summary).hexdigest(),
               "checks": {"original_0_and_3_PC_returns_reproduced": True,
                          "adjusted_price_timing_identity": True, "log_variance_identity": True,
                          "regime_inputs_available_by_signal_close": True}}
    assert (source / "summary.json").read_bytes() == original_summary
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print("REGIMES\n", regimes.round(3).to_string(index=False))
    print("TIMING\n", timing_summary[["period","model","interval","mean_daily_bps","mean_daily_bps_hac95_low","mean_daily_bps_hac95_high"]].round(3).to_string(index=False))
    print("COMPONENTS\n", grid_summary.round(3).to_string(index=False))


def plot_results(daily, timing, regimes, grid):
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    colors = {"SPY_only":"#277da1", "SPY_plus_3_residual_PCs":"#43aa8b"}
    fig, axes = plt.subplots(2,1,figsize=(13,8),sharex=True,layout="constrained")
    for model, frame in daily.groupby("model"):
        frame = frame.sort_values("date")
        eq = (1+frame.gross_return).cumprod()
        axes[0].plot(frame.date,(eq-1)*100000,color=colors[model],label=model.replace("_"," "))
        rolling_mean = frame.gross_return.rolling(126).mean()*10000
        axes[1].plot(frame.date,rolling_mean,color=colors[model])
    for ax in axes:
        ax.axhline(0,color="gray",lw=.7)
        ax.axvline(pd.Timestamp("2024-01-01"),color="black",ls="--",lw=1)
        ax.grid(alpha=.2)
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda x,pos:f"${x/1000:,.0f}k"))
    axes[0].set(title="Simulated gross profit · $100,000 initial equity, 1x gross",ylabel="Cumulative profit before costs")
    axes[0].legend()
    axes[1].set(title="126-session trailing gross mean: when did returns lean positive?",ylabel="Mean daily return (bps)",xlabel="Execution date · dashed line starts original evaluation period")
    fig.suptitle("Original frozen strategy · next vendor-bar open to close\nGross profit shown separately so assumed transaction costs do not obscure the signal",fontsize=13)
    fig.savefig(OUT/"01_gross_profit.png",dpi=170,bbox_inches="tight");plt.close(fig)

    fig, axes = plt.subplots(1,2,figsize=(13,4.8),layout="constrained")
    for ax, period in zip(axes,["development","evaluation"]):
        for model,color in colors.items():
            frame=timing.loc[timing.period.eq(period)&timing.model.eq(model)].sort_values("date")
            # Arithmetic return attribution only; hypothetical close entry is
            # intentionally not drawn as an executable equity curve.
            ax.plot(frame.date,frame.overnight_hypothetical_return.cumsum()*10000,
                    color=color,ls="--",label=model.replace("_"," ")+" · overnight hypothetical")
            ax.plot(frame.date,frame.original_intraday_raw_return.cumsum()*10000,
                    color=color,label=model.replace("_"," ")+" · actual tested intraday proxy")
        ax.axhline(0,color="gray",lw=.6);ax.grid(alpha=.2)
        ax.set(title=period,ylabel="Sum of daily return contributions (bps)")
        ax.legend(fontsize=7)
    fig.suptitle("Timing diagnosis, not an alternate executable backtest\nDashed overnight lines assume entry at the same close used to form the signal; corporate-action-adjusted prices",fontsize=12)
    fig.savefig(OUT/"02_timing_attribution.png",dpi=170,bbox_inches="tight");plt.close(fig)

    fig,axes=plt.subplots(1,2,figsize=(13,5),layout="constrained")
    states=["Low vol/Up trend","Low vol/Down trend","High vol/Up trend","High vol/Down trend"]
    for ax,period in zip(axes,["development","evaluation"]):
        for offset,(model,color) in zip([-.17,.17],colors.items()):
            frame=regimes.loc[regimes.period.eq(period)&regimes.model.eq(model)].set_index("regime").reindex(states)
            y=frame.gross_mean_daily_bps.to_numpy()
            ax.errorbar(np.arange(4)+offset,y,yerr=np.vstack([y-frame.gross_mean_hac95_low_bps,frame.gross_mean_hac95_high_bps-y]),
                        fmt="o",capsize=3,color=color,label=model.replace("_"," "))
        counts=regimes.loc[regimes.period.eq(period)&regimes.model.eq("SPY_only")].set_index("regime").reindex(states).days
        ax.set_xticks(range(4),[s.replace("/","\n")+f"\nN={int(counts.loc[s])}" for s in states],fontsize=8)
        ax.axhline(0,color="gray",lw=.7);ax.grid(axis="y",alpha=.2)
        ax.set(title=period,ylabel="Mean gross daily return (bps), approx. 95% interval")
        ax.legend(fontsize=8)
    fig.suptitle("Fixed descriptive regimes · SPY trailing 60-day direction and 20-day annualized volatility (20% threshold)\nExploratory conditional comparisons; not a validated regime-switching strategy",fontsize=12)
    fig.savefig(OUT/"03_regimes.png",dpi=170,bbox_inches="tight");plt.close(fig)

    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout="constrained")
    for period,color in [("development","#277da1"),("evaluation","#d1495b")]:
        frame=grid.loc[grid.period.eq(period)]
        axes[0].plot(frame.residual_pcs,frame.mean_combined_raw_variance_share*100,"o-",color=color,label=period)
        axes[1].plot(frame.residual_pcs,frame.gross_mean_daily_bps,"o-",color=color,label=period)
    axes[0].set(title="Average prior-window variance represented",ylabel="Raw stock-return variance (%)",xlabel="Residual PCs, in addition to explicit SPY exposure")
    axes[1].set(title="Does more coverage improve subsequent gross mean?",ylabel="Mean daily gross return (bps)",xlabel="Residual PCs, in addition to explicit SPY exposure")
    axes[1].axhline(0,color="gray",lw=.7)
    for ax in axes:ax.grid(alpha=.2);ax.legend()
    fig.suptitle("Disclosed 0/1/3/5/10 component sensitivity · follow-up exploration, no fresh holdout",fontsize=12)
    fig.savefig(OUT/"04_component_sensitivity.png",dpi=170,bbox_inches="tight");plt.close(fig)


if __name__ == "__main__":
    main()
