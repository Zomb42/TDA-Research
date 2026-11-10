# BTC research log

## November 5 — Stop and finalize the continuous archive

**User instruction and action.** The user requested stopping and finalizing. Both feeds stopped gracefully at November 05, 2026 at 11:15:26 PM Indianapolis time, using the run's STOP marker. The recorder PID no longer exists, all 52 hourly gzip files are finalized, and no partial files remain. Preserve the data and STOP marker; no restart is authorized.

**Validation.** All 52 closed files passed hash, gzip and row-count validation; all 11,467 checkpoints and 25 carried hour-boundary books matched exact-decimal replay. The archive contains 21,694,928 book updates, 165,084 trade messages and 130,962 regular Coinbase samples, totaling 725.14 MiB compressed. Interruptions are retained. Coinbase also has 36 disconnect snapshots and 1 shutdown snapshot beyond its regular sample counter. Full raw replay checked every recorded Kalshi book message, file-to-file anchors and all checkpoints. The reference journal has 155 sample spacings over two seconds, with maximum 1068.68 seconds. Calendar span is approximately 24 hours 38 minutes, not uninterrupted coverage.

**Decision and evidence.** Retain the finalized archive for subsequent explicitly chosen analyses. Existing experiment inputs/results are preserved. This finalization adds no predictive or trading claim. [Completion report](experiments/btc_archive_final_2026_11_05/README.md), [full validation](experiments/btc_archive_final_2026_11_05/final_validation.json), [collection guide](LIVE_COLLECTION.md).

## November 5 — First Kalshi perpetual return prediction test

**Question.** Do standardized return-delay persistence features improve next-minute Kalshi BTC-perp return forecasts beyond ordinary market/temporal features?

**Construction.** Frozen specification and 26 common closed Kalshi/Coinbase files, excluding live partials and later files. Use a five-second receipt-time as-of clock, ten minutes of past returns, and one nonoverlapping next-minute midpoint-return label per UTC minute. Exclude stale/missing quotes, explicit gaps and connection changes across the feature/label span. There are 528 eligible decisions; after 180 completed labels, score 348 forecasts from 07:10–15:46 UTC. Ridge uses expanding completed-label training, fixed penalty and training-only scaling, with twelve refit dates. Ordinary18 contains fifteen return/volatility/spectrum/book/flow/spot inputs and three fixed return interactions. TDA adds three standardized 116-point 3D Rips H0/H1 summaries; the primary augmented model also interacts each with recent signed return. The levels-only model is a fixed ablation. Absolute return is a separate secondary target. No trade or risk-sizing policy is implemented.

**Result.** Signed-return MSE is 86.2602 for zero, 85.1050 for history mean, 83.2255 for ordinary features, 83.2609 with TDA levels and 83.3303 with TDA interactions. The primary TDA increment worsens error 0.126%, with improvement interval [−0.767%, +0.515%]. Absolute-return MSE is 56.7826 for history mean, 35.6629 ordinary, 35.4639 TDA levels and 35.5341 TDA interactions. Corresponding TDA improvements are 0.558% and 0.361%, both uncertain. Two thousand paired sixty-calendar-minute block draws give simultaneous bands across both additions and targets; all paired pointwise and simultaneous intervals include zero.

**Interpretation and decision.** Ordinary features give favorable point forecasts, most clearly for magnitude; the tested TDA summaries establish no increment. Persistence's sign-reflection invariance explains the declared interactions, not a causal reversal mechanism. This short already-described record supplies few independent episodes. Preserve the frozen benchmark, without tuning its horizon/geometry from these results or claiming a profitable signal. Continued collection and a later predeclared confirmation remain separate; the recorder was left running.

