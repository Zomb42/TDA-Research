# What we learned from the equity correlation and PCA exploration

October 28, 2026. This walkthrough explains the saved [notebook](equity_correlation_pca.ipynb). It describes our computed results, distinguishes mathematical definitions from interpretations, and does not assign untested economic causes to components.

**Latest scope clarification:** [mean-reversion note](MEAN_REVERSION_SCOPE.md) distinguishes short-run residual-return reversal from equilibrium price spreads and multi-year valuation evidence. The subsequent 1/5/20-session experiment did not establish reliable reversal; it does not prove a random walk or long-run reversion. A separate [200-stock dataset](../market_data/datasets/equity_daily_expanded_2016_2026-10-27/README.md) now expands breadth. The numerical PCA walkthrough below remains the original 30-stock descriptive study.

**For the complete equity history, read [EQUITY_RESEARCH_LOG.md](EQUITY_RESEARCH_LOG.md).** This file is the detailed walkthrough of the original descriptive PCA study. It is not the running project record; its historical “next” language describes that first stage. The [current decision](EQUITY_NEXT_STEPS.md) lives separately.

**Subsequent experiment:** the first [daily residual-reversal backtest](experiments/equity_residual_backtest/README.md) has now evaluated 2024 onward. Both models had negative average gross evaluation returns for its specific delayed open-to-close holding rule. The descriptive analysis below still uses only 2016–2023, but later data is no longer untouched holdout data for the project. Statements below about an untested reversal question describe the initial descriptive pass; the linked backtest records the subsequent limited test.

## 1. What went into the analysis

We used 30 selected stocks, with five stocks in each of six manual groups, and 2,011 daily log returns per stock from January 5, 2016 through December 29, 2023. SPY was kept separate as a broad equity benchmark. Data from 2024 onward was excluded from the analysis. This basket was selected in 2026 and contains surviving companies, so excluding later returns does not remove universe-selection bias.

One day's observation is a list of 30 returns: how each stock moved since the previous trading day's adjusted close. We studied how these lists varied and which stocks tended to move together. We did not test whether a return today predicts a return tomorrow.

For PCA, we centered each stock's returns and divided them by that stock's sample standard deviation. A move of one standardized unit therefore means one of that stock's own standard deviations, rather than the same percentage return for every stock. This prevents a high-volatility stock from dominating just because its percentage moves are larger. The mean and scale come from the window being analyzed; the whole-period reference PCA is retrospective.

## 2. The correlation heatmaps: who moves together?

Each square compares two stocks over the same window. Red means that above-average returns for one tend to accompany above-average returns for the other; blue indicates an opposite tendency. White is near zero linear correlation. The diagonal compares each stock with itself, so it is always one. A correlation is not the probability of two stocks rising together.

The stocks were deliberately displayed in manual group order. This helps us see blocks, but the ordering is not an independently discovered clustering result. The numerical contrast supports the grouping: in the last 120 development sessions, within-group correlation averaged **0.487**, while different-group correlation averaged **0.172**.

Across all computed 60-day and 120-day windows, the average within-minus-between gap stayed positive. Its minimum was about **0.083** for 60 days and **0.101** for 120 days. This is a descriptive result for this basket, not a significance test. It does not mean every pair within every group is closer than every pair across groups, or that group membership is stable.

Concrete examples from the final 120-day window: XOM's nearest original-return peers were CVX, COP, and EOG; JPM's were BAC, C, and GS. The groups are imperfect: CAT's nearest peers included DE but also MS and GS. Our coarse industrial label does not force all industrial stocks to behave alike.

## 3. Rolling windows: the relationships change

We recomputed the picture after each day using only the last 60 or 120 trading returns. Think of this as repeatedly taking a recent-history photograph, rather than assuming one photograph represents the entire eight-year period.

The 60-day estimate responds sooner when observations enter or leave the window, but is noisier. The 120-day estimate uses more observations, but blends regimes for longer. A sudden change in an estimate can partly reflect an old extreme day dropping out. Our plots do not establish which window forecasts better. Successive windows overlap heavily and are not independent experiments.

Three illustrative 120-session snapshots make the changing structure tangible:

| Window ending | Average pair correlation | Variance represented by PC1 |
|---|---:|---:|
| 2019-12-31 | 0.389 | 44.3% |
| 2020-03-31 | 0.678 | 69.5% |
| 2023-12-29 | 0.215 | 26.7% |

