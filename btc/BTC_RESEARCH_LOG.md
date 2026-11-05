# BTC research log

## Current result — October 29, 2026

**Latest budget/preference:** no fees; the user is leaning toward self-collecting Kalshi data. Recommend reliable data-only Kalshi BTC-perp recording on existing resources, with reconnect/sequence recovery and visible missingness, instead of purchasing historical access. No subscription was purchased: the Tardis/Deribit day was a free sample. The prior bounded Kalshi run stopped after connection failures; it needs hardening before unattended collection. New recording does not backfill old depth, and no indefinite recorder or paid hosting was started in response to this preference.

**Latest user clarification and result:** Kalshi is preferred, but historical full-depth alternatives are acceptable. A complete Jan 1, 2025 **Deribit BTC-PERPETUAL** book/trade day is now saved and reconstructed: **15,452,352 price-level records, 50,816 trades, 1,440 full-book checkpoints**. Both raw archives match advertised MD5 checksums. Native-message access also worked for one historical minute (1 snapshot, 8,652 changes, intact change-ID links); the first normalized checkpoint and all 28 native trade records reconciled exactly. Full-day native sequence continuity remains unverified. [Dataset](../market_data/datasets/btc_deribit_2025-01-01/README.md), [source decision](FULL_DEPTH_SOURCE_DECISION.md). No orders or paid subscriptions were used.

**Authoritative scope correction:** the user wants external historical order-book snapshot/update/trade messages for markets beyond their existing recordings, not another analysis of their old BTC 15-minute event files. The earlier archive recounting and plots were misdirected; the user already knew that data existed. Follow [AGENTS.md](../AGENTS.md) and [current next steps](BTC_NEXT_STEPS.md). Actual external GET tests now returned historical normalized L2 snapshots/updates for Deribit BTC-PERPETUAL and BitMEX XBTUSD on Jan 1, 2025. These are bounded prefixes, not complete days or native-message replay validation. [Evidence and remaining checks](EXTERNAL_HISTORICAL_BOOKS.md).

BTC now has its own active data and feature-engineering track, authorized independently of equity work. We have historical prices, coarse historical liquidity, Kalshi perp quote history, an executed descriptive TDA pilot, and **176 audited historical BTC binary-contract book files from the HFT archive**. An authenticated data-only perp stream passed a 90-second probe and started a bounded one-hour capture; [live status](../market_data/samples/kalshi_btc_stream_2026-10-29_session01/status.json) is authoritative for its current state. No forecast advantage or trading strategy has been established. No orders were submitted in this work.

Read [the data/source assessment](DATA_SOURCES.md), [the feature findings](experiments/initial_features/README.md), and [current next steps](BTC_NEXT_STEPS.md).

## October 29 — What can we actually collect?

**Question.** Can we obtain historical BTC liquidity, including Kalshi perpetuals, rather than just candles?

**Measured result.** Saved locally:

| Source / object | Observed coverage, UTC | Size | What it preserves |
|---|---|---:|---|
| Binance BTCUSDT USD-M perp, 5-minute bars | Jan 1, 2024–Oct 27, 2026 | 296,928 bars | OHLC, BTC/USDT volume, trade count, taker-buy volume |
| Same perp, cumulative depth bands | Jan 2025 | 89,220 snapshots; 892,200 band rows | Displayed depth and notional at ±1%, ±2%, ±3%, ±4%, ±5% |
| Kalshi `KXBTCPERP`, 1-minute candles | First returned candle ends Jun 3, 2026 14:02; last ends Oct 28 00:00 | 208,328 candles | Bid/ask/trade OHLC, volume, open interest |
| Kalshi full reported REST depth | Oct 29, approximately 04:08–04:10 | 60 snapshots over two minutes | Price levels and aggregate quantities at each poll |

Binance bars have no missing or duplicate periods. Its depth has two gaps of about 15.5 minutes; no interpolation was applied. Kalshi is missing 6,232 requested minutes, including 3,721 before the first returned observation and 2,511 at or after it. Another 773 returned candles have null trade closes. We do not infer a launch date or explain missing periods from these counts alone.

**Intuition.** Candles describe what happened to prices; depth describes displayed orders still resting at an observation. Volume and open interest are useful context, but cannot recover that book. A depth band tells us the total quantity within a region, without revealing where inside it orders sit. Therefore the 1% Binance band cannot support claims about gaps 10 basis points from the best quote.

**Kalshi units matter.** The API ticker is `KXBTCPERP`. At collection, its contract size is 0.0001 BTC and underlying multiplier is 1. A $7.97 API price is approximately $79,700/BTC. Contract counts × 0.0001 give BTC quantity; API contract price × contract count gives USD notional. Original strings and metadata are retained. Binary Yes/No complement rules do not apply.

**Validation.** The [offline audit](../market_data/datasets/btc_independent_audit.json) verified 332 original files against recorded hashes and compared all normalized price, depth, and candle values against originals. Binance archives also match published checksums. Missing-range files are saved alongside the datasets. These checks validate storage/transformation, not the exchange's complete historical capture.

