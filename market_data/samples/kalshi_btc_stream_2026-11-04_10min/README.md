# Ten-minute Kalshi BTC-perp capture — November 4, 2026

Requested by the user for BTC feature engineering and liquidity. See the [collection guide](../../../btc/LIVE_COLLECTION.md) for channels, units, provenance, L2 limits, and verification commands.

**Open the data:** [formatted preview](data_preview.json) shows an actual snapshot, book update, trade, and ticker. The full raw event stream is [messages.jsonl](messages.jsonl); full reconstructed books are [checkpoints.jsonl](checkpoints.jsonl). `market.json` contains instrument metadata only. At the user's request, this sample stays uncompressed; the latest preference is lossless compression for future recordings.

**Completed; recorder stopped.** November 4, 19:22:29–19:32:29 Indianapolis (November 5, 00:22:29–00:32:29 UTC).

| Recorded item | Count |
|---|---:|
| Initial full-book snapshots | 1 |
| Price-level book deltas | 114,753 |
| Public trades | 1,327 |
| Ticker updates | 599 |
| Full-book checkpoints matched by independent replay | 119 / 119 |
| Detected book/trade sequence gaps, reconstruction/connection errors | 0 |
| Duplicate trade IDs | 0 |

All validation checks passed, including final SHA-256 hashes. Uncompressed files: **37.29 MiB** of events and **0.63 MiB** of checkpoints. Original gzip files/metadata are preserved in ignored `raw/original_gzip/`; current manifests and validation refer to the plain files. This validates the captured public L2 stream internally, not exchange-wide individual-order completeness. The data is a ten-minute development sample, not a long-history or held-out predictive study.

The live [status](status.json) is periodically updated; the final [manifest](manifest.json) and independent [replay validation](replay_validation.json) are written on completion. Initial start: November 4, 2026 at 19:22:29 Indianapolis / November 5 at 00:22:29 UTC. Planned duration: **600 seconds**; journal cap: **512 MiB uncompressed**. Environment: **`tda`**. No persistent collector is installed.

Local-only raw files:

- `messages.jsonl`: full received public L2 snapshot/delta, trade, and ticker messages plus receipt clocks/connection controls.
- `checkpoints.jsonl`: exact-decimal reconstructed full bid/ask books approximately every five seconds and at snapshots.

[market.json](market.json) retains contract metadata. [capture_context.json](capture_context.json) records recorder/environment provenance and identifies the local snapshot of the source actually used. Connection/sequence gaps are preserved as missing intervals; this is aggregated displayed L2, not every participant's individual order. No orders are submitted and no fees or subscriptions are purchased.
