"""GET-only intraday bars for the 200-stock equity panel (plus SPY).

For every trading day it saves two files:

  half_hours      30-minute bars from the open to 30 minutes before the close
  last_half_hour  10-minute bars from 30 minutes before the close to 10 minutes after it
                  (the bar that starts at the close holds the closing-auction trade)

The server's page limit counts the underlying minutes, not the bars returned
(about 10,000 stock-minutes per page), so a full session for 201 symbols costs
about 9 requests a day whatever the bar size: roughly 22,000 requests, or two
hours at the free limit of 200 requests a minute.

Prices are unadjusted ("raw"). They are only ever compared within one day,
where splits and dividends do not matter.

Uses the local paper credentials for Alpaca market data only. No account,
position, order, subscription or payment endpoint is requested, and the
credentials are never printed. Resumable: a day already saved is skipped.

    python market_data/download_equity_intraday.py --probe        # one day, prints counts
    python market_data/download_equity_intraday.py                # everything
"""
import argparse
import gzip
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
DAILY = HERE / "datasets/equity_daily_expanded_2016_2026-11-09"
OUT = HERE / "datasets/equity_intraday_2017_2026-11-09"
NY = ZoneInfo("America/New_York")
HOST, ENDPOINT = "https://data.alpaca.markets", "/v2/stocks/bars"
KINDS = {"half_hours": "30Min", "last_half_hour": "10Min", "five_minutes": "5Min"}
SPACING = 0.33                      # seconds between request starts: about 180 a minute, under the 200 limit

_lock, _next_slot = threading.Lock(), [0.0]


def wait_for_slot():
    with _lock:
        now = time.monotonic()
        start = max(now, _next_slot[0])
        _next_slot[0] = start + SPACING
    time.sleep(max(0.0, start - now))


def get(headers, params):
    url = HOST + ENDPOINT + "?" + urllib.parse.urlencode(params)
    for attempt in range(7):
        wait_for_slot()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers, method="GET"), timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            print(f"  retry: HTTP {exc.code} for {params['start'][:10]} (attempt {attempt + 1})", flush=True)
            if exc.code in (429, 500, 502, 503, 504) and attempt < 6:
                time.sleep(min(2 ** attempt, 30))
                continue
            raise RuntimeError(f"HTTP {exc.code} for {params['start']}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:   # includes "connection reset"
            print(f"  retry: {type(exc).__name__} for {params['start'][:10]} (attempt {attempt + 1})", flush=True)
            if attempt < 6:
                time.sleep(min(2 ** attempt, 30))
                continue
            raise RuntimeError("Cannot reach Alpaca; network access needed") from None


def window(day, kind):
    """Start and end of the request for one day, as New York timestamps."""
    stamp = lambda clock: datetime.fromisoformat(f"{day['date']}T{clock}:00").replace(tzinfo=NY)
    open_, close = stamp(day["open"]), stamp(day["close"])
    if kind == "half_hours":
        return open_, close - timedelta(minutes=30, seconds=1)
    if kind == "five_minutes":                       # whole regular session
        return open_, close - timedelta(seconds=1)
    return close - timedelta(minutes=30), close + timedelta(minutes=10) - timedelta(seconds=1)


def fetch_day(headers, symbols, day, kind):
    path = OUT / "raw" / kind / f"{day['date']}.json.gz"
    if path.exists():
        return 0
    start, end = window(day, kind)
    params = {"symbols": ",".join(symbols), "timeframe": KINDS[kind], "start": start.isoformat(),
              "end": end.isoformat(), "feed": "sip", "adjustment": "raw", "limit": 10000, "sort": "asc"}
    bars, token = {}, None
    while True:
        page = get(headers, {**params, **({"page_token": token} if token else {})})
        for symbol, rows in (page.get("bars") or {}).items():
            bars.setdefault(symbol, []).extend(rows)
        token = page.get("next_page_token")
        if not token:
            break
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    with gzip.open(partial, "wt") as stream:
        json.dump({"date": day["date"], "open": day["open"], "close": day["close"], "bars": bars}, stream)
    partial.rename(path)
    return sum(map(len, bars.values()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2017-01-03")
    parser.add_argument("--end", default="2026-11-09")
    parser.add_argument("--probe", action="store_true", help="fetch one early and one recent day, then stop")
    parser.add_argument("--kinds", default="half_hours,last_half_hour", help="comma-separated, from: " + ", ".join(KINDS))
    parser.add_argument("--every", type=int, default=1, help="only every Nth trading day")
    parser.add_argument("--credentials-file", type=Path, default=HERE / ".alpaca-paper.local.json")
    args = parser.parse_args()
    local = json.loads(args.credentials_file.read_text()) if args.credentials_file.exists() else {}
    key = os.environ.get("APCA_API_KEY_ID") or local.get("APCA_API_KEY_ID")
    secret = os.environ.get("APCA_API_SECRET_KEY") or local.get("APCA_API_SECRET_KEY")
    if not key or not key.startswith("PK") or not secret:
        parser.error("Existing paper credentials required; never printed")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

    import csv
    with (DAILY / "universe.csv").open() as stream:
        symbols = sorted({row["symbol"] for row in csv.DictReader(stream)} | {"SPY"})
    days = [d for d in json.loads((DAILY / "calendar.json").read_text()) if args.start <= d["date"] <= args.end]
    days = days[::args.every]
    if args.probe:
        days = [days[0], days[-1]]
    # Every fifth day first, then the next fifth, and so on: a partial download is an even sample of the whole period.
    days = [day for offset in range(5) for day in days[offset::5]]
    kinds = args.kinds.split(",")
    jobs = [(day, kind) for day in days for kind in kinds]
    print(f"{len(symbols)} symbols, {len(days)} days, {len(jobs)} files", flush=True)

    done, total_bars, started = 0, 0, time.time()
    with ThreadPoolExecutor(10) as pool:
        for count in pool.map(lambda job: fetch_day(headers, symbols, *job), jobs):
            done += 1
            total_bars += count
            if done % 200 == 0 or done == len(jobs):
                print(f"{done}/{len(jobs)} files, {total_bars:,} new bars, {time.time() - started:.0f}s", flush=True)
    if kinds != ["half_hours", "last_half_hour"]:
        return                                       # the manifest describes the main download only
    (OUT / "manifest.json").write_text(json.dumps({
        "source": "Alpaca /v2/stocks/bars, feed sip, adjustment raw", "symbols": len(symbols),
        "first_day": min(d["date"] for d in days), "last_day": max(d["date"] for d in days), "days": len(days),
        "files": {kind: len(list((OUT / "raw" / kind).glob("*.json.gz"))) for kind in KINDS},
        "finished_at": datetime.now().astimezone().isoformat()}, indent=2))


if __name__ == "__main__":
    main()
