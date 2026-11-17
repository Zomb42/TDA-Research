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
tdaeq/      shared library (data, factors, clusters, topology, portfolio, evaluate)
studies/    one script per question; each writes to results/<name>/
results/    figures, a small table and a one-page RESULT.md per study
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

## Results

| Study | Question | Result |
|---|---|---|
