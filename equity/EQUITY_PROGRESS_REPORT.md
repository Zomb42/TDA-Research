# Progress report: TDA for equity structure and trading regimes

October 29, 2026. Scope: the equity study. All performance is gross/pre-fee.

**For reconciled numbers and graphs, use [EQUITY_VALIDATION.md](EQUITY_VALIDATION.md).** It aligns the dates, portfolios, forecast targets and units across experiments. Eight audit reruns and additional legacy reconstructions passed; no numerical discrepancy was found in the audited results.

## Research question and completed work

Can topological data analysis (TDA) describe changing stock relationships and help identify conditions favorable to a factor-neutral residual-reversal strategy?

Built a reproducible dataset and evaluation pipeline using 200 stocks plus SPY, covering January 2016–October 2026. Implemented PCA and exploratory factor analysis (EFA), correlation-based peer grouping, residual-reversal backtests, and persistence-based state predictors. Factor estimates use past observations; forecasting models train only on completed outcomes. Results are compared with ordinary clustering, volatility, correlation, covariance-change and strategy-history controls, with paired block-bootstrap uncertainty and independent numerical audits.

## Main findings

- **Shared structure is clear; reversal is not established.** Stocks show common movements and repeatable peer relationships. That does not imply relative underperformers subsequently catch up. The tested 1-, 5- and 20-session residual-reversal responses remain statistically unresolved.
- **EFA does not materially improve the PCA baseline.** In January 2024–October 2026, ungated PCA and EFA strategies have gross annualized compounded returns of 3.37% and 3.54%. Across the full February 2017–October 2026 trading history, they are only **0.68% and 0.66%**; EFA's maximum drawdown is 17.1%. The later paired difference is +0.065 bps/day, with a 95% interval of [−0.104,+0.263]. Neither establishes a positive expected-return edge. These are factor-strategy results, not TDA gains.
- **H0 adds no established advantage over conventional clustering.** H0 tracks when groups connect as the distance threshold grows; here it corresponds to single linkage. Its broad cuts often connect most stocks through chains. Average linkage—merging groups by their average cross-group distance—produced stronger future correlation separation in the tested broad-universe comparisons.
- **Persistence-based trading gates have favorable points but remain unconfirmed.** In the same 2024-onward period, the stock-loading-diagram gate has 3.39% CAGR and 3.21% realized annualized volatility, versus always-on PCA's 3.37% and 3.80%. It trades only 69.4% of days. An ordinary gate also reduces volatility to 3.18%, trading 67.2% of days. Thus lower volatility alone does not establish TDA's incremental value. The stock-diagram-versus-ordinary paired return interval includes zero; the fixed persistence image performs worse in later point results.
- **Full-basket day states give slightly lower point risk-forecast error.** Represented each day by 182 stock returns, with 120 days per cloud. Raw/residual and current/change features reduced later squared log-RMS risk-forecast point error by 2.2–3.4% versus matched controls; all declared simultaneous intervals included zero. These risk forecasts were not used to size or switch off the portfolio. Separate mean-return forecasts and their trading gates did not convincingly improve. Forecast accuracy and realized portfolio risk are different measurements.

## What TDA could contribute

TDA summarizes how a cloud connects and forms holes across distance thresholds. H0 records component merges; H1 records loops in the chosen geometry, not necessarily price cycles. Comparing diagrams over time could describe changes in collective market organization and supply compact state features that ordinary summaries omit. These features might help risk forecasting or strategy conditioning, but usefulness must be established against appropriate simpler controls.

The choice of object is central: stock points describe relationships among stocks; day points describe combinations of market moves; lagged points describe local temporal patterns. Scaling changes the question as well. A persistence diagram transforms existing observations; it does not introduce new data, prove mispricing, or guarantee predictability.

## Current conclusion and limitations

The strongest established result is persistent equity structure, not profitable residual reversal or an incremental TDA trading edge. The study has produced audited benchmarks and clarified which representations preserve useful distinctions. Further work should test a specific missing distinction or frozen hypothesis on new observations, rather than search settings for a better historical curve.

The current-survivor universe, overlapping windows, short time history and already examined evaluation dates limit generalization. Findings are exploratory. Excluding fees simplifies signal research; it does not establish executable profitability.

## Evidence

- [Validated comparison ledger and aligned graphs](EQUITY_VALIDATION.md): one reference for performance periods, risk definitions and audit findings.
- [Running research log, entries 01–15](EQUITY_RESEARCH_LOG.md): full sequence and intuitive interpretation.
- [Expanded PCA/reversal](equity_expanded_pca_reversal.ipynb), [matched EFA/PCA](equity_efa_vs_pca.ipynb): ungated strategy and direct reversal tests.
- [Full continuous profit and drawdown](experiments/equity_efa_overall_profit/README.md): the stronger recent subperiod in its full-history context.
- [Persistence regimes](equity_persistence_regimes.ipynb), [persistence images](equity_persistence_images.ipynb): state forecasts and trading gates.
- [Full-basket day states](equity_full_basket_states.ipynb): separate risk/mean targets and diagram changes.
- [Expanded structural comparison](equity_expanded_structure.ipynb): peer relationships and clustering controls.
