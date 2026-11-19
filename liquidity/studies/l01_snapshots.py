"""Build offline, end-of-second KXBTCPERP books from the validated CRC journal."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "market_data/recordings/crc/2026-11-10T23-50-19Z-job-1724180"
RESULTS = ROOT / "liquidity/results/book_shape"
CACHE = RESULTS / "snapshots"
CPP = Path(__file__).with_name("replay_book.cpp")
START = datetime(2026, 11, 11, tzinfo=timezone.utc)
STOP = datetime(2026, 11, 17, 23, 50, tzinfo=timezone.utc)
LEVEL_FIELDS = ["signed_price_tick", "size_100", "added_100", "removed_100", "executed_100"]
CLOCK_FIELDS = ["second_in_hour", "epoch", "book_seq", "best_bid_tick", "best_ask_tick",
                "complete", "trade_count", "delta_count", "offset"]
CACHE_VERSION = 1


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build_hour(path, binary, code_hash):
    name = path.name.split(".")[0]
    hour = datetime.strptime(name, "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=timezone.utc)
    num_seconds = max(0, min(3600, int((STOP - hour).total_seconds()))) if hour >= START else 0
    manifest = json.loads(path.with_suffix(".manifest.json").read_text())
    target = CACHE / (name + ".parquet")
    if target.exists():
        meta = pq.read_schema(target).metadata
        cached = json.loads(meta[b"replay"])
        if (cached["source_sha256"] == manifest["sha256"] and cached["code_sha256"] == code_hash
                and cached["seconds"] == num_seconds and cached["cache_version"] == CACHE_VERSION):
            return cached
    if sha256(path) != manifest["sha256"]:
        raise ValueError(f"Archive digest mismatch in {name}")
    with tempfile.TemporaryDirectory(dir=CACHE) as temp:
        run = subprocess.run([str(binary), str(path), temp, hour.isoformat()[:13], "0", str(num_seconds)],
                             capture_output=True, text=True)
        if run.returncode:
            raise ValueError(f"{name}: {run.stderr}")
        rows, checkpoints, deltas, trades = map(int, run.stdout.split())
        counts = manifest["counts"]
        if [rows, checkpoints, deltas, trades] != [manifest["rows"], counts.get("book_checkpoint", 0),
                                                  counts.get("orderbook_delta", 0), counts.get("trade", 0)]:
            raise ValueError(f"Counts differ from the journal manifest in {name}")
        clock = np.fromfile(Path(temp) / "clock.bin", dtype=np.int64).reshape(-1, 9)
        levels = np.fromfile(Path(temp) / "levels.bin", dtype=np.int64).reshape(-1, 5)
        if not np.array_equal(clock[:, 0], np.arange(num_seconds)):
            raise ValueError(f"Incomplete second clock in {name}")
        offsets = np.r_[0, clock[:, -1]]
        if offsets[-1] != len(levels):
            raise ValueError(f"Level buffer mismatch in {name}")
        fields = {key: clock[:, i] for i, key in enumerate(CLOCK_FIELDS)}
        # Receipt-second [s,s+1) is labelled by s+1. The ladder is known at that boundary.
        columns = {"end_utc": pa.array(int(hour.timestamp()) + fields["second_in_hour"] + 1,
                                       type=pa.timestamp("s", tz="UTC"))}
        columns.update({k: fields[k] for k in ("epoch", "book_seq", "best_bid_tick", "best_ask_tick", "trade_count", "delta_count")})
        columns["complete"] = fields["complete"].astype(bool)
        columns["crossed_or_locked"] = ((fields["best_bid_tick"] >= fields["best_ask_tick"])
                                        & (fields["best_ask_tick"] > 0))
        for i, key in enumerate(LEVEL_FIELDS):
            columns[key] = pa.ListArray.from_arrays(offsets.astype(np.int32), pa.array(levels[:, i]))
        stats = dict(hour=name, seconds=num_seconds, valid_seconds=int(np.sum(columns["complete"] & ~columns["crossed_or_locked"])),
                     source_rows=rows, checkpoints=checkpoints, deltas=deltas, trades=trades,
                     source_sha256=manifest["sha256"], code_sha256=code_hash, cache_version=CACHE_VERSION)
        table = pa.table(columns).replace_schema_metadata({b"replay": json.dumps(stats).encode()})
        product = Path(temp) / "hour.parquet"
        pq.write_table(table, product, compression="zstd", use_dictionary=True, row_group_size=300)
        product.replace(target)
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    audit = json.loads((SOURCE / "local_validation_complete.json").read_text())
    market = json.loads((SOURCE / "kalshi_market.json").read_text())["market"]
    if not audit["passed"] or market["contract_size"] != "0.000100" or market["tick_size"] != "0.0001":
        raise ValueError("Unexpected archive or instrument units")
    paths = sorted((SOURCE / "kalshi_perp").glob("*.jsonl.gz"))
    if len(paths) != audit["completed_files"]:
        raise ValueError("Expected the complete audited archive")
    CACHE.mkdir(parents=True, exist_ok=True)
    prefix = Path(os.environ.get("SIMDJSON_PREFIX", "/opt/homebrew"))
    code_hash = hashlib.sha256(CPP.read_bytes() + Path(__file__).read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as build:
        binary = Path(build) / "replay"
        sdk_flags = []
        if sys.platform == "darwin":
            sdk = Path(subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip())
            if (sdk / "usr/include/c++/v1").is_dir():
                sdk_flags = ["-isystem", str(sdk / "usr/include/c++/v1")]
        subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O3", *sdk_flags, f"-I{prefix}/include",
                        f"-L{prefix}/lib", str(CPP), "-lsimdjson", "-lz", "-o", str(binary)], check=True)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            records = []
            for record in pool.map(lambda p: build_hour(p, binary, code_hash), paths):
                records.append(record)
                if len(records) % 12 == 0:
                    print(f"{len(records)} / {len(paths)} hours checked", flush=True)
    totals = {k: sum(r[k] for r in records) for k in ("seconds", "valid_seconds", "source_rows", "checkpoints", "deltas", "trades")}
    if (totals["seconds"] != int((STOP - START).total_seconds()) or totals["source_rows"] != audit["rows"]
            or totals["checkpoints"] != audit["checkpoints_replayed"] or totals["trades"] != audit["unique_trades"]
            or totals["deltas"] != audit["message_counts"]["orderbook_delta"]):
        raise ValueError("Week totals disagree with independent archive validation")
    report = dict(source=SOURCE.name, first_interval_start=START.isoformat(), last_interval_end=STOP.isoformat(),
                  totals=totals, hours=records, gap_windows=audit["gap_windows"])
    (RESULTS / "snapshot_manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(totals)


if __name__ == "__main__":
    main()
