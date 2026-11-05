"""Historical depth baselines and a bounded real Kalshi depth-grid H0 pilot.

H0 uses a vertex-weighted four-neighbor grid graph, not cubical H1. Component
lifetimes measure log-depth contrast. Branch coordinates retain source context.
"""
import json
import os
from pathlib import Path
os.environ.setdefault("MPLCONFIGDIR", "/tmp/tda-btc-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.ndimage import label

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix("")


def h0_superlevel(field):
    """Elder-rule persistence on a 4-neighbor vertex grid; nonfinite = absent.

    At threshold z, vertices with value >= z and their connecting edges enter.
    Lexicographic ties choose an elder deterministically. Zero bars are omitted.
    """
    values = field.ravel()
    height, width = field.shape
    parent = np.arange(len(values))
    active = np.zeros(len(values), dtype=bool)
    birth = values.copy()
    peak = np.arange(len(values))
    bounds = np.array([[i//width, i//width, i%width, i%width] for i in range(len(values))])
    count = np.ones(len(values), dtype=int)
    bars = []

    def find(i):
        while i != parent[i]:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def record(root, death):
        bars.append(dict(birth=float(birth[root]), death=float(death) if death is not None else None,
                         lifetime=float(birth[root]-death) if death is not None else None,
                         peak_price_index=int(peak[root]//width), peak_time_index=int(peak[root]%width),
                         price_low_index=int(bounds[root,0]), price_high_index=int(bounds[root,1]),
                         time_first_index=int(bounds[root,2]), time_last_index=int(bounds[root,3]),
                         component_vertices_at_merge=int(count[root])))

    order = sorted(np.flatnonzero(np.isfinite(values)), key=lambda i: (-values[i], i))
    for i in order:
        active[i] = True
        y, x = divmod(i, width)
        neighbors = []
        if y: neighbors.append(i-width)
        if y+1 < height: neighbors.append(i+width)
        if x: neighbors.append(i-1)
        if x+1 < width: neighbors.append(i+1)
        for j in neighbors:
            if not active[j]:
                continue
            a, b = find(i), find(j)
            if a == b:
                continue
            elder, younger = sorted([a,b], key=lambda r: (-birth[r], peak[r]))
            if birth[younger] > values[i]:
                record(younger, values[i])
            parent[younger] = elder
            bounds[elder] = [min(bounds[elder,0], bounds[younger,0]), max(bounds[elder,1], bounds[younger,1]),
                             min(bounds[elder,2], bounds[younger,2]), max(bounds[elder,3], bounds[younger,3])]
            count[elder] += count[younger]
    for root in sorted({find(i) for i in order}):
        record(root, None)
    return bars


def verify_h0():
    controls = [np.array([[3.,1.,2.]]), np.array([[2.,2.],[2.,2.]]),
                np.array([[4.,0.,3.],[0.,2.,0.]]), np.array([[4.,np.nan,3.]])]
    for grid in controls:
        bars = h0_superlevel(grid)
        thresholds = np.unique(grid[np.isfinite(grid)])
        checks = sorted(set(thresholds.tolist() + [float(x)+0.01 for x in thresholds]))
        for threshold in checks:
            count = sum(b["birth"] >= threshold and (b["death"] is None or b["death"] < threshold) for b in bars)
            observed = label(np.isfinite(grid) & (grid >= threshold))[1]
            assert count == observed, (grid, threshold, count, observed)
    simple = h0_superlevel(controls[0])
    assert any(b["birth"] == 2 and b["death"] == 1 for b in simple)


def historical_baselines():
    depth = pd.read_parquet(ROOT / "market_data/datasets/btc_binance_2024_2026-10-27/depth_bands.parquet")
    table = depth.pivot(index="timestamp_utc", columns="percentage", values="notional")
    result = pd.DataFrame(index=table.index)
    for band in (1,2,3,4,5):
        result[f"bid_notional_within_{band}pct_usdt"] = table[-band]
        result[f"ask_notional_within_{band}pct_usdt"] = table[band]
        total = table[-band] + table[band]
        result[f"imbalance_{band}pct"] = (table[-band] - table[band]) / total.where(total > 0)
        for side, sign in [("bid", -1), ("ask", 1)]:
            # Fixed 1 percentage-point annulus. This does not locate orders within it.
            result[f"{side}_annulus_{band-1}_to_{band}pct_usdt"] = table[sign*band] - (table[sign*(band-1)] if band > 1 else 0)
    result.to_parquet(OUT / "binance_depth_baselines.parquet")
    dt = result.index.to_series().diff().dt.total_seconds()
    pd.DataFrame(dict(timestamp_utc=result.index, preceding_interval_seconds=dt.to_numpy(),
                      gap_over_60s=(dt > 60).to_numpy())).to_csv(OUT / "depth_observation_clock.csv", index=False)
    kalshi = pd.read_parquet(ROOT / "market_data/datasets/btc_kalshi_2026-06_2026-10-27/candles_1m.parquet")
    q = kalshi[["end_time_utc", "bid_close_usd_per_btc", "ask_close_usd_per_btc", "volume_btc", "open_interest_btc"]].copy()
    q["mid_close_usd_per_btc"] = (q.bid_close_usd_per_btc + q.ask_close_usd_per_btc)/2
    q["spread_close_bps"] = (q.ask_close_usd_per_btc-q.bid_close_usd_per_btc)/q.mid_close_usd_per_btc*10000
    q.to_parquet(OUT / "kalshi_quote_baselines_1m.parquet", index=False)
    return len(result), len(q)


def live_grid():
    source = ROOT / "market_data/samples/kalshi_btc_depth_2026-10-29"
    observations = [json.loads(s) for s in (source / "snapshots.jsonl").read_text().splitlines()]
    rows = [r for r in observations if "summary" in r]
    size = float(json.loads((source / "market.json").read_text())["market"]["contract_size"])
    anchor = rows[0]["summary"]["mid_usd_per_btc"]
    bin_usd = 25
    edges = np.arange(np.floor(anchor*.99/bin_usd)*bin_usd, np.ceil(anchor*1.01/bin_usd)*bin_usd+bin_usd, bin_usd)
    centers = (edges[:-1]+edges[1:])/2
    grid = np.zeros((len(centers), len(observations)))
    grid[:] = np.nan
    times = pd.to_datetime([r["received_at"] for r in observations], utc=True)
    baseline_rows = []
    for column, row in enumerate(observations):
        if "summary" not in row:
            continue
        book = row["payload"]["orderbook"]
        levels = book["bids"] + book["asks"]
        prices = np.array([float(p)/size for p,q in levels])
        notionals = np.array([float(p)*float(q) for p,q in levels])
        grid[:,column] = np.histogram(prices, bins=edges, weights=notionals)[0]
        # Outside observed extrema, mark unavailable, rather than infer zero depth.
        grid[(edges[:-1] < prices.min()) | (edges[1:] > prices.max()), column] = np.nan
        baseline_rows.append(dict(received_at=row["received_at"], **row["summary"]))
    # Break graph adjacency over receipt-time outages by inserting missing columns.
    gaps = np.flatnonzero(np.diff(times.asi8)/1e9 > 5) + 1
    if len(gaps):
        raise ValueError("Live sample contains gaps >5s: segment before grid topology")
    np.savez_compressed(OUT / "kalshi_grid.npz", depth_notional_usd=grid, price_edges_usd_per_btc=edges,
                        receipt_times_ns=times.asi8)
    pd.DataFrame(baseline_rows).to_csv(OUT / "kalshi_live_baselines.csv", index=False)
    field = np.log1p(grid)  # log(1 + displayed notional / 1 USD)
    bars = h0_superlevel(field)
    for bar in bars:
        peak_mid = observations[bar["peak_time_index"]]["summary"]["mid_usd_per_btc"]
        bar.update(peak_price_usd_per_btc=float(centers[bar["peak_price_index"]]),
                   peak_received_at=str(times[bar["peak_time_index"]]),
                   peak_distance_from_mid_bps=float((centers[bar["peak_price_index"]]/peak_mid-1)*10000),
                   source_price_width_usd=float((bar["price_high_index"]-bar["price_low_index"]+1)*bin_usd),
                   source_time_span_seconds=float((times[bar["time_last_index"]]-times[bar["time_first_index"]]).total_seconds()),
                   source_recency_at_window_end_seconds=float((times[-1]-times[bar["time_last_index"]]).total_seconds()),
                   source_latest_received_at=str(times[bar["time_last_index"]]))
    (OUT / "kalshi_grid_h0_branches.json").write_text(json.dumps(bars, indent=2) + "\n")
    # Check all observed thresholds against independently labeled grid components.
    for threshold in np.linspace(np.nanmin(field), np.nanmax(field), 31):
        expected = label(np.isfinite(field) & (field >= threshold))[1]
        observed = sum(b["birth"] >= threshold and (b["death"] is None or b["death"] < threshold) for b in bars)
        assert observed == expected
    fig, ax = plt.subplots(figsize=(12,6))
    seconds = (times.asi8-times.asi8[0])/1e9
    time_edges = np.r_[seconds[0]-(seconds[1]-seconds[0])/2, (seconds[:-1]+seconds[1:])/2,
                       seconds[-1]+(seconds[-1]-seconds[-2])/2]
    im = ax.pcolormesh(time_edges, edges, field, cmap="magma", shading="flat")
    ax.set_xlabel(f"Seconds since first receipt ({times[0]:%Y-%m-%d %H:%M:%S} UTC); columns show receipt-time spacing")
    ax.set_ylabel("Fixed USD/BTC price bins ($25 each)")
    ax.set_title("Kalshi BTC perp: two-minute REST depth sample\nDisplayed notional in each bin, log(1 + USD / 1 USD)")
    fig.colorbar(im, ax=ax, label="log-depth threshold units")
    fig.tight_layout()
    fig.savefig(OUT / "kalshi_depth_grid.png", dpi=150)
    plt.close(fig)
    finite = [b for b in bars if b["death"] is not None]
    return dict(successful_snapshots=len(rows), failed_snapshots=len(observations)-len(rows),
                grid_shape=list(grid.shape), finite_h0_branches=len(finite),
                essential_h0_branches=sum(b["death"] is None for b in bars),
                max_finite_h0_lifetime=max((b["lifetime"] for b in finite), default=0),
                independent_threshold_count_checks=31,
                interpretation="Observed-grid component contrast, not duration, order identity, or predictive evidence.")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    verify_h0()
    historical_rows, quote_rows = historical_baselines()
    live = live_grid()
    report = dict(binance_historical_feature_rows=historical_rows, kalshi_quote_feature_rows=quote_rows,
                  live_grid=live, synthetic_h0_controls_passed=True,
                  construction="Vertex superlevel H0, four neighbors; fixed absolute price bins, receipt-time columns.",
                  limitations=["Binance depth is cumulative at +/-1% to +/-5%, not a near-quote L2 ladder.",
                               "Kalshi candle bid/ask OHLC values do not reconstruct past intraminute spreads or depth.",
                               "Live REST polling misses changes between requests and has no event timestamps.",
                               "This small real grid establishes plumbing and feature meaning only."])
    (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
