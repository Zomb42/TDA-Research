# Existing HFT Kalshi historical book inventory

Read-only audit completed October 29, 2026 using [audit_hft_kalshi_archive.py](../../audit_hft_kalshi_archive.py). Source files remain under `Junior-Spring/HFT/Kalshi-Orderbook-Predictor/data/` and `collector/rawdata/`.

**176 distinct files, 3,514,863,228 bytes, 415 snapshots, 13,534,604 book deltas and 822,336 public trade messages.** All files passed conservative book replay: no detected sequence gaps, unsupported book records, invalid JSON or negative resulting quantities. Snapshots replace state; additive deltas are applied using exact decimals. Public event timestamps span parts of April 20–23, 2026.

These are **Kalshi BTC 15-minute binary event contracts**, not BTC-perp books or cross-exchange BTC depth. All 176 filenames are distinct, but that does not independently rule out duplicated public executions across different source files or establish complete capture beyond the recorded intervals. Treat trade-message counts as recorded messages until doing a trade-ID-based aggregation for a specific analysis.

- [Summary](summary.json): coverage, counts, replay results and limitations.
- [Per-file inventory](files.jsonl): original absolute path, SHA256, event timestamps, sizes, counts, sequence/reset and quantity checks.
- [Review and adaptation notes](../../../liquidity/HFT_KALSHI_REVIEW.md): reusable techniques and changes needed for perps.

Original `.csv` files are JSONL, not comma-separated tables. They were neither modified nor copied. Some contain private fill messages; the audit counts message types but does not retain/export private fill payloads. The original collector/trading programs were not launched, and no orders were submitted by this task.
