"""Extract the once-per-second ticker messages, which carry Kalshi's reference (index) price.

Output: snapshots/reference_tape.parquet, one row per ticker message, with receipt time
(what the recorder knew, and when) and the exchange timestamps. Prices are in ticks of
$1/BTC (price x 10,000), the same units as the book snapshots.
"""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
import subprocess

import pandas as pd

from l01_snapshots import CACHE, SOURCE, START, STOP

TAPE = CACHE / "reference_tape.parquet"


def tick(text):
    return int(Decimal(text) * 10000)


def read_hour(path):
    cmd = f"gzip -dc '{path}' | grep -F '\"type\":\"ticker\"'"
    proc = subprocess.run(cmd, shell=True, capture_output=True)
    if proc.returncode not in (0, 1):
        raise RuntimeError(proc.stderr.decode())
    rows = []
    for line in proc.stdout.splitlines():
        row = json.loads(line)
        msg = row["message"]["msg"]
        assert msg["market_ticker"] == "KXBTCPERP"
        ref = msg["reference_price"]
        rows.append((row["received_unix_ns"] // 1000, msg["ts_ms"], tick(ref["price"]), ref["ts_ms"],
                     tick(msg["bid"]), tick(msg["ask"]), tick(msg["price"]),
                     tick(msg["settlement_mark_price"]["price"]), msg["funding_rate"]["rate"]))
    return rows


def main():
    paths = sorted((SOURCE / "kalshi_perp").glob("*.jsonl.gz"))
    with ThreadPoolExecutor(max_workers=6) as pool:
        hours = list(pool.map(read_hour, paths))
    tape = pd.DataFrame([r for h in hours for r in h],
                        columns=["received_us", "ticker_ms", "ref_tick", "ref_ms", "bid_tick", "ask_tick",
                                 "last_tick", "mark_tick", "funding_rate"])
    tape = tape.sort_values("received_us", kind="stable").reset_index(drop=True)
    # Integer second index matching the book grid: receipt second s belongs to row s.
    tape["t"] = tape.received_us // 1_000_000 - int(START.timestamp())
    tape = tape[(tape.t >= 0) & (tape.t < (STOP - START).total_seconds())]
    tape.to_parquet(TAPE, index=False, compression="zstd")
    lag = (tape.received_us / 1000 - tape.ref_ms) / 1000
    print(f"{len(tape):,} ticker messages; reference updates: {tape.ref_ms.nunique():,}")
    print("seconds from reference timestamp to receipt:", lag.quantile([.01, .5, .9, .99]).round(3).to_dict())


if __name__ == "__main__":
    main()
