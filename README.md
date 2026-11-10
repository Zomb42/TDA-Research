# Financial TDA research

**Python environment:** `conda activate tda`; select the `tda` kernel for notebooks. For commands without activation, use `conda run --no-capture-output -n tda python ...`.

**GitHub checkout:** source, notebooks, figures, and research reports are versioned; bulk histories and large generated artifacts stay local. See [repository/data setup and cleanup](REPOSITORY_CLEANUP.md) and the [local-data inventory](LOCAL_DATA_MANIFEST.json). Before pushing, run `python3 scripts/check_git_size.py` after staging your changes.

**Start with [START_HERE.md](START_HERE.md).** It is the authoritative project context, with updates through November 10, 2026. Current performance reporting is **gross/pre-fee only**, per the user's instruction.

**For equities, start with the [consolidated methods and findings](equity/EQUITY_RESEARCH_LOG.md).** It contains all 23 research steps, detailed specifications, reconciled findings and the data refresh through November 9; [current next steps](equity/EQUITY_NEXT_STEPS.md) contains the present decision. Superseded summaries and proposal statuses carry an **OUTDATED** notice with a link to their replacement. Dated results remain available for reproduction.

**For BTC, start with its [running research log](btc/BTC_RESEARCH_LOG.md).** The independent BTC track now has audited price/depth histories, Kalshi perp data, [executed descriptive features](btc/experiments/initial_features/README.md), and a [real liquidity-grid pilot](liquidity/experiments/btc_liquidity_features/README.md). [Data sources](btc/DATA_SOURCES.md) distinguish historical depth bands, candle history and live L2 capture.

The three studies now have separate folders: [equity](equity/README.md), [BTC](btc/README.md), and [liquidity](liquidity/README.md). Shared datasets, reviews, tutorials, and runtime assets remain at project root. See [the folder map](FOLDER_LAYOUT.md) for compatibility aliases and preserved paths.

The agreed initial approach is three small studies using different TDA representations:

1. **Equity peer structure and relative-return mean reversion:** use TDA to investigate peer relationships, then test deviations from weighted peer returns. Options are a possible later extension.
2. **BTC feature engineering:** delay geometry and interpretable persistence features.
3. **Liquidity organization:** cubical persistence and merge trees on price-by-time depth.

The goal is to learn what topology measures and when it helps. No main application, venue, or prediction target has been selected.

| Read when needed | Reference |
|---|---|
| Complete equity story with intuitive explanations | **[Equity research log](equity/EQUITY_RESEARCH_LOG.md)** |
| Completed persistence regime forecasts and trading gates | [Executed notebook](equity/equity_persistence_regimes.ipynb), [findings](equity/experiments/equity_persistence_regimes/README.md) |
| Broader PCA/reversal rerun and factor-coordinate/regime ideas | [Executed notebook](equity/equity_expanded_pca_reversal.ipynb), [regime proposal](equity/PERSISTENCE_REGIME_IDEAS.md) |
| Latest: does peer structure generalize to 200 stocks? | [Executed notebook](equity/equity_expanded_structure.ipynb), [findings](equity/experiments/equity_expanded_structure/README.md) |
| Latest expanded equity collection and mean-reversion scope | [200-stock dataset](market_data/datasets/equity_daily_expanded_2016_2026-10-27/README.md), [conceptual distinction](equity/MEAN_REVERSION_SCOPE.md) |
| Latest: do residual moves reverse at 1/5/20 sessions, and does peer stability help? | [Executed notebook](equity/equity_reversal_response.ipynb), [findings](equity/experiments/equity_reversal_response/README.md) |
| Current plan, decisions, data status, next steps | [START_HERE.md](START_HERE.md) |
| Short standalone summary of previous research findings | [PRIOR_RESEARCH.md](PRIOR_RESEARCH.md) |
| How features become insights; overview of previous TDA applications | [Review §§2–3](literature/financial_tda_review_2026-10-12.md#prior-work-in-context-what-has-tda-been-used-to-learn) |
| Paper-by-paper findings and limitations | [Financial TDA evidence review](literature/financial_tda_review_2026-10-12.md) |
| Merge-tree usefulness, cubical examples, weighted regression | [Technical discussion](literature/merge_trees_and_return_pilots_2026-10-12.md) |
| Tested Alpaca endpoints and reproduction | [Market-data access](market_data/README.md) |
| Notebooks, packages, TTK/ParaView setup | [Tutorial guide](TUTORIAL_GUIDE.md) |
| Executed equity correlation/PCA exploration and figures | [Notebook](equity/equity_correlation_pca.ipynb), [findings](equity/experiments/equity_correlation_pca/README.md) |
| Detailed explanation of the original correlation/PCA study | [PCA walkthrough](equity/EQUITY_INTUITION.md) |
| Intended 151 Trading Strategies residual mean reversion | [Verified strategy specification](equity/literature/residual_mean_reversion_151_2026-10-28.md) |
| First frozen daily residual-reversal backtest | [Executed notebook](equity/equity_residual_backtest.ipynb), [results and limitations](equity/experiments/equity_residual_backtest/README.md) |
| Profit graph, regimes, timing attribution, and PC-count sensitivity | [Follow-up diagnostics](equity/experiments/equity_residual_diagnostics/README.md) |
| Current equity decision, open choices, and pre-fee reporting convention | [Current next steps](equity/EQUITY_NEXT_STEPS.md) |
| Executed labeled H0 pilot and coordinate-choice explanation | [Notebook](equity/equity_h0_peers.ipynb), [findings](equity/experiments/equity_h0_peers/README.md) |
| Whole-hierarchy scale and branch-robustness study | [Notebook](equity/equity_h0_scale_robustness.ipynb), [findings](equity/experiments/equity_h0_scale_robustness/README.md) |

Existing synthetic examples: [depth organization](liquidity/experiments/depth_topology_demo.png) and [matched moments, different geometry](literature/matched_moments_demo.png). Both have adjacent reproducible Python scripts and JSON results; neither demonstrates a financial forecasting advantage.
