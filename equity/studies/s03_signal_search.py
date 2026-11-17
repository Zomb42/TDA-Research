"""C0 / D1. Is there any bounce at all, and in which form of the signal?

Each signal is a number per stock known at the close of day t. A reversal
signal should be followed by the OPPOSITE move, so a useful one has a
negative rank correlation with what comes next. To make "good" read as
positive, every number below is the correlation of MINUS the signal with the
next return ("bounce score"), and the spread is what you would earn buying
the 20% most-down stocks and shorting the 20% most-up ones (before costs).

Three ways of measuring "what comes next" (all with SPY's move removed):
  next open to close     tradable with daily bars: decide overnight, trade at the open
  next close to close    needs a trade at the same close the signal is measured on
  next open, hold 5 days tradable; exit at the close five sessions later

    conda run -n tda python equity/studies/s03_signal_search.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tdaeq import data, evaluate, plots, signals

STUDY = "s03_signal_search"


def build_signals(panel, state):
    s = state.surprise
    vs_peers = np.vstack([signals.minus_group_mean(s[t], state.group[t]) for t in range(len(s))])
    sector = np.where(state.group != signals.NOT_USED, state.sector[None, :], signals.NOT_USED)
    vs_sector = np.vstack([signals.minus_group_mean(s[t], sector[t]) for t in range(len(s))])

    # Split today's move into the overnight part and the daytime part.
    prev_close = np.vstack([np.full((1, s.shape[1]), np.nan), panel.close_adj[:-1]])
    spy_prev = np.r_[np.nan, panel.market_close[:-1]]
    overnight = ((panel.open_adj / prev_close - 1)
                 - state.beta * (panel.market_open / spy_prev - 1)[:, None]) / state.sigma
    daytime = ((panel.close_adj / panel.open_adj - 1)
               - state.beta * (panel.market_close / panel.market_open - 1)[:, None]) / state.sigma

    fill = lambda x: np.where(np.isfinite(x), x, 0.0)
    keep = lambda x, like: np.where(np.isfinite(like), x, np.nan)
    return {
        "Surprise, 1 day": s,
        "Surprise, 5 days": keep(signals.rolling_sum(fill(s), 5), s),
        "Surprise, 20 days": keep(signals.rolling_sum(fill(s), 20), s),
        "Versus sector, 1 day": vs_sector,
        "Versus sector, 5 days": keep(signals.rolling_sum(fill(vs_sector), 5), vs_sector),
        "Versus TDA peers, 1 day": vs_peers,
        "Versus TDA peers, 5 days": keep(signals.rolling_sum(fill(vs_peers), 5), vs_peers),
        "Versus TDA peers, 20 days": keep(signals.rolling_sum(fill(vs_peers), 20), vs_peers),
        "Overnight part, 1 day": overnight,
        "Daytime part, 1 day": daytime,
    }


def build_outcomes(panel, state):
    """Forward returns with SPY's move (times beta) removed. Row t = what follows day t."""
    days = len(panel.dates)
    nan_rows = lambda k: np.full((k, panel.returns.shape[1]), np.nan)
    shift = lambda x, k: np.vstack([x[k:], nan_rows(k)])
    shift1 = lambda x, k: np.r_[x[k:], np.full(k, np.nan)]
    b = state.beta
    return {
        "Next open to close": (shift(panel.close_adj, 1) / shift(panel.open_adj, 1) - 1)
            - b * (shift1(panel.market_close, 1) / shift1(panel.market_open, 1) - 1)[:, None],
        "Next close to close": (shift(panel.close_adj, 1) / panel.close_adj - 1)
            - b * (shift1(panel.market_close, 1) / panel.market_close - 1)[:, None],
        "Next open, hold 5 days": (shift(panel.close_adj, 5) / shift(panel.open_adj, 1) - 1)
            - b * (shift1(panel.market_close, 5) / shift1(panel.market_open, 1) - 1)[:, None],
    }


def daily_scores(signal, outcome):
    """Per day: bounce score (rank correlation of -signal with outcome) and the
    return of buying the lowest fifth and shorting the highest fifth."""
    ic, spread = np.full(len(signal), np.nan), np.full(len(signal), np.nan)
    for t in range(len(signal)):
        ok = np.isfinite(signal[t]) & np.isfinite(outcome[t])
        if ok.sum() < 50:
            continue
        x, y = signal[t, ok], outcome[t, ok]
        ic[t] = evaluate.rank_ic(-x, y)
        low, high = np.quantile(x, [0.2, 0.8])
        spread[t] = y[x <= low].mean() - y[x >= high].mean()
    return ic, spread


def main():
    panel = data.load_panel()
    state = signals.build_state(panel)
    sig, out = build_signals(panel, state), build_outcomes(panel, state)
    later = panel.dates >= data.SPLIT
    years = panel.dates.year.to_numpy()

    rows, daily = [], {}
    for s_name, s in sig.items():
        for o_name, o in out.items():
            ic, spread = daily_scores(s, o)
            daily[s_name, o_name] = spread
            for label, mask in (("before 2024", ~later), ("2024 on", later)):
                use = mask & np.isfinite(ic)
                block = 20 if "5 days" in o_name else 10
                mean, low, high = evaluate.mean_ci(ic[use], block=block)
                sp, sp_low, sp_high = evaluate.mean_ci(spread[use], block=block)
                by_year = pd.Series(ic[use]).groupby(years[use]).mean()
                rows.append({"signal": s_name, "outcome": o_name, "period": label, "days": int(use.sum()),
                             "bounce_score": mean, "low": low, "high": high,
                             "spread_bps": sp * 1e4, "spread_low": sp_low * 1e4, "spread_high": sp_high * 1e4,
                             "years_positive": f"{int((by_year > 0).sum())}/{len(by_year)}"})
    table = pd.DataFrame(rows)
    folder = plots.folder(STUDY)
    table.to_csv(folder / "scores.csv", index=False)
    pd.DataFrame({f"{s} | {o}": v for (s, o), v in daily.items()}, index=panel.dates).to_csv(
        folder / "daily_spreads.csv")
    pd.set_option("display.width", 220)
    print(table.round(4).to_string(index=False))
    figure(table)


def figure(table):
    outcomes = list(dict.fromkeys(table.outcome))
    names = list(dict.fromkeys(table.signal))[::-1]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6), sharey=True, layout="constrained")
    for ax, outcome in zip(axes, outcomes):
        for offset, (period, color) in enumerate((("before 2024", plots.BLUE), ("2024 on", plots.ORANGE))):
            part = table[(table.outcome == outcome) & (table.period == period)].set_index("signal").loc[names]
            y = np.arange(len(names)) + (0.16 if offset == 0 else -0.16)
            ax.errorbar(part.bounce_score, y, xerr=[part.bounce_score - part.low, part.high - part.bounce_score],
                        fmt="o", color=color, capsize=0, elinewidth=2, label=period)
        ax.axvline(0, color=plots.INK_SOFT, lw=1)
        ax.set_yticks(np.arange(len(names)), names)
        ax.set_title(outcome)
        ax.set_xlabel("Bounce score (right of zero = reverses)")
    axes[2].legend(loc="upper right")
    fig.suptitle("Does the move reverse? Rank correlation of minus-the-signal with the next return, 95% intervals",
                 x=0.01, ha="left", fontweight="bold")
    plots.save(fig, STUDY, "1_bounce_scores.png")


if __name__ == "__main__":
    main()
