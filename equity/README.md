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
| `s11_late_day_characterize` | Does the TDA hedge matter, and where does the profit come from? | TDA peers 2.21 against 1.43 for sectors and 0.88 for the market; positive in every sector and year; tuning on early years picks a worse version |
| `s12_late_day_costs` | Is it profitable after measured spreads and fees? | Ordinary orders lose money (spread 3.2 bps). Closing auction in, opening auction out: net Sharpe 0.97 (0.30 to 1.63), 1.4% a year per dollar of gross |
| `s13_intraday_barcode` | Does the 1D-sweep barcode of the day's 5-minute path say which late moves reverse? | No: its total is exactly distance travelled minus range, the rest is 72–74% explained by plain path measures, and adding it does not improve any forecast |
| `s14_learned_filter` | Does learning the curve the barcode is taken of (the paper's Remark 3.2) help? | No: the same as the model without the barcode (Sharpe difference 0.00), and below the one-line rule |
| `s15_straight_runs` | Do straight runs into 3:40 reverse more than choppy ones (seen by chance in study 13)? | Not confirmed on 1,961 unseen days: every third reverses, gap +1.5 bps (−1.5 to 4.5) |
| `s16_tuning` | Would small changes to the settings make it better? (576 versions, 2017–2026) | No: the current settings rank 18th; nothing beats them consistently, and tuning that cannot see the years it is scored on does no better |
| `s17_exit_timing` | Sell at the open, a few minutes later, or hold longer? | Sell at the open: Sharpe 2.21 against 1.20 at 10:00 and 1.64 at the next close; the first 5 minutes after the open move against the book |
| `s18_combining_and_speed` | Do blended versions, other strategies, or a faster signal help? | Fair blends add a little (2.34 against 2.26); the 5-day reversal is uncorrelated but weak (+0.1); a signal read and traded at 3:50 at the midpoint earns +0.46 bps a day, and it is not bid-ask bounce |
| `s19_grouping_checks` | Does it matter which stocks TDA groups together, and do the correlation window and rebuild frequency matter? | Members shuffled within sectors: median 1.63, best of 300 1.96, never TDA's 2.21. More frequent rebuilds help, mostly reached by every 5 days (daily +0.04 on average); shorter windows do not help; slightly better settings exist but do not hold across periods |
| `s20_density_k` | Does HDBSCAN's density step (`min_samples` k) help with the smallest group kept at 2? | No: k = 1 and 2 are identical by construction, k = 3 gives 2.06 and k = 5 gives 1.59 (−0.62, interval excludes zero). Daily rebuilds +0.07 overall, not better from 2024 on |
