# Kalshi historical API: fit for the requested liquidity data

Official documentation reviewed October 29, 2026. User preference: keep data on one easy platform if possible, with Kalshi prioritized. No order actions or private account-history requests were made in this review.

## Finding

Kalshi does have historical-data APIs, but the documented historical tiers are **not a past full-order-book replay service**. For the requested BTC-perp price-by-price displayed depth over past dates, no official historical snapshot/delta replay endpoint was found in the documentation reviewed. This is a statement about the documented API, not proof that no private/vendor archive exists.

## Perpetuals: directly relevant endpoints

All paths below are relative to `https://external-api.kalshi.com/trade-api/v2`.

| Need | Documented endpoint | What it gives |
|---|---|---|
| Past perp prices and quoted best-price summaries | `/margin/markets/{ticker}/candlesticks` | Bid/ask/trade OHLC, volume and open interest at supported intervals; not full ladders |
| Public executed perp trades | `/margin/trades` | Execution price, count, time, taker side; ticker/time filters and cursor pagination |
| Historical perp funding rates | `/margin/funding_rates/historical` | Market, funding time/rate and mark-price fields |
| Full currently reported perp depth | `/margin/markets/{ticker}/orderbook` | Current bid/ask price-size ladders; `depth=0` requests all reported levels |
| Book changes | Perp WebSocket `orderbook_delta` | Real-time initial snapshot and incremental changes; historical backfill not documented |

The order-book REST parameters are depth and aggregation size; the reference does not offer a past timestamp/replay parameter. The perp overview lists the general historical-data endpoints as unavailable on margin. This does not negate its separately documented candle, trade and historical funding-rate routes.

Official references: [Perps overview](https://docs.kalshi.com/margin), [candlesticks](https://docs.kalshi.com/margin-rest/market/get-market-candlesticks), [public trades](https://docs.kalshi.com/margin-rest/market/get-trades), [historical funding rates](https://docs.kalshi.com/margin-rest/funding/get-historical-funding-rates), [current depth](https://docs.kalshi.com/margin-rest/market/get-market-orderbook), [book feed](https://docs.kalshi.com/margin-ws/websockets/orderbook-updates).

## Why searching “historical API” gives apparently broader results

The [general historical-data guide](https://docs.kalshi.com/getting_started/historical_data) lists archived markets, candlesticks, public trades, user fills, orders and positions. `/historical/cutoff` describes when records move into those tiers. It does not list historical order-book snapshots or deltas.

`/historical/orders` is authenticated account-scoped order history, not a public tape of every participant's resting order additions/cancellations. Do not query the user's private orders to try to reconstruct the market. [Historical orders reference](https://docs.kalshi.com/api-reference/historical/get-historical-orders).

## Platform decision

Respect the preference for Kalshi rather than treating the successful Deribit/BitMEX samples as a venue choice. Kalshi's official API can keep candle/trade/funding history together, but those alone do not provide historical displayed quantity at each price. A Kalshi-only historical L2 study needs an external archive or other historical access that **specifically covers Kalshi perpetuals**. An archive advertising YES/NO prediction markets does not establish that coverage. Neither vendor entitlement nor adequate perp history has been verified here.

Do not replace the historical-data request with more live recording. Existing live recordings and old 15-minute event-contract files remain separate provenance, not the solution to this access gap. Do not purchase a subscription or restart a collector merely because a platform is preferred.
