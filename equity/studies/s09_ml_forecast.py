"""F1. Can machine learning (no topology) turn plain signals into a better forecast and a better book?

39 plain features per stock per day, all known at the close:

  recent moves   today's surprise, versus peers, versus sector, overnight and daytime parts,
                 2/3/5/10/20-day moves, close versus the day's average price, close within the day's range
  trend          60/120/250-day moves, 250-day move skipping the last 20
  risk           volatility, SPY beta, recent 5- and 20-day volatility, today's range versus usual
  volume         today's volume versus usual, 5-day versus 60-day volume, dollar volume
  peers          what the peers and the sector did today, peers' 5-day move, how tight the peers are
  path           position in the 20- and 60-day range, range, straightness, day-to-day autocorrelation
  market         yesterday's VIX, today's spread between stocks, today's SPY move (same for every stock)

Three learners, settings fixed in advance (nothing tuned):
  ridge            a straight-line fit: forecast = weighted sum of the features
  boosted trees    many small decision trees; can find "if A and B then C" patterns
  neural network   two hidden layers (32 and 16 units), average of 5 random starts

Each is trained on all earlier years and scored on the next year, 2019 onward.
Two targets: the next day's move (close to close) and the next 5 days' move
(next open to the close 5 days later), both with SPY removed.

Two feature sets, because of a trap in this data. The 200 stocks are the
largest ones AS OF 2026. A stock that was small in 2018 is only on the list
because it grew, so "small stocks go up" is true here by construction and a
learner will happily learn it. Features that say what KIND of stock it is
(size, beta, volatility, tightness of peers, long-run trend) can carry that
bias. Features that say what JUST HAPPENED to the stock cannot.

  all features           all 39
  recent behaviour only  the 31 left after removing the 8 "kind of stock" features

A third feature set tests a second trap. The gain could come from noise in the
closing price itself: a close that prints a little high makes today look
strong and tomorrow look weak, with nothing to trade. So every feature that
uses today's close is rebuilt to end at the day's average traded price
instead (and the four that cannot be rebuilt are dropped). The closing print
cannot contaminate these.

  recent, today's close not used   27 features

The same split is applied to the simple rule: today's move = the move up to
the day's average price ("early part") + the move from there to the close
("late part").

Scoring:
  1. rank correlation between forecast and outcome, against the unfitted rule
     "bet against the move"
  2. the forecast placed in the SAME peer-hedged book as s04, against s04's rule,
     before costs, with the cost per dollar traded at which profit reaches zero.
     The 1-day forecast is traded two ways: at the same close the features are
     measured on (not possible in practice without intraday data), and at the
     next open, held to that day's close.
  3. universe-bias check: the "kind of stock" features used alone as a signal

    conda run -n tda python equity/studies/s09_ml_forecast.py
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor

from s04_peer_reversal_book import exposures_for
from s08_path_shape import build_features as path_features, centred_ranks
from tdaeq import data, evaluate, plots, portfolio, signals

STUDY = "s09_ml_forecast"
FIRST_TEST_YEAR = 2019
TARGETS = ["1 day", "5 days"]
RULE = "Simple rule (nothing fitted)"
LEARNERS = {
    "Ridge": [lambda: Ridge(alpha=1000.0)],
    "Boosted trees": [lambda: HistGradientBoostingRegressor(
        max_iter=200, learning_rate=0.05, max_leaf_nodes=8, min_samples_leaf=2000,
        l2_regularization=1.0, early_stopping=False, random_state=0)],
    "Neural network": [lambda seed=seed: MLPRegressor(
        hidden_layer_sizes=(32, 16), alpha=1e-3, batch_size=4096, learning_rate_init=1e-3,
        max_iter=12, early_stopping=True, n_iter_no_change=3, random_state=seed) for seed in range(5)],
}
DAY_LEVEL = ["vix_yesterday", "spread_today", "spy_move_today"]
KIND_OF_STOCK = ["volatility", "beta", "dollar_volume", "peer_tightness", "nearest_peer_distance",
                 "z120", "z250", "z250_skip20"]
USES_TODAYS_CLOSE = ["close_vs_avg_price", "close_in_day_range", "position_20", "position_60"]
SETS = ["All features", "Recent behaviour only", "Recent, today's close not used"]
RULE_EARLY, RULE_LATE = "Rule on the early part of today's move", "Rule on the late part of today's move"
LEARNED = [f"{learner} | {features}" for features in SETS for learner in LEARNERS]
SOURCES = [RULE, RULE_EARLY, RULE_LATE] + LEARNED
COLORS = dict(zip([RULE, *LEARNERS], [plots.GRAY, plots.BLUE, plots.ORANGE, plots.AQUA]))
WAYS = {"close to close": "1 day", "next open to close": "1 day", "5-day": "5 days"}   # way of trading -> forecast used


def rolling_mean(table, n):
    """Mean of the last n rows including today; NaN unless all n values are present."""
    ok = np.isfinite(table)
    width = table.shape[1]
    total = np.vstack([np.zeros((1, width)), np.cumsum(np.where(ok, table, 0.0), axis=0)])
    seen = np.vstack([np.zeros((1, width)), np.cumsum(ok, axis=0)])
    out = np.full(table.shape, np.nan)
    out[n - 1:] = np.where(seen[n:] - seen[:-n] == n, (total[n:] - total[:-n]) / n, np.nan)
    return out


def lag(table):
    return np.vstack([np.full((1, table.shape[1]), np.nan), table[:-1]])


def feature_tables(panel, state):
    """Every feature as a days x stocks table. Row t uses only data up to the close of day t."""
    z, sigma, beta = state.surprise, state.sigma, state.beta
    days, n = z.shape
    used = state.group != signals.NOT_USED
    bars = data.load_bar_fields(panel)
    path = path_features(state)
    close, open_ = panel.close_adj, panel.open_adj
    spy_overnight = panel.market_open / np.r_[np.nan, panel.market_close[:-1]] - 1
    spy_daytime = panel.market_close / panel.market_open - 1
    move = lambda k: rolling_mean(z, k) * np.sqrt(k)            # k-day move, a random walk keeps size 1
    sector = np.where(used, state.sector[None, :], signals.NO_GROUP)
    versus = lambda table, labels: np.vstack([signals.minus_group_mean(table[t], labels[t]) for t in range(days)])
    z5 = move(5)
    vs_peers, vs_sector = versus(z, state.group), versus(z, sector)
    day_range = np.log(np.maximum(bars["h"] - bars["l"], 1e-6) / close)
    volume = np.where(bars["v"] > 0, bars["v"], np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        f = {
            "z1": z, "vs_peers": vs_peers, "vs_sector": vs_sector,
            "overnight": (open_ / lag(close) - 1 - beta * spy_overnight[:, None]) / sigma,
            "daytime": (close / open_ - 1 - beta * spy_daytime[:, None]) / sigma,
            "z2": move(2), "z3": move(3), "z5": z5, "z10": move(10), "z20": move(20),
            "close_vs_avg_price": (close / bars["vw"] - 1) / sigma,
            "close_in_day_range": (close - bars["l"]) / np.where(bars["h"] > bars["l"], bars["h"] - bars["l"], np.nan),
            "z60": move(60), "z120": move(120), "z250": move(250),
            "z250_skip20": (move(250) * np.sqrt(250) - move(20) * np.sqrt(20)) / np.sqrt(230),
            "volatility": np.log(sigma), "beta": beta,
            "recent_vol_5": np.sqrt(rolling_mean(z * z, 5)), "recent_vol_20": np.sqrt(rolling_mean(z * z, 20)),
            "range_vs_usual": day_range - lag(rolling_mean(day_range, 20)),
            "volume_vs_usual": np.log(volume) - np.log(lag(rolling_mean(volume, 20))),
            "volume_5_vs_60": np.log(rolling_mean(volume, 5) / rolling_mean(volume, 60)),
            "dollar_volume": np.log(rolling_mean(volume * bars["vw"], 20)),
            "peers_today": z - vs_peers, "sector_today": z - vs_sector, "peers_5d": z5 - versus(z5, state.group),
            "peer_tightness": state.corr_top5, "nearest_peer_distance": state.join,
            "position_20": path["position_20"], "position_60": path["position_60"],
            "range_60": path["range_60"], "straightness_60": np.abs(path["net_60"]) / path["travel_60"],
            "range_20": path["range_20"], "straightness_20": np.abs(path["net_20"]) / path["travel_20"],
            "autocorr_60": path["autocorr_60"],
        }
    # The same features with today's move ending at the day's average price instead of the close.
    spy_avg = data.load_bar_fields(panel, fields=("vw",), symbols=["SPY"])["vw"][:, 0]
    spy_prev = np.r_[np.nan, panel.market_close[:-1]]
    early = (np.log(bars["vw"] / lag(close)) - beta * np.log(spy_avg / spy_prev)[:, None]) / sigma
    late = z - early
    alt = {"z1": early, "vs_peers": versus(early, state.group), "vs_sector": versus(early, sector),
           "daytime": (bars["vw"] / open_ - 1 - beta * (spy_avg / panel.market_open - 1)[:, None]) / sigma,
           **{f"z{k}": (f[f"z{k}"] * np.sqrt(k) - late) / np.sqrt(k) for k in (2, 3, 5, 10, 20, 60)}}
    alt["peers_today"], alt["sector_today"] = early - alt["vs_peers"], early - alt["vs_sector"]
    alt["peers_5d"] = alt["z5"] - versus(alt["z5"], state.group)
    f.update({f"{name}@avg": table for name, table in alt.items()})
    parts = {RULE_EARLY: np.log(bars["vw"] / lag(close)), RULE_LATE: np.log(close / bars["vw"])}
    spy_vol = pd.Series(panel.market).rolling(20).std().shift(1).to_numpy()
    day = {"vix_yesterday": np.log(np.r_[np.nan, panel.vix[:-1]]) - 3,
           "spread_today": np.nanstd(np.where(used, z, np.nan), axis=1) - 1,
           "spy_move_today": np.clip(panel.market / spy_vol, -5, 5)}
    return f, day, parts


def columns_for(features, names):
    """Positions in `names` of the columns one feature set uses."""
    base = [n for n in names if "@" not in n]
    if features == "All features":
        chosen = base
    elif features == "Recent behaviour only":
        chosen = [n for n in base if n not in KIND_OF_STOCK]
    else:
        chosen = [f"{n}@avg" if f"{n}@avg" in names else n
                  for n in base if n not in KIND_OF_STOCK + USES_TODAYS_CLOSE]
    return [names.index(n) for n in chosen]


def targets(panel, state):
    """Outcome tables: row t is what happens AFTER the close of day t, SPY removed."""
    days, n = panel.returns.shape
    blank = lambda k: np.full((k, n), np.nan)
    close, open_, spy_c, spy_o = panel.close_adj, panel.open_adj, panel.market_close, panel.market_open
    one = np.vstack([close[1:] / close[:-1] - 1 - state.beta[:-1] * (spy_c[1:] / spy_c[:-1] - 1)[:, None], blank(1)])
    five = np.vstack([close[5:] / open_[1:-4] - 1 - state.beta[:-5] * (spy_c[5:] / spy_o[1:-4] - 1)[:, None], blank(5)])
    return {"1 day": one, "5 days": five}


def stack(panel, state, features, day_level, outcome):
    """One row per stock-day. Features and targets become ranks across the day's stocks (-0.5..0.5)."""
    names = list(features)
    X, y, day, stock = [], {k: [] for k in TARGETS}, [], []
    for t in range(len(panel.dates)):
        ok = (state.group[t] != signals.NOT_USED) & np.isfinite(features["z1"][t]) & np.isfinite(features["position_60"][t])
        if ok.sum() < 50:
            continue
        block = centred_ranks(np.column_stack([features[c][t, ok] for c in names]))
        extra = np.nan_to_num(np.array([day_level[c][t] for c in DAY_LEVEL]))
        X.append(np.hstack([block, np.tile(extra, (ok.sum(), 1))]))
        for k in TARGETS:
            value = outcome[k][t, ok] / state.sigma[t, ok]              # in units of the stock's own volatility
            ranks = centred_ranks(value[:, None])[:, 0]
            y[k].append(np.where(np.isfinite(value), ranks, np.nan))
        day.append(np.full(ok.sum(), t))
        stock.append(np.flatnonzero(ok))
    return (np.vstack(X), {k: np.concatenate(v) for k, v in y.items()}, np.concatenate(day),
            np.concatenate(stock), names + DAY_LEVEL)


