# Equity research: current decision and open choices

Updated October 29, 2026. **The completed research story now lives in [EQUITY_RESEARCH_LOG.md](EQUITY_RESEARCH_LOG.md).** This page contains the current decision, not superseded proposals. Exact settings and results stay in the linked experiment records.

**Use [EQUITY_VALIDATION.md](EQUITY_VALIDATION.md) for reconciled numbers and graphs.** It distinguishes full history from the later period, aligns all gate comparisons on common dates, and separates realized volatility from risk-forecast error. Eight audit reruns plus legacy reconstructions passed without changing strategy results.

## What is complete

We collected the original 30-stock panel, explored correlation/PCA, implemented weighted residual reversal, ran backtests/diagnostics, compared peers and the H0 hierarchy, tested 1/5/20-session responses, expanded to 200 stocks, and ran the broader structural comparison. October 29 work includes the broader rerun, scalar/image regime tests, literature reassessment, full-basket day states, and matched EFA/PCA. See [running-log entries 01–15](EQUITY_RESEARCH_LOG.md); entry 13 is a review and entries 14–15 are executed experiments.

The user accepted the existing 200 stocks. The broader trading rerun, scalar-diagram forecasting/gating experiment, and user-authorized image follow-up are complete. Neither the scalar nor image representations established incremental improvement in their declared comparisons.

The user's subsequent full-basket proposal is also complete. It uses 182 fixed reference-stock coordinates per day and tests both strategy risk and mean, not just a reproduction of the earlier index crash charts. [Full-basket findings](experiments/equity_full_basket_states/README.md).

The user-authorized EFA check is complete: same SPY exposure, three factors, 120-session history, signal, portfolio weights, and timing. All 2,446 fits converged; no structural or trading advantage over PCA is established. [EFA/PCA findings](experiments/equity_efa_vs_pca/README.md).

## Current decision

**Keep average linkage as the stronger tested structural baseline, and retain the expanded SPY/PCA daily strategy as a more favorable but unconfirmed gross return baseline.**

**EFA does not materially change the reversal conclusion.** Later gross CAGR/Sharpe is 3.54%/0.93 versus PCA 3.37%/0.89. The paired mean increment is +0.065 bps/day, interval [−0.104,+0.263]. Future residual correlations and loading-space stability are nearly unchanged; median later cross-method subspace overlap is 0.970. Standalone 1/5/20-session means and slopes remain unresolved. Retain the matched EFA result without choosing a new factor count, rotation, or gate from this favorable point rank. [Executed notebook](equity_efa_vs_pca.ipynb).

**Do not report the later CAGR as overall performance.** Full February 2017–October 2026 EFA CAGR/Sharpe is 0.66%/0.19, PCA CAGR 0.68%, and EFA maximum drawdown 17.1%. [Continuous profit and drawdown](experiments/equity_efa_overall_profit/README.md). Balanced net dollars and selected factor exposures do not mean zero gross stock exposure or zero risk.

**Do not promote the tested persistence-based timing gates.** Later stock-diagram-minus-simple mean is +0.411 bps/calendar day, approximate simultaneous interval [-0.213,+1.035]; lag-diagram-minus-simple is +0.020, interval [-0.799,+0.839]. Forecast-error improvements are also unresolved. The higher stock-diagram point Sharpe and lower active fraction do not establish a reliable incremental effect. [Completed regime findings](experiments/equity_persistence_regimes/README.md).

**The fixed persistence-image follow-up did not improve this result.** It replaced three stock-diagram summaries with sixteen H1 pixels and four H0 bins, alongside a twenty-coordinate ordinary control. Later image CAGR is 1.19%, Sharpe 0.43, versus 3.39% and 1.06 for the old three-summary gate. Forecast MSE rises to 38.103 from 32.812. Image-minus-three-summary mean is −0.857 bps/day, simultaneous interval [-2.451,+0.737]. The image slightly improves earlier point error, without a later improvement. All declared simultaneous intervals include zero. Do not tune resolution to repair the curve or promote the ordinary control from its favorable point rank. [Image findings and audit](experiments/equity_persistence_images/README.md).

