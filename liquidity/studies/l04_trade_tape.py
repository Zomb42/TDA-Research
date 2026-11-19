"""Recover individual prints for the refill study and reconcile the replayed tape by second."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import tempfile

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from l01_snapshots import CACHE, RESULTS, SOURCE, START, STOP

TAPE = CACHE / "individual_trades.parquet"
OUT = RESULTS.parent / "refill"


def read_hour(rec):
    path = SOURCE / "kalshi_perp" / (rec["hour"] + ".jsonl.gz")
    proc = subprocess.run(["rg", "-z", "--no-filename", "--no-heading", "--color=never", "-F",
                           '"type":"trade"', str(path)], capture_output=True)
    if proc.returncode not in (0, 1):
        raise RuntimeError(proc.stderr.decode())
    rows = []
    for line in proc.stdout.splitlines():
        row = json.loads(line)
        msg = row["message"]["msg"]
        assert msg["market_ticker"] == "KXBTCPERP" and msg["taker_side"] in ("ask", "bid")
        received_us = pd.Timestamp(row["received_at"]).value // 1000
        rows.append((received_us, msg["ts_ms"], int(Decimal(msg["price"])*10000),
                     int(Decimal(msg["count"])*100), int(msg["taker_side"] == "bid"), msg["is_block_trade"]))
    if len(rows) != rec["trades"]:
        raise ValueError(f"Trade count mismatch in {path}")
    tape = pd.DataFrame(rows, columns=["received_us","exchange_ms","price_tick","size_100","passive_side","block"])
    if len(rows):
        tape["t"] = tape.received_us//1_000_000 - int(START.timestamp())
        tape = tape[(tape.t >= 0) & (tape.t < (STOP-START).total_seconds())].copy()
    else:
        tape["t"] = pd.Series(dtype=int)
    if rec["seconds"]:
        snap = pq.read_table(CACHE/(rec["hour"]+".parquet"), columns=["end_utc","trade_count","signed_price_tick","executed_100"]).combine_chunks()
        start = int(snap["end_utc"][0].as_py().timestamp() - START.timestamp())-1
        times = (tape.t-start).to_numpy(dtype=int)
        counts = np.bincount(times, minlength=len(snap))
        assert np.array_equal(counts, snap["trade_count"].to_numpy())
        prices = snap["signed_price_tick"].chunk(0)
        idx = np.repeat(np.arange(len(snap)), np.diff(prices.offsets.to_numpy()))
        side = (prices.values.to_numpy() > 0).astype(int)
        qty = snap["executed_100"].chunk(0).values.to_numpy()
        from_levels = np.bincount(2*idx+side, qty, minlength=2*len(snap))
        from_prints = np.bincount(2*times+tape.passive_side.to_numpy(dtype=int), tape.size_100.to_numpy(dtype=float), minlength=2*len(snap))
        assert np.array_equal(from_levels, from_prints)
    return tape


def main():
    manifest = json.loads((RESULTS/"snapshot_manifest.json").read_text())
    with ThreadPoolExecutor(max_workers=5) as pool:
        hours = list(pool.map(read_hour, manifest["hours"]))
    tape = pd.concat([h for h in hours if len(h)], ignore_index=True)
    assert tape.received_us.is_monotonic_increasing
    with tempfile.TemporaryDirectory(dir=CACHE) as temp:
        dest = Path(temp)/TAPE.name
        tape.to_parquet(dest, index=False, compression="zstd")
        dest.replace(TAPE)
    print(f"Reconciled {len(tape):,} prints with all study seconds. Block prints: {tape.block.sum()}.")
    print(((tape.received_us/1000 - tape.exchange_ms)/1000).quantile([0,.1,.5,.9,.99,1]))


if __name__ == "__main__":
    main()
