"""Bounded Kalshi BTC-perp MARKET DATA ONLY recorder and L2 reconstructor.

Network surface: one authenticated WebSocket GET; fixed subscriptions to
orderbook_delta and trade. No trading HTTP client, account API, or user channels.
Existing credentials are read in place and never logged or copied to outputs.
"""
import argparse
import base64
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import time
import urllib.request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import websocket

ROOT = Path(__file__).resolve().parents[1]
HFT = ROOT.parents[1] / "Junior-Spring/HFT/Kalshi-Orderbook-Predictor"
WS_PATH = "/trade-api/ws/v2/margin"
WS_URL = "wss://external-api-margin-ws.kalshi.com" + WS_PATH
TICKER = "KXBTCPERP"


class InvalidBook(ValueError):
    pass


class PerpBook:
    def __init__(self):
        self.sides = {"bid": {}, "ask": {}}
        self.sid = self.seq = None
        self.ready = False

    def apply(self, event):
        kind = event["type"]
        if kind not in ("orderbook_snapshot", "orderbook_delta"):
            return False
        msg = event["msg"]
        if msg.get("market_ticker") != TICKER:
            raise InvalidBook("unexpected_market")
        sid, seq = event["sid"], event["seq"]
        if kind == "orderbook_snapshot":
            sides = {"bid": {}, "ask": {}}
            for side in sides:
                for price, quantity in msg.get(side, []):
                    p, q = Decimal(price), Decimal(quantity)
                    if not p.is_finite() or not q.is_finite() or p <= 0 or q < 0 or p in sides[side]:
                        raise InvalidBook("invalid_snapshot_level")
                    if q:
                        sides[side][p] = q
            self.sides, self.sid, self.seq, self.ready = sides, sid, seq, True
        else:
            if not self.ready or sid != self.sid:
                raise InvalidBook("delta_before_snapshot_or_wrong_subscription")
            if seq != self.seq + 1:
                self.ready = False
                raise InvalidBook("sequence_gap")
            side = msg["side"]
            if side not in self.sides:
                raise InvalidBook("unknown_side")
            p, delta = Decimal(msg["price"]), Decimal(msg["delta"])
            if not p.is_finite() or not delta.is_finite() or p <= 0:
                raise InvalidBook("invalid_delta")
            quantity = self.sides[side].get(p, Decimal(0)) + delta
            if quantity < 0:
                self.ready = False
                raise InvalidBook("negative_resulting_quantity")
            if quantity:
                self.sides[side][p] = quantity
            else:
                self.sides[side].pop(p, None)
            self.seq = seq
        return True

    def checkpoint(self):
        bid = max(self.sides["bid"], default=None)
        ask = min(self.sides["ask"], default=None)
        return dict(sid=self.sid, seq=self.seq, ready=self.ready,
                    crossed_or_locked=bool(bid is not None and ask is not None and bid >= ask),
                    bid=[[str(p), str(q)] for p,q in sorted(self.sides["bid"].items(), reverse=True)],
                    ask=[[str(p), str(q)] for p,q in sorted(self.sides["ask"].items())])


