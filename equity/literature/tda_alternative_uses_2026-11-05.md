> **OUTDATED STATUS FOR PROPOSALS 1–2 — marked November 10, 2026.** The local residual-shock and labeled relationship/exposure proposals have been executed; see entries 21–22 of the [consolidated research document](../EQUITY_RESEARCH_LOG.md). Their proposal-stage language below is historical. Conditional state paths, temporal asset selection, Mapper and new allocation rules remain unrun ideas, not agreed tasks. The method rationale is retained.

# Other roles for TDA in residual reversal

**Second subsequent execution, November5:** the user requested more work. The [labeled relationship/exposure test is complete](../experiments/tda_relationship_exposure/README.md): H0 hierarchy features give favorable squared-return risk point estimates in both periods, including beyond average-linkage controls, but every interval includes zero. Downside gains vary by period and mean forecasts worsen slightly. This tests the second proposal with a fixed H0 construction; Mapper, alternative temporal asset selection and new allocation rules remain unrun.

**Subsequent execution, November5:** the user authorized the first current-residual-shock proposal below. Its [fixed merge-tree/conditional-response comparison is complete](../experiments/tda_residual_shock/README.md): no useful incremental mean forecast is established, ordinary graph features modestly help predict absolute relative moves, and the TDA increment is negligible or adverse. No portfolio or trading policy changed. The remaining uses below are proposals; this note preserves the reasoning that preceded the executed test.

November 5, 2026. Research reassessment following the user's request to think beyond global regime-feature additions. **These are proposed uses, not new trading results or a commitment to run all of them.**

The completed studies constrain specific constructions: correlation-derived H0 peers, scalar stock/lag summaries, persistence images and full-basket day-cloud summaries. The [latest matched comparison](../experiments/tda_vix_matched/README.md) adds those cached full-basket summaries to controls plus VIX in an additive ridge forecast. It establishes neither a dependable increment nor the absence of value from every topology-based construction.

Several important choices remain open: which observations become points; whether stock identity, positions and current signal enter the representation; whether the model forecasts a portfolio mean or an individual signal response; and whether topology changes the risk model, grouping or signal construction. Changing these choices is a different hypothesis. Replacing a scalar with a more elaborate scalar is a weaker distinction.

## 1. Map the current residual shock across stock relationships

**Question:** Is today's relative loser an isolated move, part of a coherent peer sell-off, or part of a broad breakdown?

Fit a stock-neighbor graph from return histories ending before today's signal. Keep ticker labels. Put today's standardized WLS residual on each vertex. Starting with the most negative residuals, admit progressively less negative vertices and every backbone edge whose endpoints are present. H0 persistence of this lower-star filtration gives a merge tree of connected negative residual excursions. Repeat with negated residuals for positive excursions.

The filtration variable is **current residual severity**, rather than correlation distance. This is different from our original correlation-H0 clustering. A persistent branch marks a residual trough separated from neighboring troughs by less negative vertices; its lifetime is residual contrast, not time duration or statistical significance. Record component membership and exposure as well as lifetimes. Isolated large residuals and a connected cluster of large residuals can have identical residual histograms.

The financial hypothesis is that the response to a residual move depends on its location and coherence in the stock network. It is open whether isolated or coherent shocks reverse more; an isolated move can also contain stock-specific information. Do not impose a forced-selling explanation from geometry alone.

Test the interaction with the signal directly: predict next-execution relative return from today's signed residual, ordinary context, and residual times local topology. This targets whether topology changes the reversal slope, rather than only adding a market-wide intercept to a 20-session portfolio forecast. Start with the existing next-open-to-close horizon. Compare with neighbor-average residual, sector-relative residual, cross-sectional dispersion, graph assortativity and connected-component sizes. A generic graph statistic is not automatically a TDA result.

Give ordinary controls the same interaction structure and learning capacity, so improvement cannot be attributed solely to a changed learner. Keep all stocks from a date together in chronological splits and date-block uncertainty: stock-event rows do not provide independent market histories. Any event weighting or stock exclusion that becomes a portfolio must reimpose the exposure constraints rather than assume filtered holdings stay neutral.

**Priority:** strongest new mean-return hypothesis because the representation contains the actual trade signal and its location. Existing stock stability/response checks and peer tests are relevant baselines; they did not run this shock-severity filtration or establish its advantage.

## 2. Diagnose which relationships fail and which holdings are exposed

**Question:** Does the fitted neutralization model miss a newly shared movement among names we actually hold?

