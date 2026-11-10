# Equity research log

Updated November 5, 2026. **Start here for the story of the equity work.** This is the running record of what we tried, why we tried it, what the results mean, and what remains unanswered. The numbered entries follow the research sequence. Entries 01–09 summarize October 28 work; entries 10–15 record the October 29 broader rerun, regime/image tests, coordinate review, full-basket day states, and matched EFA/PCA comparison. Entry 13 is a review; entries 14–15 are executed experiments. Entry 16 tests an approximation of a user-supplied index sell-off strategy and adds separate VIX context. Entry 17 compares VIX with the original factor-neutral strategy's returns and risk. Entry 18 investigates the user-selected 20–30 VIX band as a fixed exploratory filter. Entry 19 revisits historical TDA regime studies and their use alongside VIX; it adds a review and context alignment. Entry 20 executes the matched ordinary-controls/VIX/TDA comparison with separate risk and mean targets. Entry 21 tests local current-residual-shock merge trees for next-session stock forecasts. Entry 22 tests labeled relationship changes and signed portfolio exposures against covariance and average linkage.

**Validation review, October 29:** use [EQUITY_VALIDATION.md](EQUITY_VALIDATION.md) for reconciled metrics and aligned graphs. Eight existing audits and additional legacy reconstructions passed. All fifty figures embedded in eleven notebooks match saved project images. No numerical discrepancy was found in the audited results; earlier presentations mixed periods, portfolios and risk definitions. This review adds no new strategy experiment.

## Where we stand

**November5 labeled relationship/exposure test:** attaching actual signed holdings to complete H0/single-linkage stock hierarchies gives favorable squared-return forecasting point increments beyond covariance/VIX controls and average linkage. H0 beyond the average tree has QLIKE differences−0.00270 earlier and−0.00523 later, with both simultaneous intervals spanning zero. Later downside improves in point estimate, earlier downside worsens; mean MSE worsens0.410%/0.161%. All1,176 fits and34,956 forecast losses pass audit. This retains stock identities and position alignment, but establishes neither an incremental effect nor a new allocation policy. [Report and figures](experiments/tda_relationship_exposure/README.md), entry22 below.

**November5 local residual-shock test:** current-shock H0 branch prominence/support produce essentially no mean-prediction gain beyond ordinary peer measures and VIX: later improvement0.0043%, simultaneous interval[−0.0021%,+0.0107%], with slightly worse earlier error. Ordinary graph inputs improve individual absolute-relative-move forecasts0.761% earlier and0.177% later; TDA adds negligible earlier benefit and slightly worsens later error. The graph construction distinguishes connected and separated synthetic shocks and retains named branches, but no stock-selection policy follows. All294 ridge refits and saved forecasts reconstruct independently; original holdings/returns are preserved. [Report and four figures](experiments/tda_residual_shock/README.md), entry21 below.

**November 5 matched VIX/TDA follow-up:** the risk hint survives adding VIX, but remains uncertain. On identical original dates and completed-label memberships, VIX reduces later squared log-RMS forecast error by0.95% versus ordinary controls; four cached TDA additions reduce it a further2.16–3.64%. All paired intervals span zero. Mean forecasts barely improve, and all feature models lose to historical-mean prediction later. The independent audit passed all5,306 fits. No trading gate, sizing policy or return ledger changed. [Executed report and figures](experiments/tda_vix_matched/README.md), entry20 below.

**Regime-literature context:** prior studies use day-return landscapes, correlation-network persistence and diagram changes to describe stress, compare distributions, forecast risk or set exposure. Those differ from forecasting this portfolio's mean. Full-basket day states and diagram changes are already tested; full all-layer landscape L1 is exactly one quarter of our squared-lifetime sum. The November4 review aligned all490 anchors to VIX and proposed the comparison now executed in entry20. [Review, illustrations and source caveats](literature/tda_regimes_vix_2026-11-04/README.md).

**November 4 fixed VIX20–30 follow-up:** the user-selected band raises full PCA CAGR from 0.68% to 1.26% and reduces drawdown from 16.99% to 9.33%, while trading 625/2,446 days. Its full volatility-matched comparison is also favorable in point return. Later it returns 1.21% versus always-on 3.37%, with a lower Sharpe and fewer active days. Deleting2020 leaves only 0.27% gate CAGR; deleting2022 reverses its CAGR advantage over always-on. Target means and primary increments remain uncertain, and adding the explicit band indicator does not establish better forecasts. Keep the fixed band as an exploratory benchmark, with no boundary tuning or promotion as a validated gate. [Detailed follow-up](experiments/factor_vix_20_30/README.md).

**November 4 factor/VIX comparison:** prior-session VIX correlates +0.322 with the absolute PCA-strategy return and −0.020 with its signed return. Higher VIX clearly coincides with greater observed risk, but conditional mean signs vary by era. Adding lagged VIX to past S&P volatility/return controls worsens full chronological mean-forecast MSE by 2.00% and improves absolute-return MSE by a small, uncertain 1.80%; all declared simultaneous incremental forecast intervals span zero. EFA agrees. Keep VIX among ordinary state controls for future TDA comparisons, without inferring a profitable gate or sizing policy. [Full findings and audit](experiments/factor_reversal_vix/README.md).

**November 4 index-reversal check:** a specified approximation of a LinkedIn strategy shows strong QQQ/SPY rebound means with optimistic same-close decisions, but the causal next-open versions have mean intervals including zero. This is market-direction reversal, not evidence overturning the residual-factor findings below. Free Cboe VIX history and lagged features are now saved separately; no VIX/TDA gate is established. See [entry 16 and its report](experiments/index_selloff_reversal/README.md).

**Stocks in this basket have repeatable peer relationships. The broader 200-stock daily strategy has positive later gross point estimates, unlike the original thirty-stock result, but its mean intervals still include zero. Average linkage is the stronger tested way to divide the broad basket into peer groups; that structural advantage does not establish a trading-return advantage.**

The first persistence-based regime test and a fixed persistence-image follow-up are complete. Three stock-loading diagram summaries give a modest favorable later estimate versus simple state predictors, and lagged-state features give almost no trading improvement; neither establishes an incremental benefit. Replacing the three summaries with a richer image/histogram representation increased later forecast error and reduced point trading performance. The representations preserve different measured distinctions, but a demonstrated improvement in conditional return prediction remains missing.

The literature review motivated a different object: days in return coordinates and changes between diagrams. The user then proposed using the full stock basket instead of another four-index replication. That comparison is complete: 120 day points in 182 stock-return coordinates, with raw/residual and level/change versions. Later risk point errors improve 2.2–3.4%, but no incremental effect is established; mean prediction and all four later gates fail to beat their matched controls convincingly. See entries 13–14.

The subsequent EFA-versus-PCA factor check is also complete. With the same SPY exposure, three additional factors, signal, weights, and execution, EFA gives 3.54% later gross CAGR versus 3.37% for PCA. Its paired mean increment is only +0.065 bps/day, interval [−0.104,+0.263]. Future residual correlations and factor-space stability are almost unchanged. It does not materially change the conclusion that this short-term reversal premise is unconfirmed. See entry 15.

The later return must be kept in full-history context: February 2017–October 2026 EFA gross CAGR is only **0.66%**, PCA **0.68%**, and EFA's maximum drawdown is **17.1%**. [Continuous profit chart](experiments/equity_efa_overall_profit/README.md). Zero net dollars and estimated factor constraints are not zero gross exposure or zero risk.

Two separate risk observations should also stay visible. The stock-diagram mean gate lowers later realized volatility from always-on PCA's 3.80% to 3.21%, with almost unchanged point CAGR, while trading only 69.4% of days. An ordinary gate also lowers volatility, to 3.18% at 67.2% activity. Full-basket RawChange instead lowers a risk predictor's squared log-RMS error by 3.44%; that predictor never changes positions. The first measures the returns of a trading policy, the second the accuracy of a forecast. Neither establishes reliable incremental TDA value over its matched control.

Those are separate findings:

| Question | What our work supports |
|---|---|
| Are there common movements and recognizable peers? | Yes. PCA, correlations, and clustering reveal them, and past-formed groups retain future correlation structure. |
| Do relative losers subsequently catch up with their peers? | Not reliably established for our one-day signal and tested 1/5/20-session holds. |
| Does the tested H0 construction improve on ordinary clustering? | No incremental advantage established. Average linkage has stronger future correlation separation at every declared cut/lookback in the expanded study. |
| Do diagram features help predict favorable strategy regimes? | Not established in the first scalar-summary or image tests; all declared simultaneous incremental uncertainty intervals include zero. |
| Does full-basket day geometry predict strategy risk or mean? | Modest favorable later risk point estimates, no established incremental effect; mean and trading improvements remain absent. |
| Does EFA improve the factor estimate or reversal strategy versus matched PCA? | No established advantage; three-factor spans are usually closely aligned and the later gross-return increment is small and uncertain. |

The useful positive result is persistent structure. The unresolved step is turning a relative move into a forecast. The negative incremental result concerns the particular H0 construction, not every possible use of TDA.

## Which document should I read?

| Document | Its job |
|---|---|
| **This running log** | Explain the whole equity research story intuitively, with links to evidence. |
| [EQUITY_VALIDATION.md](EQUITY_VALIDATION.md) | Give reconciled performance/risk numbers, common-calendar graphs, definitions and validation evidence. |
| [EQUITY_PROGRESS_REPORT.md](EQUITY_PROGRESS_REPORT.md) | Give a brief report-ready synthesis of completed work, findings, potential TDA uses, and limits. |
| [EQUITY_NEXT_STEPS.md](EQUITY_NEXT_STEPS.md) | State the current decision and open choices. Completed work belongs in this log, not in a growing stack of old plans. |
| [EQUITY_INTUITION.md](EQUITY_INTUITION.md) | Give the detailed original correlation/PCA explanation. It is about the first descriptive notebook, not the entire project. |
| [MEAN_REVERSION_SCOPE.md](MEAN_REVERSION_SCOPE.md) | Separate return reversal, equilibrium price spreads, and multi-year valuation questions. |
| [PERSISTENCE_REGIME_IDEAS.md](PERSISTENCE_REGIME_IDEAS.md) | Explain stock exposure points versus day/state points, the PCA geometry identity, and the original regime proposal, now linked to its completed first test. |
| [TDA regime and coordinate review](literature/tda_regimes_and_coordinate_design_2026-10-29.md) | Compare prior papers' exact point objects/dimensions with ours; separate a proposed next construction from completed tests. |
| Each experiment's README and notebook, linked below | Supply exact settings, full results, plots, uncertainty, and reproduction instructions. |
| [START_HERE.md](../START_HERE.md) | Keep project-wide context and rules across equity, BTC, and liquidity studies. |

