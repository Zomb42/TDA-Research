"""s20. Does HDBSCAN's density step help, holding the smallest group at 2?

Background. The current groups use min_samples (k) = 1, which in scikit-learn
counts the stock itself, so every "core distance" is 0 and the groups are plain
single linkage (the H0 tree) with HDBSCAN's stability-based selection. With
k >= 2 each stock's distances are first stretched to at least the distance to
its (k-1)-th nearest other stock (mutual reachability), so stocks in sparse
areas cannot chain groups together. Study 16 only varied k together with the
smallest group size (2 -> k 1, 3 -> k 3, 5 -> k 5), so the two effects were
mixed up.

Design (fixed before results were seen, November 20, 2026):
  k = 1 (current), 2, 3, 5;  smallest group (min_cluster_size) = 2 throughout
  groups rebuilt every 1 or every 5 trading days;  252-day correlation window
Strategy exactly as study 19 (signal 3:40 pm, bought or sold at 3:50 pm, sold
at the next open, before costs). Only the peer groups change; eligible stocks,
SPY beta, weights and signal are the current version's. Each setting is compared
with k = 1 at the same rebuild frequency.

    conda run -n tda python equity/studies/s20_density_k.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

import s11_late_day_characterize as s11
from s19_grouping_checks import WAY, book, group_summary, membership_change, periods
from tdaeq import evaluate, plots, signals

STUDY = "s20_density_k"
KS = (1, 2, 3, 5)
REFITS = (1, 5)


def main():
    np.seterr(invalid="ignore", divide="ignore")
    panel = s11.data.load_panel()
    base = signals.build_state(panel, plain_groups=None)           # current: k = 1, rebuilt every 5
    _, outcome, signal, sigma = s11.tables(panel, base)
    outcome, signal = outcome[WAY], signal[20]
    ready = np.isfinite(signal).sum(axis=1) >= 50
    days = np.flatnonzero(ready & (base.group != signals.NOT_USED).any(axis=1))
    days = days[days < len(panel.dates) - 1]
    dates = panel.dates[days]
    out = plots.folder(STUDY)

    returns, rows = {}, []
    for refit in REFITS:
        for k in KS:
            state = base if (k, refit) == (1, 5) else signals.build_state(
                panel, refit=refit, plain_groups=None, min_cluster_size=2, min_samples=k)
            group = np.where(base.group == signals.NOT_USED, signals.NOT_USED, state.group)
            r = book(panel, base, group, signal, sigma, outcome, days)
            returns[k, refit] = r
            ci = evaluate.sharpe_ci(r)
            rows.append({"k": k, "rebuild_every_days": refit, **periods(r, dates), "ci_low": ci[1], "ci_high": ci[2],
                         "mean_bps": r.mean() * 1e4, **group_summary(group, days),
                         "pairs_split_at_next_rebuild": membership_change(state.group, refit)})
            print(rows[-1], flush=True)
    table = pd.DataFrame(rows)
    for i, row in table.iterrows():
        ref = returns[1, row.rebuild_every_days]
        r = returns[row.k, row.rebuild_every_days]
        diff, low, high = evaluate.sharpe_difference_ci(r, ref)
        table.loc[i, ["minus_k1_same_rebuild", "diff_low", "diff_high", "corr_with_k1"]] = [
            diff, low, high, np.corrcoef(r, ref)[0, 1]]
        d5, l5, h5 = evaluate.sharpe_difference_ci(r, returns[1, 5])
        table.loc[i, ["minus_current", "current_low", "current_high"]] = [d5, l5, h5]
    table.to_csv(out / "density_k.csv", index=False)
    pd.set_option("display.width", 250)
    print(table.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
