# Residual mean reversion: the intended 151 Trading Strategies construction

Verified October 28, 2026. This records the user's intended strategy family for future implementation. It is a specification/reference note, not evidence of profitability or a completed backtest.

**Subsequent run:** the first [frozen daily backtest](../experiments/equity_residual_backtest/README.md) implements the proposed prior-day close-return signal with next vendor-bar open-to-close holding. Both baseline models have negative average gross returns in its 2024–October 2026 evaluation. Algebra checks passed; no profitable reversal effect is established. The definitions and earlier illustrative calculations below remain the reference. This run is not the source paper's overnight-signal intraday illustration.

## Source identification

The relevant sections are **3.9 (single cluster), 3.9.1 (multiple clusters), and 3.10 (weighted regression)** in Kakushadze and Serur's *151 Trading Strategies*. They form a cross-sectional contrarian construction: observe a return for every stock over the same interval, remove the return explained by specified exposures, and short relative outperformers while buying relative underperformers. The text permits general exposure columns and inverse historical variance weights. It does not uniquely specify our lookback, trading interval, exit, or costs. Section 3.7's residual **momentum** is a separate strategy. [Author manuscript, SSRN ID 3247865, mirrored PDF](https://smallake.kr/wp-content/uploads/2019/12/SSRN-id3247865.pdf)

Access: the SSRN landing page returned HTTP 403; the accessible author manuscript is dated August 17, 2018. Its printed pages 46–49 contain these sections, with consecutive equation numbers 292–318. Those numbers differ from the published book's chapter-based numbering. Relevant equations were checked against the independently published derivation in [Kakushadze, Mean-Reversion and Optimization, sections 2.3–2.7](https://arxiv.org/html/1408.2217v3). The earlier [technical note](../../literature/merge_trees_and_return_pilots_2026-10-12.md#8-equity-peer-structure-and-weighted-return-mean-reversion) retains the publisher-status caveat; this note checks the construction's mathematics.

## The mathematical specification, in our notation

At one signal timestamp, let `r` be an N-vector of observed stock log returns, `X` an N-by-K matrix of known exposures, and `W = diag(w_i)` positive regression weights. Each regression row is **one stock at the same signal time**. Historical observations can estimate X or W, but are not the rows of this cross-sectional regression.

```text
r_i = log(P_i(t2) / P_i(t1)), with a common interval [t1, t2]
beta = solve(X.T @ W @ X, X.T @ W @ r)
e = r - X @ beta
s = W @ e
D = -gross_dollars * s / sum(abs(s))
shares_i = D_i / executable_entry_price_i
```

The last normalization applies when `sum(abs(s)) > 0`; otherwise hold zero positions. `D` contains signed **dollar holdings**, not share counts. `beta` contains current cross-sectional fitted factor returns, not each stock's historical market beta. Solve the system with stable linear algebra; do not explicitly invert a matrix in implementation. Require independent columns or explicitly resolve redundant exposures.

The normal equations give the independently checkable identities:

```text
X.T @ W @ e = 0
X.T @ D = 0
sum(abs(D)) = gross_dollars
```

If the all-ones vector lies in the span of X, holdings are dollar-neutral. A complete one-hot cluster matrix already spans that vector, so adding another intercept makes the columns dependent. Cluster exposures make each cluster's **net dollars** zero; they do not imply zero market beta or equal gross allocation across clusters. Gross dollars include both long and short holdings, and need not equal account equity.

For one-hot peer groups, our algebra reduces to:

```text
peer_mean_g = sum(w_j * r_j for j in group_g) / sum(w_j for j in group_g)
e_i = r_i - peer_mean_group_i
s_i = w_i * e_i
```

The peer mean includes the stock itself. A leave-one-out peer mean is a different construction; it cannot silently replace this one while assuming the same neutrality identities.

## Why the weighting detail matters

The essential signal is **W times the WLS residual**, not the unweighted WLS residual by itself. An independently constructed three-stock example demonstrates the distinction:

| Stock | Observed return | Assumed trailing volatility | WLS residual | Dollar holding at $100,000 gross |
|---|---:|---:|---:|---:|
| A | +2% | 1% | +0.6667% | -$50,000 |
| B | +1% | 2% | -0.3333% | +$6,250 |
| C | -1% | 2% | -2.3333% | +$43,750 |

Here X is one column of ones and `w_i = 1 / volatility_i**2`. The weighted peer mean is 1.3333%. Residuals sum to -2%, while their weighted values sum to zero. Trading `-e` would fail dollar neutrality; trading `-W e` preserves it. This example tests algebra only and assigns no expected future return.

Positive residual means outperformance of the fitted peer return, even if both stock and peers fell in absolute terms. The contrarian trade sells that relative outperformance. Clipping, ranking, sign-only positions, or independent position caps generally require a fresh neutrality check or constrained portfolio construction.

## Timing: the source leaves choices that we must make explicitly

The accompanying *Mean-Reversion and Optimization* paper supplies a specific illustration in **section 7**: overnight adjusted close-to-open returns form the cross-sectional signal, and a portfolio is held intraday. Its simple example uses unit-weight industry regressions, with an idealized entry at the same open used to observe the signal. The author explicitly discusses that timing limitation and omitted costs/slippage. This illustration does **not** make overnight-to-intraday trading mandatory for sections 3.9–3.10. [Primary derivation and example](https://arxiv.org/html/1408.2217v3#S7)

Our proposed implementation choices, not instructions established by the book:

1. For the first daily pilot, estimate groups/loadings and inverse-variance weights using data available **before** the signal interval. Specify a variance floor and treatment of single-stock clusters.
2. Observe close-to-close return on day t and run the cross-sectional regression at t. A first executable daily-bar convention could enter at day t+1's open and exit at its close; this tests delayed reversal and omits any reversal before entry. It is not the paper's overnight example.
3. Alternatively, an overnight-signal study needs verified regular-session open/close definitions and post-signal entry observations. Our existing daily OHLCV supports preliminary decomposition, but realistic delayed fills require intraday data.
4. Measure next-interval returns/P&L separately from the observed signal. Include costs, borrow assumptions, turnover, and exposures when making trading claims. Never use the same return to generate positions and claim subsequent profits.

## Connection to our PCA/TDA exploration

The current notebook's **time-series regressions on SPY** are diagnostic preprocessing for correlation pictures. They are not the cross-sectional strategy above. Likewise, PCA scores are not automatically trading signals.

For a future PCA baseline, estimate an exposure basis using trailing data. If PCA was fit on volatility-standardized returns, an exposure basis for **raw-return** regressions includes the corresponding volatility scaling (`diag(training_sigma) @ eigenvectors`); rotations or per-column rescaling preserve its span, but per-stock rescaling does not. Include the intercept or verify that its vector is spanned if dollar neutrality is required.

For the TDA comparison, change how X's peer structure is defined while holding the cross-sectional regression, W, timing, normalization, and evaluation fixed. Correlation-derived H0 is single linkage. No Ornstein–Uhlenbeck fit, cointegrated price spread, residual z-score threshold, or demonstrated profitable reversal is implied by this specification.

## October 28 follow-up: explicit market and PCA neutrality

The user's current direction is to investigate positions neutral to selected common exposures, with contrarian positioning based on previous observed relative returns and appropriate normalization. This section states implementation choices as proposed research baselines; it does not establish their predictive value or an optimal component count.

### What neutrality means

In a frozen estimated linear representation `r_future = B @ f_future + residual_future`, a dollar portfolio `D` has modeled factor contribution `(B.T @ D).T @ f_future`. Requiring `B.T @ D = 0` removes that contribution in the model. Requiring `ones.T @ D = 0` also makes the stock portfolio dollar-neutral. The identities concern estimated exposures at portfolio construction; future exposures can change. With log-return factors, the dollar P&L interpretation is a small-return approximation; realized trading P&L uses actual price changes and holdings.

Neutrality does not mean every stock is hedged separately, or that the residual portfolio is risk-free. Long and short positions offset the selected exposures in aggregate. Different stocks can carry different positive and negative dollar positions.

### SPY as an explicit factor

PC1 and SPY are not interchangeable. The previously reported 0.928 correlation is a retrospective whole-period score correlation. It does not prove that a portfolio neutral to PC1 is SPY-beta-neutral, especially in a different window.

To target SPY exposure, estimate each stock's time-series beta using a prior window. Put the **N-vector of stock betas** in X, not SPY's T-day return series. Neutrality is `sum(D_i * estimated_beta_i) = 0`; dollar neutrality alone only requires `sum(D_i) = 0` and is different.

A clear first comparison is:

```text
baseline A: X = [ones, stock_SPY_betas]
baseline B: X = [ones, stock_SPY_betas, residual_PC_exposure_1, ..., residual_PC_exposure_k]
```

For baseline B, regress each stock's prior return history on an intercept and SPY, then fit PCA to the standardized historical residual panel. This seeks additional variation beyond the fitted market relationship. It does not identify economic causes or guarantee future independence from SPY. Start with a small fixed k, e.g. 3, as an exploratory setting, not a result that three is optimal. Original-return PCA with an explicit SPY constraint is another valid construction, but overlapping exposure columns require rank/conditioning checks.

### Convert standardized PCA directions to dollar-exposure units

If `S = diag(training_volatility)` and `V` contains retained eigenvectors, standardized returns satisfy approximately `z = V @ scores`. Thus raw-return reconstruction is `r - training_mean = S @ V @ scores`, and an exposure basis is `B = S @ V`. For residual PCA, use the residual training volatilities in S. Normalized correlation loadings differ from V by per-column scaling, which leaves the span unchanged; omitting S changes per-stock scaling and generally changes the neutrality condition.

To see the distinction directly, the coefficient of a component score in portfolio return is `D.T @ S @ V`, not generally `D.T @ V`. Volatility scaling therefore belongs in the exposure conversion even though PCA was intentionally standardized for estimation.

### Keep the three normalizations separate

1. **Historical standardization for PCA** controls which return variation PCA emphasizes. Estimate its mean and volatility from prior observations.
2. **Cross-sectional regression/risk weighting** uses `W = diag(1 / prior_variance_i)` in this baseline, with a prespecified variance floor. Compute `e = r_signal - X @ fitted_factor_returns`, then `s = W @ e`. This is inverse-variance weighting, not simply a residual z-score. A residual-volatility-based weighting is a separate choice to compare explicitly.
3. **Portfolio size normalization** sets `D = -gross_dollars * s / sum(abs(s))`. It rescales every position by the same scalar, preserving `X.T @ D = 0`. With zero signal, hold zero positions; an implementation also needs a prespecified tolerance rather than magnifying numerical residue into a full-gross portfolio.

Ranking residuals, clipping positions, or scaling each stock again after step 3 generally breaks exact neutrality. If such modifications are required, reimpose the constraints in portfolio construction and check them afterward.

### Causal sequence for a daily experiment

```text
Before signal day t: fit betas, PCA basis, volatilities from prior data (e.g. 120 sessions ending t-1).
After observing day t's adjusted close: compute day t's close-to-close return vector.
At that signal time: run the cross-sectional WLS and construct target dollar positions.
After signal observation: enter at a feasible subsequent time; evaluate a separately defined future return interval.
```

The 120-day **exposure estimation window**, one-day **signal return interval**, and future **holding interval** are separate choices. They should not silently become the same lookback. Daily next-open-to-close is one possible delayed experiment, not a faithful fill simulation or an established optimal horizon. No future returns are used in the algebra check below.

### Numerical check on our downloaded data

Saved [one-date math check](../experiments/equity_correlation_pca/factor_neutral_math_check.json) and [illustrative holdings](../experiments/equity_correlation_pca/factor_neutral_example_holdings.csv). Signal date: **2023-12-29**. Exposure estimation: **120 sessions, 2023-07-11 through 2023-12-28**. All holdings are per unit gross and are historical illustrations.

Dollar + SPY neutrality, dollar + three original-return PC constraints, and dollar + SPY + three residual-PC constraints were checked separately. Maximum absolute exposure errors against column-scaled constraints were about `1e-15` or smaller. The raw-WLS-residual position alternatives failed these same constraints (errors roughly 0.08–0.19 under the reported scaling). This verifies an algebraic distinction, not performance.

The original-PC portfolio had SPY beta exposure about 0.0073 per unit gross on this date; the explicitly SPY-neutral portfolios were near numerical zero. The particular magnitude is illustrative, not a claim that PCA-only portfolios generally have small market exposure.

All 30 independent original PCs span the entire 30-stock space. Fitting all of them left a residual norm around `2e-17`. Requiring neutrality to all those directions permits only zero holdings. We must choose a limited set of exposures; larger explained-variance coverage is not automatically a better mean-reversion strategy.
