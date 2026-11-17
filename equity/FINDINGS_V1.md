# What the first 23 equity experiments found

A short record of the work done between October 28 and November 10, 2026. Full reports, code and outputs are in `_archive/equity_v1/` (the complete log is `_archive/equity_v1/docs/EQUITY_RESEARCH_LOG.md`). All returns are before costs.

## The strategy that was tested

Each day, for every stock:

1. Using the previous 120 days, estimate how the stock moves with SPY and with three common patterns found by PCA.
2. Take today's return and subtract what those explain. What is left is the stock's **surprise**.
3. Buy stocks with a negative surprise and short those with a positive one, sized so the book has zero net dollars, zero SPY exposure and zero exposure to the three patterns.
4. Enter at the next day's open, exit at that day's close.

## The three questions, and where each stands

| Question | Answer so far |
|---|---|
| **Shared movement:** do stocks have stable peer groups? | **Yes.** Groups formed from past data keep moving together afterwards. |
| **Reversal:** does a surprise move bounce back? | **Not shown.** Every estimate has a confidence interval that includes zero. |
| **Neutral portfolio:** can the book cancel common risk? | **Mechanically yes**, but being neutral did not create a return. |

## The numbers that matter

**Base strategy, 200 stocks**

| Period | Return per year | Sharpe |
|---|---:|---:|
| Feb 2017 – Oct 2026 (all) | 0.68% | 0.19 |
| Jan 2024 – Oct 2026 (later part only) | 3.37% | 0.89 |

Mean in the later part is +1.34 bps/day with a 95% interval of about −0.5 to +3.5. On the original 30 stocks the same strategy lost money (−0.65 bps/day). Worst drawdown over the full run is 17%.

**Peer groups** (11 groups, 252-day history, scored on the next 20 days; higher is better)

| Method | Largest group | Future correlation inside minus outside |
|---|---:|---:|
| H0 / single linkage | 186 of 199 stocks | 0.063 |
| Sectors | 41 | 0.145 |
| Average linkage | 78 | 0.210 |

H0 of a correlation-distance filtration is exactly single-linkage clustering. It chains nearly every stock into one group. Small tight branches are real and stable (AEP/DUK/SO, AMAT/KLAC/LRCX, COP/CVX/EOG/XOM, MPC/PSX/VLO), but average linkage finds almost all of them too (486 of 496).

## Every experiment in one line

| # | What was tried | Result |
|---|---|---|
| 1–2 | Correlations and PCA on 30 stocks | Clear common movement; PC1 is the market (0.93 correlation with SPY) |
| 3–5 | Build and backtest the strategy on 30 stocks | No edge; more PCA factors or overnight timing did not fix it |
| 6–7 | H0 clusters as peer groups (30 stocks) | Chaining; no better than average linkage |
| 8 | Hold 1, 5 or 20 days | No reliable bounce at any horizon |
| 9 | Peer groups on 200 stocks | Table above |
| 10 | Strategy on 200 stocks | Table above |
| 11 | Persistence summaries as an on/off switch | +0.41 bps/day over a plain switch, interval −0.21 to +1.04 |
| 12 | Persistence images as the switch | Worse (1.19% a year versus 3.39%) |
| 13, 19 | Literature reviews | Prior work finds TDA useful for describing stress and risk, less for returns |
| 14 | Whole-market "day cloud" shapes | Risk forecast error 2.2–3.4% lower, interval includes zero; no return gain |
| 15 | Factor analysis instead of PCA | +0.065 bps/day, no real difference |
| 16 | Buy index after a 3-day sell-off (QQQ/SPY) | Works only if you could trade at the closing price you just observed |
| 17–18 | VIX as a condition | VIX tracks the strategy's risk (correlation 0.32 with the size of its moves), not its direction; the 20–30 band result depends on 2020 |
| 20 | TDA shapes on top of VIX | Risk error a further 2.2–3.6% lower, interval includes zero |
| 21 | Merge tree of today's surprises on a stock graph | No gain in predicting returns |
| 22 | H0 tree combined with actual holdings | Small risk-forecast gain, interval includes zero |
| 23 | Data refresh to Nov 9; centroid linkage | Centroid linkage chains as badly as H0 (188 of 200 in one group) |

## Why the TDA results were flat

1. **The target was too hard.** Most tests asked TDA to predict the average profit of a strategy that has almost no profit, using about 138 overlapping forecasts. Very little could pass that.
2. **No noise check.** Shapes came from 120 days on about 200 stocks. With more stocks than days, correlations are noisy, and no one measured how much shape pure noise creates.
3. **H0 was used in its weakest form.** Plain single linkage chains. The standard fix (requiring dense neighbourhoods, as HDBSCAN does) was never tried.
4. **The only consistent hints were about risk**, not return (rows 14, 17, 20, 22).

These four points are what the new studies in [README.md](README.md) are built to address.

## Caveats that still apply

- The 200 stocks are today's large companies, so past losers that shrank or delisted are missing.
- Dates from 2024 onward have been looked at many times. Only data after November 9, 2026 is truly unseen.
- Fills are assumed at the daily bar's open and close prices.