**Full-basket state changes give only a weak risk hint.** Four raw/residual and current/change additions reduce later squared log-RMS point error by 2.2–3.4% versus matched controls. RawChange's primary paired difference is −0.00238, simultaneous interval [-0.00600,+0.00124]; no incremental effect is established. Mean forecasts barely improve, and all four later gates have lower point means than their control. Their gross CAGR is 1.55–2.02% versus Controls 2.44% and always-on 3.37%. Do not translate risk detection into a profitability gate without measuring that link. [Executed notebook](equity_full_basket_states.ipynb).

The 3.4% figure is lower **forecast error**, with no allocation based on that risk forecast. Separately, the stock-diagram mean gate has lower later realized volatility than always-on PCA (3.21% versus 3.80%), while active only 69.4% of days. The ordinary SimpleGate reaches 3.18% volatility at 67.2% activity. These favorable point observations remain valid; neither establishes a reliable TDA-specific improvement.

The expanded 120-session SPY-only and three-PC later means are +1.143 and +1.343 bps/day, compared with -1.291 and -0.646 for the matched original thirty stocks. Their mean intervals still include zero. All declared settings are reported; no component count or lookback is selected as a validated winner. [PCA/reversal findings](experiments/equity_expanded_pca_reversal/README.md).

The intuitive distinction is that we can identify stocks whose movements remain related, without establishing that yesterday's relative loser will catch up. H0/single linkage retains useful small branches, but its broad cuts chain most of the basket together, and ordinary average linkage recovers nearly all of its stable local groups.

The expanded study supports average linkage over the tested H0 partitions on future correlation separation. At the matched eleven-group count it also exceeds the broad snapshot-sector gap, with group-size and pair-selection qualifications. It does not establish reversal profit, an optimal lookback, or a generally superior economic classification. [Latest findings](experiments/equity_expanded_structure/README.md).

## What the first regime test settled—and what remains open

The user's persistence/factor-coordinate proposal has now had one bounded forecasting test. The [conceptual note](PERSISTENCE_REGIME_IDEAS.md) separates these objects:

| Point object | Question |
|---|---|
| Stocks in factor-loading coordinates | How are fitted common-return sensitivities arranged? Full eigenvalue-weighted PCA coordinates duplicate correlation geometry; truncation changes it. |
| Days in factor-score coordinates | What combinations of common moves occurred? An unordered cloud loses time ordering. |
| Lagged factor-score transitions | What short temporal patterns occurred, and do their summaries add predictive value beyond simple state variables? |

The executed target was next-twenty-session performance of the fixed **120-session SPY-plus-three-PC daily strategy**, forecast every five sessions with expanding completed-label training. Stock-loading and lag-state clouds each added three fixed summaries to a simple model. Exact windows, membership, scaling, training, and the zero forecast gate are saved in the [specification](experiments/equity_persistence_regimes/specification.json). Controls establish different representation sensitivities; they do not supply a demonstrated forecasting advantage.

The image follow-up addressed one specific omitted distinction: birth-scale and lifetime distributions can differ even when the original three summaries match. The vectorization preserves that distinction in a controlled example, but it did not deliver demonstrated return prediction in the real-data comparison. That separates a successful representation check from an unsuccessful incremental forecasting result.

The subsequent [primary-source coordinate review](literature/tda_regimes_and_coordinate_design_2026-10-29.md) identifies a specific next distinction: **day-return state clouds and temporal changes between diagrams**, rather than another vectorization of the same three-dimensional stock-loading cloud. Our three retained residual directions cover a median 27.63% of standardized residual variance at later formation anchors; this records substantial truncation, not evidence that more components would forecast better.

