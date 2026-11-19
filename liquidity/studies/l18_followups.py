"""Follow-up checks from the November 19, 2026 discussion. Results go to results/followups/.

1. microprice_splits.csv  Are Reeb-graph splits an artifact of the plain midpoint? The per-second
   1-bp depth grid is rebuilt twice from the same books: distance measured from the plain midpoint
   (best bid + best ask) / 2, and from the microprice
   (bid x ask size + ask x bid size) / (bid size + ask size), which leans toward the thinner side
   and moves less when a small order joins the best quote. Same rule for both: each grid's own
   November 11 percentile cutoffs (75 / 90 / 97.5), same one-second linking, scored Nov 12-17.
2. large_trade_path.csv   Price path after Astra's 1,791 isolated large trades and their matched quiet
   seconds, in the large trade's direction, for Kalshi and Binance futures.
3. trade_distance.csv     Where trades fill: volume by distance from the pre-trade midpoint.
4. price_gap.json         Kalshi midpoint minus Binance price, in dollars.
"""
import json

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from l01_snapshots import CACHE, RESULTS
from l03_band_age import WEIGHTS
from l06_book_breaks import countbits, transition_arrays

OUT = RESULTS.parent / "followups"
DAY = 86400
S_NS = 1794355200 * 10**9


def grids():
    """Per-second 1-bp depth grids measured from the midpoint and from the microprice."""
    manifest = json.loads((RESULTS / "snapshot_manifest.json").read_text())
    out = {"midpoint": [], "microprice": []}
    valid_all, ref_all = [], {"midpoint": [], "microprice": []}
    for rec in manifest["hours"]:
        if not rec["seconds"]:
            continue
        t = pq.read_table(CACHE / (rec["hour"] + ".parquet"), columns=[
            "best_bid_tick", "best_ask_tick", "complete", "crossed_or_locked", "signed_price_tick", "size_100"]).combine_chunks()
        bb, ba = t["best_bid_tick"].to_numpy().astype(float), t["best_ask_tick"].to_numpy().astype(float)
        valid = t["complete"].to_numpy() & ~t["crossed_or_locked"].to_numpy()
        col = t["signed_price_tick"].chunk(0)
        tick = col.values.to_numpy()
        size = t["size_100"].chunk(0).values.to_numpy().astype(float)
        row = np.repeat(np.arange(len(bb)), np.diff(col.offsets.to_numpy()))
        bid_size = np.bincount(row, size * (tick == -bb[row]), minlength=len(bb))
        ask_size = np.bincount(row, size * (tick == ba[row]), minlength=len(bb))
        mid = (bb + ba) / 2
        micro = np.where(bid_size + ask_size > 0, (bb * ask_size + ba * bid_size) / np.maximum(bid_size + ask_size, 1), mid)
        valid &= (bid_size > 0) & (ask_size > 0)
        side = (tick > 0).astype(int)
        price = np.abs(tick).astype(float)
        usd = price * size / 1e6
        for name, ref in (("midpoint", mid), ("microprice", micro)):
            r = ref[row]
            dist = np.where(side == 1, price - r, r - price) / np.maximum(r, 1) * 1e4
            b = np.floor(dist).astype(int)
            keep = (b >= 0) & (b < 25) & (size > 0) & valid[row]
            cell = (row[keep] * 2 + side[keep]) * 25 + b[keep]
            out[name].append(np.bincount(cell, usd[keep], minlength=len(bb) * 50).reshape(-1, 2, 25))
            ref_all[name].append(ref)
        valid_all.append(valid)
    return {k: np.concatenate(v) for k, v in out.items()}, np.concatenate(valid_all), {k: np.concatenate(v) for k, v in ref_all.items()}


def microprice_splits():
    g, valid, refs = grids()
    n = len(valid)
    pair_ok = valid[1:] & valid[:-1] & (np.arange(1, n) >= DAY)
    rows = []
    for name, grid in g.items():
        r = np.log(refs[name]) * 1e4
        step = np.abs(np.diff(r))[pair_ok]
        for q in (0.75, 0.90, 0.975):
            row = dict(reference=name, cutoff_quantile=q, reference_moved_share=float(np.mean(step > 1e-9)),
                       reference_median_abs_step_bp=float(np.median(step)))
            for s, side in enumerate(("bid", "ask")):
                cut = np.quantile(grid[:DAY, s][valid[:DAY]], q)
                masks = (((grid[:, s] >= cut) & valid[:, None]).astype(np.uint32) @ WEIGHTS).astype(np.int64)
                tr = transition_arrays(masks[:-1], masks[1:])[pair_ok]
                row[f"{side}_cutoff_usd"] = cut
                row[f"{side}_splits"] = int(countbits(tr[:, 3].astype(np.int64)).sum())
                row[f"{side}_deaths"] = int(countbits(tr[:, 2].astype(np.int64)).sum())
                row[f"{side}_births"] = int(tr[:, 4].sum())
            rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "microprice_splits.csv", index=False)
    return out


