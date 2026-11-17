"""D. A reversal book built on TDA peer groups, against plain competitors.

Every book bets against today's move, and differs only in what it is neutral to:

  Market only        zero dollars, zero SPY beta                  (all stocks)
  Sectors            also zero inside each of the 11 sectors      (all stocks)
  TDA peer groups    also zero inside each HDBSCAN group          (grouped stocks only)
  Plain fine groups  same idea with average linkage cut into 100  (grouped stocks only)
  Market only, same stocks   the first book restricted to the TDA-grouped stocks

Being neutral inside a group means the bet is "this stock against its close
peers", so most of the shared noise cancels.

Three ways of trading it (all before costs, total long + short = 1):
  close to close   trade at today's close, hold to tomorrow's close (needs a close trade)
  open to close    decide overnight, trade at tomorrow's open, exit at the close
  5-day            signal is the 5-day move; enter next open, hold 5 days, 1/5 of capital per day

    conda run -n tda python equity/studies/s04_peer_reversal_book.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tdaeq import data, evaluate, factors, plots, portfolio, signals

STUDY = "s04_peer_reversal_book"
BOOKS = ["Market only", "Sectors", "TDA peer groups", "Plain fine groups", "Market only, same stocks"]
COLORS = dict(zip(BOOKS, [plots.GRAY, plots.AQUA, plots.BLUE, plots.ORANGE, plots.YELLOW]))
WAYS = ["close to close", "open to close", "5-day"]


def exposures_for(book, state, t, used):
    """Which stocks the book trades on day t, and the columns it must be neutral to."""
    beta = state.beta[t]
    if book == "Market only":
        stocks = used
        columns = np.column_stack([np.ones(len(stocks)), beta[stocks]])
    elif book == "Sectors":
        stocks = used
        columns = factors.group_exposures(state.sector[stocks], beta[stocks])
    elif book == "Market only, same stocks":
        stocks = used[state.group[t, used] >= 0]
        columns = np.column_stack([np.ones(len(stocks)), beta[stocks]])
    else:
        labels = state.group[t] if book == "TDA peer groups" else state.group_plain[t]
        stocks = used[labels[used] >= 0]
        columns = factors.group_exposures(labels[stocks], beta[stocks])
    return stocks, columns


def run(panel, state):
    days, n = panel.returns.shape
    close_close = np.vstack([panel.close_adj[1:] / panel.close_adj[:-1] - 1, np.full((1, n), np.nan)])
    open_close = np.vstack([panel.close_adj[1:] / panel.open_adj[1:] - 1, np.full((1, n), np.nan)])
    five_day = signals.rolling_sum(np.nan_to_num(panel.returns), 5)

    start = data.MIN_HISTORY + 5
    held = {(book, kind): np.zeros((days, n)) for book in BOOKS for kind in ("1d", "5d")}
    for t in range(start, days - 1):
        used = np.flatnonzero(state.group[t] != signals.NOT_USED)
        total_sigma = np.maximum(panel.returns[t - 252:t, used].std(axis=0, ddof=1), 1e-4)
        weights_all = np.zeros(n)
        weights_all[used] = 1 / total_sigma ** 2
        for book in BOOKS:
            stocks, columns = exposures_for(book, state, t, used)
            for kind, signal in (("1d", panel.returns[t]), ("5d", five_day[t])):
                holdings, _ = portfolio.neutral_book(signal[stocks], columns, weights_all[stocks])
                held[book, kind][t, stocks] = holdings

    index = np.arange(start, days - 1)
    returns, turnover = {}, {}
    for book in BOOKS:
        h1, h5 = held[book, "1d"], held[book, "5d"]
        returns[book, "close to close"] = np.nansum(h1[index] * close_close[index], axis=1)
        turnover[book, "close to close"] = np.abs(h1[index] - h1[index - 1]).sum(axis=1)
        returns[book, "open to close"] = np.nansum(h1[index] * open_close[index], axis=1)
        turnover[book, "open to close"] = np.full(len(index), 2.0)          # in at the open, out at the close
        # 5-day sleeves: the cohort formed on day t-k earns open-to-close on its first day, close-to-close after
        daily = np.nansum(h5[index] * open_close[index], axis=1)
        for k in range(1, 5):
            daily = daily + np.nansum(h5[index - k] * close_close[index], axis=1)
        returns[book, "5-day"] = daily / 5
        turnover[book, "5-day"] = np.full(len(index), 2.0 / 5)
    return panel.dates[index + 1], returns, turnover


def main():
    panel = data.load_panel()
    state = signals.build_state(panel)
    dates, returns, turnover = run(panel, state)
    later = dates >= data.SPLIT

    rows = []
    for (book, way), r in returns.items():
        for label, mask in (("before 2024", ~later), ("2024 on", later), ("all", np.ones(len(r), bool))):
            perf = evaluate.performance(r[mask])
            sharpe, low, high = evaluate.sharpe_ci(r[mask])
            rows.append({"book": book, "way": way, "period": label, **perf,
                         "sharpe_low": low, "sharpe_high": high,
                         "turnover_per_day": turnover[book, way][mask].mean(),
                         "breakeven_cost_bps": r[mask].mean() / turnover[book, way][mask].mean() * 1e4})
    table = pd.DataFrame(rows)

    paired = []
    for way in WAYS:
        for rival in BOOKS:
            if rival == "TDA peer groups":
                continue
            for label, mask in (("before 2024", ~later), ("2024 on", later)):
                diff, low, high = evaluate.sharpe_difference_ci(
                    returns["TDA peer groups", way][mask], returns[rival, way][mask])
                paired.append({"way": way, "period": label, "rival": rival,
                               "sharpe_difference": diff, "low": low, "high": high})
    paired = pd.DataFrame(paired)

    out = plots.folder(STUDY)
    table.to_csv(out / "performance.csv", index=False)
    paired.to_csv(out / "tda_minus_rival_sharpe.csv", index=False)
    pd.DataFrame({f"{b} | {w}": r for (b, w), r in returns.items()}, index=dates).to_csv(out / "daily_returns.csv")
    pd.set_option("display.width", 250)
    show = table[table.period != "all"].drop(columns=["days", "max_drawdown_pct"])
    print(show.round(2).to_string(index=False))
    print(paired.round(2).to_string(index=False))
    figure(dates, returns)


def figure(dates, returns):
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2), layout="constrained")
    for ax, way in zip(axes, WAYS):
        for book in BOOKS:
            r = returns[book, way]
            scaled = r * (0.05 / np.sqrt(252)) / r.std(ddof=1)        # every book shown at 5% yearly volatility
            ax.plot(dates, np.cumsum(scaled) * 100, color=COLORS[book], lw=1.6, label=book)
        ax.axvline(data.SPLIT, color=plots.INK_SOFT, lw=1, ls="--")
        ax.axhline(0, color=plots.AXIS, lw=1)
        ax.set_title(f"Traded {way}")
        ax.set_ylabel("Cumulative return, % (each book scaled to 5% volatility)")
    axes[0].legend(loc="upper left")
    axes[0].text(data.SPLIT, axes[0].get_ylim()[0], " 2024", va="bottom", fontsize=8.5, color=plots.INK_SOFT)
    fig.suptitle("Reversal books before costs: the same bet, hedged against different peer groups",
                 x=0.01, ha="left", fontweight="bold")
    plots.save(fig, STUDY, "1_cumulative_returns.png")


if __name__ == "__main__":
    main()
