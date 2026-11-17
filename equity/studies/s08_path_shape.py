"""E1. Does the peaks-and-valleys shape of a stock's own recent path help forecast it?

This tests the feature at the centre of "Topological Attention for Time Series
Forecasting" (Zeng et al., NeurIPS 2021) on our data, without the neural network.

The paper's TDA is different from s01-s07. It looks at ONE series at a time:
the barcode of a path lists every dip that was later recovered and every bump
that was later given back, with the level it happened at (topology.path_bars).

For every stock and day we take its path over the last 20 and 60 days with SPY
removed, in units of the stock's own daily volatility, ending at today = 0.

  barcode features   total / longest / number of swings, plus an 18-cell grid
                     (valleys or peaks  x  below, near, above today's level  x  small, medium, large)
  plain features     net move, range, distance travelled, position in the range,
                     day-to-day autocorrelation, 1- and 5-day moves, move versus peers, volatility

Three questions:
  1. How much of the barcode summaries do the plain path measures already explain?
  2. Is the bounce (s03's signal) stronger for stocks whose path has been choppy?
  3. Does a learner forecast tomorrow better when the barcode is added to the plain
     features?  Trained on all earlier years, scored on the next year, 2019 onward.

    conda run -n tda python equity/studies/s08_path_shape.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge

from s05_when_is_the_bounce import THIRDS, spread, thirds_within_day
from tdaeq import data, evaluate, plots, signals, topology

STUDY = "s08_path_shape"
WINDOWS = [20, 60]
FIRST_TEST_YEAR = 2019
SUMMARY = ["swing_total", "swing_longest", "swing_count"]
IMAGE = [f"{side}_{level}_{size}" for side in ("valley", "peak") for level in ("below", "near", "above")
         for size in ("small", "medium", "large")]
PATH_PLAIN = ["net", "range", "travel", "position"]


def describe_path(p, n):
    """p = n+1 levels ending at 0. Returns barcode summaries, the 18-cell grid, plain measures."""
    scale = math.sqrt(n)                       # a random walk moves about sqrt(n) in n days
    total = longest = 0.0
    count = 0
    image = [0.0] * 18
    for side, bars in ((0, topology.path_bars(p)), (1, topology.path_bars([-v for v in p]))):
        for birth, death, _ in bars:
            length = death - birth
            total += length
            longest = max(longest, length)
            count += length >= 1
            if length < 0.5:                   # ignore wiggles under half a daily move
                continue
            level = (birth if side == 0 else -birth) / scale      # where the valley/peak sits versus today
            row = 0 if level < -0.5 else (1 if level <= 0.5 else 2)
            col = 0 if length < 1.5 else (1 if length < 3 else 2)
            image[side * 9 + row * 3 + col] += length
    low, high = min(p), max(p)
    travel = sum(abs(p[k + 1] - p[k]) for k in range(n))
    return ([total / scale, longest / scale, count], image,
            [-p[0] / scale, (high - low) / scale, travel / scale, -low / (high - low)])


def build_features(state):
    """One table per feature, days x stocks. Slow part (about two minutes), so it is cached."""
    cache = plots.folder(STUDY) / "features.npz"
    if cache.exists():
        return dict(np.load(cache))
    days, stocks = state.surprise.shape
    finite = np.isfinite(state.surprise)
    z = np.where(finite, state.surprise, 0.0)
    level = np.vstack([np.zeros((1, stocks)), np.cumsum(z, axis=0)])
    seen = np.vstack([np.zeros((1, stocks), int), np.cumsum(finite, axis=0)])
    out = {f"{name}_{n}": np.full((days, stocks), np.nan)
           for n in WINDOWS for name in SUMMARY + IMAGE + PATH_PLAIN}
    out["autocorr_60"] = np.full((days, stocks), np.nan)
    for n in WINDOWS:
        names = [f"{name}_{n}" for name in SUMMARY + IMAGE + PATH_PLAIN]
        for t in range(n - 1, days):
            for i in np.flatnonzero(seen[t + 1] - seen[t + 1 - n] == n):      # all n days present
                p = (level[t + 1 - n:t + 2, i] - level[t + 1, i]).tolist()
                summary, image, plain = describe_path(p, n)
                for name, value in zip(names, summary + image + plain):
                    out[name][t, i] = value
    for t in range(59, days):
        cols = np.flatnonzero(seen[t + 1] - seen[t - 59] == 60)
        a, b = z[t - 58:t + 1, cols], z[t - 59:t, cols]
        a, b = a - a.mean(axis=0), b - b.mean(axis=0)
        out["autocorr_60"][t, cols] = (a * b).sum(axis=0) / np.sqrt((a * a).sum(axis=0) * (b * b).sum(axis=0))
    np.savez_compressed(cache, **out)
    return out


def explained_by_plain(feats, ok):
    """Share of each barcode summary's variation that plain path measures explain (all stock-days pooled)."""
    rows = []
    for n in WINDOWS:
        use = ok & np.isfinite(feats[f"swing_total_{n}"])
        net, rng, travel, pos = (feats[f"{name}_{n}"][use] for name in PATH_PLAIN)
        x = np.column_stack([np.ones(use.sum()), np.abs(net), rng, travel, pos])
        for name in SUMMARY:
            y = feats[f"{name}_{n}"][use]
            fitted = x @ np.linalg.lstsq(x, y, rcond=None)[0]
            rows.append({"window": n, "barcode_summary": name,
                         "explained_by_plain": 1 - ((y - fitted) ** 2).sum() / ((y - y.mean()) ** 2).sum()})
    return pd.DataFrame(rows)


