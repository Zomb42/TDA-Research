# Liquidity organization on price-by-time grids

**November 5: first continuous BTC archive analysis and actual Reeb graphs.** [Report and figures](experiments/btc_archive_initial_2026_11_05/README.md). Six closed segments passed validation, including 1,703 full-book checkpoints and exact hour-boundary anchors. Native TTK time-Reeb graphs summarize high-depth band connectivity, but cycle counts vary with preprocessing; a translated fixed ask profile already creates cycles after smoothing. This is exploratory feature interpretation, not an established predictor. **The recorder subsequently stopped at the user's request at 11:15:26 p.m. Indianapolis**; [completed-run pointer](../btc/ACTIVE_CAPTURE.json). No restart is authorized.

This is the third mini-study: cubical persistence and merge structures of displayed depth. [Project checkpoint](../START_HERE.md).

**Working Kalshi direction:** following the user's October 29 proposal, use a snapshot plus fine-grained book changes and executed trades to reconstruct displayed liquidity, then analyze broader price/time scales. See [event-by-event book design](KALSHI_EVENT_BOOK_DESIGN.md) for the distinction between execution flow and resting depth, capture requirements, and the TDA connection.

**HFT follow-up:** [archive/collector review](HFT_KALSHI_REVIEW.md) found 176 replayable historical BTC binary-contract book files (13.5 million deltas). Their subcent price structure should be preserved. A separate authenticated BTC-perp stream probe passed replay validation, and a bounded one-hour data-only capture was started. [Live status](../market_data/samples/kalshi_btc_stream_2026-10-29_session01/status.json). No orders were submitted; the original trading executable was not run.

**See the actual historical data:** [reconstructed book table and depth heatmap](experiments/historical_book_preview/README.md) show an April 23 binary-contract session, with exact native price/quantity rows and an explicitly sampled price-by-time field. This historical dataset is already usable for liquidity geometry; live perp collection is additional data.

**October 29, 2026:** the [real BTC liquidity pilot](experiments/btc_liquidity_features/README.md) now includes historical Binance band-depth baselines, Kalshi quote baselines, a bounded two-minute Kalshi perp depth recording, and H0 persistence on an attributed price-by-time grid. This establishes working data/feature plumbing, not forecasting value. See [BTC source assessment](../btc/DATA_SOURCES.md) and [research log](../btc/BTC_RESEARCH_LOG.md).

Earlier local work is a **synthetic educational demonstration**, not a validated predictor:

- [Depth-topology source](experiments/depth_topology_demo.py)
- [Figure](experiments/depth_topology_demo.png)
- [Numerical results](experiments/depth_topology_demo.json)

The demo calculates closed-cell Betti counts at thresholds; it is not a general persistence-pairing or merge-tree implementation. The broader [technical note](../literature/merge_trees_and_return_pilots_2026-10-12.md) explains candidate constructions and limitations.

Historical Binance data now supplies coarse cumulative depth at ±1–5%; its two January outages are retained. It cannot reconstruct near-quote levels. Kalshi public perp candles and current depth were verified; a long historical Kalshi multilevel archive remains unestablished. The shared [Alpaca data notes](../market_data/README.md) separately establish live spot depth access. Kalshi event contracts, Kalshi perps, Binance USDT perps and Alpaca spot are different products. A final venue for a predictive liquidity study has not been selected.

The shared [TTK notebook](../topology_toolkit_intro.ipynb), [runtime guide](../TUTORIAL_GUIDE.md), `ttk_assets/`, and **ParaView TTK.app** remain at project root so their installed launchers and library paths continue to work. They are reusable learning/runtime assets. They have not been moved or rebuilt.

Attach source-region price, recency, width, and duration to merge measurements. The new pilot retains these coordinates explicitly. Branch persistence measures depth contrast, not seconds. Future performance reporting is gross/pre-fee. BTC and its liquidity-data work are active independently of equity.
