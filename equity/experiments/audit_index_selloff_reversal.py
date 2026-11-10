"""Independent scalar ledger reconstruction and timing fixtures; run with tda."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from index_selloff_reversal import OUT, PERIODS, MODES, load_bars, signals, simulate


def scalar_ledger(frame, signal, mode, a, b):
    rows = []
    blocked_through = a - 1
    for t in range(a, b+1):
        if t <= blocked_through or not signal[t] or (mode != 'ideal_close' and t == b):
            continue
        s = t + int(mode in ['delay_entry', 'causal_open'])
        entry_price = frame.o.iloc[s] if mode in ['delay_entry', 'causal_open'] else frame.c.iloc[s]
        up_date = None
        for u in range(t+1, b+1):
            if frame.c.iloc[u] > frame.c.iloc[u-1]:
                up_date = u
                break
        if mode == 'overnight_only':
            e, complete, price = t+1, True, frame.o.iloc[t+1]
        else:
            proposed = up_date + int(mode == 'causal_open') if up_date is not None else b+1
            complete = proposed <= b
            e = min(proposed, b)
            price = frame.o.iloc[e] if mode == 'causal_open' and complete else frame.c.iloc[e]
        rows.append((t, s, e, complete, price/entry_price-1))
        blocked_through = e
    return rows


def main():
    # A down day followed by a small up day can still lose overall.
    fixture = pd.DataFrame({'c': [100., 95., 96., 97.], 'o': [100., 98., 94., 96.]},
                           index=['a','b','c','d'])
    sig = np.array([True, False, False, False])
    expected = {'ideal_close': -.04, 'delay_entry': 96/98-1,
                'causal_open': 96/98-1, 'overnight_only': -.02}
    for mode, value in expected.items():
        tr, daily, _ = simulate(fixture, sig, mode)
        assert len(tr) == 1 and np.isclose(tr.return_gross.iloc[0], value)
        assert np.isclose(np.prod(1+daily)-1, value)
    # Missing first up day remains a censored marked position, never an invented exit.
    falling = fixture.copy()
    falling['c'] = [100., 99., 98., 97.]
    for mode in ['ideal_close', 'delay_entry', 'causal_open']:
        tr, _, _ = simulate(falling, sig, mode)
        assert not tr.complete.iloc[0] and tr.exit_i.iloc[0] == 3
    ledgers = pd.read_csv(OUT / 'trades.csv')
    curves = pd.read_csv(OUT / 'daily_curves.csv')
    checked_trades = 0
    for symbol in ['QQQ', 'SPY']:
        frame = load_bars(symbol)
        ret = frame.c.pct_change(fill_method=None)
        manual = np.full(len(frame), False)
        for t in range(21, len(frame)):
            sigma = np.std(ret.iloc[t-20:t].values, ddof=1)
            manual[t] = (frame.c.iloc[t]/frame.c.iloc[t-3]-1) <= -1.5*np.sqrt(3)*sigma
        sig, _, _ = signals(frame)
        assert np.array_equal(sig, manual)
        # Changing future prices cannot change an earlier signal.
        changed = frame.copy()
        changed.loc[changed.index[1500:], 'c'] *= 1.7
        assert np.array_equal(signals(changed)[0][:1500], sig[:1500])
        for period, (lo, hi) in PERIODS.items():
            ix = np.flatnonzero((frame.index >= lo) & (frame.index <= hi))
            a, b = int(ix[0]), int(ix[-1])
            for mode in MODES:
                expected_rows = scalar_ledger(frame, manual, mode, a, b)
                actual = ledgers.loc[(ledgers.symbol == symbol) & (ledgers.period == period) & (ledgers['mode'] == mode)]
                assert len(actual) == len(expected_rows)
                for row, (t, s, e, complete, value) in zip(actual.itertuples(), expected_rows):
                    assert (row.signal_i, row.entry_i, row.exit_i, row.complete) == (t,s,e,complete)
                    assert np.isclose(row.return_gross, value, atol=1e-12)
                if period == 'full':
                    part = curves.loc[(curves.symbol == symbol) & (curves['mode'] == mode)]
                    ledger_value = np.prod([1+r[4] for r in expected_rows])
                    assert np.isclose(part.equity.iloc[-1], ledger_value, atol=1e-12)
                    assert np.allclose(part.equity, np.cumprod(1+part.return_gross), atol=1e-12)
                checked_trades += len(actual)
        features = pd.read_csv(OUT / f'{symbol.lower()}_features.csv')
        source = pd.read_csv(OUT.parents[2] / 'market_data/datasets/mean_reversion_context_2026-11-04/vix_daily.csv').set_index('date').close
        assert np.allclose(features.vix_previous_session, source.reindex(frame.index).shift(1), equal_nan=True)
    report = dict(passed=True, ledger_rows_checked=checked_trades, checks=[
        'hand-calculated timing cases', 'right-censored last positions',
        'independent scalar volatility/signal computation', 'future-price perturbation',
        'independent first-up exit and blocking reconstruction, all periods/modes',
        'trade wealth equals marked daily wealth', 'lagged VIX alignment'])
    (OUT / 'audit.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
