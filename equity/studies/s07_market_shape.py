"""A2 + B2. How does the market's shape move through time, and does it warn of risk?

Every day, from the previous 120 days of the eligible stocks:

  shape measures   typical distance to the nearest group (H0), total ring lifetime (H1),
                   number of TDA peer groups, share of stocks with no close peer,
                   and how far the ring diagram moved in the last 5 days
  plain measures   average correlation between stocks (after removing SPY),
                   share of variance in the first common pattern, SPY volatility, VIX

Two questions:
  1. How much of each shape measure is already explained by the plain measures?
  2. Do the shape measures improve a forecast of next week's dispersion (how
     far stocks spread apart from each other, the risk a market-neutral book
     carries) beyond its own recent history and VIX?

    conda run -n tda python equity/studies/s07_market_shape.py
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tdaeq import clusters, data, evaluate, factors, plots, topology

STUDY = "s07_market_shape"
WINDOW, AHEAD = 120, 5
EVENTS = {"2018-02-05": "Feb 2018", "2020-03-16": "Mar 2020", "2022-06-13": "2022",
          "2023-03-13": "Mar 2023", "2024-08-05": "Aug 2024", "2025-04-04": "Apr 2025", "2026-11-02": "Nov 2026"}
SHAPE = ["h0_mean_death", "h1_total", "groups", "no_peer_share", "ring_change_5d"]
PLAIN = ["mean_abs_corr", "pc1_share", "spy_vol_20d", "vix"]
LABELS = {"h0_mean_death": "Typical distance to nearest group (H0)", "h1_total": "Total ring lifetime (H1)",
          "groups": "Number of TDA peer groups", "no_peer_share": "Share of stocks with no close peer",
          "ring_change_5d": "Change in ring diagram over 5 days"}


def daily_measures(panel):
    rows, previous = [], {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        for t in range(data.MIN_HISTORY, len(panel.dates)):
            cols = panel.eligible(t)
            geo = factors.geometry(panel.returns[t - WINDOW:t, cols], panel.market[t - WINDOW:t])
            dgms = topology.diagrams(geo.distance)
            labels = clusters.hdbscan_labels(geo.distance, min_cluster_size=2, min_samples=1)
            values = np.linalg.eigvalsh(geo.corr)
            off = geo.corr[np.triu_indices(len(cols), 1)]
            today = panel.returns[t, cols] - geo.beta * panel.market[t]
            previous[t] = dgms[1]
            rows.append({
                "date": panel.dates[t], **topology.summarize(dgms),
                "groups": clusters.describe(labels)["groups"], "no_peer_share": (labels < 0).mean(),
                "ring_change_5d": topology.diagram_distance(dgms[1], previous[t - 5]) if t - 5 in previous else np.nan,
                "mean_abs_corr": np.abs(off).mean(), "pc1_share": values[-1] / values.sum(),
                "spy_vol_20d": panel.market[t - 20:t].std(ddof=1) * np.sqrt(252),
                "vix": panel.vix[t - 1],                        # yesterday's close, known this morning
                "dispersion": today.std(ddof=1),                # how spread out today's non-SPY moves are
                "spy_level": np.exp(panel.market[:t + 1].sum())})
            previous.pop(t - 6, None)
    return pd.DataFrame(rows).set_index("date")


def explained_by_plain(table):
    """Share of each shape measure's variation that the plain measures already explain."""
    use = table.dropna(subset=SHAPE + PLAIN)
    x = np.column_stack([np.ones(len(use)), use[PLAIN].to_numpy()])
    rows = []
    for name in SHAPE:
        y = use[name].to_numpy()
        fitted = x @ np.linalg.lstsq(x, y, rcond=None)[0]
        rows.append({"shape_measure": LABELS[name], "explained_by_plain": 1 - ((y - fitted) ** 2).sum() / ((y - y.mean()) ** 2).sum(),
                     "corr_with_mean_abs_corr": np.corrcoef(y, use.mean_abs_corr)[0, 1]})
    return pd.DataFrame(rows)


