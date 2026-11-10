> **OUTDATED PROPOSAL STATUS — marked November 10, 2026.** This October 29 review preceded the completed full-basket and matched VIX/TDA tests. Its next-design and unexecuted-comparison language is historical. The four-ETF suggestion was not selected. See entries 14 and 20 of the [consolidated research document](../EQUITY_RESEARCH_LOG.md) for executed choices and results. The literature and coordinate explanations are retained.

# TDA regimes: what the points and dimensions should represent

**November4 follow-up:** the [updated regime/VIX review](tda_regimes_vix_2026-11-04/README.md) incorporates the completed full-basket study, recent VIX results, landscape equivalences, additional source checks, and an unexecuted comparison using cached TDA after adding VIX controls. The original review-stage proposal below is preserved as historical context.

Focused review, October 29, 2026. This is a method comparison and proposed next question, **not a new backtest**. It supplements the [earlier literature review](../../literature/financial_tda_review_2026-10-12.md) and interprets the completed [scalar regime](../experiments/equity_persistence_regimes/README.md) and [image](../experiments/equity_persistence_images/README.md) experiments.

**Subsequent execution:** the user chose days with the full basket's returns rather than a four-index replication. The [120-day × 182-coordinate experiment](../experiments/equity_full_basket_states/README.md) is complete, with raw/residual and current/change variants and separate risk/mean targets. Its modest favorable later risk point errors remain uncertain; mean/gate improvements are unestablished. The four-ETF proposal below is retained as review-stage context, not a pending task or a claim of execution.

**Assessment:** coordinate choice deserves priority over another image resolution. Our negative image result remains valid for its construction. It does not test every way of representing a market state, a change in state, or a reversal process. Prior work supplies concrete alternative constructions and risk-detection evidence, but not a validated profitable regime for our particular strategy.

## 1. Four meanings of dimension

| Meaning | What it counts | Our example |
|---|---|---|
| Cloud coordinate dimension | Numbers describing each stock/day/transition before computing distances | Three stock loadings, or six lagged factor scores |
| Number of cloud points | Stocks/days/transitions whose geometry we inspect | 182 reference stocks, or 119 adjacent-day pairs |
| Homology dimension | Type of shape being tracked | H0 components and H1 loops; H1 does not mean a one-coordinate cloud |
| Predictor dimension | Numbers supplied to the regression after vectorizing the diagrams | Ten ordinary predictors plus four H0 bins and sixteen H1 pixels = thirty inputs |

A persistence diagram itself is plotted with two axes, birth and death, regardless of whether the cloud has three, six, or thirty coordinates. A 4×4 image has sixteen pixels; it does not give the original stock cloud sixteen coordinates.

## 2. What the relevant prior studies actually constructed

These short method records are based on the linked primary texts. Reported empirical successes are the authors' findings, not our replications. Accessible preprints are identified separately from published versions.

