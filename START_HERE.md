# Financial TDA research — current starting point

**November 10 equity refresh and consolidation:** the same 200 equities plus SPY now have a separate audited daily vintage through **November 9** (nine added sessions). [Consolidated equity document](equity/EQUITY_RESEARCH_LOG.md) now includes all 23 research steps, full saved method specifications, reconciled performance/risk findings, and the single/average/centroid explanation. [Latest descriptive update](equity/experiments/equity_recent_refresh_2026_11_10/README.md) tests the centroid proposal on identical vectors and distinguishes the user's deleveraging hypothesis from measured returns and documented fund-risk cuts. Existing strategy/forecast ledgers remain on the October 27 vintage; BTC/liquidity work is separate.

**November 10 CRC collection setup:** [deployment guide](btc/CRC_COLLECTION.md) and
[Grid Engine job](jobs/kalshi_btc_crc.job) are prepared for a new Kalshi BTC-perp
capture on the student/CRC system. No remote submission or new local capture
was launched; the completed November 5 archive below remains preserved.

**Latest collection instruction, November 5: stopped and finalized.** At the user's explicit request, both Kalshi BTC-perp and Coinbase reference feeds stopped gracefully at **11:15:26 p.m. Indianapolis**. The recorder PID no longer exists; all 52 gzip segments are closed, the final manifest is saved, and no partial files remain. [Completed-run pointer](btc/ACTIVE_CAPTURE.json) · [Collection guide](btc/LIVE_COLLECTION.md). Preserve the archive and STOP marker; do not restart without a new user request. All 52 closed files passed hash, gzip and row-count validation; all 11,467 checkpoints and 25 carried hour-boundary books matched exact-decimal replay. The archive contains 21,694,928 book updates, 165,084 trade messages and 130,962 regular Coinbase samples, totaling 725.14 MiB compressed. Interruptions are retained. [Completion report](btc/experiments/btc_archive_final_2026_11_05/README.md). The November 4 start instruction is superseded. No order actions or paid services were involved.

**Latest user instruction, November 4:** use the existing **`tda` Conda environment** for project Python/notebooks. The user explicitly requested a **ten-minute Kalshi BTC-perp capture** for BTC features and liquidity, and asked us to consult the existing HFT C++ recorder. [Live-collection guide](btc/LIVE_COLLECTION.md) records this run and its final validation. It captures public L2 snapshots/deltas, trades, and ticker context; L2 does not identify every participant's order. No indefinite service, paid access, or order action is authorized. Older October 29 historical-data priorities below remain historical context; new capture is now expressly requested and does not backfill prior books.

**October 29 Coinbase follow-up:** [historical access/key/storage assessment](btc/COINBASE_HISTORICAL_API.md). Existing ECDSA key passed a view-only permissions check; public BTC-USD spot depth worked without a key. One-minute measured volume extrapolates to 5.86 GB/day raw L2 or 0.397 GB/day compressed journal. Free historical replay was not found in reviewed Coinbase APIs. A bounded probe completed; no ongoing Coinbase recorder or platform switch was initiated.

**Latest BTC budget/preference, October 29:** no fees. The user is leaning toward self-collecting Kalshi BTC-perp data. Recommend hardening the existing data-only recorder on existing resources; do not buy historical data/API access or paid hosting. The free Deribit sample remains development data. New capture does not backfill past depth, and no indefinite service was started from this preference. Follow [AGENTS.md](AGENTS.md).

**BTC/liquidity scope correction, user October 29:** follow [AGENTS.md](AGENTS.md). The current request is to investigate **external historical book-message data for markets beyond the user's existing recordings**, with relevant BTC spot/perpetual markets and Kalshi perps in scope. The user is **not asking to revisit the BTC 15-minute binary-event archive** and already knows it exists. Earlier archive recounting/plots were a scope error, not discoveries addressing this request. Live capture is separate from historical availability. No order submissions, amendments or cancellations are authorized.

Updated October 29, 2026. **Read this first in future chats.** This file is the authoritative summary of the current research direction; linked documents provide detail only when needed. Original data-access measurements are dated October 12; later equity updates are identified below.

