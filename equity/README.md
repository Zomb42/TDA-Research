# Equity study: what does the shape of stock relationships tell us?

Data: 200 large US stocks plus SPY, daily, January 2016 – November 9, 2026 (`market_data/datasets/equity_daily_expanded_2016_2026-11-09`).

Three questions, and how TDA is used for each:

| Question | TDA's job | How we score it |
|---|---|---|
| **A. Shared movement** — which stocks move together? | Find peer groups and market-wide shape | Do the groups still move together over the next 20 days? |
| **B. Neutral portfolio** — can we cancel common risk? | Give a cleaner picture of which stocks share risk | Realized volatility of the portfolio afterwards |
| **C. Reversal** — does a surprise move bounce back? | Say which surprises are likely noise | Rank correlation between the signal and the next return |
| **D. Strategy** — combine whatever works | — | Return and Sharpe on dates not used to design it |

What the earlier 23 experiments found: [FINDINGS_V1.md](FINDINGS_V1.md).

## Layout

```
tdaeq/      shared library (data, factors, clusters, topology, signals, portfolio, risk, evaluate, plots)
studies/    one script per question; each writes to results/<name>/
results/    figures and tables written by the studies
RESULTS.md  what the studies found
tests/      checks on the library
literature/ the exact maths of the reversal strategy
```

## Running

```sh
conda run -n tda python equity/tests/test_tdaeq.py            # library checks
conda run -n tda python equity/studies/s00_baseline_check.py  # new code reproduces the old numbers
conda run -n tda python equity/studies/<study>.py             # any study
```

## Rules for every study

1. **Time split.** Design on dates before 2024. Confirm once on 2024 – Nov 9, 2026 (these dates were already looked at by the old experiments, so treat them as a weak check). Data after Nov 9, 2026 is the real test.
2. **Noise first.** A shape only counts if scrambled data does not produce it.
3. **Plain competitor.** Every TDA number sits next to a simple method using the same inputs.
4. **Before costs**, with fills at the daily open and close.
5. **Know the two traps** (both measured in `s09_ml_forecast`): the stock list was chosen with hindsight, and close-to-close results use the close as both signal and trade price.

## Results

Full write-up with figures: **[RESULTS.md](RESULTS.md)**.

| Study | Question | Result |
|---|---|---|
| `s00_baseline_check` | Does the new library reproduce the old numbers? | Yes, all six |
| `s01_noise_floor` | How much of the shape is real? | H0 links are real (94% beat noise at 252 days); total ring lifetime is lower than in noise and mirrors average correlation |
| `s02_peer_groups` | Do long-lived H0 branches make good peer groups? | Peer correlation 0.62 against 0.41 for sectors; ties a fine average-linkage cut |
| `s03_signal_search` | Is there any bounce? | Small; the steadiest form is the 1-day move relative to TDA peers (positive in 10 of 10 years) |
| `s04_peer_reversal_book` | Does it make a strategy? | Gross Sharpe 0.81 against 0.30 for market-neutral; breaks even at 0.8 bps of cost, so not profitable after costs |
| `s05_when_is_the_bounce` | Does tightness or VIX strengthen it? | No stable pattern |
| `s06_risk_estimates` | Do tree-based risk estimates help? | Better than raw, worse than standard shrinkage |
| `s07_market_shape` | Does shape warn of risk? | No; classic summaries are 80–85% explained by average correlation |
| `s08_path_shape` | Does the barcode of a stock's own path (Zeng et al. 2021) help forecast it? | No; gain in rank correlation +0.0011 and +0.0015, both intervals include zero |
| `s09_ml_forecast` | Does machine learning without topology help? | It doubles the gross Sharpe (0.9 to about 2.0), but a one-line rule on the late part of the day's move matches it, and the effect needs a trade at the close it is measured on |
| `s10_late_day_tradable` | Is the late-day reversal tradable? | It is visible before the close: seen 20 minutes before, traded 10 minutes before, Sharpe 2.2 before costs (1.6 to 3.0). It breaks even at 0.70 bps per dollar traded, about the size of trading costs |
