"""Walk-forward residual reversal experiment on local Alpaca daily bars.

No network, orders, parameter search, or signal-day fills. Execution is an
idealized next vendor-bar open/close proxy, not verified auction execution.
"""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "market_data/datasets/equity_daily_30_2016_2026-10-27"
OUT = ROOT / "experiments/equity_residual_backtest"
SPEC = {
    "training_sessions": 120, "residual_pcs": 3,
    "volatility_floor_daily": 0.0001,
    "models": ["SPY_only", "SPY_plus_3_residual_PCs"],
    "signal": "one-session adjusted close-to-close log return at t",
    "exposures_and_weights": "estimated from 120 return observations ending t-1",
    "entry": "next session vendor daily-bar raw open; ideal fractional-dollar target fill",
    "exit": "same entry session vendor daily-bar raw close; liquidate all positions",
    "gross_per_starting_equity": 1.0,
    "regression_weights": "inverse trailing total-return variance, floored",
    "neutrality": "dollars, SPY beta; additional 3 residual-PC raw-return exposures for PCA model",
    "per_side_execution_cost_bps": [0, 1, 2, 5, 10],
    "annual_borrow_cost_bps": [0, 100, 500],
    "primary_execution_cost_bps_per_side": 5,
    "primary_annual_borrow_bps": 100,
    "borrow_convention": "entry short notional * assumed annual rate / 252, charged each trade day",
    "development_last_execution_date": "2023-12-31",
    "evaluation_first_execution_date": "2024-01-01",
    "annual_sessions": 252, "newey_west_lags": 5,
    "position_caps": None, "signal_threshold": "numerical-zero only",
    "cash_interest_financing": "omitted; gross and adjusted returns are compared to zero",
    "selection": "fixed 2026-selected 30-stock basket; survivorship/selection bias remains",
    "parameter_search": False,
}


