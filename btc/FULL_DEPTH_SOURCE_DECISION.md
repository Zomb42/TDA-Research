# Historical full-depth source decision

**Superseded spending recommendation, latest October 29 preference:** the user explicitly wants no fees and is leaning toward self-collecting Kalshi. No paid subscription, API plan, data purchase or paid hosting is authorized. The complete Deribit day below was free and remains useful as a development sample; it is not a recommendation to buy Tardis access. The recommended next path is improving reliable Kalshi BTC-perp recording on existing resources, with the limitation that this builds new history rather than backfilling old books. Earlier source comparisons remain provenance.

Updated October 29, 2026 after the user clarified that alternatives to Kalshi are acceptable when historical full-depth data is available. Keep Kalshi preferred, but use an actually accessible historical-depth source for the pilot.

| Candidate | Historical depth and messages | Practical status |
|---|---|---|
| **Deribit BTC-PERPETUAL through Tardis** | Provider documents full-depth snapshots/updates and exchange-native book/trade messages | **Complete Jan 1, 2025 L2 + trades downloaded and reconstructed**; one native minute sequence-checked and reconciled. Best tested starting point. |
| Kalshi BTC perps | Official candles, trades, funding and current/live depth; no documented past full-book replay found | Venue preference retained; historical full-depth archive remains unverified. Do not replace it with binary-event history. |
| Coinbase BTC-USD spot through Tardis | Provider documents full-depth L2 and native L3, with history since 2019 | Documented alternative, not downloaded/tested here; different instrument from perps and subject to provider/exchange access conditions. |
| Kraken Futures BTC perpetual through Tardis | Provider documents full-depth snapshots/updates and BTC perpetual history since 2019 | Documented alternative, not downloaded/tested here. |
| Hyperliquid official S3 archive | Historical L2 snapshots; separately documented raw node datasets | Snapshot source documented; incremental historical-message suitability not verified. Requester-paid transfers and possible missing data. |

Primary provider/exchange references: [depth coverage](https://docs.tardis.dev/faq/order-books), [Deribit](https://docs.tardis.dev/historical-data-details/deribit), [Coinbase](https://docs.tardis.dev/historical-data-details/coinbase), [Kraken Futures](https://docs.tardis.dev/historical-data-details/cryptofacilities), [Hyperliquid](https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data). [Kalshi official API assessment](KALSHI_HISTORICAL_API.md).

**Working choice: Deribit historical full-depth L2 through Tardis for a bounded pilot.** This keeps one archive API/schema and matching trade data together. Tardis is the historical data provider, not the trading venue; this is not Kalshi data. The user permits the alternative, without requiring an account/platform migration or authorizing paid purchases.

The [complete-day dataset](../market_data/datasets/btc_deribit_2025-01-01/README.md) contains 15,452,352 price-level records, 50,816 trades and 1,440 reconstructed book checkpoints. Both complete archives matched advertised MD5 checksums. The independent native minute has 1 snapshot, 8,652 changes and 28 trades within 16 trade messages; its sequence chain is intact and its first normalized checkpoint/trades match exactly.

These facts establish available historical depth and a working reconstruction pilot. They do not prove full-day native sequence continuity, all internal order-level actions, every remote level beyond what the exchange publishes, or predictive usefulness. One day is not a general research panel. The next expansion should declare historical dates, inspect capture outages, verify inverse-contract units, and choose coverage/cost tradeoffs before buying anything.

Free first-of-month samples allow more disconnected historical episodes without a subscription; they must not be stitched together as continuous time. Continuous non-sample periods require checking provider entitlement/pricing. [Access policy](https://docs.tardis.dev/downloadable-csv-files/api).
