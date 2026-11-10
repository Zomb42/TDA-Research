"""Refresh the frozen 200-stock universe into a separate, complete data vintage.

Reuses the original GET-only downloader and its data checks. Reuses the saved
holdings/asset snapshots, never today's holdings, so this is a time extension
of the same securities. Full history is fetched rather than splicing differently
adjusted vendor vintages. Credentials remain in their existing private file.
"""
import argparse
from datetime import date
import json
from pathlib import Path
import shutil
import sys

import pandas as pd

import download_equity_expanded as download


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=download.HERE / "datasets/equity_daily_expanded_2016_2026-10-27")
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source, out = args.source.resolve(), args.out.resolve()
    if out == source or source in out.parents or out in source.parents:
        parser.error("Output must be separate from the preserved source")
    old = json.loads((source / "manifest.json").read_text())
    if str(args.end) <= old["last_session"]:
        parser.error("Refresh end must extend the source calendar")
    before = {p.name: download.sha(p) for p in source.iterdir() if p.is_file()}
    out.mkdir(parents=True, exist_ok=True)
    # This downloader reconstructs selection from these frozen snapshots, then
    # verifies that universe.csv is unchanged before any bars are requested.
    for name in ["ivv_holdings_source.csv", "holdings_retrieval.json", "alpaca_active_assets.json.gz", "universe.csv"]:
        target = out / name
        if target.exists():
            if download.sha(target) != download.sha(source / name):
                raise ValueError(f"Frozen snapshot mismatch: {name}")
        else:
            shutil.copyfile(source / name, target)
    download.PLAN = dict(old["plan"], requested_end=str(args.end),
        purpose="time extension of the frozen October 2026 universe; no reselection or strategy retuning",
        universe_refresh="reuse original holdings, asset master and security identifiers byte for byte",
        vintage="complete raw/all-adjusted history repull; do not splice old and new adjusted prices",
        source_dataset=source.name, source_manifest_sha256=before["manifest.json"])
    saved_argv = sys.argv
    try:
        sys.argv = [str(Path(download.__file__)), "--out", str(out)]
        download.main()
    finally:
        sys.argv = saved_argv
    assert download.sha(out / "universe.csv") == before["universe.csv"]
    overlap = {}
    for mode in ["raw", "all"]:
        old_bars = pd.read_csv(source / f"bars_{mode}.csv").set_index(["symbol", "date"])
        new_bars = pd.read_csv(out / f"bars_{mode}.csv").set_index(["symbol", "date"])
        assert old_bars.index.isin(new_bars.index).all()
        delta = (new_bars.loc[old_bars.index, ["o", "h", "l", "c"]] - old_bars[["o", "h", "l", "c"]]).abs()
        overlap[mode] = {"old_bars_checked": len(old_bars),
            "bars_with_changed_ohlc": int((delta.max(axis=1) > 1e-10).sum()),
            "maximum_absolute_ohlc_difference": float(delta.max().max()),
            "new_bars": len(new_bars) - len(old_bars)}
    assert all(download.sha(source / name) == digest for name, digest in before.items())
    calendar = json.loads((out / "calendar.json").read_text())
    added = [r["date"] for r in calendar if r["date"] > old["last_session"]]
    report = {"source_dataset": source.name, "refreshed_dataset": out.name,
        "requested_end": str(args.end), "added_sessions": added,
        "added_session_count": len(added), "overlap": overlap,
        "checks": {"frozen_universe_identical": True, "entire_source_dataset_unchanged": True,
            "all_old_observations_retained": True, "full_vintage_not_spliced": True},
        "source_sha256_before": before, "refresh_script_sha256": download.sha(Path(__file__))}
    download.write_json(out / "refresh_audit.json", report)
    download.write_json(out / "sha256.json", {p.name: download.sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != "sha256.json"})
    print(json.dumps({k: v for k, v in report.items() if k != "source_sha256_before"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
