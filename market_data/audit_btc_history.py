"""Offline audit using originals, independently of collection transformations."""
import hashlib
import json
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
BINANCE = BASE / "datasets/btc_binance_2024_2026-10-27"
KALSHI = BASE / "datasets/btc_kalshi_2026-06_2026-10-27"


def gap_ranges(missing, seconds):
    groups = []
    if len(missing):
        start = previous = missing[0]
        for t in missing[1:]:
            if (t - previous).total_seconds() != seconds:
                groups.append(dict(first_missing_end_utc=str(start), last_missing_end_utc=str(previous),
                                   missing_periods=int((previous-start).total_seconds()/seconds)+1))
                start = t
            previous = t
        groups.append(dict(first_missing_end_utc=str(start), last_missing_end_utc=str(previous),
                           missing_periods=int((previous-start).total_seconds()/seconds)+1))
    return pd.DataFrame(groups, columns=["first_missing_end_utc", "last_missing_end_utc", "missing_periods"])


def main():
    checked = 0
    for folder in [BINANCE, KALSHI]:
        for meta_path in folder.rglob("*.meta.json"):
            meta = json.loads(meta_path.read_text())
            original = meta_path.with_name(meta_path.name.removesuffix(".meta.json"))
            assert hashlib.sha256(original.read_bytes()).hexdigest() == meta["sha256"]
            checked += 1
    bars = pd.read_parquet(BINANCE / "bars_5m.parquet")
    frames = []
    for f in sorted((BINANCE / "raw/bars").glob("*.zip")):
        with zipfile.ZipFile(f) as z:
            with z.open(z.namelist()[0]) as stream:
                frames.append(pd.read_csv(stream))
    original = pd.concat(frames).sort_values("open_time").reset_index(drop=True)
    pd.testing.assert_frame_equal(original, bars[original.columns], check_exact=True)
    assert np.all(np.diff(bars.open_time) == 300000)
    assert bars.open_time.iloc[0] == pd.Timestamp("2024-01-01", tz="UTC").value // 10**6
    assert bars.open_time.iloc[-1] == pd.Timestamp("2026-10-27 23:55", tz="UTC").value // 10**6
    depth = pd.read_parquet(BINANCE / "depth_bands.parquet")
    pivot = depth.pivot(index="timestamp_utc", columns="percentage", values="notional")
    assert not pivot.isna().any().any()
    for columns in [[-1, -2, -3, -4, -5], [1, 2, 3, 4, 5]]:
        assert (np.diff(pivot[columns].values, axis=1) >= -1e-5).all()
    deltas = pivot.index.to_series().diff().dt.total_seconds()
    gap_rows = []
    for end, seconds in deltas[deltas > 60].items():
        gap_rows.append(dict(previous_snapshot_utc=str(end - pd.Timedelta(seconds=seconds)),
                             next_snapshot_utc=str(end), gap_seconds=seconds))
    pd.DataFrame(gap_rows).to_csv(BINANCE / "depth_time_gaps.csv", index=False)
    # Check depth values against independent original-file concatenation, too.
    frames = []
    for f in sorted((BINANCE / "raw/depth").glob("*.zip")):
        with zipfile.ZipFile(f) as z:
            with z.open(z.namelist()[0]) as stream:
                frames.append(pd.read_csv(stream))
    raw_depth = pd.concat(frames).sort_values(["timestamp", "percentage"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(raw_depth, depth[raw_depth.columns], check_exact=True)
    candles = pd.read_parquet(KALSHI / "candles_1m.parquet")
    rows = []
    for f in sorted((KALSHI / "raw").glob("candles_????-??-??_1m.json")):
        rows.extend(json.loads(f.read_text())["candlesticks"])
    original_candles = pd.json_normalize(rows, sep="_").sort_values("end_period_ts").reset_index(drop=True)
    for column in original_candles:
        expected = pd.to_numeric(original_candles[column])
        np.testing.assert_allclose(candles[column], expected, rtol=0, atol=0, equal_nan=True)
    size = float(json.loads((KALSHI / "market.json").read_text())["market"]["contract_size"])
    np.testing.assert_allclose(candles.price_close_usd_per_btc, candles.price_close / size, equal_nan=True)
    np.testing.assert_allclose(candles.volume_btc, candles.volume * size)
    assert not candles.end_time_utc.duplicated().any()
    expected = pd.date_range("2026-06-01 00:01", "2026-10-28", freq="min", tz="UTC")
    missing = expected.difference(pd.DatetimeIndex(candles.end_time_utc))
    gaps = gap_ranges(missing, 60)
    gaps.to_csv(KALSHI / "missing_period_ranges.csv", index=False)
    candles[candles.price_close.isna()][["end_time_utc", "volume", "bid_close", "ask_close"]].to_csv(KALSHI / "null_trade_close_periods.csv", index=False)
    report = dict(raw_files_sha256_verified=checked, binance_bars_match_originals_exactly=True,
                  binance_depth_matches_originals_exactly=True, binance_continuous_5m_prices=True,
                  kalshi_candles_match_originals=True, kalshi_unit_conversion_verified=True,
                  binance_depth_intervals_over_60s=len(gap_rows),
                  kalshi_missing_minutes=len(missing), kalshi_missing_ranges=len(gaps),
                  kalshi_null_trade_closes=int(candles.price_close.isna().sum()),
                  no_filling_applied=True,
                  conclusion="Original-byte and transformation checks passed. Depth outages and Kalshi missing/null periods remain quality limitations.")
    (BASE / "datasets/btc_independent_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
