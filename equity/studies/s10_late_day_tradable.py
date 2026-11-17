"""G1. Is the late-day reversal tradable?

Study 9 found that the late part of a stock's move (from the day's average
traded price to the close) reverses by the next morning. That rule used the
closing price as both the signal and the trade price, so it could not be
traded as measured. This study uses intraday bars to split it up.

The late move has three pieces:

  up to 10 minutes before the close   visible in time to send an order for the close
  the last 10 minutes of trading      visible only at the very end
  the closing auction                 not visible before you trade

Signals, each used in the same peer-hedged book as studies 4 and 9
(bet against the signal, neutral inside every TDA peer group):

  as in study 9            average price of the whole day -> official close
  known 30 / 20 / 10 minutes before the close
                           average price so far -> price at that moment
  last 10 minutes only     price 10 minutes before the close -> last regular trade
  closing auction only     last regular trade -> official close

Ways of trading:

  at the close, to the next close    an order for the closing auction, held one day
  at the close, to the next open     the same, sold at the next open
  10 minutes before the close, to the next open
                                     trade straight away in the open market instead
                                     of waiting for the auction (only for signals
                                     known by then)

All before costs. "Minutes before the close" also handles half days.

    conda run -n tda python equity/studies/s10_late_day_tradable.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from s04_peer_reversal_book import exposures_for
from tdaeq import data, evaluate, plots, portfolio, signals

STUDY = "s10_late_day_tradable"
S9 = "As in study 9 (day's average price to official close)"
KNOWN = {m: f"Known {m} minutes before the close" for m in (30, 20, 10)}
LAST10, AUCTION = "Last 10 minutes of trading only", "Closing auction only"
WHOLE = "Whole day's move, known 10 minutes before the close"
WAYS = ["At the close, to the next close", "At the close, to the next open",
        "10 minutes before the close, to the next open"]
EARLY_ENOUGH = [KNOWN[30], KNOWN[20], KNOWN[10], WHOLE]          # signals that exist 10 minutes before the close


def build_signals(panel, intraday):
    """Each signal is a log move, days x stocks. The book bets against it."""
    day_average = data.load_bar_fields(panel, fields=("vw",))["vw"]
    previous_close = np.vstack([np.full((1, panel.returns.shape[1]), np.nan), panel.close_raw[:-1]])
    split_days = np.abs(np.log(panel.close_raw / previous_close) - panel.returns) > 0.02     # split or large dividend
    out = {S9: np.log(panel.close_adj / day_average)}
    for minutes, name in KNOWN.items():
        out[name] = np.log(intraday[f"price_{minutes}"] / intraday[f"vwap_{minutes}"])
    out[LAST10] = np.log(intraday["last_trade"] / intraday["price_10"])
    out[AUCTION] = np.log(panel.close_raw / intraday["last_trade"])
    out[WHOLE] = np.where(split_days, np.nan, np.log(intraday["price_10"] / previous_close))
    have = np.isfinite(intraday["price_10"])
    return {name: np.where(have, table, np.nan) for name, table in out.items()}


def run(panel, state, bets, intraday):
    days, n = panel.returns.shape
    total_sigma = np.maximum(pd.DataFrame(panel.returns).rolling(252).std(ddof=1).shift(1).to_numpy(), 1e-4)
    to_next_close = np.vstack([panel.close_adj[1:] / panel.close_adj[:-1] - 1, np.full((1, n), np.nan)])
    to_next_open = np.vstack([panel.open_adj[1:] / panel.close_adj[:-1] - 1, np.full((1, n), np.nan)])
    early_entry = (panel.close_raw / intraday["price_10"]) * (1 + to_next_open) - 1     # bought 10 minutes before the close
    ready = np.isfinite(bets[S9]).sum(axis=1) >= 50
    index = np.flatnonzero(ready & (state.group != signals.NOT_USED).any(axis=1))
    index = index[index < days - 1]
    returns, turnover = {}, {}
    for name, signal in bets.items():
        held = np.zeros((days, n))
        for t in index:
            used = np.flatnonzero((state.group[t] != signals.NOT_USED) & np.isfinite(signal[t])
                                  & np.isfinite(total_sigma[t]))
            stocks, columns = exposures_for("TDA peer groups", state, t, used)
            held[t, stocks], _ = portfolio.neutral_book(signal[t, stocks], columns, 1 / total_sigma[t, stocks] ** 2)
        previous = np.vstack([np.zeros((1, n)), held[:-1]])
        returns[name, WAYS[0]] = np.nansum(held[index] * to_next_close[index], axis=1)
        turnover[name, WAYS[0]] = np.abs(held[index] - previous[index]).sum(axis=1)
        returns[name, WAYS[1]] = np.nansum(held[index] * to_next_open[index], axis=1)
        turnover[name, WAYS[1]] = np.full(len(index), 2.0)
        if name in EARLY_ENOUGH:
            returns[name, WAYS[2]] = np.nansum(held[index] * early_entry[index], axis=1)
            turnover[name, WAYS[2]] = np.full(len(index), 2.0)
    return panel.dates[index], returns, turnover


def score(dates, returns, turnover):
    periods = [("2017 on", dates >= "2017"), ("2019 on", dates >= "2019"),
               ("before 2024", dates < data.SPLIT), ("2024 on", dates >= data.SPLIT)]
    rows = []
    for (name, way), r in returns.items():
        for label, mask in periods:
            if mask.sum() < 60:
                continue
            sharpe, low, high = evaluate.sharpe_ci(r[mask])
            trade = turnover[name, way][mask].mean()
            rows.append({"signal": name, "way": way, "period": label, **evaluate.performance(r[mask]),
                         "sharpe_low": low, "sharpe_high": high, "turnover_per_day": trade,
                         "breakeven_cost_bps": r[mask].mean() / trade * 1e4,
                         "sharpe_after_1bp_cost": evaluate.sharpe(r[mask] - turnover[name, way][mask] * 1e-4)})
    return pd.DataFrame(rows)


def figure(table, period):
    part = table[table.period == period]
    names = [S9, KNOWN[10], KNOWN[20], KNOWN[30], LAST10, AUCTION, WHOLE][::-1]
    short = {S9: "As in study 9: day's average price\nto official close (not tradable)",
             KNOWN[10]: "Known 10 minutes before the close", KNOWN[20]: "Known 20 minutes before",
             KNOWN[30]: "Known 30 minutes before", LAST10: "Last 10 minutes of trading only",
             AUCTION: "Closing auction only", WHOLE: "Whole day's move,\nknown 10 minutes before"}
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), sharey=True, sharex=True, layout="constrained")
    for ax, way in zip(axes, WAYS):
        rows = part[part.way == way].set_index("signal").reindex(names)
        y = np.arange(len(names))
        ok = rows.sharpe.notna().to_numpy()
        ax.errorbar(rows.sharpe[ok], y[ok], xerr=[(rows.sharpe - rows.sharpe_low)[ok], (rows.sharpe_high - rows.sharpe)[ok]],
                    fmt="o", color=plots.BLUE, elinewidth=2, capsize=0)
        ax.axvline(0, color=plots.INK_SOFT, lw=1)
        ax.set_yticks(y, [short[n] for n in names])
        ax.grid(axis="y", visible=False)
        ax.set_title(f"Traded: {way[0].lower()}{way[1:]}", fontsize=10)
        ax.set_xlabel("Sharpe before costs")
    fig.suptitle(f"Which piece of the late-day move reverses, and can it be traded? Peer-hedged book, {period}, 95% intervals",
                 x=0.01, ha="left", fontweight="bold", fontsize=10)
    plots.save(fig, STUDY, "1_which_piece.png")


def main():
    np.seterr(invalid="ignore", divide="ignore")              # missing prices give NaN on purpose
    panel = data.load_panel()
    state = signals.build_state(panel)
    intraday = data.load_intraday(panel)
    bets = build_signals(panel, intraday)
    have = np.isfinite(bets[KNOWN[10]])
    size = lambda table: np.nanmedian(np.abs(table[have])) * 1e4
    sizes = pd.DataFrame([{"piece": name, "typical_size_bps": size(table)} for name, table in bets.items()])
    link = np.corrcoef(bets[S9][have & np.isfinite(bets[S9])], bets[KNOWN[10]][have & np.isfinite(bets[S9])])[0, 1]
    dates, returns, turnover = run(panel, state, bets, intraday)
    table = score(dates, returns, turnover)
    out = plots.folder(STUDY)
    sizes.to_csv(out / "piece_sizes.csv", index=False)
    table.to_csv(out / "books.csv", index=False)
    pd.DataFrame({f"{name} | {way}": r for (name, way), r in returns.items()}, index=dates).to_csv(out / "daily_returns.csv")
    pd.set_option("display.width", 250)
    print(f"{len(dates)} trading days, {dates[0].date()} to {dates[-1].date()}")
    print(sizes.round(1).to_string(index=False))
    print(f"correlation of the study-9 signal with the one known 10 minutes before the close: {link:.2f}")
    show = ["signal", "way", "period", "mean_bps", "vol_pct", "sharpe", "sharpe_low", "sharpe_high",
            "breakeven_cost_bps", "sharpe_after_1bp_cost"]
    period = "2017 on"
    print(table[table.period == period][show].round(2).to_string(index=False))
    figure(table, period)


if __name__ == "__main__":
    main()
