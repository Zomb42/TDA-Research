"""B1. Does the shape of BTC's recent return path help forecast what comes next?

The earlier BTC pilot scored 348 one-minute forecasts from one night of data.
This uses the 2.8 years of Binance BTCUSDT 5-minute bars already on disk:
about 24,000 hourly decision points.

At every hour, from the past 24 hours of 5-minute returns:

  shape features   the same construction as the earlier pilot. Standardise the
                   returns, turn them into points (return now, 15 minutes later,
                   30 minutes later), keep 128 evenly spaced points, and take the
                   persistence diagram. H1 = loops in that cloud, H0 = clumps.
                   Because the returns are standardised first, these do not just
                   measure volatility.
  plain features   realized volatility over the last 1 hour, 4 hours, 24 hours and
                   7 days (the standard "HAR" volatility forecast), last-hour and
                   24-hour return, autocorrelation, volume, hour of the day
  plain tail features  how fat-tailed the same 24 hours were: kurtosis, the average
                   absolute move relative to volatility, and the share of all variance
                   in the single largest move. A standardised cloud changes shape when
                   a few moves dominate, so these are the fair plain competitor.

Three things to forecast: volatility over the next hour, volatility over the
next 24 hours, and the next hour's return. A straight-line model is refitted
every 30 days on all earlier data and scored on the next 30 days.

    conda run -n tda python btc/studies/b01_shape_vs_volatility.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "equity"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from ripser import ripser

from tdaeq import evaluate, plots

plots.RESULTS = REPO / "btc" / "results"
STUDY = "b01_shape_vs_volatility"
BARS = REPO / "market_data/datasets/btc_binance_2024_2026-10-27/bars_5m.parquet"
DAY, WEEK, HOUR = 288, 2016, 12                      # in 5-minute bars
SHAPE = ["h1_longest", "h1_total", "h1_count", "h0_total"]
LABELS = {"h1_longest": "Longest loop (H1)", "h1_total": "Total loop lifetime (H1)",
          "h1_count": "Number of loops (H1)", "h0_total": "Total clump lifetime (H0)"}


def shape_of(window):
    """Persistence summaries of the delay cloud of one standardised 24-hour window."""
    z = (window - window.mean()) / window.std()
    cloud = np.column_stack([z[:-6], z[3:-3], z[6:]])
    cloud = cloud[np.linspace(0, len(cloud) - 1, 128).astype(int)]
    h0, h1 = ripser(cloud, maxdim=1)["dgms"]
    life = h1[:, 1] - h1[:, 0]
    return [life.max() if len(life) else 0.0, life.sum(), len(life), h0[np.isfinite(h0[:, 1]), 1].sum()]


def build():
    cache = plots.folder(STUDY) / "features.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    bars = pd.read_parquet(BARS)
    r = np.diff(np.log(bars.close.to_numpy())) * 1e4          # basis points; r[i] is known at when[i]
    when = pd.DatetimeIndex(bars.available_at_utc.to_numpy()[1:])
    volume = bars.quote_volume.to_numpy()[1:]
    square = np.r_[0.0, np.cumsum(r * r)]
    total = np.r_[0.0, np.cumsum(r)]
    vol_sum = np.r_[0.0, np.cumsum(volume)]
    rv = lambda end, n: np.sqrt((square[end + 1] - square[end + 1 - n]) / n)     # volatility of the n returns ending at `end`
    rows = []
    for k in np.flatnonzero(when.minute == 0):
        if k < WEEK or k + DAY >= len(r):
            continue
        window = r[k - DAY + 1:k + 1]
        a, b = window[1:] - window[1:].mean(), window[:-1] - window[:-1].mean()
        z = (window - window.mean()) / window.std()
        rows.append({
            "time": when[k],
            "rv_1h": np.log(rv(k, HOUR)), "rv_4h": np.log(rv(k, 4 * HOUR)),
            "rv_24h": np.log(rv(k, DAY)), "rv_7d": np.log(rv(k, WEEK)),
            "ret_1h": total[k + 1] - total[k + 1 - HOUR], "ret_24h": total[k + 1] - total[k + 1 - DAY],
            "autocorr": (a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()),
            "volume": np.log((vol_sum[k + 1] - vol_sum[k + 1 - HOUR]) * 24 / (vol_sum[k + 1] - vol_sum[k + 1 - DAY])),
            "kurtosis": np.log((z ** 4).mean()), "abs_move_ratio": np.abs(z).mean(),
            "largest_move_share": (window ** 2).max() / (window ** 2).sum(),
            **dict(zip(SHAPE, shape_of(window))),
            "next_vol_1h": np.log(rv(k + HOUR, HOUR)), "next_vol_24h": np.log(rv(k + DAY, DAY)),
            "next_ret_1h": total[k + 1 + HOUR] - total[k + 1]})
    table = pd.DataFrame(rows).set_index("time")
    table.to_parquet(cache)
    return table


def walk_forward(x, y, purge, first=180 * 24, step=30 * 24):
    """Squared errors and forecasts from refitting every 30 days on all earlier, fully known rows."""
    forecast = np.full(len(y), np.nan)
    for begin in range(first, len(y), step):
        train = slice(0, begin - purge)
        coef = np.linalg.lstsq(x[train], y[train], rcond=None)[0]
        block = slice(begin, min(begin + step, len(y)))
        forecast[block] = x[block] @ coef
    return forecast


def main():
    table = build()
    table = table[np.isfinite(table).all(axis=1)]             # drops 2 hours in which the price did not move at all
    hours = pd.get_dummies(table.index.hour, prefix="hour", dtype=float).to_numpy()
    plain_vol = np.column_stack([hours, table[["rv_1h", "rv_4h", "rv_24h", "rv_7d", "autocorr", "volume"]],
                                 np.abs(table.ret_1h), np.abs(table.ret_24h)])
    tails = table[["kurtosis", "abs_move_ratio", "largest_move_share"]].to_numpy()
    tails = (tails - tails.mean(axis=0)) / tails.std(axis=0)
    shape = table[SHAPE].to_numpy()
    shape = (shape - shape.mean(axis=0)) / shape.std(axis=0)
    plain_ret = np.column_stack([np.ones(len(table)), table[["ret_1h", "ret_24h"]],
                                 table.autocorr * table.ret_1h])
    shape_ret = np.column_stack([shape, shape * table.ret_1h.to_numpy()[:, None]])   # shape, and shape as a switch on momentum

    explained = []
    design = np.column_stack([np.ones(len(table)), table[["rv_1h", "rv_4h", "rv_24h", "rv_7d", "autocorr", "volume"]],
                              np.abs(table.ret_1h), np.abs(table.ret_24h)])
    share = lambda x, y: 1 - ((y - x @ np.linalg.lstsq(x, y, rcond=None)[0]) ** 2).mean()
    for j, name in enumerate(SHAPE):
        explained.append({"shape_feature": LABELS[name], "explained_by_plain": share(design, shape[:, j]),
                          "explained_by_plain_and_tails": share(np.column_stack([design, tails]), shape[:, j])})
    explained = pd.DataFrame(explained)

    with_tails = np.column_stack([plain_vol, tails])
    tests = [("Volatility, next hour", "Plain", "next_vol_1h", plain_vol, shape, 1, 48),
             ("Volatility, next hour", "Plain + tails", "next_vol_1h", with_tails, shape, 1, 48),
             ("Volatility, next hour", "Plain: what do tails add?", "next_vol_1h", plain_vol, tails, 1, 48),
             ("Volatility, next 24 hours", "Plain", "next_vol_24h", plain_vol, shape, 24, 96),
             ("Volatility, next 24 hours", "Plain + tails", "next_vol_24h", with_tails, shape, 24, 96),
             ("Volatility, next 24 hours", "Plain: what do tails add?", "next_vol_24h", plain_vol, tails, 24, 96),
             ("Return, next hour", "Plain", "next_ret_1h", plain_ret, shape_ret, 1, 48)]
    rows = []
    for label, baseline, target, base, extra, purge, block in tests:
        y = table[target].to_numpy()
        plain = walk_forward(base, y, purge)
        both = walk_forward(np.column_stack([base, extra]), y, purge)
        scored = np.isfinite(plain)
        naive = (y[scored] - y[:scored.argmax()].mean()) ** 2                    # forecast = the early average
        e_plain, e_both = (y[scored] - plain[scored]) ** 2, (y[scored] - both[scored]) ** 2
        change, low, high = evaluate.mean_ci(e_both - e_plain, block=block)
        rows.append({"target": label, "baseline": baseline, "forecasts": int(scored.sum()),
                     "plain_error_vs_naive_pct": (e_plain.mean() / naive.mean() - 1) * 100,
                     "corr_baseline": np.corrcoef(plain[scored], y[scored])[0, 1],
                     "corr_with_added": np.corrcoef(both[scored], y[scored])[0, 1],
                     "shape_changes_error_pct": change / e_plain.mean() * 100,
                     "low": low / e_plain.mean() * 100, "high": high / e_plain.mean() * 100})
    scores = pd.DataFrame(rows)

    out = plots.folder(STUDY)
    explained.to_csv(out / "explained_by_plain.csv", index=False)
    scores.to_csv(out / "forecast_scores.csv", index=False)
    pd.set_option("display.width", 220)
    print(f"{len(table):,} hourly decision points, {table.index[0]} to {table.index[-1]}")
    print(explained.round(3).to_string(index=False))
    print(scores.round(3).to_string(index=False))

    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 3.6), layout="constrained")
    rows = np.arange(len(explained))[::-1]
    left.barh(rows + 0.19, explained.explained_by_plain * 100, color=plots.BLUE, height=0.34, label="By plain features")
    left.barh(rows - 0.19, explained.explained_by_plain_and_tails * 100, color=plots.ORANGE, height=0.34,
              label="By plain + tail features")
    left.set_yticks(rows, explained.shape_feature)
    left.legend(loc="lower right")
    left.set_xlim(0, 100)
    left.set_xlabel("% of the shape feature explained")
    left.grid(axis="y", visible=False)
    left.set_title("Is the shape new information?")
    shown = scores[~scores.baseline.str.contains("what do")]
    names = list(dict.fromkeys(shown.target))
    for offset, (baseline, color) in zip((0.14, -0.14), (("Plain", plots.BLUE), ("Plain + tails", plots.ORANGE))):
        part = shown[shown.baseline == baseline]
        y = np.array([len(names) - 1 - names.index(t) for t in part.target]) + offset
        right.errorbar(part.shape_changes_error_pct, y,
                       xerr=[part.shape_changes_error_pct - part.low, part.high - part.shape_changes_error_pct],
                       fmt="o", color=color, elinewidth=2, capsize=0, label=f"Added to: {baseline.lower()}")
    right.axvline(0, color=plots.INK_SOFT, lw=1)
    right.legend(loc="lower left")
    right.set_yticks(np.arange(len(names))[::-1], names)
    right.grid(axis="y", visible=False)
    right.set_xlabel("Change in forecast error from adding shape, % (left = better)")
    right.set_title("Does it improve a forecast? 95% intervals")
    plots.save(fig, STUDY, "1_shape_vs_plain.png")


if __name__ == "__main__":
    main()
