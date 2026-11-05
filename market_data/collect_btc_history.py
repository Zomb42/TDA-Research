"""Collect public, read-only BTC histories with cached originals and checksums.

Run with conda tda. All ranges are UTC, start inclusive and end exclusive.
Binance bands are cumulative displayed depth, not individual price levels.
Kalshi prices are USD per contract; metadata supplies the BTC contract size.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

import numpy as np
import pandas as pd

VISION = "https://data.binance.vision/data/futures/um"
KALSHI = "https://external-api.kalshi.com/trade-api/v2/margin"


def fetch(url, path):
    """Cache exact bytes and their receipt metadata. Retry transient failures only."""
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    if path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest():
            return meta
        raise ValueError(f"Cache checksum mismatch: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        started = datetime.now(timezone.utc).isoformat()
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "TDA-Research/1.0"})
            with urllib.request.urlopen(request, timeout=40) as response:
                body = response.read()
                status = response.status
            meta = dict(url=url, requested_at=started, received_at=datetime.now(timezone.utc).isoformat(),
                        status=status, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            path.with_suffix(path.suffix + ".tmp").write_bytes(body)
            path.with_suffix(path.suffix + ".tmp").replace(path)
            meta_path.write_text(json.dumps(meta, indent=2) + "\n")
            return meta
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
        time.sleep(2 ** attempt)


def archive_job(url, folder):
    path = folder / url.rsplit("/", 1)[-1]
    row = {"url": url, "file": str(path.name)}
    try:
        row.update(fetch(url, path))
        checksum = path.with_suffix(path.suffix + ".CHECKSUM")
        fetch(url + ".CHECKSUM", checksum)
        expected = checksum.read_text().split()[0]
        if row["sha256"] != expected:
            raise ValueError("Published SHA256 mismatch")
        row["published_checksum_verified"] = True
        with zipfile.ZipFile(path) as z:
            if len(z.namelist()) != 1:
                raise ValueError("Expected exactly one CSV per archive")
            with z.open(z.namelist()[0]) as f:
                frame = pd.read_csv(f)
        row["rows"] = len(frame)
        return row, frame
    except Exception as error:
        row.update(error_type=type(error).__name__, error=str(error))
        return row, None


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def collect_binance(args):
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    # Whole completed months only; use daily files for the partial last month.
    cursor, end = pd.Timestamp(args.start, tz="UTC"), pd.Timestamp(args.end, tz="UTC")
    while cursor < end:
        following = cursor + pd.offsets.MonthBegin(1)
        if cursor.day == 1 and following <= end:
            key = cursor.strftime("%Y-%m")
            jobs.append((f"{VISION}/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-{key}.zip", "bars"))
            cursor = following
        else:
            key = cursor.strftime("%Y-%m-%d")
            jobs.append((f"{VISION}/daily/klines/BTCUSDT/5m/BTCUSDT-5m-{key}.zip", "bars"))
            cursor += pd.Timedelta(days=1)
    for day in pd.date_range(args.depth_start, args.depth_end, inclusive="left", freq="D"):
        key = day.strftime("%Y-%m-%d")
        jobs.append((f"{VISION}/daily/bookDepth/BTCUSDT/BTCUSDT-bookDepth-{key}.zip", "depth"))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda job: archive_job(job[0], out / "raw" / job[1]), jobs))
    save_json(out / "requests.json", [r for r, _ in results])
    failures = [r for r, f in results if f is None]
    if failures:
        raise RuntimeError(f"{len(failures)} archive downloads failed; see requests.json. No partial panel accepted.")
    bars = pd.concat([f for (_, kind), (_, f) in zip(jobs, results) if kind == "bars"], ignore_index=True)
    if not ((bars.open_time > 10**12) & (bars.open_time < 10**13)).all():
        raise ValueError("Expected futures epoch milliseconds; do not apply spot microsecond rules")
    bars["open_time_utc"] = pd.to_datetime(bars.open_time, unit="ms", utc=True)
    # Logical bar completion: the first instant after the exchange close_time.
    bars["available_at_utc"] = pd.to_datetime(bars.close_time + 1, unit="ms", utc=True)
    bars = bars.sort_values("open_time").reset_index(drop=True)
    expected = pd.date_range(args.start, args.end, inclusive="left", freq="5min", tz="UTC")
    observed = pd.DatetimeIndex(bars.open_time_utc)
    missing, extra = expected.difference(observed), observed.difference(expected)
    ohlc_bad = ((bars.low > bars[["open", "close"]].min(axis=1)) |
                (bars.high < bars[["open", "close"]].max(axis=1)) | (bars.low > bars.high) |
                (bars[["open", "high", "low", "close"]] <= 0).any(axis=1))
    audit = dict(rows=len(bars), expected_rows=len(expected), duplicates=int(observed.duplicated().sum()),
                 missing_bars=len(missing), extra_bars=len(extra), invalid_ohlc=int(ohlc_bad.sum()),
                 invalid_durations=int(((bars.close_time - bars.open_time) != 299999).sum()),
                 missing_first_20=[str(x) for x in missing[:20]],
                 negative_volume=int((bars.volume < 0).sum()),
                 invalid_taker_volume=int(((bars.taker_buy_volume < 0) | (bars.taker_buy_volume > bars.volume + 1e-8)).sum()))
    bars.to_parquet(out / "bars_5m.parquet", index=False)
    depth = pd.concat([f for (_, kind), (_, f) in zip(jobs, results) if kind == "depth"], ignore_index=True)
    depth["timestamp_utc"] = pd.to_datetime(depth.timestamp, utc=True)
    depth = depth.sort_values(["timestamp_utc", "percentage"]).reset_index(drop=True)
    depth.to_parquet(out / "depth_bands.parquet", index=False)
    groups = depth.groupby("timestamp_utc")
    times = pd.DatetimeIndex(sorted(depth.timestamp_utc.unique()))
    dt = np.diff(times.asi8) / 1e9
    bands = sorted(float(x) for x in depth.percentage.unique())
    decreasing = 0
    for side in (-1, 1):
        part = depth[depth.percentage * side > 0].copy()
        part["distance"] = part.percentage.abs()
        part = part.sort_values(["timestamp_utc", "distance"])
        decreasing += int((part.groupby("timestamp_utc").notional.diff() < -1e-5).sum())
    depth_audit = dict(rows=len(depth), snapshots=len(times), percentage_bands=bands,
                       duplicates=int(depth.duplicated(["timestamp_utc", "percentage"]).sum()),
                       incomplete_snapshots=int((groups.size() != len(bands)).sum()),
                       negative_depth=int(((depth.depth < 0) | (depth.notional < 0)).sum()),
                       nonmonotone_cumulative_notional=decreasing,
                       cadence_seconds_p50=float(np.median(dt)), cadence_seconds_max=float(dt.max()),
                       intervals_over_60s=int((dt > 60).sum()),
                       first_timestamp=str(times[0]), last_timestamp=str(times[-1]))
    audit["depth"] = depth_audit
    save_json(out / "audit.json", audit)
    save_json(out / "manifest.json", dict(source="Binance USD-M BTCUSDT perpetual", quote_currency="USDT",
              requested_start=args.start, requested_end_exclusive=args.end, depth_start=args.depth_start,
              depth_end_exclusive=args.depth_end, created_at=datetime.now(timezone.utc).isoformat(),
              limitations=["Percentage-band depth cannot recover exact prices, spreads, queues or hidden liquidity.",
                           "Archive receipt times are not original publication times.",
                           "available_at_utc is logical bar close, not a measured historical delivery timestamp.",
                           "Venue-specific USDT perpetual; not a consolidated BTC/USD spot series."] ))
    print(json.dumps(audit, indent=2))
    if any(audit[k] for k in ["duplicates", "missing_bars", "extra_bars", "invalid_ohlc", "invalid_durations", "negative_volume", "invalid_taker_volume"]):
        raise RuntimeError("Price panel audit failed")


def kalshi_day(day, end, out, period):
    a = int(day.timestamp())
    b = int(min(day + timedelta(days=1), end).timestamp())
    # API end-period timestamps are inclusive; request (a,b] explicitly.
    params = dict(start_ts=a + 1, end_ts=b, period_interval=period, include_latest_before_start="false")
    url = f"{KALSHI}/markets/KXBTCPERP/candlesticks?" + urllib.parse.urlencode(params)
    path = out / "raw" / f"candles_{day:%Y-%m-%d}_{period}m.json"
    meta = fetch(url, path)
    data = json.loads(path.read_text())
    if data.get("ticker") != "KXBTCPERP":
        raise ValueError("Unexpected ticker")
    rows = data["candlesticks"]
    if any(not (a < x["end_period_ts"] <= b) for x in rows):
        raise ValueError("API returned out-of-range candle")
    meta.update(day=f"{day:%Y-%m-%d}", rows=len(rows))
    return meta, rows


def collect_kalshi(args):
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    market_path = out / "market.json"
    fetch(f"{KALSHI}/markets/KXBTCPERP", market_path)
    document = json.loads(market_path.read_text())
    market = document.get("market", document)
    size = float(market["contract_size"])
    if market["ticker"] != "KXBTCPERP" or size <= 0:
        raise ValueError("Unexpected market metadata")
    start, end = pd.Timestamp(args.start, tz="UTC"), pd.Timestamp(args.end, tz="UTC")
    days = list(pd.date_range(start, end, freq="D", inclusive="left"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda d: kalshi_day(d, end, out, args.period), days))
    save_json(out / "requests.json", [meta for meta, _ in results])
    raw = [row for _, rows in results for row in rows]
    if not raw:
        raise RuntimeError("No historical candles returned")
    frame = pd.json_normalize(raw, sep="_")
    for col in frame:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    frame = frame.sort_values("end_period_ts").reset_index(drop=True)
    frame["end_time_utc"] = pd.to_datetime(frame.end_period_ts, unit="s", utc=True)
    frame["start_time_utc"] = frame.end_time_utc - pd.Timedelta(minutes=args.period)
    for kind in ("price", "bid", "ask"):
        for field in ("open", "high", "low", "close"):
            col = f"{kind}_{field}"
            if col in frame:
                frame[col + "_usd_per_btc"] = frame[col] / size
    frame["volume_btc"] = frame.volume * size
    frame["open_interest_btc"] = frame.open_interest * size
    expected = pd.date_range(start + pd.Timedelta(minutes=args.period), end, freq=f"{args.period}min")
    observed = pd.DatetimeIndex(frame.end_time_utc)
    missing = expected.difference(observed)
    after_first = missing[missing >= observed.min()]
    null_price = int(frame.price_close.isna().sum())
    pair = frame[["bid_close", "ask_close"]].dropna()
    audit = dict(rows=len(frame), period_minutes=args.period, requested_expected_rows=len(expected),
                 first_candle_end=str(observed.min()), last_candle_end=str(observed.max()),
                 missing_requested=len(missing), missing_at_or_after_first=len(after_first),
                 missing_first_20=[str(t) for t in after_first[:20]],
                 empty_days=[meta["day"] for meta, rows in results if not rows],
                 duplicate_periods=int(observed.duplicated().sum()), null_trade_closes=null_price,
                 crossed_close_quotes=int((pair.bid_close > pair.ask_close).sum()),
                 contract_size_btc=size, filled_prices=False)
    frame.to_parquet(out / f"candles_{args.period}m.parquet", index=False)
    save_json(out / "audit.json", audit)
    save_json(out / "manifest.json", dict(source="Kalshi KXBTCPERP", requested_start=args.start,
              requested_end_exclusive=args.end, contract_size_btc=size, price_unit="USD per contract",
              quantity_unit="contracts", quote_currency="USD", period_minutes=args.period,
              created_at=datetime.now(timezone.utc).isoformat(),
              limitations=["Candles preserve OHLC quotes and trades, not historical multilevel depth.",
                           "Missing or null prices are not forward filled.",
                           "Coverage is observed, not an independently verified launch date.",
                           "No authenticated WebSocket access was tested."]))
    print(json.dumps(audit, indent=2))
    if audit["duplicate_periods"]:
        raise RuntimeError("Duplicate Kalshi candles")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=["binance", "kalshi"])
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--depth-start", default="2025-01-01")
    parser.add_argument("--depth-end", default="2025-02-01")
    parser.add_argument("--period", type=int, choices=[1, 60, 1440], default=1)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if pd.Timestamp(args.end) <= pd.Timestamp(args.start):
        parser.error("end must follow start")
    (collect_binance if args.source == "binance" else collect_kalshi)(args)


if __name__ == "__main__":
    main()
