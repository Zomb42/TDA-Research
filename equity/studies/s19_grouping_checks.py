"""s19. Does the TDA grouping itself matter, and do the two grouping settings
that were never varied change the result?

Strategy: study 11's main version (signal at 3:40 pm, bought or sold at 3:50 pm,
sold at the next open; before costs). Only the peer groups change. SPY beta,
position weights and the signal are exactly the current version's.

Part 1. Random groups (is it the grouping, or just having small groups?).
  On each rebuild date keep TDA's set of grouped stocks and its group sizes,
  and shuffle which stock sits in which group:
    anywhere       across all grouped stocks
    within sector  only among grouped stocks of the same sector, so every group
                   keeps its sector mix (a TDA "refiners" group becomes a group
                   of random energy stocks)
  Same stocks, same number and size of groups, same hedging; only "who is
  paired with whom" differs. Repeated 300 times each to see the range that
  arbitrary groups of this shape produce.

Part 2. Grouping settings never varied before.
  Correlation window 63 / 126 / 189 / 252 days  x  groups rebuilt every
  1 / 5 / 21 / 63 trading days. (504 days is not possible without changing the
  stock-eligibility rule, which needs 272 days of history.) The current
  setting is 252 days, rebuilt every 5. Because the book goes fully in and out
  every day, rebuild frequency does not change how much it trades.

    conda run -n tda python equity/studies/s19_grouping_checks.py
"""
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import s11_late_day_characterize as s11
from tdaeq import data, evaluate, plots, signals
from tdaeq.data import MIN_HISTORY

STUDY = "s19_grouping_checks"
WAY = "3:50 pm to next open"
SHUFFLES = 300
WINDOWS = (63, 126, 189, 252)
REFITS = (1, 5, 21, 63)
CURRENT = (252, 5)


def shuffled_groups(state, refit, within_sector, rng):
    """TDA labels with stocks shuffled between groups on every rebuild date."""
    group = state.group.copy()
    days = group.shape[0]
    for start in range(MIN_HISTORY, days, refit):
        grouped = np.flatnonzero(state.group[start] >= 0)
        labels = state.group[start, grouped]
        new = labels.copy()
        if within_sector:
            for s in np.unique(state.sector[grouped]):
                where = np.flatnonzero(state.sector[grouped] == s)
                new[where] = labels[where][rng.permutation(len(where))]
        else:
            new = labels[rng.permutation(len(labels))]
        group[start:start + refit, grouped] = new
    return group


def book(panel, state, group, signal, sigma, outcome, days):
    held = s11.holdings(panel, replace(state, group=group), signal, sigma, "TDA peer groups", days)
    return s11.daily_return(held, outcome, days)


def periods(r, dates):
    return {"all": evaluate.sharpe(r), "before_2024": evaluate.sharpe(r[dates < data.SPLIT]),
            "2024_on": evaluate.sharpe(r[dates >= data.SPLIT])}


def group_summary(group, days):
    rows = group[days]
    grouped = (rows >= 0).sum(axis=1)
    count = np.array([len(np.unique(r[r >= 0])) for r in rows])
    eligible = (rows != signals.NOT_USED).sum(axis=1)
    return {"median_groups": float(np.median(count)), "median_share_grouped": float(np.median(grouped / eligible))}


def membership_change(group, refit):
    """Share of same-group pairs on one rebuild date that are no longer together on the next."""
    changes = []
    starts = list(range(MIN_HISTORY, group.shape[0], refit))
    for a, b in zip(starts[:-1], starts[1:]):
        ga, gb = group[a], group[b]
        ok = (ga >= 0)
        same_a = (ga[:, None] == ga[None, :]) & ok[:, None] & ok[None, :]
        np.fill_diagonal(same_a, False)
        if same_a.sum() == 0:
            continue
        same_b = (gb[:, None] == gb[None, :]) & (gb[:, None] >= 0)
        changes.append(1 - (same_a & same_b).sum() / same_a.sum())
    return float(np.mean(changes)) if changes else np.nan


