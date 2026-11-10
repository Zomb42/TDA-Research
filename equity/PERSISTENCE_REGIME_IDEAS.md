> **OUTDATED PROPOSAL STATUS — marked November 10, 2026.** The scalar-regime, persistence-image and full-basket experiments discussed as proposals here have been completed. Their outcomes are in entries 11–15 and 20 of the [consolidated research document](EQUITY_RESEARCH_LOG.md). This note retains the coordinate explanations and original reasoning; its proposals are not a pending work queue.

# Persistence diagrams, factor exposures, and strategy regimes

October 29, 2026. This records the user's proposal to use factor coefficients as coordinates and investigate when residual reversal is profitable. **The first proposed regime-forecast experiment has now been executed:** [notebook](equity_persistence_regimes.ipynb), [results](experiments/equity_persistence_regimes/README.md). Stock-loading features have a modest favorable later point estimate versus the simple gate; neither stock nor lagged-state persistence establishes an incremental benefit. The conceptual discussion and design questions below preserve the proposal stage; exact executed choices are in the linked specification.

**The user-authorized persistence-image follow-up is also complete:** [image notebook](equity_persistence_images.ipynb), [findings](experiments/equity_persistence_images/README.md). A fixed 4×4 H1 image plus four H0 bins preserves birth/distribution detail missed by the scalar summaries, but increased later forecast error and reduced gross point performance. No incremental benefit is established. See running-log entry 12 for the intuitive explanation; do not treat a richer diagram representation as demonstrated economic information.

**October 29 literature reassessment:** [exact point objects, dimensions, and proposed next design](literature/tda_regimes_and_coordinate_design_2026-10-29.md). Prior studies motivate day-return clouds and changes between diagrams as a distinct next question. Our image used stock points in three dimensions; the earlier lag cloud used day pairs in six. The new review is not another backtest or a reversal of the completed results. Running-log entry 13 explains the distinction intuitively.

**The user's full-basket day-cloud follow-up is now executed:** [notebook](equity_full_basket_states.ipynb), [findings](experiments/equity_full_basket_states/README.md). Each point is one day with 182 stock-return coordinates over 120 prior days; raw/residual and level/change variants are compared. Later squared log-RMS error improves 2.2–3.4% in point estimates, with all simultaneous intervals spanning zero. Mean forecasts barely improve and all new later gates trail matched controls. See running-log entry 14. The earlier four-ETF proposal was not run.

## 1. Did the diagrams mostly show correlation we already knew about?

**Yes, for the original construction.** We put one stock at each point, using standardized trailing SPY-residual returns as coordinates. Distances between those points are determined completely by their sample correlations. H0 then summarizes the distances at which connected components merge; the labeled construction is single linkage.

The useful measured step was checking whether the groups survived historical perturbations and retained future co-movement. We did not discover an independent data source or a reason relative returns should reverse. A good diagram is not an alpha signal by itself.

Also, the bare H0 diagram retains less than the labeled hierarchy: it records merge scales without telling us which stocks were joined. Different labeled markets can share a diagram. H1 from the same stock-correlation distances can summarize loops in that distance geometry, but cannot recover joint-return information already discarded when we reduced the sample to correlations.

That does not make the summaries useless. A compact transformation can help a forecasting model generalize. It must demonstrate an incremental benefit against simpler summaries of the same inputs, rather than claim new information by definition.

## 2. “Factor weights” can mean two different things

| Point represents… | Coordinates might be… | Question it addresses |
|---|---|---|
| **A stock** | Its fitted exposures to factor 1, factor 2, factor 3 | Which stocks have similar common-return sensitivities? How separated or concentrated are those exposure profiles? |
| **A historical day** | Factor 1's return that day, factor 2's return, factor 3's return | What combinations of common market moves has the market visited? |
| **A historical transition** | Today's factor returns together with the preceding day's factor returns | What local patterns of continuation, alternation, or recurrence occurred? |

A stock's exposure coefficient is relatively fixed within a fitted model. A factor's daily score changes each day. They are different objects, even if both come from PCA. We need to choose the point object before interpreting a diagram.

### Stocks as points: the user's coefficient idea

This is a sensible candidate representation. Imagine each stock at a point with three coordinates describing its sensitivity to three common patterns. Nearby points have similar sensitivities. A diagram can summarize how those profiles spread out or form groups across distance scales.

