"""Does connected-band age tell us which depth bins will still be high in one minute?"""
from functools import lru_cache
import json

import numpy as np
import pandas as pd

from l01_snapshots import RESULTS
from l02_describe import GRID_CACHE, SIDES, plt
from matplotlib.collections import LineCollection

QUANTILES = (.75, .90, .975)
AGE_NAMES = ("under 5 s", "5–29 s", "30 s or more")
DAY = 86400
# First two minutes of the first full evaluation day at noon UTC, chosen by clock.
EXAMPLE_START = DAY + 12*3600 - 1
WEIGHTS = 1 << np.arange(25, dtype=np.uint32)


@lru_cache(maxsize=8192)
def intervals(mask):
    runs = []
    while mask:
        low = (mask & -mask).bit_length()-1
        shifted = mask >> low
        length = (shifted ^ (shifted+1)).bit_length()-1
        runs.append((low, low + length))  # right endpoint excluded
        mask ^= ((1 << length)-1) << low
    return tuple(runs)


@lru_cache(maxsize=32768)
def links(old_mask, new_mask):
    old, new = intervals(old_mask), intervals(new_mask)
    return tuple((i, j) for i, (a, b) in enumerate(old) for j, (c, d) in enumerate(new)
                 if max(a, c) < min(b, d))


def branch_starts(prev_mask, mask, prev_starts, now):
    old, new = intervals(prev_mask), intervals(mask)
    parents = [[] for _ in new]
    children = [0]*len(old)
    for i, j in links(prev_mask, mask):
        parents[j].append(i)
        children[i] += 1
    return [prev_starts[p[0]] if len(p) == 1 and children[p[0]] == 1 else now for p in parents]


@lru_cache(maxsize=32768)
def reachable_next(reached, high_mask):
    # Follow all splits and merges forward, requiring overlap at each step.
    result = 0
    for lo, hi in intervals(high_mask):
        run = (1 << hi) - (1 << lo)
        if run & reached:
            result |= run
    return result


def fill_short_gaps(window, max_gap=4):
    # Only fill gaps bracketed by two actual highs inside the observed window.
    times = np.arange(len(window))[:, None]
    last = np.maximum.accumulate(np.where(window, times, -1000), axis=0)
    following = np.minimum.accumulate(np.where(window, times, 1000)[::-1], axis=0)[::-1]
    return following - last <= max_gap+1


def trace_path(start_mask, future_masks):
    reached = start_mask
    for mask in future_masks:
        reached = reachable_next(reached, int(mask))
        if not reached:
            break
    return reached


def band_cases(depth, valid, cut, decisions, side):
    high = (depth >= cut) & valid[:, None]
    masks = (high.astype(np.uint32) @ WEIGHTS).astype(np.int64)
    changes = np.flatnonzero(np.r_[True, masks[1:] != masks[:-1]])
    events = np.union1d(changes, decisions)
    score_here = np.zeros(len(depth), bool)
    score_here[decisions] = True
    prev_mask, born = 0, []
    starts = np.zeros(25, dtype=int)
    cases = []
    for t in events:
        mask = int(masks[t])
        if mask != prev_mask:
            born = branch_starts(prev_mask, mask, born, t)
            new_bins = mask & ~prev_mask
            for lo, hi in intervals(new_bins):
                starts[lo:hi] = t
            prev_mask = mask
        if score_here[t] and mask:
            window = high[t:t+61]
            continuous = window.all(axis=0)
            bridged_masks = fill_short_gaps(window).astype(np.uint32) @ WEIGHTS
            for (lo, hi), birth in zip(intervals(mask), born):
                start_mask = (1 << hi) - (1 << lo)
                reached = trace_path(start_mask, masks[t+1:t+61])
                bridged = trace_path(start_mask, bridged_masks[1:])
                for b in range(lo, hi):
                    cases.append((t, side, b, depth[t, b]/cut, t-starts[b], t-birth, high[t+60, b],
                                  continuous[b], bool(reached & (1 << b)), bool(bridged & (1 << b))))
    return pd.DataFrame(cases, columns=["t", "side", "bin", "size_multiple", "bin_age_s", "branch_age_s", "outcome", "continuous", "connected", "bridged"])


