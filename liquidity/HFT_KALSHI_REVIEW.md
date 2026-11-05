# HFT Kalshi archive and collector review

**Scope correction:** the user supplied this folder for techniques and access context, already knows their old books exist, and is not asking to study 15-minute events. The inventory here is provenance, not a new discovery or a response to external historical availability. Current work follows [AGENTS.md](../AGENTS.md) and [external access tests](../btc/EXTERNAL_HISTORICAL_BOOKS.md).

Reviewed October 29, 2026. The user explicitly requested inspecting `Junior-Spring/HFT/Kalshi-Orderbook-Predictor` and prohibited submitting orders. Original source/data files were not modified. The original collector, strategy and market-maker programs were not executed. The new collector uses market-data channels only.

## Historical books already exist locally

The earlier statement that no long Kalshi book history had been established referred to the newly collected BTC **perpetual** data and had not accounted for this HFT archive. The local archive now establishes separately replayable **BTC 15-minute binary event-contract** books:

| Item | Audited result |
|---|---:|
| Files in `data/` and `collector/rawdata/` | 176, with distinct filenames |
| Raw size | 3,514,863,228 bytes |
| Book snapshots | 415 |
| Book deltas | 13,534,604 |
| Public trade messages | 822,336 |
| Whole-file replay checks passed | 176 / 176 |
| Detected sequence gaps / negative quantities | 0 / 0 |

Public event timestamps range from **2026-04-20 04:15 UTC to 2026-04-23 22:22:48.835 UTC**, across distinct contract sessions. This is not a continuous four-day perp dataset. Files named `.csv` are actually newline-delimited JSON WebSocket messages.

The [offline inventory](../market_data/datasets/hft_kalshi_archive_inventory/README.md) records each original path, byte size, SHA256, message counts, timestamp range and replay checks. The audit used exact decimal quantities and respected snapshot resets and subscription sequence continuity. A gap, unsupported message or negative quantity would invalidate replay until a later snapshot; quantities were never silently clamped. All recorded book deltas passed these checks. Original receipt times are not present in the sampled raw envelopes, so event-to-local network latency cannot be recovered from those files.

Some original files also contain historical private fill messages. The audit counts their type only and does not export their payloads. Their presence is not evidence of any order action in this session. Sequence continuity and successful replay validate the recorded stream's internal consistency, not independent completeness of exchange capture.

## Techniques to retain

- **Raw capture before feature computation.** [C++ worker](../../../Junior-Spring/HFT/Kalshi-Orderbook-Predictor/collector/include/kalshi_worker.hpp) and [writer](../../../Junior-Spring/HFT/Kalshi-Orderbook-Predictor/collector/include/csv_writer.hpp) preserve messages, allowing replay and different later grids. The new recorder adds UTC receipt times, connection epochs and status/checkpoint files.
- **Snapshot replacement and additive changes.** [Python book](../../../Junior-Spring/HFT/Kalshi-Orderbook-Predictor/kalshi_live/orderbook.py) is a useful template for state updates. A repeated snapshot clears previous state; a delta changes a price-level quantity. The new perp implementation uses exact decimal prices/quantities and invalidates sequence gaps.
- **Conventional depth baselines.** [Feature tracker](../../../Junior-Spring/HFT/Kalshi-Orderbook-Predictor/kalshi_live/features_live.py) provides OBI at several depths, spread, depth skew, momentum and flow context. These should accompany topology using the same inputs and time windows. Previously reported model metrics in code comments were not independently replicated here.
- **Separate clocks.** [Latency utilities](../../../Junior-Spring/HFT/Kalshi-Orderbook-Predictor/kalshi_live/latency_util.py) distinguish message and receipt time. Their difference also includes clock error and timestamp semantics; it is not an independently measured pure network delay.

## Adaptations and limits

1. **Preserve native precision and use the correct product schema.** The [C++ book](../../../Junior-Spring/HFT/Kalshi-Orderbook-Predictor/collector/include/orderbook.hpp) maps binary prices into 99 one-cent slots. Our audit observed **203 simultaneous Yes price levels** and **186 No levels**; actual delta prices include `0.0010`, `0.0110` and `0.0120`. Thus the existing archive already contains subcent structure that the 99-slot representation would collapse. [Price-precision evidence](../market_data/datasets/hft_kalshi_archive_inventory/price_precision_evidence.json). The Python book preserves finer price keys, though it uses floating-point values. Its complementary Yes/No rules also do not apply to perps. The new perp recorder preserves exact decimal bid/ask levels using the perp schema.
2. **Validate sequence continuity and rebuild on reconnect.** The inspected older readers do not validate `seq`. The recorded archive nevertheless passed that validation in this audit. New capture refreshes signing headers for every connection, clears book state, and waits for its own snapshot. The older Python reader constructs headers before its retry loop, which could reuse stale authentication on a later reconnect.
3. **Do not infer trades/cancellations from size alone.** The [market-maker simulator](../../../Junior-Spring/HFT/Kalshi-Orderbook-Predictor/collector/include/market_maker.hpp) treats a negative change larger than a fixed threshold as a probable cancellation. That is a simulation heuristic, not an observed event classification. Use actual public trades for executed-flow features; aggregate deltas do not identify every original order action.
4. **Use actual timestamps for windows.** The old tracker converts seconds into a fixed number of rows at a declared sampling rate. Stalls or skipped rows can change the physical span represented by that count. Preserve actual timestamps, staleness and missing intervals in research features.
5. **Define concentration measures explicitly.** The old `depth_hhi` is a particular best-level/depth ratio, and its `toxicity` is a ratio of absolute side-depth changes. Do not import broader economic interpretations from those labels. A conventional price-level HHI can instead be defined explicitly as the sum of squared depth shares over a declared region.

The market-maker [session](../../../Junior-Spring/HFT/Kalshi-Orderbook-Predictor/collector/include/session.hpp) can attach a trading REST client when live mode is enabled. Consequently, the original executable was kept stopped. This task uses a separate recorder without an order client or private account subscriptions.

## New BTC-perp capture

[record_kalshi_btc_stream.py](../market_data/record_kalshi_btc_stream.py) reuses the RSA-PSS signing pattern while reading the existing credentials in place. It connects only to Kalshi's perp WebSocket and sends fixed subscriptions to `orderbook_delta` and `trade` for `KXBTCPERP`. It does not import the HFT strategy package, submit/amend/cancel orders, or subscribe to private fills/orders. Secrets and authentication headers are not written to outputs.

The **90-second probe** captured **26,250 book deltas, 203 trades and one initial snapshot**, with zero connection errors, sequence gaps or reconstruction errors. All **18 saved checkpoints** matched independent replay of the retained raw journal exactly. [Probe validation](../market_data/samples/kalshi_btc_stream_2026-10-29_probe/replay_validation.json).

A **one-hour capture, capped at 512 MiB of raw messages**, was then started. Its [live status](../market_data/samples/kalshi_btc_stream_2026-10-29_session01/status.json) is the current authority for whether it remains active, how much has been recorded, and any errors. `messages.jsonl` retains event and receipt timestamps; `checkpoints.jsonl` retains full reconstructed states approximately every five seconds. A separate bounded public REST recording also runs as a snapshot comparison. No permanent service or scheduled restart is installed; these processes depend on the host remaining awake and connected.

This supplies two complementary research inputs: archived binary-contract depth for immediate replay/TDA work, and newly recorded BTC-perp depth and executions for a separate instrument. Keep their datasets and interpretations distinct.
