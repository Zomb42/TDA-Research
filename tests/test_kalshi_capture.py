"""Offline regression checks for compressed capture and reconnect recovery."""
from contextlib import redirect_stdout
import importlib.util
import io
import gzip
import json
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "market_data" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CaptureRecoveryTest(unittest.TestCase):
    def test_six_recovered_disconnects_do_not_exhaust_total_error_budget(self):
        recorder = load("recorder_under_test", "record_kalshi_btc_stream.py")
        validator = load("validator_under_test", "audit_kalshi_btc_stream.py")
        clock, handlers, sockets = [0.0], {}, []

        class Socket:
            def __init__(self, number):
                self.number, self.sent = number, []
                self.events = [
                    {"type": "subscribed", "msg": {"channel": c, "sid": i}}
                    for i,c in enumerate(["orderbook_delta", "trade", "ticker"],1)
                ] + [
                    {"type": "orderbook_snapshot", "sid": 1, "seq": 1,
                     "msg": {"market_ticker": recorder.TICKER, "bid": [["7.9701", "2.50"]], "ask": [["7.9802", "3.00"]]}},
                    {"type": "orderbook_delta", "sid": 1, "seq": 2,
                     "msg": {"market_ticker": recorder.TICKER, "side": "bid", "price": "7.9701", "delta": "-0.50"}},
                    {"type": "orderbook_delta", "sid": 1, "seq": 3,
                     "msg": {"market_ticker": recorder.TICKER, "side": "bid", "price": "7.9701", "delta": "0.25"}},
                    {"type": "trade", "sid": 2, "seq": 1,
                     "msg": {"market_ticker": recorder.TICKER, "trade_id": str(number), "price": "7.9701", "count": "0.50"}},
                ]

            def settimeout(self, value):
                pass

            def send(self, value):
                self.sent.append(json.loads(value))

            def recv(self):
                clock[0] += 3
                if self.events:
                    return json.dumps(self.events.pop(0))
                if self.number < 7:
                    raise ConnectionResetError()
                handlers[signal.SIGTERM](signal.SIGTERM, None)
                return json.dumps({"type": "ticker", "sid": 3, "seq": 1,
                                   "msg": {"market_ticker": recorder.TICKER}})

            def close(self, **kwargs):
                pass

        def connect(*args, **kwargs):
            socket = Socket(len(sockets)+1)
            sockets.append(socket)
            return socket

        def sleep(seconds):
            clock[0] += seconds

        with tempfile.TemporaryDirectory(prefix="tda-offline-capture-") as directory:
            arguments = ["recorder", "--out", directory, "--seconds", "1000", "--gzip", "--include-ticker"]
            with (patch.object(sys, "argv", arguments),
                  patch.object(recorder, "headers", return_value={}),
                  patch.object(recorder.websocket, "create_connection", side_effect=connect),
                  patch.object(recorder.urllib.request, "urlopen", return_value=io.BytesIO(b'{"market":{}}')),
                  patch.object(recorder.signal, "signal", side_effect=lambda number, handler: handlers.update({number: handler})),
                  patch.object(recorder.time, "monotonic", side_effect=lambda: clock[0]),
                  patch.object(recorder.time, "sleep", side_effect=sleep),
                  redirect_stdout(io.StringIO())):
                recorder.main()
            manifest = json.loads((Path(directory)/"manifest.json").read_text())
            self.assertEqual(manifest["state"], "stopped_by_signal")
            self.assertEqual(manifest["connections"], 7)
            self.assertEqual(manifest["connection_errors"], 6)
            self.assertEqual(manifest["sequence_gaps"], 0)
            self.assertEqual(len(manifest["gap_windows"]), 6)
            self.assertTrue(all(g["next_snapshot_received_at"] for g in manifest["gap_windows"]))
            self.assertTrue(validator.audit(Path(directory))["passed"])
            for socket in sockets:
                self.assertEqual([m["params"]["channels"] for m in socket.sent], [["orderbook_delta"], ["trade"], ["ticker"]])
                self.assertTrue(all(m["cmd"] == "subscribe" for m in socket.sent))
                self.assertEqual(socket.sent[0]["params"]["update_interval_ms"], 0)
            # A lost update must fail replay/count/hash checks, even when all
            # later connection snapshots remain present and well formed.
            journal = Path(directory)/"messages.jsonl.gz"
            with gzip.open(journal, "rt") as stream:
                records = [json.loads(line) for line in stream]
            missing = next(i for i,r in enumerate(records) if r.get("message", {}).get("type") == "orderbook_delta")
            del records[missing]
            with gzip.open(journal, "wt") as stream:
                for record in records:
                    stream.write(json.dumps(record)+"\n")
            failed = validator.audit(Path(directory))
            self.assertFalse(failed["passed"])
            self.assertGreater(failed["book_sequence_gaps"], 0)


if __name__ == "__main__":
    unittest.main()
