# Kalshi BTC perpetual minute history

Collected October 29, 2026 with public GET requests to the [perps candle endpoint](https://docs.kalshi.com/margin-rest/market/get-market-candlesticks). No API credentials were used.

`candles_1m.parquet` retains **208,328** returned `KXBTCPERP` candles. Requested candle ends are `(2026-06-01 00:00, 2026-10-28 00:00]` UTC. The first returned end is June 3 at 14:02 UTC. This is observed endpoint coverage, not independent evidence of the product launch date.

Of 214,560 requested minute boundaries, **6,232** have no returned candle: 3,721 before the first observation and 2,511 at or after it. There are also **773 returned candles with null trade closes**. Bid/ask prices may remain available then. No missing or null prices are filled, no previous-price synthetic candle is requested, and no duplicate timestamps or crossed bid/ask close quotes were found. [All missing ranges](missing_period_ranges.csv) and [null trade-close periods](null_trade_close_periods.csv) are saved.

Original prices are **USD per contract**. Saved market metadata gives contract size **0.0001 BTC** and multiplier 1. Added columns ending `_usd_per_btc` divide contract price by 0.0001; `volume_btc` and `open_interest_btc` multiply contract count by 0.0001. Original columns and raw response strings are preserved. Bid and ask close prices describe the reported boundary quotes; independently observed intraminute highs/lows must not be combined as though simultaneous.

Candles include trade and bid/ask OHLC, trade volume and open interest. They **do not contain historical multilevel resting depth**. The separate [REST depth sample](../../samples/kalshi_btc_depth_2026-10-29/manifest.json) was collected going forward. Raw daily JSON responses, exact query URLs and receipt/hash metadata live in `raw/`; see [audit](audit.json), [manifest](manifest.json), and [independent audit](../btc_independent_audit.json). Historical candle availability was measured; long historical L2 replay was not established.
