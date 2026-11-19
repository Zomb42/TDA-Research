# Market data

Download, recording and audit scripts, plus the datasets they produce. Bulk files are on this machine only, not in git; each dataset folder keeps a README, a manifest and its checks. Only free, public or already-entitled data is used, with read-only access and no orders. Rules: [AGENTS.md](../AGENTS.md).

## Datasets in use

| Folder | What it holds | Used by |
|---|---|---|
| `datasets/equity_daily_expanded_2016_2026-11-09/` | Daily bars for 200 large US stocks plus SPY, 2016 to November 9, 2026 (Alpaca, raw and adjusted) | equity, all studies |
| `datasets/equity_intraday_2017_2026-11-09/` | Intraday bars for the same stocks, 2017–2026 (`download_equity_intraday.py`) | equity s10 onward |
| `datasets/equity_quotes_1550_2017_2026-11-09/` | Bid-ask spread just before 3:50 pm, every 5th day (`download_equity_quotes.py`) | equity s12 (costs) |
| `datasets/mean_reversion_context_2026-11-04/` | QQQ daily and Cboe VIX history | equity |
| `datasets/btc_binance_2024_2026-10-27/` | Binance BTCUSDT 5-minute bars 2024–2026, coarse depth bands January 2025 | btc b01 |
| `datasets/btc_binance_aggtrades_2026-11-11_17/` | Binance futures and spot trades, November 11–17, 2026 | liquidity l12 onward |
| `recordings/crc/2026-11-10T23-50-19Z-job-1724180/` | Kalshi BTC perp order book and trades, one week (recorded on Notre Dame CRC) | liquidity, all studies |
| `recordings/2026-11-05T03-36-49Z/` | 25-hour Kalshi perp + Coinbase pilot recording | liquidity November 5 Reeb pilot |

BTC data details and validation: [btc/DATA.md](../btc/DATA.md).

## Older datasets and samples (kept, not used by current studies)

- `datasets/equity_daily_30_2016_2026-10-27/` and `datasets/equity_daily_expanded_2016_2026-10-27/` are earlier equity panels behind the archived v1 experiments.
- `datasets/btc_deribit_2025-01-01/` is one free historical Deribit full-book day. `datasets/btc_kalshi_2026-06_2026-10-27/` holds Kalshi perp minute candles.
- `datasets/hft_kalshi_archive_inventory/` inventories the user's older Kalshi binary-contract recordings, which are out of scope.
- `samples/` holds October access probes: Alpaca stocks, options and crypto; Coinbase depth; short Kalshi streams. The October 12 Alpaca findings are written up in `_archive/root_docs/market_data_README_alpaca_and_history_2026-11-17.md`. In brief: Alpaca gives stock trades and best quotes, plus live crypto order books, but no historical depth.

## Credentials

- **Alpaca:** the paper-account keys live in `.alpaca-paper.local.json` (owner-only, git-ignored), or in the `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` environment variables. Download scripts read them in place, and the scripts only read data.
- **Kalshi:** recording keys are read in place by `record_btc_archive.py` and are never copied or printed.

## Scripts

- **Downloads:** `download_equity_*.py`, `refresh_equity_daily.py`, `download_mean_reversion_context.py`, `collect_btc_history.py`, `collect_deribit_historical_day.py`.
- **Recording:** `record_btc_archive.py` (the recorder used for both Kalshi captures), `btc_archive_control.py`, plus the older `record_kalshi_btc_*.py`. No recording is running or planned.
- **Audits:** `audit_*.py` check each dataset against its manifest.
- **Probes and assessments:** `alpaca_probe.py`, `probe_*.py`, `analyze_coinbase_depth.py`, `assess_perp_capture.py`. These are October access tests.
