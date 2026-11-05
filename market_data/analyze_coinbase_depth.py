"""Offline replay and storage estimate for the bounded public Coinbase probe."""
from collections import Counter
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "samples/coinbase_depth_2026-10-29"


def main():
    report = json.loads((OUT / "summary.json").read_text())
    probe = report["live_volume_probe"]
    book = {"bid": {}, "offer": {}}
    previous = None
    gaps = snapshots = updates = negative = crossed = 0
    counts = Counter()
    steady_lines = []
    first_quote = None
    for line in gzip.open(OUT / "public_stream.jsonl.gz", "rt"):
        message = json.loads(line)["message"]
        sequence = message.get("sequence_num")
        if isinstance(sequence, int):
            if previous is not None and sequence != previous + 1:
                gaps += 1
            previous = sequence
        counts[message["channel"]] += 1
        is_snapshot = False
        for event in message.get("events", []):
            if message["channel"] != "l2_data":
                continue
            assert event["product_id"] == "BTC-USD"
            if event["type"] == "snapshot":
                book = {"bid": {}, "offer": {}}
                snapshots += 1
                is_snapshot = True
            else:
                assert snapshots and event["type"] == "update"
            for update in event["updates"]:
                price, size = Decimal(update["price_level"]), Decimal(update["new_quantity"])
                levels = book[update["side"]]
                if size < 0:
                    negative += 1
                    raise ValueError("Negative displayed quantity")
                if size == 0:
                    levels.pop(price, None)
                else:
                    levels[price] = size
                updates += not is_snapshot
            assert book["bid"] and book["offer"]
            quote = {"bid": str(max(book["bid"])), "ask": str(min(book["offer"]))}
            first_quote = first_quote or quote
            crossed += Decimal(quote["bid"]) > Decimal(quote["ask"])
        if not is_snapshot:
            steady_lines.append(line)
    compressed_steady = len(gzip.compress("".join(steady_lines).encode(), mtime=0))
    seconds = probe["steady_observation_seconds"]
    result = dict(
        source_sha256=hashlib.sha256((OUT / "public_stream.jsonl.gz").read_bytes()).hexdigest(),
        sequenced_messages=sum(counts.values()),
        connection_sequence_discontinuities=gaps,
        sequence_scope="All subscribed channels on this captured connection, not L2 alone",
        snapshots=snapshots,
        replacement_level_updates=updates,
        negative_quantities=negative,
        crossed_books_after_l2_event=crossed,
        initial_best_quote=first_quote,
        final_best_quote=quote,
        final_bid_levels=len(book["bid"]), final_ask_levels=len(book["offer"]),
        steady_gzip_bytes=compressed_steady,
        estimated_gzip_mb_per_hour=compressed_steady / seconds * 3600 / 1e6,
        estimated_gzip_gb_per_day=compressed_steady / seconds * 86400 / 1e9,
        storage_scope="Raw receipt envelopes for L2, public trades, subscriptions and heartbeats; initial L2 snapshot excluded",
        limitation="Short local replay, not an independently reconciled historical archive or a long-run traffic forecast",
    )
    assert gaps == 0 and snapshots == 1 and negative == 0 and crossed == 0
    probe.pop("l2_sequence_discontinuities", None)
    probe["connection_sequence_discontinuities"] = gaps
    report["offline_replay"] = result
    (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    (OUT / "replay_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