def bounce_by_choppiness(feats, vs_peers, outcome, later):
    """s05's test with three new splits. High third = choppiest path."""
    days = len(outcome)
    efficiency = np.abs(feats["net_60"]) / feats["travel_60"]          # 1 = straight line, 0 = went nowhere
    splits = {"Barcode: total swing length": feats["swing_total_60"],
              "Barcode: longest recovered swing": feats["swing_longest_60"],
              "Plain: 1 - |net move| / distance travelled": 1 - efficiency}
    daily = {}
    for t in range(days - 1):
        traded = np.isfinite(vs_peers[t])
        if not traded.any():
            continue
        for name, values in splits.items():
            bucket = thirds_within_day(np.where(traded, values[t], np.nan))
            for b in range(3):
                daily.setdefault((name, THIRDS[b]), np.full(days, np.nan))[t] = spread(
                    np.where(bucket == b, vs_peers[t], np.nan), outcome[t])
    rows = []
    for (name, bucket), series in daily.items():
        for label, mask in (("before 2024", ~later), ("2024 on", later)):
            use = mask & np.isfinite(series)
            mean, low, high = evaluate.mean_ci(series[use], block=10)
            rows.append({"split": name, "bucket": bucket, "period": label, "days": int(use.sum()),
                         "spread_bps": mean * 1e4, "low": low * 1e4, "high": high * 1e4})
    return pd.DataFrame(rows)


def centred_ranks(table):
    """Rank each column across today's stocks, scaled to -0.5..0.5. Missing values become 0 (the middle)."""
    ranks = rankdata(table, axis=0, nan_policy="omit")
    counts = np.isfinite(table).sum(axis=0)
    return np.nan_to_num((ranks - 0.5) / np.maximum(counts, 1) - 0.5)


