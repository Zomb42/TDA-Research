"""Current project presentation: gross/pre-fee results only.

Reads the frozen experiment; does not rerun strategies or apply trading costs.
Old cost scenarios remain in original artifacts solely for provenance.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "experiments/equity_residual_backtest/evaluated"
OUT = ROOT / "experiments/equity_residual_backtest/gross_report"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    daily = pd.read_csv(ORIGINAL / "daily_returns_and_diagnostics.csv", parse_dates=["date"])
    performance = pd.read_csv(ORIGINAL / "performance.csv")
    performance = performance.loc[performance.scenario.eq("gross")].drop(columns="scenario")
    performance.to_csv(OUT / "performance.csv", index=False)
    annual = pd.read_csv(ORIGINAL / "annual_returns.csv")
    annual = annual[["period", "model", "year", "days", "gross_compound_return"]]
    annual.to_csv(OUT / "annual_returns.csv", index=False)
    fields = ["model", "date", "signal_date", "training_start", "training_end", "period",
              "gross_return", "gross_notional", "net_dollar_exposure", "estimated_SPY_beta_exposure",
              "max_scaled_exposure_error", "max_abs_position", "signal_residual_rms"]
    daily[fields].to_csv(OUT / "daily_returns_and_diagnostics.csv", index=False)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    colors = {"SPY_only": "#277da1", "SPY_plus_3_residual_PCs": "#43aa8b"}
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), layout="constrained")
    for ax, period in zip(axes, ["development", "evaluation"]):
        for model, color in colors.items():
            frame = daily.loc[daily.period.eq(period)&daily.model.eq(model)].sort_values("date")
            ax.plot(frame.date, (1+frame.gross_return).cumprod(), label=model.replace("_", " "), color=color)
        ax.axhline(1, color="gray", lw=.7)
        ax.set(title=period, ylabel="Gross equity per initial $1 · 1x gross")
        ax.legend(fontsize=8); ax.grid(alpha=.2)
    fig.suptitle("Gross/pre-fee performance · original frozen daily reversal experiment\nEach panel starts at $1; daily-bar prices remain idealized execution proxies", fontsize=12)
    fig.savefig(OUT / "01_gross_equity.png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(12, 4.5), layout="constrained")
    years = sorted(annual.year.unique())
    for offset, (model, color) in zip([-.2, .2], colors.items()):
        frame = annual.loc[annual.model.eq(model)].set_index("year").reindex(years)
        ax.bar([i+offset for i in range(len(years))], frame.gross_compound_return*100, width=.38,
               color=color, label=model.replace("_", " "))
    ax.set_xticks(range(len(years)), years)
    ax.axhline(0, color="gray", lw=.7)
    ax.set(title="Calendar-period gross returns\n2016 begins after warm-up; 2026 ends October 27; both are partial years", ylabel="Gross compounded return (%)")
    ax.legend(); ax.grid(axis="y", alpha=.2)
    fig.savefig(OUT / "02_gross_annual_returns.png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    for name in ["component_sensitivity_summary.csv", "conditional_regimes.csv"]:
        source = ROOT / "experiments/equity_residual_diagnostics" / name
        frame = pd.read_csv(source)
        frame = frame[[c for c in frame.columns if "cost" not in c and "borrow" not in c]]
        frame.to_csv(OUT / name, index=False)
    print("Saved gross-only report, tables, and plots to", OUT)


if __name__ == "__main__":
    main()
