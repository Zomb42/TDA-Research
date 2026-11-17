"""A1. How much of the "shape" in stock correlations is real, and how much is noise?

For each date and window length we compute the real persistence diagram and
compare it with diagrams from scrambled data:

  noise    each stock keeps its link to SPY, everything else is shuffled in time
  sectors  each stock keeps its link to SPY and to its sector, the rest is shuffled

A real feature must beat what the scrambled data produces.

Pure noise looks the same on every date (it depends only on how many stocks
and days there are), and its diagrams are slow to compute, so the noise level
is measured once per window length from a few dates. The sector version is
fast and is redone on every date.

    conda run -n tda python equity/studies/s01_noise_floor.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tdaeq import clusters, data, factors, plots, topology

STUDY = "s01_noise_floor"
WINDOWS = [120, 252, 504]
DRAWS = 20            # scrambled copies; the largest of 20 is roughly a 95% ceiling
STEP = 50             # days between dates


def ring_lifetimes(history, market):
    return topology.diagrams(factors.geometry(history, market).distance)


def noise_level(panel, window, rng):
    """Pure-noise reference for one window length, pooled over DRAWS scrambles on spread-out dates."""
    dates = np.linspace(max(WINDOWS) + 1, len(panel.dates) - 1, 5).astype(int)
    draws = []
    for t in np.repeat(dates, DRAWS // 5):
        cols = panel.eligible(t, history=max(WINDOWS))
        history, market = panel.returns[t - window:t, cols], panel.market[t - window:t]
        draws.append(ring_lifetimes(topology.market_only(history, market, rng), market))
    lives = [topology.lifetimes(d[1]) for d in draws]
    return {"draws": draws,
            "h1_count_noise": np.mean([len(l) for l in lives]),
            "h1_total_noise": np.mean([l.sum() for l in lives]),
            "h1_ceiling_noise": max(l.max() for l in lives),
            "h0_floor_noise": np.quantile(np.concatenate([d[0][:, 1] for d in draws]), 0.01)}


def compare(history, market, labels, noise, rng):
    geo = factors.geometry(history, market)
    real = topology.diagrams(geo.distance)
    real_life = topology.lifetimes(real[1])
    off_diagonal = geo.corr[np.triu_indices(len(geo.corr), 1)]
    sector_lives = [topology.lifetimes(ring_lifetimes(
        topology.market_and_groups(history, market, labels, rng), market)[1]) for _ in range(DRAWS)]
    sector_ceiling = max(l.max() for l in sector_lives)
    row = {"mean_abs_corr": np.abs(off_diagonal).mean(),
           "h1_count": len(real_life), "h1_total": real_life.sum(), "h1_max": real_life.max(),
           "h1_count_noise": noise["h1_count_noise"], "h1_total_noise": noise["h1_total_noise"],
           "h1_ceiling_noise": noise["h1_ceiling_noise"],
           "loops_above_noise": int((real_life > noise["h1_ceiling_noise"]).sum()),
           "h0_share_below_noise": (real[0][:, 1] < noise["h0_floor_noise"]).mean(),
           "h1_total_sectors": np.mean([l.sum() for l in sector_lives]),
           "h1_ceiling_sectors": sector_ceiling,
           "loops_above_sectors": int((real_life > sector_ceiling).sum())}
    return row, real


def planted_ring(days, share, rng, stocks=200, ring=30):
    """Fake market in which `ring` stocks sit on a circle: each moves with its
    neighbours on the circle and against the stocks opposite. `share` is the
    fraction of those stocks' non-market variance that the circle explains."""
    market = rng.normal(0, 0.01, days)
    beta = rng.uniform(0.6, 1.4, stocks)
    own = rng.normal(0, 0.015, (days, stocks))
    angle = np.linspace(0, 2 * np.pi, ring, endpoint=False)
    f1, f2 = rng.normal(0, 0.015, (2, days))
    circle = np.outer(f1, np.cos(angle)) + np.outer(f2, np.sin(angle))
    own[:, :ring] = np.sqrt(share) * circle + np.sqrt(1 - share) * own[:, :ring]
    return market[:, None] * beta + own, market


def power_table(rng, shares=(0.1, 0.2, 0.3, 0.5), trials=25):
    """How often is a planted ring of a given strength detected above the noise ceiling?"""
    rows = []
    for days in WINDOWS:
        # share 0 = the same fake market with no ring: its longest bar over DRAWS runs is the ceiling
        ceiling = max(topology.lifetimes(ring_lifetimes(*planted_ring(days, 0.0, rng))[1]).max()
                      for _ in range(DRAWS))
        for share in shares:
            hits, longest = 0, []
            for _ in range(trials):
                life = topology.lifetimes(ring_lifetimes(*planted_ring(days, share, rng))[1])
                hits += life.max() > ceiling
                longest.append(life.max())
            rows.append({"window": days, "share": share, "detected": hits / trials,
                         "median_longest_bar": np.median(longest)})
    return pd.DataFrame(rows)