## What average linkage actually does

**Average linkage is a rule for building groups: merge the two groups whose members are closest on average.** “Linkage” just means the rule for deciding how far apart two groups are once some stocks have already been grouped.

First we need a distance between each pair of stocks. In our experiments, we compare their prior daily return histories after fitting out SPY and standardizing each stock. More positively correlated residual histories get smaller distances. This measures similarity of historical movement, not how close their dollar share prices are.

The grouping algorithm then works from the bottom up:

1. Start with each stock in its own group.
2. For any two groups, list **every stock-to-stock distance across the groups** and take their arithmetic average. If one group has three stocks and the other has two, average all six cross-group distances.
3. Merge the two groups with the smallest average distance.
4. Recalculate distances involving that new group and repeat. Keeping the merges gives the tree. Stopping when eleven groups remain gives an eleven-group partition; eleven is our chosen cut, not a number the algorithm discovers as economically correct.

Here is a **hypothetical distance example**, not measured stock data. Suppose A, B, and C have already formed a group. D and E are still separate:

| Pair | Distance |
|---|---:|
| D to A | 0.40 |
| D to B | 0.30 |
| D to C | 0.20 |
| D to E | 0.25 |

Average linkage says D is `(0.40 + 0.30 + 0.20) / 3 = 0.30` away from the ABC group. D is only 0.25 away from E, so **between those two candidate merges it prefers joining D and E**. The actual next merge always depends on comparing every candidate group pair.

**Single linkage, which corresponds to our H0 components, uses only the closest cross-group pair.** It calls D only 0.20 away from ABC because of C. Between the same candidates, it prefers attaching D to ABC. A series of such short connections can pull a large chain together even when its distant endpoints are not close.

That difference is why we compare the methods. Average linkage considers how well groups match across all their member pairs; single linkage asks whether there is one short bridge. Average linkage can still make uneven groups and does not globally optimize all possible partitions. In our measured basket it produced stronger future peer separation, rather than being guaranteed superior by definition.

**The word “average” here refers to pairwise distances.** It does not mean averaging stock prices, buying an equal-weight portfolio, or taking average returns as a trading signal. Portfolio weighting is a separate step.

## The central idea in plain language

We started with the possibility that some stock moves are temporary deviations from what similar stocks are doing. Identify the common movement, measure what is left, and ask whether that leftover move subsequently reverses.

As a **hypothetical arithmetic example**, suppose a stock rises 3% while its fitted common movement is 2%. The approximately one-percentage-point difference is its residual: it did better than this particular model expected. A contrarian signal would short relative winners and buy relative losers, while balancing the selected exposures.

But a residual is not automatically a pricing mistake. The stock could give back its relative gain, or new information could justify it permanently. Both are compatible with having moved closely with peers in the past. The actual experiments use the specified log-return signal and weighted regression; the numbers above only illustrate the idea.

We therefore need to separate **describing shared movement**, **predicting a reversal**, and **constructing a portfolio that neutralizes selected exposures**. Success at one does not establish the other two.

## 01 — Collect a daily panel and see what moves together

**Question.** Is there enough visible structure to make a peer-based equity study worthwhile?

**What we did.** Downloaded 30 selected stocks, five in each of six manual groups, plus SPY. The panel spans January 2016–October 27, 2026. The first descriptive analysis used only 2016–2023. We saved raw and vendor-adjusted daily bars and daily returns locally.

**What we learned.** Stocks share substantial common movement, and stocks within our manual groups tend to have closer return relationships than stocks in different groups. Fitting out SPY did not erase all peer structure. For example, the last development window's mean residual correlation was about 0.359 within manual groups and 0.0015 between them. Correlations also changed with the historical window.

**Intuition.** Some of a stock's daily move resembles a broad market move. Some resembles a smaller set of peers. Looking only at raw correlations mixes those patterns together; removing a fitted SPY component helps us inspect what remains.

**Limit.** Correlation is co-movement, not catch-up. These are selected surviving stocks, not a historically investable universe reconstructed at each date.

**Evidence:** [initial notebook](equity_correlation_pca.ipynb), [findings](experiments/equity_correlation_pca/README.md), [original data](../market_data/datasets/equity_daily_30_2016_2026-10-27/README.md).

## 02 — Use PCA to summarize common return patterns

**Question.** Can a few directions describe much of the basket's movement?

**What we did.** Standardized each stock's returns so high-volatility names did not dominate simply because their percentage moves were larger. PCA then found combinations with the greatest sample variance, subject to nonredundant perpendicular directions.

**What we learned.** In the 2016–2023 reference fit, PC1 captured 43.6% of standardized variance and its score correlated 0.928 with SPY. The first three PCs captured about 60.8%; the first ten about 80.4%.

**Intuition.** PCA finds recurring ways the whole list of returns changes. PC1 looked like broad common movement because all stocks loaded positively and its score closely tracked SPY. Other components described contrasts among sets of stocks. The coefficients describe a direction; each day's score says how strongly that day's returns line up with it.

**Limit.** Capturing 80% of variance means reconstructing much of the observed movement. It does not mean predicting 80% of future returns. A component is not automatically an economic cause. Its sign is arbitrary, and its identity can change with the sample. Uncorrelated fitted scores are not necessarily independent.

**Decision.** Keep PCA as a useful linear baseline. Do not add PCs merely to reach a variance percentage and assume the remaining returns will reverse.

**Evidence:** [detailed intuitive walkthrough](EQUITY_INTUITION.md), [component results](experiments/equity_correlation_pca/pca_variance.csv).

## 03 — Implement the intended residual-reversal strategy correctly

**Question.** Can we buy relative underperformers and short relative outperformers while neutralizing selected common exposures?

**What we did.** Verified the cross-sectional weighted-regression construction from the intended *151 Trading Strategies* sections. Each regression row is a stock at the signal time. Historical data supplies exposure columns and inverse-variance weights; the current return vector supplies the signal.

The compact version is `residual = current returns - fitted common returns`, then **holdings proportional to minus W times that residual**, scaled to a fixed total absolute exposure. W contains the positive regression weights. Trading the unweighted residual after a weighted fit would generally lose the neutrality property.

**Intuition.** The regression identifies the part of today's return pattern explained by the selected common exposures. Its leftover vector provides the contrarian direction. The weighting and portfolio construction make the longs and shorts balance against those particular exposure columns.

**Important distinctions.** Dollar neutrality, SPY-beta neutrality, and PCA neutrality are different constraints. PC1 resembles SPY in the descriptive fit but is not identical to it. Estimated factor neutrality does not remove every possible future risk, and it does not create an expected return. Neutralizing all independent stock directions would leave nothing to trade.

**Evidence:** [verified strategy and math](literature/residual_mean_reversion_151_2026-10-28.md).

## 04 — Run the first frozen reversal backtest

**Question.** Does that particular contrarian signal earn a positive gross return with a feasible information sequence?

**What we did.** Used 120 prior sessions ending before the signal day to fit exposures. Compared dollar/SPY neutrality with dollar/SPY plus three residual PCs. Observed the signal day's close-to-close return, then entered at the next vendor daily-bar open and exited at that day's close. Targets had unit gross exposure and no individual position cap.

**What we learned.** Over 708 later execution dates in 2024–October 2026, mean gross returns were about **-1.29 bps/day** for SPY-only and **-0.65 bps/day** with three residual PCs. Both mean intervals included zero. The PCA version had lower later volatility, but no positive return edge was established.

**Intuition.** The portfolio can satisfy its neutrality equations and still have a weak forecast. Removing common risk is not the same as locating temporary errors. Nor does a negative estimate with a wide interval prove that the true expected return is negative.

**Limit.** These are idealized fractional-dollar targets at vendor bar prices, not verified auction fills. One stock's largest target reached about 46% of gross exposure. All current interpretation is pre-fee; assumed fees do not explain these already weak gross results.

**Evidence:** [backtest notebook](equity_residual_backtest.ipynb), [specification and results](experiments/equity_residual_backtest/README.md), [current gross summary](experiments/equity_residual_backtest/gross_report/performance.csv).

## 05 — Check the obvious explanations for that result

**Question.** Did the signal work only in certain periods, reverse before entry, or need more factors removed?

**What we did.** Inspected the gross profit path and calendar returns; examined fixed SPY trend/volatility states; measured hypothetical overnight contributions; and reported an exploratory grid of 0, 1, 3, 5, and 10 residual PCs.

**What we learned.** There were profitable stretches, but the tested regime descriptions did not identify a reliably positive switch. Hypothetical overnight contrarian contributions were negative on average in both original periods; we did not find an aggregate positive overnight reversal that our next-open entry had simply missed. Increasing the combined SPY-plus-PC reconstruction to roughly 80% of raw training stock-return variance did not make the later mean positive. That coverage measure differs from the standardized full-period PCA percentages in entry 02.

**Intuition.** A profitable year is an observation, not a rule for recognizing the next profitable year. Movement occurring overnight is not necessarily predictable profit. Better reconstruction of the past is not necessarily a better return forecast.

**Decision.** Missing positive overnight reversal and insufficient PC count were not supported as simple fixes. The diagnostics did not identify the true economic cause. We did not measure crowding or establish that statistical arbitrage generally is “drying up.”

**Evidence:** [profit graph and diagnostics](experiments/equity_residual_diagnostics/README.md).

