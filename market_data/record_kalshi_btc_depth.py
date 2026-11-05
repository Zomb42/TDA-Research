"""Bounded public REST snapshot recorder for KXBTCPERP; not tick-complete.

Each observation is an independent full depth=0 snapshot. Errors remain in the
raw journal; no stale book is reused. REST has no exchange event timestamp here.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import time
import urllib.request

from collect_btc_history import KALSHI


def request(path):
    req = urllib.request.Request(KALSHI + path, headers={"User-Agent": "TDA-Research/1.0", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


def summarize(payload, contract_size):
    book = payload["orderbook"]
    sides = {}
    for side, key, reverse in [("bid", "bids", True), ("ask", "asks", False)]:
        levels = [(Decimal(p), Decimal(q)) for p, q in book[key]]
        if not levels or any(p <= 0 or q < 0 for p, q in levels):
            raise ValueError("Empty side or invalid level")
        if len({p for p, _ in levels}) != len(levels):
            raise ValueError("Duplicate price levels")
        sides[side] = sorted(levels, reverse=reverse)
    bid, ask = sides["bid"][0][0], sides["ask"][0][0]
    if bid >= ask:
        raise ValueError("Locked or crossed REST snapshot")
    mid = (bid + ask) / 2
    result = dict(bid_usd_per_btc=float(bid / contract_size), ask_usd_per_btc=float(ask / contract_size),
                  mid_usd_per_btc=float(mid / contract_size), spread_bps=float((ask - bid) / mid * 10000),
                  bid_levels=len(sides["bid"]), ask_levels=len(sides["ask"]))
    for band in (10, 25, 50, 100):
        notionals = {}
        for side in ("bid", "ask"):
            notionals[side] = sum(p * q for p, q in sides[side] if abs(p / mid - 1) * 10000 <= band)
            result[f"{side}_notional_{band}bps"] = float(notionals[side])
        total = notionals["bid"] + notionals["ask"]
        result[f"imbalance_{band}bps"] = float((notionals["bid"] - notionals["ask"]) / total) if total else None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--interval", type=float, default=2)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.seconds <= 0 or args.interval < 1:
        parser.error("positive duration and interval >= 1 second required")
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "snapshots.jsonl"
    if path.exists():
        raise SystemExit("Use a new output directory; existing journals are never overwritten")
    market = request("/markets/KXBTCPERP")
    (args.out / "market.json").write_text(json.dumps(market, indent=2) + "\n")
    item = market.get("market", market)
    size = Decimal(item["contract_size"])
    start = time.monotonic()
    successes = failures = 0
    with path.open("x", buffering=1) as f:
        while time.monotonic() - start < args.seconds:
            tick = time.monotonic()
            row = dict(requested_at=datetime.now(timezone.utc).isoformat(), exchange_timestamp=None)
            try:
                row["payload"] = request("/markets/KXBTCPERP/orderbook?depth=0")
                row["received_at"] = datetime.now(timezone.utc).isoformat()
                row["request_seconds"] = time.monotonic() - tick
                row["summary"] = summarize(row["payload"], size)
                successes += 1
            except Exception as error:
                row.update(received_at=datetime.now(timezone.utc).isoformat(), error_type=type(error).__name__, error=str(error))
                failures += 1
            f.write(json.dumps(row) + "\n")
            time.sleep(max(0, min(args.interval - (time.monotonic() - tick), args.seconds - (time.monotonic() - start))))
    summary = dict(successful_snapshots=successes, failed_snapshots=failures, elapsed_seconds=time.monotonic() - start,
                   requested_interval_seconds=args.interval, contract_size_btc=str(size),
                   collection="public REST depth=0", tick_complete=False, historical_backfill=False,
                   limitations=["Receipt-time samples, no exchange event timestamps or sequence numbers.",
                                "Changes between polls and within request latency are unobserved.",
                                "This program exits after its bounded duration; no background service installed."])
    (args.out / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
