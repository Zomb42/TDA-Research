"""Describe capital and passive benchmarks using frozen sell-off results; tda Python.

No strategy refit or new download. Cash earns zero. Passive risk matching uses full-
sample realized volatility and is a hindsight diagnostic, not an investable forecast.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_name('index_selloff_reversal')


def describe(returns):
    wealth = np.r_[1., np.cumprod(1+returns)]
    sigma = np.std(returns, ddof=1)
    return dict(starting_capital=100000., ending_capital=100000*wealth[-1],
                total_return_pct=100*(wealth[-1]-1),
                cagr_pct=100*(wealth[-1]**(252/len(returns))-1),
                annualized_daily_vol_pct=100*sigma*np.sqrt(252),
                sharpe_vs_zero=np.mean(returns)/sigma*np.sqrt(252),
                max_daily_close_drawdown_pct=100*(wealth/np.maximum.accumulate(wealth)-1).min())


def main():
    curves = pd.read_csv(OUT / 'daily_curves.csv')
    summary = pd.read_csv(OUT / 'summary.csv')
    prices = pd.read_csv(ROOT / 'market_data/datasets/equity_daily_expanded_2016_2026-10-27/close_all.csv', index_col='date')
    qqq = pd.read_csv(ROOT / 'market_data/datasets/mean_reversion_context_2026-11-04/bars_all.csv', index_col='date').c
    passive = {'SPY': prices.SPY.pct_change(fill_method=None).fillna(0).to_numpy(),
               'QQQ': qqq.pct_change(fill_method=None).fillna(0).to_numpy()}
    rows, matched = [], []
    for symbol in ['SPY', 'QQQ']:
        rows.append(dict(symbol=symbol, policy='buy_hold', fraction_sessions_exposed=1.,
                         fraction_account_invested_when_active=1., **describe(passive[symbol])))
        for mode in ['ideal_close', 'causal_open']:
            part = curves.loc[(curves.symbol == symbol) & (curves['mode'] == mode)]
            assert part.date.tolist() == prices.index.tolist()
            returns = part.return_gross.to_numpy()
            metrics = describe(returns)
            frozen = summary.loc[(summary.symbol == symbol) & (summary.period == 'full') & (summary['mode'] == mode)].iloc[0]
            assert np.isclose(metrics['cagr_pct'], frozen.cagr_pct)
            assert np.isclose(metrics['total_return_pct'], frozen.total_return_pct)
            assert np.isclose(metrics['max_daily_close_drawdown_pct'], frozen.max_drawdown_pct)
            rows.append(dict(symbol=symbol, policy=mode, fraction_sessions_exposed=part.active.mean(),
                             fraction_account_invested_when_active=1., **metrics))
            weight = np.std(returns, ddof=1)/np.std(passive['SPY'], ddof=1)
            benchmark = weight*passive['SPY']
            assert np.isclose(np.std(benchmark, ddof=1), np.std(returns, ddof=1))
            matched.append(dict(target_symbol=symbol, target_policy=mode,
                benchmark='daily_rebalanced_SPY_plus_zero_return_cash',
                weight_SPY=weight, weight_cash=1-weight,
                calibration='hindsight_full_period_realized_daily_volatility', **describe(benchmark)))
    pd.DataFrame(rows).to_csv(OUT / 'capital_comparison.csv', index=False)
    pd.DataFrame(matched).to_csv(OUT / 'passive_risk_comparison.csv', index=False)
    print(pd.DataFrame(rows).round(4).to_string(index=False))
    print(pd.DataFrame(matched).round(4).to_string(index=False))


if __name__ == '__main__':
    main()