def learner_test(panel, feats, extra, outcome):
    plain = [f"{name}_{n}" for n in WINDOWS for name in PATH_PLAIN] + ["autocorr_60"] + list(extra)
    barcode = [f"{name}_{n}" for n in WINDOWS for name in SUMMARY + IMAGE]
    tables = {**feats, **extra}
    efficiency = {f"efficiency_{n}": np.abs(feats[f"net_{n}"]) / feats[f"travel_{n}"] for n in WINDOWS}
    tables.update(efficiency)
    plain += list(efficiency)
    columns = plain + barcode
    blocks, targets, day_of_row = [], [], []
    for t in range(len(panel.dates) - 1):
        ok = np.isfinite(feats["swing_total_60"][t]) & np.isfinite(outcome[t])
        if ok.sum() < 50:
            continue
        blocks.append(centred_ranks(np.column_stack([tables[c][t, ok] for c in columns])))
        targets.append(centred_ranks(outcome[t, ok][:, None])[:, 0])
        day_of_row.append(np.full(ok.sum(), t))
    X, y, day = np.vstack(blocks), np.concatenate(targets), np.concatenate(day_of_row)
    year = panel.dates.year.to_numpy()[day]
    sets = {"Plain path measures": np.arange(len(plain)),
            "Barcode only": np.arange(len(plain), len(columns)),
            "Plain + barcode": np.arange(len(columns))}
    learners = {"Straight-line fit (ridge)": lambda: Ridge(alpha=1000.0),
                "Boosted trees": lambda: HistGradientBoostingRegressor(
                    max_iter=100, learning_rate=0.05, max_leaf_nodes=8, min_samples_leaf=2000,
                    l2_regularization=1.0, early_stopping=False, random_state=0)}
    test_days = np.unique(day[year >= FIRST_TEST_YEAR])
    scores = {}
    for learner, make in learners.items():
        for name, cols in sets.items():
            prediction = np.full(len(y), np.nan)
            for test_year in range(FIRST_TEST_YEAR, year.max() + 1):
                train, test = year < test_year, year == test_year
                prediction[test] = make().fit(X[train][:, cols], y[train]).predict(X[test][:, cols])
            scores[learner, name] = np.array([evaluate.rank_ic(prediction[day == t], y[day == t]) for t in test_days])
    # reference with nothing fitted: bet against today's move versus peers (the s03 signal)
    peers = columns.index("vs_peers")
    reference = np.array([evaluate.rank_ic(-X[day == t, peers][X[day == t, peers] != 0],
                                           y[day == t][X[day == t, peers] != 0]) for t in test_days])
    later = panel.dates[test_days] >= data.SPLIT
    rows = []
    for label, mask in ((f"{FIRST_TEST_YEAR}-2023", ~later), ("2024 on", later)):
        mean, low, high = evaluate.mean_ci(reference[mask], block=20)
        rows.append({"learner": "No fitting", "features": "Bet against move versus peers", "period": label,
                     "days": int(mask.sum()), "bounce_score": mean, "low": low, "high": high})
        for (learner, name), series in scores.items():
            mean, low, high = evaluate.mean_ci(series[mask], block=20)
            rows.append({"learner": learner, "features": name, "period": label, "days": int(mask.sum()),
                         "bounce_score": mean, "low": low, "high": high})
        for learner in learners:
            gain = scores[learner, "Plain + barcode"][mask] - scores[learner, "Plain path measures"][mask]
            mean, low, high = evaluate.mean_ci(gain, block=20)
            rows.append({"learner": learner, "features": "GAIN from adding the barcode", "period": label,
                         "days": int(mask.sum()), "bounce_score": mean, "low": low, "high": high})
    return pd.DataFrame(rows), len(plain), len(barcode), len(y)


def figure_example(panel, state, symbol="XOM", n=60):
    """What the barcode of one path is, on a real stock."""
    i, t = list(panel.symbols).index(symbol), len(panel.dates) - 1
    z = state.surprise[t - n + 1:t + 1, i]
    p = np.r_[0.0, np.cumsum(z)] - z.sum()
    fig, ax = plt.subplots(figsize=(9, 4.2), layout="constrained")
    ax.plot(np.arange(-n, 1), p, color=plots.GRAY, lw=1.6)
    for bars, sign, color, label in ((topology.path_bars(p), 1, plots.BLUE, "Dip that was recovered (valley bar)"),
                                     (topology.path_bars(-p), -1, plots.ORANGE, "Bump that was given back (peak bar)")):
        big = [b for b in bars if b[1] - b[0] >= 1.5]
        for k, (birth, death, where) in enumerate(big):
            ax.plot([where - n, where - n], [sign * birth, sign * death], color=color, lw=3,
                    solid_capstyle="round", label=label if k == 0 else None)
    ax.axhline(0, color=plots.AXIS, lw=1)
    ax.set_xlabel("Trading days before November 9, 2026")
    ax.set_ylabel("Path with SPY removed, in daily moves (today = 0)")
    ax.legend(loc="best")
    ax.set_title(f"The barcode of one path: {symbol}, last {n} days\n"
                 "Each bar runs from a valley up to the level where it was recovered, or from a peak down. "
                 "Swings of 1.5+ daily moves shown.", fontsize=10)
    plots.save(fig, STUDY, "1_what_the_barcode_is.png")