In the window ending March 2020, movements were much more aligned than in these other two windows. That is what we measured. It does not demonstrate an advance warning, identify the cause of the alignment, or predict when it will happen again. The snapshots cover overlapping portions of different periods, not just the named endpoint day.

## 4. PCA: a compact description of how the basket moved

Imagine writing each day's 30 standardized returns in a row. Some patterns repeat approximately: many stocks move in the same direction, or one set does better while another does worse. PCA chooses weighted combinations of the stocks that summarize the largest amounts of variation in these rows.

PC1 is the weighted combination with the greatest sample variance under PCA's unit-length coefficient constraint. PC2 captures the greatest remaining variance while being perpendicular to PC1; PC3 repeats the process, and so on. If the components were allowed to be redundant, they could all copy the largest pattern. Perpendicular directions prevent that redundancy in this linear representation.

Each component has two different things to distinguish:

- **A direction:** the coefficients describing how stocks combine to form the component. Once fitted, this direction is fixed for that fit.
- **A daily score:** the day's standardized returns projected onto that direction. This changes each day, showing how strongly that day's return pattern lines up with the direction.

The plotted loading table is a third quantity: **correlation between each stock's return and the daily component score**. It is useful for interpretation, but is not the coefficient vector or a ready-to-trade portfolio.

PCA does not receive sector labels or economic explanations. We can inspect its output for similarities to known groups, but it has not discovered the reasons prices moved.

### What our first components actually show

These descriptions concern the single reference fit over 2016–2023. Positive/negative signs use an arbitrary plotting convention; reversing both the direction and its daily scores changes nothing.

| Component | Share of total standardized variance | Pattern supported by our loading table |
|---|---:|---|
| PC1 | 43.6% | Every stock has positive correlation with its score. The score correlates 0.928 with SPY. This supports a broad common equity-movement interpretation. |
| PC2 | 10.9% | Energy stocks have positive correlations around 0.43–0.52; consumer staples have negative correlations around -0.30 to -0.50. Several other groups also participate. It is a contrast between sets of stocks, not a pure energy component. |
| PC3 | 6.3% | Technology stocks have positive correlations, strongest for NVDA (0.58) and AMD (0.53). Health-care and energy stocks have negative correlations. This is another fitted contrast, not proof of a technology-specific economic cause. |
| PC4 | 4.5% | Energy stocks have positive correlations and financial stocks negative correlations; technology also participates positively. The plot only displayed the first three loading columns, but this component is saved in the table. |
| PC5 | 3.8% | Health-care stocks have positive correlations and consumer staples negative correlations. Other stocks also contribute. This is an observed pattern, not an identified economic factor. |

We have not tested explanations such as interest rates, oil prices, inflation, growth/value, investor flows, or crowding. Do not attach those labels to these PCs as findings. An economic interpretation would need independently measured variables and a separate evaluation. Components can also change or rotate when we change dates, windows, scaling, or the stock basket.

### What the percentages mean

The 43.6% for PC1 is its share of **aggregate standardized return variance across the basket**. It is not the percentage of each stock's movement explained, the percentage of future returns predicted, or a percentage profit. The PC1/SPY correlation supports similarity; it does not make PC1 equal to SPY or prove that SPY causes the stock moves.

PC1 and PC2 together represent **54.5%**, the first three **60.8%**, and the first ten **80.4%** of the observed standardized variance. Thus a smaller number of linear combinations provides a useful but incomplete approximation. These numbers do not establish exactly ten economic drivers. All 30 components have positive sample eigenvalues; the remaining components contain variation, and we have not established whether it is noise or useful signal.

PCA scores are uncorrelated with each other in the fitted sample. This is an algebraic property, not proof of statistical independence, different economic causes, or uncorrelated future performance.

### The PC2/PC3 stock map

Each stock is placed by its correlations with PC2 and PC3. Two nearby stocks have similar relationships to those two particular components. The map omits PC1 and PC4–PC30, so nearby dots need not have similar complete return histories. Far-apart dots do not automatically form an attractive hedge or a mean-reverting pair. This is a partial view of the return structure.

## 5. Removing SPY: what remains beyond one market exposure?

