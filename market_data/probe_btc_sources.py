"""Read-only public BTC source probe. No credentials or trading endpoints."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import urllib.error
import urllib.request
import zipfile


URLS = {
    "kalshi_margin_docs": "https://docs.kalshi.com/margin.md",
    "kalshi_candles_docs": "https://docs.kalshi.com/margin-rest/market/get-market-candlesticks.md",
    "kalshi_book_docs": "https://docs.kalshi.com/margin-rest/market/get-market-orderbook.md",
    "kalshi_stream_docs": "https://docs.kalshi.com/margin-ws/websockets/orderbook-updates.md",
    "kalshi_markets": "https://external-api.kalshi.com/trade-api/v2/margin/markets?limit=100",
    "kalshi_btc_book": "https://external-api.kalshi.com/trade-api/v2/margin/markets/KXBTCPERP/orderbook",
    "kalshi_btc_candles": "https://external-api.kalshi.com/trade-api/v2/margin/markets/KXBTCPERP/candlesticks?start_ts=1793059200&end_ts=1793145600&period_interval=60",
    "hyperliquid_history_docs": "https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data.md",
    "binance_depth_sample": "https://data.binance.vision/data/futures/um/daily/bookDepth/BTCUSDT/BTCUSDT-bookDepth-2025-01-01.zip",
    "binance_bars_sample": "https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2025-01.zip",
}


def probe(item, out):
    name, url = item
    row = {"name": name, "url": url, "requested_at": datetime.now(timezone.utc).isoformat()}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TDA-Research/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
            row.update(status=response.status, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        suffix = ".zip" if url.endswith(".zip") else ".md" if url.endswith(".md") else ".json"
        (out / (name + suffix)).write_bytes(body)
        if suffix == ".zip":
            with zipfile.ZipFile(io.BytesIO(body)) as z:
                row["members"] = z.namelist()
                with z.open(z.namelist()[0]) as f:
                    row["first_lines"] = [f.readline().decode().strip() for _ in range(3)]
    except urllib.error.HTTPError as error:
        row.update(status=error.code, error_body=error.read().decode(errors="replace")[:1000])
    except Exception as error:
        row.update(error_type=type(error).__name__, error=str(error))
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tardis-size-only", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.tardis_size_only:
        url = "https://datasets.tardis.dev/v1/bitstamp/book_snapshot_5/2025/01/01/BTCUSD.csv.gz"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as response:
                meta = dict(url=url, status=response.status, headers=dict(response.headers.items()))
        except urllib.error.HTTPError as error:
            meta = dict(url=url, status=error.code, error=str(error))
        (args.out / "tardis_head.json").write_text(json.dumps(meta, indent=2) + "\n")
        print(json.dumps(meta, indent=2))
        return
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda item: probe(item, args.out), URLS.items()))
    (args.out / "probe.json").write_text(json.dumps(rows, indent=2) + "\n")
    for row in rows:
        print(json.dumps(row))


if __name__ == "__main__":
    main()
