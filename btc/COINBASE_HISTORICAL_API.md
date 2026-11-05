# Coinbase BTC order-book access and storage assessment

Checked October 29, 2026. User requested documentation review, inspection of existing API keys, and a practical assessment of data volume. No fees, purchases, order actions or persistent service were used.

## Historical availability

**No free historical full-depth replay was found in the reviewed standard Coinbase Exchange/Advanced Trade APIs.** The documented REST product-book endpoint retrieves current open orders; it has a depth selector, not a historical date or replay cursor. The WebSocket sends a current snapshot followed by new updates. This is a conclusion about the reviewed interfaces, not proof that no historical Coinbase archive exists anywhere.

- [Exchange product book](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-book): level 2 is the full aggregated displayed book; level 3 is nonaggregated. Current snapshots do not backfill past changes.
- [Advanced Trade public WebSocket](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-endpoints): live snapshots/updates and public trades; no JWT required for public channels.
- [Coinbase Data Marketplace](https://help.coinbase.com/en/data-marketplace/getting-started/coinbase-data-marketplace): historical purchases/licensing are separate, with a sales agreement and SFTP access. An ordinary CDP key does not itself establish that entitlement. The reviewed [product list](https://help.coinbase.com/en/data-marketplace/getting-started/data-marketplace-products) lists tick trades, OHLCV and daily prices; it does **not** establish historical L2 availability. Paid access is outside the user's budget and was not pursued.

Free forward collection is feasible, but it solves a different problem from historical backfill. Kalshi remains the user's preferred venue; this Coinbase lookup is not a platform-selection decision. BTC-USD here is Coinbase spot, not a Kalshi perpetual.

## Existing key and implementation review

The original HFT strategy/collector was inspected only and never executed. Existing credentials stayed in their original files. No key values, identifiers or JWTs were copied to reports.

- `Junior-Spring/HFT/Kalshi-Orderbook-Predictor/collector/misc/cdp_api_key.json`: ECDSA P-256 key. A signed, read-only `GET /api/v3/brokerage/key_permissions` returned HTTP 200: `can_view=true`, `can_trade=false`, `can_transfer=false`. This establishes validity for that request at check time; it does not grant historical-data access.
- `.../secrets/cdp_api_key.json`: raw Ed25519 seed/public pair. Classified locally, not sent to an API. The reviewed [Coinbase App authentication documentation](https://docs.cdp.coinbase.com/coinbase-app/authentication-authorization/api-key-authentication) specifies ECDSA for this integration. Do not reinterpret Ed25519 bytes as an EC private key, as the old helper's generic fallback could do.
- `collector/include/coinbase_worker.hpp` explicitly replaced `level2` with `ticker` and `market_trades` to reduce volume. Its old comment estimates L2 at about 270 MB/hour. Ticker/trade recording alone cannot reconstruct all depth. This explains the remembered volume concern without treating the known archive as a new discovery.

## Measured public sample

[Retained sample and machine-readable results](../market_data/samples/coinbase_depth_2026-10-29/README.md). Both snapshot and WebSocket access succeeded without authentication.

| Measurement | Result |
|---|---:|
| REST full aggregated book | 20,252 bid levels; 20,632 ask levels |
| REST snapshot size | 1.07 MB raw; 0.286 MB gzip |
| WebSocket observation | about 62 seconds elapsed; about 61 seconds after initial snapshot |
| WebSocket initial snapshot | 40,901 price levels; 4.51 MB raw payload |
| Subsequent L2 updates | 713 messages containing 37,687 level replacements |
| Connection sequence gaps | 0 across all 1,030 received messages |
| Raw steady L2 rate extrapolation | 244 MB/hour; 5.86 GB/day; 176 GB/30 days |
| Gzip steady L2 + trades + heartbeat journal extrapolation | 16.6 MB/hour; 0.397 GB/day; 11.9 GB/30 days |

Decimal MB/GB throughout. Initial L2 snapshot is excluded from both steady estimates; reconnects/checkpoints add storage. Gzip includes local receipt envelopes and non-L2 messages, while the raw estimate is L2 payload only. WebSocket/TLS transport overhead is excluded. A one-minute observation cannot establish normal, peak or long-run traffic. Compression reduces disk use, not the uncompressed feed payload transmitted over the network.

Offline exact-decimal replay applied the snapshot and all 37,687 replacements, observing no negative quantities or crossed books after complete L2 events. Sequence numbers in this sample advance across **all subscribed channels on the connection**. Checking only L2 falsely suggests gaps when trades/heartbeats intervene. This short capture has not been independently reconciled against an exchange checkpoint; it is not a historical backfill or a proof of long-run uptime.

## What liquidity information is preserved

The [`level2` schema](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/websocket/level2) supplies `side`, `price_level`, `new_quantity`, `event_time`, product, message timestamp and sequence. Our journal also keeps receipt time. For BTC-USD, price is USD per BTC and size is BTC. The captured initial best bid was $81,794.80 with 0.02377329 BTC displayed at that price. Other prices have their own quantities.

`new_quantity` **replaces** the aggregate quantity at that price; zero removes the level. It is not an additive delta. Public trades are retained separately. This supports spread, price-by-time depth, imbalance, gaps and replenishment analysis. It does not identify every original order, exact queue position, or hidden liquidity, nor does an L2 size decrease by itself distinguish a cancellation from an execution.

## Practical assessment

For one BTC-USD spot pair, measured compressed storage is manageable on existing hardware, with headroom for busier periods. Retain raw compressed snapshot/update/trade journals, rotate files, validate sequences, and resnapshot after an interruption. Maintain the book incrementally in memory rather than saving a new full snapshot after every change. Derive coarser grids for TDA separately so that the source depth is preserved. Process research data in chunks instead of loading months of JSON into RAM.

This is a useful no-fee **forward-recording option**, not an established free historical source. No ongoing Coinbase collection was started. The bounded probe exited after its sample; no orders were submitted, amended or cancelled.