def large_trade_path():
    pairs = pd.read_csv(RESULTS.parent / "refill" / "matched_seconds.csv")
    z = np.load(CACHE / "midpoint_grid.npz")
    mid2 = z["mid2"].astype(float)
    lm = np.log(np.where(mid2 > 0, mid2 / 2, np.nan)) * 1e4
    fut = (np.log(np.load(CACHE / "binance_100ms.npz")["fut"]) * 1e4)[9::10][:len(lm)]
    sign = np.where(pairs.side.to_numpy() == 1, 1, -1)   # passive ask hit => taker bought => +1
    rows = []
    for arm in ("event", "calm"):
        t = pairs[arm].to_numpy()
        for h in (-10, -1, 0, 1, 5, 10, 30, 60, 300):
            k = np.clip(t + h, 0, len(lm) - 1)
            rows.append(dict(arm=arm, seconds_after=h, kalshi_mean_bp=np.nanmean(sign * (lm[k] - lm[t - 1])),
                             kalshi_median_bp=np.nanmedian(sign * (lm[k] - lm[t - 1])),
                             binance_mean_bp=np.nanmean(sign * (fut[k] - fut[t - 1]))))
    t = pairs.event.to_numpy()
    binance_same_second = sign * (fut[t] - fut[t - 1])
    jump = sign * (lm[t] - lm[t - 1])
    for label, m in (("binance moved with the trade (> 0.5 bp)", binance_same_second > 0.5),
                     ("binance flat or against", binance_same_second <= 0)):
        for h in (0, 60, 300):
            k = np.clip(t + h, 0, len(lm) - 1)
            rows.append(dict(arm=label, seconds_after=h, kalshi_mean_bp=np.nanmean((sign * (lm[k] - lm[t - 1]))[m]),
                             events=int(m.sum())))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "large_trade_path.csv", index=False)
    return out, float(np.mean(binance_same_second > 0)), jump


def trade_distance():
    t = pd.read_parquet(CACHE / "trades_bbo.parquet")
    t = t[(t.book_valid == 1) & (t.received_ns >= S_NS + DAY * 10**9)]
    m0 = (t.bid_tick + t.ask_tick) / 2
    dist = np.abs(t.price_tick - m0) / m0 * 1e4
    bins = pd.cut(dist, [0, 0.5, 1, 2, 5, 10, 15, 20, 25, np.inf], right=False)
    w = t.size_100 / 100
    out = pd.DataFrame({"prints": bins.value_counts(sort=False), "contracts": w.groupby(bins, observed=False).sum()})
    out["volume_share"] = out.contracts / out.contracts.sum()
    out.index = out.index.astype(str)
    out.to_csv(OUT / "trade_distance.csv")
    order = ((t.exchange_ms.diff() != 0) | (t.taker_buy.diff() != 0)).cumsum()
    o = pd.DataFrame({"q": w, "d": dist}).groupby(order.to_numpy()).agg(q=("q", "sum"), d=("d", "max"))
    return out, dict(taker_orders=len(o), median_order_contracts=float(o.q.median()),
                     p999_order_contracts=float(o.q.quantile(0.999)), orders_reaching_20bp=int((o.d >= 20).sum()))


def price_gap():
    k = np.load(CACHE / "bbo_100ms.npz")
    b = np.load(CACHE / "binance_100ms.npz")
    ok = k["valid"] & (k["bid"] > 0)
    mid = (k["bid"] + k["ask"]) / 2.0
    out = {}
    for name in ("fut", "spot"):
        d = (mid - b[name])[ok]
        d = d[np.isfinite(d)]
        out[f"kalshi_minus_binance_{name}_usd"] = dict(median=float(np.median(d)), p5=float(np.percentile(d, 5)),
                                                       p95=float(np.percentile(d, 95)), share_within_100=float(np.mean(np.abs(d) < 100)))
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    splits = microprice_splits()
    path, share, _ = large_trade_path()
    dist, orders = trade_distance()
    summary = dict(price_gap=price_gap(), large_trades_binance_same_direction_share=share, **orders)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    pd.set_option("display.width", 220)
    for x in (splits, path, dist):
        print(x.round(3).to_string())
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