Track labeled stock relationships over rolling histories. Use persistent components over correlation scales, with explicit membership changes; consider zigzag persistence only if the question requires following homology across changing complexes. Compare against ordinary community matching and covariance-change detectors before adding that complexity. Zigzag persistence provides a mathematical framework for linked, non-nested spaces; it does not by itself turn a changing network into a financial warning. [Carlsson–de Silva, foundations](https://arxiv.org/abs/0812.0197).

Attach today's signed holdings to components and retain which tickers participate. Measure net and gross component exposure, emerging cross-peer connections, and overlap with subsequent residual-risk contributions. A natural primary outcome is future factor-model error or portfolio downside exceedance, with RMS as a separate outcome. The strongest ordinary controls include shrinkage-covariance portfolio variance, sector/cluster exposure, downside co-exceedance and recent factor-fit error. Average correlation alone is insufficient.

**A controlled identity example:** four unit-volatility assets have weights `(0.25, 0.25, -0.25, -0.25)`. Only two disjoint pairs have correlation 0.8. If the pairs are `(1,2)` and `(3,4)`, portfolio variance is 0.45. If the pairs are `(1,3)` and `(2,4)`, it is 0.05. These covariance matrices have the same eigenvalues and differ only by relabeling. A corresponding permutation of the stock coordinates preserves every day-cloud Euclidean distance and hence its persistence diagram, yet fixed-holdings variance changes ninefold. This is a synthetic calculation, not a measured market result.

The example identifies information discarded by an unlabelled global diagram. It does **not** establish TDA superiority: ordinary `w' Sigma w` already distinguishes these cases exactly. A useful topology-based method would have to improve estimation, explain concentrations or forecast relationship failures beyond that control.

**Priority:** strongest structural/risk hypothesis. A better diagnosis can support monitoring without automatically reducing or switching off exposure. Any changed weights require a separate policy test and renewed dollar/factor-neutral constraints.

## 3. Study different paths through the same VIX level

**Question:** At VIX 25, are stocks entering a disruption, recovering from one, or experiencing a different cross-sectional configuration?

A Mapper construction can organize historical multivariate states into overlapping local groups, potentially displaying branches that a single VIX axis combines. Use available VIX level/change alongside residual dispersion, dependence changes, factor-fit error and declared topology inputs. The original algorithm clusters within overlapping ranges of chosen functions and connects groups that share observations; results depend on the functions, cover and clustering choices. [Singh–Mémoli–Carlsson, original Mapper paper](https://publish.illinois.edu/ymb/files/2020/03/Mapper_TopoMtdsAnalHiDimData.pdf).

Mapper overlap edges are **not time transitions**. Add chronological transition counts separately. Fit scaling, cover and clusters using training history, with an explicit later-point assignment and an unknown-state option; do not rebuild a favorable graph from the full outcome history. Historical outcome colors are descriptive. Forecasts require completed labels and subsequent evaluation.

This motivates fixed interactions such as topology times VIX change or topology times signal magnitude, or strongly shrunk local response estimates. The latest additive ridge comparison does not test these interaction effects. However, the November 4 review already proposed Mapper-style displays, so the new work would be the explicit state-assignment and conditional-response design, not a new graph name. Compare against splines/interactions on ordinary controls, Gaussian mixtures, nearest historical states and simple change-point models. A prettier graph does not establish an increment.

**Priority:** useful for understanding and forming specific conditional hypotheses; predictive priority below the first two because there are relatively few independent stress episodes.

## 4. Change asset selection or peer similarity itself

Build a temporal signature for each stock from a declared sequence of past delay-cloud diagrams/landscapes. Use distances between these signatures to propose peers or choose representatives before portfolio construction. This changes the similarity definition from our old correlation-H0 construction.

There is direct financial precedent: Goel, Filipović and Pasricha use diagram/landscape-based, time-aware distances and clustering for sparse index-tracking and mean-variance portfolios. Their construction includes long-only buy-and-hold constraints. It motivates asset selection, but does not validate our daily long-short reversal signal. [Author preprint, §§3–4](https://arxiv.org/html/2401.16920v2).

Two stocks can have similar individual dynamics while moving at different times. Signature similarity is therefore insufficient for a hedge or a stable spread. Compare with return-history correlation, average linkage, dynamic time warping, factor loadings and ordinary portfolio diversification. Verify future co-movement and residual predictability separately. Preserve neutrality if groups or holdings change.

**Priority:** a distinct structural application, with lower priority for rescuing the current signal because prior peer structure already worked better than return prediction.

## 5. Identify residual temporal motifs and forecast tails

Per-stock residual delay clouds could describe recurrent oscillation versus irregular motion; functional landscape or diagram distances could retain distinctions discarded by a few norms. Perea–Harer establish a connection between sliding-window persistence and periodicity for signals, not trading profitability. [Primary paper](https://arxiv.org/abs/1307.6188).

This is partially covered, not wholly new: we tested lagged factor clouds and persistence images. A defensible extension must target an omitted distinction, such as stock-specific dynamics, localized excursion structure or signed downside co-movement. Delay-cloud loops are not automatically mean reversion; ordinary Euclidean constructions can remain invariant to time reversal. Compare with autocorrelation, spectra and ordinary temporal models.

Likewise, future loss probability, downside quantiles and joint loss concentration differ from mean and RMS. These targets could reveal a useful risk application that average-error tests miss. Use proper probability/quantile losses and conventional tail-risk controls; rare events sharply limit inference. A positive result on a new target remains a new claim requiring evaluation, rather than an interpretation of existing forecasts.

## Recommended next decision

Prioritize **the topology of today's residual shock on a past stock graph**, with the **relationship-failure/exposure diagnosis** as a separate risk question. Both connect the representation to something our strategy actually does. First demonstrate the intended distinction on controlled cases and trace a few real events to named stocks. Then declare a small chronological comparison against the specific ordinary alternatives above. VIX stays an entry-available context variable, including its fixed 20–30 indicator where appropriate; it does not replace local structure.

This is a recommendation, not a user-selected next experiment. Existing examined-history limitations and gross/pre-fee reporting remain. No strategy, cached forecast or trading policy changed for this reassessment.