**Validation and evidence.** All 26 files pass hashes, gzip CRC and row counts; selected exact-decimal raw replay matches 311 checkpoints. Independent closed-form ridge reproduces all 72 feature-model target fits and saved reference forecasts, checks all 528 labels and as-of joins, reconstructs uncertainty, and verifies nine geometry windows and sign/scale/constant controls. Maximum forecast discrepancy is 1.03e−13 bps. [Report and three figures](experiments/kalshi_perp_return_prediction_2026_11_05/README.md), [pre-run specification](experiments/kalshi_perp_return_prediction_2026_11_05/specification.json), [metrics](experiments/kalshi_perp_return_prediction_2026_11_05/forecast_metrics.csv), [audit](experiments/kalshi_perp_return_prediction_2026_11_05/audit.json).

## November 5 — First closed archive inspection and time-Reeb liquidity pilot

**Question.** Are the new continuous recordings healthy, what do price/depth look like, and can Reeb graphs explain liquidity structure?

**Measured result.** The frozen closed interval 03:36:50–06:00 UTC (November 4 at 10:36 p.m. through November 5 at 1 a.m. Indianapolis) contains 1,552,329 perp deltas, 14,868 public trades, and 17,175 Coinbase reference samples. All six closed files passed hashing/CRC/count checks; all 1,703 book checkpoints matched independent replay, and both real UTC-hour seam books/sequences agreed exactly. The sole recorded Coinbase interruption recovered after 2.261 seconds; no perp gaps were found. Perp midpoint declined about 0.53%; as-of/freshness-filtered five-second return correlation with spot was 0.623, and median quote difference +1.70 bps. These are descriptive observations with timing limitations. Median combined displayed depth was 351.27 BTC/$28.22m, including $6.82m within 10 bps. [Report](../liquidity/experiments/btc_archive_initial_2026_11_05/README.md).

**Construction and interpretation.** On a mechanically selected ten-minute window, native TTK computed actual Reeb graphs of time on clipped high-depth price/time regions, separately for bids/asks. The primary field uses $10 bins and a $250k-per-bin equivalent density cutoff after centered $10/5-second smoothing. A graph loop represents splitting and rejoining high-depth regions, not a loop in returns or a tracked order. All 17 graph cases matched independently calculated clipped-mesh component/hole counts; known one-band/two-band/loop controls passed.

**Important limit and decision.** Bid graph cycles changed from 18 to 14 with $20 bins, or 34 without smoothing. A fixed ask profile translated with the observed midpoint generated 13 cycles after the same processing, despite no underlying profile-shape change. Moving-frame re-binning raises median first-profile cosine similarity from 0.65→0.97 for bids and 0.54→0.94 for asks, while topology still changes with preprocessing. Investigate midpoint-relative fields and ordinary profile/size/translation controls before interpreting raw graph complexity. Merely relabeling coordinates would not change topology; re-binning/smoothing changes the field. All data are development data, and centered smoothing is not causal. The recorder was left running; no predictive target, order action, or paid source was introduced.

## November 4, 10:36 p.m. Indianapolis — Start continuous perp and spot-reference capture

**User instruction.** Accept the proposed perp-focused dataset and lightweight broader-BTC reference, start both now using existing keys, compress, and create roughly hourly files. The earlier ten-minute authorization applied only to the completed example.

**Action.** Started a detached `tda` process using [record_btc_archive.py](../market_data/record_btc_archive.py). [ACTIVE_CAPTURE.json](ACTIVE_CAPTURE.json) points to the current data/status. Kalshi retains every delivered public `KXBTCPERP` snapshot/delta/trade/ticker message with nanosecond receipt clocks and exact-decimal checkpoints. Coinbase uses the existing ECDSA CDP key to receive BTC-USD ticker/trades/heartbeats and saves a 2 Hz reference with quote age, best quotes/sizes, midpoint, last price and interval trade aggregates; historical trade snapshots are excluded from new volume. No source credentials were copied or exposed, no original HFT executable was run, and no orders/private channels were used.

**Storage and validation.** Each source writes hourly UTC gzip segments; carried perp book anchors permit replay from the start of each new segment without reconnecting. Closed files receive hashes/count/size manifests; live `.partial` files can be prefix-inspected. Offline tests passed hour-boundary replay and interval-volume/deduplication controls. Initial live inspection independently matched all 23 persisted perp checkpoints; both authenticated feeds had zero detected sequence gaps and connection failures. Fresh status remains the authority for later health, not this initial observation.

