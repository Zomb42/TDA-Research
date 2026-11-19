"""G7. Two kinds of possible improvement: combining versions, and trading faster.

1. Combining. Versions of the strategy whose daily returns are not perfectly
   correlated can be held together: their construction noise partly cancels.
   Picking the best of 576 versions is luck-prone, but the AVERAGE of a fixed
   set of versions is not chosen by its results, so its Sharpe is honest.
   Also: how correlated is the late-day book with the other strategy in this
   project, study 4's close-to-close reversal against TDA peers?

2. Speed. Study 10's best-looking row (Sharpe 3.09) reads the signal from the
   last trade before 3:50 and trades at that same price. A fast system could
   act within milliseconds, so delay is not the problem. The problem is that
   a trade prints at either the bid or the ask: a stock whose last print was at
   the bid looks like it fell, and the backtest "buys" at that low price. Real
   orders pay the ask. The quotes at 3:50 (every 5th day, study 12) give the
   midpoint, which has no such bounce:

     current        signal at 3:40 (last trade), enter at the 3:50 last trade
     current, mid   signal at 3:40, enter at the 3:50 midpoint
     3:50 trade     signal at 3:50 from the last trade, enter at that trade (study 10's 3.09)
     3:50 mid       signal at 3:50 from the midpoint, enter at the midpoint

   If "3:50 mid" keeps the gain, the fresher signal is real information a fast
   system could use. If it falls back to "current", the gain was bounce.

All before costs.

    conda run -n tda python equity/studies/s18_combining_and_speed.py
"""
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from s11_late_day_characterize import holdings, tables
from s12_late_day_costs import QUOTES
from tdaeq import data, evaluate, plots, signals

STUDY = "s18_combining_and_speed"
CURRENT = "since the open | raw move | 1 / variance | (252, 2) | left out"


def combining():
    f = pd.read_parquet(plots.RESULTS / "s16_tuning/A_before_costs/daily_net_returns.parquet")
    best = pd.read_csv(plots.RESULTS / "s16_tuning/A_before_costs/all_versions.csv").sort_values("sharpe").key.iloc[-1]
    corr = f.corr().to_numpy()[np.triu_indices(f.shape[1], 1)]
    blends = {"Current version": f[CURRENT],
              "Best of 576 in hindsight": f[best],
              "Current + best, half each (best chosen with hindsight)": (f[CURRENT] + f[best]) / 2,
              "Average of all 576 versions (nothing chosen)": f.mean(axis=1)}
    # walk-forward blend: each year from 2019, average the K versions that were best on all earlier years
    years = f.index.year
    for k in (10, 50):
        blend = pd.Series(np.nan, index=f.index)
        for y in range(2019, 2027):
            past = f[years < y]
            top = (past.mean() / past.std()).sort_values().index[-k:]
            blend[years == y] = f.loc[years == y, top].mean(axis=1)
        blends[f"Walk-forward blend of the top {k} (from 2019)"] = blend
    rows = []
    for name, r in blends.items():
        if name.startswith("Walk-forward"):
            current_same = f[CURRENT][r.notna()]
            r = r.dropna()
        s, low, high = evaluate.sharpe_ci(r.to_numpy())
        rows.append({"version": name, "sharpe": s, "low": low, "high": high,
                     "before_2024": evaluate.sharpe(r[r.index < data.SPLIT]), "from_2024": evaluate.sharpe(r[r.index >= data.SPLIT]),
                     "correlation_with_current": r.corr(f[CURRENT]),
                     "current_on_same_days": evaluate.sharpe(f[CURRENT][r.index].to_numpy())})
    table = pd.DataFrame(rows)
    # the other strategy in the project: study 4 (dates there are the day the trade is closed)
    s04 = pd.read_csv(plots.RESULTS / "s04_peer_reversal_book/daily_returns.csv", index_col=0, parse_dates=True)
    other = {}
    for col in ("TDA peer groups | close to close", "TDA peer groups | 5-day"):
        o = s04[col]
        late = f[CURRENT].copy()
        late.index = pd.DatetimeIndex([panel_next[d] for d in late.index])          # date the late-day trade is closed
        both = pd.concat([late, o], axis=1, join="inner").dropna()
        a, b = both.iloc[:, 0], both.iloc[:, 1]
        sa, sb, rho = evaluate.sharpe(a.to_numpy()), evaluate.sharpe(b.to_numpy()), a.corr(b)
        mix = a / a.std() + b / b.std()                       # equal risk in each
        # best possible fixed mix of the two (weights chosen with hindsight; one number to choose)
        best_mix = np.sqrt(max((sa ** 2 + sb ** 2 - 2 * rho * sa * sb) / (1 - rho ** 2), 0))
        other[col] = {"other_sharpe": sb, "late_day_sharpe": sa, "correlation": rho,
                      "equal_risk_mix_sharpe": evaluate.sharpe(mix.to_numpy()), "best_fixed_mix_sharpe": best_mix,
                      "days": len(both)}
    return table, pd.DataFrame(other).T, float(np.median(corr)), float(np.quantile(corr, 0.1))