## 06 — Test H0 as a way of defining peers

**Question.** Could a dependence hierarchy provide useful peers beyond manual groups or PCA?

**What we did.** Represented each stock by its prior SPY-residual return history, standardized to emphasize correlation rather than volatility. Close points are stocks with similar historical residual moves. Compared six manual groups, six average-linkage groups, six H0/single-linkage components, and an exposure-count-matched PCA baseline under the same trading timing and weighting.

**What H0 means here.** Start with separate stock vertices. As the distance threshold rises, connect close stocks; H0 records when connected components merge. For this construction, that is the **single-linkage hierarchy**, not a new clustering algorithm. Average linkage instead compares average distances between members of groups.

**What we learned.** H0 and single linkage produced identical groups and holdings, as they should. The six-component H0 cut often put most stocks in one component: its later largest group averaged 21.6 of 30 stocks. No peer definition established a positive later gross mean.

**Intuition.** Single linkage can connect A to B and B to C even if A and C are not particularly similar. Repeating that process creates a chain. A persistent merged component can therefore be too broad to serve as a useful all-member peer group. A singleton is also consequential: imposing neutrality to a group containing only one stock forces that stock's holding to zero.

**Coordinate lesson.** Full eigenvalue-weighted PCA coordinates preserve the same correlation distances; they do not supply independent new information. Truncation changes the geometry. Plain full eigenvector rows are equally distant from one another and are unsuitable as a similarity map. Adding the complete PCA coordinates to their source return coordinates duplicates the same geometry.

**Evidence:** [H0 notebook](equity_h0_peers.ipynb), [construction, controls, and results](experiments/equity_h0_peers/README.md).

## 07 — Check the whole hierarchy rather than blaming one cut

**Question.** Did six groups hide useful smaller branches?

**What we did.** On the 30-stock panel, inspected all group counts, changed historical windows, resampled blocks of days, compared future correlation structure with group-size-matched random labels, and checked whether exact named branches recur anywhere in perturbed trees.

**What we learned.** Yes: stable local groups existed inside the poor global partition. But all 126 later stable H0 branch occurrences also appeared in average-linkage trees, and 119 were stable under both. Average linkage had stronger future coherence at many broader cuts. A narrow H0-favorable result at 27 groups left about 25.6 stocks isolated and did not support a broadly useful partition.

**Intuition.** Cutting a tree horizontally forces one global partition. Looking at branches separately can expose a good small group even when the global cut is unhelpful. However, finding a repeatable local set is different from showing that H0 uniquely finds it or that its relative returns reverse.

**Limit.** “126 occurrences” repeats groups across dates and can include nested groups. It is not 126 independent discoveries. Persistence across distance thresholds is not duration in calendar time or a statistical confidence level.

**Evidence:** [whole-hierarchy notebook](equity_h0_scale_robustness.ipynb), [findings](experiments/equity_h0_scale_robustness/README.md).

## 08 — Directly test catch-up over one day, one week, and about one month

**Question.** Do bigger residual moves predict opposite subsequent moves, perhaps over a longer hold? Does having stable peers help?

**What we did.** Compared manual peers, average-linkage peers, and PCA on the same 30 stocks at fixed 1/5/20-session horizons. Entered after the signal at the next vendor-bar open, held the initial sleeves, and kept formation exposures fixed for outcome attribution. Also compared high- versus lower-stability peer assignments using past-only window variations.

**What we learned.** Every overall response-slope and gross-event-mean interval included zero in both periods. Some estimates favored reversal: later manual five-session gross return was **+3.66 bps/event**, interval **[-0.56,+7.97]**; later PCA twenty-session return was **+6.84**, interval **[-3.60,+16.78]**. Stable-peer versus lower-stability response differences were also unresolved.

**Intuition.** If relative losers reliably caught up, a plot of today's residual against the future relative return would slope downward. The estimated relationships were too uncertain to establish that pattern. A positive mean with an interval spanning zero is worth recording, but it is not a validated winning horizon.

**Limit.** These are overlapping event responses, not the compounded returns of a funded strategy opening new multi-day positions every day. Twenty-session returns consume more time and cannot be compared with daily returns as if capital usage were the same. Initial neutrality can drift over a hold. All horizons used a common complete-outcome date sample and consistent vendor-adjusted price proxies, so these figures need not match the earlier raw-price one-day pilot's sample averages.

**Decision.** Neither a longer hold nor the tested peer-stability split established a simple repair. This does not prove a random walk or long-run price mean reversion; those are different hypotheses. See [the scope explanation](MEAN_REVERSION_SCOPE.md).

**Evidence:** [response notebook](equity_reversal_response.ipynb), [plots, timing, intervals, and interpretation](experiments/equity_reversal_response/README.md).

## 09 — Expand to 200 stocks and test structural generalization

**Question.** Were the peer-structure findings just an artifact of our small hand-picked basket?

**What we did.** Downloaded 200 equity securities plus SPY using a documented current-size rule from published IVV holdings and current Alpaca asset metadata. All original 30 names were retained. The calendar stayed 2016–October 2026: 182 stocks have complete history and 18 start later. A SPY-only earlier-history probe returned no pre-2016 bars from the tested account/feed, so this added breadth rather than years.

For the structural comparison, required 272 complete prior returns and used the same eligible stocks for both 120- and 252-session fits. Scored 6/11/20/40 groups against a common subsequent twenty-session correlation target. There were 121 nonoverlapping target blocks: 86 development and 35 later, with 182–200 eligible stocks per anchor. No new trading strategy was run.

**What we learned.** Repeatable peer relationships extend to the larger basket. The H0 giant component also persists. Later-period results at the matched eleven-group count, with a 252-session history:

| Measurement | H0 / single linkage | Average linkage | Snapshot sectors |
|---|---:|---:|---:|
| Largest group, mean stocks | 185.6 | 77.9 | 41.2 |
| Future within-minus-between correlation | 0.0625 | 0.2098 | 0.1452 |

The eligible basket averaged 198.7 names in this period. At every declared cut and both lookbacks, average linkage had a larger future correlation gap; the paired approximate simultaneous intervals supported that difference in both periods. At matched K=11 it also exceeded the broad sector gap, although partition sizes and which pairs are classified as peers still differ.

**Intuition.** A useful peer definition should put stocks together that continue to resemble one another more than stocks outside the group. Average linkage does that more effectively under this metric. Broad sector labels capture some relationships, while the data-derived grouping preserves additional detail. That is a statement about return organization, not a prediction that yesterday's loser will rebound.

Small named branches remained robust. Under later 252-session H0 fits, AEP/DUK/SO, AMAT/KLAC/LRCX, COP/CVX/EOG/XOM, and MPC/PSX/VLO met the past-only stability diagnostic at all 35 anchors. Yet **486 of 496** stable H0 occurrences also appeared under average linkage, and **436** were stable under both. There are a few H0-only occurrences; no extra usefulness was established for them.

Longer histories increased measured resampling agreement, but did not fix H0 chaining or establish an optimal lookback. The comparison uses different dates and admission rules from the 30-stock study, so it is not a controlled estimate of the effect of adding names alone.

**Decision.** Retain average linkage as the stronger tested structural baseline. Keep labeled branches for interpretation. The larger basket supplies no new evidence of reversal profitability and no reason by itself to add H1 or select more trading thresholds.

**Evidence:** [expanded dataset](../market_data/datasets/equity_daily_expanded_2016_2026-10-27/README.md), [structural notebook](equity_expanded_structure.ipynb), [full findings and independent audit](experiments/equity_expanded_structure/README.md).

## 10 — Rerun PCA and residual reversal on the broader panel; define the regime question

**Date: October 29, 2026. Question.** Does the original strategy behave differently with more stocks? Could a persistence representation help identify when this fixed style performs well?

**What we did.** The user accepted the existing 200-stock panel rather than collecting 300. Reran descriptive PCA and the original SPY-only/three-PC daily strategies, plus declared sector, average-linkage, and ten-PC comparisons. Kept 120 sessions as the primary fit and reported a 252-session sensitivity. Daily admission requires 272 complete prior returns, with the same eligible stocks across broader models/lookbacks. Original thirty-stock controls use identical dates and reproduce their old returns.

**PCA result.** The 2016–2023 descriptive fit includes the 182 names available throughout that reference interval. PC1 captures **41.23%** of standardized variation and correlates **0.9738** with SPY; ten PCs capture **61.27%**, versus **80.43%** on the original thirty. The same small number of directions leaves more of the larger basket's movement unrepresented. This is a reconstruction observation, not a forecast or an optimal factor-count recommendation.

**Trading result.** On the same 708 later execution dates as the original backtest, primary 120-session gross means changed:

| Model | Original 30, bps/day | Expanded panel, bps/day | Expanded approximate pointwise 95% interval |
|---|---:|---:|---:|
| SPY only | -1.291 | +1.143 | [-0.692,+3.395] |
| SPY + 3 residual PCs | -0.646 | +1.343 | [-0.530,+3.452] |

The 252-session three-PC estimate is **+1.560 bps/day**, interval **[-0.244,+3.535]**. Every declared daily mean interval includes zero. Some paired broad-minus-original differences favor the broader construction, but neither a validated standalone edge nor a winning model/lookback is established. Effective gross breadth is about ninety names for later 120-session three-PC positions versus sixteen in the original basket.

**Intuition.** The original small basket's negative result did not carry over unchanged. More positions and different fitted factors produced a different observed portfolio. However, neither the stronger point estimate nor the more diversified weights explain an economic mechanism or repair current-survivor selection. The earlier average-linkage coherence result describes peer organization; it does not make that grouping a proven superior trading signal.

**Timing/sample limit.** The separate 1/5/20-session frozen-sleeve tests still have intervals including zero. Their common later sample has 689 dates, rather than the daily strategy's 708. For primary three-PC positions, full raw daily mean is +1.343; common-date raw mean is +0.905 and adjusted mean +0.903. The nineteen omitted tail dates averaged +17.225 raw bps/day and contribute materially to the primary mean. We reported them, not a rule selected to identify them. Longer frozen holds are also different from asking how twenty successive daily strategy trades perform.

