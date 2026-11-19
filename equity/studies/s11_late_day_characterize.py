"""G2. Characterize the late-day reversal: does the TDA hedge matter, can it be
tuned honestly, where does the money come from, and how big could it be?

The strategy (study 10's main version), every trading day:
  3:40 pm   signal = log(price now / average traded price since the open)
  3:50 pm   bet against the signal, cash neutral and SPY-beta neutral inside
            every TDA peer group, half the capital long and half short;
            buy or sell at the 3:50 price
  next day  close everything at the official open

Four parts:

  1. Hedge.     The same signal, neutral inside TDA peer groups / plain fine
                groups (average linkage cut into 100) / sectors / the market only.
  2. Tuning.    A small grid (when the signal is read x hedge x how it is traded),
                chosen on dates before 2024 only and then scored once on 2024 on.
  3. Where the money comes from.  Profit per dollar held, split by sector,
                stock size, signal size, yesterday's VIX, weekday and year.
  4. Capacity.  For a book of a given size, each position as a share of the
                stock's trading in the last 10 minutes and in the closing auction.

All before costs (study 12 adds measured costs).

    conda run -n tda python equity/studies/s11_late_day_characterize.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gzip
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from s04_peer_reversal_book import exposures_for
from tdaeq import data, evaluate, plots, portfolio, signals

STUDY = "s11_late_day_characterize"
HEDGES = ["TDA peer groups", "Plain fine groups", "Sectors", "Market only", "Market only, same stocks"]
COLORS = dict(zip(HEDGES, [plots.BLUE, plots.ORANGE, plots.AQUA, plots.GRAY, plots.YELLOW]))
WAYS = {"3:50 pm to next open": "enter at the 3:50 pm price, exit at the next open",
        "Close to next open": "enter in the closing auction, exit at the next open"}
MAIN = ("TDA peer groups", 20, "3:50 pm to next open")


def tables(panel, state):
    np.seterr(invalid="ignore", divide="ignore")
    intraday = data.load_intraday(panel)
    n = panel.returns.shape[1]
    to_next_open = np.vstack([panel.open_adj[1:] / panel.close_adj[:-1] - 1, np.full((1, n), np.nan)])
    outcome = {"3:50 pm to next open": (panel.close_raw / intraday["price_10"]) * (1 + to_next_open) - 1,
               "Close to next open": to_next_open}
    signal = {m: np.log(intraday[f"price_{m}"] / intraday[f"vwap_{m}"]) for m in (30, 20, 10)}
    sigma = np.maximum(pd.DataFrame(panel.returns).rolling(252).std(ddof=1).shift(1).to_numpy(), 1e-4)
    return intraday, outcome, signal, sigma


def holdings(panel, state, signal, sigma, hedge, days):
    """Day x stock holdings of the book (absolute positions add to 1 each day)."""
    held = np.zeros(panel.returns.shape)
    for t in days:
        used = np.flatnonzero((state.group[t] != signals.NOT_USED) & np.isfinite(signal[t]) & np.isfinite(sigma[t]))
        if len(used) < 50:
            continue
        stocks, columns = exposures_for(hedge, state, t, used)
        held[t, stocks], _ = portfolio.neutral_book(signal[t, stocks], columns, 1 / sigma[t, stocks] ** 2)
    return held


def daily_return(held, outcome, days):
    return np.nansum(held[days] * outcome[days], axis=1)


def summarize(r, dates, label):
    rows = []
    for period, mask in (("2017-2026", np.ones(len(r), bool)), ("before 2024", dates < data.SPLIT),
                         ("2024 on", dates >= data.SPLIT)):
        sharpe, low, high = evaluate.sharpe_ci(r[mask])
        rows.append({**label, "period": period, **evaluate.performance(r[mask]), "sharpe_low": low, "sharpe_high": high,
                     "breakeven_cost_bps": r[mask].mean() / 2 * 1e4})          # in and out once a day: 2x traded
    return rows


def attribution(panel, state, held, outcome, days, extra):
    """Profit per dollar held, split several ways. Every split is known at 3:50 pm."""
    pnl = held[days] * np.nan_to_num(outcome[days])
    gross = np.abs(held[days])
    total = pnl.sum()
    rows = []

    def add(split, bucket, mask):
        p, g = (pnl * mask).sum(), (gross * mask).sum()
        series = (pnl * mask).sum(axis=1)
        rows.append({"split": split, "bucket": bucket, "share_of_capital": g / gross.sum(),
                     "bps_per_dollar_per_day": p / g * 1e4 if g > 0 else np.nan, "share_of_profit": p / total,
                     "sharpe_of_its_profit": evaluate.sharpe(series) if series.std() > 0 else np.nan})

    sector = np.broadcast_to(panel.sectors, pnl.shape)
    for name in sorted(set(panel.sectors)):
        add("Sector", name, sector == name)
    for split, table in (("Stock size (20-day dollar volume)", extra["dollar_volume"][days]),
                         ("Signal size", np.abs(extra["signal"][days]))):
        ranks = pd.DataFrame(np.where(held[days] != 0, table, np.nan)).rank(axis=1, pct=True).to_numpy()
        for b, name in enumerate(["Lowest third", "Middle third", "Highest third"]):
            add(split, name, (ranks > b / 3) & (ranks <= (b + 1) / 3))
    vix = np.r_[np.nan, panel.vix[:-1]][days]
    cuts = np.nanquantile(vix[panel.dates[days] < data.SPLIT], [1 / 3, 2 / 3])
    for b, name in enumerate(["Low", "Middle", "High"]):
        in_bucket = np.isfinite(vix) & (np.searchsorted(cuts, vix) == b)
        add("Yesterday's VIX", name, np.broadcast_to(in_bucket[:, None], pnl.shape))
    weekday = panel.dates[days].dayofweek.to_numpy()
    for d, name in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]):
        add("Day of the week (held overnight from)", name, np.broadcast_to((weekday == d)[:, None], pnl.shape))
    year = panel.dates[days].year.to_numpy()
    for y in sorted(set(year)):
        add("Year", str(y), np.broadcast_to((year == y)[:, None], pnl.shape))
    return pd.DataFrame(rows)


def capacity(panel, held, days, intraday_folder):
    """Each position's dollars as a share of the stock's dollars traded 3:50-4:00 pm and in the closing auction."""
    late, auction = np.full(panel.returns.shape, np.nan), np.full(panel.returns.shape, np.nan)
    column = {s: i for i, s in enumerate(panel.symbols)}
    row = {str(d.date()): t for t, d in enumerate(panel.dates)}
    for path in sorted((intraday_folder / "raw" / "last_half_hour").glob("*.json.gz"))[::5]:
        day = json.load(gzip.open(path))
        close = pd.Timestamp(f"{day['date']} {day['close']}", tz="America/New_York").tz_convert("UTC")
        for symbol, bars in day["bars"].items():
            if symbol not in column or day["date"] not in row:
                continue
            for bar in bars:
                minutes = round((pd.Timestamp(bar["t"]) - close).total_seconds() / 60)
                if minutes == -10:
                    late[row[day["date"]], column[symbol]] = bar["v"] * bar["vw"]
                elif minutes == 0:          # the bar holding the closing auction (it also has a few after-hours trades)
                    auction[row[day["date"]], column[symbol]] = bar["v"] * bar["vw"]
    rows = []
    position = np.abs(held[days])
    for book in (1e6, 1e7, 1e8, 1e9):
        for name, traded in (("last 10 minutes of trading", late), ("closing-auction bar", auction)):
            share = np.where((position > 0) & np.isfinite(traded[days]), position * book / traded[days], np.nan)
            values = share[np.isfinite(share)]
            rows.append({"book_size_usd": book, "compared_with": name, "median_share_pct": np.median(values) * 100,
                         "p95_share_pct": np.quantile(values, 0.95) * 100, "max_share_pct": values.max() * 100})
    return pd.DataFrame(rows)


def figure_hedges(table, daily, dates):
    fig, (left, right) = plt.subplots(1, 2, figsize=(12.5, 4.3), layout="constrained",
                                      gridspec_kw={"width_ratios": [1.3, 1]})
    for hedge in HEDGES:
        r = daily[hedge]
        scaled = r * (0.05 / np.sqrt(252)) / r.std(ddof=1)
        left.plot(dates, np.cumsum(scaled) * 100, color=COLORS[hedge], lw=1.6, label=hedge)
    left.axvline(data.SPLIT, color=plots.INK_SOFT, lw=1, ls="--")
    left.axhline(0, color=plots.AXIS, lw=1)
    left.set_ylabel("Cumulative return, % (each scaled to 5% volatility)")
    left.legend(loc="upper left")
    left.set_title("Same signal, different hedge")
    part = table[(table.period == "2017-2026")].set_index("hedge").loc[HEDGES[::-1]]
    y = np.arange(len(HEDGES))
    right.errorbar(part.sharpe, y, xerr=[part.sharpe - part.sharpe_low, part.sharpe_high - part.sharpe],
                   fmt="o", color=plots.BLUE, elinewidth=2, capsize=0)
    right.set_yticks(y, HEDGES[::-1])
    right.axvline(0, color=plots.INK_SOFT, lw=1)
    right.grid(axis="y", visible=False)
    right.set_xlabel("Sharpe before costs, 2017-2026 (95% interval)")
    right.set_title("What the hedge is worth")
    fig.suptitle("Late-day reversal, signal at 3:40 pm, entered at 3:50 pm, sold at the next open",
                 x=0.01, ha="left", fontweight="bold", fontsize=10)
    plots.save(fig, STUDY, "1_hedges.png")


def figure_attribution(attr):
    splits = ["Stock size (20-day dollar volume)", "Signal size", "Yesterday's VIX", "Sector"]
    fig, axes = plt.subplots(1, len(splits), figsize=(15, 4.4), layout="constrained",
                             gridspec_kw={"width_ratios": [1, 1, 1, 2.2]})
    for ax, split in zip(axes, splits):
        part = attr[attr.split == split]
        ax.barh(np.arange(len(part))[::-1], part.bps_per_dollar_per_day, color=plots.BLUE, height=0.6)
        ax.set_yticks(np.arange(len(part))[::-1], part.bucket)
        ax.axvline(0, color=plots.INK_SOFT, lw=1)
        ax.grid(axis="y", visible=False)
        ax.set_title(split, fontsize=10)
        ax.set_xlabel("bps per dollar held per day")
    fig.suptitle("Where the profit comes from (main version, before costs, 2017-2026)",
                 x=0.01, ha="left", fontweight="bold", fontsize=10)
    plots.save(fig, STUDY, "2_where_the_money_comes_from.png")


def figure_profit(panel, dates, r):
    """Profit of the main version over the years, and a close-up of October - November 2026."""
    r = pd.Series(r, index=dates)
    spy = pd.Series(panel.market_close, index=panel.dates)
    fig, axes = plt.subplots(2, 2, figsize=(14, 6.4), layout="constrained", sharex="col",
                             gridspec_kw={"height_ratios": [2, 1], "width_ratios": [1.7, 1]})
    top, bottom, ztop, zbottom = axes[0, 0], axes[1, 0], axes[0, 1], axes[1, 1]
    top.plot(r.index, r.cumsum() * 100, color=plots.BLUE, lw=1.6)
    top.axhline(0, color=plots.AXIS, lw=1)
    ymax = r.cumsum().max() * 100
    for year, part in r.groupby(r.index.year):
        top.text(pd.Timestamp(f"{year}-07-01"), ymax * 1.06, f"{part.sum() * 100:+.1f}%", ha="center", fontsize=8.5,
                 color=plots.INK_SOFT)
    top.set_ylim(top.get_ylim()[0], ymax * 1.14)
    top.set_ylabel("Cumulative profit, % of gross")
    top.set_title("Late-day reversal, before costs (numbers above: each year's profit)")
    bottom.plot(spy.loc[dates[0]:].index, spy.loc[dates[0]:], color=plots.GRAY, lw=1.2)
    bottom.set_ylabel("SPY price")
    bottom.set_title("For context: SPY", fontsize=10)
    zoom = r.loc["2026-10-01":]
    ztop.bar(zoom.index, zoom * 1e4, color=[plots.BLUE if v >= 0 else plots.ORANGE for v in zoom], width=0.8)
    ztop.axhline(0, color=plots.INK_SOFT, lw=1)
    ztop.set_ylabel("Profit, bps (trade placed that afternoon)")
    ztop.set_title("October - November 2026, day by day")
    worst = zoom.idxmin()
    ztop.annotate("Oct 28: earnings overnight\n(FTNT -27%, NOW -19%)", (worst, zoom.min() * 1e4), xytext=(10, 0),
                  textcoords="offset points", fontsize=8.5, color=plots.INK_SOFT, va="center")
    crash = spy.pct_change().loc["2026-10-01":].idxmin()
    ztop.annotate(f"{crash:%b} {crash.day}: SPY {spy.pct_change()[crash] * 100:.1f}%\nbook {zoom[crash] * 1e4:+.0f} bps",
                  (crash, max(zoom[crash] * 1e4, 0)), xytext=(-250, -170), textcoords="offset points", fontsize=8.5,
                  color=plots.INK_SOFT, arrowprops={"arrowstyle": "-", "color": plots.AXIS})
    spy_zoom = spy.loc["2026-10-01":"2026-11-09"]
    zbottom.plot(spy_zoom.index, spy_zoom, color=plots.GRAY, lw=1.4, marker="o", markersize=3)
    zbottom.set_ylabel("SPY price")
    zbottom.tick_params(axis="x", rotation=45)
    plots.save(fig, STUDY, "3_profit_over_time.png")


def main():
    panel = data.load_panel()
    state = signals.build_state(panel)
    intraday, outcome, signal, sigma = tables(panel, state)
    ready = np.isfinite(signal[20]).sum(axis=1) >= 50
    days = np.flatnonzero(ready & (state.group != signals.NOT_USED).any(axis=1))
    days = days[days < len(panel.dates) - 1]
    dates = panel.dates[days]
    out = plots.folder(STUDY)
    pd.set_option("display.width", 250)

    # 1 + 2: every (hedge, signal time, way of trading). Reading the signal at 3:50 and
    # trading at 3:50 would use one price for both, so that pair is left out.
    grid, daily, books = [], {}, {}
    for hedge in HEDGES:
        for minutes in (30, 20, 10):
            held = holdings(panel, state, signal[minutes], sigma, hedge, days)
            books[hedge, minutes] = held
            for way in WAYS:
                if minutes == 10 and way == "3:50 pm to next open":
                    continue
                r = daily_return(held, outcome[way], days)
                daily[hedge, minutes, way] = r
                grid += summarize(r, dates, {"hedge": hedge, "signal_minutes_before_close": minutes, "way": way})
    grid = pd.DataFrame(grid)
    grid.to_csv(out / "grid.csv", index=False)
    pd.DataFrame({f"{h} | {m} min | {w}": r for (h, m, w), r in daily.items()}, index=dates).to_csv(out / "daily_returns.csv")

    hedge_table = grid[(grid.signal_minutes_before_close == MAIN[1]) & (grid.way == MAIN[2])]
    print(hedge_table[["hedge", "period", "cagr_pct", "vol_pct", "sharpe", "sharpe_low", "sharpe_high",
                       "max_drawdown_pct", "breakeven_cost_bps"]].round(2).to_string(index=False))
    rivals = []
    main_r = daily[MAIN]
    for hedge in HEDGES[1:]:
        for period, mask in (("2017-2026", np.ones(len(dates), bool)), ("before 2024", dates < data.SPLIT),
                             ("2024 on", dates >= data.SPLIT)):
            diff, low, high = evaluate.sharpe_difference_ci(main_r[mask], daily[hedge, MAIN[1], MAIN[2]][mask])
            rivals.append({"rival": hedge, "period": period, "tda_minus_rival_sharpe": diff, "low": low, "high": high})
    rivals = pd.DataFrame(rivals)
    rivals.to_csv(out / "tda_minus_rival.csv", index=False)
    print(rivals.round(2).to_string(index=False))

    early = grid[grid.period == "before 2024"]
    for way in WAYS:
        best = early[early.way == way].sort_values("sharpe").iloc[-1]
        later = grid[(grid.period == "2024 on") & (grid.way == way) & (grid.hedge == best.hedge)
                     & (grid.signal_minutes_before_close == best.signal_minutes_before_close)].iloc[0]
        print(f"tuning, {way}: best before 2024 = {best.hedge}, signal {best.signal_minutes_before_close} min "
              f"(Sharpe {best.sharpe:.2f}); its 2024-on Sharpe {later.sharpe:.2f}")
    tuning = []
    for way in WAYS:
        part = early[early.way == way].sort_values("sharpe", ascending=False)
        for _, b in part.iterrows():
            later = grid[(grid.period == "2024 on") & (grid.way == way) & (grid.hedge == b.hedge)
                         & (grid.signal_minutes_before_close == b.signal_minutes_before_close)].iloc[0]
            tuning.append({"way": way, "hedge": b.hedge, "signal_minutes_before_close": b.signal_minutes_before_close,
                           "sharpe_before_2024": b.sharpe, "sharpe_2024_on": later.sharpe})
    tuning = pd.DataFrame(tuning)
    tuning.to_csv(out / "tuning.csv", index=False)
    print(tuning.round(2).to_string(index=False))
    print("rank correlation of before-2024 and 2024-on Sharpe across the grid:",
          round(tuning[["sharpe_before_2024", "sharpe_2024_on"]].corr(method="spearman").iloc[0, 1], 2))

    # 3: attribution for the main version
    bars = data.load_bar_fields(panel, fields=("v", "vw"))
    dollar_volume = pd.DataFrame(bars["v"] * bars["vw"]).rolling(20).mean().shift(1).to_numpy()
    held = books[MAIN[0], MAIN[1]]
    attr = attribution(panel, state, held, outcome[MAIN[2]], days, {"dollar_volume": dollar_volume, "signal": signal[20]})
    attr.to_csv(out / "attribution.csv", index=False)
    print(attr.round(3).to_string(index=False))

    # 4: capacity (every 5th day is enough for a median)
    cap = capacity(panel, held, days, data.dataset_folder(data.INTRADAY))
    cap.to_csv(out / "capacity.csv", index=False)
    print(cap.round(3).to_string(index=False))

    figure_hedges(hedge_table, {h: daily[h, MAIN[1], MAIN[2]] for h in HEDGES}, dates)
    figure_profit(panel, dates, daily[MAIN])
    figure_attribution(attr)


if __name__ == "__main__":
    main()
