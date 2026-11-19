"""G4. Confirm a pattern found by accident: do straight runs reverse more than choppy ones?

Study 13 (114 days, every 25th trading day) found that the late-day reversal
comes from stocks whose price moved in a straight run that day, not from choppy
ones. It was not planned, so it could be chance. This tests it on days that
played no part in finding it.

  straightness = |move from the open to 3:40| / distance travelled
                 (1 = a straight line, near 0 = a lot of back and forth)

measured on the 30-minute path (open, then 10:00 ... 15:30, then 15:40), which
exists for every day. "Held-out days" are all days outside the 5-minute sample
(every 5th trading day), so none of them was seen by study 13.

  1. Reversal by straightness third, within each day (as in study 13)
  2. The main book (study 11) restricted to the straighter half or the choppier
     half of each peer group's stocks, before and after measured costs (study 12)

    conda run -n tda python equity/studies/s15_straight_runs.py
"""
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from s04_peer_reversal_book import exposures_for
from s05_when_is_the_bounce import THIRDS, spread, thirds_within_day
from s11_late_day_characterize import tables
from s12_late_day_costs import SEC_FEE_BPS
from tdaeq import data, evaluate, plots, portfolio, signals

STUDY = "s15_straight_runs"


def straightness(panel, intraday):
    cache = plots.folder(STUDY) / "straightness.npy"
    if cache.exists():
        return np.load(cache)
    folder = data.dataset_folder(data.INTRADAY) / "raw" / "half_hours"
    column = {s: i for i, s in enumerate(panel.symbols)}
    row = {str(d.date()): t for t, d in enumerate(panel.dates)}
    out = np.full(panel.returns.shape, np.nan)
    for path in sorted(folder.glob("*.json.gz")):
        day = json.load(gzip.open(path))
        t = row.get(day["date"])
        if t is None:
            continue
        for symbol, bars in day["bars"].items():
            i = column.get(symbol)
            if i is None or not np.isfinite(intraday["price_20"][t, i]):
                continue                        # the loader's completeness check already passed for this stock-day
            prices = np.log([bars[0]["o"]] + [b["c"] for b in bars] + [intraday["price_20"][t, i]])
            travel = np.abs(np.diff(prices)).sum()
            out[t, i] = abs(prices[-1] - prices[0]) / travel if travel > 0 else np.nan
    np.save(cache, out)
    return out


def book(panel, state, signal, sigma, days, keep):
    """Main book (TDA peer groups), trading only the stocks where keep is True."""
    held = np.zeros(panel.returns.shape)
    for t in days:
        used = np.flatnonzero((state.group[t] != signals.NOT_USED) & np.isfinite(signal[t]) & np.isfinite(sigma[t]) & keep[t])
        if len(used) < 30:
            continue
        stocks, columns = exposures_for("TDA peer groups", state, t, used)
        held[t, stocks], _ = portfolio.neutral_book(signal[t, stocks], columns, 1 / sigma[t, stocks] ** 2)
    return held


