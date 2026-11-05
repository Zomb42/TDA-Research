# Binance BTC perpetual histories

Collected October 29, 2026, using [collect_btc_history.py](../../collect_btc_history.py) and Binance's [public data archive](https://github.com/binance/binance-public-data).

`bars_5m.parquet` contains **296,928 BTCUSDT USD-M perpetual bars**, Jan 1, 2024 00:00–Oct 27, 2026 23:55 UTC. There are no missing or duplicate five-minute bars. OHLC ordering, positive prices, durations and taker-volume bounds passed. Original exchange milliseconds and raw OHLCV/count fields are retained; quantities are BTC, notional is USDT. `available_at_utc` is logical candle completion, not measured original publication time.

`depth_bands.parquet` contains **892,200 rows / 89,220 snapshots** over January 2025. Bands are cumulative at ±1%, ±2%, ±3%, ±4%, ±5%. Negative bands are below-mid bid depth; positive bands are above-mid ask depth. Quantities are BTC; notional is USDT. Median interval is 30 seconds. Two intervals exceed 60 seconds: **930 seconds and 928 seconds on January 7**. See [exact gaps](depth_time_gaps.csv). No duplicate band/time keys, incomplete returned band sets, negative quantities or decreasing cumulative notional were found. The observed gap durations do not establish their cause.

These bands cannot recover individual prices, the best spread, sub-1% structure, queues or hidden liquidity. Differencing successive cumulative bands gives annular totals, not a reconstructed price ladder. Do not bridge outages with zero depth or connect topology across them.

`raw/` retains all ZIPs, published `.CHECKSUM` files and retrieval metadata. All 91 downloaded archives match published SHA256 checksums. [Requests](requests.json), [collection audit](audit.json), [manifest](manifest.json), and [independent offline audit](../btc_independent_audit.json) document coverage and transformation checks. Retrieval timestamps are not historical first-publication timestamps. The series is venue-specific and USDT-quoted, not consolidated BTC/USD spot.
