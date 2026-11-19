"""H1. Does the 1D-sweep barcode of a stock's path WITHIN THE DAY say which late moves reverse?

Study 8 tested the barcode of each stock's daily path over 20-60 days and found
nothing. The late-day reversal lives inside one day, so this applies the same
barcode (topology.path_bars: valley bars sweeping up, peak bars sweeping down)
to each stock's 5-minute path from the open to 3:40 pm, the moment the signal
is read. Every 5th trading day, 2017-2026 (market_data/download_equity_intraday.py
--kinds five_minutes --every 5).

Path: log price at the open and at the end of each 5-minute bar to 3:40 pm
(75 points), in units of the stock's daily volatility, ending at 0.

  barcode features   valley and peak bars: total length, longest, number of
                     swings over 0.25 daily moves, and a 2 x 3 x 3 grid (valleys
                     or peaks x below / near / above the 3:40 price x small /
                     medium / large)
  plain features     the signal (3:40 price against the day's average price),
                     the same against peers, net move since the open, range,
                     distance travelled, where 3:40 sits in the day's range,
                     5-minute volatility and autocorrelation, last hour's move,
                     share of volume in the last hour

Target: the move from 3:50 pm to the next open, against the stock's peers
(the trade of studies 10-12).

  1. How much of the barcode do plain path measures already explain?
  2. Is the reversal stronger for choppy paths?  (barcode against plain choppiness)
  3. Does a learner forecast better with the barcode, and does the book improve?
     Trained on earlier years, scored on the next, 2019 onward.

The prepared table is cached for study 14.

    conda run -n tda python equity/studies/s13_intraday_barcode.py
"""
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge

from s05_when_is_the_bounce import THIRDS, spread, thirds_within_day
from s08_path_shape import centred_ranks
from s11_late_day_characterize import tables
from s04_peer_reversal_book import exposures_for
from tdaeq import data, evaluate, plots, portfolio, signals, topology

STUDY = "s13_intraday_barcode"
FIVE = data.dataset_folder(data.INTRADAY) / "raw" / "five_minutes"
POINTS = 75                                   # open + 74 bar closes, 9:35 ... 15:40
SUMMARY = [f"{side}_{what}" for side in ("valley", "peak") for what in ("total", "longest", "count")]
GRID = [f"{side}_{level}_{size}" for side in ("valley", "peak") for level in ("below", "near", "above")
        for size in ("small", "medium", "large")]
PLAIN = ["signal", "signal_vs_peers", "net", "range", "travel", "position", "vol_5m", "autocorr_5m",
         "last_hour", "late_volume_share", "straightness"]
FIRST_TEST_YEAR = 2019


def barcode(path):
    summary, grid = [], [0.0] * 18
    for side, bars in ((0, topology.path_bars(path)), (1, topology.path_bars(-path))):
        lengths = [d - b for b, d, _ in bars]
        summary += [sum(lengths), max(lengths, default=0.0), sum(l >= 0.25 for l in lengths)]
        for (b, d, _), length in zip(bars, lengths):
            level = b if side == 0 else -b                 # where the valley floor / peak top sits versus 3:40
            row = 0 if level < -0.25 else (1 if level <= 0.25 else 2)
            col = 0 if length < 0.15 else (1 if length < 0.4 else 2)
            grid[side * 9 + row * 3 + col] += length
    return summary, grid