**Persistence representation result.** We checked one historical snapshot: stock points in full residual histories, stock points in three weighted factor loadings, and day points in three factor-score coordinates. Full weighted loading coordinates reproduce the original correlation distances. Truncation changes what variation survives; changing points from stocks to days changes the question. An additional synthetic control shows identical unordered observations can have opposite time-order patterns while their ordinary point-cloud H0 remains unchanged; lag coordinates can distinguish the transitions.

**Decision and proposed next question.** The broader strategy is a more favorable, still unconfirmed gross baseline. The user's regime idea should target **future performance of one fixed daily strategy using only past information**, comparing a simple state model with the same model plus a few declared persistence summaries. Stock factor coefficients describe exposure geometry; lagged factor-score states address temporal dynamics more directly. No persistence-conditioned profitability model or trading gate was fitted in this step.

**Evidence:** [executed notebook and profit plots](equity_expanded_pca_reversal.ipynb), [full results, sample bridge, and audit](experiments/equity_expanded_pca_reversal/README.md), [factor-coordinate and regime proposal](PERSISTENCE_REGIME_IDEAS.md).

## 11 — Test persistence as a predictor of favorable strategy states

**Date: October 29, 2026. Question.** Can a diagram tell us when the existing daily residual-reversal strategy will perform better, beyond ordinary measures of market conditions?

**What we did.** Kept the 200-stock, 120-session SPY-plus-three-PC strategy fixed. Every five sessions, predicted the average gross return of its next twenty daily trades. A positive forecast meant running the original daily strategy over the next five sessions; a nonpositive forecast meant remaining flat. All days, including flat zero-return days, stayed in the performance calendar.

Compared the mean of completed historical target windows, a simple state forecast, and the same simple forecast with three stock-loading or three lagged-state persistence summaries. The simple inputs included volatility, correlation, PC concentration, lag-one dependence, spectral concentration, trailing strategy returns, strategy stock count, and the clouds' scales. The fitted model was a **linear forecast with a fixed coefficient-shrinkage penalty**, often called ridge regression. We did not optimize that penalty or the trading threshold after seeing profit.

**Representation controls.** Fixed a reference cohort of 182 stocks using the first formation's prior history. Stock points used three weighted factor loadings. Lagged-state points used three whitened factor scores from each day and the preceding day, giving 119 transition points. Each cloud was normalized by its own median pair distance. Common shuffling of historical days left the stock-loading diagram unchanged but changed the lagged-state diagram. Uniform return scaling left both unchanged. Reversing time also left both unchanged: the lag cloud retains transition geometry but not the arrow of time. These are measured representation distinctions, not evidence of profitable states.

**What we learned.** There were 379 past-only forecasts, starting April 18, 2019. Later calendar results, before fees:

| Rule | Active days | Mean gross bps/calendar day |
|---|---:|---:|
| Always trade the fixed strategy | 100.0% | 1.343 |
| Simple state forecast gate | 67.2% | 0.933 |
| Simple + stock-loading diagrams | 69.4% | 1.344 |
| Simple + lagged-state diagrams | 58.1% | 0.953 |

The paired later increment over the simple model was **+0.411 bps/day** for stock diagrams, approximate simultaneous interval **[-0.213,+1.035]**, and **+0.020** for lagged-state diagrams, interval **[-0.799,+0.839]**. All incremental intervals included zero in both periods. Stock diagrams achieved almost the always-on point mean with lower observed volatility, but their higher point Sharpe is not a validated superiority claim.

Forecast accuracy was also unconvincing. Later average squared prediction errors were **32.277** for the historical-mean forecast, **33.347** for simple states, **32.812** with stock diagrams, and **34.493** with lagged states. Lower is better. Neither augmentation established improvement over the simple model; both complex variants had worse point error than the historical-mean baseline later.

**Intuition.** A regime model needs to separate periods where this fixed strategy is expected to perform well from periods where it is not. Later, the simple model's positive and nonpositive forecasts corresponded to almost the same realized next20 mean: **1.156 versus 1.113 bps/day**. Stock diagrams widened that descriptive gap slightly; lagged-state diagrams reversed the desired ordering. The representation can respond to different shapes without recognizing a useful return regime.

**Limits and decision.** Training used only target windows completed by each decision, with training-only scaling. Later models learned from earlier completed later-period labels as time passed. Targets overlap, and the current-survivor universe and examined dates remain. Independent reconstruction verified all forecasts, memberships, gates, diagram summaries, and paired intervals. **Do not promote either gate as an established improvement or search more settings simply to rescue this profit curve.** Keep the result as a bounded benchmark; another representation needs a concrete distinction and an appropriate simple comparator.

**Evidence:** [executed regime notebook](equity_persistence_regimes.ipynb), [full findings, calibration, and audit](experiments/equity_persistence_regimes/README.md), [original conceptual proposal](PERSISTENCE_REGIME_IDEAS.md).

## 12 — Preserve more diagram detail with a persistence image

**Date: October 29, 2026. Question.** Did the first regime test throw away useful information by compressing an entire stock diagram into just three numbers?

**What we did.** Reused exactly the same saved stock diagrams and fixed daily portfolio. For H1, placed a smooth Gaussian bump at each diagram point in birth/lifetime coordinates, weighted each bump by lifetime, and integrated them into a **4×4 grid**. Each of the sixteen pixel values becomes one regression input. For H0, all components start at scale zero, so four one-dimensional bins describe their merge distances. The infinite H0 interval is excluded. Together that adds twenty inputs to the same simple state model.

**Intuition.** The diagram is a collection of events: a loop appears at one connection distance and disappears at another. An image describes where those events concentrate. Two diagrams can have the same longest loop and sum of squared lifetimes while those loops start at different scales; the image can distinguish them. The smooth bumps prevent a tiny point movement from abruptly moving all its weight into another pixel. Neither image axis is elapsed time, and longer-lived loops are not established economic signals.

The grid was calibrated once from the first forecast's 104 completed training anchors, without choosing settings against profits. The same expanding completed-label training, fixed ridge penalty, zero forecast threshold, next20 target, and next5 active/flat decisions were retained. We also added an ordinary control with twenty conventional distance/correlation quantiles. No alternate image resolution, bandwidth, or lag-image model was searched.

**What we learned.** On the same 708 later calendar days, all gross/pre-fee:

| Rule | Annualized compounded return | Sharpe versus zero | Active days |
|---|---:|---:|---:|
| Always trade | 3.37% | 0.89 | 100.0% |
| Simple state gate | 2.33% | 0.74 | 67.2% |
| Three stock-diagram summaries | 3.39% | 1.06 | 69.4% |
| Twenty ordinary distance/correlation inputs | 3.75% | 1.10 | 82.1% |
| Persistence image plus H0 bins | 1.19% | 0.43 | 55.9% |

Later forecast MSE rose from **32.812** with three summaries to **38.103** with the image. Lower is better. The image had slightly better earlier point forecast error, so the favorable earlier comparison did not carry into the later period. The image-minus-three-summary later trading mean was **−0.857 bps/calendar day**, approximate simultaneous interval **[−2.451,+0.737]**. All declared simultaneous incremental intervals span zero, and all daily mean intervals span zero. Ordinary20's favorable point ranking is not a validated winner.

The gate's later selection also had the wrong descriptive ordering: the underlying strategy averaged **0.870 bps on days it traded and 1.942 bps on days it skipped**. That explains the missed positive returns in its curve, but those realized group averages were unavailable at decision time and do not identify the cause of the forecast failure.

**What the checks rule out.** All 379 forecasts, exact completed training memberships, every gate return, metrics, and uncertainty bands reconcile independently. All 490 image vectors were independently reconstructed, and numerical integration confirmed the Gaussian calculation. The old baselines match exactly. Only three of 30,270 H1 points fall outside the fixed grid; median retained weighted Gaussian mass is 88.6%, with the remainder including expected tails beyond the image boundaries. This is not evidence of widespread range overflow. It does not prove that this grid or smoothing was the best choice.

**Limit.** We have not identified why the image forecast was worse later. Extra estimation noise, weak economic relevance of these shapes, or an unsuitable representation are possibilities, not measured causes. Overlapping windows and already examined dates remain; more pixels do not create more independent market history. This single negative comparison is not a verdict on every persistence-image application.

**Decision.** Retain this as a negative incremental result. Keep the fixed daily strategy as the benchmark and the gates as unconfirmed variants. Do not enlarge the image or select profitable pixels just to repair the observed curve; a new experiment needs a distinct justified question or new observations.

**Evidence:** [executed image notebook](equity_persistence_images.ipynb), [full intuitive findings and profit plots](experiments/equity_persistence_images/README.md), [frozen specification](experiments/equity_persistence_images/specification.json), [independent audit](experiments/equity_persistence_images/independent_audit.json).

## 13 — Revisit regime research before choosing more diagram features

**Date: October 29, 2026. Question.** Were we using a point object and coordinates suited to regime changes, and what do previous studies suggest? This entry records a focused primary-source review, not new model results.

**What we checked.** The classic four-index crash construction uses **days as points and four simultaneous returns as coordinates**. Correlation-network studies instead use assets as vertices and correlation-derived distances. A cryptocurrency study uses **four consecutive returns of one series** as its coordinates. The accessible Baitinger–Flegel preprint describes **day clouds in 10 or 30 industry-return dimensions**, then compares successive diagrams to construct a turbulence indicator. These are distinct constructions, despite all using persistent homology. Exact source links, method details, and access limits are in the review below.

**Our dimensions.** The image study used **182 stock points with three weighted residual-PCA loading coordinates each**. The earlier lag-state study used **119 adjacent-day pairs with six coordinates**. The image's sixteen pixels were downstream regression inputs, not additional coordinates of the stock cloud. H1 is the type of shape being tracked, not the input coordinate count.

The three retained directions cover a median **27.63% of standardized SPY-residual variance** across 142 later formation anchors. This is a rolling residual-geometry statistic, not the raw descriptive PCA coverage. It makes the truncation substantial; it does not establish that adding dimensions improves prediction.

