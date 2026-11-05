"""Read-only inventory and conservative replay audit of existing HFT book logs.

Originals remain in place. Only summary metadata is exported; private fill
payloads are neither copied nor printed. These files contain binary contracts.
"""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parents[1] / "Junior-Spring/HFT/Kalshi-Orderbook-Predictor"
OUT = ROOT / "market_data/datasets/hft_kalshi_archive_inventory"


def audit_file(path):
    counts = Counter()
    result = dict(path=str(path), file=path.name, bytes=path.stat().st_size,
                  invalid_json_lines=0, sequence_gaps=0, sequence_restarts=0,
                  deltas_without_valid_snapshot=0, negative_quantity_updates=0,
                  unsupported_book_messages=0, valid_applied_deltas=0,
                  snapshot_count=0, empty_snapshots=0, book_messages_without_sequence=0,
                  first_event_time=None, last_event_time=None, maximum_yes_levels=0, maximum_no_levels=0)
    books = {"yes": {}, "no": {}}
    valid = False
    sid = last_seq = None
    timestamps = []
    hasher = hashlib.sha256()
    for line in path.open("rb"):
        hasher.update(line)
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("not an object")
        except (ValueError, UnicodeDecodeError):
            result["invalid_json_lines"] += 1
            valid = False
            continue
        kind, msg = event.get("type", "unknown"), event.get("msg", {})
        counts[kind] += 1
        if kind not in ("orderbook_snapshot", "orderbook_delta", "trade"):
            continue
        # Public event timestamps only; do not retain private fill fields.
        if msg.get("ts_ms") is not None:
            stamp = float(msg["ts_ms"])/1000
        elif isinstance(msg.get("ts"), (int,float)):
            stamp = float(msg["ts"])
        elif isinstance(msg.get("ts"), str):
            try:
                stamp = datetime.fromisoformat(msg["ts"].replace("Z", "+00:00")).timestamp()
            except ValueError:
                stamp = None
        else:
            stamp = None
        if stamp is not None:
            if not timestamps:
                timestamps = [stamp,stamp]
            else:
                timestamps[0] = min(timestamps[0], stamp)
                timestamps[1] = max(timestamps[1], stamp)
        if kind == "trade":
            continue
        sequence = event.get("seq")
        if sequence is None:
            result["book_messages_without_sequence"] += 1
        if kind == "orderbook_snapshot":
            result["snapshot_count"] += 1
            if last_seq is not None and sequence is not None and sequence <= last_seq:
                result["sequence_restarts"] += 1
            books = {"yes": {}, "no": {}}
            try:
                for side in books:
                    if side + "_dollars_fp" in msg:
                        levels, divisor = msg[side + "_dollars_fp"], Decimal(1)
                    elif side + "_dollars" in msg:
                        levels, divisor = msg[side + "_dollars"], Decimal(1)
                    else:
                        levels, divisor = msg.get(side, []), Decimal(100)
                    for p,q in levels or []:
                        price, quantity = Decimal(str(p))/divisor, Decimal(str(q))
                        if not 0 < price < 1 or quantity < 0:
                            raise ValueError("invalid level")
                        if quantity:
                            books[side][price] = quantity
                valid = sequence is not None
                sid, last_seq = event.get("sid"), sequence
                if not books["yes"] and not books["no"]:
                    result["empty_snapshots"] += 1
            except (ValueError, TypeError, InvalidOperation):
                result["unsupported_book_messages"] += 1
                valid = False
        else:
            if sequence is not None and last_seq is not None and (event.get("sid") != sid or sequence != last_seq+1):
                result["sequence_gaps"] += 1
                valid = False
            last_seq = sequence
            if not valid:
                result["deltas_without_valid_snapshot"] += 1
                continue
            try:
                side = msg["side"]
                if side not in books:
                    raise ValueError("unknown side")
                price = Decimal(str(msg["price_dollars"])) if "price_dollars" in msg else Decimal(str(msg["price"]))/100
                delta = Decimal(str(msg["delta_fp"] if "delta_fp" in msg else msg["delta"]))
                if not 0 < price < 1 or not delta.is_finite():
                    raise ValueError("invalid delta")
                q = books[side].get(price, Decimal(0)) + delta
                if q < 0:
                    result["negative_quantity_updates"] += 1
                    valid = False
                    continue
                if q:
                    books[side][price] = q
                else:
                    books[side].pop(price, None)
                result["valid_applied_deltas"] += 1
            except (KeyError,ValueError,TypeError,InvalidOperation):
                result["unsupported_book_messages"] += 1
                valid = False
        result["maximum_yes_levels"] = max(result["maximum_yes_levels"],len(books["yes"]))
        result["maximum_no_levels"] = max(result["maximum_no_levels"],len(books["no"]))
    if timestamps:
        result["first_event_time"] = datetime.fromtimestamp(timestamps[0], timezone.utc).isoformat()
        result["last_event_time"] = datetime.fromtimestamp(timestamps[1], timezone.utc).isoformat()
    result.update(message_counts=dict(counts), sha256=hasher.hexdigest(), final_book_valid=valid)
    result["whole_file_book_replay_passed"] = bool(result["snapshot_count"] and not any(result[k] for k in
        ["invalid_json_lines", "sequence_gaps", "deltas_without_valid_snapshot", "negative_quantity_updates", "unsupported_book_messages", "book_messages_without_sequence"]))
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted([*SOURCE.joinpath("data").glob("KX*.csv"), *SOURCE.joinpath("collector/rawdata").glob("KX*.csv")])
    started = time.monotonic()
    results = []
    with (OUT/"files.jsonl").open("w",buffering=1) as journal:
        for i,path in enumerate(files):
            row = audit_file(path)
            journal.write(json.dumps(row)+"\n")
            results.append(row)
            (OUT/"progress.json").write_text(json.dumps(dict(files_completed=i+1,files_total=len(files),elapsed_seconds=time.monotonic()-started),indent=2)+"\n")
    messages = Counter()
    for row in results:
        messages.update(row["message_counts"])
    report = dict(files=len(results), unique_filenames=len({r["file"] for r in results}),
                  bytes=sum(r["bytes"] for r in results), message_counts=dict(messages),
                  replay_passed_files=sum(r["whole_file_book_replay_passed"] for r in results),
                  replay_flagged_files=sum(not r["whole_file_book_replay_passed"] for r in results),
                  sequence_gaps=sum(r["sequence_gaps"] for r in results),
                  negative_quantity_updates=sum(r["negative_quantity_updates"] for r in results),
                  valid_applied_deltas=sum(r["valid_applied_deltas"] for r in results),
                  first_event_time=min((r["first_event_time"] for r in results if r["first_event_time"]), default=None),
                  last_event_time=max((r["last_event_time"] for r in results if r["last_event_time"]), default=None),
                  source_instrument="Kalshi BTC 15-minute binary event contracts; not BTC perpetuals",
                  originals_modified=False, private_fill_payloads_exported=False,
                  elapsed_seconds=time.monotonic()-started,
                  limitations=["Sequence continuity does not independently prove complete exchange capture.",
                               "A negative quantity invalidates replay until a later snapshot; it is never silently clamped.",
                               "No local receipt timestamps were found in the sampled raw envelopes; event time is not network latency."])
    (OUT/"summary.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
