"""GET-only expanded equity dataset with frozen selection and resumable pages.

Uses local paper credentials only for Alpaca market data, assets, and calendar.
No account, position, order, subscription, or payment endpoints are requested.
"""
import argparse
import csv
from datetime import date, datetime, time as dt_time, timezone
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE / "datasets/equity_daily_30_2016_2026-10-27"
NY = ZoneInfo("America/New_York")
HOLDINGS_URL = "https://www.ishares.com/us/products/239726/ishares-core-s-p-500-etf/latest-holdings.csv"
PLAN = {
    "decision_date": "2026-10-28",
    "purpose": "broader cross-sectional structural research; no automatic strategy or TDA retuning",
    "universe_rule": "top 200 IVV equity holdings by published USD market value descending, ticker ascending ties; active tradable Alpaca us_equity; union original 30; SPY benchmark",
    "holdings_source": HOLDINGS_URL,
    "holdings_snapshot": "downloaded provider snapshot, recorded before price-history collection; must not postdate requested history end",
    "mapping": "spaces in provider share-class tickers become dots; verify against Alpaca active asset master; no history-based replacements",
    "share_classes": "distinct listed securities retained, including multiple classes of one issuer; not independent issuers",
    "classification": "provider sector snapshot, not historical labels; legacy manual groups retained separately",
    "requested_start": "2016-01-01", "requested_end": "2026-10-27", "symbol_asof": "2026-10-28",
    "data": "SIP 1Day OHLCV, raw and all-adjusted, full pagination; same range as original panel",
    "earlier_history_probe": "SPY raw SIP daily bars 2000-01-01 through 2015-12-31; records actual returned availability only",
    "selection_uses_strategy_outcomes": False,
    "missingness": "keep all selected symbols; calendar-aligned blanks; no forward fill, backfill or zero-return substitution; returns require adjacent observed sessions",
    "audit": "unique symbol/date, positive finite ordered OHLC, calendar, missing leading/internal/trailing, compounding, prior-panel overlap changes",
    "future_analysis": "freeze separate structural design before evaluating expanded-universe outcomes; consider 120-day shrinkage and declared longer-window baseline",
    "limitations": ["Current survivor/size selection; not a point-in-time historical investable universe.",
                    "Fund weight is a size selection proxy, not a measured liquidity guarantee.",
                    "Current sector labels and current asset tradability are not historical eligibility.",
                    "Adding names does not create independent time histories or restore untouched 2024+ data.",
                    "Adjusted returns are a vendor proxy, not an audited action-level total-return ledger.",
                    "A longer historical panel is not itself a test of long-run equilibrium mean reversion."],
    "fees": "no performance or fee experiment in this collection",
}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def write_gzip_json(path, value):
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(value, stream, separators=(",", ":"))