def walk_forward(X, y, day, year, makers):
    """Train on every row dated at least 6 days before the test year starts; forecast that year."""
    prediction = np.full(len(y), np.nan)
    last = None
    for test_year in range(FIRST_TEST_YEAR, year.max() + 1):
        test = year == test_year
        train = (day < day[test].min() - 6) & np.isfinite(y)
        fits = [make().fit(X[train], y[train]) for make in makers]
        prediction[test] = np.mean([m.predict(X[test]) for m in fits], axis=0)
        last = fits[0]
    return prediction, last


def forecasts(panel, X, y, day, stock, names):
    """Forecast tables (days x stocks) for every learner and target. Cached: fitting takes several minutes."""
    cache = plots.folder(STUDY) / "forecasts.npz"
    coefs = plots.folder(STUDY) / "ridge_weights.csv"
    if cache.exists():
        return dict(np.load(cache))
    year = panel.dates.year.to_numpy()[day]
    out, weights = {}, {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        for features in SETS:
            keep = columns_for(features, names)
            for target in TARGETS:
                for learner, makers in LEARNERS.items():
                    prediction, last = walk_forward(X[:, keep], y[target], day, year, makers)
                    table = np.full(panel.returns.shape, np.nan)
                    table[day, stock] = prediction
                    out[f"{learner} | {features}|{target}"] = table
                    if learner == "Ridge":
                        weights[f"{features}, {target}"] = pd.Series(last.coef_, index=[names[i] for i in keep])
    pd.DataFrame(weights).reindex(names).to_csv(coefs)
    np.savez_compressed(cache, **out)
    return out


def score_forecasts(panel, forecast, features, outcome):
    days = len(panel.dates)
    test = np.flatnonzero(panel.dates.year >= FIRST_TEST_YEAR)
    later = panel.dates[test] >= data.SPLIT
    rules = {"1 day": {RULE: -features["z1"], RULE_EARLY: -features["z1@avg"],
                       RULE_LATE: features["z1@avg"] - features["z1"]},
             "5 days": {RULE: -features["z5"]}}
    rows = []
    for target in TARGETS:
        seen = np.isfinite(forecast[f"{LEARNED[0]}|{target}"])
        series = {name: np.array([evaluate.rank_ic(np.where(seen[t], signal[t], np.nan), outcome[target][t]) for t in test])
                  for name, signal in rules[target].items()}
        for source in LEARNED:
            series[source] = np.array([evaluate.rank_ic(forecast[f"{source}|{target}"][t], outcome[target][t]) for t in test])
        for label, mask in ((f"{FIRST_TEST_YEAR}-2023", ~later), ("2024 on", later)):
            for source, values in series.items():
                use = mask & np.isfinite(values)
                mean, low, high = evaluate.mean_ci(values[use], block=20)
                row = {"target": target, "source": source, "period": label, "days": int(use.sum()),
                       "rank_correlation": mean, "low": low, "high": high}
                if source != RULE:
                    both = use & np.isfinite(series[RULE])
                    gain, g_low, g_high = evaluate.mean_ci(values[both] - series[RULE][both], block=20)
                    row.update({"gain_over_rule": gain, "gain_low": g_low, "gain_high": g_high})
                rows.append(row)
    return pd.DataFrame(rows)


def universe_bias(panel, features, outcome):
    """Each "kind of stock" feature used alone, nothing fitted: does simply holding one
    kind of stock pay? Sign chosen so that positive = smaller / lower beta / etc. did better."""
    test = np.flatnonzero(panel.dates.year >= 2017)
    rows = []
    for name in KIND_OF_STOCK:
        ic = np.array([evaluate.rank_ic(features[name][t], outcome["5 days"][t]) for t in test])
        ic = ic[np.isfinite(ic)]
        mean, low, high = evaluate.mean_ci(ic, block=20)
        rows.append({"feature": name, "rank_correlation_with_next_5_days": mean, "low": low, "high": high})
    return pd.DataFrame(rows)


def run_books(panel, state, forecast, parts):
    """Each forecast placed in the s04 book: hedged against TDA peer groups, or against the market only."""
    days, n = panel.returns.shape
    total_sigma = np.maximum(pd.DataFrame(panel.returns).rolling(252).std(ddof=1).shift(1).to_numpy(), 1e-4)
    close_close = np.vstack([panel.close_adj[1:] / panel.close_adj[:-1] - 1, np.full((1, n), np.nan)])
    open_close = np.vstack([panel.close_adj[1:] / panel.open_adj[1:] - 1, np.full((1, n), np.nan)])
    index = np.flatnonzero(panel.dates.year >= FIRST_TEST_YEAR)[:-1]
    bet_against = {(RULE, "1 day"): panel.returns,
                   (RULE, "5 days"): signals.rolling_sum(np.nan_to_num(panel.returns), 5),
                   (RULE_EARLY, "1 day"): parts[RULE_EARLY], (RULE_LATE, "1 day"): parts[RULE_LATE]}
    for source in LEARNED:
        for target in TARGETS:                                     # forecast up = buy, so bet against its negative
            bet_against[source, target] = -forecast[f"{source}|{target}"] * total_sigma
    returns, turnover = {}, {}
    for hedge in ("TDA peer groups", "Market only"):
        for (source, target), signal in bet_against.items():
            held = np.zeros((days, n))
            for t in range(index[0] - 1, index[-1] + 1):
                used = np.flatnonzero((state.group[t] != signals.NOT_USED) & np.isfinite(signal[t])
                                      & np.isfinite(total_sigma[t]))
                if len(used) < 50:
                    continue
                stocks, columns = exposures_for(hedge, state, t, used)
                held[t, stocks], _ = portfolio.neutral_book(signal[t, stocks], columns, 1 / total_sigma[t, stocks] ** 2)
            if target == "1 day":
                key = (hedge, "close to close", source)             # trade at the close, hold to the next close
                returns[key] = np.nansum(held[index] * close_close[index], axis=1)
                turnover[key] = np.abs(held[index] - held[index - 1]).sum(axis=1)
                key = (hedge, "next open to close", source)         # decide overnight, in at the open, out at the close
                returns[key] = np.nansum(held[index] * open_close[index], axis=1)
                turnover[key] = np.full(len(index), 2.0)
            else:                                                  # enter at the next open, hold 5 days, 1/5 of capital a day
                key = (hedge, "5-day", source)
                daily = np.nansum(held[index] * open_close[index], axis=1)
                for k in range(1, 5):
                    daily = daily + np.nansum(held[index - k] * close_close[index], axis=1)
                returns[key] = daily / 5
                turnover[key] = np.full(len(index), 2.0 / 5)
    return panel.dates[index + 1], returns, turnover


def score_books(dates, returns, turnover):
    later = dates >= data.SPLIT
    rows = []
    for (hedge, way, source), r in returns.items():
        trade = turnover[hedge, way, source]
        for label, mask in ((f"{FIRST_TEST_YEAR}-2023", ~later), ("2024 on", later), ("all", np.ones(len(r), bool))):
            sharpe, low, high = evaluate.sharpe_ci(r[mask])
            row = {"hedge": hedge, "way": way, "source": source, "period": label, **evaluate.performance(r[mask]),
                   "sharpe_low": low, "sharpe_high": high, "turnover_per_day": trade[mask].mean(),
                   "breakeven_cost_bps": r[mask].mean() / trade[mask].mean() * 1e4,
                   "sharpe_after_1bp_cost": evaluate.sharpe(r[mask] - trade[mask] * 1e-4)}
            if source != RULE:
                diff, d_low, d_high = evaluate.sharpe_difference_ci(r[mask], returns[hedge, way, RULE][mask])
                row.update({"sharpe_minus_rule": diff, "diff_low": d_low, "diff_high": d_high})
            rows.append(row)
    return pd.DataFrame(rows)


def figure_sharpe(books):
    """Sharpe of the peer-hedged book, 2019 onward, for every way of trading and feature set."""
    part = books[(books.hedge == "TDA peer groups") & (books.period == "all")]
    labels = ["Rule:\nwhole move", "Rule:\nearly part", "Rule:\nlate part", "Ridge", "Boosted\ntrees", "Neural\nnetwork"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), sharey=True, layout="constrained")
    for ax, way in zip(axes, WAYS):
        rows = part[part.way == way].set_index("source")
        for x, rule in enumerate([RULE, RULE_EARLY, RULE_LATE]):
            if rule in rows.index:
                one = rows.loc[rule]
                ax.errorbar([x], [one.sharpe], yerr=[[one.sharpe - one.sharpe_low], [one.sharpe_high - one.sharpe]],
                            fmt="o", color=plots.GRAY, elinewidth=2, capsize=0)
        for offset, (features, color) in zip((-0.2, 0, 0.2), zip(SETS, (plots.BLUE, plots.ORANGE, plots.AQUA))):
            use = rows.loc[[f"{learner} | {features}" for learner in LEARNERS]]
            ax.errorbar(np.arange(3, 6) + offset, use.sharpe, yerr=[use.sharpe - use.sharpe_low, use.sharpe_high - use.sharpe],
                        fmt="o", color=color, elinewidth=2, capsize=0, label=features)
        ax.axhline(0, color=plots.INK_SOFT, lw=1)
        ax.set_xticks(np.arange(6), labels, fontsize=8)
        ax.set_xlim(-0.5, 5.5)
        ax.grid(axis="x", visible=False)
        ax.set_title({"close to close": "Traded at the close, held 1 day",
                      "next open to close": "In at the next open, out at the close",
                      "5-day": "In at the next open, held 5 days"}[way])
    axes[0].set_ylabel("Sharpe before costs, 2019 onward")
    axes[2].legend(loc="upper right", title="Features given to the learner")
    fig.suptitle("The same peer-hedged book, with a simple rule (grey) or a learner deciding what to buy and sell. 95% intervals",
                 x=0.01, ha="left", fontweight="bold", fontsize=10)
    plots.save(fig, STUDY, "1_book_sharpe.png")


