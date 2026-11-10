"""Independently replay a completed public BTC-perp capture, including gzip files.

No network or credentials. Validates recorded bytes/checkpoints and reports gaps;
it cannot prove that the exchange published every order action.
"""
import argparse
from collections import Counter
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path


def rows(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def audit(out):
    manifest = json.loads((out / "manifest.json").read_text())
    journal = out / manifest.get("journal_file", "messages.jsonl")
    checkpoints = out / manifest.get("checkpoint_file", "checkpoints.jsonl")
    expected = {}
    for row in rows(checkpoints):
        key = (row["epoch"], row["received_at"], row["sid"], row["seq"])
        if key in expected:
            raise ValueError("duplicate checkpoint identity")
        expected[key] = row
    checkpoint_count = len(expected)
    counts, controls, bounds = Counter(), Counter(), {}
    sides = {"bid": {}, "ask": {}}
    epoch = sid = seq = None
    ready = False
    matched = book_errors = book_gaps = trade_gaps = duplicate_trades = 0
    max_levels = {"bid": 0, "ask": 0}
    trade_sequences, trade_ids, ack_channels = {}, set(), set()
    receipt_start = receipt_end = None
    unexpected_types = set()
    for row in rows(journal):
        if "message" not in row:
            controls[row.get("control", "unknown")] += 1
            continue
        if epoch != row["epoch"]:
            epoch = row["epoch"]
            sides = {"bid": {}, "ask": {}}
            sid = seq = None
            ready = False
        event = row["message"]
        kind = event.get("type", "unknown")
        counts[kind] += 1
        msg = event.get("msg", {})
        receipt_start = receipt_start or row["received_at"]
        receipt_end = row["received_at"]
        if kind == "subscribed":
            ack_channels.add(msg["channel"])
        elif kind not in ("orderbook_snapshot", "orderbook_delta", "trade", "ticker", "error", "unsubscribed"):
            unexpected_types.add(kind)
        if kind in ("orderbook_snapshot", "orderbook_delta", "trade", "ticker"):
            if msg.get("market_ticker") != manifest["ticker"]:
                raise ValueError("unexpected market in filtered subscription")
            timestamp = msg.get("ts_ms", event.get("ts_ms"))
            if timestamp is not None:
                value = bounds.setdefault(kind, {"min_ts_ms": timestamp, "max_ts_ms": timestamp})
                value["min_ts_ms"] = min(value["min_ts_ms"], timestamp)
                value["max_ts_ms"] = max(value["max_ts_ms"], timestamp)
        if kind == "trade":
            trade_key = (epoch, event["sid"])
            previous = trade_sequences.get(trade_key)
            if previous is not None and event["seq"] != previous+1:
                trade_gaps += 1
            trade_sequences[trade_key] = event["seq"]
            identifier = msg["trade_id"]
            duplicate_trades += int(identifier in trade_ids)
            trade_ids.add(identifier)
        if kind not in ("orderbook_snapshot", "orderbook_delta"):
            continue
        try:
            if kind == "orderbook_snapshot":
                replacement = {"bid": {}, "ask": {}}
                for side in replacement:
                    for price, quantity in msg[side]:
                        price, quantity = Decimal(price), Decimal(quantity)
                        if not price.is_finite() or not quantity.is_finite() or price <= 0 or quantity < 0 or price in replacement[side]:
                            raise ValueError("invalid snapshot level")
                        if quantity:
                            replacement[side][price] = quantity
                sides, sid, seq, ready = replacement, event["sid"], event["seq"], True
            else:
                if not ready or event["sid"] != sid:
                    raise ValueError("delta without matching valid snapshot")
                if event["seq"] != seq+1:
                    book_gaps += 1
                    raise ValueError("book sequence gap")
                side = msg["side"]
                price, delta = Decimal(msg["price"]), Decimal(msg["delta"])
                if not price.is_finite() or not delta.is_finite() or price <= 0:
                    raise ValueError("nonfinite or invalid delta")
                quantity = sides[side].get(price, Decimal(0)) + delta
                if quantity < 0:
                    raise ValueError("negative resulting quantity")
                if quantity:
                    sides[side][price] = quantity
                else:
                    sides[side].pop(price, None)
                seq = event["seq"]
        except (ValueError, KeyError, ArithmeticError):
            ready = False
            book_errors += 1
            continue
        for side in sides:
            max_levels[side] = max(max_levels[side], len(sides[side]))
        key = (epoch, row["received_at"], sid, seq)
        if key in expected:
            saved = expected.pop(key)
            for side in sides:
                restored = {Decimal(p): Decimal(q) for p,q in saved[side]}
                if restored != sides[side] or len(restored) != len(saved[side]):
                    raise ValueError("checkpoint differs from independent raw replay")
            matched += 1
    checks = {
        "all_message_counts_match_manifest": dict(counts) == manifest["message_counts"],
        "all_checkpoints_match_exact_decimal_replay": not expected and matched == manifest["checkpoints"] == checkpoint_count,
        "book_gap_count_matches_manifest": book_gaps == manifest["sequence_gaps"],
        "book_error_count_matches_manifest": book_errors == manifest["reconstruction_errors"],
        "trade_gap_count_matches_manifest": trade_gaps == manifest.get("trade_sequence_gaps", 0),
        "all_requested_channels_acknowledged": set(manifest["allowed_channels"]) == ack_channels,
        "no_unexpected_channel_types": not unexpected_types,
        "capture_has_snapshot_and_deltas_and_trades": all(counts[k] > 0 for k in ("orderbook_snapshot", "orderbook_delta", "trade")),
    }
    hashes = {"journal_sha256": sha256(journal), "checkpoint_sha256": sha256(checkpoints)}
    for name, value in hashes.items():
        if name in manifest:
            checks[name+"_matches_manifest"] = value == manifest[name]
    result = {
        "passed": all(checks.values()), "checks": checks,
        "message_counts": dict(counts), "control_counts": dict(controls),
        "checkpoints_replayed_exactly": matched, "book_sequence_gaps": book_gaps,
        "book_reconstruction_errors": book_errors, "trade_sequence_gaps": trade_gaps,
        "duplicate_trade_ids": duplicate_trades, "max_price_levels": max_levels,
        "receipt_start_utc": receipt_start, "receipt_end_utc": receipt_end,
        "exchange_timestamp_bounds": bounds,
        "capture_state": manifest["state"], "gap_windows": manifest.get("gap_windows", []),
        "stored_journal_bytes": journal.stat().st_size,
        "stored_checkpoint_bytes": checkpoints.stat().st_size, **hashes,
        "scope": "Internal capture/replay integrity; aggregated public L2, not exchange-wide L3 completeness",
    }
    (out / "replay_validation.json").write_text(json.dumps(result, indent=2)+"\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    result = audit(parser.parse_args().out)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)