def read_gzip_json(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def write_csv(path, fields, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NoAuthenticatedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Unexpected redirect from authenticated fixed Alpaca endpoint")


def parse_holdings(data):
    text = data.decode("utf-8-sig")
    lines = text.splitlines()
    snapshot = next(csv.reader([next(line for line in lines if line.startswith("Fund Holdings as of"))]))[1]
    observed = datetime.strptime(snapshot, "%b %d, %Y").date()
    start = next(i for i, line in enumerate(lines) if line.startswith("Ticker,Name,"))
    rows = []
    for row in csv.DictReader(io.StringIO("\n".join(lines[start:]))):
        if row.get("Asset Class") != "Equity":
            continue
        ticker = row["Ticker"].strip()
        if not ticker or ticker == "-":
            continue
        market_value = float(row["Market Value"].replace(",", ""))
        weight_field = "Market Weight" if "Market Weight" in row else "Weight (%)"
        currency = row.get("Market Currency", row.get("Currency", "USD"))
        if currency != "USD":
            raise ValueError("Non-USD equity encountered; review frozen selection rule")
        symbol = ticker.replace(" ", ".")
        if not re.fullmatch(r"[A-Z][A-Z0-9.\-]*", symbol):
            raise ValueError(f"Unsupported provider symbol {ticker!r}")
        rows.append({"symbol": symbol, "provider_ticker": ticker, "name": row["Name"],
                     "sector_snapshot": row["Sector"], "market_value_usd": market_value,
                     "fund_weight_pct": float(row[weight_field].replace(",", "")) if row[weight_field] not in ("-", "", None) else "",
                     "provider_exchange": row.get("Exchange", "")})
    if len(rows) < 400 or len(set(r["symbol"] for r in rows)) != len(rows):
        raise ValueError("Incomplete or duplicate provider equity holdings")
    return observed, sorted(rows, key=lambda r: (-r["market_value_usd"], r["symbol"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--credentials-file", type=Path, default=HERE / ".alpaca-paper.local.json")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    if out == ORIGINAL.resolve() or ORIGINAL.resolve() in out.parents:
        parser.error("Expanded collection must not modify the original dataset")
    end, start, asof = map(date.fromisoformat, [PLAN["requested_end"], PLAN["requested_start"], PLAN["symbol_asof"]])
    if end >= datetime.now(NY).date():
        parser.error("End must be a completed prior date")
    out.mkdir(parents=True, exist_ok=True)
    plan_path = out / "collection_plan.json"
    if plan_path.exists() and json.loads(plan_path.read_text()) != PLAN:
        raise ValueError("Existing collection plan differs")
    write_json(plan_path, PLAN)  # Freeze selection before downloading histories.
    protected_before = {p.name: sha(p) for p in ORIGINAL.iterdir() if p.is_file()}
    local = json.loads(args.credentials_file.read_text()) if args.credentials_file.exists() else {}
    key = os.environ.get("APCA_API_KEY_ID") or local.get("APCA_API_KEY_ID")
    secret = os.environ.get("APCA_API_SECRET_KEY") or local.get("APCA_API_SECRET_KEY")
    if not key or not key.startswith("PK") or not secret:
        parser.error("Existing paper credentials required; never printed")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    opener = urllib.request.build_opener(NoAuthenticatedRedirect())
    log_path = out / "requests.jsonl"
    def get(host, endpoint, params):
        if host not in ("https://data.alpaca.markets", "https://paper-api.alpaca.markets"):
            raise ValueError("Unapproved host")
        allowed = ["/v2/stocks/bars", "/v2/assets", "/v2/calendar"]
        if endpoint not in allowed:
            raise ValueError("Only approved data/asset/calendar GET endpoints allowed")
        url = host + endpoint + "?" + urllib.parse.urlencode(params)
        for attempt in range(6):
            try:
                request = urllib.request.Request(url, headers=headers, method="GET")
                with opener.open(request, timeout=45) as response:
                    value = json.load(response)
                with log_path.open("a") as stream:
                    stream.write(json.dumps({"endpoint": endpoint, "params": params,
                        "received_at": datetime.now(timezone.utc).isoformat(), "http_status": 200}) + "\n")
                return value
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < 5:
                    time.sleep(min(2 ** attempt, 10)); continue
                raise RuntimeError(f"GET {endpoint}: HTTP {exc.code}") from None
            except urllib.error.URLError:
                raise RuntimeError(f"Cannot reach Alpaca {endpoint}; network access needed") from None
        raise RuntimeError("Retries exhausted")
    holdings_path = out / "ivv_holdings_source.csv"
    if not holdings_path.exists():
        try:
            request = urllib.request.Request(HOLDINGS_URL, headers={"User-Agent": "Mozilla/5.0"}, method="GET")
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read()
            parse_holdings(raw)  # Reject an error page before caching it.
            holdings_path.write_bytes(raw)
            write_json(out / "holdings_retrieval.json", {"url": HOLDINGS_URL,
                "received_at": datetime.now(timezone.utc).isoformat(), "sha256": sha(holdings_path)})
        except urllib.error.URLError:
            raise RuntimeError("Cannot reach public iShares holdings; network access needed") from None
    snapshot, holdings = parse_holdings(holdings_path.read_bytes())
    if snapshot > end:
        raise ValueError("Provider snapshot postdates end; need a dated snapshot rather than silently changing design")
    assets_path = out / "alpaca_active_assets.json.gz"
    if not assets_path.exists():
        write_gzip_json(assets_path, get("https://paper-api.alpaca.markets", "/v2/assets", {"status": "active", "asset_class": "us_equity"}))
    assets = {a["symbol"]: a for a in read_gzip_json(assets_path)}
    eligible, rejected = [], []
    for row in holdings:
        asset = assets.get(row["symbol"])
        if asset and asset["status"] == "active" and asset["tradable"] and asset["class"] == "us_equity":
            eligible.append(row)
        else:
            rejected.append({"symbol": row["symbol"], "reason": "absent or not active/tradable us_equity in current asset master"})
    if len(eligible) < 200:
        raise ValueError("Fewer than 200 eligible provider holdings")
    with (ORIGINAL / "universe.csv").open() as stream:
        legacy = {r["symbol"]: r for r in csv.DictReader(stream) if r["role"] == "equity"}
    selected = {r["symbol"]: dict(r, in_top_200=True) for r in eligible[:200]}
    source_by_symbol = {r["symbol"]: r for r in holdings}
    for symbol in legacy:
        if symbol not in selected:
            if symbol not in assets or not assets[symbol]["tradable"]:
                raise ValueError(f"Legacy symbol {symbol} unavailable; no silent replacement")
            row = source_by_symbol.get(symbol, {"symbol": symbol, "provider_ticker": symbol,
                  "name": assets[symbol]["name"], "sector_snapshot": "not_in_provider_snapshot",
                  "market_value_usd": "", "fund_weight_pct": "", "provider_exchange": ""})
            selected[symbol] = dict(row, in_top_200=False)
    universe = []
    rank = {r["symbol"]: i+1 for i, r in enumerate(eligible)}
    for symbol, row in sorted(selected.items()):
        asset = assets[symbol]
        universe.append({**row, "role": "equity", "eligible_weight_rank": rank.get(symbol, ""),
            "in_original_30": symbol in legacy, "legacy_research_group": legacy.get(symbol, {}).get("research_group", ""),
            "asset_exchange": asset["exchange"], "asset_id": asset["id"],
            "asset_tradable_snapshot": asset["tradable"], "asset_shortable_snapshot": asset.get("shortable", ""),
            "holdings_asof": str(snapshot)})
    universe.append({**{k: "" for k in universe[0]}, "symbol": "SPY", "provider_ticker": "SPY",
                     "name": "SPDR S&P 500 ETF Trust", "role": "benchmark", "in_top_200": False,
                     "in_original_30": False, "sector_snapshot": "benchmark", "holdings_asof": str(snapshot)})
    frozen_universe = out / "universe.csv"
    if frozen_universe.exists():
        with frozen_universe.open() as stream:
            prior = list(csv.DictReader(stream))
        expected = [{k: str(v) for k, v in r.items()} for r in universe]
        if prior != expected:
            raise ValueError("Selected universe differs from existing frozen snapshot")
    else:
        write_csv(frozen_universe, list(universe[0]), universe)
    write_json(out / "selection_audit.json", {"holdings_asof": str(snapshot), "provider_equities": len(holdings),
        "eligible_equities": len(eligible), "selected_equities": len(selected), "legacy_names_added": sorted(set(selected) - set(r["symbol"] for r in eligible[:200])),
        "all_original_names_retained": set(legacy) <= set(selected), "rejected_provider_symbols": rejected,
        "sectors": sorted(set(r["sector_snapshot"] for r in universe if r["role"] == "equity")),
        "universe_sha256": sha(frozen_universe), "plan_sha256": sha(plan_path)})
    print(f"Frozen universe: {len(selected)} equities + SPY; holdings as of {snapshot}", flush=True)
    if args.prepare_only:
        return
    symbols = [r["symbol"] for r in universe]
    calendar_path = out / "calendar.json"
    if not calendar_path.exists():
        write_json(calendar_path, get("https://paper-api.alpaca.markets", "/v2/calendar", {"start": str(start), "end": str(end)}))
    sessions = sorted(r["date"] for r in json.loads(calendar_path.read_text()))
    session_set = set(sessions)
    probe_path = out / "spy_pre2016_probe.json.gz"
    if not probe_path.exists():
        write_gzip_json(probe_path, get("https://data.alpaca.markets", "/v2/stocks/bars", {
            "symbols": "SPY", "timeframe": "1Day", "start": "2000-01-01T00:00:00-05:00",
            "end": "2015-12-31T23:59:59-05:00", "asof": str(asof), "feed": "sip", "adjustment": "raw", "limit": 10000}))
    probe = read_gzip_json(probe_path)
    audits, series = {}, {}
    for adjustment in ["raw", "all"]:
        collected = {symbol: [] for symbol in symbols}
        params = {"symbols": ",".join(symbols), "timeframe": "1Day",
            "start": datetime.combine(start, dt_time.min, NY).isoformat(),
            "end": datetime.combine(end, dt_time(23, 59, 59), NY).isoformat(),
            "asof": str(asof), "feed": "sip", "adjustment": adjustment, "limit": 10000, "sort": "asc"}
        seen = set(); page = 0
        while True:
            page += 1
            cache = out / f"response_{adjustment}_{page:03d}.json.gz"
            if cache.exists():
                saved = read_gzip_json(cache)
                if saved["params"] != params:
                    raise ValueError("Cached request parameters differ")
                payload = saved["response"]
            else:
                payload = get("https://data.alpaca.markets", "/v2/stocks/bars", params)
                write_gzip_json(cache, {"params": params, "response": payload})
            for symbol, values in (payload.get("bars") or {}).items():
                if symbol not in collected:
                    raise ValueError(f"Unexpected symbol {symbol}")
                collected[symbol].extend(values or [])
            if page % 5 == 0:
                print(f"{adjustment}: {page} pages, {sum(map(len, collected.values()))} bars", flush=True)
            token = payload.get("next_page_token")
            if not token:
                break
            if token in seen:
                raise ValueError("Repeated page token")
            seen.add(token); params = dict(params, page_token=token)
        indexed, mode = {}, {}
        flat = []
        for symbol, values in collected.items():
            observed = {}
            for bar in values:
                day = datetime.fromisoformat(bar["t"].replace("Z", "+00:00")).astimezone(NY).date().isoformat()
                if day in observed or day not in session_set:
                    raise ValueError(f"Duplicate or off-calendar bar {symbol} {day}")
                if not all(math.isfinite(bar[f]) and bar[f] > 0 for f in ["o", "h", "l", "c"]):
                    raise ValueError(f"Invalid OHLC {symbol} {day}")
                if not (bar["l"] <= min(bar["o"], bar["c"]) <= max(bar["o"], bar["c"]) <= bar["h"]) or bar["v"] < 0:
                    raise ValueError(f"Invalid OHLC order or volume {symbol} {day}")
                observed[day] = bar
                flat.append({"symbol": symbol, "date": day, "timestamp": bar["t"],
                    **{f: bar.get(f, "") for f in ["o", "h", "l", "c", "v", "n", "vw"]}})
            indexed[symbol] = observed
            missing = sorted(session_set - observed.keys())
            first, last = min(observed) if observed else None, max(observed) if observed else None
            internal = [d for d in missing if first and first < d < last]
            mode[symbol] = {"bars": len(observed), "first_date": first, "last_date": last,
                "missing_session_count": len(missing), "leading_missing": sum(d < first for d in missing) if first else len(missing),
                "internal_missing": len(internal), "trailing_missing": sum(d > last for d in missing) if last else 0,
                "internal_missing_dates": internal}
        write_csv(out / f"bars_{adjustment}.csv", ["symbol", "date", "timestamp", "o", "h", "l", "c", "v", "n", "vw"],
                  sorted(flat, key=lambda r: (r["date"], r["symbol"])))
        write_csv(out / f"close_{adjustment}.csv", ["date", *symbols],
                  ({"date": d, **{s: indexed[s].get(d, {}).get("c", "") for s in symbols}} for d in sessions))
        series[adjustment] = indexed
        audits[adjustment] = {"pages": page, "total_bars": len(flat), "by_symbol": mode}
        print(f"{adjustment}: complete; {len(flat)} bars", flush=True)
    simple_rows, log_rows, extreme = [], [], []
    for i, day in enumerate(sessions):
        simple, logs = {"date": day}, {"date": day}
        for symbol in symbols:
            current = series["all"][symbol].get(day)
            previous = series["all"][symbol].get(sessions[i-1]) if i else None
            if current and previous:
                ratio = current["c"] / previous["c"]
                simple[symbol], logs[symbol] = ratio-1, math.log(ratio)
                if abs(ratio-1) > .25:
                    extreme.append({"symbol": symbol, "date": day, "return": ratio-1})
            else:
                simple[symbol] = logs[symbol] = ""
        simple_rows.append(simple); log_rows.append(logs)
    write_csv(out / "returns_simple.csv", ["date", *symbols], simple_rows)
    write_csv(out / "returns_log.csv", ["date", *symbols], log_rows)
    for symbol in symbols:
        anchor, product = None, 1.
        for row in simple_rows:
            bar = series["all"][symbol].get(row["date"])
            if not bar:
                anchor, product = None, 1.; continue
            if anchor is None:
                anchor = bar["c"]; continue
            product *= 1 + row[symbol]
            if not math.isclose(product, bar["c"] / anchor, rel_tol=1e-9):
                raise ValueError("Contiguous-segment compounding failure")
    coverage = [{"symbol": s, **audits["all"]["by_symbol"][s], "role": next(r["role"] for r in universe if r["symbol"] == s)} for s in symbols]
    write_csv(out / "coverage.csv", list(coverage[0]), coverage)
    write_json(out / "large_adjusted_return_flags.json", extreme)
    if not series["all"]["SPY"] or len(series["all"]["SPY"]) != len(sessions):
        raise ValueError("Benchmark calendar incomplete")
    unchanged = all(sha(ORIGINAL / name) == expected for name, expected in protected_before.items())
    if not unchanged:
        raise ValueError("Original dataset changed unexpectedly")
    # Compare each legacy observation rather than silently splicing vendor vintages.
    overlap = {}
    for mode in ["raw", "all"]:
        changed = 0; max_delta = 0.; checked = 0
        with (ORIGINAL / f"bars_{mode}.csv").open() as stream:
            for row in csv.DictReader(stream):
                bar = series[mode][row["symbol"]].get(row["date"])
                if not bar:
                    raise ValueError("An original observation is missing in the new pull")
                delta = max(abs(float(row[f]) - bar[f]) for f in ["o", "h", "l", "c"])
                changed += delta > 1e-10; max_delta = max(max_delta, delta); checked += 1
        overlap[mode] = {"old_bars_checked": checked, "bars_with_changed_ohlc": changed, "max_abs_ohlc_price_difference": max_delta}
    manifest = {"retrieved_at": datetime.now(timezone.utc).isoformat(), "plan": PLAN,
        "holdings_asof": str(snapshot), "equity_count": len(selected), "benchmark": "SPY",
        "sessions": len(sessions), "first_session": sessions[0], "last_session": sessions[-1],
        "adjustments": audits, "earlier_SPY_probe_bars": sum(len(b) for b in (probe.get("bars") or {}).values()),
        "earlier_SPY_probe_next_page": bool(probe.get("next_page_token")),
        "earlier_probe_caveat": "SPY only, tested dates/feed/account; no global claim about all vendors or symbols",
        "large_adjusted_return_flags": len(extreme), "legacy_overlap": overlap,
        "original_dataset_sha256_before": protected_before,
        "checks": {"all_pages_consumed": True, "unique_symbol_session": True, "valid_ohlcv": True,
                   "calendar_alignment": True, "no_forward_fill": True, "adjacent_session_returns": True,
                   "contiguous_compounding": True, "original_dataset_unchanged": unchanged},
        "source_sha256": sha(Path(__file__))}
    write_json(out / "manifest.json", manifest)
    write_json(out / "sha256.json", {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != "sha256.json"})
    print(json.dumps({"dataset": str(out), "equities": len(selected), "sessions": len(sessions),
        "bars_per_adjustment": audits["all"]["total_bars"],
        "full_history_equities": sum(r["bars"] == len(sessions) and r["role"] == "equity" for r in coverage),
        "internal_missing_adjusted_bars": sum(r["internal_missing"] for r in coverage),
        "pre2016_SPY_bars": manifest["earlier_SPY_probe_bars"], "legacy_overlap": overlap,
        "checks": manifest["checks"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
