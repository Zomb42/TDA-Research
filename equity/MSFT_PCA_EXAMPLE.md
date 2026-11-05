# An actual Microsoft factor equation

Extracted October 29, 2026 from the existing PCA strategy; no strategy was retuned. Signal date: **October 26, 2026**. Exposure estimation: **120 sessions, May 5–October 23, 2026**, across 200 admitted stocks. The corresponding execution was October 27.

## The equation

Using daily log returns, with the stock and SPY returns centered on their respective training-window means:

\[
\widetilde r_{\mathrm{MSFT},t}
\approx
1.069545\,\widetilde r_{\mathrm{SPY},t}
-0.482801\,F_{1,t}
-1.033699\,F_{2,t}
-0.087460\,F_{3,t}
+\epsilon_{\mathrm{MSFT},t}.
\]

Each PCA factor is scaled to **1% daily sample standard deviation in this training window**. This makes the coefficients readable as return sensitivities. A +1% value of F2 contributes approximately −1.034 percentage points to Microsoft's fitted daily log return, holding the other terms fixed. These coefficients are exposures, not fractions invested; they need not sum to one.

For a hypothetical day with SPY one percentage point above its training mean, F2 = +1%, and F1 = F3 = 0, the model's Microsoft return above its training mean is approximately `1.070% − 1.034% = 0.036%`, before its residual. This is illustrative arithmetic, not an observed day or a forecast.

Without centering the stock/SPY returns, the equivalent historical decomposition has an intercept of **0.146176% daily log return**. That fitted historical intercept is not an established expected profit or a separate trading signal.

## What those factors actually are

First fit each stock's prior returns on an intercept and SPY. Divide the resulting residual history by its stock-specific residual standard deviation to obtain standardized histories Z. PCA's top three right singular vectors V define three weighted combinations of these histories. The raw scores are `scores = Z @ V`.

Let `s_k` be the sample standard deviation of score k. Define `F_k = 0.01 * score_k / s_k`. A stock's readable coefficient is then `B_ik = residual_sigma_i * V_ik * s_k / 0.01`. Consequently, `F @ B.T` exactly equals the original score reconstruction. This is a change of units, not a new model.

Microsoft's original saved exposure coefficients are `[-0.000775071179, -0.002584333795, -0.000265939013]`; score standard deviations are `[6.229121869, 3.999867506, 3.288723391]`. The conversion above produces the displayed equation. Microsoft's SPY beta is 1.069544618.

The component signs have no intrinsic economic meaning: flipping both a factor and its loading preserves the same fitted return. The factors are statistical directions, not automatically named economic causes. These are window-specific coefficients, not permanent Microsoft properties.

## Connection to the actual trading rule

The equation above describes the historical factor construction. On a signal day, the strategy freezes the estimated stock exposures, then fits that day's returns across stocks using weighted regression with columns `[ones, SPY beta, three PCA exposures]`. Its fitted coefficient on the SPY-beta column is estimated across stocks; it is not forced to equal that day's observed SPY return. The daily cross-sectional intercept is also distinct from Microsoft's historical intercept above.

Positions are proportional to minus inverse-variance-weighted cross-sectional residuals, normalized to unit gross. Rescaling the PCA columns and inversely rescaling their fitted factor returns leaves the holdings unchanged.

For the October 26 signal, Microsoft's cross-sectional fitted log return was **−0.077990%**, versus its observed **+1.530618%**, leaving a **+1.608608%** residual. It was therefore shorted at **0.606149% of total gross exposure** for the next session. This observed cross-sectional fit uses the day's fitted common-move coefficients, not a direct substitution of observed SPY into the historical equation. A positive residual does not establish that a reversal will follow.

## Verification and source

The calculation reconstructed the exposure estimation from the saved return panel and verified: PCA exposures match the saved arrays; SPY betas match; factor rescaling preserves the full fitted reconstruction; all 200 reconstructed portfolio holdings match the saved holdings to numerical tolerance.

- [Saved exposures, betas, scales and holdings](experiments/equity_efa_vs_pca/positions_and_loadings.npz), PCA3 index 0, final signal index.
- [Source implementation](experiments/equity_efa_vs_pca.py), functions `fit` and `main`.
- [Daily return panel](../market_data/datasets/equity_daily_expanded_2016_2026-10-27/returns_log.csv).

This is an explanatory extraction from existing results, not a new backtest, factor-count choice or TDA result.
