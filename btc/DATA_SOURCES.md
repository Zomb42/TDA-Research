# BTC data sources and collection

**Scope correction, October 29:** the current task is **external historical message-level book data for other relevant BTC markets**, not the user's existing 15-minute event recordings. Their inventory below is historical provenance only. A source's documentation is not the same as tested access or a downloaded/replay-validated sample. See [project instructions](../AGENTS.md).

**Latest platform preference:** Kalshi preferred, other venues explicitly acceptable if historical full depth is available. The [tested pilot choice](FULL_DEPTH_SOURCE_DECISION.md) is Deribit BTC-PERPETUAL through Tardis: a complete Jan 1, 2025 book/trade day was downloaded and reconstructed, plus an independently checked native minute. [Dataset](../market_data/datasets/btc_deribit_2025-01-01/README.md). [Kalshi official API review](KALSHI_HISTORICAL_API.md) still leaves past perp snapshot/delta replay unverified. No paid purchase or account migration was made.

Measured October 29, 2026. All dataset intervals and timestamps below use UTC.

| Need | Source / measured access | Status |
|---|---|---|
| Coinbase BTC-USD full displayed spot depth | Public Exchange REST L2 and Advanced Trade WebSocket | Current snapshot and bounded public stream worked. Old ECDSA key passed a separate permissions GET, with view enabled and trade/transfer disabled. About 5.86 GB/day raw L2 or 0.397 GB/day gzip journal in a one-minute extrapolation. **Free historical L2 replay not found in reviewed APIs.** [Assessment](COINBASE_HISTORICAL_API.md). |
| Historical full-depth BTC perpetual pilot | Deribit BTC-PERPETUAL via Tardis, Jan 1, 2025 | Complete L2/trade archives downloaded and MD5/CRC checked; 15,452,352 level rows reconstructed into 1,440 full-book checkpoints, with 50,816 trades. One native minute sequence-checked and independently reconciled. [Dataset](../market_data/datasets/btc_deribit_2025-01-01/README.md). |
| Long continuous temporal-state input | [Binance public archive](https://github.com/binance/binance-public-data), BTCUSDT USD-M perp | 2024–Oct 27, 2026 five-minute bars downloaded; continuous |
| Historical displayed-liquidity totals | Same archive, `daily/bookDepth/BTCUSDT` | January 2025 downloaded; 1–5% cumulative bands, nominally about 30 seconds apart |
| Kalshi BTC perp price and quote history | [Perps candle endpoint](https://docs.kalshi.com/margin-rest/market/get-market-candlesticks) | Public GET worked; 208,328 minute candles retained, with gaps/nulls audited |
| Kalshi current multilevel depth | [Perps orderbook endpoint](https://docs.kalshi.com/margin-rest/market/get-market-orderbook) | Public GET worked with `depth=0`; two-minute capture completed |
| Kalshi tick-stream capture going forward | [Perps WebSocket book updates](https://docs.kalshi.com/margin-ws/websockets/orderbook-updates) | Authenticated 90-second probe passed: 26,250 deltas, 203 trades, 18 exact-replay checkpoints. A bounded one-hour data-only capture was then started; see live status below. |
| Existing historical Kalshi binary books | Local HFT predictor archive | 176 files, 13,534,604 book deltas and 822,336 public trade messages, parts of Apr 20–23, 2026; all files passed conservative replay. These are BTC 15-minute event contracts, not perps. |
| Kalshi historical multilevel book backfill | [Perps overview](https://docs.kalshi.com/margin) | No past-book replay established. Its general historical-endpoint exclusion should not be read as saying its separately documented candle/funding histories do not exist. |
| Historical higher-resolution perp L2 | [Hyperliquid archive](https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data) | Official docs identify L2 snapshots in requester-pays S3. Not downloaded; coverage/missingness and transfer cost need inspection before a larger pull. |
| Historical recorded L2 across venues | [Tardis downloadable datasets](https://docs.tardis.dev/downloadable-csv-files/overview) | Actual GET access verified: 512-KiB historical normalized L2 prefixes for Deribit BTC-PERPETUAL and BitMEX XBTUSD, Jan 1, 2025, both containing snapshot/update rows. Full days and native-message replay are not yet validated. [Results](EXTERNAL_HISTORICAL_BOOKS.md). The earlier HEAD 404 was not a valid dataset-availability test. |

The checked Kalshi ticker is `KXBTCPERP`, not `BTCPERP`. The initial incorrect-ticker 404 and subsequent verified response are retained in the probe directories. This is actual perp data; existing local Kalshi BTC 15-minute event-contract files are a different instrument and were not merged into it. The [HFT review](../liquidity/HFT_KALSHI_REVIEW.md) and [archive inventory](../market_data/datasets/hft_kalshi_archive_inventory/README.md) now establish their separate historical-book coverage.

**Active capture:** [record_kalshi_btc_stream.py](../market_data/record_kalshi_btc_stream.py) is a separate data-only perp recorder using existing HFT credentials in place. It has no order API and subscribes only to books and public trades. A one-hour run capped at 512 MiB was started after the probe. Check [live status](../market_data/samples/kalshi_btc_stream_2026-10-29_session01/status.json) for current state, freshness and counters; do not assume the bounded process remains running in a later session. No permanent service was installed. [Probe replay validation](../market_data/samples/kalshi_btc_stream_2026-10-29_probe/replay_validation.json).

Local datasets: [Binance](../market_data/datasets/btc_binance_2024_2026-10-27/README.md), [Kalshi candles](../market_data/datasets/btc_kalshi_2026-06_2026-10-27/README.md), and [Kalshi depth sample](../market_data/samples/kalshi_btc_depth_2026-10-29/manifest.json). Exact URLs, raw bytes, request/receipt times and hashes are retained. Receipt times measure our retrieval, not the historical publication time of each archive. `available_at_utc` on Binance bars is the logical completion boundary, not a measured original delivery time.

Reproduce from `Senior-Fall/TDA_Research` in the `tda` environment:

```sh
python market_data/collect_btc_history.py binance --start 2024-01-01 --end 2026-10-28 --depth-start 2025-01-01 --depth-end 2025-02-01 --out market_data/datasets/btc_binance_2024_2026-10-27
python market_data/collect_btc_history.py kalshi --start 2026-06-01 --end 2026-10-28 --period 1 --out market_data/datasets/btc_kalshi_2026-06_2026-10-27
python market_data/audit_btc_history.py
python btc/feature_engineering.py
python liquidity/experiments/btc_liquidity_features.py
```

The downloader reuses hash-checked originals. A new data vintage needs a new output directory. End dates are exclusive for bar-start intervals; Kalshi requests candle ends in `(start,end]`. Never insert a previous-price synthetic candle or silently fill missing bars. Binance USDT and Kalshi USD are separate quote currencies and venues, even after BTC unit conversion.

To collect a new bounded REST depth sample:

```sh
python market_data/record_kalshi_btc_depth.py --seconds 120 --interval 2 --out market_data/samples/kalshi_btc_depth_NEW
```

This REST command exits after two minutes and installs no persistent process or schedule. Full reported snapshots, failures, request/receipt times, spread, depth and imbalance are retained. The new WebSocket recorder separately implements snapshot replacement, exact-decimal additive deltas, subscription-sequence checks, and reconnect/resnapshot on invalid state. Its 90-second retained journal reproduced all checkpoints exactly; live gap/reconnect recovery has not yet been observed in the successful capture. Daily rotation and restart supervision remain future hardening work. Keep receipt and exchange timestamps separately; timestamps are not a substitute for sequence validation.
