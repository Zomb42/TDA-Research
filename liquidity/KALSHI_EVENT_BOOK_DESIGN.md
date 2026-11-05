# Kalshi event-by-event liquidity reconstruction

Working design, October 29, 2026, following the user's proposal to collect fine-grained Kalshi data and reconstruct broad displayed liquidity. The current instrument is the BTC perpetual, `KXBTCPERP`; binary BTC event contracts remain a separate product.

## What we would reconstruct

The object is the **published aggregate bid/ask quantity at each price**, evolving over time. Record the finest available feed first; aggregate it into price/time grids later. A large analysis window does not require coarse source data.

| Feed | Purpose |
|---|---|
| Initial order-book snapshot | Establish quantities already resting before capture starts |
| Incremental price-level deltas | Maintain the book as published quantities change |
| Public executed trades | Measure executed size, price and taker side alongside displayed liquidity |

Kalshi documents snapshots followed by deltas and subscription sequence validation in its [perp book feed](https://docs.kalshi.com/margin-ws/websockets/orderbook-updates). Its [public trade feed](https://docs.kalshi.com/margin-ws/websockets/public-trades) exposes executions with trade ID, price, count and taker side. These are execution notifications, not a public record of every original submitted market order. One aggressive order can produce several fills; a marketable limit order can also consume liquidity.

## Why executions alone are insufficient

Hypothetical BTC asks: 0.4 BTC at $80,000 and 0.6 BTC at $80,010. A 0.5-BTC aggressive buy consumes the first level and 0.1 BTC of the second, leaving 0.5 BTC at $80,010. But a new resting sell or a cancellation changes that remaining book without requiring any trade. A historical trade tape therefore cannot recover the resting book without its initial state and subsequent book changes.

Use deltas as the source of book quantities. Do not subtract executions again after applying deltas: that would count consumption twice. Keep trades as a separate synchronized stream. Do not require a one-to-one match between trade and delta messages or treat subscription sequence numbers as one global ordering across channels.

## Capture and reconstruction rules

1. Authenticate to the perp WebSocket and subscribe to book updates and public trades for `KXBTCPERP`. Use `update_interval_ms=0` for book updates, requesting the documented real-time rather than conflated mode. This does not establish access to internal exchange events or every submitted order.
2. Write raw messages, receipt times and available exchange/send timestamps before deriving features. Preserve market metadata and native contract units; convert USD per contract and contract counts using the saved BTC contract size.
3. Replace local state on every book snapshot. Apply additive deltas in that subscription's delivery sequence, using exact decimal arithmetic; remove zero-quantity levels. A delta before initialization, missing sequence, or negative resulting quantity invalidates the reconstruction and requires recovery.
4. On a sequence gap, record the invalid interval and request fresh snapshots for the affected subscription's markets. Reconnects start from their own snapshots. Never bridge a missing interval with a stale or zero book.
5. Persist periodic reconstructed checkpoints for fast replay. Compare raw-message replay with saved checkpoints. Keep trades distinct and retain their identifiers for duplicate detection.

The [WebSocket handshake requires authentication](https://docs.kalshi.com/margin-ws/websockets/websocket-connection). The first two-minute REST sample established snapshot access. A subsequent authenticated data-only recorder passed a 90-second probe and exact checkpoint replay, then started a bounded one-hour capture. See [current status](../market_data/samples/kalshi_btc_stream_2026-10-29_session01/status.json) and [HFT review](HFT_KALSHI_REVIEW.md). No permanent service is installed. The existing HFT archive independently supplies historical binary-contract book streams; historical executions alone still cannot reconstruct earlier missing perp books.

## Connecting the book to the TDA question

Create a depth field `D(price, time)` from reconstructed states, using both native fixed-price coordinates and declared distance-from-midpoint coordinates as separate representations. Preserve bids/asks, observed coverage, missingness and physical coordinates. Do not treat omitted/unobserved depth as zero.

Start with 1-second sampling and declared price bins as analysis choices, retaining the raw stream so those choices can be revised. This sampling does not claim that every order change lasts a second. Fixed-price coordinates describe liquidity at actual prices; midpoint-relative coordinates describe depth at distance from a moving market. They can show different geometry.

Compare broad concentrations, depleted regions and their recovery across thresholds and resolutions. Merge/H0 branches can identify depth concentrations; source price, distance, width, recency and temporal span make them interpretable. Persistence measures depth contrast, not elapsed order duration. Cubical H1 is a separate possible construction for enclosed low-depth pockets; important open gaps need not form holes.

Add executed buy/sell volume and trade intensity as separate flow features. For example, replenishment after aggressive buying is a measurable pattern; deciding which net depth changes were new orders versus cancellations can require more information than aggregate L2 supplies. Compare topology with spread, depth, imbalance, gaps and replenishment before making predictive claims.

“Broad liquidity” here means a broad view of **Kalshi's displayed BTC-perp book**. The feed describes aggregate price levels, not every participant's order identity, exact queue positions, hidden interest or cross-exchange Bitcoin liquidity.