def main():
    np.seterr(invalid="ignore", divide="ignore")
    panel = data.load_panel()
    base = signals.build_state(panel, plain_groups=None)
    _, outcome, signal, sigma = s11.tables(panel, base)
    outcome, signal = outcome[WAY], signal[20]
    ready = np.isfinite(signal).sum(axis=1) >= 50
    days = np.flatnonzero(ready & (base.group != signals.NOT_USED).any(axis=1))
    days = days[days < len(panel.dates) - 1]
    dates = panel.dates[days]
    out = plots.folder(STUDY)
    pd.set_option("display.width", 250)

    current = book(panel, base, base.group, signal, sigma, outcome, days)
    sector_r = s11.daily_return(s11.holdings(panel, base, signal, sigma, "Sectors", days), outcome, days)
    market_r = s11.daily_return(s11.holdings(panel, base, signal, sigma, "Market only, same stocks", days), outcome, days)
    reference = {"TDA peer groups (current)": current, "Sectors": sector_r, "Market only, same stocks": market_r}
    print({k: round(evaluate.sharpe(v), 2) for k, v in reference.items()})

    # Part 1: random groups of the same shape
    rng = np.random.default_rng(0)
    rows, sample_daily = [], {}
    for kind, within in (("anywhere", False), ("within sector", True)):
        for i in range(SHUFFLES):
            r = book(panel, base, shuffled_groups(base, 5, within, rng), signal, sigma, outcome, days)
            rows.append({"shuffle": kind, "seed": i, **periods(r, dates)})
            if i == 0:
                sample_daily[kind] = r
        part = pd.DataFrame([x for x in rows if x["shuffle"] == kind])
        print(f"{kind}: median {part['all'].median():.2f}, 95th pct {part['all'].quantile(0.95):.2f}, "
              f"max {part['all'].max():.2f}, share >= TDA {np.mean(part['all'] >= evaluate.sharpe(current)):.3f}")
    shuffles = pd.DataFrame(rows)
    shuffles.to_csv(out / "shuffles.csv", index=False)
    ref_rows = [{"book": k, **periods(v, dates), **dict(zip(("ci_low", "ci_high"), evaluate.sharpe_ci(v)[1:]))}
                for k, v in reference.items()]
    pd.DataFrame(ref_rows).to_csv(out / "reference_books.csv", index=False)

    # Part 2: window x rebuild frequency
    grid = []
    for window in WINDOWS:
        for refit in REFITS:
            state = base if (window, refit) == CURRENT else signals.build_state(
                panel, window=window, refit=refit, plain_groups=None)
            group = np.where(base.group == signals.NOT_USED, signals.NOT_USED, state.group)   # same eligible stocks
            r = current if (window, refit) == CURRENT else book(panel, base, group, signal, sigma, outcome, days)
            diff, low, high = evaluate.sharpe_difference_ci(r, current)
            ci = evaluate.sharpe_ci(r)
            grid.append({"window_days": window, "rebuild_every_days": refit, **periods(r, dates),
                         "ci_low": ci[1], "ci_high": ci[2], "minus_current": diff, "diff_low": low, "diff_high": high,
                         "mean_bps": r.mean() * 1e4, "corr_with_current": np.corrcoef(r, current)[0, 1],
                         **group_summary(group, days), "pairs_split_at_next_rebuild": membership_change(state.group, refit)})
            print(grid[-1])
    grid = pd.DataFrame(grid)
    grid.to_csv(out / "settings_grid.csv", index=False)
    print(grid.round(2).to_string(index=False))

    # honest check: rank the 16 settings on before-2024, look at 2024 on
    print("rank correlation of before-2024 and 2024-on Sharpe across settings:",
          round(grid[["before_2024", "2024_on"]].corr(method="spearman").iloc[0, 1], 2))
    best = grid.sort_values("before_2024").iloc[-1]
    print(f"best before 2024: window {best.window_days}, rebuild {best.rebuild_every_days} "
          f"({best.before_2024:.2f}); its 2024-on Sharpe {best['2024_on']:.2f}")

    figure(shuffles, reference, grid)


def figure(shuffles, reference, grid):
    fig, (left, right) = plt.subplots(1, 2, figsize=(13.5, 4.6), layout="constrained",
                                      gridspec_kw={"width_ratios": [1.4, 1]})
    bins = np.linspace(min(shuffles["all"].min(), 0.6), 2.4, 40)
    for kind, color in (("anywhere", plots.GRAY), ("within sector", plots.AQUA)):
        left.hist(shuffles.loc[shuffles.shuffle == kind, "all"], bins=bins, color=color, alpha=0.75,
                  label=f"Random groups, shuffled {kind} ({SHUFFLES})")
    for (name, r), color in zip(reference.items(), (plots.BLUE, plots.ORANGE, plots.YELLOW)):
        s = evaluate.sharpe(r)
        left.axvline(s, color=color, lw=2.2)
        left.text(s, left.get_ylim()[1] * 0.97, f" {name}\n {s:.2f}", color=color, fontsize=8.5, va="top",
                  ha="right" if name.startswith("TDA") else "left")
    left.set_xlabel("Sharpe before costs, 2017-2026")
    left.set_ylabel("Number of shuffles")
    left.set_title("Same stocks, same group sizes, random members")
    left.legend(loc="upper left", bbox_to_anchor=(0, 0.8))

    table = grid.pivot(index="window_days", columns="rebuild_every_days", values="all").loc[list(WINDOWS)[::-1]]
    image = right.imshow(table.to_numpy(), cmap="Blues", vmin=1.0, vmax=2.6, aspect="auto")
    for i, w in enumerate(table.index):
        for j, f in enumerate(table.columns):
            v = table.loc[w, f]
            mark = " (current)" if (w, f) == CURRENT else ""
            right.text(j, i, f"{v:.2f}{mark}", ha="center", va="center", fontsize=9,
                       color="white" if v > 2.0 else plots.INK)
    right.set_xticks(range(len(table.columns)), [f"every {f}" for f in table.columns])
    right.set_yticks(range(len(table.index)), [f"{w} days" for w in table.index])
    right.set_xlabel("Groups rebuilt (trading days)")
    right.set_ylabel("Correlation window")
    right.grid(False)
    right.set_title("Grouping settings: Sharpe before costs, 2017-2026")
    fig.colorbar(image, ax=right, shrink=0.8)
    fig.suptitle("Late-day reversal: does the TDA grouping matter, and do its settings?",
                 x=0.01, ha="left", fontweight="bold")
    plots.save(fig, STUDY, "1_grouping_checks.png")


if __name__ == "__main__":
    main()
