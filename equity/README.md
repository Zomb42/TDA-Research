# Equity dependence, peers, and residual reversal

**Read [EQUITY_RESEARCH_LOG.md](EQUITY_RESEARCH_LOG.md) first.** It is the single consolidated equity document: all 23 research steps, detailed method specifications, reconciled findings, the single/average/centroid explanation, and the November 10 data refresh. The question behind each experiment, what we measured, what the result means, and the evidence are together there.

**Latest data:** the frozen 200-stock universe plus SPY now extends through **November 9, 2026**, in a separate [fully audited vintage](../market_data/datasets/equity_daily_expanded_2016_2026-11-09/README.md). The [recent descriptive comparison](experiments/equity_recent_refresh_2026_11_10/README.md) includes centroid linkage and the user's deleveraging hypothesis. Existing trading/forecast results below still use the October 27 vintage and end dates.

**For performance numbers and graphs, use [EQUITY_VALIDATION.md](EQUITY_VALIDATION.md).** It reconciles the full and later periods, ordinary and TDA gates, realized volatility and risk-forecast error, with common-calendar plots and audit evidence.

Current position: repeatable peers exist; the expanded daily strategy has positive later gross estimates but its mean intervals include zero; average linkage remains the stronger tested structural baseline than fixed-K H0 partitions. Scalar/image and full-basket state tests establish no incremental gate improvement. Matched EFA gives only a small uncertain later return increment over PCA, without an established structural advantage. Performance reporting is **gross/pre-fee only**. The survivor universe and already examined dates make the follow-ups exploratory.

| Read when you want… | Document |
|---|---|
| The full research story and intuitive explanations | **[Equity research log](EQUITY_RESEARCH_LOG.md)** |
| Consistent performance/risk comparisons and validation evidence | **[Validated comparison ledger](EQUITY_VALIDATION.md)** |
| The earlier October 29 progress snapshot, now superseded | [OUTDATED summary](EQUITY_PROGRESS_REPORT.md); use the consolidated document for current findings |
| How the frozen factor-neutral strategy's returns and risk compare with VIX | [Factor/VIX comparison and forecast check](experiments/factor_reversal_vix/README.md) |
| Whether trading only at prior VIX20–30 improves that strategy | [Fixed-band policy, capital, concentration and nonlinear check](experiments/factor_vix_20_30/README.md) |
| How historical studies used landscapes/networks for regimes and where VIX fits | [Literature review and illustrations; OUTDATED proposal status](literature/tda_regimes_vix_2026-11-04/README.md) |
| Whether existing TDA adds mean/risk forecasts beyond ordinary controls and VIX | [Executed matched comparison and independent audit](experiments/tda_vix_matched/README.md) |
| Original rationale for alternative TDA roles | [Proposal note; OUTDATED status for its first two tests](literature/tda_alternative_uses_2026-11-05.md); completed results are linked below |
| Whether today's local residual-shock topology improves next-session stock forecasts | [Executed shock merge-tree comparison and audit](experiments/tda_residual_shock/README.md) |
| Whether changing labeled stock relationships identify risk in actual portfolio holdings | [Executed hierarchy-exposure comparison against covariance and average linkage](experiments/tda_relationship_exposure/README.md) |
| The current decision and open choices | [Current next steps](EQUITY_NEXT_STEPS.md) |
| The original correlation/PCA explanation in more detail | [PCA intuition; OUTDATED project status, retained explanations](EQUITY_INTUITION.md) |
| An actual Microsoft factor equation, coefficients and worked interpretation | [Microsoft PCA example](MSFT_PCA_EXAMPLE.md) |
| The distinction between different mean-reversion claims | [Mean-reversion scope](MEAN_REVERSION_SCOPE.md) |
| Original factor-coordinate and profitability-regime proposal | [Persistence/regime ideas; OUTDATED proposal status](PERSISTENCE_REGIME_IDEAS.md) |
| Exact dimensions used in prior regime papers, compared with ours | [Coordinate-design literature review; OUTDATED proposal status](literature/tda_regimes_and_coordinate_design_2026-10-29.md) |
| Exact trading equations and source reference | [Verified strategy math](literature/residual_mean_reversion_151_2026-10-28.md) |
| Context across equity, BTC, and liquidity | [Project starting point](../START_HERE.md) |

## Executed notebooks

| Research step | Notebook |
|---|---|
| Initial dependence and factor exploration | [Correlation/PCA](equity_correlation_pca.ipynb) |
| Frozen residual-reversal baseline and diagnostics | [Gross backtest](equity_residual_backtest.ipynb) |
| Matched-exposure comparison of manual, average, H0, and PCA peers | [H0 pilot](equity_h0_peers.ipynb) |
| All cuts, perturbations, and local-branch recovery on 30 stocks | [Whole-hierarchy robustness](equity_h0_scale_robustness.ipynb) |
| Direct 1/5/20-session catch-up and stability tests | [Residual responses](equity_reversal_response.ipynb) |
| Peer-structure generalization to 182–200 eligible stocks | [Expanded structural test](equity_expanded_structure.ipynb) |
| Broader PCA/reversal rerun, profit plots, original controls, and representation illustration | [Expanded PCA/reversal](equity_expanded_pca_reversal.ipynb) |
| Past-only state forecasts, stock/lag diagram features, and fixed active/flat trading gates | [Persistence regimes](equity_persistence_regimes.ipynb) |
| Four-by-four H1 image and H0 bins versus scalar summaries and ordinary distance/correlation controls | [Persistence images](equity_persistence_images.ipynb) |
| Full 182-stock day vectors, raw/residual diagram levels/changes, separate risk and mean targets | [Full-basket states](equity_full_basket_states.ipynb) |
| SPY plus three EFA versus PCA factors with matched reversal, future residual correlations, and stability | [EFA/PCA](equity_efa_vs_pca.ipynb) |

Each experiment has an adjacent README, specification, result tables, plots, source, and audit under `experiments/`. The running log links the relevant evidence at each step.

## Data and files

**Current data:** the [refreshed 200-stock panel plus SPY](../market_data/datasets/equity_daily_expanded_2016_2026-11-09/README.md) runs through November 9. **Archived experiment inputs:** the [original 30-stock panel](../market_data/datasets/equity_daily_30_2016_2026-10-27/README.md) and [older expanded panel](../market_data/datasets/equity_daily_expanded_2016_2026-10-27/README.md) end October 27. Keep those exact vintages for their original structural, trading and forecasting results. Older data does not make a dated experiment invalid; the November refresh is a separate descriptive extension.

`market_data` in this folder is an alias to the shared data directory, not another copy of prices or credentials. Old project-root notebook/script/result paths are compatibility aliases. Select **TDA (conda)** for the notebook kernel; reproduction commands live in the experiment READMEs.

After a completed equity experiment, append an entry to the research log and update its current summary. Keep this page as navigation and `EQUITY_NEXT_STEPS.md` as the current decision, rather than adding another historical status paragraph to each file.
