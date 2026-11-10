# Frozen equity universe, refreshed through November 9, 2026

Downloaded November 10 using the existing `tda` environment and Alpaca SIP daily
market data. **200 equities plus SPY, 2,729 sessions, January 4, 2016–November 9,
2026.** All original thirty stocks are included. This adds nine sessions to the
preserved October 27 vintage, with 1,809 new bars per adjustment mode.

The original October 27 holdings, asset master and universe were reused. There
was no selection from today's holdings. All 182 originally complete-history
stocks remain complete; eighteen have leading missing history. No internal or
trailing gaps, no filling, and returns require adjacent observed closes.

Both raw and all-adjusted **full histories** were retrieved: 528,637 bars and
53 complete response pages per mode. Old/new overlap contains 526,828 bars per
mode. Raw OHLC matches throughout; 55,674 adjusted OHLC bars differ, maximum
absolute difference $2.26. These are observed vendor-vintage differences; their
individual corporate-action causes have not been independently audited. Do not
splice adjusted closes from the two vintages. The complete old panel is unchanged.

- [Manifest](manifest.json), [collection plan](collection_plan.json), [frozen universe](universe.csv).
- [Refresh/overlap audit](refresh_audit.json), [independent data audit](independent_audit.json), [coverage](coverage.csv), [checksums](sha256.json).
- `bars_raw.csv`, `bars_all.csv`: observed OHLCV and original timestamps.
- `close_raw.csv`, `close_all.csv`: calendar-aligned closes.
- `returns_simple.csv`, `returns_log.csv`: adjusted adjacent-session returns, in decimal fractions.
- `response_{raw,all}_*.json.gz`: complete cached responses and request parameters; no credentials.
- [Descriptive update and centroid comparison](../../../equity/experiments/equity_recent_refresh_2026_11_10/README.md).
- [Consolidated equity methods and findings](../../../equity/EQUITY_RESEARCH_LOG.md).

The independent audit reconstructs selection, response pagination, row keys,
OHLCV validity, calendar matrices, returns, compounding and missingness. It does
not certify corporate actions or identify who traded. This remains a survivor
sample with snapshot sectors, rather than a historical investable universe.
The original trading/forecast experiments still end October 27; this refresh
does not silently extend their saved results. The earlier SPY-only pre-2016
availability probe again returned no bars from the tested endpoint/account.

From the project root, using `tda`:

```sh
python market_data/refresh_equity_daily.py --end 2026-11-09 --out market_data/datasets/equity_daily_expanded_2016_2026-11-09
python market_data/audit_equity_expanded.py --dataset market_data/datasets/equity_daily_expanded_2016_2026-11-09
python equity/experiments/equity_recent_refresh.py
```

All authenticated requests were GETs to data/calendar endpoints, using the
existing private credential file in place. [Alpaca documents](https://docs.alpaca.markets/us/reference/stockbars)
the daily bars, adjustments, symbol-as-of mapping and page tokens. Raw data stays
ignored by Git; documentation and audit summaries are retained.
