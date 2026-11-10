# QQQ and VIX context for the sell-off reversal check

Collected November 4, 2026 with the existing `tda` environment. Original equity panels are unchanged. No paid access, account-state queries, or orders.

- **QQQ:** Alpaca SIP daily OHLCV, `raw` and `all` adjustment, January 4, 2016–October 27, 2026. Both have 2,720 unique sessions and exactly match the existing SPY calendar. QQQ is an ETF proxy for Nasdaq-100 exposure, not the index itself. All-adjusted prices are vendor return proxies, not an audited corporate-action ledger. Raw response pages and request parameters are retained locally.
- **VIX:** Cboe's public [daily history](https://www.cboe.com/tradable_products/vix/vix_historical_data), 9,308 rows from January 2, 1990 through November 3, 2026 at retrieval. The experiment uses only data through its October 27 end date. `vix_source.csv` preserves the download; `vix_daily.csv` normalizes column names/date formatting. VIX is an options-implied S&P 500 volatility index, not a stock or a realized-volatility estimate.
- **Provenance:** [manifest](manifest.json) records retrieval times, the public Cboe URL, QQQ request URLs without headers, checksums, and calendar validation. Credentials are read in place and never written here.

Alpaca's September 2, 2026 [index-options announcement](https://alpaca.markets/blog/alpaca-launches-index-options-via-trading-api/) explicitly says index data is not currently included in its Market Data offering. VIX option trading support does not supply spot VIX history. This is a documentation-based coverage finding; we did not infer it from an empty stock-symbol request. VIX futures ETFs such as VXX would be different instruments and are not substitutes for VIX index values.

For causal daily features, align VIX by equity session and shift one session, without filling missing observations. A same-date final VIX close is not assumed known before an equity closing-price decision. The experiment saves `qqq_features.csv` and `spy_features.csv` with this conservative lag; it does not retrofit or retune existing factor/TDA experiments.

Reproduce from the project root:

```sh
conda run --no-capture-output -n tda python market_data/download_mean_reversion_context.py
```

The public VIX source is updated over time, so a later re-download can change the snapshot. Preserve this manifest and source for the current results. Bulk QQQ histories use the repository's existing ignore rules. VIX files are small and retained alongside documentation.
