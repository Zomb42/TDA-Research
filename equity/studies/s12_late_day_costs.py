"""G3. Is the late-day reversal profitable after measured trading costs?

Real bid-ask quotes 10 minutes before the close (market_data/download_equity_quotes.py,
every 5th trading day, all quotes in the 5 seconds before 3:50 pm) give each
stock's spread. Each stock's median spread in each calendar quarter is applied
to every day of that quarter.

Costs charged, per dollar traded:

  spread       half the bid-ask spread, when trading against the market
               (an auction order pays no spread: everyone gets one price)
  SEC fee      0.278 bps on every dollar sold ($27.80 per million, the rate
               set for 2025; my assumption for the whole period)
  commission   0 (many US brokers charge none)
  short borrow about 0.3% a year on the short half, held overnight: under
               0.01 bps a day, ignored

Three ways of trading, each with the book from studies 10-11 (TDA peer groups):

  A  signal at 3:40, ordinary order at 3:50, exit in the next opening auction
     cost = half spread on entry + SEC fee
  B  signal at 3:50, closing-auction order (deadline 3:50 on NYSE), exit in the
     next opening auction: cost = SEC fee only
  B40  the same with the signal read at 3:40, leaving ten minutes to send the order
  C  as A, but also paying half the spread at the open. I have no opening
     quotes; this assumes the opening spread is twice the 3:50 one (a stress case)

Every day the whole book is bought and sold once: entry and exit each trade
the full gross amount, and half of each is a sale.

    conda run -n tda python equity/studies/s12_late_day_costs.py
"""
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from s11_late_day_characterize import holdings, tables
from tdaeq import data, evaluate, plots, signals

STUDY = "s12_late_day_costs"
QUOTES = data.REPO / "market_data/datasets/equity_quotes_1550_2017_2026-11-09"
SEC_FEE_BPS = 0.278
SCENARIOS = {"A": "Order at 3:50, exit in the opening auction",
             "B": "Closing auction in, opening auction out (signal at 3:50)",
             "B40": "Closing auction in, opening auction out (signal at 3:40)",
             "C": "Order at 3:50, order at the open (stress case)"}


def spreads(panel):
    """Days x stocks full bid-ask spread in bps: each stock's median in that calendar quarter."""
    raw = np.full(panel.returns.shape, np.nan)
    column = {s: i for i, s in enumerate(panel.symbols)}
    row = {str(d.date()): t for t, d in enumerate(panel.dates)}
    files = sorted((QUOTES / "days").glob("*.json.gz"))
    for path in files:
        day = json.load(gzip.open(path))
        for symbol, q in day["symbols"].items():
            if symbol in column and day["date"] in row:
                raw[row[day["date"]], column[symbol]] = q["median_spread_bps"]
    quarter = panel.dates.to_period("Q")
    frame = pd.DataFrame(raw, index=panel.dates)
    filled = frame.groupby(quarter).transform("median").to_numpy()
    return raw, filled, len(files)