The user chose full-basket day states rather than the review's proposed four-ETF benchmark. That execution uses a 120-day window, full 182-coordinate raw/residual clouds, current and lag5 diagram information, and shared ordinary controls. Risk is the primary target; mean and gates are secondary. The original four-ETF/sixty-day proposal remains a historical suggestion, **not a pending task or a completed replication**.

The full-basket result does not establish whether a different temporal construction would add value. Before another run, specify a distinction the current unordered clouds and ordinary change controls cannot capture, and whether the objective is risk or mean. Do not expand windows, dimensions, thresholds, or learners merely to select a better historical curve. A frozen approach on new observations remains the cleaner confirmation. No further experiment is inferred from the current point ranking.

If another equity experiment is chosen:

- Keep average linkage and the appropriate sector/PCA comparisons. H0 from correlation-distance components is single linkage; renaming a cut is not an incremental TDA method.
- Separate structural coherence from reversal prediction. A whole-market diagram also needs an explicit mapping to a stock-level exposure or clearly defined conditioning variable before it can enter a strategy.
- Use past-only admission and estimation, account for missingness and overlapping observations, and declare uncertainty comparisons. The expanded study's 272-return admission rule belongs to that experiment; another question may require a different rule fixed in advance.
- Do not call already examined 2024–2026 dates a fresh holdout. More securities do not create independent decades or remove current-survivor selection.
- H1 from the same correlation matrix reorganizes pairwise information; it does not recover otherwise unmeasured higher-order return dependence. Explain a controlled example and a use before adding a feature.

## Reporting and preservation rules

**Use gross/pre-fee performance only.** Do not deduct assumed commissions, spread/slippage, impact, borrow, financing, or a generic fee schedule in default plots, tables, or conclusions. Institutions and retail have different implementation economics; the current stage studies the signal. Historical cost scenarios remain only as provenance.

Continue to state information timestamps, actual price conventions, initial exposure constraints, concentration, and multi-session drift accurately. Excluding fees does not justify fills at an already-observed closing price.

Preserve the frozen source, specifications, datasets, and result files. Put a newly authorized experiment in its own source/output location, then append an intuitive entry to the [running log](EQUITY_RESEARCH_LOG.md). Update this page only when the current decision changes.

## Where to look next

- [Running research log](EQUITY_RESEARCH_LOG.md): what we did and what it means.
- [Persistence-regime notebook](equity_persistence_regimes.ipynb): completed forecasts, gates, profit plots, controls, and uncertainty.
- [Persistence-image notebook](equity_persistence_images.ipynb): fixed image/H0 vectorization versus scalar and ordinary controls, gross profits, grid coverage, and independent audit.
- [Full-basket day-state notebook](equity_full_basket_states.ipynb): all 182 return coordinates, raw/residual current/change features, separate risk/mean tests, and gross gates.
- [Matched EFA/PCA notebook](equity_efa_vs_pca.ipynb): three-factor alternatives with identical signal/weights/timing, gross profit, future residual correlations, and factor stability.
- [Latest structural notebook](equity_expanded_structure.ipynb): plots and tables for the expanded basket.
- [Broader PCA/reversal notebook](equity_expanded_pca_reversal.ipynb): new descriptive PCA, gross daily profits, horizon tests, original-basket controls, and representation illustration.
- [Persistence/regime ideas](PERSISTENCE_REGIME_IDEAS.md): factor weights versus factor states, geometry identities, and the proposal linked to its completed first test.
- [Regime literature and coordinate design](literature/tda_regimes_and_coordinate_design_2026-10-29.md): exact published/preprint point choices, our dimensions and preprocessing, and the proposed next bounded question.
- [Residual-response notebook](equity_reversal_response.ipynb): direct catch-up tests and peer-stability comparisons.
- [Mean-reversion scope](MEAN_REVERSION_SCOPE.md): short-run reversal versus price equilibrium and long-horizon valuation.
- [Verified strategy math](literature/residual_mean_reversion_151_2026-10-28.md): exact weighted-residual construction.
