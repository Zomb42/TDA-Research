"""GET-only bid/ask quotes 10 minutes before the close, for the 200-stock panel plus SPY.

For each sampled trading day, all quotes in the 5 seconds before
"close minus 10 minutes" (15:49:55-15:50:00, or 12:49:55-12:50:00 on a half day).
That is the moment the late-day book would be entered with an ordinary order.

Saved per day: for each symbol, the number of quotes, the median and the last
bid-ask spread in basis points of the midpoint, and the last bid and ask.
Quotes with a crossed or zero-width market are dropped.

Uses the local paper credentials for Alpaca market data only. No account,
position, order, subscription or payment endpoint is requested, and the
credentials are never printed. Resumable.

    python market_data/download_equity_quotes.py --every 5        # every 5th trading day
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import json
import os
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
DAILY = HERE / "datasets/equity_daily_expanded_2016_2026-11-09"
OUT = HERE / "datasets/equity_quotes_1550_2017_2026-11-09"
NY = ZoneInfo("America/New_York")
URL = "https://data.alpaca.markets/v2/stocks/quotes"
SPACING = 0.33


def get(headers, params):
    url = URL + "?" + urllib.parse.urlencode(params)
    for attempt in range(7):
        time.sleep(SPACING)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers, method="GET"), timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            print(f"  retry: HTTP {exc.code} (attempt {attempt + 1})", flush=True)
            if exc.code in (429, 500, 502, 503, 504) and attempt < 6:
                time.sleep(min(2 ** attempt, 30))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            print(f"  retry: {type(exc).__name__} (attempt {attempt + 1})", flush=True)
            if attempt < 6:
                time.sleep(min(2 ** attempt, 30))
                continue
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--every", type=int, default=5)
    parser.add_argument("--credentials-file", type=Path, default=HERE / ".alpaca-paper.local.json")
    args = parser.parse_args()
    local = json.loads(args.credentials_file.read_text()) if args.credentials_file.exists() else {}
    key = os.environ.get("APCA_API_KEY_ID") or local.get("APCA_API_KEY_ID")
    secret = os.environ.get("APCA_API_SECRET_KEY") or local.get("APCA_API_SECRET_KEY")
    if not key or not key.startswith("PK") or not secret:
        parser.error("Existing paper credentials required; never printed")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    with (DAILY / "universe.csv").open() as stream:
        symbols = sorted({row["symbol"] for row in csv.DictReader(stream)} | {"SPY"})
    days = [d for d in json.loads((DAILY / "calendar.json").read_text()) if "2017-01-03" <= d["date"] <= "2026-11-09"]
    days = days[::args.every]
    (OUT / "days").mkdir(parents=True, exist_ok=True)
    print(f"{len(symbols)} symbols, {len(days)} days", flush=True)
    started = time.time()

    def fetch(day):
        path = OUT / "days" / f"{day['date']}.json.gz"
        if path.exists():
            return
        moment = datetime.fromisoformat(f"{day['date']}T{day['close']}:00").replace(tzinfo=NY) - timedelta(minutes=10)
        params = {"symbols": ",".join(symbols), "start": (moment - timedelta(seconds=5)).isoformat(),
                  "end": (moment - timedelta(microseconds=1)).isoformat(), "feed": "sip", "limit": 10000}
        quotes, token = {}, None
        while True:
            page = get(headers, {**params, **({"page_token": token} if token else {})})
            for symbol, rows in (page.get("quotes") or {}).items():
                quotes.setdefault(symbol, []).extend(rows)
            token = page.get("next_page_token")
            if not token:
                break
        summary = {}
        for symbol, rows in quotes.items():
            spreads, last = [], None
            for q in rows:
                bid, ask = q.get("bp", 0), q.get("ap", 0)
                if bid > 0 and ask > bid:
                    spreads.append((ask - bid) / ((ask + bid) / 2) * 1e4)
                    last = (bid, ask)
            if spreads:
                summary[symbol] = {"quotes": len(spreads), "median_spread_bps": statistics.median(spreads),
                                   "last_spread_bps": spreads[-1], "last_bid": last[0], "last_ask": last[1]}
        with gzip.open(path.with_suffix(".part"), "wt") as stream:
            json.dump({"date": day["date"], "moment": moment.isoformat(), "symbols": summary}, stream)
        path.with_suffix(".part").rename(path)

    with ThreadPoolExecutor(8) as pool:
        for k, _ in enumerate(pool.map(fetch, days)):
            if (k + 1) % 50 == 0:
                print(f"{k + 1}/{len(days)} days, {time.time() - started:.0f}s", flush=True)
    (OUT / "manifest.json").write_text(json.dumps({
        "source": "Alpaca /v2/stocks/quotes, feed sip", "window": "5 seconds ending 10 minutes before the close",
        "every_nth_trading_day": args.every, "days": len(list((OUT / "days").glob("*.json.gz"))),
        "first_day": days[0]["date"], "last_day": days[-1]["date"], "symbols": len(symbols),
        "finished_at": datetime.now().astimezone().isoformat()}, indent=2))
    print("done", flush=True)


if __name__ == "__main__":
    main()
