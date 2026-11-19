# Binance BTCUSDT aggregated trades, November 11–17, 2026

Downloaded November 18, 2026 from Binance's free public archive (`data.binance.vision`): daily `aggTrades` files for the USDT perpetual future (`futures/um`) and spot. There are 14 ZIP files in `raw/`; each matches its published SHA-256 checksum (`.CHECKSUM` files kept alongside).

- Futures columns: `agg_trade_id, price, quantity, first_trade_id, last_trade_id, transact_time (ms), is_buyer_maker` (with header).
- Spot columns: the same order, no header, with `transact_time` in **microseconds**, plus a final `is_best_match` column.
- Times are Binance's matching-engine timestamps (UTC).

`liquidity/studies/l12_binance_grid.py` turns these into a last-price series every 100 ms (`liquidity/results/book_shape/snapshots/binance_100ms.npz`).