def main():
    panel = data.load_panel()
    state = signals.build_state(panel)
    intraday, outcome, signal, sigma = tables(panel, state)
    raw, spread, n_days = spreads(panel)
    ready = np.isfinite(signal[20]).sum(axis=1) >= 50
    days = np.flatnonzero(ready & (state.group != signals.NOT_USED).any(axis=1))
    days = days[days < len(panel.dates) - 1]
    dates = panel.dates[days]
    out = plots.folder(STUDY)
    pd.set_option("display.width", 250)

    sampled = raw[np.isfinite(raw).any(axis=1)]
    yearly = pd.Series(np.nanmedian(sampled, axis=1), index=panel.dates[np.isfinite(raw).any(axis=1)]).groupby(
        lambda d: d.year).median()
    print(f"quote days: {n_days}; median full spread at 3:50 pm, bps, by year: {yearly.round(2).to_dict()}")

    books = {"A": (holdings(panel, state, signal[20], sigma, "TDA peer groups", days), "3:50 pm to next open"),
             "B": (holdings(panel, state, signal[10], sigma, "TDA peer groups", days), "Close to next open"),
             "B40": (holdings(panel, state, signal[20], sigma, "TDA peer groups", days), "Close to next open")}
    books["C"] = books["A"]
    rows, daily = [], {}
    half = np.nan_to_num(spread / 2, nan=np.nanmedian(spread) / 2)          # a stock-quarter with no quote gets the median
    for key, (held, way) in books.items():
        h = np.abs(held[days])
        gross = np.nansum(held[days] * outcome[way][days], axis=1)
        fees = h.sum(axis=1) * SEC_FEE_BPS * 1e-4                           # half of entry + half of exit are sales
        spread_cost = {"A": (h * half[days]).sum(axis=1), "B": np.zeros(len(days)), "B40": np.zeros(len(days)),
                       "C": (h * half[days] * 3).sum(axis=1)}[key] * 1e-4     # C: entry half spread + exit at 2x spread
        net = gross - fees - spread_cost
        daily[key] = {"gross": gross, "net": net}
        weighted_spread = np.nansum(h * spread[days]) / h[np.isfinite(spread[days])].sum()
        for period, mask in (("2017-2026", np.ones(len(days), bool)), ("before 2024", dates < data.SPLIT),
                             ("2024 on", dates >= data.SPLIT)):
            g, n = evaluate.performance(gross[mask]), evaluate.performance(net[mask])
            s, low, high = evaluate.sharpe_ci(net[mask])
            rows.append({"scenario": key, "description": SCENARIOS[key], "period": period,
                         "gross_bps_per_day": g["mean_bps"], "cost_bps_per_day": (fees + spread_cost)[mask].mean() * 1e4,
                         "net_bps_per_day": n["mean_bps"], "gross_sharpe": g["sharpe"], "net_sharpe": s,
                         "net_low": low, "net_high": high, "net_return_pct_per_year": n["cagr_pct"],
                         "net_vol_pct": n["vol_pct"], "net_max_drawdown_pct": n["max_drawdown_pct"],
                         "position_weighted_full_spread_bps": weighted_spread})
    table = pd.DataFrame(rows)
    table.to_csv(out / "net_of_costs.csv", index=False)
    pd.DataFrame({f"{k} {kind}": v for k, d in daily.items() for kind, v in d.items()}, index=dates).to_csv(out / "daily_returns.csv")
    print(table.drop(columns=["description"]).round(2).to_string(index=False))

    # How much leverage, and what it would earn net, for one target volatility
    for key in ("A", "B", "B40"):
        r = daily[key]["net"]
        lev = 0.10 / (r.std(ddof=1) * np.sqrt(252))
        print(f"scenario {key}: leverage for 10% volatility = {lev:.1f}x; net return at that leverage "
              f"= {r.mean() * lev * 252 * 100:.1f}% a year (before financing)")

    fig, ax = plt.subplots(figsize=(10, 4.3), layout="constrained")
    for key, color in zip(SCENARIOS, (plots.BLUE, plots.ORANGE, plots.AQUA, plots.GRAY)):
        r = daily[key]["net"]
        ax.plot(dates, np.cumsum(r) * 100, color=color, lw=1.6, label=f"{key}: {SCENARIOS[key]}")
    ax.plot(dates, np.cumsum(daily["A"]["gross"]) * 100, color=plots.BLUE, lw=1, ls=":", label="A before costs")
    ax.axhline(0, color=plots.AXIS, lw=1)
    ax.axvline(data.SPLIT, color=plots.INK_SOFT, lw=1, ls="--")
    ax.set_ylabel("Cumulative return after costs, % (1x gross)")
    ax.legend(loc="upper left")
    ax.set_title("Late-day reversal after measured spreads and fees")
    plots.save(fig, STUDY, "1_after_costs.png")


if __name__ == "__main__":
    main()
