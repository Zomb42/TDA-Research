# BTC data: what exists, where, and how it was checked

All bulk data lives under `market_data/` on this machine and is not in git. All times are UTC. The project only uses free, public data, and no orders were ever placed. Rules are in [AGENTS.md](../AGENTS.md). **The data is final:** no new collection is planned (user, November 18, 2026).

## Datasets in use

| Dataset | What it holds | Where | Used by |
|---|---|---|---|
| **Kalshi perp week** | KXBTCPERP full order book (snapshot + every change) and every trade, November 10, 23:50 to November 17, 23:50. 205.7 million book updates, 1.49 million trades, 7.6 GB compressed. | `market_data/recordings/crc/2026-11-10T23-50-19Z-job-1724180/` | All liquidity studies |
| **Binance trades, same week** | BTCUSDT perpetual futures and spot aggregated trades, November 11–17, from Binance's free daily files | `market_data/datasets/btc_binance_aggtrades_2026-11-11_17/` | Liquidity WHO_WINS, BOOK_CLOUD |
| **Binance 5-minute bars** | BTCUSDT perpetual bars, January 2024 to October 27, 2026, plus coarse depth bands (±1–5%) for January 2025 | `market_data/datasets/btc_binance_2024_2026-10-27/` | BTC study b01 |
| **Kalshi + Coinbase pilot** | 25 hours of Kalshi perp book and trades, with Coinbase BTC-USD quotes at 2 Hz, November 5–6 | `market_data/recordings/2026-11-05T03-36-49Z/` | Liquidity Reeb pilot |

## How the Kalshi week was checked

The recorder saved a full copy of the book about once every five seconds and at every hour boundary. Replaying the updates from scratch rebuilds the same book. The checks:

- **All 118,446 saved books** and all 168 hour-boundary hand-offs matched the replay exactly, using exact decimals.
- Every file passed its hash, compression and row-count checks.
- There are no sequence gaps and no duplicate trades.
- **One reconnect gap**, November 12, 08:50:57.50–08:51:00.13 (2.6 s). Analyses mark it as missing.
- At each hour boundary the recorder's receipt times lag by about 5 s while it rotates files. The trading studies drop the first 10 s of every hour.

The detailed validation logs are inside the recording folder (`local_validation_complete.json`).

**Format.** One gzip file per hour, one JSON message per line:

- **Book snapshot:** the full book, sent at the start.
- **Book delta:** a size change at one price, *added* to the size there.
- **Trade:** price, count and taker side.
- **Ticker:** about once a second, carrying Kalshi's reference index.
- **Saved book:** the recorder's own full copy, used for checking.

Every message has the exchange's timestamp and the recorder's receipt time. Contract size is 0.0001 BTC, and the tick is $1/BTC (about 0.14 bp).

## What else was looked into (October 2026)

Before recording, earlier sessions searched for *historical* order-book data. Conclusions:

- **Kalshi** offers past candles, trades and funding rates, but no replay of past full books.
- **Coinbase:** no free historical full-depth data was found. Live full depth is free.
- **Deribit through Tardis:** free sample days exist; one (January 1, 2025) was downloaded and checked, at `market_data/datasets/btc_deribit_2025-01-01/`. Wider access is paid, so it was not pursued.

That is why the project recorded its own data. The old notes on these searches, the live-recording guides and the Notre Dame CRC job guide are in `_archive/btc_2026-11-18/`. The job script itself is `jobs/kalshi_btc_crc.job`.
