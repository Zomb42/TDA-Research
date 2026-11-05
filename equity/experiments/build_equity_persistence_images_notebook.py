"""Build and execute a local, output-rich research notebook without kernel sockets."""
from pathlib import Path
import os
import platform
import nbformat as nb
from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.capture import capture_output
from traitlets.config import Config

ROOT = Path(__file__).resolve().parents[1]


def main():
    cells = [
        nb.v4.new_markdown_cell('''# Do persistence images improve the equity gate?

October 29, 2026. **Result: no improvement established.** The image model had higher later forecast error and lower gross trading performance than the existing three-summary model. It looked slightly better on earlier point forecasts, which did not carry into the later period. All declared simultaneous incremental intervals span zero.

[Intuitive findings and exact design](experiments/equity_persistence_images/README.md) · [fixed specification](experiments/equity_persistence_images/specification.json) · [source](experiments/equity_persistence_images.py) · [running research log](EQUITY_RESEARCH_LOG.md).

Only the representation changes. The original dollar/SPY/three-PC-neutral daily portfolio and the positive-forecast on/off rule remain fixed. Everything is **gross/pre-fee**. The historical dates were already examined, so this is exploratory research, not a new untouched test.'''),
        nb.v4.new_code_cell('''from pathlib import Path
import json
import numpy as np
import pandas as pd
from IPython.display import display, Image
cwd = Path.cwd()
candidates = [cwd, cwd/"TDA_Research", cwd/"Senior-Fall"/"TDA_Research", *cwd.parents]
project = next(p for p in candidates if (p/"START_HERE.md").is_file() and (p/"equity").is_dir())
out = project/"equity"/"experiments"/"equity_persistence_images"
result = json.loads((out/"summary.json").read_text())
audit = json.loads((out/"independent_audit.json").read_text())
grid = json.loads((out/"frozen_grid.json").read_text())
features = pd.read_csv(out/"state_features_and_targets.csv")
predictions = pd.read_csv(out/"walk_forward_predictions.csv")
forecast = pd.read_csv(out/"forecast_metrics.csv")
performance = pd.read_csv(out/"gate_performance.csv")
comparisons = pd.read_csv(out/"paired_incremental_comparisons.csv")
pnl = pd.read_csv(out/"daily_gate_returns.csv", parse_dates=["date"])
assert all(result["checks"].values()) and all(audit["checks"].values())
print("Feature anchors:", result["feature_anchors"], "| forecasts:", result["predictions"])
print("First forecast:", result["first_prediction"], "| last:", result["last_prediction"])
print("Complete forecast scores:", result["forecast_scores_by_period"])
print("Daily calendar:", result["calendar_days_by_period"])'''),
        nb.v4.new_markdown_cell('''## 1. What becomes an image?

We reuse the saved stock diagrams. A point in the original cloud is a stock described by three weighted residual-PCA exposures, estimated from the prior 120 sessions. Distances are divided by their median. The fixed reference set contains 182 stocks; the traded portfolio can admit additional names as their histories arrive.

H1 describes loops in this stock-exposure geometry. A diagram point records the connection distance at which a loop appears and the distance at which it disappears. We use **birth and lifetime (death minus birth)** as axes. These are distance scales, not days or economic cycles.

Place a smooth Gaussian bump at each point, weight it by lifetime, then integrate the bumps into sixteen pixels. Each pixel is one input to the same small regression. Longer lifetime gets more weight by construction; it is not proof of stronger return predictability. This is a vector representation, not a screenshot passed to a neural network. See [Adams et al. (2017)](https://www.jmlr.org/papers/volume18/16-337/16-337.pdf).

All H0 components start at zero, so their useful coordinate is their merge distance. We use four frequency bins instead of allocating a second image dimension to a constant. One infinite interval is excluded. **Four H0 bins plus sixteen H1 pixels give twenty added inputs.**

The grid uses only diagrams from the first forecast's 104 completed training labels. Its bounds are 1.25 times the initial maxima, with Gaussian width half a pixel. They stay fixed; feature scaling and regression coefficients update from completed training history only. No resolution or bandwidth search was performed.'''),
        nb.v4.new_code_cell('''print({k: v for k, v in grid.items() if k != "calibration_anchors"})
display(Image(filename=str(out/"01_diagram_to_image.png")))'''),
        nb.v4.new_markdown_cell('''## 2. Did the richer representation predict returns better?

The target is the average gross daily return over the next twenty **daily strategy trades**, not holding today's weights for twenty days. Forecasts update every five sessions. All models share the previous ordinary state predictors, including volatility, correlations, PCA concentration, temporal summaries, recent strategy performance, stock count, and cloud scales.

`SimplePlusStockPD` adds the old three summaries. `Ordinary20` adds twenty conventional distance/correlation quantiles. `PersistenceImage20` adds the four H0 bins and sixteen image pixels. The latter two have equal added feature count, although their effective complexity can differ. `HistoryMean` simply predicts the average of completed historical target windows.

**Lower mean squared error is better.** The image's later error is 38.103 versus 32.812 for the three-summary model. Earlier, the image's point error was slightly lower than the simple and three-summary models. Its historical advantage did not persist across these periods. No causal reason for that change is identified.

We report paired approximate 95% simultaneous bands across the three image-minus-comparator contrasts within each period and metric. Every such interval includes zero. The forecast bootstrap resamples twelve consecutive five-session anchors at a time to acknowledge dependence. It conditions on the saved forecasts rather than refitting the entire model each time.'''),
        nb.v4.new_code_cell('''display(forecast[["period", "model", "forecasts", "MSE_bps_squared", "MAE_bps"]].round(4))
display(comparisons.loc[comparisons.metric.eq("forecast_MSE_bps_squared"),
    ["period", "comparator", "difference", "sim95_low", "sim95_high"]].round(4))
display(Image(filename=str(out/"03_incremental_comparisons.png")))'''),
        nb.v4.new_markdown_cell('''## 3. What happened to gross profit?

A forecast above zero runs the existing strategy for the next five sessions; otherwise it holds no stock positions. During active sessions, weights still refresh daily, enter at the next daily-bar open, and close that day. All flat days remain zero in the calendar series.

Later image-gate CAGR is **1.19%**, Sharpe **0.43**, versus **3.39%** and **1.06** for the three-summary gate. The ordinary twenty-coordinate control has higher later point performance than either, but it is not a validated winner. All daily mean intervals include zero. No costs of any kind are deducted.

The image-minus-three-summary later mean difference is **−0.857 bps/calendar day**, approximate simultaneous interval **[−2.451,+0.737]**. The point result is unfavorable, but the uncertainty does not establish a definitive ranking. Calendar intervals use sixty-session blocks. Curves start from zero separately in each period.'''),
        nb.v4.new_code_cell('''table = performance.copy()
table["CAGR_percent"] = table.gross_CAGR*100
table["active_percent"] = table.active_fraction*100
display(table[["period", "model", "mean_daily_bps", "mean_low", "mean_high", "CAGR_percent", "sharpe_vs_zero", "active_percent"]].round(3))
display(Image(filename=str(out/"02_gross_gate_profit.png")))'''),
        nb.v4.new_markdown_cell('''## 4. Did it skip useful trades? Did the grid fail?

The table below is a **descriptive decomposition**, not a new fitted rule: what did the underlying strategy earn on days a gate allowed it to trade versus days it skipped? The gate's calendar mean equals active fraction times the underlying mean on active days. Positive skipped-day returns are gains the gate omitted; negative skipped-day returns are losses it avoided. These realized subgroup means cannot be known at decision time.

For the later image gate, the underlying portfolio averaged **0.870 bps on active days and 1.942 bps on skipped days**. It skipped the more profitable group in this sample. Earlier it had the desired ordering: +1.433 active versus −1.235 skipped. This does not establish why the relationship changed or a statistically reliable ranking.

Separately, only 3 of 30,270 H1 points lie outside the fixed rectangle across all feature anchors. Median retained weighted Gaussian mass is 88.6%, including ordinary tails outside the nonnegative grid. H0 overflow is retained in the last bin. This argues against widespread range overflow; it does not prove that the chosen smoothing or grid is best.'''),
        nb.v4.new_code_cell('''selection = []
for period, days in pnl.groupby("period", sort=False):
    for model in ["Simple", "SimplePlusStockPD", "Ordinary20", "PersistenceImage20"]:
        active = days[model+"_active"].astype(bool)
        active_mean = days.loc[active, "AlwaysOn"].mean()*1e4
        skipped_mean = days.loc[~active, "AlwaysOn"].mean()*1e4
        assert np.isclose(active.mean()*active_mean, days[model].mean()*1e4)
        assert np.isclose(active.mean()*active_mean+(~active).mean()*skipped_mean, days.AlwaysOn.mean()*1e4)
        selection.append({"period": period, "model": model, "active_fraction": active.mean(),
            "underlying_active_day_mean_bps": active_mean, "underlying_skipped_day_mean_bps": skipped_mean})
selection = pd.DataFrame(selection)
selection.to_csv(out/"gate_selection_diagnostics.csv", index=False)
display(selection.round(4))
display(pd.Series(result["range_diagnostics"], name="Range checks"))
display(Image(filename=str(out/"04_image_coverage.png")))'''),
        nb.v4.new_markdown_cell('''## 5. What we learned and what remains uncertain

The image preserves a real distinction omitted by lifetime summaries: hypothetical diagrams with equal lifetimes but shifted births produce different pixels. Empty and zero-lifetime H1 contribute zero, and reordering diagram points changes nothing. But preserving more diagram information did not yield demonstrated forecasting value in this test.

The checks below reconstruct every image and forecast independently, preserve completed-label chronology, and reconcile the old baseline, daily P&L, metrics, and uncertainty bands. These checks address implementation errors; they do not prove a strategy edge or establish why the image model underperformed.

Additional estimation noise, a weak relationship between shape and returns, and an unsuitable representation are possible explanations. This run cannot distinguish them. The survivor universe, already examined history, overlapping windows, single grid choice, and fixed learner remain limitations.

**Decision:** keep this as a negative incremental result. Retain the daily strategy as an unconfirmed benchmark; do not promote the tested gates or tune a larger image merely to repair this curve. New observations or a distinct justified hypothesis would be more informative than selecting the best pixel settings on the same history.'''),
        nb.v4.new_code_cell('''for name, passed in audit["checks"].items():
    print(name, passed)
print("Images checked:", audit["images_checked"], "| forecasts checked:", audit["forecasts_checked"])
print("Maximum independent image error:", audit["max_image_error"])
print("Maximum independent forecast error, bps:", audit["max_prediction_error_bps"])
assert all(audit["checks"].values())'''),
    ]
    notebook = nb.v4.new_notebook(cells=cells, metadata={"kernelspec": {"display_name": "TDA (conda)", "language": "python", "name": "tda"},
        "language_info": {"name": "python", "version": platform.python_version()}})
    os.chdir(ROOT)
    cfg = Config(); cfg.HistoryManager.hist_file = ":memory:"
    shell = InteractiveShell.instance(config=cfg)
    for cell in notebook.cells:
        if cell.cell_type != "code":
            continue
        count = shell.execution_count
        with capture_output() as captured:
            result = shell.run_cell(cell.source, store_history=True)
        if result.error_before_exec or result.error_in_exec:
            raise RuntimeError(str(result.error_before_exec or result.error_in_exec))
        cell.execution_count = count
        cell.outputs = []
        for name, text in [("stdout", captured.stdout), ("stderr", captured.stderr)]:
            if text:
                cell.outputs.append(nb.v4.new_output("stream", name=name, text=text))
        for output in captured.outputs:
            cell.outputs.append(nb.v4.new_output("display_data", data=output.data, metadata=output.metadata))
    nb.validate(notebook)
    nb.write(notebook, ROOT/"equity_persistence_images.ipynb")
    print("Executed", sum(c.cell_type == "code" for c in notebook.cells), "cells; embedded",
        sum("image/png" in o.get("data", {}) for c in notebook.cells if c.cell_type == "code" for o in c.outputs), "figures")


if __name__ == "__main__":
    main()