**October 29 equity status:** broader PCA/reversal, scalar/image regime gates, full-basket day states, and matched EFA/PCA are complete. No reliable short-term residual reversal or incremental TDA gate is established. The latest EFA comparison keeps SPY plus three factors and all signal/weight/timing choices fixed: later gross CAGR 3.54% versus PCA 3.37%, paired mean increment +0.065 bps/day, interval [−0.104,+0.263]. Future residual correlations and loading stability are nearly unchanged. **Read [running-log entries 01–15](equity/EQUITY_RESEARCH_LOG.md), [current decision](equity/EQUITY_NEXT_STEPS.md), and [EFA/PCA findings](equity/experiments/equity_efa_vs_pca/README.md).** BTC and liquidity remain separate mini-studies.

**Equity validation reference:** [EQUITY_VALIDATION.md](equity/EQUITY_VALIDATION.md) now reconciles periods, policies, graphs and risk definitions. Eight audit reruns plus legacy reconstructions passed. Preserve both favorable point observations: the stock-diagram mean gate has lower later realized volatility while trading fewer days, and full-basket RawChange has 3.44% lower risk-forecast error. The latter forecast never sizes positions; neither establishes a reliable incremental TDA effect. Full-history EFA CAGR is 0.66%, distinct from its 3.54% later CAGR.

**Current reporting rule — user instruction, October 28:** use **gross/pre-fee performance only** for this research stage. Do not deduct assumed commissions, spread/slippage, impact, borrow, financing, or other fee schedules in default results, plots, comparisons, or conclusions. Institutions and retail have different implementation economics; this stage studies the signal. Original cost-scenario artifacts are preserved only as historical provenance and are superseded as the reporting default. Execution timing, look-ahead checks, exposures, and concentration remain relevant. See [the next-step recommendation](equity/EQUITY_NEXT_STEPS.md) and [current gross report](equity/experiments/equity_residual_backtest/gross_report/performance.csv).

**Organization:** topic work is in [equity/](equity/README.md), [btc/](btc/README.md), and [liquidity/](liquidity/README.md); shared data, reviews, tutorials, and TTK launchers remain at root. [Folder map](FOLDER_LAYOUT.md). Old notebook/script/result entry points are symlink aliases, not copies. The completed equity experiments are indexed in the running log; [EQUITY_NEXT_STEPS.md](equity/EQUITY_NEXT_STEPS.md) contains the current decision only.

**October 29 BTC status after user correction:** current work is external historical full-depth snapshot/update/trade data beyond the user's own recordings. Kalshi is preferred, but the user explicitly accepts alternatives with historical full depth. A complete Jan 1, 2025 Deribit BTC-PERPETUAL L2/trade day via Tardis is now downloaded/checksummed/reconstructed (15,452,352 level rows, 50,816 trades, 1,440 checkpoints). One native historical minute has intact change-ID links and matches the normalized first checkpoint and 28 trades. Full-day native continuity is not independently established. [Dataset](market_data/datasets/btc_deribit_2025-01-01/README.md), [source decision](btc/FULL_DEPTH_SOURCE_DECISION.md), [next steps](btc/BTC_NEXT_STEPS.md). Follow [AGENTS.md](AGENTS.md). Earlier 15-minute binary archive work was outside the intended task. The bounded Kalshi live recorder has stopped; no order actions or paid purchases are authorized. Equity work is separate.

## Agreed initial scope

Learn TDA through **three small financial studies using different mathematical representations**, then decide whether one deserves a deeper project. The central question is:

> What does each topological representation preserve, discard, and make interpretable, and when is that useful beyond ordinary summaries?

The initial three-study framework is agreed. A main application, venue, prediction target, horizon, and model are **not** selected. “Three features” means three families of constructions, not exactly three scalar predictors. This is a TDA learning/research project; optimizing a trading system or demonstrating profitability is not a prerequisite.