| Study | Point object, coordinates, and window | Relevant output and limitation |
|---|---|---|
| [Gidea–Katz, *Landscapes of Crashes*, 2017 preprint / 2018 journal](https://arxiv.org/html/1703.04385), §4 | One **day**; four coordinates are S&P 500, DJIA, NASDAQ, and Russell 2000 daily log returns. Rolling clouds have **50 or 100 days**, shifted daily. | H1 landscape norms around selected historical crashes. This is a day-state construction, not stock-loading geometry or a residual-strategy profit test. The authors also analyze temporal indicators of the norms. |
| [Gidea, *Critical Transitions in Financial Networks*, 2017](https://arxiv.org/html/1701.06081), §3 | One **stock vertex**; DJIA return correlations over a horizon parameter **T=15**, with distance `sqrt(2(1-correlation))`. No three-PC embedding is required. | Diagram distances relative to a reference state around the financial crisis. A graph distance matrix supplies the filtration directly; the number of stocks is not a chosen coordinate count. |
| [Gidea et al., cryptocurrency transitions, 2018 preprint](https://arxiv.org/html/1809.00695), §4 | Each cryptocurrency separately: four consecutive log-return coordinates, with rolling clouds of **50 delay vectors**. Four dimensions are temporal coordinates, not four cryptocurrencies in one point. | Landscape L1 norms; clustering additionally uses price and return. Selected peak endpoints and mixed clustering inputs limit claims of isolated prospective TDA prediction. |
| [Baitinger–Flegel, 2019 author-posted preprint](https://www.researchgate.net/publication/337857521_The_Better_Turbulence_Index_Forecasting_Adverse_Financial_Markets_Regimes_with_Persistent_Homology), §§2, 3.4; [published 2021 article](https://link.springer.com/article/10.1007/s11408-020-00377-x) | One **day**; **10 or 30 industry-portfolio returns** as coordinates; **60-day clouds**. The preprint compares successive diagrams with a Wasserstein distance, smooths it over 60 days, and calibrates monthly exposure using 60 months. | Authors report out-of-sample S&P allocation improvements. This is positive risk/allocation precedent, not a reproduction of our daily strategy. Exact implementation facts here refer to the accessible preprint; the journal body remains subscription-restricted. |
| [Yagufarov, 2026 working paper](https://mpra.ub.uni-muenchen.de/129341/1/MPRA_paper_129341.pdf), §§2–3 | **49 industry vertices**, correlation-distance filtration, primary **20-day estimation**. Uses topology levels and rates of change for stress forecasts. | Author reports forecast improvements. §2.4 includes average correlation but explicitly omits lagged volatility from predictive controls. Our inference: incremental value against a strong volatility baseline therefore remains unestablished. No code/results replication was performed here. |

The earlier review's Baitinger–Flegel access limitation is now partly resolved by reading an author-posted preprint. Its parameter choices should not silently be attributed to the final journal version. A further [2026 Levine preprint abstract](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5922083) discusses temporal-scale coherence and mean-reversion risk filtering; full-text access returned 403, so its detailed claims and thresholds were not verified or adopted.

## 3. Exactly what our coordinates were

### The stock-loading construction used for the image

At each formation, take the reference stocks' prior 120 returns, fit out SPY stock by stock, and standardize the residual histories. Write their correlation matrix as `C = V Lambda V'`.

Stock i becomes the three-coordinate point:

`x_i = (sqrt(lambda1)*V[i,1], sqrt(lambda2)*V[i,2], sqrt(lambda3)*V[i,3])`.

There are **182 points in three dimensions**. Each coordinate measures the stock's sensitivity along one retained common residual pattern, weighted by its sample variance. Distances are divided by their median. This asks how stock exposure profiles are arranged. It does not put daily return trajectories into the cloud.

All eigenvalue-weighted components reproduce correlation distance; keeping three changes the geometry by truncation. Plain unweighted eigenvector rows are not an equivalent distance representation. Three is an experimental choice, not a demonstrated optimal number or a theorem about market state. Low-variance directions can matter for returns, so variance coverage alone cannot select predictive coordinates.

Rechecking the saved features gives a useful size check: across **142 formation anchors dated 2024 onward**, these three PCs explain a median **27.63%** of the standardized SPY-residual variance, with range **23.31–34.03%**. Earlier the median was 25.36%. These are fixed-reference, rolling 120-session residual fits, not the 2016–2023 raw-return descriptive PCA percentages. The discarded variance is substantial, but this does not establish that it contains useful predictors or that adding components would help.

The image experiment encoded **this same geometry** more fully. Its poor result does not tell us whether a day-return cloud or diagram-change signal would work.

### The lag-state construction tested earlier

Let `u_s` be the three residual-factor scores, each divided by its fitted standard deviation. One point is

`y_s = (u_s, u_(s-1))/sqrt(2)`.

The 120-session history produces **119 points in six dimensions**. The coordinates describe adjacent historical states of the retained factors, not stock sensitivities. This cloud also has median-normalized distances. It received three scalar diagram summaries; **the image follow-up did not test an image of this lag cloud**.

Lag coordinates preserve some adjacency information that an unordered day cloud lacks. Nevertheless, this particular distance construction is unchanged under time reversal: swap the two coordinate blocks and reorder the points. It does not directly measure an arrow of time or a signed, tradable response.

## 4. What the literature changes about our interpretation

**Market structure, changes in structure, and profitable reversal are separate targets.** A market can be turbulent while relative-return reversal is profitable, unprofitable, or simply more volatile. No reviewed study supplies that mapping for our stock portfolio. We must measure it rather than assume that detecting stress means switching off.

**Our preprocessing removes meaningful distinctions deliberately.** SPY regression removes the fitted broad-market component; stock standardization removes stock-specific historical return amplitudes; factor whitening equalizes retained factor variances; cloud median normalization removes overall distance scale. These transformations isolate particular notions of shape. If the task is stress detection, discarded amplitude or synchronization could be useful. That is a reason to compare representations, not evidence that preprocessing caused the failed gate. The simple model already includes SPY volatility, PC concentration, residual mean correlation, and cloud scale controls, so those distinctions are not all absent from the forecasting model.

**A market-neutral portfolio can still have market-state-dependent performance.** Zero estimated SPY beta constrains a linear exposure at formation. It does not imply that the distribution of reversal profits is independent of market volatility, jumps, changing correlations, or estimation error. Adding market state to a predictor would not require adding market beta to the holdings.

**A change detector asks a different question from a level predictor.** Our regressions received current summary levels or image pixels, plus ordinary temporal and strategy-history controls. They did not explicitly receive the distance between today's diagram and a prior diagram. A moving shape may have a stable lifetime norm, and a large static norm need not mean the shape is changing rapidly. Temporal differencing is therefore a specific untested distinction. It also needs conventional change controls: covariance-matrix changes, volatility changes, and movement in distance quantiles. Overlapping rolling clouds share almost all their points, so change scores can merely track entering/leaving outliers.

**Simply replacing our lifetime statistic by a full landscape L1 norm would not create a new test.** Our own mathematical deduction: each interval of lifetime l contributes a tent of area `l²/4`, and summing all landscape layers preserves that total. Therefore `landscape_L1 = sum(lifetime²)/4`. We already used the numerator as a scalar feature. For the same diagrams, that rescaling carries identical information and is canceled by training standardization. A first-layer-only norm, L2 norm, different point cloud, or diagram-change metric is a different construction and must be labeled as such.

**Choosing a dimension is choosing a distance.** Adding an unscaled volatility number to return coordinates may make volatility dominate every neighbor relation just because of its numerical units. Adding many unrelated coordinates can bury a useful relation in estimation noise. Specify why each coordinate belongs to the same observation and fix its scaling from past data. A stock coefficient and a day return cannot simply be concatenated without deciding which date and stock the resulting point represents.

## 5. Recommended next question, not yet executed

The next useful step would be **one literature-grounded market-state benchmark and its temporal change**, followed by a separate strategy-specific check. This changes the measured object instead of searching for a prettier encoding of the same stock cloud.

An interpretable starting point is one day represented by four index-proxy returns:

`z_s = (SPY_return_s, QQQ_return_s, IWM_return_s, DIA_return_s)`.

Those four coordinates represent broad U.S., Nasdaq-100, small-cap, and Dow exposure. They are an ETF-proxy construction, not an exact replication of the four index series. The choice is motivated by the classic study, not selected from our profit ranking. Our existing equity download includes SPY, not these three additional ETF series; their usable history, price conventions, and coverage need checking before execution. No download was performed for this review.

Start with one declared 60-session cloud and H0/H1, with Euclidean distances in common return units. Compare the original distance scale with a version divided by its median while retaining that median as a baseline input. Those versions ask whether scale or shape matters. Do not whiten every new window in the first amplitude-preserving version. Coordinate rescaling learned from the whole evaluation history would be leakage.

Choose one diagram-change statistic and one comparison lag before looking at its outcomes. For example, an H1 Wasserstein distance between the current and five-sessions-earlier diagrams asks how much loop structure moved over the gate's update interval. The matching point count, infinite-interval treatment, Wasserstein order, normalization, and empty-diagram behavior must be specified before running. No distance lag is known to be optimal from the reviewed studies.

The first primary task should be a clearly defined risk target, such as the fixed strategy's next20-session RMS gross daily return. RMS is the square root of the average squared return; it measures amplitude of both favorable and unfavorable outcomes, not the mean. Compare with trailing strategy RMS, index volatilities, the full four-variable covariance summaries, and ordinary measures of their changes. This does not assume stress is bad for the strategy. A separately declared mean-return target can test the missing profitability link; finding only a risk signal would not justify a profit gate.

Keep the trading portfolio fixed and report everything pre-fee if a gate is eventually tested. Use completed labels, past-only preprocessing, all calendar days, and dependent-data uncertainty. Existing 2024–2026 observations remain examined; an exploratory historical comparison cannot become a fresh holdout through a different representation. Do not add many dimensions or lags, select a threshold by this sample's Sharpe, or infer that the literature guarantees a benefit.

This is a proposed bounded design, not a claim that four dimensions or sixty days is best. The important sequence is **target → point object → coordinates and units → window and metric → diagram and temporal change → incremental test**.

## Evidence locations and access

- Gidea–Katz: full arXiv HTML, §3.1 and §4; exact point dimension and window sizes checked.
- Gidea financial networks: full arXiv HTML, §3.1–3.2; metric and horizon parameter checked.
- Cryptocurrency transitions: full arXiv HTML, §2.1 and §4; delay dimension and analysis/classifier inputs checked.
- Baitinger–Flegel: author-posted 2019 preprint text, §§2, 3.4, 4; publisher abstract/appendix preview. This improves access over our October 12 review without claiming final-version identity.
- Yagufarov: full 23-page MPRA working paper, §§2.1, 2.4, 3.1, 3.3–3.5. Predictive controls and tuning scheme inspected, code unreplicated.
- Levine: indexed SSRN author abstract only; direct page returned 403. Parameter claims are not used as prescriptions.
- Our constructions: [source](../experiments/equity_persistence_regimes.py), [original specification](../experiments/equity_persistence_regimes/specification.json), [image specification](../experiments/equity_persistence_images/specification.json). No frozen source or result was changed for this review.