def figure_diagrams(examples, date):
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), sharey=True, layout="constrained")
    for ax, window in zip(axes, WINDOWS):
        real, noise_draws, row = examples[window]
        noise = np.vstack([d[1] for d in noise_draws[:3]])
        ax.scatter(noise[:, 0], noise[:, 1] - noise[:, 0], s=8, color=plots.GRAY, alpha=0.35,
                   linewidths=0, label="Scrambled (noise)")
        ax.scatter(real[1][:, 0], topology.lifetimes(real[1]), s=22, color=plots.BLUE,
                   edgecolors=plots.SURFACE, linewidths=0.6, label="Real data")
        ax.axhline(row["h1_ceiling_noise"], color=plots.INK_SOFT, lw=1, ls="--")
        ax.text(0.02, row["h1_ceiling_noise"], " noise ceiling", transform=ax.get_yaxis_transform(),
                va="bottom", fontsize=8.5, color=plots.INK_SOFT)
        ax.set_title(f"{window} days: {row['loops_above_noise']} above the ceiling")
        ax.set_xlabel("Distance at which the ring closes")
    axes[0].set_ylabel("How long the ring lasts (lifetime)")
    axes[0].legend(loc="upper left")
    fig.suptitle(f"Rings (H1) among stocks on {date}: real data versus scrambled data",
                 x=0.01, ha="left", fontweight="bold")
    return fig


def figure_over_time(table):
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6), layout="constrained")
    one = table[table.window == 252]
    ax = axes[0]
    for window, color in zip(WINDOWS, plots.SERIES):
        part = table[table.window == window]
        ax.plot(part.date, part.h0_share_below_noise * 100, color=color, label=f"{window} days")
    ax.set_ylim(0, 105)
    ax.set_title("Links between groups (H0) that are\ncloser than noise allows, %")
    ax.legend(title="Window", loc="lower right")
    ax = axes[1]
    ax.axhline(one.h1_total_noise.iloc[0], color=plots.GRAY, label="Scrambled (noise)")
    ax.plot(one.date, one.h1_total_sectors, color=plots.ORANGE, label="Market + sectors only")
    ax.plot(one.date, one.h1_total, color=plots.BLUE, label="Real data")
    ax.set_ylim(0)
    ax.set_title("Total ring lifetime (H1), 252-day window\nReal data has LESS than noise")
    ax.legend(loc="center right")
    ax = axes[2]
    ax.plot(one.date, one.loops_above_noise, color=plots.BLUE, label="Above noise ceiling")
    ax.plot(one.date, one.loops_above_sectors, color=plots.ORANGE, label="Above market + sectors ceiling")
    ax.set_ylim(0)
    ax.set_title("Number of real rings that beat\nthe scrambled data, 252-day window")
    ax.legend(loc="upper left")
    return fig


def figure_power(power, real_longest):
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6), layout="constrained")
    for window, color in zip(WINDOWS, plots.SERIES):
        part = power[power.window == window]
        axes[0].plot(part.share * 100, part.detected * 100, "o-", color=color, label=f"{window} days")
        axes[1].plot(part.share * 100, part.median_longest_bar, "o-", color=color, label=f"{window} days")
    axes[0].set(ylim=(0, 105), xlabel="Variance explained by the planted ring, %",
                title="Planted ring detected, % of trials")
    axes[0].legend(title="Window")
    axes[1].axhline(real_longest, color=plots.INK_SOFT, lw=1, ls="--")
    axes[1].text(0.98, real_longest, "longest real ring (median date) ", ha="right", va="bottom",
                 transform=axes[1].get_yaxis_transform(), fontsize=8.5, color=plots.INK_SOFT)
    axes[1].set(ylim=0, xlabel="Variance explained by the planted ring, %",
                title="Lifetime of the longest ring found")
    return fig


def main():
    panel = data.load_panel()
    rng = np.random.default_rng(20261116)
    rows, examples = [], {}
    noise = {window: noise_level(panel, window, rng) for window in WINDOWS}
    print("noise levels done", flush=True)
    anchors = list(range(max(WINDOWS) + 1, len(panel.dates), STEP))
    for t in anchors:
        cols = panel.eligible(t, history=max(WINDOWS))
        labels = clusters.factorize(panel.sectors[cols])
        for window in WINDOWS:
            row, real = compare(panel.returns[t - window:t, cols], panel.market[t - window:t],
                                labels, noise[window], rng)
            rows.append({"date": panel.dates[t - 1], "window": window, "stocks": len(cols), **row})
            if t == anchors[-1]:
                examples[window] = (real, noise[window]["draws"], row)
    table = pd.DataFrame(rows)
    print("dates done", flush=True)
    power = power_table(rng)

    out = plots.folder(STUDY)
    table.to_csv(out / "by_date.csv", index=False)
    power.to_csv(out / "planted_ring_power.csv", index=False)
    plots.save(figure_diagrams(examples, panel.dates[anchors[-1] - 1].date()), STUDY, "1_real_vs_noise.png")
    plots.save(figure_over_time(table), STUDY, "2_over_time.png")
    plots.save(figure_power(power, table[table.window == 252].h1_max.median()), STUDY, "3_planted_ring_power.png")

    summary = table.groupby("window").agg(
        dates=("date", "size"), h0_share_real=("h0_share_below_noise", "mean"),
        h1_total_real=("h1_total", "mean"), h1_total_noise=("h1_total_noise", "mean"),
        h1_total_sectors=("h1_total_sectors", "mean"), h1_longest_real=("h1_max", "median"),
        noise_ceiling=("h1_ceiling_noise", "median"), loops_above_noise=("loops_above_noise", "mean"),
        loops_above_sectors=("loops_above_sectors", "mean"))
    summary["corr_h1total_vs_meanabscorr"] = [
        np.corrcoef(g.h1_total, g.mean_abs_corr)[0, 1] for _, g in table.groupby("window")]
    summary.to_csv(out / "summary.csv")
    print(summary.round(3).T.to_string())
    print(power.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
