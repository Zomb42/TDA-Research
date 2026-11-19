"""Binance BTCUSDT last trade price every 100 ms, on the same clock as bbo_100ms.npz.

Input: Binance's free public daily aggregated-trade files (data.binance.vision), USDT perpetual
futures and spot, Nov 11-17 2026, checksums verified on download, in
market_data/datasets/btc_binance_aggtrades_2026-11-11_17/raw/.
Output: snapshots/binance_100ms.npz with `fut` and `spot` (last price at or before the end of
each 100 ms slot, carried forward) and per-slot signed traded BTC (`fut_flow`, `spot_flow`).

Times are Binance's matching-engine timestamps. Kalshi times are the recorder's receipt times,
about 13 ms after Kalshi's own stamps. The two clocks are independent, so lags of a few tens
of milliseconds are not meaningful; lags of hundreds of milliseconds are.
"""
import zipfile

import numpy as np
import pandas as pd

from l01_snapshots import CACHE, ROOT, START, STOP

RAW = ROOT / "market_data/datasets/btc_binance_aggtrades_2026-11-11_17/raw"
OUT = CACHE / "binance_100ms.npz"
SLOT_NS = 100_000_000


def load(kind, day):
    path = RAW / f"{kind}_BTCUSDT-aggTrades-2026-11-{day}.zip"
    with zipfile.ZipFile(path) as z:
        with z.open(z.namelist()[0]) as f:
            if kind == "futures_um":
                d = pd.read_csv(f, usecols=["price", "quantity", "transact_time", "is_buyer_maker"])
                ns = d.transact_time.to_numpy(np.int64) * 1_000_000
                maker = d.is_buyer_maker.astype(str).str.lower().eq("true").to_numpy()
            else:
                d = pd.read_csv(f, header=None, usecols=[1, 2, 5, 6], names=["price", "quantity", "us", "is_buyer_maker"])
                ns = d.us.to_numpy(np.int64) * 1000
                maker = d.is_buyer_maker.astype(str).str.lower().eq("true").to_numpy()
    sign = np.where(maker, -1.0, 1.0)  # buyer is maker => taker sold
    return ns, d.price.to_numpy(float), sign * d.quantity.to_numpy(float)


def grid(kind):
    n = int((STOP - START).total_seconds() * 10)
    start_ns = int(START.timestamp()) * 10**9
    last = np.full(n, np.nan)
    flow = np.zeros(n)
    for day in range(11, 18):
        ns, price, signed = load(kind, day)
        assert np.all(np.diff(ns) >= 0), f"{kind} {day} not time ordered"
        slot = (ns - start_ns) // SLOT_NS
        keep = (slot >= 0) & (slot < n)
        slot, price, signed = slot[keep], price[keep], signed[keep]
        # Last trade within each slot: the final index of each run of equal slots.
        end = np.r_[np.flatnonzero(np.diff(slot)), len(slot) - 1]
        last[slot[end]] = price[end]
        np.add.at(flow, slot, signed)
    return pd.Series(last).ffill().to_numpy(), flow


def main():
    fut, fut_flow = grid("futures_um")
    spot, spot_flow = grid("spot")
    np.savez(OUT, fut=fut, spot=spot, fut_flow=fut_flow, spot_flow=spot_flow)
    print(f"{len(fut):,} slots; futures slots with a trade: {np.mean(fut_flow != 0):.1%}; "
          f"spot: {np.mean(spot_flow != 0):.1%}")


if __name__ == "__main__":
    main()