**Limits and next step.** Continue until stopped, with a 20 GiB archive cap and 10 GiB free-disk floor, preserving recorded history. Temporary idle-sleep prevention is active; forced sleep, lid closure, shutdown and network outages can still create gaps. No login/boot service is installed. Let coverage accumulate, then inspect a closed segment and choose bounded descriptive examples for studies 2 and 3. The original sample remains uncompressed; no prediction target or TDA advantage is established by recording data.

## November 4 — Is a perp-focused dataset sufficient for studies 2 and 3?

**Question.** How much book depth and liquidity do we record, what is the storage burden, how does it compare with the HFT Coinbase/binary recordings, and should the project narrow to perps plus a lightweight BTC reference?

**Measured result.** The ten-minute perp sample has 190–260 occupied price levels at a time and 716 distinct prices across the interval. The existing exact gzip files are 9.83× smaller than the plain files: the measured sample projects to 239 MB/hour raw or 24 MB/hour gzip, about 0.58 GB/day compressed if its rate persists. Median full-book displayed quantity across 119 checkpoints is 350.32 BTC / $28.22m two-sided notional, including $6.82m within 10 bps of the midpoint. Best quotes alone total a median $2.63k. All 176 HFT Coinbase files were read: they contain ticker/trades, no L2 book, with median best-quote notional $25.85k and about 12 MB/hour raw. All 176 binary-event books were replayed: median displayed YES/NO bid cash is $12.37k. April versus November dates and event versus perp units prevent a controlled liquidity ranking. [Full assessment and methodology](../liquidity/experiments/perp_capture_assessment_2026_11_04/README.md).

**Interpretation and recommendation.** Use one perp book/trade dataset for two different objects: temporal delay-cloud features (study 2), and displayed-depth fields (study 3). A twice-per-second spot midpoint/best-quote/last-trade reference is sufficient initial context for seconds-to-minutes questions; a second full book is unnecessary for that scope. This is a recommendation, not a chosen prediction target or evidence of a TDA advantage. Ten minutes validates the pipeline, not the research conclusions. The user now prefers gzip for future capture while keeping this sample uncompressed. No new recorder or paid service was started.

## Latest direction — November 4, 2026

The user specifies the existing `tda` Conda environment and explicitly requests new BTC-perp data for temporal features and liquidity. After clarification, the first run is **ten minutes only**. The HFT C++ worker/writer/session/book code was inspected again; its raw-journal and reconnect pattern transfers, while its event-contract endpoint, 15-minute scheduler, private-fill subscription, and 99-slot binary book do not provide the required perp recorder. Those original files were not changed or executed.

The bounded perp recorder now optionally compresses journals, records nanosecond receipt clocks, retains public ticker context and contract metadata, tracks trade sequences, and counts consecutive failures rather than terminating after five failures spread across otherwise healthy connections. A new offline validator independently replays exact-decimal book states and checks recorded counts, checkpoints, and final file hashes. See [LIVE_COLLECTION.md](LIVE_COLLECTION.md) for the actual run and its final outcome. No predictive experiment, order action, paid service, or permanent recorder is inferred from this capture.

**Completed result:** November 4 at 19:22:29–19:32:29 Indianapolis, using `tda`. One initial snapshot, **114,753 deltas, 1,327 trades, and 599 ticker messages** were retained in **3.86 MiB** of compressed journals. All **119 checkpoints** matched independent exact-decimal raw replay; recorded counts and file hashes matched, with no detected book/trade sequence gaps, reconstruction errors, connection failures, or duplicate trade IDs. Snapshot depth reached 160 bid and 110 ask price levels. The bounded recorder stopped automatically; no ongoing capture is running. These are aggregated displayed L2 records, not individual-order L3. [Dataset and validation](../market_data/samples/kalshi_btc_stream_2026-11-04_10min/README.md).

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