But **plain PCA eigenvector entries are not automatically suitable coordinates**. For a standardized-return correlation matrix `C = V Lambda V'`, use `L = V sqrt(Lambda)` when the intention is to represent fitted correlations. Every component's coordinate is weighted by how much variance it carries.

- **All components of L reproduce the original correlation distances exactly.** The coordinates have changed, but the geometry has not. A different diagram is not available merely by rotating the same complete information.
- **The first three columns of L give a different, truncated geometry.** They retain the dominant fitted patterns while discarding other variation. This may help or hurt. It is a filtering hypothesis, not proof of nonlinear information or better return prediction.
- **All unweighted eigenvector rows are equally distant.** Using that full matrix directly destroys the intended similarity information.

If the intended coordinates are raw-return betas to external economic factors, scale them deliberately. A coefficient of one on a very volatile factor represents a different typical return contribution from a coefficient of one on a quiet factor. A natural distance is the historical variance of the **difference in modeled common returns**, using the factor covariance matrix. This can retain volatility information the standardized correlation representation removed; it still does not create new observations.

For reference, with stock exposure vectors `beta_i` and factor covariance `Sigma_F`, that squared distance is `(beta_i-beta_j)' Sigma_F (beta_i-beta_j)`. In PCA coordinates this explains the eigenvalue weighting. Portfolio exposure constraints are a separate use: rescaling a whole factor column preserves the constraint span, but changes unadjusted Euclidean distances if the matrix is used as a point cloud.

### Days as points: a more direct market-state object

Here one point might be `(factor1 return, factor2 return, factor3 return)` for one historical day. A rolling cloud summarizes what joint common moves occurred during that period. This uses observations of the joint distribution, rather than only a stock-correlation matrix. Its geometry need not be fixed by the ordinary covariance summary.

This is closer to a market-state description. However, an unordered cloud does not preserve the sequence of days. The same set of returns can be arranged into alternating moves or long runs without changing its ordinary point-cloud diagram. If the hypothesis involves **reversal dynamics**, add a declared lag: for example, concatenate each day's three factor scores with the preceding day's three scores. Then a point represents a transition. This still needs autocorrelation and other conventional temporal summaries as comparators.

PCA signs and rotations do not change Euclidean distances when applied consistently within a cloud. Aligning bases becomes necessary when comparing individual coefficients or combining coordinates across separately fitted windows; it is not a prerequisite for comparing diagrams that already ignore a whole-cloud orthogonal rotation. Changing the retained factor subspace or relative axis scaling can change geometry and must be measured.

## 3. What we actually illustrated

The [executed PCA/reversal notebook](equity_expanded_pca_reversal.ipynb) includes a deliberately **descriptive** snapshot at formation December 29, 2023, using the preceding 252 sessions:

1. **198 stock points:** full standardized SPY-residual return histories.
2. **The same 198 stock points:** three eigenvalue-weighted PCA loading coordinates.
3. **252 day points:** the first three residual-factor scores on each historical day.

The full loading-coordinate identity is checked numerically before truncation. H0 and H1 diagrams are saved for these three objects. Each is normalized by its own median pair distance for illustration, with the original scales retained. [Snapshot results](experiments/equity_expanded_pca_reversal/representation_snapshot_summary.csv), [figure](experiments/equity_expanded_pca_reversal/06_representation_diagrams.png).

The diagrams differ after truncating or changing the point object. That establishes a change in representation, **not** a favorable regime, statistical significance, or an economic interpretation for a loop. The day-cloud point count differs from the stock-cloud count; raw bar counts and longest lifetimes are not a fair predictive ranking. The state illustration has no delay coordinates yet and does not claim to recover time ordering.

## 4. What would a profitability regime mean?

The useful target is **future performance of a fixed strategy conditional on information available now**. A label such as “crisis,” a cluster in feature space, or a year that happened to make money is not enough.

For a concrete next design, retain the original **120-session SPY-plus-three-PC daily strategy** as the primary target, rather than choosing whichever model in the new table has the highest realized return. Ask whether today's state predicts the strategy's average gross daily return over the next twenty sessions.

This target follows the strategy as it **refits and trades daily**. It is not the separate experiment that holds today's initial stock positions for twenty sessions. Those measure different behavior.

