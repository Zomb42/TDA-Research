"""Best quotes every 100 ms and at every trade, replayed from the validated journal.

Outputs (git-ignored, in snapshots/):
  bbo_100ms.npz      bid, ask, bid_size, ask_size, valid for every 100 ms of receipt time,
                     Nov 11 00:00 to Nov 17 23:50 UTC. Row k is the book at START + (k+1) x 100 ms.
  trades_bbo.parquet every trade with the best quotes just before it (updates from earlier exchange milliseconds).
Prices are ticks of $1/BTC, sizes are hundredths of a contract (as in the snapshots).
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

from l01_snapshots import CACHE, SOURCE, START, STOP

CPP = Path(__file__).with_name("replay_bbo.cpp")
BBO = CACHE / "bbo_100ms.npz"
TRADES = CACHE / "trades_bbo.parquet"
TRADE_FIELDS = ["received_ns", "exchange_ms", "price_tick", "size_100", "taker_buy",
                "bid_tick", "ask_tick", "book_valid", "block"]


def run_hour(path, binary):
    hour = datetime.strptime(path.name.split(".")[0], "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=timezone.utc)
    if hour < START:
        return None
    slots = max(0, min(36000, int((STOP - hour).total_seconds() * 10)))
    manifest = json.loads(path.with_suffix(".manifest.json").read_text())
    with tempfile.TemporaryDirectory() as temp:
        run = subprocess.run([str(binary), str(path), temp, str(int(hour.timestamp())), str(slots)],
                             capture_output=True, text=True)
        if run.returncode:
            raise ValueError(f"{path.name}: {run.stderr}")
        rows, checkpoints, deltas, trades = map(int, run.stdout.split())
        counts = manifest["counts"]
        assert [rows, checkpoints, deltas, trades] == [manifest["rows"], counts.get("book_checkpoint", 0),
                                                      counts.get("orderbook_delta", 0), counts.get("trade", 0)], path.name
        grid = np.fromfile(Path(temp) / "grid.bin", dtype=np.int64).reshape(-1, 6)
        tape = np.fromfile(Path(temp) / "trades.bin", dtype=np.int64).reshape(-1, 9)
    assert np.array_equal(grid[:, 0], np.arange(slots)), path.name
    return hour, grid[:, 1:], tape


def main():
    prefix = Path(os.environ.get("SIMDJSON_PREFIX", "/opt/homebrew"))
    paths = sorted((SOURCE / "kalshi_perp").glob("*.jsonl.gz"))
    with tempfile.TemporaryDirectory() as build:
        binary = Path(build) / "replay_bbo"
        flags = []
        if sys.platform == "darwin":
            sdk = Path(subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip())
            if (sdk / "usr/include/c++/v1").is_dir():
                flags = ["-isystem", str(sdk / "usr/include/c++/v1")]
        subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O3", *flags, f"-I{prefix}/include",
                        f"-L{prefix}/lib", str(CPP), "-lsimdjson", "-lz", "-o", str(binary)], check=True)
        with ThreadPoolExecutor(max_workers=6) as pool:
            parts = [p for p in pool.map(lambda p: run_hour(p, binary), paths) if p is not None]
    parts.sort(key=lambda p: p[0])
    grid = np.concatenate([p[1] for p in parts])
    assert len(grid) == int((STOP - START).total_seconds() * 10)
    np.savez(BBO, bid=grid[:, 0], ask=grid[:, 1], bid_size=grid[:, 2], ask_size=grid[:, 3], valid=grid[:, 4].astype(bool))
    tape = pd.DataFrame(np.concatenate([p[2] for p in parts]), columns=TRADE_FIELDS)
    tape = tape[(tape.received_ns >= int(START.timestamp()) * 10**9) & (tape.received_ns < int(STOP.timestamp()) * 10**9)]
    tape.to_parquet(TRADES, index=False, compression="zstd")
    print(f"{len(grid):,} quote slots ({grid[:, 4].mean():.4%} valid); {len(tape):,} trades")


if __name__ == "__main__":
    main()
