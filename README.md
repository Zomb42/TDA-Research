# Financial TDA research

Three small studies of topological data analysis (TDA) on financial data. Each uses a different kind of object:

| Study | Object | Where |
|---|---|---|
| **Equity** (current focus) | Relationships among 200 stocks | [equity/](equity/README.md) |
| BTC | Shapes traced by a price series over time | [btc/](btc/README.md) |
| Liquidity | Order-book depth as a surface over price and time | [liquidity/](liquidity/README.md) |

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
