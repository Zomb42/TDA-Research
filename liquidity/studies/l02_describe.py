"""Describe the size and coordinate stability of the reconstructed books."""
import json
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/tda-btc-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from l01_snapshots import CACHE, RESULTS, START

SIDES = ("bid", "ask")
LAGS = (1, 10, 60, 600, 3600)
GRID_CACHE = CACHE / "midpoint_grid.npz"


def book_series(manifest):
    grids, good, midpoints, deltas = [], [], [], []
    sampled = {}
    count = 0
    for rec in manifest["hours"]:
        if not rec["seconds"]:
            continue
        table = pq.read_table(CACHE / (rec["hour"] + ".parquet"), columns=[
            "end_utc", "best_bid_tick", "best_ask_tick", "complete", "crossed_or_locked",
            "signed_price_tick", "size_100", "delta_count"]).combine_chunks()
        def scalar(key):
            return table[key].to_numpy()
        clock = scalar("end_utc").astype("datetime64[s]").astype("int64")
        if not np.array_equal(clock, int(START.timestamp()) + count + 1 + np.arange(len(clock))):
            raise ValueError("Seconds are missing or out of order")
        valid = scalar("complete") & ~scalar("crossed_or_locked")
        mid2 = scalar("best_bid_tick") + scalar("best_ask_tick")
        column = table["signed_price_tick"].chunk(0)
        offsets = column.offsets.to_numpy()
        tick = column.values.to_numpy()
        size = table["size_100"].chunk(0).values.to_numpy()
        row = np.repeat(np.arange(len(clock)), np.diff(offsets))
        side = (tick > 0).astype(int)
        distance2 = np.abs(2*np.abs(tick) - mid2[row])
        dist_bin = distance2 * 10000 // np.maximum(1, mid2[row])
        weights = np.abs(tick) * size / 1_000_000  # USD displayed, valued at each limit price
        keep = (dist_bin < 25) & valid[row] & (size > 0)
        cell = (row[keep]*2 + side[keep])*25 + dist_bin[keep]
        grid = np.bincount(cell, weights[keep], minlength=len(clock)*50).reshape(-1, 2, 25)
        grids.append(grid)
        good.append(valid)
        midpoints.append(mid2)
        deltas.append(scalar("delta_count"))
        # Keep only the native ladders used by the equal-width coordinate comparison.
        for i in np.flatnonzero(valid & np.isin(clock % 60, (0, 1, 10))):
            pieces = []
            sl = slice(offsets[i], offsets[i+1])
            for s in (0, 1):
                take = (side[sl] == s) & (size[sl] > 0) & (distance2[sl] < 500)
                pieces.append((distance2[sl][take], weights[sl][take]))
            sampled[count+i] = pieces
        count += len(clock)
    return (np.concatenate(grids), np.concatenate(good), np.concatenate(midpoints),
            np.concatenate(deltas), sampled)


def cosine(start, target_bins, weights):
    # Target bins can move outside the initial window. Include their mass in the norm.
    if not len(weights):
        return np.nan
    lo = int(min(0, target_bins.min()))
    future = np.bincount(target_bins - lo, weights, minlength=25-lo)
    denom = np.linalg.norm(start) * np.linalg.norm(future)
    return np.dot(start, future[-lo:25-lo]) / denom if denom else np.nan