def prepare(panel, state, intraday, outcome, sigma):
    cache = plots.folder(STUDY) / "prepared.npz"
    files = len(list(FIVE.glob("*.json.gz")))
    if cache.exists():
        saved = dict(np.load(cache))
        if int(saved.pop("files", -1)) == files:               # rebuilt when more days have been downloaded
            return saved
    column = {s: i for i, s in enumerate(panel.symbols)}
    row = {str(d.date()): t for t, d in enumerate(panel.dates)}
    rows = {k: [] for k in ["t", "i", "path", "volume"] + SUMMARY + GRID + PLAIN}
    for path in sorted(FIVE.glob("*.json.gz")):
        day = json.load(gzip.open(path))
        if day["close"] != "16:00" or day["date"] not in row:
            continue                                       # full days only
        t = row[day["date"]]
        open_ = pd.Timestamp(f"{day['date']} {day['open']}", tz="America/New_York").tz_convert("UTC")
        cutoff = open_ + pd.Timedelta(minutes=5 * (POINTS - 1))        # 15:40
        for symbol, bars in day["bars"].items():
            i = column.get(symbol)
            if i is None or state.group[t, i] == signals.NOT_USED or not np.isfinite(outcome[t, i]):
                continue
            use = [b for b in bars if pd.Timestamp(b["t"]) < cutoff]
            if len(use) != POINTS - 1:
                continue                                   # a missing 5-minute bar: skip the stock-day
            daily = sigma[t, i]
            prices = np.log([use[0]["o"]] + [b["c"] for b in use])
            p = (prices - prices[-1]) / daily
            volume = np.array([b["v"] for b in use], float)
            vwap = sum(b["v"] * b["vw"] for b in use) / volume.sum()
            steps = np.diff(p)
            summary, grid = barcode(p)
            values = {"signal": np.log(np.exp(prices[-1]) / vwap) / daily, "net": -p[0], "range": p.max() - p.min(),
                      "travel": np.abs(steps).sum(), "position": (0 - p.min()) / max(p.max() - p.min(), 1e-9),
                      "vol_5m": np.sqrt((steps ** 2).sum()),
                      "autocorr_5m": np.corrcoef(steps[1:], steps[:-1])[0, 1] if steps.std() > 0 else 0.0,
                      "last_hour": -p[-13], "late_volume_share": volume[-12:].sum() / volume.sum()}
            values["straightness"] = abs(values["net"]) / max(values["travel"], 1e-9)
            for k, v in zip(SUMMARY + GRID, summary + grid):
                rows[k].append(v)
            for k, v in values.items():
                rows[k].append(v)
            rows["t"].append(t); rows["i"].append(i); rows["path"].append(p); rows["volume"].append(volume)
    out = {k: np.array(v) for k, v in rows.items() if k != "signal_vs_peers"}
    # signal against the stock's TDA peers, the same day
    vs = np.full(len(out["t"]), np.nan)
    for t in np.unique(out["t"]):
        k = np.flatnonzero(out["t"] == t)
        vs[k] = signals.minus_group_mean(out["signal"][k], state.group[t, out["i"][k]])
    out["signal_vs_peers"] = vs
    np.savez_compressed(cache, files=files, **out)
    return out


