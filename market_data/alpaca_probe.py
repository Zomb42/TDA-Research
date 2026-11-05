"""Small read-only Alpaca data probe. Credentials are excluded from outputs.

Run with the tda environment (websocket-client is already installed there).
No account balances, positions, or orders are requested; all HTTP calls are GET.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import getpass
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

PAPER = "https://paper-api.alpaca.markets"
DATA = "https://data.alpaca.markets"
SECRET_VALUES = []


def credentials(path):
    local = json.loads(path.read_text()) if path.exists() else {}
    key = os.environ.get("APCA_API_KEY_ID") or local.get("APCA_API_KEY_ID") or getpass.getpass("Paper API key (hidden): ")
    secret = os.environ.get("APCA_API_SECRET_KEY") or local.get("APCA_API_SECRET_KEY") or getpass.getpass("Paper API secret (hidden): ")
    if not key.startswith("PK") or not secret:
        raise SystemExit("This probe requires paper credentials (PK prefix).")
    SECRET_VALUES.extend([key, secret])
    return key, secret


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def clean(value):
    encoded = json.dumps(value)
    for secret in SECRET_VALUES:
        if secret:
            encoded = encoded.replace(secret, "[REDACTED]")
    return json.loads(encoded)


def save_json(path, data):
    path.write_text(json.dumps(clean(data), indent=2) + "\n")


def save_csv(path, rows):
    if not rows:
        return
    rows = clean(rows)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()})


def get(name, host, endpoint, params, headers, out):
    if host not in (PAPER, DATA):
        raise ValueError("Only the paper trading and market-data hosts are allowed")
    url = host + endpoint
    if params:
        url += "?" + urllib.parse.urlencode(params)
    meta = {"name": name, "method": "GET", "url": url, "received_at": utc_now()}
    payload = None
    try:
        request = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=20) as response:
            meta["http_status"] = response.status
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        meta["http_status"] = error.code
        try:
            meta["error"] = json.loads(error.read())
        except (ValueError, UnicodeError):
            meta["error"] = "Non-JSON HTTP error"
    except Exception as error:
        meta["error"] = {"type": type(error).__name__, "message": str(error)}
    if payload is not None:
        save_json(out / (name + ".json"), payload)
        for kind in ("trades", "quotes", "bars"):
            data = payload.get(kind, {}) if isinstance(payload, dict) else {}
            if isinstance(data, dict):
                data = {s: items if isinstance(items, list) else [items] if isinstance(items, dict) else []
                        for s, items in data.items()}
                rows = [{"symbol": symbol, **row} for symbol, items in data.items()
                        for row in (items or [])]
                if rows:
                    save_csv(out / (name + ".csv"), rows)
                    meta["records_by_symbol"] = {s: len(items or []) for s, items in data.items()}
                    meta["fields"] = sorted(set().union(*(row.keys() for row in rows)))
                    meta["first_timestamp"] = min(row["t"] for row in rows if "t" in row)
                    meta["last_timestamp"] = max(row["t"] for row in rows if "t" in row)
        if isinstance(payload, dict):
            meta["has_more_pages"] = bool(payload.get("next_page_token"))
            contracts = payload.get("option_contracts")
            if contracts is not None:
                meta["contract_count"] = len(contracts)
                save_csv(out / (name + ".csv"), contracts)
            snapshots = payload.get("snapshots")
            if snapshots:
                meta["snapshot_count"] = len(snapshots)
                meta["snapshot_fields"] = sorted(set().union(*(item.keys() for item in snapshots.values())))
                save_csv(out / (name + ".csv"), [{"symbol": s, **item} for s, item in snapshots.items()])
            books = payload.get("orderbooks", {})
            if books:
                meta["depth_by_symbol"] = {s: {"bids": len(book.get("b", [])),
                                                    "asks": len(book.get("a", [])),
                                                    "timestamp": book.get("t")}
                                                for s, book in books.items()}
                rows = [{"symbol": s, "side": side, "rank": i + 1,
                         "price": level["p"], "size": level["s"],
                         "exchange_timestamp": book.get("t")}
                        for s, book in books.items()
                        for side, field in (("bid", "b"), ("ask", "a"))
                        for i, level in enumerate(book.get(field, []))]
                save_csv(out / (name + ".csv"), rows)
    print(json.dumps(clean(meta)), flush=True)
    return meta, payload


def stream(name, url, subscription, key, secret, seconds, out):
    """Capture received data only. The authentication request is never logged."""
    import websocket

    meta = {"name": name, "url": url, "started_at": utc_now(),
            "requested_seconds": seconds, "subscription": subscription,
            "counts": {}, "authenticated": False}
    events, depth_rows, books = [], [], {}
    reset_symbols = set()
    ws = None
    try:
        ws = websocket.create_connection(url, timeout=10, enable_multithread=True)
        greeting = json.loads(ws.recv())
        events.extend(greeting)
        ws.send(json.dumps({"action": "auth", "key": key, "secret": secret}))
        ack = json.loads(ws.recv())
        events.extend(ack)
        if not any(m.get("T") == "success" and m.get("msg") == "authenticated" for m in ack):
            meta["authentication_response"] = ack
            return meta
        meta["authenticated"] = True
        ws.send(json.dumps({"action": "subscribe", **subscription}))
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and len(events) < 5000:
            ws.settimeout(min(2, max(0.1, deadline - time.monotonic())))
            try:
                messages = json.loads(ws.recv())
            except websocket.WebSocketTimeoutException:
                continue
            if not isinstance(messages, list):
                messages = [messages]
            for message in messages:
                message = {"received_at": utc_now(), **message}
                events.append(message)
                kind = message.get("T", "unknown")
                meta["counts"][kind] = meta["counts"].get(kind, 0) + 1
                if kind == "error":
                    meta.setdefault("stream_errors", []).append(message)
                if kind != "o":
                    continue
                symbol = message["S"]
                if message.get("r"):
                    books[symbol] = {"b": {}, "a": {}}
                    reset_symbols.add(symbol)
                if symbol not in reset_symbols:
                    meta["updates_before_reset"] = meta.get("updates_before_reset", 0) + 1
                    continue
                book = books[symbol]
                for side in ("b", "a"):
                    for level in message.get(side, []):
                        price, size = Decimal(str(level["p"])), Decimal(str(level["s"]))
                        if not size:
                            book[side].pop(price, None)
                        else:
                            book[side][price] = size
                if book["b"] and book["a"]:
                    bid, ask = max(book["b"]), min(book["a"])
                    depth_rows.append({"symbol": symbol, "exchange_timestamp": message["t"],
                                       "received_at": message["received_at"],
                                       "bid_levels": len(book["b"]), "ask_levels": len(book["a"]),
                                       "best_bid": str(bid), "best_ask": str(ask),
                                       "spread": str(ask - bid),
                                       "displayed_bid_quantity": str(sum(book["b"].values())),
                                       "displayed_ask_quantity": str(sum(book["a"].values()))})
        meta["event_cap_reached"] = len(events) >= 5000
        meta["reset_symbols"] = sorted(reset_symbols)
        meta["reconstructed_depth_rows"] = len(depth_rows)
        meta["final_depth_by_symbol"] = {s: {"bids": len(book["b"]), "asks": len(book["a"])}
                                               for s, book in books.items()}
        meta["max_depth_by_symbol"] = {s: {"bids": max(r["bid_levels"] for r in depth_rows if r["symbol"] == s),
                                               "asks": max(r["ask_levels"] for r in depth_rows if r["symbol"] == s)}
                                            for s in {r["symbol"] for r in depth_rows}}
    except Exception as error:
        meta["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        if ws is not None:
            ws.close()
        with (out / (name + ".jsonl")).open("w") as f:
            for event in events:
                f.write(json.dumps(clean(event)) + "\n")
        save_csv(out / (name + "_depth.csv"), depth_rows)
        for kind, suffix in (("t", "trades"), ("q", "quotes")):
            save_csv(out / (name + "_" + suffix + ".csv"),
                     [m for m in events if m.get("T") == kind])
        meta["finished_at"] = utc_now()
        print(json.dumps(clean(meta)), flush=True)
    return meta


def probe_options(request, server_now, summary):
    """Compare indicative and OPRA access for a few near-money call contracts."""
    latest = request("options_underlying_latest_trades", DATA, "/v2/stocks/trades/latest",
                     {"symbols": "AAPL,SPY", "feed": "iex"}) or {}
    contracts = []
    today = server_now.date()
    for underlying in ("AAPL", "SPY"):
        price = latest.get("trades", {}).get(underlying, {}).get("p")
        params = {"underlying_symbols": underlying, "type": "call", "status": "active",
                  "expiration_date_gte": (today + timedelta(days=1)).isoformat(),
                  "expiration_date_lte": (today + timedelta(days=7)).isoformat(), "limit": 4}
        if price:
            params.update(strike_price_gte=round(price - 5, 2), strike_price_lte=round(price + 5, 2))
        payload = request("options_contracts_" + underlying.lower(), PAPER, "/v2/options/contracts", params)
        contracts.extend((payload or {}).get("option_contracts", []))
    symbols = ",".join(c["symbol"] for c in contracts)
    summary["selected_option_symbols"] = [c["symbol"] for c in contracts]
    if not symbols:
        summary["options_note"] = "No contracts returned for the small selection window."
        return
    prior_summary = Path(__file__).parent / "samples/alpaca_2026-10-12/summary.json"
    window = json.loads(prior_summary.read_text()).get("stock_history_window") if prior_summary.exists() else None
    if not window or not window["start"].startswith(today.isoformat()):
        history_end = server_now.astimezone(timezone.utc) - timedelta(minutes=20)
        window = {"start": (history_end - timedelta(minutes=5)).isoformat(), "end": history_end.isoformat()}
    summary["options_history_window"] = window
    for feed in ("indicative", "opra"):
        params = {"symbols": symbols, "feed": feed}
        for kind in ("trades", "quotes"):
            request(f"options_latest_{feed}_{kind}", DATA, f"/v1beta1/options/{kind}/latest", params)
        request("options_" + feed + "_snapshots", DATA, "/v1beta1/options/snapshots", params)
    request("options_historical_trades", DATA, "/v1beta1/options/trades",
            {"symbols": symbols, **window, "limit": 1000, "sort": "asc"})
    request("options_historical_bars", DATA, "/v1beta1/options/bars",
            {"symbols": symbols, **window, "timeframe": "1Min", "limit": 1000})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=15)
    parser.add_argument("--credentials-file", type=Path,
                        default=Path(__file__).parent / ".alpaca-paper.local.json")
    parser.add_argument("--options-only", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.seconds <= 60:
        parser.error("Keep this small probe between 1 and 60 seconds")
    key, secret = credentials(args.credentials_file)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    args.out.mkdir(parents=True, exist_ok=True)
    summary = {"started_at": utc_now(), "read_only": True,
               "history_sampling": "One page, at most 1000 records per request; check has_more_pages.",
               "results": []}

    def request(name, host, endpoint, params=None):
        meta, payload = get(name, host, endpoint, params, headers, args.out)
        summary["results"].append(meta)
        return payload

    clock = request("paper_clock", PAPER, "/v2/clock")
    if not clock or not clock.get("timestamp"):
        save_json(args.out / "summary.json", summary)
        raise SystemExit("Paper authentication/clock failed; stopped before further requests.")
    server_now = datetime.fromisoformat(clock["timestamp"].replace("Z", "+00:00"))
    summary["server_timestamp"] = clock["timestamp"]
    if args.options_only:
        probe_options(request, server_now, summary)
        summary["finished_at"] = utc_now()
        save_json(args.out / "summary.json", summary)
        print("Saved sanitized options results to " + str(args.out), flush=True)
        return
    for symbol in ("AAPL", "SPY"):
        request("asset_" + symbol.lower(), PAPER, "/v2/assets/" + symbol)
    sessions = request("calendar", PAPER, "/v2/calendar",
                       {"start": (server_now.date() - timedelta(days=14)).isoformat(),
                        "end": server_now.date().isoformat()})
    from zoneinfo import ZoneInfo
    completed = []
    for session in sessions or []:
        close = datetime.fromisoformat(session["date"] + "T" + session["close"]).replace(tzinfo=ZoneInfo("America/New_York"))
        if close < server_now:
            completed.append(session)
    if completed:
        session = completed[-1]
        opened = datetime.fromisoformat(session["date"] + "T" + session["open"]).replace(tzinfo=ZoneInfo("America/New_York"))
        start = opened.astimezone(timezone.utc).isoformat()
        end = (opened + timedelta(minutes=5)).astimezone(timezone.utc).isoformat()
        summary["stock_history_window"] = {"start": start, "end": end}
        for feed in ("iex", "sip"):
            for symbol in ("AAPL", "SPY"):
                for kind in ("trades", "quotes"):
                    request(f"stock_{feed}_{symbol.lower()}_{kind}", DATA, "/v2/stocks/" + kind,
                            {"symbols": symbol, "feed": feed, "start": start, "end": end,
                             "limit": 1000, "sort": "asc"})
            request("stock_" + feed + "_bars", DATA, "/v2/stocks/bars",
                    {"symbols": "AAPL,SPY", "feed": feed, "start": start, "end": end,
                     "timeframe": "1Min", "limit": 1000, "adjustment": "raw"})
    for feed in ("iex", "sip"):
        for kind in ("trades", "quotes"):
            request(f"stock_latest_{feed}_{kind}", DATA, f"/v2/stocks/{kind}/latest",
                    {"symbols": "AAPL,SPY", "feed": feed})
    request("crypto_us_latest_orderbooks", DATA, "/v1beta3/crypto/us/latest/orderbooks",
            {"symbols": "BTC/USD,ETH/USD"})
    recent_end = server_now.astimezone(timezone.utc) - timedelta(seconds=5)
    for kind in ("trades", "quotes"):
        request("crypto_us_" + kind, DATA, "/v1beta3/crypto/us/" + kind,
                {"symbols": "BTC/USD,ETH/USD", "start": (recent_end - timedelta(minutes=5)).isoformat(),
                 "end": recent_end.isoformat(), "limit": 1000, "sort": "asc"})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(stream, "stock_iex_stream", "wss://stream.data.alpaca.markets/v2/iex",
                               {"trades": ["AAPL", "SPY"], "quotes": ["AAPL", "SPY"]},
                               key, secret, args.seconds, args.out),
                   pool.submit(stream, "crypto_us_stream", "wss://stream.data.alpaca.markets/v1beta3/crypto/us",
                               {"trades": ["BTC/USD", "ETH/USD"], "quotes": ["BTC/USD", "ETH/USD"],
                                "orderbooks": ["BTC/USD", "ETH/USD"]},
                               key, secret, args.seconds, args.out)]
        summary["results"].extend(f.result() for f in futures)
    summary["finished_at"] = utc_now()
    save_json(args.out / "summary.json", summary)
    print("Saved sanitized probe results to " + str(args.out), flush=True)


if __name__ == "__main__":
    main()
