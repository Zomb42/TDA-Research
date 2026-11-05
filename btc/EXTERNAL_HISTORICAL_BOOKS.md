# External historical BTC book data: actual access tests

October 29, 2026. This addresses the corrected task in [AGENTS.md](../AGENTS.md): obtain historical book-message data for markets beyond the user's own recordings. No 15-minute binary-event data or live recording was used for these tests.

**Latest result:** after the user accepted non-Kalshi venues with historical full depth, a complete **Jan 1, 2025 Deribit BTC-PERPETUAL** L2/trade day was downloaded and reconstructed: 15,452,352 price-level records and 50,816 trades. A native historical minute also returned snapshots, change actions and sequence IDs; independent native replay matched the normalized first checkpoint and 28 trades exactly. [Dataset and limitations](../market_data/datasets/btc_deribit_2025-01-01/README.md), [source decision](FULL_DEPTH_SOURCE_DECISION.md). The prefix tests below are earlier preflight provenance, superseded as the current Deribit access status.

## Access verified

[probe_external_historical_books.py](../market_data/probe_external_historical_books.py) made unauthenticated HTTP **GET** requests with a 512-KiB byte range per file. Both returned **206 Partial Content**, and their compressed prefixes decompressed into historical normalized L2 data:

| Market | Historical date | Complete CSV rows in downloaded prefix | Snapshot rows | Incremental update rows | Full daily archive size advertised by server |
|---|---|---:|---:|---:|---:|
| Deribit `BTC-PERPETUAL` | Jan 1, 2025 | 66,127 | 2,939 | 63,188 | 124,189,509 compressed bytes |
| BitMEX `XBTUSD` | Jan 1, 2025 | 65,140 | 5,627 | 59,513 | 186,513,150 compressed bytes |

Snapshot counts here are **price-level rows**, not separate whole-book snapshots. Multiple rows can belong to one source message. These are external historical BTC perpetual markets, outside the user's old recordings. Only 512 KiB per archive was downloaded; **complete days, full continuity, and reconstruction were not validated**. The full-file sizes come from `Content-Range`, not from a completed transfer.

Exact public URLs, HTTP statuses, hashes, schemas and actual snapshot/update row examples are in [access_tests.json](../market_data/samples/external_historical_books_2026-10-29/access_tests.json). Downloaded compressed prefixes and readable CSV prefixes are retained beside it.

## What was obtained, and what remains to verify

The columns are `exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount`. Timestamps are microseconds. The provider defines `amount` as **replacement size at that price**, not an additive delta; zero removes the level. Snapshot boundaries must be handled according to the normalized schema. Do not reuse Kalshi's additive update semantics for these records. [Provider schema](https://docs.tardis.dev/downloadable-csv-files/data-types).

This proves practical access to historical snapshot and incremental L2 records. It does **not** yet prove access to every original order submission, exchange-native message envelopes/sequence IDs, a complete day, or a multi-year continuous panel. Individual order-level L3 is another capability to investigate if needed.

Tardis separately documents exchange-native historical WebSocket replay. For Deribit, the book channel retains exchange message structure and the provider describes validating `prev_change_id`; raw replay access remains **documented, not tested in this step**. [Deribit coverage and native replay](https://docs.tardis.dev/historical-data-details/deribit). The free-first-day sample rule is documented in the [dataset API](https://docs.tardis.dev/downloadable-csv-files/api); other dates and native API access need their own entitlement/cost checks.

Next checks: obtain a bounded native-message replay sample, inspect actual snapshot/change/trade envelopes and sequence fields, determine full-period depth/coverage and units, then download and replay a complete declared interval. Check market-specific contract conventions before comparing liquidity quantities. Keep Kalshi-perp historical access as a separate venue-specific question; an absent Kalshi endpoint does not imply absence of historical books elsewhere.

Hyperliquid's official S3 archive is another documented option, but L2 snapshots are not automatically an incremental-message archive; coverage and requester-paid transfer costs have not been tested. [Official historical-data documentation](https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data).

## Correction to the earlier failed probe

The earlier Bitstamp sample check used **HEAD**, which Tardis's [API documentation](https://docs.tardis.dev/downloadable-csv-files/api) explicitly says returns 404. That response did not establish that a GET-accessible dataset was missing. Current tests use the documented GET/Range mechanism. Do not infer vendor availability from the earlier HEAD result.
