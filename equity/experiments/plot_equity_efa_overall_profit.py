"""Full continuous profit/drawdown view of the frozen ungated EFA/PCA ledger."""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/"experiments/equity_efa_vs_pca/daily_gross_returns.csv"
OUT = ROOT/"experiments/equity_efa_overall_profit"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    daily = pd.read_csv(SOURCE, parse_dates=["date", "signal_date"])
    start = daily.signal_date.min()
    frames = {}; records = []
    for model in ["PCA3", "EFA3"]:
        f = daily.loc[daily.model.eq(model)].sort_values("date")
        r = f.gross_return.to_numpy()
        equity = 100000*np.cumprod(1+r)
        peak = np.maximum.accumulate(np.r_[100000., equity])[1:]
        drawdown = equity/peak-1
        frame = pd.DataFrame({"date": f.date, "model": model, "gross_return": r,
            "equity_100k": equity, "gross_profit_100k": equity-100000, "drawdown": drawdown})
        frames[model] = frame
        for period, selected in [("full", f), ("2017-2023", f.loc[f.date.lt("2024-01-01")]),
                                 ("2024-onward", f.loc[f.date.ge("2024-01-01")])]:
            values = selected.gross_return.to_numpy(); curve = np.cumprod(1+values)
            dd = curve/np.maximum.accumulate(np.r_[1., curve])[1:]-1
            records.append({"model": model, "period": period, "start": str(selected.date.min().date()),
                "end": str(selected.date.max().date()), "trading_days": len(values),
                "gross_CAGR": float(curve[-1]**(252/len(values))-1), "total_gross_return": float(curve[-1]-1),
                "ending_equity_from_100k": float(100000*curve[-1]), "annualized_volatility": float(values.std(ddof=1)*np.sqrt(252)),
                "sharpe_vs_zero": float(values.mean()/values.std(ddof=1)*np.sqrt(252)), "max_drawdown": float(dd.min())})
    metrics = pd.DataFrame(records)
    all_curves = pd.concat(frames.values(), ignore_index=True)
    metrics.to_csv(OUT/"performance_by_period.csv", index=False)
    all_curves.to_csv(OUT/"continuous_equity_curves.csv", index=False)
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 1, figsize=(12, 7.5), sharex=True, height_ratios=[2.3, 1], layout="constrained")
    colors = {"PCA3": "#277da1", "EFA3": "#e58a20"}
    for model, f in frames.items():
        cagr = metrics.loc[metrics.model.eq(model) & metrics.period.eq("full"), "gross_CAGR"].iloc[0]
        dates = pd.DatetimeIndex([start, *f.date.tolist()])
        axes[0].plot(dates, np.r_[0., f.gross_profit_100k], color=colors[model], lw=1.7,
            label=f"{model[:-1]} + SPY, three factors | full-run CAGR {cagr:.2%}")
        axes[1].plot(dates, np.r_[0., f.drawdown], color=colors[model], lw=1.4)
    split = pd.Timestamp("2024-01-01"); last = daily.date.max()
    for ax in axes:
        ax.axvline(split, color="#555555", ls="--", lw=1.)
        ax.axvspan(split, last, color="#777777", alpha=.07)
        ax.axhline(0, color="#444444", lw=.6)
        ax.grid(axis="y", alpha=.2)
        ax.margins(x=.02)
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda value, position: f"${value:,.0f}"))
    axes[0].set_ylabel("Cumulative gross profit on initial $100,000")
    axes[0].legend(loc="upper left", fontsize=10)
    axes[0].text(.99, .97, "Shaded: 2024 onward\nEFA CAGR 3.54%; full curve never resets",
        transform=axes[0].transAxes, ha="right", va="top", fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": .85})
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1].set_ylabel("Drawdown from running peak")
    axes[1].set_xlabel("Trading dates | first execution February 3, 2017; last October 27, 2026")
    fig.suptitle("Overall ungated PCA and EFA strategy profit\nGross/pre-fee, 1× gross stock notional; no TDA filter, no cash-interest return", fontsize=14)
    fig.savefig(OUT/"overall_profit_and_drawdown.png", dpi=180)
    fig.savefig(OUT/"overall_profit_and_drawdown.svg")
    plt.close(fig)
    assert all(np.isclose(f.equity_100k.iloc[-1], metrics.loc[metrics.model.eq(m) & metrics.period.eq("full"), "ending_equity_from_100k"].iloc[0]) for m, f in frames.items())
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == digest
    result = {"source": str(SOURCE.relative_to(ROOT)), "source_sha256": digest, "initial_equity": 100000,
        "compounding": "daily return reinvestment, unit gross notional relative to current equity", "annualization": "252 trading sessions",
        "notes": "continuous full trading ledger; no reset at2024; period metrics separately reset for reporting; no rerun or change of strategy",
        "source_unchanged": True, "source_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/"provenance.json").write_text(json.dumps(result, indent=2)+"\n")
    print(metrics.round(6).to_string(index=False))


if __name__ == "__main__": main()
