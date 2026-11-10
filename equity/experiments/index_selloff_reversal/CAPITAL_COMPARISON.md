# Capital commitment and buy-and-hold comparison

November 4, 2026 follow-up using the frozen experiment's **full January 4, 2016–October 27, 2026** calendar. This comparison adds no new strategy fit, parameter choice or download. It evaluates our specified approximation, not the author's unavailable full strategy.

**The SPY implementation does not establish an advantage over holding the S&P 500.** The ideal-close QQQ result is more interesting relative to its daily volatility, but that advantage depends on optimistic timing and does not survive the causal next-open comparison convincingly.

## Same starting account

Every row starts with **$100,000**, reinvests gains, takes no leverage, and uses all account equity whenever invested. Cash earns zero. Results are gross/pre-fee and use adjusted-price proxies. “Drawdown” means the largest peak-to-trough decline in the daily marked account, not the worst intraday loss.

| Policy | Ending account | Annualized return | Annualized daily volatility | Maximum drawdown | Sessions exposed |
|---|---:|---:|---:|---:|---:|
| Hold SPY | $450,937 | 14.97% | 17.42% | 33.79% | 100% |
| SPY sell-off, ideal close decisions | $159,940 | 4.45% | 7.52% | 12.80% | 6.47% |
| SPY sell-off, both decisions next open | $95,939 | −0.38% | 6.97% | 24.05% | 9.04% |
| Hold QQQ | $712,909 | 19.96% | 22.21% | 35.00% | 100% |
| QQQ sell-off, ideal close decisions | $249,742 | 8.85% | 7.91% | 6.72% | 6.51% |
| QQQ sell-off, both decisions next open | $142,235 | 3.32% | 6.47% | 14.41% | 9.63% |

The ideal-close decisions consume a closing price and assume a fill at that price; those fills are not established from daily bars. The causal versions wait for the next open after observing each decision. Trading occupancy and counts consequently differ. The [main report](README.md) explains timing, pointwise uncertainty and the approximate strategy specification.

## What capital is actually committed?

Capital is invested and recovered, rather than consumed anew every trade. With a $100,000 account, the first signal uses approximately **$100,000 of ETF exposure**. After an exit the account is cash; the next signal invests the then-current full account again. Returns in the table are on the **whole starting account**, including flat periods, not a return percentage calculated only while trading.

About 6.5% of sessions exposed does **not** mean $6,500 is sufficient to reproduce the $100,000 account. It describes how often the full position is present. The active-session indicator is a daily observation convention, not a measurement of exact minutes of capital use. There is no assumed margin or reduced capital requirement.

Idle funds could earn a cash yield or support other strategies, but neither benefit has been measured here. Deploying those funds elsewhere also requires accounting for coincident signals, available liquidity and total portfolio risk. Holding SPY already with the entire account and adding a full-account rebound position would require reducing that holding or adding capital/leverage; the extra return cannot simply be added to buy-and-hold at no exposure cost. Dividing CAGR by the active-session fraction is not an investable annual return or a valid leverage calculation.

## A passive comparison with similar measured volatility

Lower stock exposure naturally changes both return and risk. As a descriptive check, take the **whole-period observed daily volatility** of each strategy and choose a daily rebalanced SPY/cash allocation with that same volatility. This calibration uses hindsight, earns zero on cash, assumes no rebalance costs, and is not a proposed deployable allocation rule. Equal full-period volatility does not equate tail, conditional or liquidity risk.

| Strategy being matched | Matching SPY / cash weights | Passive annual return | Strategy annual return | Passive / strategy drawdown |
|---|---:|---:|---:|---:|
| SPY ideal close | 43.20% / 56.80% | 6.61% | 4.45% | 15.78% / 12.80% |
| SPY next open | 40.02% / 59.98% | 6.13% | −0.38% | 14.68% / 24.05% |
| QQQ ideal close | 45.44% / 54.56% | 6.95% | 8.85% | 16.54% / 6.72% |
| QQQ next open | 37.16% / 62.84% | 5.70% | 3.32% | 13.68% / 14.41% |

The SPY ideal-close rule has lower drawdown than its volatility-matched passive comparison, but earns less; it does not dominate on both dimensions. The QQQ ideal-close rule has a favorable point comparison on both. Once both decisions wait for the next open, neither strategy exceeds the passive comparator's full-period CAGR, and both have larger observed maximum drawdowns. This weakens the case for an executable capital-allocation advantage. The QQQ-versus-SPY comparison also changes the underlying market exposure, rather than isolating timing within one index; its own buy-and-hold row is therefore retained above.

The rebound observation can still be meaningful as a hypothesis about conditional returns. A high win rate or a large per-trade mean does not by itself establish superiority to a simple portfolio. The unresolved question is whether an implementable version adds return or reduces risk **after controlling for the capital and risks it actually uses**.

## Reproduction

```sh
conda run --no-capture-output -n tda python equity/experiments/index_selloff_capital_comparison.py
```

Source: [comparison script](../index_selloff_capital_comparison.py). Tables: [capital comparison](capital_comparison.csv), [passive risk comparison](passive_risk_comparison.csv). The script consumes frozen daily curves and source prices, verifies strategy CAGRs/total returns/drawdowns against the saved summary, and checks that each passive blend matches its target daily volatility. The original run manifest and source remain unchanged; these are separate follow-up artifacts.