**Intuition.** Stock-loading geometry asks how exposures are arranged. A return-day cloud asks what combinations of moves occurred. Diagram distance asks how much that arrangement or distribution changed. A model can describe the current shape without measuring its speed of change. Our image test encoded one stock geometry more fully; it did not test every possible market-state object.

SPY removal, residual standardization, factor whitening, and median-distance scaling deliberately suppress some market/amplitude distinctions. These choices may be suitable for isolating shape, while being unsuitable for a stress detector. They are not demonstrated causes of the gate's weak performance, and the simple model already retains several volatility, correlation, concentration, and scale controls. Also, estimated market-neutral holdings can still have performance that depends on market conditions.

**What changes—and what does not.** A separate market-state/change comparison now has a concrete motivation. Prior reported risk/allocation benefits do not show that stress means low expected return for our reversal portfolio. Replacing our squared-lifetime sum by the full landscape L1 norm alone would not change its information: the latter is exactly one quarter of that sum on the same finite diagram. Changing the object or measuring change is more substantive than renaming the existing scalar.

**Recommended next question, not executed.** Start with a small day-return cloud with transparent index-proxy coordinates and a fixed window, compare amplitude-preserving and shape-normalized versions, and measure one declared diagram change. First test a risk target against strong volatility/covariance/change controls; separately test whether it predicts the fixed strategy's mean. Do not assume a stress signal supplies a profitable on/off gate. Four ETF-proxy coordinates and sixty days are a proposed benchmark, not an optimized or validated choice; three additional ETF histories would need checking/collection. No new data or backtest was run for this review.

**Limits.** The papers differ in objectives, horizons, normalization, and evidence. An accessible 2019 preprint partly resolves the turbulence paper's earlier access limitation, without establishing identity with its final journal version. A newer working paper's predictive controls omit lagged volatility, so its stress-forecast claim is not yet a strong-volatility-baseline comparison. Our already examined historical dates remain exploratory regardless of the new representation.

**Evidence:** [primary-source comparison, exact dimensions, deductions, and proposed design](literature/tda_regimes_and_coordinate_design_2026-10-29.md), [earlier broad review](../literature/financial_tda_review_2026-10-12.md), [current executed geometry source](experiments/equity_persistence_regimes.py).

## 14 — Let each day contain the entire stock basket

**Date: October 29, 2026. Question.** Rather than repeat a four-index crash study, does a day cloud using the actual basket's complete returns help describe and predict our strategy's changing conditions?

**What we did.** Used each historical day as one point with **182 stock-return coordinates**, over a fixed prior **120-day window**. This is a 120×182 matrix: days are rows and stocks are columns. The reference names were fixed from initially available history. There is no PCA truncation, changing coordinate count, filled data, or new download. The daily trading portfolio stays unchanged.

Tested raw market-inclusive returns and standardized SPY residuals. For each, tested current H1 summaries and diagram changes over five sessions. A diagram distance measures the minimum cost of moving/matching loop events, including their appearance/disappearance. Those rolling windows share 115 days, so changes can reflect entering/leaving observations as well as broader state changes. We compared against 33 shared ordinary state, volatility, covariance/change, distance, and MST controls; H0 merge distances are already MST information.

**Separate targets.** First forecast the next twenty strategy returns' **RMS**, the square root of average squared returns, on a log scale. Both big gains and losses raise it. Separately forecast their mean and apply the old positive-mean five-session gate. We did not turn the strategy off based on high predicted risk or assume turbulence is unprofitable.

**What we learned.** On the same 138 later complete forecasts, all four additions reduced squared log-RMS point error by **2.2–3.4%**. The raw-change variant gives 0.06686 versus 0.06924 for Controls, paired difference **−0.00238**, simultaneous interval **[−0.00600,+0.00124]**. Earlier effects are much smaller and not uniformly favorable. Every declared simultaneous interval includes zero. These are error reductions, not reduced realized risk or increased profit.

Later mean-return forecasts barely change. Gross/pre-fee gate CAGR/Sharpe:

| Rule | CAGR | Sharpe versus zero |
|---|---:|---:|
| Always trade | 3.37% | 0.89 |
| Matched ordinary controls | 2.44% | 0.79 |
| Add raw current geometry | 1.72% | 0.57 |
| Add raw geometry changes | 1.90% | 0.63 |
| Add residual current geometry | 1.55% | 0.52 |
| Add residual geometry changes | 2.02% | 0.66 |

All four later gate point increments are unfavorable relative to Controls, with simultaneous intervals spanning zero. The old three-summary gate remains a different, frozen feature-set comparison; we have not chosen a winner across experiments by Sharpe.

**Intuition.** A feature can help estimate how large future strategy moves may be without identifying whether their average will be positive. This experiment supplies a weak favorable risk estimate, not a measured profitable regime. We also checked that high dimension did not make every day equally distant: later pair-distance relative spreads are about 0.25 raw and 0.21 residual. Effective covariance ranks are about eleven and twenty-five, respectively; these measure variance concentration, not true economic factor counts.

**Verification and limits.** Independent reconstruction checks all 491 state windows including the initial comparison window, all diagram-change distances via a separate transport linear program, and all 4,548 target/model/date fits with scikit-learn. Labels, chronology, memberships, gate returns, statistics, and uncertainty bands reconcile. The survivor basket, overlapping histories/targets, examined dates, single window/lag, fixed learner, and untested stochastic significance of loops remain. An unordered day cloud still loses within-window order; measuring diagram change does not recover every temporal dependency.

**Decision.** Keep the full-basket construction as a completed benchmark. Do not promote a risk signal or trading gate from these estimates, or search more dimensions merely to obtain a better curve. A subsequent experiment must distinguish risk forecasting from mean prediction and identify what additional temporal or economic distinction it tests. The earlier ETF-proxy reproduction remains unrun, not an outstanding authorized task.

**Evidence:** [executed full-basket notebook](equity_full_basket_states.ipynb), [full findings, plots, and specification](experiments/equity_full_basket_states/README.md), [independent audit](experiments/equity_full_basket_states/independent_audit.json).

## 15 — Replace PCA factors with exploratory factor analysis

**Date: October 29, 2026. Question.** Does explicitly separating shared variation from stock-specific noise produce better common factors and a more convincing reversal signal?

**What we did.** Matched the expanded 200-candidate portfolio with **SPY plus three additional factors**, using 120 prior observations and the same daily admission rule. PCA takes leading directions of standardized SPY-residual returns. EFA estimates three common-factor loadings and a different unique variance for each stock. Neither gives the factors identified economic causes or makes the residual a temporary pricing error by definition.

Converted both sets of loadings to raw-return exposure units. Kept the one-day return signal, cross-sectional WLS, inverse total-return variance weights, minus-W-times-residual holdings, next raw open-to-close execution, and unit gross fixed. EFA uniqueness estimates did not replace portfolio weights, and its posterior scores did not become a new signal. There was no TDA gate, count/rotation search, or new download.

**What we learned.** All 2,446 EFA fits converged, median 10.5 iterations and maximum 77. Later daily results are gross/pre-fee:

| Model | Mean bps/day | Approximate 95% interval | Gross CAGR | Sharpe versus zero |
|---|---:|---:|---:|---:|
| SPY + 3 PCA directions | 1.343 | [−0.764,+3.335] | 3.37% | 0.89 |
| SPY + 3 EFA factors | 1.408 | [−0.703,+3.382] | 3.54% | 0.93 |

The primary paired EFA-minus-PCA mean is **+0.065 bps/day**, approximate 95% interval **[−0.104,+0.263]**. Earlier it is −0.040, interval [−0.126,+0.039]. The slight later point improvement is not an established advantage. New bootstrap draws change interval endpoints; every PCA point return and holding matches the frozen baseline.

**Overall profit view.** The full continuous trading ledger begins February 3, 2017 and ends October 27, 2026. EFA's gross CAGR is **0.66%**, with **17.14%** maximum drawdown and **0.19** Sharpe versus zero; $100,000 becomes about **$106,550**. PCA's full CAGR is **0.68%**. The quoted 3.54% is the stronger 2024-onward subperiod, not the whole run. The [continuous profit/drawdown chart](experiments/equity_efa_overall_profit/README.md) has no reset at the 2024 boundary. With 1× gross exposure the initially balanced portfolio holds approximately $50,000 long and $50,000 short per $100,000 equity; net-dollar/SPY/factor neutrality does not remove all risk. This is a reporting view of the same saved ledger, not a new backtest.

**Factor diagnosis.** Median later overlap between the fitted raw three-factor spaces is **0.970**, on a scale where one means the same span after allowing rotations. This is similarity of estimated spaces, not 97% economic-factor accuracy. Later future mean absolute WLS-residual correlation is **0.20614 PCA versus 0.20646 EFA**. Average stability across diagnostic blocks is **0.8765 versus 0.8802**. Both paired simultaneous intervals span zero; EFA has no consistent structural advantage. Future coefficients are used only in ex-post diagnostic decompositions, never to form trades.

**Direct reversal check.** EFA's later 1/5/20-session frozen-sleeve means are +0.968, +0.236, and −2.946 bps. Every standalone event mean and response-slope interval includes zero. Some twenty-session paired pointwise differences favor EFA, but the declared simultaneous three-horizon intervals include zero; the EFA twenty-session point mean remains negative. The event sample has 689 later dates versus 708 in the daily ledger, with adjusted marks and a common complete twenty-day requirement.

**Intuition.** EFA was a sensible alternative because its covariance model gives each stock its own noise allowance. In this particular fit it usually identifies a closely aligned factor span, with little change in future co-movement left over. Small changes in the residuals can move portfolio returns without establishing that the new residuals reliably reverse. Better factor modeling and positive expected catch-up remain separate claims.

