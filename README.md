# Financial TDA research

Three studies of topological data analysis (TDA) on financial data, each built on a different kind of object. They will be presented together on December 4, 2026.

| Study | Object | Start here |
|---|---|---|
| **Equity** | 200 stocks as points, linked by correlation | [equity/README.md](equity/README.md), then [RESULTS.md](equity/RESULTS.md) |
| **BTC price path** | The shape traced by BTC's recent returns | [btc/README.md](btc/README.md), then [RESULTS.md](btc/RESULTS.md) |
| **Liquidity** | The Kalshi BTC perp order book: depth over price and time, bands, point clouds | [liquidity/README.md](liquidity/README.md) |

## Main results (as of November 18, 2026)

| Study | What TDA found | Plain competitor | Trading result (before costs unless stated) |
|---|---|---|---|
| Equity | Persistence (H0) finds about 45 tight peer groups; peers track a stock at 0.62, against 0.41 for sector peers | A plain clustering cut equally finely ties it | The late-day move reverses overnight. Hedged with TDA peers: Sharpe 2.2 before costs; after measured costs only the auction-to-auction version survives (net Sharpe 1.0) |
| BTC price path | Shape of the last day's returns improves a volatility forecast by 1% | Plain fat-tail measures improve it by 2% and make shape redundant | Return direction not forecastable |
| Liquidity | Depth sits in ridges that move with the price. The band graph (time-Reeb graph) and point clouds of book states show real structure | Plain bin counts explain 72–97% of the topological features, which add nothing to forecasts | Kalshi copies Binance about 100–200 ms late. Resting orders lose; no strategy slower than about 100 ms found an edge |

**The pattern across all three:** TDA points at something real, and a plain measure of the same thing ties or beats it. The equity peer groups are where TDA earns its place, as the hedge behind the one profitable strategy.

## Conventions

- Performance is reported **before costs** and says so. Measured costs are shown separately where they were measured.
- Anything used to decide at time t must be known before t: receipt times for the order book, signals known before the trade for equities.
- Every TDA result is shown next to a plain method that uses the same inputs.

## Setup and layout

Use the `tda` Conda environment: `conda activate tda`, or `/Users/derickshi/anaconda3/envs/tda/bin/python` on this Mac.

```
equity/        shared library (tdaeq/), studies s01-s19, results
btc/           price-path study b01, BTC data notes (DATA.md)
liquidity/     order-book studies l01-l17, results
market_data/   download/recording scripts and datasets (bulk data local only; see its README)
literature/    reviews used by more than one study
jobs/, tests/  the CRC recording job and its tests
_archive/      superseded experiments and notes (local only, not in git)
```

Tutorial notebooks, [TUTORIAL_GUIDE.md](TUTORIAL_GUIDE.md) and the ParaView/TTK launchers stay at the top level; the Reeb-graph code uses that TTK install. [AGENTS.md](AGENTS.md) holds the standing rules for AI assistants working here.

## History and archive

- **November 16:** the equity folder was rebuilt around one shared library. The 23 earlier experiments are summarized in [equity/FINDINGS_V1.md](equity/FINDINGS_V1.md). Their files are in `_archive/equity_v1/`, and the tracked ones are in git under the tag `pre-cleanup-2026-11-16`.
- **November 18:** the liquidity and BTC notes were rewritten. Superseded plans, logs, design notes and October pilots are in `_archive/liquidity_2026-11-18/`, `_archive/btc_2026-11-18/` and `_archive/root_docs/`. Files that were tracked can be restored from git commit `5f0579f` (`git checkout 5f0579f -- <path>`).
