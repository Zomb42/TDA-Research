"""G6. When should the late-day book be sold the next morning?

The main version (signal at 3:40, bought or sold at the 3:50 price) sells at the
next official open (9:30). The first minutes of trading are the noisiest of the
day, so selling a little later might avoid noise, or might give up the bounce.
Holding longer might also catch more of it.

Exit prices on the next day (unadjusted, compared only with that day's open):

  every day         10:00, 10:30, 11:00 and 12:00 (ends of 30-minute bars), and the close
  every 5th day     9:35, 9:40, 9:45, 9:50, 9:55 (ends of 5-minute bars)

Return = (official close / 3:50 price) x (next open / official close, adjusted)
         x (exit price / next open) - 1.
A stock with no bar at the exit time on a day is sold at the open instead (0.2%).
Before costs. Same positions in every row: only the exit changes.

    conda run -n tda python equity/studies/s17_exit_timing.py
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

STUDY = "s17_exit_timing"
HALF = {"10:00": 30, "10:30": 60, "11:00": 90, "12:00": 150}             # minutes after the open
FIVE = {"9:35": 5, "9:40": 10, "9:45": 15, "9:50": 20, "9:55": 25, "10:00": 30}


def exit_prices(panel):
    """Price at each exit time on day t (unadjusted), days x stocks. Cached."""
    cache = plots.folder(STUDY) / "exit_prices.npz"
    if cache.exists():
        return dict(np.load(cache))
    raw = data.dataset_folder(data.INTRADAY) / "raw"
    column = {s: i for i, s in enumerate(panel.symbols)}
    row = {str(d.date()): t for t, d in enumerate(panel.dates)}
    out = {f"half|{k}": np.full(panel.returns.shape, np.nan) for k in HALF}
    out.update({f"five|{k}": np.full(panel.returns.shape, np.nan) for k in FIVE})
    out["five_day"] = np.zeros(len(panel.dates), bool)
    for kind, times, folder in (("half", HALF, "half_hours"), ("five", FIVE, "five_minutes")):
        for path in sorted((raw / folder).glob("*.json.gz")):
            day = json.load(gzip.open(path))
            t = row.get(day["date"])
            if t is None:
                continue
            if kind == "five":
                out["five_day"][t] = True
            open_ = pd.Timestamp(f"{day['date']} {day['open']}", tz="America/New_York").tz_convert("UTC")
            for symbol, bars in day["bars"].items():
                i = column.get(symbol)
                if i is None:
                    continue
                ends = {round((pd.Timestamp(b["t"]) - open_).total_seconds() / 60) + (30 if kind == "half" else 5): b["c"]
                        for b in bars}
                for label, minutes in times.items():
                    if minutes in ends:
                        out[f"{kind}|{label}"][t, i] = ends[minutes]
    np.savez_compressed(cache, **out)
    return out


def main():
    np.seterr(invalid="ignore", divide="ignore")
    panel = data.load_panel()
    state = signals.build_state(panel)
    intraday, outcomes, signal, sigma = tables(panel, state)
    exits = exit_prices(panel)
    ready = np.isfinite(signal[20]).sum(axis=1) >= 50
    days = np.flatnonzero(ready & (state.group != signals.NOT_USED).any(axis=1))
    days = days[days < len(panel.dates) - 1]
    held = holdings(panel, state, signal[20], sigma, "TDA peer groups", days)
    base = outcomes["3:50 pm to next open"]                       # 3:50 price -> next official open
    n = panel.returns.shape[1]
    nxt = lambda a: np.vstack([a[1:], np.full((1, n), np.nan)])  # next day's value on row t
    open_raw_next = nxt(panel.open_raw)
    close_next = (1 + base) * nxt(panel.close_raw) / open_raw_next - 1      # hold to the next close

    def book(exit_raw_next):
        after_open = np.where(np.isfinite(exit_raw_next), exit_raw_next / open_raw_next, 1.0)
        return np.nansum(held[days] * ((1 + base) * after_open - 1)[days], axis=1)

    series = {"9:30 (open, current)": np.nansum(held[days] * base[days], axis=1)}
    for label in HALF:
        series[label] = book(nxt(exits[f"half|{label}"]))
    series["next close (16:00)"] = np.nansum(held[days] * np.nan_to_num(close_next[days]), axis=1)
    five_days = np.r_[exits["five_day"][1:], False][days].astype(bool)         # the NEXT day has 5-minute bars
    five = {"9:30 (open, current)": series["9:30 (open, current)"][five_days]}
    for label in FIVE:
        five[label] = book(nxt(exits[f"five|{label}"]))[five_days]

    dates = panel.dates[days]
    rows = []
    for sample, table, mask in (("every day", series, np.ones(len(days), bool)), ("every 5th day (5-minute bars)", five, None)):
        current = table["9:30 (open, current)"]
        for label, r in table.items():
            s, low, high = evaluate.sharpe_ci(r, block=60 if mask is not None else 12)
            diff, dl, dh = evaluate.sharpe_difference_ci(r, current, block=60 if mask is not None else 12)
            rows.append({"sample": sample, "exit": label, "days": len(r), "bps_per_day": r.mean() * 1e4,
                         "volatility_bps_per_day": r.std() * 1e4, "sharpe": s, "low": low, "high": high,
                         "minus_open": diff, "diff_low": dl, "diff_high": dh})
    table = pd.DataFrame(rows)
    out = plots.folder(STUDY)
    table.to_csv(out / "exit_times.csv", index=False)
    pd.set_option("display.width", 220)
    print(table.round(2).to_string(index=False))

    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout="constrained")
    for ax, sample in zip(axes, ("every day", "every 5th day (5-minute bars)")):
        part = table[table["sample"] == sample]
        x = np.arange(len(part))
        ax.errorbar(x, part.sharpe, yerr=[part.sharpe - part.low, part.high - part.sharpe], fmt="o", color=plots.BLUE,
                    elinewidth=2, capsize=0)
        ax.set_xticks(x, part.exit, rotation=30, fontsize=8.5)
        ax.axhline(part.sharpe.iloc[0], color=plots.ORANGE, lw=1, ls="--")
        ax.grid(axis="x", visible=False)
        ax.set_title(f"{sample}, {int(part.days.iloc[0])} days", fontsize=10)
        ax.set_ylabel("Sharpe before costs (95% interval)")
    fig.suptitle("When to sell the next morning? Same positions, only the exit time changes (orange = selling at the open)",
                 x=0.01, ha="left", fontweight="bold", fontsize=10)
    plots.save(fig, STUDY, "1_exit_times.png")


if __name__ == "__main__":
    main()