**Verification and limits.** Independent reconstruction checks every WLS portfolio and Gaussian training likelihood, thirteen separate EFA refits, an EM likelihood step, all price ledgers, structural diagnostics, metrics and uncertainty. Original data and frozen PCA results are intact. One count/lookback, Gaussian/diagonal-noise assumptions, a short rolling sample, noisy twenty-day correlations, the survivor basket, and examined history limit generalization. Convergence is not proof of a true model or global optimum.

**Decision.** Keep PCA as the established project baseline and EFA as a completed matched alternative. EFA does not materially alter the finding that reliable short-term residual reversal is unconfirmed. Do not infer a TDA gate or another factor-count/rotation search from its slightly higher later point CAGR.

**Evidence:** [executed EFA/PCA notebook](equity_efa_vs_pca.ipynb), [full findings, profit curves and exact design](experiments/equity_efa_vs_pca/README.md), [independent audit](experiments/equity_efa_vs_pca/independent_audit.json).

## 16 — Check a three-day index sell-off rule and VIX availability

**Date: November 4, 2026. Question.** Does the LinkedIn claim—buy after a volatility-scaled three-day Nasdaq-100 decline and exit on the first up day—have support in our available data? Can Alpaca supply VIX for context?

**What we did.** The post does not disclose its exact parameters, and LinkedIn did not expose a fuller specification. Fixed a transparent approximation before the new backtest: three-day close return at most −1.5 times sqrt(3) times the preceding twenty daily returns' sample volatility; exit on the first later positive close-to-close day. Kept existing SPY data, downloaded QQQ separately over the same 2,720 sessions, and tested four timing conventions. Reported every declared 10/20/60-day, 1/1.5/2-threshold, consecutive/nonconsecutive sensitivity, raw-price control, ordinary-entry first-up exit, fixed-next-day response and shifted-signal comparison. Original factor results are unchanged. All performance is gross/pre-fee.

**Result.** In 2020–October 27, 2026, ideal-close QQQ has 71 completed trades, 83.1% winners, 1.62-session average hold and +0.942% mean trade return, approximate twenty-session-block interval [+0.445%,+1.492%]. SPY has 73, 80.8%, 1.67 sessions and +0.652%, interval [+0.355%,+0.946%]. All eighteen adjusted-price sensitivity variants have positive later ideal-close point means. Full-history QQQ/SPY ideal-close CAGR is 8.85%/4.45%, distinct from later 10.01%/7.11%. QQQ ideal-close has no negative later calendar year, but that property fails under delayed execution.

**Timing and intuition.** The completed closing price determines both the entry condition and first-up exit. Daily bars cannot establish a fill at that same observed price. Entry-only delay retains 78%/64% of QQQ/SPY later mean return, so our approximation does not confirm that most return vanishes before the next open. Delaying both decisions gives +0.404% QQQ and +0.037% SPY per trade, with both intervals spanning zero and losing years appearing. Ordinary entries with the same optimistic first-up exit already win around 73–74% of later trades; a high winner percentage alone is weak evidence. The sell-off-conditioned fixed-next-day means also exceed ordinary-day means, so the observation is broader than a win-rate artifact, while remaining exploratory.

**VIX.** Alpaca's current official announcement explicitly excludes index values from its market-data offering despite VIX-option trading support. Downloaded Cboe's free VIX daily series into a separate context dataset and saved previous-equity-session VIX with past-only realized volatility. Higher-VIX bins show larger unscaled rebound means but contain only ten/eleven later high-VIX trades and confound return magnitude with volatility. No incremental predictive effect or VIX gate is established.

**Capital/benchmark follow-up, November 4.** Each active trade commits the full account; roughly 6.5% active sessions is not a 6.5% capital requirement. On the full 2016–October 2026 calendar, $100,000 becomes $450,937 holding SPY, $159,940 using ideal-close SPY reversal, and $95,939 using causal-open SPY reversal. A descriptive, hindsight-calibrated daily rebalanced 43.20% SPY / 56.80% zero-yield cash portfolio matches the ideal-close strategy's observed daily volatility and earns 6.61% annually versus its 4.45%, with greater drawdown (15.78% versus 12.80%). QQQ's ideal-close 8.85% CAGR compares favorably with a matched passive SPY/cash 6.95%, but its causal 3.32% is below the matched passive 5.70%. These checks do not establish a deployable advantage and introduce no new strategy fit. [Capital explanation, full comparisons and reproduction](experiments/index_selloff_reversal/CAPITAL_COMPARISON.md).

**Limits and decision.** This supports investigating market-wide rebounds; it does not validate the author's exact rule, 1995 training history, costs, preregistration, t statistic, pre-1995 regime claim or forced-selling mechanism. QQQ and SPY are correlated ETF proxies. These dates were already examined and are not a new holdout. Keep this direction distinct from relative-stock residual reversal, and do not select thresholds or retrofit VIX into the frozen factor/TDA studies from this result. A subsequent executable close rule would need a defined pre-close information cutoff and intraday/fill evidence; VIX can be a specified ordinary state control in a separately authorized factor test.

**Evidence:** [full report and timing chart](experiments/index_selloff_reversal/README.md), [frozen approximation](experiments/index_selloff_reversal/specification.json), [results](experiments/index_selloff_reversal/summary.csv), [audit reconstructing all 1,716 primary ledger rows](experiments/index_selloff_reversal/audit.json), [QQQ/VIX dataset and source documentation](../market_data/datasets/mean_reversion_context_2026-11-04/README.md).

## 17 — Compare factor-neutral reversal returns with VIX

**Date: November 4, 2026. Question.** Does VIX explain when the original short-term factor-neutral mean-reversion strategy performs well or poorly? Is the distinction about mean returns, risk, or both?

**What we did.** Kept the frozen 120-session SPY-plus-PCA3 strategy and matched EFA3 version unchanged: existing 2,446 next-open-to-close daily returns, unit gross, flat overnight. Aligned Cboe VIX on the complete equity calendar and used the previous-session close/change for entry-available comparisons. Fixed prior-VIX bins below15/15–20/20–30/at-least30, a high20-minus-low20 mean contrast, and a same-day change diagnostic. Added descriptive HAC regressions and one expanding forecast check against prior S&P return/realized-volatility controls, with 504 initial training days and 21-session refits. No prediction changes holdings or exposure; all returns remain gross/pre-fee.

**What we learned.** Full-sample PCA prior-VIX correlation is −0.020 with signed daily return but +0.322 with its absolute value. Mean returns by VIX bin are +0.17, −0.41, +1.97, and −1.75 bps/day; every full-sample bin interval includes zero. Daily standard deviations rise from 17.85 to 21.68, 25.43, and 52.29 bps. The fixed high20-minus-low20 mean difference is +1.38 bps, interval [−2.62,+6.05]; later it is +3.76, [−1.72,+9.03]. The at-least30 mean changes from −3.46 bps before2024 to +14.09 later, but only fifteen later days qualify and twelve fall in April2025. Its favorable pointwise interval is not evidence from fifteen independent stress episodes.

**Prediction and timing.** Previous-session VIX changes have weak full signed-return correlation (+0.023); same-day changes have a small negative correlation (−0.063) and are unavailable for the morning decision. After controlling for past realized S&P volatility and returns, log prior VIX retains an in-sample association with absolute strategy return, not an established signed-return effect. In 1,942 chronological forecast dates beginning February6,2019, adding both VIX inputs increases signed-return MSE 2.00% and decreases absolute-return MSE 1.80%. Later improvements are only 0.14% and 1.76%. EFA closely agrees. All declared four-comparison simultaneous forecast intervals include zero with both sixty- and twenty-session blocks. A weak mean forecast is not translated into a trading gate.

**Intuition.** Balancing fitted SPY/factor exposures does not make residual portfolio risk constant. VIX distinguishes environments in which this fixed-gross strategy experiences different-sized outcomes more clearly than environments with reliably different profit signs. This is a measured risk association, not identification of forced selling, a tradable VIX exposure, or proof that a volatility-based position-size rule improves outcomes.

**Limits and decision.** These are already examined dates and current-survivor stocks. Regime bins contain clustered days; interval estimates remain approximate, especially in the fifteen-day later stress bin. Forecasts test one fixed linear construction, not every possible VIX feature. Include VIX as an ordinary state control when assessing any future TDA risk feature; do not adopt a VIX gate, choose a new threshold, or claim incremental predictive value from the small favorable risk point estimate. Original strategy profitability conclusions remain unchanged.

**Verification and evidence.** Independent source checks reconstruct every daily feature; statsmodels reproduces all 48 HAC fits and all 23,304 expanding forecast rows. Frozen-return provenance, temporal boundaries, conditional moments, paired losses and input/output hashes pass. [Full report and four figures](experiments/factor_reversal_vix/README.md), [specification](experiments/factor_reversal_vix/specification.json), [conditional results](experiments/factor_reversal_vix/conditional_returns.csv), [forecast comparisons](experiments/factor_reversal_vix/forecast_comparisons.csv), [audit](experiments/factor_reversal_vix/audit.json).

## 18 — Investigate the user-selected VIX20–30 band

**Date: November 4, 2026. Question.** Does the positive mean in the 20–30 VIX group translate into a useful factor-neutral portfolio policy, rather than just a favorable selected-day statistic?

**What we did.** After the user identified this band in entry17, fixed the rule at 20<=previous-session VIX<30, using unchanged PCA/EFA next-open-to-close holdings at unit gross and zero-yield cash otherwise. No boundary search, leverage, original strategy rerun or new data. Compared always-on, outside-band, all original bins, and constant strategy fractions matching average exposure or realized daily volatility. Calibrated fractions are hindsight descriptive controls. Checked annual contributions, contiguous active episodes and known episode origins/ages, single-year omissions, symmetric five-best/five-worst-day deletions, controlled regressions, and one expanding forecast addition of a binary band indicator. This is a post-discovery follow-up on already examined history, not a fresh holdout.