def speed(panel, state, intraday, outcomes, signal, sigma):
    mid = np.full(panel.returns.shape, np.nan)
    column = {s: i for i, s in enumerate(panel.symbols)}
    row = {str(d.date()): t for t, d in enumerate(panel.dates)}
    for path in sorted((QUOTES / "days").glob("*.json.gz")):
        day = json.load(gzip.open(path))
        t = row.get(day["date"])
        for symbol, q in day["symbols"].items():
            if t is not None and symbol in column:
                mid[t, column[symbol]] = (q["last_bid"] + q["last_ask"]) / 2
    # the 3:50 midpoint and last trade should be close; a big gap means a stale or bad quote
    gap = np.abs(np.log(mid / intraday["price_10"]))
    mid = np.where(gap < 0.01, mid, np.nan)
    have = np.isfinite(mid) & np.isfinite(intraday["price_10"])
    n = panel.returns.shape[1]
    to_next_open = np.vstack([panel.open_adj[1:] / panel.close_adj[:-1] - 1, np.full((1, n), np.nan)])
    from_price = lambda price: (panel.close_raw / price) * (1 + to_next_open) - 1
    versions = {
        "current: signal 3:40, enter at the 3:50 last trade": (signal[20], from_price(intraday["price_10"])),
        "current signal, enter at the 3:50 midpoint": (signal[20], from_price(mid)),
        "signal 3:50 last trade, enter at that trade (study 10's 3.09)": (np.log(intraday["price_10"] / intraday["vwap_10"]), from_price(intraday["price_10"])),
        "signal 3:50 midpoint, enter at the midpoint": (np.log(mid / intraday["vwap_10"]), from_price(mid)),
    }
    days = np.flatnonzero(have.sum(axis=1) >= 50)
    days = days[days < len(panel.dates) - 1]
    series = {}
    for name, (sig, out) in versions.items():
        held = holdings(panel, state, np.where(have, sig, np.nan), sigma, "TDA peer groups", days)
        series[name] = np.nansum(held[days] * out[days], axis=1)
    base = series["current: signal 3:40, enter at the 3:50 last trade"]
    rows = []
    for name, r in series.items():
        s, low, high = evaluate.sharpe_ci(r, block=12)
        row = {"version": name, "days": len(r), "bps_per_day": r.mean() * 1e4, "sharpe": s, "low": low, "high": high}
        diff, dl, dh = evaluate.mean_ci(r - base, block=12)
        row.update({"bps_minus_current": diff * 1e4, "diff_low": dl * 1e4, "diff_high": dh * 1e4})
        rows.append(row)
    return pd.DataFrame(rows), float(np.median(gap[have]) * 1e4)


def main():
    global panel_next
    np.seterr(invalid="ignore", divide="ignore")
    panel = data.load_panel()
    panel_next = dict(zip(panel.dates[:-1], panel.dates[1:]))
    out = plots.folder(STUDY)
    pd.set_option("display.width", 250)
    table, other, median_corr, low_corr = combining()
    table.to_csv(out / "combining.csv", index=False)
    other.to_csv(out / "other_strategy.csv")
    print(f"pairwise correlation of daily returns between the 576 versions: median {median_corr:.2f}, 10th percentile {low_corr:.2f}")
    print(table.round(2).to_string(index=False))
    print(other.round(3).to_string())
    state = signals.build_state(panel)
    intraday, outcomes, signal, sigma = tables(panel, state)
    fast, gap_bps = speed(panel, state, intraday, outcomes, signal, sigma)
    fast.to_csv(out / "speed.csv", index=False)
    print(f"median distance between the 3:50 midpoint and the last trade: {gap_bps:.2f} bps")
    print(fast.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
