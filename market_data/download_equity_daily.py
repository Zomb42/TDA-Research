"""GET-only daily equity research download; no trading/account-state requests.

Uses retained Alpaca paper credentials without logging them. Standard library only.
Daily adjusted returns are vendor-adjusted close changes, not executable P&L.
"""

import argparse
import csv
from datetime import date, datetime, time as dt_time, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo


GROUPS = {
    "technology": ["AAPL", "MSFT", "NVDA", "AMD", "ORCL"],
    "financials": ["JPM", "BAC", "C", "GS", "MS"],
    "health_care": ["JNJ", "PFE", "MRK", "ABBV", "AMGN"],
    "energy": ["XOM", "CVX", "COP", "EOG", "SLB"],
    "consumer_staples": ["WMT", "COST", "PG", "KO", "PEP"],
    "industrials": ["CAT", "DE", "HON", "UPS", "UNP"],
}
NY = ZoneInfo("America/New_York")


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2) + "\n")


def write_csv(path, fields, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2016, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, required=True,
                        help="Last completed New York session date, inclusive")
    parser.add_argument("--asof", type=date.fromisoformat, required=True,
                        help="Explicit symbol-mapping snapshot date")
    parser.add_argument("--credentials-file", type=Path,
                        default=Path(__file__).parent / ".alpaca-paper.local.json")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.start > args.end or args.end >= datetime.now(NY).date():
        parser.error("Require start <= end and end before today's New York date")
    # Read credentials only into memory; never save headers or credential contents.
    local = json.loads(args.credentials_file.read_text()) if args.credentials_file.exists() else {}
    key = os.environ.get("APCA_API_KEY_ID") or local.get("APCA_API_KEY_ID")
    secret = os.environ.get("APCA_API_SECRET_KEY") or local.get("APCA_API_SECRET_KEY")
    if not key or not key.startswith("PK") or not secret:
        parser.error("Existing paper credentials required; credentials are not printed")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    args.out.mkdir(parents=True, exist_ok=True)
    requests = []

    def get(host, endpoint, params):
        assert host in ("https://data.alpaca.markets", "https://paper-api.alpaca.markets")
        url = host + endpoint + "?" + urllib.parse.urlencode(params)
        for attempt in range(5):
            try:
                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=45) as response:
                    payload = json.load(response)
                requests.append({"endpoint": endpoint, "params": params.copy(),
                                 "received_at": datetime.now(timezone.utc).isoformat(),
                                 "http_status": 200})
                return payload
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < 4:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                # Do not log authentication headers or arbitrary response bodies.
                raise RuntimeError(f"GET {endpoint}: HTTP {exc.code}") from None
            except urllib.error.URLError:
                raise RuntimeError(f"Cannot reach Alpaca endpoint {endpoint}; check network access") from None
        raise RuntimeError("Retries exhausted")

    universe = [{"symbol": symbol, "research_group": group, "role": "equity"}
                for group, symbols in GROUPS.items() for symbol in symbols]
    universe.append({"symbol": "SPY", "research_group": "market", "role": "benchmark"})
    symbols = [row["symbol"] for row in universe]
    write_csv(args.out / "universe.csv", ["symbol", "research_group", "role"], universe)
    calendar = get("https://paper-api.alpaca.markets", "/v2/calendar",
                   {"start": args.start.isoformat(), "end": args.end.isoformat()})
    write_json(args.out / "calendar.json", calendar)
    sessions = sorted(row["date"] for row in calendar)
    session_set = set(sessions)
    series = {}
    audits = {}
    for adjustment in ("raw", "all"):
        collected = {symbol: [] for symbol in symbols}
        params = {
            "symbols": ",".join(symbols), "timeframe": "1Day",
            "start": datetime.combine(args.start, dt_time.min, NY).isoformat(),
            "end": datetime.combine(args.end, dt_time(23, 59, 59), NY).isoformat(),
            "asof": args.asof.isoformat(), "feed": "sip", "adjustment": adjustment,
            "limit": 10000, "sort": "asc",
        }
        seen_tokens = set()
        page = 0
        while True:
            payload = get("https://data.alpaca.markets", "/v2/stocks/bars", params)
            page += 1
            write_json(args.out / f"response_{adjustment}_{page:03d}.json", payload)
            for symbol, bars in (payload.get("bars") or {}).items():
                if symbol not in collected:
                    raise ValueError(f"Unexpected response symbol {symbol}")
                collected[symbol].extend(bars or [])
            print(f"{adjustment}: page {page}, {sum(map(len, collected.values()))} bars", flush=True)
            token = payload.get("next_page_token")
            if not token:
                break
            if token in seen_tokens:
                raise ValueError("Repeated pagination token")
            seen_tokens.add(token)
            params["page_token"] = token
        flat = []
        indexed = {}
        mode_audit = {}
        for symbol, bars in collected.items():
            by_date = {}
            for bar in bars:
                day = datetime.fromisoformat(bar["t"].replace("Z", "+00:00")).astimezone(NY).date().isoformat()
                if day in by_date:
                    raise ValueError(f"Duplicate daily bar {symbol} {day}")
                if day not in session_set:
                    raise ValueError(f"Unexpected session {symbol} {day}")
                if not all(math.isfinite(bar[f]) and bar[f] > 0 for f in ("o", "h", "l", "c")):
                    raise ValueError(f"Invalid OHLC {symbol} {day}")
                if not (bar["l"] <= min(bar["o"], bar["c"]) <= max(bar["o"], bar["c"]) <= bar["h"]):
                    raise ValueError(f"Inconsistent OHLC {symbol} {day}")
                if bar["v"] < 0:
                    raise ValueError(f"Negative volume {symbol} {day}")
                by_date[day] = bar
                flat.append({"symbol": symbol, "date": day, "timestamp": bar["t"],
                             **{f: bar.get(f, "") for f in ("o", "h", "l", "c", "v", "n", "vw")}})
            indexed[symbol] = by_date
            missing = sorted(session_set - by_date.keys())
            mode_audit[symbol] = {"bars": len(bars), "first_date": min(by_date) if by_date else None,
                                  "last_date": max(by_date) if by_date else None,
                                  "missing_session_count": len(missing), "missing_sessions": missing}
        write_csv(args.out / f"bars_{adjustment}.csv",
                  ["symbol", "date", "timestamp", "o", "h", "l", "c", "v", "n", "vw"],
                  sorted(flat, key=lambda row: (row["date"], row["symbol"])))
        write_csv(args.out / f"close_{adjustment}.csv", ["date", *symbols],
                  ({"date": day, **{s: indexed[s].get(day, {}).get("c", "") for s in symbols}}
                   for day in sessions))
        series[adjustment] = indexed
        audits[adjustment] = {"pages": page, "total_bars": len(flat), "by_symbol": mode_audit}
    # Align to the trading calendar. Never forward-fill; a missing adjacent session
    # yields a missing return, not a mislabeled multi-session return.
    simple_rows, log_rows, extreme = [], [], []
    for i, day in enumerate(sessions):
        simple, log = {"date": day}, {"date": day}
        for symbol in symbols:
            today = series["all"][symbol].get(day)
            previous = series["all"][symbol].get(sessions[i - 1]) if i else None
            if today and previous:
                ratio = today["c"] / previous["c"]
                simple[symbol], log[symbol] = ratio - 1, math.log(ratio)
                if abs(ratio - 1) > .25:
                    extreme.append({"symbol": symbol, "date": day, "return": ratio - 1})
            else:
                simple[symbol] = log[symbol] = ""
        simple_rows.append(simple)
        log_rows.append(log)
    write_csv(args.out / "returns_simple.csv", ["date", *symbols], simple_rows)
    write_csv(args.out / "returns_log.csv", ["date", *symbols], log_rows)
    if any(not series["all"][symbol] for symbol in symbols):
        raise ValueError("At least one requested symbol has no adjusted data")
    # Independent algebraic check: each available contiguous return segment must
    # compound to the segment's adjusted endpoint close ratio.
    for symbol in symbols:
        product = 1.0
        first = None
        for row in simple_rows:
            bar = series["all"][symbol].get(row["date"])
            if not bar:
                first = None
                product = 1.0
                continue
            if first is None:
                first = bar["c"]
                continue
            product *= 1 + row[symbol]
            if not math.isclose(product, bar["c"] / first, rel_tol=1e-10):
                raise ValueError(f"Return compounding failed for {symbol}")
    manifest = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "requested_start": str(args.start), "requested_end": str(args.end), "symbol_asof": str(args.asof),
        "feed": "sip", "timeframe": "1Day", "equity_count": 30, "benchmark": "SPY",
        "sessions": len(sessions), "first_session": sessions[0], "last_session": sessions[-1],
        "adjustments": audits, "absolute_adjusted_returns_above_25pct": extreme,
        "checks": {"pagination_exhausted": True, "unique_symbol_session": True,
                   "positive_finite_ohlc": True, "ohlc_ordering": True,
                   "calendar_alignment": True, "return_compounding": True},
        "limitations": [
            "Fixed basket chosen on retrieval date, with survivorship/selection bias; not a point-in-time universe.",
            "Research groups are coarse manual labels, not historical classification records.",
            "All-adjusted closes use vendor split/dividend/spin-off adjustments as retrieved; not an audited total-return index.",
            "Daily bars use vendor aggregation; regular-session-only closing-auction prices are not independently established.",
            "First return is missing. No price or return forward-fill. Returns are decimal fractions.",
            "An observed daily close cannot be assumed executable after observing that close.",
        ],
        "requests": requests,
    }
    write_json(args.out / "manifest.json", manifest)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(args.out.iterdir()) if p.is_file() and p.name != "sha256.json"}
    write_json(args.out / "sha256.json", hashes)
    print(json.dumps({"out": str(args.out), "sessions": len(sessions),
                      "symbols": len(symbols), "bars_per_adjustment": audits["all"]["total_bars"],
                      "missing_adjusted_bars": sum(v["missing_session_count"] for v in audits["all"]["by_symbol"].values()),
                      "large_return_flags": len(extreme), "checks": manifest["checks"]}, indent=2))


if __name__ == "__main__":
    main()