**Result.** On the full February2017–October2026 calendar, PCA gate CAGR/volatility/Sharpe/drawdown is **1.26%/2.04%/0.62/9.33%**, versus always-on **0.68%/3.92%/0.19/16.99%**. It trades625/2,446 days (25.55%); $100,000 becomes $112,894 rather than $106,801. On active days it commits the full 1x-gross account, approximately half long/half short. The +1.97bps active-day mean becomes +0.504bps per whole-calendar day. Later, activity is110/708 days, gate CAGR/Sharpe **1.21%/0.71**, below always-on **3.37%/0.89**, while drawdown falls to2.01% from5.41%. EFA is similar: full1.23% versus0.66%, later1.28% versus3.54%.

**Exposure/risk controls.** A constant52.15% fraction of always-on matches the full gate's realized volatility but earns0.37%, with9.22% drawdown. Thus the favorable full point return is not explained solely by lower measured risk; the gate does not improve drawdown versus this matched control. Later the analogous constant45.47% fraction earns1.54%, exceeding the gate's1.21%, with2.48% versus2.01% drawdown. Average-exposure matching is a different question: concentrating exposure on more volatile days produces more risk than a constant25.55% allocation.

**Concentration.** The active-day mean stays positive under every single-year omission, but deleting2020 reduces gate CAGR to0.27% and selected-day mean to0.51bps. Deleting2022 reverses the gated/always CAGR ranking to2.14% versus2.34%. There are110 contiguous active episodes; two2020 episodes account for56.2% of the net arithmetic sum. These are consecutive separate intraday sleeves, never overnight-held positions. Removing five best full-history days leaves0.79% gate CAGR, but removing five best later days leaves only0.05%. These are ex-post diagnostics with symmetric worst-day checks, not tradable exclusions.

**No stable refinement found or selected.** Full episode-origin means are similar when entering from below20 versus cooling from30plus (+1.91/+2.04bps), but later are +4.74/−2.37, with only four later cooling episodes. Episode-age bins are preserved descriptively without adopting a new age rule. After ordinary controls, the full band coefficient still has an interval including zero. Adding the binary band indicator to the fixed smooth-VIX forecast improves full mean MSE0.13% and worsens later MSE0.25%; every paired forecast interval spans zero. This directly checks the nonlinearity omitted by entry17's smooth feature set.

**Uncertainty and decision.** Full PCA gate-minus-always mean is +0.205bps/calendar day, pointwise block60 interval [−0.925,+1.305]; volatility-matched increment is +0.348, [−0.215,+0.870]. Conditional target mean, calendar mean and original-band simultaneous comparisons remain unresolved. Report favorable full estimates, reduced exposure/risk and positive year-omission signs, alongside temporal concentration and later underperformance. Keep20–30 as a fixed exploratory reference; do not optimize boundaries or promote a validated policy. New observations or suitable independent history are needed for confirmation.

**Evidence.** [Full report, three figures and capital interpretation](experiments/factor_vix_20_30/README.md), [design and post-selection status](experiments/factor_vix_20_30/specification.json), [policy metrics](experiments/factor_vix_20_30/performance.csv), [uncertainty](experiments/factor_vix_20_30/inference.csv), [forecast test](experiments/factor_vix_20_30/forecast_comparison.csv), [independent audit](experiments/factor_vix_20_30/audit.json). The audit reconstructs all48 policy/period results and39,136 curve rows, daily episode states, year deletion diagnostics, twelve HAC models and all7,768 nonlinear forecast rows, with frozen source provenance intact.

## 19 — Revisit historical TDA regimes with VIX in the comparison

**Date: November4,2026. Question.** How have researchers actually used TDA to identify regimes, what do landscapes and other graphs preserve, and how should those ideas apply to this strategy alongside VIX?

**What we reviewed.** Rechecked primary texts for Gidea's correlation networks, Gidea–Katz return-cloud landscapes, Aguilar–Ensor mean landscapes, Baitinger–Flegel turbulence allocation, Ismail and coauthors' warning thresholds, Valdivia's later-crash generalization check, and Souto's volatility forecasts. Read Bubenik's landscape construction/identity, inspected relevant PDF figures, and examined the public PH-RV example at the commit cited by its paper. Distinguish published previews, accessible author preprints, reported successes and our own methodological inferences.

**What it means.** Historical studies supply positive structural/risk/allocation precedents, but a detected market transition does not determine the expected return of our market-neutral reversal sleeve. VIX appears in several of these studies as a benchmark or control. Valdivia documents limits to the classic norm-warning pattern across later crashes. In Souto's public illustrative code, the assigned date precedes some inputs used in the diagram comparison, so it needs correction before reuse; this is not a blanket invalidation or reproduction of the paper's separate empirical work.

**Avoid repeating old features under a new name.** The all-layer L1 landscape of finite bars equals sum(lifetime²)/4, so the corresponding scalar information is already in our tested features. Full landscape curves, norms and distances are distinct; even a norm difference of zero need not imply an unchanged curve. Scalar/image tests and the120day182coordinate raw/residual level/change study are already complete. The latter's favorable2.2–3.4% later risk-error point reductions remain uncertain, and no profitable gate was established. A different representation would need a stated distinction, not just a new label.

**How VIX can fit.** Keep entry-available VIX level/change and the already-selected20–30 indicator as ordinary state inputs. Compare original controls, controls+VIX, and controls+VIX+each original TDA augmentation using identical completed-label fits and separate risk/mean targets. That particular matched comparison remains unexecuted. Do not append unscaled VIX levels to return coordinates or equate VIX-prediction accuracy with reversal profitability. State/Mapper-style graphs can visualize historical configurations, with training-only construction and no profitable-cluster selection from the whole history.

**Concrete artifacts.** Added a synthetic landscape/function/scale illustration and a hypothetical equal-VIX/equal-average-correlation network example, with mathematical checks. Aligned all490 cached TDA anchors to VIX known before first execution, preserving original topology history-end dates, with no missing context and unchanged source hashes. This plot/panel is descriptive and contains no future-return labels. No TDA models, portfolios or gates were rerun.

**Decision and evidence.** Retain regime dependence as a relevant hypothesis; evaluate topology beyond VIX/realized-volatility/correlation controls before new representation or threshold searches. The hypothesis that some same-VIX states have more favorable reversal remains a question. [Full literature synthesis and figures](literature/tda_regimes_vix_2026-11-04/README.md), [proposed comparison, NOT executed](literature/tda_regimes_vix_2026-11-04/proposed_comparison.json), [aligned context panel](literature/tda_regimes_vix_2026-11-04/cached_tda_vix_context.csv), [alignment validation](literature/tda_regimes_vix_2026-11-04/context_validation.json), [source/access provenance](literature/tda_regimes_vix_2026-11-04/review_provenance.json).

## 20 — Test existing TDA forecasts beyond ordinary controls and VIX

**Date: November5,2026. Question.** Does the cached topology predict future strategy risk or mean beyond the original controls plus entry-available VIX level/change and the fixed20–30 indicator?

**What we did.** Reused all490 cached anchors, original379 forecast dates, exact expanding completed-label memberships, fixed ridge penalty and training-only scaling. Compared historical mean, original33 controls, controls+VIX36, and each of four existing TDA additions. Scored identical233 development and138 later complete labels. Targets remain next20-session mean daily gross return and log RMS return, evaluated separately. No topology, holdings or trading rules were recomputed.

**Result: risk.** VIX reduces later squared log-RMS point error by0.95%. Beyond that VIX baseline, raw levels/raw changes/residual levels/residual changes reduce it by2.60%/3.64%/2.48%/2.16%. Raw changes' paired loss difference is−0.002493, simultaneous95% interval[−0.006090,+0.001103]. Its combined improvement over original controls is4.55%. Native RMS MAE is4.844bps for controls,4.790 withVIX,4.720 withrawchanges. Earlier TDA increments beyondVIX range from−0.23% to+0.51%.

**Result: mean.** Later TDA increments beyondVIX range from−1.08% to+0.29%. Historical-mean MSE32.277bps² is below every feature model's34.886–35.367. VIX alone gives a small0.41% later mean-error reduction but worsens earlier error0.93%. All paired intervals, pointwise and simultaneous, include zero for both targets.

**Intuition.** VIX does not absorb the entire favorable later topology risk point estimate. That leaves a possible incremental risk signal, without establishing a dependable one or a mapping from risk to expected profitability. Lower forecast error is not lower realized strategy risk, and high risk can coexist with either favorable or unfavorable returns.

**Limits and decision.** Circular12-anchor blocks account for overlapping outcomes, but138 later forecasts are not138 independent regimes. This is already examined current-survivor history; the20–30 feature was selected after seeing earlier outcomes. Retain every model's result without selecting a point winner or inventing a trading-off rule. No new gate or sizing result follows from this experiment.

**Evidence.** [Report and three figures](experiments/tda_vix_matched/README.md), [pre-run specification](experiments/tda_vix_matched/specification.json), [metrics](experiments/tda_vix_matched/forecast_metrics.csv), [paired uncertainty](experiments/tda_vix_matched/paired_comparisons.csv), [independent audit](experiments/tda_vix_matched/audit.json). The audit refits all5,306 predictions with sklearn (maximum discrepancy2.49e-14), checks VIX alignment against sources, reconstructs completed targets and every metric/interval, reproduces original controls, and verifies protected-source hashes.

## 21 — Map today's residual shocks onto a past stock graph

**Date: November5,2026. Question.** Does local shock topology change the next-session reversal response beyond ordinary peer shocks, sector context and VIX?

**What we did.** Reconstructed the original2,446 SPY+PCA3 strategy dates and469,308 stock events. Built a daily undirected union of each stock's five strongest positively correlated SPY-residual peers, using120 prior sessions. Ran positive/negative H0 filtrations over current standardized residual severity, recording each assigned peak's prominence and pre-merge support. This changes the filtration from correlation distance to the current signal on a labeled graph. Features retain branch identities, with explicit zero caps. A same-histogram chain control distinguishes connected from separated shocks.

**Forecast comparison.** After504 initial training dates, predicted1,942 sessions/377,454 stock events using expanding date-weighted ridge, refitted every20 days. All models allow signal interactions:14 core inputs includingVIX,20 withordinarygraphmeasures,22 withTDA(27/39/43 expanded columns). Primary outcome is next-session raw open-to-close formation-relative stock return divided by prior total sigma; secondary outcome is its absolute magnitude. These differ from entry20's portfolio mean/RMS targets. Later has708 dates, development1,234; stock events travel together in60-date block uncertainty.