| Small study | TDA you would explore | What we would try to learn |
|---|---|---|
| **Equity peer structure and relative-return mean reversion** | Correlation-distance filtrations, H0/H1, clustering or merge structures | Whether multiscale asset relationships define useful peer groups, and whether deviations from weighted peer returns subsequently reverse |
| **BTC feature engineering** | Delay embeddings, persistent homology, landscapes or persistence images | What the features respond to—oscillation, jumps, scale, recurrence—and whether a few interpretable features help a defined task |
| **Liquidity organization** | Cubical persistence and merge trees on price-by-time depth | Whether liquidity concentrations and depleted regions have useful, explainable multiscale structure |

These are three complementary objects: **relationships among assets**, **clouds of temporal states**, and **scalar fields on a grid**. Landscapes and persistence images summarize persistence; using both does not constitute two independent TDA constructions.

## Explanation priorities

**October 28 explanation preference:** explain results intuitively, connecting each displayed quantity to an observed distinction and its practical limits. The user explicitly requests no invented connections. Distinguish computed facts, mathematical properties, supported interpretations, hypotheses, and untested economic causes. Do not assign macroeconomic labels to PCs from sector-looking exposures alone. PCA orthogonality means uncorrelated fitted scores, not independence; variance captured is not return predictability or a count of true economic drivers.

Define a method's actual rule before naming it as a winner or baseline. The user specifically found “average linkage” unexplained: describe the cross-group pairwise averaging and give a small labeled hypothetical example before interpreting its results. Do not substitute another technical label for an explanation. The [running-log example](equity/EQUITY_RESEARCH_LOG.md#what-average-linkage-actually-does) is the current reference.

Read the [equity research log](equity/EQUITY_RESEARCH_LOG.md) for the complete, intuitive history. [EQUITY_INTUITION.md](equity/EQUITY_INTUITION.md) remains the detailed original PCA walkthrough, not the current project ledger. This file supplies project-wide context; a separate `codex.md` is not needed. After each completed equity experiment, append a dated question/result/intuition/decision/evidence entry to the log, refresh its current summary, and update the current decision page. Avoid scattering new historical status paragraphs across navigation files.

The user understands basic topology and wants the missing connection from a TDA feature to an important analytical insight. Explain each construction through **feature → distinction between plausible configurations → interpretation → use**, with a simpler competing explanation. A loop has different meanings in an asset network, a delay cloud, and a depth grid. A change in a scalar topological score is not yet an explanation.

