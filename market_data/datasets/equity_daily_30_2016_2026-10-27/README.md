# Equity daily research panel

Downloaded October 28, 2026, using authenticated GET requests to Alpaca. No orders, balances, or positions were requested. Credentials are not included.

## Coverage

- **January 4, 2016–October 27, 2026**, inclusive: 2,720 trading sessions.
- **30 equities plus SPY**: 84,320 daily bars per adjustment mode.
- Both `raw` and `all` (split, cash-dividend, and spin-off adjusted) SIP bars retained.
- 2,719 daily returns per symbol; the first session has a blank return.
- All 31 symbols cover all requested calendar sessions; no missing bars or forward filling.
- Approximately 54 MB including original JSON response pages and CSV derivatives.

| Manual research group | Stocks |
|---|---|
| Technology | AAPL, MSFT, NVDA, AMD, ORCL |
| Financials | JPM, BAC, C, GS, MS |
| Health care | JNJ, PFE, MRK, ABBV, AMGN |
| Energy | XOM, CVX, COP, EOG, SLB |
| Consumer staples | WMT, COST, PG, KO, PEP |
| Industrials | CAT, DE, HON, UPS, UNP |
| Benchmark | SPY |

These are coarse manual labels for a learning basket, not historical sector classifications. The basket was chosen before inspecting downloaded return results, to provide several plausible peer groups with long histories. It is a current fixed basket with selection/survivorship bias, not an investable point-in-time universe. SPY should normally be excluded from the 30-stock peer network and used separately as a market control.

## Files

- `returns_log.csv`: date-by-symbol natural log changes in all-adjusted closes; suggested input for the initial correlation study.
- `returns_simple.csv`: date-by-symbol `close_t / close_previous_session - 1`, as decimal fractions (0.01 means 1%).
- `close_all.csv`, `close_raw.csv`: date-by-symbol closing-price matrices.
- `bars_all.csv`, `bars_raw.csv`: long-format OHLCV, trade counts (`n`), vendor VWAP (`vw`), and original timestamps. Field names follow Alpaca.
- `response_all_*.json`, `response_raw_*.json`: original paginated bar responses, with all pages retained and pagination exhausted.
- `calendar.json`: Alpaca session calendar; dates are interpreted in America/New_York.
- `universe.csv`: symbols, manual groups, and benchmark role.
- `manifest.json`: request settings, retrieval times, per-symbol coverage, quality checks, and flagged observations.
- `sha256.json`: hashes for generated data and metadata at download completion; this README is separate from the hashed download artifacts.

To load the equity return panel with pandas:

```python
from pathlib import Path
import pandas as pd

root = Path("market_data/datasets/equity_daily_30_2016_2026-10-27")
universe = pd.read_csv(root / "universe.csv")
symbols = universe.loc[universe.role.eq("equity"), "symbol"].tolist()
returns = pd.read_csv(root / "returns_log.csv", index_col="date", parse_dates=True)
equity_returns = returns[symbols].iloc[1:]
market_returns = returns["SPY"].iloc[1:]
```

## Validation and limits

Checks passed: fully exhausted pagination, unique symbol/session observations, alignment to the trading calendar, positive finite OHLC, OHLC ordering, nonnegative volume, and return compounding back to each adjusted endpoint price ratio. Raw and adjusted downloads both contain nine pages and 84,320 bars. These are internal consistency checks, not an independent audit against a second data vendor.

Six all-adjusted moves exceed 25% in absolute value: AMD (2016-04-22), NVDA (2016-11-11), EOG and SLB (2020-03-09), COP (2020-03-24), and ORCL (2025-09-10). Adjacent raw and adjusted bars were inspected; large price moves are also present in raw prices. Preserve these observations and investigate them before any proposed filtering. Their economic causes have not been independently checked here.

Daily SIP bars use Alpaca's aggregation rules. This download does not independently establish that each close equals the regular-session closing-auction price. Adjusted prices reflect vendor adjustments and numerical precision as retrieved, with symbol mapping explicitly set to 2026-10-28. Adjusted close changes are not an independently audited total-return index or an executable trading P&L series. Absolute adjusted price levels are unsuitable as causal trading features without further consideration of historical corporate-action information.

Daily returns are suitable for initial dependence and peer-group studies. They cannot establish intraday opportunities or executable reversal profits. A signal that uses a day's closing observation needs a subsequent feasible entry rule. Keep later years held out before tuning peer groups or return forecasts.

The Basic plan's **30-symbol restriction concerns live WebSocket subscriptions**, not the historical REST universe. This 31-symbol historical pull succeeded. Historical SIP access succeeded with the saved credentials; current live SIP entitlement was not retested.

Official references, checked October 28, 2026: [plans and limits](https://docs.alpaca.markets/us/docs/about-market-data-api), [historical bars and adjustments](https://docs.alpaca.markets/us/reference/stockbars), [feed/access FAQ](https://docs.alpaca.markets/us/docs/market-data-faq).

## Reproduce

From `Senior-Fall/TDA_Research`:

```sh
python3 market_data/download_equity_daily.py \
  --start 2016-01-01 --end 2026-10-27 --asof 2026-10-28 \
  --out market_data/datasets/equity_daily_30_2016_2026-10-27
```

The downloader uses saved paper credentials or the existing `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` environment variables. Credentials are never placed in command arguments or outputs. Vendor revisions can change a later repeat download; use a new output directory to preserve this snapshot.