**Mean result.** TDA beyond graph+VIX changes MSE by−0.00618% earlier and+0.00427% later, where positive denotes improvement. The later simultaneous interval is[−0.00215%,+0.01068%]. Later MSE0.4860528 remains above a zero forecast's0.4858705. No useful incremental return prediction is established.

**Separate magnitude result.** Ordinary graph features improve MSE by0.7608% earlier and0.1770% later, with simultaneous intervals[+0.2349%,+1.2867%] and[+0.0543%,+0.2997%]. TDA adds+0.0040% earlier and−0.0125% later. The tiny later adverse interval[−0.0246%,−0.0004%] excludes zero within this fixed comparison; it is not a substantial economic effect. Larger predicted individual moves do not identify portfolio loss or require switching off the strategy.

**Intuition.** The representation can trace a residual excursion to connected named stocks: onMarch16,2020, TJX/ROST/LOW share theTJX branch. That is an interpretable distinction, but does not establish a mechanism or profitable reversal. The training-fixed low-prominence group has a negative later raw response slope(−0.0197), while the higher group is nearzero(+0.0017). Those unadjusted group patterns do not become incremental forecasting success, and no stock filter is selected from them.

**Limits and decision.** This tests one five-peer graph and two local summaries, with a fixed learner and horizon, on examined current-survivor history and snapshot sector labels. Retain the construction and the ordinary magnitude finding, without tuning another version to these outcomes or promoting a new policy. Labeled relationship-failure tracking and other applications remain separate proposals, not completed tests. No original holdings, gates, P&L or costs changed.

**Evidence.** [Report and figures](experiments/tda_residual_shock/README.md), [pre-run specification](experiments/tda_residual_shock/specification.json), [metrics](experiments/tda_residual_shock/forecast_metrics.csv), [paired uncertainty](experiments/tda_residual_shock/paired_comparisons.csv), [response plot data](experiments/tda_residual_shock/response_summary.csv), [audit](experiments/tda_residual_shock/audit.json). All daily holdings/returns reconcile; independent PCA/WLS/graphs reconstruct18 dates and36 complete trees. All294 ridge refits and forecasts reconstruct independently(maximum discrepancy4.58e-14), with12 selected weighted sklearn refits, plus every daily loss and declared interval.

## 22 — Track labeled relationship changes and attach actual holdings

**Date: November5,2026. Question.** Do changing persistent stock groups identify risk to the actual frozen portfolio beyond covariance, VIX and ordinary hierarchical clustering?

**What we did.** Used the original2,446 signal dates and actual SPY+PCA3 holdings, retaining ticker identities. Fit120-session SPY-residual correlation hierarchies endingt−1 andt−6 on common admitted stocks. H0/single linkage gives the merge scale for every stock pair. Integrating component co-membership across every distance threshold yields a positive-semidefinite kernel; current holdings times past intraday sigma attach signed exposure to that kernel. Three features describe current exposure, signed exposure change and weighted membership change. A matched average-linkage hierarchy uses the same inputs and feature definitions. The synthetic four-stock relabeling distinguishes identical global geometry with different long/short alignment; ordinary covariance also sees that distinction.

**Forecast comparison.** First504 completed dates train; predict1,942 next-session portfolio outcomes, refitting every20 dates. Twenty ordinary controls include intraday and close-close Ledoit–Wolf portfolio risk, covariance changes, concentration, historical sleeve tails, actual strategy history and entry-available VIX. Compare controls, controls+average, controls+H0 and both trees. Primary target is actual gross squared return, secondary squared loss, each using a positive conditional-moment model scored by QLIKE. Signed mean return is a separate ridge forecast. No portfolio weights or gates change.

**Risk result.** Adding H0 beyond average linkage and controls gives squared-return QLIKE differences−0.002698 earlier and−0.005234 later, simultaneous95% intervals[−0.013610,+0.008213] and[−0.017417,+0.006949]. H0 without average inputs also gives favorable point differences in both periods. For squared losses, the beyond-average difference is+0.038328 earlier and−0.016446 later, both uncertain. Every declared pointwise and simultaneous interval includes zero. QLIKE differences are forecast scores, not percentage portfolio-risk reductions.

**Mean result.** H0 beyond average linkage worsens mean MSE0.410% earlier and0.161% later, with unresolved paired intervals. Simple zero/history-mean benchmarks have lower point errors than all feature models. Risk information does not establish favorable expected-return regimes.

**Intuition.** A portfolio can offset longs and shorts within a persistent group or accumulate a common signed exposure there. A labeled hierarchy preserves this distinction; an unlabeled diagram need not. The construction changes our risk representation, without creating information outside the underlying correlations or proving those relationships have economically failed. Its favorable squared-return estimate remains small relative to uncertainty, and downside behavior differs by era.

**Limits and decision.** This is one fixed120-session/five-shift H0 construction on examined current-survivor history, with existing snapshot sectors and selectedVIX20–30. Sixty-date resampling and three-comparison simultaneous bands do not correct across all earlier research. Retain a possible additional risk representation without choosing a winner, tuning the same history or switching trading off. Mapper and temporal asset-selection ideas remain separate, unrun proposals.

**Evidence.** [Report and four figures](experiments/tda_relationship_exposure/README.md), [pre-run design](experiments/tda_relationship_exposure/specification.json), [metrics](experiments/tda_relationship_exposure/forecast_metrics.csv), [paired intervals](experiments/tda_relationship_exposure/paired_comparisons.csv), [named component exposures](experiments/tda_relationship_exposure/fixed_date_components.csv), [independent audit](experiments/tda_relationship_exposure/audit.json). All2,446 source outcomes reconcile;17 source reconstructions and68 exact kernel integrations pass, including independent Ledoit–Wolf moment calculations and MST minimax checks. All1,176 fits and34,956 daily losses check, with392 sklearn mean fits and24 separate trust-region risk optimizations. Maximum risk stationarity gradient3.10e-12; all original hashes remain intact.

## How to read the recurring measurements

| Term | Plain-language meaning | What it does not establish |
|---|---|---|
| Residual | Movement left after subtracting the selected model's fitted common movement. | Mispricing or a temporary error. |
| Variance explained | How much of the observed movement a representation reconstructs. | Future return predictability. |
| Factor neutrality | Initial holdings balance against chosen estimated exposure columns. | No risk or positive expected return. |
| Average linkage | Merge the groups with the smallest average of every cross-group stock-pair distance. | Equal-sized groups, a globally optimal partition, or a trading rule. |
| Single linkage / our H0 groups | Merge groups through their closest cross-group stock pair. | Every member being close to every other member. |
| Correlation gap / coherence | Average future within-group correlation minus between-group correlation. | Reversal of relative prices or trading profit. |
| ARI / partition stability | Agreement between assignments after changing the historical sample. | Accuracy, a p-value, or a causal explanation. |
| Stable branch | The same named stock set repeatedly appears under the declared past-data perturbations. | An independent discovery each time it reappears or a tradable partition. |
| H0 persistence | The distance thresholds at which components merge. | Calendar-time persistence or statistical significance. |
| Persistence image | Smooth diagram points into a fixed grid so each pixel can be a forecasting input. | Additional observations, economic meaning for each shape, or guaranteed improvement over scalar summaries. |
| Basis point | 0.01 percentage point; 100 bps is 1%. | A rate per day unless the stated measurement is daily. |
| Ridge forecast | A linear prediction with a penalty shrinking large fitted coefficients. | A causal explanation or protection from every form of overfitting. |
| MSE | Average squared difference between forecasts and realized targets; lower is better. | Trading profit or correct identification of an economic regime. |
| RMS return | Square root of average squared returns; both positive and negative moves contribute. | Expected profit or downside-only risk. |
| Effective covariance rank | How spread out the covariance eigenvalues are, using a stated concentration formula. | A discovered latent dimension or exact count of economic factors. |
| EFA unique variance | The factor model's allowance for stock-specific variation after its common factors. | Tradable noise, a temporary deviation, or a reason to replace portfolio weights automatically. |
| Loading-subspace overlap | Agreement between fitted factor spans after ignoring arbitrary signs/rotations. | Economic-factor accuracy or demonstrated forecasting value. |

## Rules that apply to every entry

**Performance is gross/pre-fee.** Do not subtract generic assumed commissions, spreads, slippage, impact, borrow, or financing charges. Original cost-scenario files remain historical provenance only. Signal timing and price conventions still matter when fees are excluded.

**All data and artifacts are saved in this workspace.** Shared prices are under [market_data/](../market_data/README.md), notebooks in this equity folder, and exact outputs/source scripts under `experiments/`. `equity/market_data` and old notebook entry points are aliases, not duplicate datasets. Credentials remain separate from research artifacts and should never enter notes.

**The later dates have already been examined.** “Development,” “evaluation,” and “later” identify saved study splits; changing a method does not make 2024 onward untouched again. Current-size survivor selection and current sector labels also limit historical generalization. These are exploratory findings, with uncertainty and measurement limitations recorded in each experiment.

**Keep explanations tied to measurements.** We have not identified the economic causes of PCA directions, measured crowding, established that medium-frequency stat arb is disappearing, demonstrated long-run price equilibrium, or tested every possible TDA application. Neither a weak strategy nor a good-looking hierarchy supplies those conclusions.

## Keeping this a running document

After each completed equity experiment, append the next numbered, dated entry with **question → what we did → result → intuition → limit → decision → evidence**. Update the short “Where we stand” section when a conclusion changes. Keep old findings attached to their original sample and experiment rather than silently rewriting them.

Maintain [EQUITY_NEXT_STEPS.md](EQUITY_NEXT_STEPS.md) as the current decision page. Exact numerical ledgers, full settings, and audits remain in the experiment folders; this log explains their meaning instead of copying every table. Hypothetical examples must be labeled, and proposed work must be distinguished from completed work.