def forecast_test(table):
    """Predict the log of average dispersion over the next 5 days, walking forward in time."""
    log_d = np.log(table.dispersion)
    frame = pd.DataFrame({
        "target": log_d.rolling(AHEAD).mean().shift(-AHEAD),      # days t+1 .. t+5
        "d1": log_d, "d5": log_d.rolling(5).mean(), "d20": log_d.rolling(20).mean(),
        "log_vix": np.log(table.vix)})
    for name in SHAPE:
        frame[name] = (table[name] - table[name].rolling(250).mean()) / table[name].rolling(250).std()
    frame = frame.dropna()
    models = {"Recent dispersion": ["d1", "d5", "d20"],
              "+ VIX": ["d1", "d5", "d20", "log_vix"],
              "+ VIX + shape": ["d1", "d5", "d20", "log_vix"] + SHAPE}
    start, refit = 500, 20
    errors = {name: np.full(len(frame), np.nan) for name in models}
    y = frame.target.to_numpy()
    for name, columns in models.items():
        x = np.column_stack([np.ones(len(frame)), frame[columns].to_numpy()])
        for begin in range(start, len(frame), refit):
            train = slice(0, begin - AHEAD)                        # only targets fully known by then
            coef = np.linalg.lstsq(x[train], y[train], rcond=None)[0]
            block = slice(begin, min(begin + refit, len(frame)))
            errors[name][block] = (y[block] - x[block] @ coef) ** 2
    rows = []
    later = frame.index >= data.SPLIT
    for label, mask in (("before 2024", ~later), ("2024 on", later)):
        use = mask & np.isfinite(errors["+ VIX"])
        for name in models:
            rows.append({"period": label, "model": name, "days": int(use.sum()),
                         "mean_squared_error": errors[name][use].mean()})
        diff, low, high = evaluate.mean_ci(errors["+ VIX + shape"][use] - errors["+ VIX"][use], block=20)
        base = errors["+ VIX"][use].mean()
        rows.append({"period": label, "model": "shape minus no-shape, % of error", "days": int(use.sum()),
                     "mean_squared_error": diff / base * 100, "low": low / base * 100, "high": high / base * 100})
    return pd.DataFrame(rows)


def figure(table):
    panels = [("spy_level", "SPY (growth of 1)", plots.GRAY), ("vix", "VIX", plots.GRAY),
              ("mean_abs_corr", "Plain: average correlation between stocks (SPY removed)", plots.ORANGE),
              ("h1_total", LABELS["h1_total"], plots.BLUE),
              ("ring_change_5d", LABELS["ring_change_5d"], plots.BLUE),
              ("groups", LABELS["groups"], plots.BLUE)]
    fig, axes = plt.subplots(len(panels), 1, figsize=(11, 10.5), sharex=True, layout="constrained")
    for ax, (column, title, color) in zip(axes, panels):
        ax.plot(table.index, table[column], color=color, lw=1.4)
        ax.set_title(title, fontsize=10, pad=18 if ax is axes[0] else 6)   # room for the event labels
        for day in EVENTS:
            ax.axvline(pd.Timestamp(day), color=plots.AXIS, lw=1, zorder=0)
    top = axes[0]
    for day, label in EVENTS.items():
        top.text(pd.Timestamp(day), top.get_ylim()[1], label, rotation=0, ha="center", va="bottom",
                 fontsize=8, color=plots.INK_SOFT)
    fig.suptitle(f"The market's shape through time ({WINDOW}-day windows). Blue = shape measures, orange = plain measure\n",
                 x=0.01, ha="left", fontweight="bold")
    plots.save(fig, STUDY, "1_timeline.png")


def main():
    panel = data.load_panel()
    table = daily_measures(panel)
    out = plots.folder(STUDY)
    table.to_csv(out / "daily_measures.csv")
    explained = explained_by_plain(table)
    forecast = forecast_test(table)
    explained.to_csv(out / "explained_by_plain.csv", index=False)
    forecast.to_csv(out / "dispersion_forecast.csv", index=False)
    print(explained.round(3).to_string(index=False))
    print(forecast.round(4).to_string(index=False))
    figure(table)


if __name__ == "__main__":
    main()
