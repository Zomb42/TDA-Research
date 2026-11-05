# BTC temporal-state geometry

This is the second mini-study: delay embeddings, persistence, and interpretable feature behavior. The agreed question is what these constructions preserve and when they add a useful distinction beyond ordinary time-series summaries. [Project checkpoint](../START_HERE.md).

**Active independently of equity as of October 29, 2026.** Start with the **[BTC running research log](BTC_RESEARCH_LOG.md)**, [data-source assessment](DATA_SOURCES.md), and [current next steps](BTC_NEXT_STEPS.md).

Historical Binance BTC perpetual prices and coarse depth, Kalshi perp minute candles, and a bounded Kalshi multilevel-depth sample are now saved and audited. The [executed feature pilot](experiments/initial_features/README.md) contains 1,030 past-window TDA/conventional-feature rows with controlled-signal checks. A [real liquidity-grid pilot](../liquidity/experiments/btc_liquidity_features/README.md) is also complete. No forecasting advantage has been established, and long historical Kalshi L2 depth remains unestablished. Prior Alpaca samples remain separate feasibility evidence.

The initial study should explain features on controlled oscillations, jumps, volatility changes, and temporal rearrangements before any prediction test. Compare against volatility, autocorrelation, and spectral summaries. A persistent interval measures filtration scale, not elapsed time. A multivariate return cloud and a delay embedding answer different questions.

Shared learning resources: [scikit-TDA tutorial](../scikit_tda_tutorial.ipynb), [synthetic playground](../playground.ipynb), [tutorial guide](../TUTORIAL_GUIDE.md), and [literature review](../literature/financial_tda_review_2026-10-12.md). Keep future BTC-specific notebooks, source, and outputs in this folder.

**HFT follow-up:** the [collector/archive review](../liquidity/HFT_KALSHI_REVIEW.md) found 176 replayable historical BTC binary-contract book files. A separate authenticated BTC-perp stream probe passed exact replay, and a bounded one-hour data-only capture was started. Check its [live status](../market_data/samples/kalshi_btc_stream_2026-10-29_session01/status.json). The earlier historical-depth limitation concerns long **perp** backfill. No orders were submitted and the original trading executable was kept stopped.

Any future performance reporting is gross/pre-fee, per the user's project convention. The BTC work has its own data, log, and next-step page; equity findings remain in the equity track.