def main():
    np.seterr(invalid="ignore", divide="ignore")
    panel = data.load_panel()
    state = signals.build_state(panel)
    intraday, outcomes, signal_tables, sigma = tables(panel, state)
    outcome = outcomes["3:50 pm to next open"]
    d = prepare(panel, state, intraday, outcome, sigma)
    t_all, i_all = d["t"], d["i"]
    target = outcome[t_all, i_all]
    peer_target = np.full(len(t_all), np.nan)
    for t in np.unique(t_all):
        k = np.flatnonzero(t_all == t)
        peer_target[k] = signals.minus_group_mean(target[k], state.group[t, i_all[k]])
    grouped = np.isfinite(peer_target) & np.isfinite(d["signal_vs_peers"])
    n_days = len(np.unique(t_all))
    print(f"{len(t_all):,} stock-days on {n_days} days; {grouped.sum():,} with a TDA peer group")
    check = np.log(intraday["price_20"] / intraday["vwap_20"])[t_all, i_all] / sigma[t_all, i_all]
    ok = np.isfinite(check)
    print("signal from 5-minute bars against study 10's signal: correlation",
          round(np.corrcoef(check[ok], d["signal"][ok])[0, 1], 4))
    out = plots.folder(STUDY)
    pd.set_option("display.width", 250)

    # 1. explained by plain
    plain_x = np.column_stack([np.ones(len(t_all))] + [d[k] for k in ["net", "range", "travel", "position", "vol_5m", "straightness"]]
                              + [np.abs(d["net"])])
    explained = []
    for k in SUMMARY:
        y = d[k]
        fit = plain_x @ np.linalg.lstsq(plain_x, y, rcond=None)[0]
        explained.append({"barcode_feature": k, "explained_by_plain": 1 - ((y - fit) ** 2).sum() / ((y - y.mean()) ** 2).sum()})
    explained = pd.DataFrame(explained)
    explained.to_csv(out / "explained_by_plain.csv", index=False)
    print(explained.round(3).to_string(index=False))
    identity = d["valley_total"] + d["peak_total"] - (d["travel"] - d["range"])
    print("valley total + peak total - (travel - range): max abs", float(np.abs(identity).max()))

    # 2. reversal by choppiness, within each day
    dates = panel.dates[t_all]
    later = dates >= data.SPLIT
    splits = {"Barcode: longest recovered swing (valley or peak)": np.maximum(d["valley_longest"], d["peak_longest"]),
              "Barcode: number of swings": d["valley_count"] + d["peak_count"],
              "Plain: 1 - straightness": 1 - d["straightness"]}
    buckets = []
    for name, values in splits.items():
        series = {b: [] for b in THIRDS}
        day_dates = []
        for t in np.unique(t_all):
            k = np.flatnonzero((t_all == t) & grouped)
            if len(k) < 60:
                continue
            third = thirds_within_day(values[k])
            day_dates.append(panel.dates[t])
            for b, label in enumerate(THIRDS):
                pick = third == b
                series[label].append(spread(np.where(pick, d["signal_vs_peers"][k], np.nan), peer_target[k]))
        day_dates = pd.DatetimeIndex(day_dates)
        for label, s in series.items():
            s = np.array(s)
            for period, mask in (("2017-2026", np.ones(len(s), bool)), ("before 2024", day_dates < data.SPLIT),
                                 ("2024 on", day_dates >= data.SPLIT)):
                use = mask & np.isfinite(s)
                mean, low, high = evaluate.mean_ci(s[use], block=5)
                buckets.append({"split": name, "third": label, "period": period, "days": int(use.sum()),
                                "reversal_bps": mean * 1e4, "low": low * 1e4, "high": high * 1e4})
    buckets = pd.DataFrame(buckets)
    buckets.to_csv(out / "reversal_by_choppiness.csv", index=False)
    print(buckets[buckets.period == "2017-2026"].round(2).to_string(index=False))

    # 3. learners
    X_plain = np.column_stack([d[k] for k in PLAIN])
    X_bar = np.column_stack([d[k] for k in SUMMARY + GRID])
    use = grouped
    tt, yy = t_all[use], peer_target[use]
    ranks = lambda X: np.vstack([centred_ranks(X[use][tt == t]) for t in np.unique(tt)])
    order = np.concatenate([np.flatnonzero(tt == t) for t in np.unique(tt)])
    tt, yy = tt[order], yy[order]
    Xp, Xb = ranks(X_plain), ranks(X_bar)
    y_rank = np.concatenate([centred_ranks(yy[tt == t][:, None])[:, 0] for t in np.unique(tt)])
    year = panel.dates.year.to_numpy()[tt]
    sets = {"Plain path measures": Xp, "Barcode only": Xb, "Plain + barcode": np.hstack([Xp, Xb])}
    learners = {"Ridge": lambda: Ridge(alpha=300.0),
                "Boosted trees": lambda: HistGradientBoostingRegressor(max_iter=150, learning_rate=0.05, max_leaf_nodes=8,
                                                                       min_samples_leaf=1000, l2_regularization=1.0,
                                                                       early_stopping=False, random_state=0)}
    test_days = np.unique(tt[year >= FIRST_TEST_YEAR])
    forecasts, ic = {}, {}
    rule = -Xp[:, PLAIN.index("signal_vs_peers")]
    forecasts["Rule: bet against the signal vs peers"] = rule
    for learner, make in learners.items():
        for name, X in sets.items():
            pred = np.full(len(yy), np.nan)
            for y_test in range(FIRST_TEST_YEAR, year.max() + 1):
                train, test = year < y_test, year == y_test
                pred[test] = make().fit(X[train], y_rank[train]).predict(X[test])
            forecasts[f"{learner} | {name}"] = pred
    for name, pred in forecasts.items():
        ic[name] = np.array([evaluate.rank_ic(pred[tt == t], yy[tt == t]) for t in test_days])
    later_t = panel.dates[test_days] >= data.SPLIT
    rows = []
    for period, mask in ((f"{FIRST_TEST_YEAR}-2026", np.ones(len(test_days), bool)), (f"{FIRST_TEST_YEAR}-2023", ~later_t),
                         ("2024 on", later_t)):
        for name, s in ic.items():
            mean, low, high = evaluate.mean_ci(s[mask], block=5)
            rows.append({"forecast": name, "period": period, "days": int(mask.sum()), "rank_correlation": mean, "low": low, "high": high})
        for learner in learners:
            gain = ic[f"{learner} | Plain + barcode"][mask] - ic[f"{learner} | Plain path measures"][mask]
            mean, low, high = evaluate.mean_ci(gain, block=5)
            rows.append({"forecast": f"{learner}: GAIN from adding the barcode", "period": period, "days": int(mask.sum()),
                         "rank_correlation": mean, "low": low, "high": high})
    scores = pd.DataFrame(rows)
    scores.to_csv(out / "forecast_scores.csv", index=False)
    print(scores.round(4).to_string(index=False))

    # the book: each forecast decides the trades of the TDA-peer book, on the sampled test days
    i_sorted = i_all[use][order]
    book_rows, book_daily = [], {}
    for name, pred in forecasts.items():
        r = []
        for t in test_days:
            k = np.flatnonzero(tt == t)
            bet = np.full(panel.returns.shape[1], np.nan)
            bet[i_sorted[k]] = -pred[k]
            stocks = np.flatnonzero(np.isfinite(bet) & np.isfinite(sigma[t]))
            stocks, columns = exposures_for("TDA peer groups", state, t, stocks)
            h, _ = portfolio.neutral_book(bet[stocks], columns, 1 / sigma[t, stocks] ** 2)
            r.append(np.nansum(h * outcome[t, stocks]))
        book_daily[name] = np.array(r)
    base = book_daily["Rule: bet against the signal vs peers"]
    for name, r in book_daily.items():
        s, low, high = evaluate.sharpe_ci(r, block=10)
        row = {"forecast": name, "days": len(r), "bps_per_day": r.mean() * 1e4, "sharpe": s, "low": low, "high": high}
        if r is not base:
            diff, dl, dh = evaluate.sharpe_difference_ci(r, base, block=10)
            row.update({"minus_rule": diff, "diff_low": dl, "diff_high": dh})
        book_rows.append(row)
    books = pd.DataFrame(book_rows)
    books.to_csv(out / "books.csv", index=False)
    print(books.round(2).to_string(index=False))
    figure(scores, buckets)