The [review's feature-to-insight section](literature/financial_tda_review_2026-10-12.md#3-what-can-tda-provide-beyond-ordinary-statistics) now develops this bridge. Its [prior-work overview](literature/financial_tda_review_2026-10-12.md#prior-work-in-context-what-has-tda-been-used-to-learn) covers representative nonfinancial applications and maps the financial literature by task before the detailed bibliography.

For a short standalone synthesis of previous findings, read [PRIOR_RESEARCH.md](PRIOR_RESEARCH.md). Keep literature results distinct from our proposed applications.

Current assessment, not a new agreed ordering: equity peers offer a concrete task but H0 overlaps with conventional clustering; BTC provides clear controls for learning feature meaning; annotated liquidity offers a tangible connection to source regions but greater data burden. A strong research outcome explains when a representation preserves a useful distinction and when simpler methods suffice. No incremental real-data TDA advantage or novelty is established. Preserve the three-study scope and open choices below.

## Working interpretation of each study

**Equity:** distinguish two questions: whether stocks have repeatable peer relationships, and whether deviations from fitted peer returns predict reversal. The current work supports the former but has not established the latter. Correlation-derived H0 is single linkage, and no compelling incremental advantage over average linkage is established by our structural comparisons. Exact completed constructions and limitations are in the [running log](equity/EQUITY_RESEARCH_LOG.md); a future hypothesis or specification remains a choice, not permission to rerun or tune old experiments. Options remain a possible later extension.

**BTC:** Start by explaining features on controlled signals and real windows. A univariate delay embedding is sufficient; multiple streams are optional. BTC/ETH or price/volume/spread channels answer different questions and need consistent clocks and scaling. If testing prediction, specify one target and horizon before evaluating held-out data; “improve BTC returns” is too vague.

**Liquidity:** A merge tree could group depth peaks into concentrations and distinguish major branches from shallow ripples. Attach source-region width, temporal span, recency, and distance to the best quote to make those structures interpretable. Branch persistence measures **depth contrast, not seconds**. Abstract trees can lose time direction and price location. Cubical H1 detects enclosed low-depth pockets; an important open gap need not create a hole. These are proposed features, not demonstrated forecasting benefits. Kalshi is one possible venue, not a mathematical requirement.

See [technical examples and regression details](literature/merge_trees_and_return_pilots_2026-10-12.md) only when developing these constructions.

## A bounded evaluation template

For each study:

1. State the data object, filtration, feature meaning, units, and expected invariances.
2. Create a small positive control and a confound/negative control.
3. Inspect a few real examples, tracing features to source observations when possible.
4. Compare with relevant conventional summaries using the same information.
5. Document what is learned and decide whether to deepen, revise, or stop that pilot.

Suggested comparisons: correlation/PCA/clustering for equities; volatility, autocorrelation and spectral features for BTC; depth, imbalance, gaps, turnover and duration for liquidity. Simple regression or other ML is compatible with explainability. Separate feature meaning, source attribution, and model behavior.

Keep preprocessing causal; use later held-out periods and account for overlapping windows. Inspect sensitivity to window length, lag, binning, normalization, missingness, and boundaries. A careful negative result about a representation can be valuable; an unexplained failed backtest is not automatically a contribution.

## Evidence and interpretation to preserve

| Claim | Current assessment from the reviewed literature |
|---|---|
| Describing changes in market structure | Repeated empirical examples, especially around stress; advance warning is less established |
| Adding forecasting features | Positive results in some studies, conditional on construction, target, learner, and evaluation |
| Summarizing geometry across thresholds | Established mathematical capability; financial usefulness still requires validation |
| Predicting liquidity or execution outcomes | A research hypothesis here; no dependable general advantage established |

TDA transforms its inputs; it does not create new information beyond them. Beating average correlation does not mean adding information beyond the complete correlation matrix. Scale alone changes persistence. A long bar is neither a p-value nor an economic mechanism. Liquidity and financial TDA both have prior work; no novelty claim is established. Crisis/risk prediction is background literature, not the user's preferred application.

The [evidence review](literature/financial_tda_review_2026-10-12.md) retains paper links, reported findings, and access/verification limitations. It is a scoping review, not an independent replication.

## Data status

Alpaca access probes were measured October 12; equity datasets were collected October 28, 2026; the independent BTC price/depth collection was completed October 29.

**Equity data:** both the [original 30-stock-plus-SPY panel](market_data/datasets/equity_daily_30_2016_2026-10-27/README.md) and the [expanded 200-stock-plus-SPY panel](market_data/datasets/equity_daily_expanded_2016_2026-10-27/README.md) are saved locally, January 2016–October 27, 2026. The original panel is complete. In the expanded panel, 182 stocks have all 2,720 sessions and 18 have shorter leading histories; there are no internal gaps and no filled prices. Raw/adjusted bars, returns, source pages, coverage, and audits are retained. A SPY-only earlier-history probe returned no pre-2016 bars from the tested feed/account. Both universes use current-survivor selection; the broader one uses a documented current-size rule. This added breadth, not years or historical point-in-time eligibility.

| Need | What is established locally |
|---|---|
| Equity return panels | Daily 30-stock and 200-stock panels plus SPY since 2016. Earlier trading tests use 30 stocks; the expanded structural test uses the broader panel with past-only admission. Intraday samples remain bounded access probes. |
| BTC prices | Continuous Binance BTCUSDT perpetual five-minute history, Jan 2024–Oct 27, 2026, now saved/audited. Kalshi BTC perp minute history is saved separately with gaps/nulls. Prior Alpaca BTC/ETH probes remain separate. |
| Crypto spot depth | Live multilevel Alpaca depth worked. A long historical depth archive has not been established. |
| BTC perpetual historical depth | January 2025 Binance BTCUSDT cumulative ±1–5% depth bands: 89,220 snapshots, with two recorded outages. Coarse band totals do not reconstruct near-quote L2 levels. |
| Options | Metadata, historical trades/bars, and indicative snapshots with Greeks/IV worked. Latest OPRA failed; indicative quotes are modified. Authentic historical quote/IV panels remain unverified. |
| Equity/options full depth | Not provided by the tested feeds; their quotes are top-of-book. |
| Kalshi depth | Existing HFT binary-contract archive: 176 replayable book files, 13.5M deltas, parts of Apr 20–23. Perp REST and authenticated book/trade capture now verified; a bounded one-hour stream was started. Historical perp backfill remains unestablished. |

Detailed endpoint results and reproduction live in [market_data/README.md](market_data/README.md). No orders were submitted. The user authorized retaining paper credentials locally; they are in an ignored private file referenced by that README. Never copy credentials into notes or outputs.

**Kalshi distinction:** binary crypto event contracts and actual perpetual futures are different products. The [documented perps API](https://docs.kalshi.com/margin) is separate. Public candle history/current depth and authenticated perp streaming were measured October 29. Existing historical binary books passed offline replay; historical **perp** book backfill remains unestablished. `KXBTCPERP` prices are USD per 0.0001-BTC contract in the saved metadata. Event-contract bounds, expiry, and complementary Yes/No mechanics must not be applied to perps. The old C++ 99-slot binary representation also collapses observed subcent prices and should not be reused for research replay. Alpaca spot crypto and Binance USDT perps are different markets.

## Existing work and how to resume

**Equity history:** use [EQUITY_RESEARCH_LOG.md](equity/EQUITY_RESEARCH_LOG.md), not a second experiment-by-experiment ledger here. Its entries explain the sequence from data/PCA through backtests, diagnostics, H0, horizon tests, expanded collection, and the broader structural comparison. The [equity README](equity/README.md) indexes notebooks and the [current decision](equity/EQUITY_NEXT_STEPS.md) records open choices.

Keep these points available when resuming:

- **Trading:** preserve the original thirty-stock negative result as historical, not a conclusion about every universe. The broader October 29 rerun has positive later means, still with intervals including zero; 120-session three-PC effective breadth is about ninety versus sixteen original names. Matched original controls reproduce all 4,892 saved overlapping model/date returns. Broader and original frozen-sleeve 1/5/20-session tests do not establish reliable reversal. The common horizon sample has 689 later dates versus 708 daily dates; favorable omitted tail dates materially explain the one-session mean difference. See [PCA/reversal results](equity/experiments/equity_expanded_pca_reversal/README.md). No generic fee deductions apply.
- **Regime/representation result:** the [first completed regime study](equity/experiments/equity_persistence_regimes/README.md) made 379 past-only forecasts from April 2019 onward, scoring 233 development/138 later complete targets and retaining all 708 later calendar executions. Fixed 182 reference stocks; 120-session stock-loading and 119-point lag-state clouds; completed-target training, training-only scaling, fixed ridge penalty and zero forecast gate. All paired incremental intervals include zero. Stock diagrams have a modest favorable later gate estimate; lag diagrams add almost no gate mean and have worse point forecast error. Neither beats the historical-mean forecast's later point MSE. Common day shuffling preserves stock diagrams but changes lag diagrams; both are invariant to uniform return scaling and time reversal. This establishes representation distinctions, not a reliable profitable state. Exact sources, memberships, forecasts, coefficients, and audits are saved; do not promote the point Sharpe or tune more settings solely to rescue the curve.
- **Structure:** the expanded study used 121 nonoverlapping future blocks, 120/252-session geometries, and K=6/11/20/40 on the same 182–200 past-eligible stocks. Average linkage has stronger future correlation separation at every declared cell; H0 retains a giant component. At eleven groups later with 252 observations, gaps are H0 0.0625, average 0.2098, sectors 0.1452. Strong local H0 branches exist but nearly all stable occurrences also appear under average linkage. This is not new P&L evidence.
- **Persistence-image follow-up:** the user-authorized [fixed image test](equity/experiments/equity_persistence_images/README.md) is complete. Four H0 bins plus sixteen H1 pixels added no established benefit over simple, three-summary, or twenty-coordinate ordinary controls. Later image CAGR/Sharpe is 1.19%/0.43 versus 3.39%/1.06 for three summaries; forecast error increased. All primary simultaneous intervals span zero. Baselines, completed-label timing, all 490 vectors/379 forecasts, and inputs reconcile independently. Read running-log entry 12; do not tune image resolution merely to repair the curve.
- **Full-basket day states:** the user then authorized [120 day points in 182 stock-return coordinates](equity/experiments/equity_full_basket_states/README.md), without PCA truncation. Four raw/residual current/change additions were tested against 33 ordinary controls, with separate risk/mean targets. Later risk point errors fall 2.2–3.4%, with all simultaneous intervals spanning zero; mean forecasts barely improve and all four later mean gates trail their control. All 4,548 fits and diagram-change transports reconcile independently. Read running-log entry 14. The review's four-ETF proposal remains unrun; do not infer another search from the point ranking.
- **EFA factor check:** [matched EFA versus PCA](equity/experiments/equity_efa_vs_pca/README.md) is complete. Same SPY plus three factors, prior120 fit, WLS/-W-residual signal construction, weights and raw open-close timing. All 2,446 EFA fits converge. Later gross CAGR/Sharpe 3.54%/0.93 versus 3.37%/0.89; paired daily mean increment +0.065 bps, interval [−0.104,+0.263]. Factor-space overlap is usually high; future residual correlations/stability and 1/5/20 reversal remain unresolved. Read entry 15; do not replace portfolio weights by EFA uniqueness or use a slightly higher point CAGR as established evidence.
- **Math:** intended [151 strategy](equity/literature/residual_mean_reversion_151_2026-10-28.md) uses holdings proportional to **minus W times the WLS residual**, not an unweighted residual after WLS. Complete group indicators span the intercept. Standardized PCA directions need raw-return exposure scaling `diag(training_sigma) @ eigenvectors`; clustering coordinates use eigenvalue weighting instead. Dollar, SPY, and PCA neutrality are distinct. The linked note and source files retain the exact checks and conventions.
- **Evidence and preservation:** notebook plots, full settings, uncertainty, numerical ledgers, and independent audits live with each experiment. Preserve frozen scripts/data/results; a changed method requires a separate experiment. Do not overwrite old specifications or pick settings from already observed profit.

Other existing artifacts:

- [Depth demonstration](liquidity/experiments/depth_topology_demo.py), [figure](liquidity/experiments/depth_topology_demo.png), and [results](liquidity/experiments/depth_topology_demo.json): synthetic matched-summary examples; closed-cell Betti counts, **not** a general persistence-pairing or merge-tree implementation. Assertions and visual checks passed.
- [Matched-moments example](literature/matched_moments_demo.py): synthetic clouds with matched mean/covariance and different persistence. No financial predictive claim.
- [Learning/setup guide](TUTORIAL_GUIDE.md): notebooks, `tda` environment, and working TTK/ParaView launchers. Preserve `~/ttk-binary` and runtime assets.

**Evaluation and scope:** 2024 onward has been examined and is no longer untouched holdout data. The expanded universe does not restore unseen time or remove survivor bias. Further model changes are exploratory unless evaluated on genuinely unexamined data or a separately justified design. Preserve the difference between the tested prior-day-return signal and the source paper's overnight-signal illustration. No profitable strategy or incremental TDA advantage is established. The three-study learning scope remains active; another equity strategy, BTC experiment, or liquidity collector requires its own concrete task/design rather than being inferred from an old proposal.

The user has relevant internship experience but explicitly declined discussing proprietary work. Use public concepts and independently obtained data; do not request or search for internship materials. Sports are outside the current interests.

## Documentation map

Read `README.md` → this file for project-wide context; read [EQUITY_RESEARCH_LOG.md](equity/EQUITY_RESEARCH_LOG.md) for equity history and interpretation. Use the evidence review for literature, the technical note for merge trees/regression, and the market-data README for access. Keep detailed experiment history in its topic log rather than duplicating it here.

The former `research_discussion_notes.md` and `research_brainstorming.md` were consolidated and removed at the user's request. Their superseded plans and repeated discussion are not active instructions. The three-study framework above is the current starting point.