Only labels whose full twenty-session outcome has already occurred can be used to train a forecast at the current date. Feature normalization, any grouping of states, regularization, and thresholds must also be fitted using past training observations. Clustering the full history and then naming its profitable clusters would leak future information into the regime description.

The motivation is plausible: the same recent relative move could be temporary in one state and persistent in another. Whether our proposed geometry identifies that distinction is **unmeasured**. We have not identified economic causes for profitable stretches.

## 5. A bounded comparison worth specifying next

**My recommended next hypothesis is a state/transition representation, with the stock-loading representation retained as a controlled alternative.** It changes the question from “which stocks form peers?” to “what kinds of joint factor moves have recently occurred, and do they condition this fixed strategy's later return?”

Start with a small forecast comparison:

| Model | Inputs | What it tests |
|---|---|---|
| Always-on strategy | No timing signal | Existing baseline performance |
| Simple state forecast | Prior market volatility, average residual correlation, leading-PC variance share, a declared lag-one dependence statistic, trailing realized strategy return | Whether ordinary state variables help |
| Same forecast plus a few diagram summaries | Identical simple inputs plus a small, fixed H0/H1 summary set from the chosen cloud | Whether the diagram adds conditional predictive value |

Use a low-capacity regularized forecast first. A continuous estimate of expected strategy return can be more informative than forcing arbitrary discrete regimes. If a trading gate is evaluated, fix its rule before evaluation—for example, trade at unit gross when the forecast is positive and otherwise remain flat. Report returns on the **entire calendar**, including flat days, so apparent gains do not come from reporting only selected active dates.

Before that experiment runs, fix these remaining choices in its own specification:

- **Point object and coordinates:** start with a rolling cloud of three factor-score vectors and one lag; choose its fit length and scaling. Treat stock-loading clouds as a separate representation check, not extra coordinates blindly concatenated with their source returns.
- **A few summaries:** for example, a declared H0 death quantile and a declared H1 lifetime norm, or a fixed persistence-landscape representation. Define treatment of the infinite H0 interval and the scale denominator. Do not search many diagram statistics for the winning one.
- **Membership and point count:** use a declared past-formed fixed reference subset or an explicit matched-count construction. Otherwise IPO admissions and different cloud lengths can move diagram summaries mechanically. The 200-stock strategy can retain its own past-only admission rule; the state representation need not pretend unavailable histories exist.
- **Time-order controls:** create histories with the same unordered observations in different orders. The ordinary day cloud should be invariant; the chosen lag construction should respond to altered transitions. Compare with lag-one dependence and other simple explanations.
- **Scale controls:** rescale or volatility-match synthetic observations to determine whether a diagram feature mostly measures dispersion. A large lifetime is not automatically a new state variable independent of volatility.
- **Chronological evaluation:** expanding or rolling past-only training; omit incomplete labels; purge training/validation boundaries by the target horizon; account for overlapping targets and persistent state features in uncertainty estimates. Restrict tuning to prior training periods.
- **Success criterion:** incremental future forecast quality and a stable gross strategy comparison against the simple state model, not a visually attractive diagram or a hand-picked profitable state. Report the entire declared comparison, including no improvement.

The 2024–2026 period has already been examined, and the stock universe is selected from current survivors. A new walk-forward exercise can be causally implemented but remains exploratory; it does not become a fresh temporal holdout.

## 6. Research context

[Gidea and Katz](https://arxiv.org/abs/1703.04385) studied rolling clouds derived from several equity-index return series and persistence landscapes around historical crashes. That is relevant precedent for time-dependent market-state objects, not evidence that our residual strategy has a profitable diagram-conditioned regime.

[Bubenik's persistence-landscape paper](https://www.jmlr.org/papers/v16/bubenik15a.html) provides a vector-space summary suitable for statistical learning. It motivates a way to encode diagrams for a model; financial usefulness still needs our task-specific comparison.

The earlier [past-fit state features](experiments/equity_expanded_pca_reversal/past_state_features.csv) remain an initial ledger from the PCA/reversal step. The executed regime study saves its own [features and targets](experiments/equity_persistence_regimes/state_features_and_targets.csv), exact training memberships, causal predictions, and active/flat daily returns. No profitable diagram-conditioned regime is established by that first comparison.
