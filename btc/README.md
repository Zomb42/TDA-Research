# BTC temporal-state geometry

**November 5 first prediction test:** [Kalshi next-minute return pilot](experiments/kalshi_perp_return_prediction_2026_11_05/README.md). On 348 chronological forecasts, adding standardized delay-cloud summaries and recent-return interactions slightly worsens signed-return MSE by 0.126% and improves absolute-return MSE by 0.361%; both simultaneous intervals include zero. Ordinary features have better point errors than simple references, especially for magnitude. Independent numerical checks passed. This is a short pilot, with no trading rule or established incremental TDA benefit; the recorder was left running.

**Collection stopped November 5 at 11:15:26 p.m. Indianapolis**, at the user's request. Both feeds stopped gracefully and all 52 gzip files closed. [Completed-run pointer](ACTIVE_CAPTURE.json) · [Collection guide](LIVE_COLLECTION.md). Preserve the archive; no restart is authorized. All 52 closed files passed hash, gzip and row-count validation; all 11,467 checkpoints and 25 carried hour-boundary books matched exact-decimal replay. The archive contains 21,694,928 book updates, 165,084 trade messages and 130,962 regular Coinbase samples, totaling 725.14 MiB compressed. Interruptions are retained. [Final completion report](experiments/btc_archive_final_2026_11_05/README.md).

**November 4:** use `conda activate tda`. A new user-requested **ten-minute** public BTC-perp capture is described in [LIVE_COLLECTION.md](LIVE_COLLECTION.md), with the dataset's status and replay validation linked there. This is new history for both BTC features and liquidity, separate from the completed October 29 recordings and unresolved historical backfill.

This is the second mini-study: delay embeddings, persistence, and interpretable feature behavior. The agreed question is what these constructions preserve and when they add a useful distinction beyond ordinary time-series summaries. [Project checkpoint](../START_HERE.md).

**Active independently of equity as of October 29, 2026.** Start with the **[BTC running research log](BTC_RESEARCH_LOG.md)**, [data-source assessment](DATA_SOURCES.md), and [current next steps](BTC_NEXT_STEPS.md).

Historical Binance BTC perpetual prices and coarse depth, Kalshi perp minute candles, and a bounded Kalshi multilevel-depth sample are now saved and audited. The [executed feature pilot](experiments/initial_features/README.md) contains 1,030 past-window TDA/conventional-feature rows with controlled-signal checks. A [real liquidity-grid pilot](../liquidity/experiments/btc_liquidity_features/README.md) is also complete. No forecasting advantage has been established, and long historical Kalshi L2 depth remains unestablished. Prior Alpaca samples remain separate feasibility evidence.

The initial study should explain features on controlled oscillations, jumps, volatility changes, and temporal rearrangements before any prediction test. Compare against volatility, autocorrelation, and spectral summaries. A persistent interval measures filtration scale, not elapsed time. A multivariate return cloud and a delay embedding answer different questions.

Shared learning resources: [scikit-TDA tutorial](../scikit_tda_tutorial.ipynb), [synthetic playground](../playground.ipynb), [tutorial guide](../TUTORIAL_GUIDE.md), and [literature review](../literature/financial_tda_review_2026-10-12.md). Keep future BTC-specific notebooks, source, and outputs in this folder.

**HFT follow-up:** the [collector/archive review](../liquidity/HFT_KALSHI_REVIEW.md) found 176 replayable historical BTC binary-contract book files. A separate authenticated BTC-perp stream probe passed exact replay, and a bounded one-hour data-only capture was started. Check its [live status](../market_data/samples/kalshi_btc_stream_2026-10-29_session01/status.json). The earlier historical-depth limitation concerns long **perp** backfill. No orders were submitted and the original trading executable was kept stopped.

Any future performance reporting is gross/pre-fee, per the user's project convention. The BTC work has its own data, log, and next-step page; equity findings remain in the equity track.