def main():
    np.seterr(invalid="ignore", divide="ignore")
    panel = data.load_panel()
    state = signals.build_state(panel)
    intraday, outcomes, signal, sigma = tables(panel, state)
    straight = straightness(panel, intraday)
    calendar = [d["date"] for d in json.loads((data.dataset_folder(data.CURRENT) / "calendar.json").read_text())
                if "2017-01-03" <= d["date"] <= "2026-11-09"]
    sampled = set(calendar[::5])
    in_sample = np.array([str(d.date()) in sampled for d in panel.dates])
    ready = np.isfinite(signal[20]).sum(axis=1) >= 50
    days = np.flatnonzero(ready & (state.group != signals.NOT_USED).any(axis=1))
    days = days[days < len(panel.dates) - 1]
    out = plots.folder(STUDY)
    pd.set_option("display.width", 250)

    # 1. reversal by straightness third, as in study 13 (signal and outcome against peers)
    outcome = outcomes["3:50 pm to next open"]
    rows = []
    daily = {b: np.full(len(panel.dates), np.nan) for b in THIRDS}
    for t in days:
        grouped = state.group[t] >= 0
        s = np.where(grouped, signal[20][t] / sigma[t], np.nan)
        vs = signals.minus_group_mean(s, state.group[t])
        y = signals.minus_group_mean(np.where(grouped, outcome[t], np.nan), state.group[t])
        third = thirds_within_day(np.where(np.isfinite(vs), straight[t], np.nan))
        for b, label in enumerate(THIRDS):
            daily[label][t] = spread(np.where(third == b, vs, np.nan), y)
    for label, series in daily.items():
        for name, mask in (("held-out days", ~in_sample), ("held-out, before 2024", ~in_sample & (panel.dates < data.SPLIT)),
                           ("held-out, 2024 on", ~in_sample & (panel.dates >= data.SPLIT)), ("5-minute sample days", in_sample)):
            use = mask & np.isfinite(series)
            mean, low, high = evaluate.mean_ci(series[use], block=10)
            rows.append({"straightness_third": label, "days": name, "n": int(use.sum()), "reversal_bps": mean * 1e4,
                         "low": low * 1e4, "high": high * 1e4})
    thirds = pd.DataFrame(rows)
    thirds.to_csv(out / "reversal_by_straightness.csv", index=False)
    print("Low third = choppiest, High third = straightest")
    print(thirds.round(2).to_string(index=False))
    gap = daily["High"] - daily["Low"]
    for name, mask in (("held-out days", ~in_sample), ("5-minute sample days", in_sample)):
        use = mask & np.isfinite(gap)
        mean, low, high = evaluate.mean_ci(gap[use], block=10)
        print(f"straightest minus choppiest, {name}: {mean * 1e4:.2f} bps ({low * 1e4:.2f} to {high * 1e4:.2f})")

    # 2. the book on the straighter or the choppier half of each day's stocks
    rank = pd.DataFrame(straight).rank(axis=1, pct=True).to_numpy()
    halves = {"All stocks (study 11)": np.ones(rank.shape, bool), "Straighter half": rank > 0.5, "Choppier half": rank <= 0.5}
    book_rows, cum = [], {}
    held_out = days[~in_sample[days]]
    dates = panel.dates[held_out]
    for way, minutes, cost in (("3:50 pm to next open", 20, "spread"), ("Close to next open", 10, "auction")):
        for name, keep in halves.items():
            held = book(panel, state, signal[minutes], sigma, held_out, keep)
            h = np.abs(held[held_out])
            gross = np.nansum(held[held_out] * outcomes[way][held_out], axis=1)
            fees = h.sum(axis=1) * SEC_FEE_BPS * 1e-4
            if cost == "spread":
                quoted = pd.read_csv(plots.RESULTS / "s12_late_day_costs" / "net_of_costs.csv")
                half_spread = quoted[(quoted.scenario == "A") & (quoted.period == "2017-2026")].position_weighted_full_spread_bps.iloc[0] / 2
                net = gross - fees - h.sum(axis=1) * half_spread * 1e-4
            else:
                net = gross - fees
            cum[way, name] = net
            for period, mask in (("held-out days", np.ones(len(dates), bool)), ("held-out, before 2024", dates < data.SPLIT),
                                 ("held-out, 2024 on", dates >= data.SPLIT)):
                s, low, high = evaluate.sharpe_ci(gross[mask])
                n, nl, nh = evaluate.sharpe_ci(net[mask])
                book_rows.append({"way": way, "stocks": name, "period": period, "days": int(mask.sum()),
                                  "gross_bps_per_day": gross[mask].mean() * 1e4, "gross_sharpe": s, "gross_low": low, "gross_high": high,
                                  "net_bps_per_day": net[mask].mean() * 1e4, "net_sharpe": n, "net_low": nl, "net_high": nh})
    books = pd.DataFrame(book_rows)
    books.to_csv(out / "books.csv", index=False)
    print(books.round(2).to_string(index=False))
    for way in ("3:50 pm to next open", "Close to next open"):
        diff, low, high = evaluate.sharpe_difference_ci(cum[way, "Straighter half"], cum[way, "Choppier half"])
        print(f"{way}: straighter minus choppier half, net Sharpe {diff:.2f} ({low:.2f} to {high:.2f})")

    fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
    part = thirds[thirds.days.isin(["5-minute sample days", "held-out days"])]
    for offset, (name, color) in zip((-0.12, 0.12), (("5-minute sample days", plots.GRAY), ("held-out days", plots.BLUE))):
        p = part[part.days == name].set_index("straightness_third").loc[THIRDS]
        ax.errorbar(np.arange(3) + offset, p.reversal_bps, yerr=[p.reversal_bps - p.low, p.high - p.reversal_bps],
                    fmt="o", color=color, elinewidth=2, capsize=0, label=f"{name} ({int(p.n.iloc[0])} days)")
    ax.set_xticks(np.arange(3), ["Choppiest third", "Middle third", "Straightest third"])
    ax.set_xlim(-0.5, 2.5)
    ax.axhline(0, color=plots.INK_SOFT, lw=1)
    ax.set_ylabel("Reversal by the next open, bps")
    ax.legend(loc="upper left")
    ax.set_title("Do straight runs into 3:40 pm reverse more than choppy ones? 95% intervals")
    plots.save(fig, STUDY, "1_straight_runs.png")


if __name__ == "__main__":
    main()