def coordinate_pairs(valid, mid2, sampled):
    missing = np.r_[0, np.cumsum(~valid)]
    rows, prior_day = [], []
    for t in range(59, len(valid), 60):
        if not valid[t]:
            continue
        for lag in LAGS:
            u = t + lag
            if u >= len(valid) or missing[u+1] != missing[t]:
                continue
            shift = mid2[u] - mid2[t]
            for s, direction in enumerate((-1, 1)):
                start_dist, start_w = sampled[t][s]
                end_dist, end_w = sampled[u][s]
                if not len(start_w) or not len(end_w):
                    continue
                start = np.bincount(start_dist//20, start_w, minlength=25)
                moving = cosine(start, end_dist//20, end_w)
                fixed = cosine(start, (end_dist + direction*shift)//20, end_w)
                translated = cosine(start, (start_dist + direction*shift)//20, start_w)
                if lag == 60 and t-86400 in sampled:
                    prev_dist, prev_w = sampled[t-86400][s]
                    if len(prev_w):
                        old = np.bincount(prev_dist//20, prev_w, minlength=25)
                        prior_day.append((SIDES[s], moving, cosine(old, end_dist//20, end_w)))
                rows.append((t, lag, SIDES[s], abs(shift)/2, moving, fixed, translated))
    pairs = pd.DataFrame(rows, columns=["t", "lag_s", "side", "move_usd_btc", "moving", "fixed", "translated_fixed"])
    paired = pd.DataFrame(prior_day, columns=["side", "current", "prior_day"])
    paired["paired_difference"] = paired.current - paired.prior_day
    return pairs, paired.groupby("side", as_index=False).agg(
        pairs=("current", "size"), current=("current", "median"), prior_day=("prior_day", "median"),
        paired_difference=("paired_difference", "median"))


def plot(profile, comparison):
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(10.5, 4.0), layout="constrained")
    colors = ("#176886", "#a84a24")
    for side, color in zip(SIDES, colors):
        p = profile.query("side == @side and sample == 'evaluation'")
        ax.plot(p["bin"]+.5, p["median_usd"]/1e6, color=color, marker=".", label=side.title())
        c = comparison.query("side == @side and sample == 'evaluation' and movement == 'all'")
        bx.plot(c.lag_s, c.moving, color=color, label=f"{side.title()}, moving")
        bx.plot(c.lag_s, c.fixed, color=color, linestyle="--", label=f"{side.title()}, fixed")
    ax.set(xlabel="Distance from midpoint (basis points)", ylabel="Median displayed depth ($ millions)",
           title="A. Where depth is displayed")
    bx.set(xscale="log", xticks=LAGS, xticklabels=["1 s", "10 s", "1 min", "10 min", "1 h"], ylim=(-.04, 1.04),
           xlabel="Time between observations", ylabel="Median profile similarity", title="B. Does the shape move with price?")
    bx.minorticks_off()
    for axis in (ax, bx):
        axis.spines[["right", "top"]].set_visible(False)
        axis.legend(frameon=False, fontsize=9)
        axis.grid(axis="y", alpha=.15)
    fig.savefig(RESULTS / "depth_and_frames.png", dpi=180)
    plt.close(fig)


def main():
    manifest = json.loads((RESULTS / "snapshot_manifest.json").read_text())
    grid, valid, mid2, deltas, sampled = book_series(manifest)
    np.savez_compressed(GRID_CACHE, grid=grid, valid=valid, mid2=mid2, deltas=deltas)
    pairs, prior_day = coordinate_pairs(valid, mid2, sampled)
    prior_day.to_csv(RESULTS / "previous_day_control.csv", index=False)
    pairs["sample"] = np.where(pairs.t+1+pairs.lag_s < 86400, "calibration",
                               np.where(pairs.t+1 >= 86400, "evaluation", "boundary"))
    parts = []
    for movement, mask in [("all", pairs.move_usd_btc >= 0), ("at_least_one_bin", pairs.move_usd_btc >= 10)]:
        sub = pairs[mask & pairs["sample"].ne("boundary")]
        summary = sub.groupby(["sample", "lag_s", "side"], as_index=False).agg(
            pairs=("t", "size"), moving=("moving", "median"), fixed=("fixed", "median"),
            paired_difference=("moving", lambda x: (x - sub.loc[x.index, "fixed"]).median()),
            translated_fixed=("translated_fixed", "median"))
        parts.append(summary.assign(movement=movement))
    comparison = pd.concat(parts, ignore_index=True)
    comparison.to_csv(RESULTS / "coordinate_similarity.csv", index=False)
    profiles = []
    for label, use in [("calibration", np.arange(len(grid))+1 < 86400),
                       ("evaluation", np.arange(len(grid))+1 >= 86400)]:
        for s, side in enumerate(SIDES):
            q = np.quantile(grid[valid & use, s], [.25, .5, .75], axis=0)
            for b in range(25):
                profiles.append((label, side, b, *q[:, b]))
    profile = pd.DataFrame(profiles, columns=["sample", "side", "bin", "q25_usd", "median_usd", "q75_usd"])
    profile.to_csv(RESULTS / "depth_profile.csv", index=False)
    plot(profile, comparison)


if __name__ == "__main__":
    main()