**Decision.** Use the continuous Binance price series for the first temporal-geometry study. Keep Kalshi as a separately identified perp source for quote/liquidity work. A long historical Kalshi multilevel depth archive is still unestablished. Public REST market data worked without credentials; authenticated sequence-aware WebSocket access has not been tested.

## October 29 — Does loop persistence mean more than volatility?

**Construction.** One observation is a past window of 288 five-minute log returns, a 24-hour span. Build 3D points `(r[t], r[t+3], r[t+6])`, then use a declared evenly spaced subset of at most 128 points. Compute Vietoris–Rips H0/H1 with Euclidean distance. Produce both raw-return-basis-point and within-window standardized versions. The window advances by 288 returns; 1,030 full windows are available. Timing and point selection are retained in the [specification](experiments/initial_features/specification.json).

**Controls.** A repeating oscillation has longest standardized H1 lifetime 2.302; the same values shuffled have 0.642. A threefold amplitude change triples raw persistence but leaves standardized persistence unchanged. Reversing the oscillation leaves persistence unchanged as well. Gaussian noise, a single jump, and a variance burst were also run. These are examples, not distributions of significance tests.

**Intuition.** The oscillation revisits states in an organized order and makes a loop. Shuffling preserves the values and variance while changing adjacent delay coordinates. But a spectrum and autocorrelation also distinguish these signals. This control demonstrates feature meaning, not an advantage over those ordinary features. Reversal gives an isometric delay cloud (coordinate reversal), so this construction generally loses time direction.

**Real-data result.** Spearman correlation of longest raw H1 lifetime with window return standard deviation is **0.820**. For the standardized version it is **−0.051**. Raw geometry strongly reflects scale here. Removing that association does not establish independent information, a market mechanism, or predictability. The full conventional-feature comparison matrix is saved.

**Validation / decision.** Scale, reversal, constant-signal, finite-output and causal-prefix checks passed. Keep both scale and shape features; inspect sensitivity and source windows before selecting a forecasting task. Every date used in this descriptive pilot is development data; no untouched holdout is claimed.

## October 29 — Can the liquidity pipeline retain location and time?

The [liquidity pilot](../liquidity/experiments/btc_liquidity_features/README.md) creates 89,220 historical band-depth baseline rows, 208,328 Kalshi quote-baseline rows, and a 65-by-60 fixed-price grid from the two-minute live sample. Its actual H0 superlevel persistence retains peak price, observation time, and the merging component's spatial/temporal extent. Threshold component counts match independent connected-component labeling on controls and 31 real-grid thresholds.

This uses a four-neighbor **vertex grid**, not the earlier closed-square cubical example and not H1. Persistence measures log-depth contrast; the separately attached component time span measures seconds. A displayed concentration is not proof that the same order remained there or that it would execute. The short sample establishes working plumbing and source attribution only.

## October 29 follow-up — Existing HFT history and new fine-grained capture

**User direction.** Inspect the HFT Kalshi orderbook predictor for techniques and existing access, start collecting data, and do not submit orders.

**Historical discovery.** The HFT `data/` and `collector/rawdata/` directories contain 176 distinct binary-contract JSONL files despite their `.csv` extension: 3.515 GB, 415 snapshots, 13,534,604 book deltas, and 822,336 public trade messages across parts of April 20–23, 2026. All 176 passed conservative exact-decimal replay with no detected sequence gaps, unsupported book records or negative resulting quantities. Some originals also contain private fills; their payloads were not exported. [Inventory](../market_data/datasets/hft_kalshi_archive_inventory/README.md).

**Correction to earlier scope.** We do have historical Kalshi binary-contract books in this HFT archive, which had not been inspected in the first collection step. This does not supply long historical BTC-perp books. No perpetual backfill was inferred from binary data.

**Technique findings.** Raw retention, snapshot replacement, additive deltas, and conventional depth/imbalance baselines transfer to the new study. The C++ 99-cent-slot representation would lose actual subcent structure: audited books reach 203 simultaneous Yes levels and include prices such as 0.0110/0.0120. Preserve native precision. The older readers do not validate sequence continuity, and size-based cancellation/fill heuristics are simulator assumptions, not observed classifications. [Full review](../liquidity/HFT_KALSHI_REVIEW.md).

**New capture.** A new independent recorder reads the existing HFT signing credentials in place, connects to the perp WebSocket, and subscribes only to public book updates and trades. It has no trading REST client or order functions. The original HFT collector/strategy executables were not launched. A 90-second probe captured 26,250 deltas and 203 trades without gaps or reconstruction errors; all 18 saved checkpoints matched raw-message replay exactly. A subsequent one-hour capture with a 512-MiB raw-journal cap was started; the live status file above records progress and errors. Existing credentials were not copied into source, outputs or command arguments.

**Decision.** Use the historical binary books for immediate depth-geometry work while building a separate perp archive. Keep instrument, sequence/reset boundaries, physical price precision and clocks explicit. The current recorder is a bounded process, not a permanently installed collection service. Longer uptime and live recovery validation remain open.