def headers(credentials_path, private_key_path):
    key_id = json.loads(credentials_path.read_text())["key_id"]
    private_key = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
    timestamp = str(int(time.time()*1000))
    signature = private_key.sign((timestamp + "GET" + WS_PATH).encode(),
                                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
                                hashes.SHA256())
    return {"KALSHI-ACCESS-KEY": key_id, "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode()}


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials-file", type=Path, default=HFT / "secrets/kalshi_credentials.json")
    parser.add_argument("--private-key-file", type=Path, default=HFT / "secrets/TestExample1.pem")
    parser.add_argument("--seconds", type=int, default=3600)
    parser.add_argument("--max-mb", type=int, default=256)
    parser.add_argument("--gzip", action="store_true", help="Compress journals losslessly as they are written")
    parser.add_argument("--include-ticker", action="store_true", help="Also retain public prices/marks/funding/open-interest ticker context")
    parser.add_argument("--max-consecutive-errors", type=int, default=5, help="Stop after this many consecutive failures; 0 retries until the duration/cap")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.seconds <= 0 or args.max_mb <= 0:
        parser.error("positive duration and byte cap required")
    if args.max_consecutive_errors < 0:
        parser.error("max-consecutive-errors must be nonnegative")
    args.out.mkdir(parents=True, exist_ok=True)
    suffix = ".jsonl.gz" if args.gzip else ".jsonl"
    journal_path = args.out / ("messages" + suffix)
    checkpoint_path = args.out / ("checkpoints" + suffix)
    if any(args.out.glob("messages.jsonl*")) or checkpoint_path.exists():
        raise SystemExit("Existing journal: select a new directory")
    # Fail before connecting if either credential is missing or cannot be read.
    headers(args.credentials_file, args.private_key_file)
    started = time.monotonic()
    deadline = started + args.seconds
    stopped = False
    def stop(signum, frame):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    counts = Counter()
    channels = ["orderbook_delta", "trade"] + (["ticker"] if args.include_ticker else [])
    stats = dict(pid=os.getpid(), state="starting", started_at=datetime.now(timezone.utc).isoformat(),
                 planned_seconds=args.seconds, max_bytes=args.max_mb*1024*1024, ticker=TICKER,
                 planned_end_at=datetime.fromtimestamp(time.time()+args.seconds, timezone.utc).isoformat(),
                 endpoint=WS_URL, allowed_channels=channels,
                 order_actions_available=False, bytes_written=0, connections=0, sequence_gaps=0,
                 reconstruction_errors=0, connection_errors=0, checkpoints=0,
                 connection_attempts=0, consecutive_connection_errors=0,
                 trade_sequence_gaps=0, last_sequences={}, gap_windows=[],
                 python_executable=sys.executable, compression="gzip" if args.gzip else "none",
                 journal_file=journal_path.name, checkpoint_file=checkpoint_path.name,
                 byte_cap_basis="uncompressed journal envelopes; checkpoints additional",
                 authenticated_connection_established=False, first_snapshot_received_at=None)
    def status():
        stats.update(updated_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic()-started,
                     message_counts=dict(counts))
        atomic_json(args.out / "status.json", stats)
    status()
    # Preserve the instrument's unit/contract metadata using a public GET only.
    try:
        url = "https://external-api.kalshi.com/trade-api/v2/margin/markets/" + TICKER
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = response.read()
        (args.out / "market.json").write_bytes(payload)
        stats["market_metadata_sha256"] = hashlib.sha256(payload).hexdigest()
        stats["market_metadata_received_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as error:
        stats["market_metadata_error_type"] = type(error).__name__
    opener = (lambda p: gzip.open(p, "xt", encoding="utf-8", compresslevel=3)) if args.gzip else (lambda p: p.open("x", buffering=1))
    with opener(journal_path) as raw, opener(checkpoint_path) as checkpoints:
        def journal(value):
            line = json.dumps(value, separators=(",", ":")) + "\n"
            raw.write(line)
            stats["bytes_written"] += len(line.encode())
        last_healthy_receive = None
        pending_gap = None
        while not stopped and time.monotonic() < deadline and stats["bytes_written"] < stats["max_bytes"]:
            ws = None
            book = PerpBook()
            stats["connection_attempts"] += 1
            epoch = stats["connection_attempts"]
            sequences = {}
            try:
                if shutil.disk_usage(args.out).free < 1024**3:
                    stats["state"] = "low_disk_space"
                    break
                # The signed header values never enter logs or saved journals.
                ws = websocket.create_connection(WS_URL, header=headers(args.credentials_file, args.private_key_file),
                                                 timeout=min(10, max(1, deadline-time.monotonic())))
                ws.settimeout(2)
                stats["connections"] += 1
                stats["authenticated_connection_established"] = True
                stats["state"] = "awaiting_snapshot"
                journal(dict(control="connected", epoch=epoch, received_at=datetime.now(timezone.utc).isoformat()))
                # These are the ONLY application messages this recorder sends.
                for identifier, channel in enumerate(channels, 1):
                    params = dict(channels=[channel], market_ticker=TICKER)
                    if channel == "orderbook_delta":
                        params["update_interval_ms"] = 0
                    ws.send(json.dumps(dict(id=identifier, cmd="subscribe", params=params)))
                last_checkpoint = last_status = time.monotonic()
                last_receive = time.monotonic()
                while not stopped and time.monotonic() < deadline and stats["bytes_written"] < stats["max_bytes"]:
                    try:
                        message = ws.recv()
                        if not message:
                            raise ConnectionError("stream_closed")
                    except websocket.WebSocketTimeoutException:
                        status()
                        if time.monotonic()-last_receive > 30:
                            raise ConnectionError("no_data_for_30_seconds")
                        continue
                    received_at = datetime.now(timezone.utc).isoformat()
                    received_unix_ns = time.time_ns()
                    received_monotonic_ns = time.monotonic_ns()
                    last_receive = time.monotonic()
                    event = json.loads(message)
                    journal(dict(epoch=epoch, received_at=received_at,
                                 received_unix_ns=received_unix_ns,
                                 received_monotonic_ns=received_monotonic_ns, message=event))
                    kind = event.get("type", "unknown")
                    counts[kind] += 1
                    stats["last_message_received_at"] = received_at
                    if kind == "error":
                        stats["server_error_code"] = event.get("msg", {}).get("code")
                        raise ConnectionError("server_subscription_error")
                    sid, seq = event.get("sid"), event.get("seq")
                    if sid is not None and seq is not None:
                        previous = sequences.get(sid)
                        if kind == "trade" and previous is not None and seq != previous+1:
                            stats["trade_sequence_gaps"] += 1
                            journal(dict(control="trade_sequence_gap", epoch=epoch,
                                         previous_seq=previous, seq=seq, received_at=received_at))
                        sequences[sid] = seq
                        stats["last_sequences"] = {str(k): v for k,v in sequences.items()}
                    try:
                        changed = book.apply(event)
                    except InvalidBook as error:
                        stats["reconstruction_errors"] += 1
                        if str(error) == "sequence_gap":
                            stats["sequence_gaps"] += 1
                        journal(dict(control="book_invalid", epoch=epoch, reason=str(error), received_at=received_at))
                        raise
                    if kind == "orderbook_snapshot":
                        if pending_gap is not None:
                            pending_gap["next_snapshot_received_at"] = received_at
                            journal(dict(control="gap_ended_at_snapshot", **pending_gap))
                            pending_gap = None
                        stats["first_snapshot_received_at"] = stats["first_snapshot_received_at"] or received_at
                        stats["state"] = "collecting"
                        stats["consecutive_connection_errors"] = 0
                        status()
                    if kind in ("orderbook_snapshot", "orderbook_delta") and book.ready:
                        last_healthy_receive = received_at
                    if changed and (kind == "orderbook_snapshot" or time.monotonic()-last_checkpoint >= 5):
                        saved = dict(epoch=epoch, received_at=received_at, **book.checkpoint())
                        checkpoints.write(json.dumps(saved) + "\n")
                        stats["checkpoints"] += 1
                        last_checkpoint = time.monotonic()
                    if time.monotonic()-last_status >= 5:
                        raw.flush(); checkpoints.flush()
                        status()
                        last_status = time.monotonic()
                        if shutil.disk_usage(args.out).free < 1024**3:
                            stats["state"] = "low_disk_space"
                            stopped = True
            except Exception as error:
                stats["connection_errors"] += 1
                stats["consecutive_connection_errors"] += 1
                # Do not serialize exception text/headers, which may include credentials.
                detail = dict(error_type=type(error).__name__, http_status=getattr(error, "status_code", None))
                stats["last_connection_error"] = detail
                if pending_gap is None:
                    pending_gap = dict(previous_last_valid_book_at=last_healthy_receive,
                                       disconnected_at=datetime.now(timezone.utc).isoformat(),
                                       next_snapshot_received_at=None)
                    stats["gap_windows"].append(pending_gap)
                journal(dict(control="connection_ended", epoch=epoch, received_at=datetime.now(timezone.utc).isoformat(), **detail))
                stats["state"] = "reconnecting"
                status()
                if detail["http_status"] in (401,403) or stats.get("server_error_code") is not None or (args.max_consecutive_errors and stats["consecutive_connection_errors"] >= args.max_consecutive_errors):
                    stats["state"] = "access_or_connection_failed"
                    break
                retry_until = min(deadline, time.monotonic()+min(30,2**min(stats["consecutive_connection_errors"],5)))
                while not stopped and time.monotonic() < retry_until:
                    time.sleep(min(0.25, max(0,retry_until-time.monotonic())))
            finally:
                if ws is not None:
                    try:
                        ws.close(timeout=1)
                    except Exception:
                        pass
        if stats["state"] not in ("access_or_connection_failed", "low_disk_space"):
            stats["state"] = "stopped_by_signal" if stopped else "byte_cap_reached" if stats["bytes_written"] >= stats["max_bytes"] else "completed"
        status()
    stats["stored_journal_bytes"] = journal_path.stat().st_size
    stats["stored_checkpoint_bytes"] = checkpoint_path.stat().st_size
    with journal_path.open("rb") as stream:
        stats["journal_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    with checkpoint_path.open("rb") as stream:
        stats["checkpoint_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    status()
    atomic_json(args.out / "manifest.json", stats)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