def canonical_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def load_data(development_only=False):
    universe = pd.read_csv(DATA / "universe.csv")
    symbols = universe.loc[universe.role.eq("equity"), "symbol"].tolist()
    returns = pd.read_csv(DATA / "returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    bars = pd.read_csv(DATA / "bars_raw.csv", parse_dates=["date"])
    if development_only:
        returns = returns.loc[:SPEC["development_last_execution_date"]]
        bars = bars.loc[bars.date.le(SPEC["development_last_execution_date"])]
    opens = bars.pivot(index="date", columns="symbol", values="o").reindex(index=returns.index, columns=symbols)
    closes = bars.pivot(index="date", columns="symbol", values="c").reindex(index=returns.index, columns=symbols)
    assert returns[symbols + ["SPY"]].notna().all().all()
    assert opens.notna().all().all() and closes.notna().all().all()
    assert (opens > 0).all().all() and (closes > 0).all().all()
    return symbols, returns, opens, closes


def exposures(history, market):
    sigma = np.maximum(history.std(axis=0, ddof=1), SPEC["volatility_floor_daily"])
    market_design = np.column_stack([np.ones(len(market)), market])
    coefficients = np.linalg.lstsq(market_design, history, rcond=None)[0]
    beta = coefficients[1]
    residual = history - market_design @ coefficients
    residual_sigma = np.maximum(residual.std(axis=0, ddof=1), SPEC["volatility_floor_daily"])
    z = (residual - residual.mean(axis=0)) / residual_sigma
    eigs, vectors = np.linalg.eigh(z.T @ z / (len(z)-1))
    basis = residual_sigma[:, None] * vectors[:, np.argsort(eigs)[::-1][:SPEC["residual_pcs"]]]
    return {
        "SPY_only": np.column_stack([np.ones(history.shape[1]), beta]),
        "SPY_plus_3_residual_PCs": np.column_stack([np.ones(history.shape[1]), beta, basis]),
    }, 1 / sigma**2, beta


def construct(signal, x, weights):
    # Per-column scaling changes no constraints and improves conditioning.
    scale = np.sqrt(np.mean(x*x, axis=0))
    if np.any(scale <= 0):
        raise ValueError("Zero exposure column")
    xn = x / scale
    design = np.sqrt(weights)[:, None] * xn
    coefficients, _, rank, _ = np.linalg.lstsq(design, np.sqrt(weights)*signal, rcond=None)
    if rank != x.shape[1]:
        raise ValueError("Rank-deficient exposure matrix")
    residual = signal - xn @ coefficients
    if np.linalg.norm(residual) <= 1e-12 * max(1., np.linalg.norm(signal)):
        holdings = np.zeros_like(signal)
    else:
        weighted = weights * residual
        holdings = -weighted / np.abs(weighted).sum()
    errors = xn.T @ holdings
    if np.max(np.abs(errors)) > 1e-9:
        raise ValueError("Neutrality check failed")
    return holdings, residual, float(np.max(np.abs(errors))), float(np.linalg.cond(design))


def day_accounting(holdings, future_simple_returns):
    gross = float(holdings @ future_simple_returns)
    # Both opening and closing trades, measured at their respective prices.
    traded = float(np.abs(holdings).sum() + np.abs(holdings * (1+future_simple_returns)).sum())
    short = float(-holdings[holdings < 0].sum())
    return gross, traded, short


def adjusted_returns(frame, execution_bps, borrow_bps):
    return (frame.gross_return - frame.traded_notional * execution_bps / 10000
            - frame.short_notional * borrow_bps / 10000 / SPEC["annual_sessions"])


def newey_west_mean_interval(values):
    values = np.asarray(values)
    n = len(values)
    demeaned = values - values.mean()
    long_run_variance = float(demeaned @ demeaned / n)
    for lag in range(1, min(SPEC["newey_west_lags"], n-1)+1):
        covariance = float(demeaned[lag:] @ demeaned[:-lag] / n)
        long_run_variance += 2 * (1-lag/(SPEC["newey_west_lags"]+1)) * covariance
    se = np.sqrt(max(0, long_run_variance)/n)
    return float((values.mean()-1.96*se)*10000), float((values.mean()+1.96*se)*10000)


def performance(values):
    values = np.asarray(values, dtype=float)
    if np.any(values <= -1):
        raise ValueError("Nonpositive equity under fixed-fraction compounding")
    equity = np.cumprod(1+values)
    peaks = np.maximum.accumulate(np.r_[1., equity])[1:]
    std = values.std(ddof=1)
    lower, upper = newey_west_mean_interval(values)
    return {"days": len(values), "mean_daily_bps": float(values.mean()*10000),
            "mean_daily_bps_hac95_low": lower, "mean_daily_bps_hac95_high": upper,
            "annualized_arithmetic_mean": float(values.mean()*252),
            "annualized_volatility": float(std*np.sqrt(252)),
            "sharpe_vs_zero": float(values.mean()/std*np.sqrt(252)) if std else None,
            "compound_annual_growth": float(equity[-1]**(252/len(values))-1),
            "total_compound_return": float(equity[-1]-1),
            "max_drawdown": float(np.min(equity/peaks-1)),
            "positive_day_fraction": float((values>0).mean())}


def run_checks():
    rng = np.random.default_rng(481)
    x = np.column_stack([np.ones(30), rng.normal(size=(30, 4))])
    weights = np.exp(rng.normal(size=30))
    signal = rng.normal(size=30)
    h, e, _, _ = construct(signal, x, weights)
    assert np.allclose(x.T @ h, 0, atol=1e-10) and np.isclose(abs(h).sum(), 1)
    pure_factor = x @ rng.normal(size=5)
    assert np.allclose(construct(pure_factor, x, weights)[0], 0)
    transform = np.eye(5) + .05*rng.normal(size=(5, 5))
    assert np.allclose(construct(signal, x@transform, weights)[0], h)
    assert h @ (-e) > 0  # Exact hypothetical reversal has positive gross P&L.
    pnl, traded, short = day_accounting(np.array([.5, -.5]), np.array([.01, -.01]))
    assert np.isclose(pnl, .01) and np.isclose(traded, 2) and np.isclose(short, .5)
    # Flat-within-factor signal should not become a full-gross numerical trade.
    return {"weighted_neutrality": True, "pure_factor_signal_zero": True,
            "basis_invariance": True, "hypothetical_reversal_sign": True,
            "entry_and_exit_notional_cost_accounting": True}


def backtest(development_only):
    symbols, panel, opens, closes = load_data(development_only)
    stock_returns = panel[symbols].to_numpy()
    market = panel.SPY.to_numpy()
    intraday = (closes/opens-1).to_numpy()
    daily, positions = [], []
    lookback = SPEC["training_sessions"]
    for t in range(lookback, len(panel)-1):
        history = stock_returns[t-lookback:t]
        matrices, weights, beta = exposures(history, market[t-lookback:t])
        assert panel.index[t-1] < panel.index[t] < panel.index[t+1]
        for model, x in matrices.items():
            holdings, residual, error, condition = construct(stock_returns[t], x, weights)
            gross, traded, short = day_accounting(holdings, intraday[t+1])
            gross_notional = float(np.abs(holdings).sum())
            daily.append({"model": model, "date": panel.index[t+1], "signal_date": panel.index[t],
                          "training_start": panel.index[t-lookback], "training_end": panel.index[t-1],
                          "gross_return": gross, "traded_notional": traded, "short_notional": short,
                          "gross_notional": gross_notional, "net_dollar_exposure": float(holdings.sum()),
                          "estimated_SPY_beta_exposure": float(beta@holdings),
                          "max_scaled_exposure_error": error, "max_abs_position": float(abs(holdings).max()),
                          "regression_condition_number": condition,
                          "signal_residual_rms": float(np.sqrt(np.mean(residual**2)))})
            positions.extend({"model": model, "date": panel.index[t+1], "symbol": symbol,
                              "unit_gross_target_dollars": float(holdings[i]),
                              "signal_log_return": float(stock_returns[t,i]),
                              "signal_residual": float(residual[i]),
                              "future_bar_open_to_close_return": float(intraday[t+1,i]),
                              "gross_pnl_contribution": float(holdings[i]*intraday[t+1,i])}
                             for i, symbol in enumerate(symbols))
    daily = pd.DataFrame(daily)
    daily["period"] = np.where(daily.date < pd.Timestamp("2024-01-01"), "development", "evaluation")
    daily["primary_cost_adjusted_return"] = adjusted_returns(
        daily, SPEC["primary_execution_cost_bps_per_side"], SPEC["primary_annual_borrow_bps"])
    return daily, pd.DataFrame(positions)


def write_results(daily, positions, stage, checks):
    out = OUT / stage
    out.mkdir(parents=True, exist_ok=True)
    daily.to_csv(out / "daily_returns_and_diagnostics.csv", index=False)
    positions.to_csv(out / "daily_positions.csv", index=False)
    metrics, costs, annual = [], [], []
    for (period, model), frame in daily.groupby(["period", "model"]):
        for label, values in (("gross", frame.gross_return), ("primary_cost_adjusted", frame.primary_cost_adjusted_return)):
            metrics.append({"period": period, "model": model, "scenario": label,
                            "first_date": str(frame.date.min().date()), "last_date": str(frame.date.max().date()),
                            **performance(values)})
        for execution in SPEC["per_side_execution_cost_bps"]:
            for borrow in SPEC["annual_borrow_cost_bps"]:
                costs.append({"period": period, "model": model,
                              "execution_bps_per_side": execution, "borrow_bps_annual": borrow,
                              **performance(adjusted_returns(frame, execution, borrow))})
        for year, year_frame in frame.groupby(frame.date.dt.year):
            annual.append({"period": period, "model": model, "year": int(year),
                           "days": len(year_frame),
                           "gross_compound_return": float(np.prod(1+year_frame.gross_return)-1),
                           "primary_cost_adjusted_compound_return": float(np.prod(1+year_frame.primary_cost_adjusted_return)-1)})
    pd.DataFrame(metrics).to_csv(out / "performance.csv", index=False)
    pd.DataFrame(costs).to_csv(out / "cost_sensitivity.csv", index=False)
    pd.DataFrame(annual).to_csv(out / "annual_returns.csv", index=False)
    comparison = []
    for period, frame in daily.groupby("period"):
        paired = frame.pivot(index="date", columns="model", values="gross_return")
        delta = paired.SPY_plus_3_residual_PCs-paired.SPY_only
        low, high = newey_west_mean_interval(delta)
        comparison.append({"period": period, "pca_minus_spy_mean_daily_bps": float(delta.mean()*10000),
                           "paired_hac95_low_bps": low, "paired_hac95_high_bps": high})
    summary = {"specification": SPEC, "specification_sha256": canonical_hash(SPEC),
               "source_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "input_sha256": {name: hashlib.sha256((DATA/name).read_bytes()).hexdigest()
                                for name in ["returns_log.csv", "bars_raw.csv", "universe.csv"]},
               "checks": checks, "paired_comparison": comparison,
               "max_scaled_exposure_error": float(daily.max_scaled_exposure_error.max()),
               "max_abs_SPY_beta_exposure": float(abs(daily.estimated_SPY_beta_exposure).max()),
               "max_abs_position": float(daily.max_abs_position.max()),
               "average_traded_notional_per_day": float(daily.traded_notional.mean()),
               "cash_signal_days": int(daily.gross_notional.eq(0).sum()),
               "performance": metrics}
    (out / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    plot_results(daily, pd.DataFrame(costs), pd.DataFrame(annual), out)
    print(pd.DataFrame(metrics)[["period", "model", "scenario", "days", "mean_daily_bps", "sharpe_vs_zero", "compound_annual_growth", "max_drawdown"]].round(4).to_string(index=False))
    print(json.dumps({k: summary[k] for k in ["max_scaled_exposure_error", "max_abs_position", "average_traded_notional_per_day", "paired_comparison"]}, indent=2))


def plot_results(daily, costs, annual, out):
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    periods = [p for p in ["development", "evaluation"] if p in daily.period.unique()]
    fig, axes = plt.subplots(2, len(periods), figsize=(7*len(periods), 8), squeeze=False, layout="constrained")
    for row, model in enumerate(SPEC["models"]):
        for col, period in enumerate(periods):
            frame = daily.loc[daily.model.eq(model)&daily.period.eq(period)]
            ax = axes[row,col]
            ax.plot(frame.date, (1+frame.gross_return).cumprod(), label="Gross", color="#277da1")
            ax.plot(frame.date, (1+frame.primary_cost_adjusted_return).cumprod(), label="5 bps/side + 1% annual borrow", color="#d1495b")
            ax.axhline(1, color="gray", lw=.6)
            ax.set(title=f"{model.replace('_', ' ')} · {period}", ylabel="Equity per initial $1 (1x gross)")
            ax.grid(alpha=.2)
            ax.legend(fontsize=8)
    fig.suptitle("Frozen daily reversal experiment · next vendor-bar open to close\nEach panel starts at $1; assumed costs are scenarios, not measured execution", fontsize=13)
    fig.savefig(out / "01_equity_curves.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    fig, axes = plt.subplots(1, len(periods), figsize=(7*len(periods), 4.5), squeeze=False, layout="constrained")
    for col, period in enumerate(periods):
        ax = axes[0,col]
        for model, color in zip(SPEC["models"], ["#277da1", "#43aa8b"]):
            frame = costs.loc[costs.period.eq(period)&costs.model.eq(model)&costs.borrow_bps_annual.eq(100)]
            ax.plot(frame.execution_bps_per_side, frame.mean_daily_bps, "o-", label=model.replace("_", " "), color=color)
        ax.axhline(0,color="gray",lw=.7)
        ax.set(title=period, xlabel="Assumed execution cost (bps per side)", ylabel="Mean daily return (bps)")
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    fig.suptitle("Cost sensitivity · fixed additional 1% annual borrow assumption")
    fig.savefig(out / "02_cost_sensitivity.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(12, 4.5), layout="constrained")
    years = sorted(annual.year.unique())
    for offset, model, color in zip([-.2,.2], SPEC["models"], ["#277da1", "#43aa8b"]):
        frame = annual.loc[annual.model.eq(model)].set_index("year").reindex(years)
        ax.bar(np.arange(len(years))+offset, frame.primary_cost_adjusted_compound_return*100, width=.38,
               label=model.replace("_", " "), color=color)
    ax.set_xticks(range(len(years)), years)
    ax.axhline(0,color="gray",lw=.7)
    ax.set(title="Calendar-period compounded returns after primary assumed costs\n2016 starts after warm-up; 2026 ends October 27; both are partial years",
           ylabel="Return (%)")
    ax.legend(fontsize=8)
    ax.grid(axis="y",alpha=.2)
    fig.savefig(out / "03_annual_returns.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluate", action="store_true", help="Evaluate frozen settings on 2024 onward as well")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    freeze_path = OUT / "frozen_specification.json"
    frozen = {"specification": SPEC, "sha256": canonical_hash(SPEC)}
    if freeze_path.exists():
        if json.loads(freeze_path.read_text()) != frozen:
            raise ValueError("Frozen settings differ; do not silently overwrite the original experiment")
    else:
        if args.evaluate:
            raise ValueError("Run development checks before evaluating the later period")
        freeze_path.write_text(json.dumps(frozen, indent=2)+"\n")
    checks = run_checks()
    if args.evaluate:
        dev_summary = json.loads((OUT / "development_only/summary.json").read_text())
        if dev_summary["source_script_sha256"] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
            raise ValueError("Source changed after development checks")
    daily, positions = backtest(development_only=not args.evaluate)
    if args.evaluate:
        # A future suffix must not alter any prior positions or daily returns.
        previous = pd.read_csv(OUT / "development_only/daily_returns_and_diagnostics.csv")
        actual = daily.loc[daily.period.eq("development")]
        assert len(previous) == len(actual)
        for field in ["gross_return", "primary_cost_adjusted_return", "max_abs_position", "estimated_SPY_beta_exposure"]:
            assert np.allclose(previous[field], actual[field], atol=1e-12, rtol=1e-10)
        checks["future_suffix_does_not_change_development_results"] = True
    checks["training_before_signal_before_execution"] = True
    write_results(daily, positions, "evaluated" if args.evaluate else "development_only", checks)


if __name__ == "__main__":
    main()