def figure_learners(table):
    sets = ["Bet against move versus peers", "Plain path measures", "Barcode only", "Plain + barcode"]
    short = ["Reversal signal\n(nothing fitted)", "Plain path\nmeasures", "Barcode\nonly", "Plain +\nbarcode"]
    learners = [l for l in dict.fromkeys(table.learner) if l != "No fitting"]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4), sharey=True, layout="constrained")
    for ax, learner in zip(axes, learners):
        for offset, (period, color) in enumerate(zip(dict.fromkeys(table.period), (plots.BLUE, plots.ORANGE))):
            part = table[(table.period == period) & table.learner.isin([learner, "No fitting"])].set_index("features").loc[sets]
            x = np.arange(len(sets)) + (-0.12 if offset == 0 else 0.12)
            ax.errorbar(x, part.bounce_score, yerr=[part.bounce_score - part.low, part.high - part.bounce_score],
                        fmt="o", color=color, elinewidth=2, capsize=0, label=period)
        ax.axhline(0, color=plots.INK_SOFT, lw=1)
        ax.set_xticks(np.arange(len(sets)), short)
        ax.set_xlim(-0.5, len(sets) - 0.5)
        ax.grid(axis="x", visible=False)
        ax.set_title(learner)
    axes[0].set_ylabel("Rank correlation of forecast with next day's move")
    axes[0].legend(loc="upper left")
    fig.suptitle("Does adding a stock's path barcode improve the forecast? Scored on years the learner had not seen, 95% intervals",
                 x=0.01, ha="left", fontweight="bold", fontsize=10)
    plots.save(fig, STUDY, "2_learners.png")


def main():
    panel = data.load_panel()
    state = signals.build_state(panel)
    days, n = panel.returns.shape
    feats = build_features(state)
    vs_peers = np.vstack([signals.minus_group_mean(state.surprise[t], state.group[t]) for t in range(days)])
    next_cc = np.vstack([panel.close_adj[1:] / panel.close_adj[:-1] - 1, np.full((1, n), np.nan)])
    spy_next = np.r_[panel.market_close[1:] / panel.market_close[:-1] - 1, np.nan]
    outcome = next_cc - state.beta * spy_next[:, None]
    later = panel.dates >= data.SPLIT
    out = plots.folder(STUDY)
    pd.set_option("display.width", 200)

    explained = explained_by_plain(feats, np.isfinite(outcome))
    explained.to_csv(out / "explained_by_plain.csv", index=False)
    print(explained.round(4).to_string(index=False))

    buckets = bounce_by_choppiness(feats, vs_peers, outcome, later)
    buckets.to_csv(out / "bounce_by_choppiness.csv", index=False)
    print(buckets.round(2).to_string(index=False))

    extra = {"z1": state.surprise, "z5": signals.rolling_sum(np.nan_to_num(state.surprise), 5), "vs_peers": vs_peers,
             "log_sigma": np.log(state.sigma)}
    learners, n_plain, n_barcode, n_rows = learner_test(panel, feats, extra, outcome)
    learners.to_csv(out / "learners.csv", index=False)
    print(f"{n_rows:,} stock-days, {n_plain} plain features, {n_barcode} barcode features")
    print(learners.round(4).to_string(index=False))

    figure_example(panel, state)
    figure_learners(learners)


if __name__ == "__main__":
    main()