def figure_books(dates, returns):
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2), sharey=True, layout="constrained")
    for ax, features in zip(axes, SETS):
        for name in [RULE, *LEARNERS]:
            source = name if name == RULE else f"{name} | {features}"
            r = returns["TDA peer groups", "close to close", source]
            ax.plot(dates, np.cumsum(r) * 100, color=COLORS[name], lw=1.6, label=name)
        ax.axvline(data.SPLIT, color=plots.INK_SOFT, lw=1, ls="--")
        ax.axhline(0, color=plots.AXIS, lw=1)
        ax.set_title(f"Learner given: {features.lower()}")
    axes[0].set_ylabel("Cumulative return before costs, %")
    axes[0].legend(loc="upper left")
    fig.suptitle("Peer-hedged book traded at the close and held 1 day",
                 x=0.01, ha="left", fontweight="bold", fontsize=10)
    plots.save(fig, STUDY, "2_books.png")


def main():
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    panel = data.load_panel()
    state = signals.build_state(panel)
    features, day_level, parts = feature_tables(panel, state)
    outcome = targets(panel, state)
    X, y, day, stock, names = stack(panel, state, features, day_level, outcome)
    print(f"{len(day):,} stock-days; features per set: " + ", ".join(f"{f} {len(columns_for(f, names))}" for f in SETS))
    forecast = forecasts(panel, X, y, day, stock, names)
    out = plots.folder(STUDY)
    pd.set_option("display.width", 250)

    scores = score_forecasts(panel, forecast, features, outcome)
    scores.to_csv(out / "forecast_scores.csv", index=False)
    print(scores.round(4).to_string(index=False))
    bias = universe_bias(panel, features, outcome)
    bias.to_csv(out / "universe_bias.csv", index=False)
    print(bias.round(4).to_string(index=False))

    dates, returns, turnover = run_books(panel, state, forecast, parts)
    old = pd.read_csv(plots.RESULTS / "s04_peer_reversal_book/daily_returns.csv", index_col="date", parse_dates=True)
    same = np.allclose(old.loc[dates, "TDA peer groups | close to close"], returns["TDA peer groups", "close to close", RULE])
    print(f"simple-rule book equals the s04 book on these dates: {same}")
    books = score_books(dates, returns, turnover)
    books.to_csv(out / "books.csv", index=False)
    pd.DataFrame({" | ".join(k): r for k, r in returns.items()}, index=dates).to_csv(out / "daily_returns.csv")
    show = ["way", "source", "period", "mean_bps", "vol_pct", "sharpe", "sharpe_low", "sharpe_high",
            "turnover_per_day", "breakeven_cost_bps", "sharpe_after_1bp_cost", "sharpe_minus_rule", "diff_low", "diff_high"]
    print(books[books.hedge == "TDA peer groups"][show].round(2).to_string(index=False))

    weights = pd.read_csv(out / "ridge_weights.csv", index_col=0)
    for column in weights:
        top = weights[column].reindex(weights[column].abs().sort_values(ascending=False).index).head(8)
        print(f"largest ridge weights ({column}): " + ", ".join(f"{k} {v:+.4f}" for k, v in top.items()))
    figure_sharpe(books)
    figure_books(dates, returns)


if __name__ == "__main__":
    main()