For each stock, we separately fitted its historical return to an intercept plus a coefficient times SPY's return, using the same window. The residual is the stock's actual return minus that fitted return.

As a hypothetical arithmetic example, if a fitted stock model expects +1.2% on a particular day and the stock returns +1.5%, its residual is +0.3 percentage points. That residual says it outperformed this fitted benchmark; it does not say it is overpriced or will fall tomorrow. These numbers illustrate subtraction and are not observations from our dataset.

We then correlated the residuals. In the last 120 development sessions, same-group residual correlation averaged **0.359**, versus **0.0015** for different-group pairs. For example, XOM/CVX residual correlation was about **0.804**, and JPM/BAC about **0.502**. These relationships were not fully absorbed by the fitted SPY exposure.

This supports studying peers beyond one broad market benchmark. It does not establish that industry membership caused the remaining correlation, or that residuals are purely company-specific. Other exposures, events, estimation effects, and SPY's composition may matter. Zero average across-group correlation also does not mean every across-group pair has zero correlation; positive and negative relationships can cancel.

**This time-series SPY regression is not the intended trading regression.** Here we fit one stock over many dates for a diagnostic picture. In the [151 strategy](literature/residual_mean_reversion_151_2026-10-28.md), each regression row is a different stock at the same signal time, and holdings are proportional to minus the regression weights times the residuals.

## 6. The trees: a conventional way to organize peers

**Average linkage tells us how to measure the distance between groups of stocks.** Take every pair with one stock in the first group and one in the second, then average those pairwise distances. If the groups contain three and two stocks, that is six distances. Starting with each stock separate, merge the two groups with the smallest average distance, recalculate, and repeat to build the tree. The running log has a [worked numerical example](EQUITY_RESEARCH_LOG.md#what-average-linkage-actually-does).

This is an average of historical-movement distances, not average dollar prices, returns, or portfolio holdings. Single linkage uses the closest cross-group pair instead, so one close connection can join otherwise broad groups. Average linkage considers all cross-group pairs, although it can still produce uneven groups.

Lower merges indicate greater similarity under the chosen correlation distance. The vertical axis is distance, not elapsed time or statistical confidence. Left-to-right order is a display choice. Label colors are the manual groups we supplied, not groups inferred by the tree.

These trees provide a baseline for peer definitions. They force a hierarchy even if the underlying relationships have no clean hierarchy, and we did not test whether their branches stay stable or predict anything. Correlation-based H0 persistence would instead correspond to **single linkage**, so the displayed average-linkage trees are not themselves our TDA result.

## 7. What this changes about the research plan

We now have measured reasons to distinguish broad common movement from more specific peer relationships, and to avoid assuming one fixed relationship structure describes every period. The manual grouping is a useful baseline rather than an arbitrary label with no relation to the data. PCA gives another way to represent shared movements. These are descriptive findings, not established new discoveries about markets.

The next unanswered question is whether relative return deviations have predictive value. For intuition, a stock and its peers can move together most days, then a stock can permanently underperform following new information. That is entirely compatible with high historical return correlation. Neither a bright correlation block nor a clean PCA direction proves that the deviation should reverse.

We have not established mean reversion, profitable implementation, TDA superiority, stable PC identities, advance warnings, economic causes of PCs, or whether medium-frequency stat arb is drying up. Our analysis uses only historical price relationships in this selected basket, so it cannot answer all of those questions.

The next bounded experiment should specify the signal interval, historical peer/exposure construction, weights, executable entry/exit, and evaluation before testing future reversal. Compare manual groups, ordinary clustering, and a trailing PCA basis under the same cross-sectional regression. Only then can we ask whether a topological representation preserves a distinction that improves interpretation or evaluation beyond these baselines. Later data remains available for evaluation rather than further tuning.

## Evidence files

All numerical observations above come from the existing local outputs: [summary](experiments/equity_correlation_pca/summary.json), [rolling metrics](experiments/equity_correlation_pca/rolling_metrics.csv), [component variance shares](experiments/equity_correlation_pca/pca_variance.csv), [stock/component correlations](experiments/equity_correlation_pca/pca_stock_component_correlations.csv), and [nearest peers](experiments/equity_correlation_pca/nearest_peers_2023-12-29.csv). The [analysis guide](experiments/equity_correlation_pca/README.md) contains the figures and reproducibility details. No new performance test was run to write this explanation.