def figure(scores, buckets):
    fig, (left, right) = plt.subplots(1, 2, figsize=(12.5, 4.2), layout="constrained")
    part = buckets[buckets.period == "2017-2026"]
    names = list(dict.fromkeys(part.split))
    for offset, (name, color) in zip((-0.2, 0, 0.2), zip(names, (plots.BLUE, plots.AQUA, plots.GRAY))):
        p = part[part.split == name].set_index("third").loc[THIRDS]
        x = np.arange(3) + offset
        left.errorbar(x, p.reversal_bps, yerr=[p.reversal_bps - p.low, p.high - p.reversal_bps], fmt="o", color=color,
                      elinewidth=2, capsize=0, label=name)
    left.set_xticks(np.arange(3), [f"{t} third" for t in THIRDS])
    left.axhline(0, color=plots.INK_SOFT, lw=1)
    left.set_ylabel("Reversal, bps (lowest fifth minus highest fifth)")
    left.legend(loc="upper left", fontsize=8)
    left.set_title("Is the reversal stronger for choppy paths?", fontsize=10)
    whole = scores[scores.period == scores.period.iloc[0]]
    whole = whole[~whole.forecast.str.contains("GAIN")].iloc[::-1]
    y = np.arange(len(whole))
    right.errorbar(whole.rank_correlation, y, xerr=[whole.rank_correlation - whole.low, whole.high - whole.rank_correlation],
                   fmt="o", color=plots.BLUE, elinewidth=2, capsize=0)
    right.set_yticks(y, whole.forecast, fontsize=8)
    right.axvline(0, color=plots.INK_SOFT, lw=1)
    right.grid(axis="y", visible=False)
    right.set_xlabel("Rank correlation with the move to the next open (vs peers)")
    right.set_title(f"Forecasts scored on unseen years ({whole.period.iloc[0]})", fontsize=10)
    fig.suptitle("The 1D-sweep barcode of each stock's 5-minute path, open to 3:40 pm. 95% intervals",
                 x=0.01, ha="left", fontweight="bold", fontsize=10)
    plots.save(fig, STUDY, "1_intraday_barcode.png")


if __name__ == "__main__":
    main()
