# Financial TDA research

Three small studies of topological data analysis (TDA) on financial data. Each uses a different kind of object:

| Study | Object | Where |
|---|---|---|
| **Equity** (current focus) | Relationships among 200 stocks | [equity/](equity/README.md) |
| BTC | Shapes traced by a price series over time | [btc/](btc/README.md) |
| Liquidity | Order-book depth as a surface over price and time | [liquidity/](liquidity/README.md) |

## Where each study stands (November 17, 2026)

| Study | State | Main result | Next |
|---|---|---|---|
| Equity | 10 studies, [results](equity/RESULTS.md) | TDA peer groups beat sectors (0.62 against 0.41) and tie a plain fine clustering. The strongest effect is not topological: the late part of a stock's day reverses by the next open, and it is visible before the close | Measure real spreads near the close, forward test |
| BTC | 1 large study, [results](btc/RESULTS.md) | Shape features improve a volatility forecast by 1%; plain fat-tail measures improve it by 2% and make shape redundant | Stop return prediction; move to the order book |
| Liquidity | Plumbing and one method finding | Loop counts in depth surfaces come from the smoothing and binning, not from the book. 25 hours of order-book data is too little to test anything | One week of order-book recording is in progress on a VM; then test book shape against spread, depth and imbalance |

The same pattern holds in every head-to-head test so far: TDA points at something real, and a plain measure of the same thing ties or beats it.

## Setup

Use the existing `tda` Conda environment: `conda activate tda`, or `conda run -n tda python ...`.

## Layout

```
equity/        shared library, studies, results (start with equity/README.md)
btc/           BTC features and data-collection notes
liquidity/     depth-grid experiments
market_data/   download scripts and datasets (bulk data is local, not in git)
literature/    reviews that apply to more than one study
jobs/, tests/  BTC collection job and its tests
_archive/      old equity experiments, notebooks and docs (local only, not in git)
```

Tutorial notebooks, [TUTORIAL_GUIDE.md](TUTORIAL_GUIDE.md) and the ParaView/TTK launchers stay at the top level. [AGENTS.md](AGENTS.md) holds the rules for BTC data collection (no orders, no paid data).

## Conventions

- Performance is reported **before costs**, and says so.
- Anything used to make a decision on day t must be known before that day's trade.
- Every TDA result is shown next to a plain method that uses the same inputs.

## History

On 2026-11-16 the equity folder was rebuilt around one shared library. The earlier 23 experiments are summarised in [equity/FINDINGS_V1.md](equity/FINDINGS_V1.md). Their files are in `_archive/equity_v1/` on this machine, and the tracked ones are also in git under the tag `pre-cleanup-2026-11-16` (`git checkout pre-cleanup-2026-11-16 -- <path>` restores any of them).
