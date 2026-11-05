# Bounded Coinbase BTC-USD public-depth probe

Collected October 29, 2026, approximately 15:46–15:48 UTC. This is a new live sample, not an external historical backfill. BTC-USD is spot. No fees or order actions; no persistent recorder installed.

- [Summary](summary.json): sanitized key permission check, REST depth counts, throughput and offline replay results.
- [Replay validation](replay_validation.json): gzip SHA256, connection continuity, exact-decimal replay and compressed steady-rate estimate.
- `public_exchange_snapshot.json.gz`: one public Exchange `GET /products/BTC-USD/book?level=2` response; full aggregated book.
- `public_stream.jsonl.gz`: public Advanced Trade `level2`, `market_trades`, `heartbeats` receipt envelopes. One initial L2 snapshot and 713 L2 update events; 37,687 price-level replacements. No authentication used for these feeds.
- `key_checks.json`: only key format, original relative location, HTTP status and permission booleans; no credentials or identifiers. `partial_results.json` was written before the WebSocket probe as a progress artifact.

One minute suggests 5.86 GB/day of raw L2 payload or 0.397 GB/day of gzip journal including trades/heartbeats, excluding the initial L2 snapshot. Treat these as short-sample extrapolations. Reconnect snapshots, recurring checkpoints, busy periods and processing outputs add volume. Gzip does not reduce inbound uncompressed feed payload.

All 1,030 messages advance the connection sequence by one. Checking L2 alone would falsely report gaps because sequence numbers also cover intervening channel messages in this capture. Replay observed no negative sizes or crossed books after complete L2 events; independent final checkpoint reconciliation was not performed.

From the project root, in the existing `tda` environment:

```sh
python market_data/analyze_coinbase_depth.py
```

The analyzer is offline and does not access credentials. `probe_coinbase_depth.py` performs the original bounded network/key check; it is not an unattended recorder and refuses to overwrite an existing stream file. Historical availability, source docs and practical interpretation: [Coinbase assessment](../../../btc/COINBASE_HISTORICAL_API.md).