def score_tables(cases, distance_width=5):
    t = cases.t.to_numpy()
    y = cases.outcome.to_numpy(dtype=float)
    side = cases.side.to_numpy()
    distance = cases["bin"].to_numpy() // distance_width
    n_dist = 25 // distance_width
    size = np.searchsorted([1.5, 2], cases.size_multiple, side="right")
    bin_age = np.searchsorted([5, 30], cases.bin_age_s, side="right")
    branch_age = np.searchsorted([5, 30], cases.branch_age_s, side="right")
    base = (side*n_dist + distance)*3 + size
    n_base = 2*n_dist*3
    bin_key = base*3 + bin_age
    branch_key = bin_key*3 + branch_age
    day = (t+1) // DAY
    parts = []
    for d in np.unique(day[day > 0]):
        train = t+1+60 <= d*DAY
        test = day == d
        pred = np.array([y[train].mean()])
        losses = {}
        for label, key, width, child_count in [
                ("size_distance", base, n_base, n_base), ("bin_age", bin_key, n_base*3, 3),
                ("branch_age", branch_key, n_base*9, 3)]:
            n = np.bincount(key[train], minlength=width)
            hits = np.bincount(key[train], y[train], minlength=width)
            pred = (hits + 20*np.repeat(pred, child_count))/(n + 20)
            losses[label] = (pred[key[test]] - y[test])**2
        cols = ["t", "side", "bin", "bin_age_s", "branch_age_s", "outcome", "continuous", "connected", "bridged", "active"]
        parts.append(cases.loc[test, cols].assign(day=d, hour=(t[test]+1)//3600, **losses))
    return pd.concat(parts, ignore_index=True)


def score_summary(scored):
    summaries, daily = [], []
    for sample, frame in [("all", scored), ("recent_updates", scored[scored.active])]:
        for label, new, old in [("bin_age", "bin_age", "size_distance"),
                                ("added_branch_age", "branch_age", "bin_age")]:
            rng = np.random.default_rng(20261118)
            frame = frame.assign(difference=frame[new]-frame[old])
            # Paired differences and numbers of eligible bin observations travel together.
            blocks = frame.groupby(["day", "hour"]).difference.agg(["sum", "size"])
            sums = np.zeros(2000)
            counts = np.zeros(2000)
            for d, group in blocks.groupby(level="day"):
                group = group.droplevel("day").reindex(range(24*d, 24*(d+1)), fill_value=0)
                n_hours = len(group)
                draw = rng.integers(n_hours, size=(2000, n_hours))
                sums += group["sum"].to_numpy()[draw].sum(axis=1)
                counts += group["size"].to_numpy()[draw].sum(axis=1)
                day_frame = frame[frame.day == d]
                daily.append((sample, label, int(d)+11, len(day_frame), day_frame[old].mean(),
                              day_frame[new].mean(), day_frame.difference.mean()))
            lo, hi = np.quantile(sums/counts, [.025, .975])
            summaries.append((sample, label, len(frame), frame.t.nunique(), len(blocks), frame[old].mean(),
                              frame[new].mean(), frame.difference.mean(), lo, hi))
    names = ["sample", "comparison", "cases", "minutes", "hours", "baseline_brier", "new_brier", "difference", "lo95", "hi95"]
    return pd.DataFrame(summaries, columns=names), pd.DataFrame(daily, columns=[
        "sample", "comparison", "november_day_utc", "cases", "baseline_brier", "new_brier", "difference"])


def graph_edges(field):
    masks = [sum(1 << int(b) for b in np.flatnonzero(row)) for row in field]
    lines = []
    counts = dict(births=0, deaths=0, splits=0, merges=0)
    for t, (prior, current) in enumerate(zip(masks, masks[1:])):
        a, b = intervals(prior), intervals(current)
        pairs = links(prior, current)
        out_degree = [0]*len(a)
        in_degree = [0]*len(b)
        for i, j in pairs:
            out_degree[i] += 1
            in_degree[j] += 1
            lines.append(((t, sum(a[i])/2), (t+1, sum(b[j])/2)))
        counts["births"] += in_degree.count(0)
        counts["deaths"] += out_degree.count(0)
        counts["splits"] += sum(x > 1 for x in out_degree)
        counts["merges"] += sum(x > 1 for x in in_degree)
    return lines, counts


def translation_control(profile, mid2, cut):
    # Freeze bin-center offsets in bps and dollar masses. Translate using observed midpoints.
    offsets = np.arange(25)+.5
    positions = mid2[:, None]*(1-offsets/10000)
    moving_bins = np.floor((mid2[:, None]-positions)*10000/mid2[:, None]).astype(int)
    fixed_bins = np.floor((mid2[0]-positions)*10000/mid2[0]).astype(int)
    controls = {}
    for name, bins in [("translated_moving", moving_bins), ("translated_fixed", fixed_bins)]:
        low, high = bins.min(), bins.max()
        mass = np.zeros((len(bins), high-low+1))
        np.add.at(mass, (np.arange(len(bins))[:, None], bins-low), np.broadcast_to(profile, bins.shape))
        _, controls[name] = graph_edges(mass >= cut)
    return controls


def figure(grid, cut, paths):
    example = grid[EXAMPLE_START:EXAMPLE_START+120, 0]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(11.5, 4.3), gridspec_kw={"width_ratios":[1.45, 1]},
                                 layout="constrained")
    img = ax.imshow((example/1e6).T, aspect="auto", origin="lower", interpolation="nearest",
                    extent=[-.5, 119.5, 0, 25], cmap="Blues", vmin=0, vmax=np.max(example)/1e6)
    lines, _ = graph_edges(example >= cut)
    ax.add_collection(LineCollection(lines, colors="#bd431f", linewidths=1.1))
    ax.set(xlabel="Seconds after 12:00 UTC on November 12", ylabel="Bid distance from midpoint (bp)",
           title="A. Connected bands of high displayed depth")
    fig.colorbar(img, ax=ax, location="bottom", shrink=.76, pad=.16, label="Displayed USD millions per bin")
    keys = ["high_again", "connected_with_4s_gaps", "connected_to_original", "high_every_second"]
    labels = ["High again", "Path allowing up to 4 s gaps", "Path at every second", "Same bin high every second"]
    counts = [int(paths[key]) for key in keys]
    rates = np.array(counts)*100 / paths["cases"]
    bars = bx.barh(np.arange(4), rates, height=.45, color=["#176886", "#598794", "#b35330", "#9c694e"])
    bx.set(yticks=np.arange(4), yticklabels=labels, xlim=(0, 43), ylim=(3.6,-.65),
           xlabel=f"Share of {paths['cases']:,} starting observations (%)", title="B. What survives one minute?")
    for bar, count, rate in zip(bars, counts, rates):
        digits = 1 if rate >= 1 else 3
        bx.text(rate+.5, bar.get_y()+bar.get_height()/2, f"{count:,}  ({rate:.{digits}f}%)",
                va="center", fontsize=8.5)
    bx.spines[["top", "right", "left"]].set_visible(False)
    bx.tick_params(axis="y", length=0)
    fig.savefig(RESULTS / "band_age.png", dpi=180)
    plt.close(fig)


def verify_tracker():
    assert intervals(0b110110) == ((1, 3), (4, 6))
    assert branch_starts(0b111, 0b101, [2], 7) == [7, 7]
    assert branch_starts(0b101, 0b111, [3, 5], 8) == [8]
    assert branch_starts(0b110, 0b011, [3], 8) == [3]
    assert branch_starts(0b100, 0b010, [3], 8) == [8]
    field = np.array([[1,1,1], [1,0,1], [1,1,1], [0,0,0], [0,1,0]], bool)
    assert graph_edges(field)[1] == dict(births=1, deaths=1, splits=1, merges=1)
    depth = np.zeros((160, 25))
    depth[:, :3] = 1
    depth[50, 1] = 0
    valid = np.ones(160, bool)
    cases = band_cases(depth, valid, .5, np.array([60]), 0)
    assert cases.branch_age_s.tolist() == [9, 9, 9] and cases.bin_age_s.tolist() == [60, 9, 60]
    assert cases.outcome.all()
    # A branch migrates away and back via an overlapping bin.
    depth[:] = 0
    depth[:, 2] = 1
    depth[61:120, 3] = 1
    depth[64:118, 2] = 0
    cases = band_cases(depth, valid, .5, np.array([60]), 0)
    assert cases.outcome.item() and cases.connected.item() and not cases.continuous.item()
    depth[80] = 0
    cases = band_cases(depth, valid, .5, np.array([60]), 0)
    assert cases.outcome.item() and not cases.connected.item() and cases.bridged.item()
    gap = np.array([0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0], bool)[:, None]
    assert np.flatnonzero(fill_short_gaps(gap)).tolist() == [1, 2, 3, 4, 5, 6, 12]


def main():
    verify_tracker()
    with np.load(GRID_CACHE) as data:
        grid, valid, mid2, deltas = (data[k] for k in ("grid", "valid", "mid2", "deltas"))
    t = np.arange(len(grid))
    calibration = (t+1 < DAY) & valid
    candidate = np.arange(59, len(grid)-60, 60)
    missing = np.r_[0, np.cumsum(~valid)]
    # 60-second history also eliminates left-censoring of the 30+ age group after gaps.
    decisions = candidate[missing[candidate+61] == missing[candidate-59]]
    activity = np.r_[0, np.cumsum(deltas)]
    cutoffs, scores, days, rates, controls, paths = [], [], [], [], [], []
    for q in QUANTILES:
        cuts = np.quantile(grid[calibration], q, axis=(0, 2))
        parts = []
        for s, side in enumerate(SIDES):
            cut = cuts[s]
            if cut <= 0:
                raise ValueError("High-depth threshold must be positive")
            cutoffs.append((q, side, cut))
            parts.append(band_cases(grid[:, s], valid, cut, decisions, s))
        cases = pd.concat(parts, ignore_index=True)
        cases["active"] = activity[cases.t+1] > activity[cases.t-59]
        scored = score_tables(cases)
        summary, daily = score_summary(scored)
        paths.append(dict(quantile=q, cases=len(scored), high_again=int(scored.outcome.sum()),
                          connected_to_original=int(scored.connected.sum()), high_every_second=int(scored.continuous.sum()),
                          connected_with_4s_gaps=int(scored.bridged.sum())))
        scores.append(summary.assign(quantile=q))
        days.append(daily.assign(quantile=q))
        for name, frame in [("all", scored), ("recent_updates", scored[scored.active])]:
            for feature in ("bin_age", "branch_age"):
                ages = np.searchsorted([5, 30], frame[feature+"_s"], side="right")
                grouped = frame.groupby(ages).agg(size=("outcome", "size"), mean=("outcome", "mean"),
                                                  continuous=("continuous", "mean"), connected=("connected", "mean"))
                rates.extend((q, name, feature, AGE_NAMES[i], int(row["size"]), row["mean"], row["continuous"], row["connected"])
                             for i, row in grouped.iterrows())
        span = slice(EXAMPLE_START, EXAMPLE_START+120)
        if not valid[span].all():
            raise ValueError("Chosen example crosses invalid data")
        checks = translation_control(grid[EXAMPLE_START, 0], mid2[span], cuts[0])
        checks["observed_moving"] = graph_edges(grid[span, 0] >= cuts[0])[1]
        controls.append(dict(quantile=q, **checks))
        if q == .90:
            primary_cut = cuts[0]
            fine_summary, _ = score_summary(score_tables(cases, distance_width=1))
            fine_summary.to_csv(RESULTS / "exact_distance_check.csv", index=False)
    rates = pd.DataFrame(rates, columns=["quantile", "sample", "feature", "age", "cases", "rate", "continuous_rate", "connected_rate"])
    rates.to_csv(RESULTS / "age_rates.csv", index=False)
    pd.DataFrame(paths).to_csv(RESULTS / "band_paths.csv", index=False)
    pd.DataFrame(cutoffs, columns=["quantile", "side", "threshold_usd"]).to_csv(RESULTS / "cutoffs.csv", index=False)
    pd.concat(scores).to_csv(RESULTS / "band_scores.csv", index=False)
    pd.concat(days).to_csv(RESULTS / "band_scores_daily.csv", index=False)
    (RESULTS / "graph_controls.json").write_text(json.dumps(controls, indent=2)+"\n")
    figure(grid, primary_cut, next(row for row in paths if row["quantile"] == .90))
    print(pd.concat(scores).query("sample == 'all'").to_string(index=False))


if __name__ == "__main__":
    main()
