"""Exploratory ETF sell-off reversal. Read the adjacent specification before results.

Uses tda Python. Gross returns only. Close-conditioned same-close fills are optimistic.
"""
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', '/tmp/tda-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix('')
DATA = ROOT / 'market_data/datasets'
CONTEXT = DATA / 'mean_reversion_context_2026-11-04'
PERIODS = {'full': ('2016-01-04', '2026-10-27'),
           '2016-2019': ('2016-01-04', '2019-12-31'),
           '2020-2026': ('2020-01-01', '2026-10-27')}
MODES = ['ideal_close', 'delay_entry', 'causal_open', 'overnight_only']


def load_bars(symbol, adjustment='all'):
    path = (CONTEXT if symbol == 'QQQ' else DATA / 'equity_daily_expanded_2016_2026-10-27') / f'bars_{adjustment}.csv'
    frame = pd.read_csv(path)
    frame = frame.loc[frame.symbol == symbol].set_index('date').sort_index()
    assert len(frame) == 2720 and frame.index.is_unique
    return frame


def signals(frame, lookback=20, threshold=1.5, consecutive=False):
    ret = frame.c.pct_change(fill_method=None)
    vol = ret.rolling(lookback, min_periods=lookback).std(ddof=1).shift(1)
    z = (frame.c / frame.c.shift(3) - 1) / (np.sqrt(3) * vol)
    signal = z.le(-threshold)
    if consecutive:
        signal &= ret.lt(0).rolling(3).sum().eq(3)
    return signal.to_numpy(), z, vol


def simulate(frame, signal, mode='ideal_close', start=0, end=None):
    """One position; fixed shares during each trade; full capital reinvested at entry.

    Signal t is consumed only while flat. Same-close exits are intentionally labelled
    optimistic. An unexited last trade is marked to final close and marked incomplete.
    """
    end = len(frame) - 1 if end is None else end
    c, o = frame.c.to_numpy(), frame.o.to_numpy()
    up = c > np.r_[np.nan, c[:-1]]
    daily, active = np.zeros(len(frame)), np.zeros(len(frame), dtype=bool)
    records = []
    t = start
    while t <= end:
        if not signal[t] or (mode != 'ideal_close' and t == end):
            t += 1
            continue
        entry_open = mode in ['delay_entry', 'causal_open']
        s = t + int(entry_open)
        if mode == 'overnight_only':
            j, e, exit_open, complete = t + 1, t + 1, True, True
        else:
            ups = np.flatnonzero(up[t+1:end+1])
            j = t + 1 + int(ups[0]) if len(ups) else end
            e = j + int(mode == 'causal_open')
            complete = bool(len(ups)) and e <= end
            if not complete:
                e = end
            exit_open = mode == 'causal_open' and complete
        entry = o[s] if entry_open else c[s]
        exit_price = o[e] if exit_open else c[e]
        previous = entry
        first_day = s if entry_open else s + 1
        for k in range(first_day, e + 1):
            mark = o[k] if exit_open and k == e else c[k]
            daily[k] = mark / previous - 1
            active[k] = True
            previous = mark
        value = exit_price / entry - 1
        if first_day <= e:
            assert np.isclose(np.prod(1 + daily[first_day:e+1]) - 1, value)
        # Exact log attribution: first gap is absent when entry is at next open.
        gap_log = 0.0
        for k in range(t + 1, e + 1):
            if entry_open and k == s:
                continue
            gap_log += np.log(o[k] / c[k-1])
        total_log = np.log(exit_price / entry)
        records.append(dict(signal_i=t, entry_i=s, exit_i=e, signal_date=frame.index[t],
                            entry_date=frame.index[s], exit_date=frame.index[e],
                            entry_price=entry, exit_price=exit_price, complete=complete,
                            return_gross=value, hold_sessions=max(1, e-s+int(entry_open and not exit_open)),
                            overnight_log=gap_log, intraday_log=total_log-gap_log))
        t = e + 1
    return pd.DataFrame(records), daily[start:end+1], active[start:end+1]


def metrics(trades, daily, active):
    done = trades.loc[trades.complete] if len(trades) else trades
    values = done.return_gross.to_numpy() if len(done) else np.array([])
    curve = np.r_[1., np.cumprod(1 + daily)]
    std = values.std(ddof=1) if len(values) > 1 else np.nan
    return dict(trades=len(values), censored=len(trades)-len(values),
                win_rate=float(np.mean(values > 0)) if len(values) else np.nan,
                mean_trade_bps=float(values.mean()*1e4) if len(values) else np.nan,
                median_trade_bps=float(np.median(values)*1e4) if len(values) else np.nan,
                trade_t_descriptive=float(values.mean()/std*np.sqrt(len(values))) if std > 0 else np.nan,
                mean_hold=float(done.hold_sessions.mean()) if len(done) else np.nan,
                worst_trade_pct=float(values.min()*100) if len(values) else np.nan,
                best_trade_pct=float(values.max()*100) if len(values) else np.nan,
                total_return_pct=float((curve[-1]-1)*100),
                cagr_pct=float((curve[-1]**(252/len(daily))-1)*100),
                max_drawdown_pct=float((curve/np.maximum.accumulate(curve)-1).min()*100),
                exposure_fraction=float(active.mean()), daily_mean_bps=float(daily.mean()*1e4))


def block_trade_ci(trades, start, end, block, seed):
    rng = np.random.default_rng(seed)
    n = end-start+1
    sums, counts = np.zeros(n), np.zeros(n)
    for row in trades.itertuples():
        if row.complete:
            sums[row.signal_i-start] = row.return_gross
            counts[row.signal_i-start] = 1
    means = []
    for _ in range(2000):
        starts = rng.integers(0, n, size=int(np.ceil(n/block)))
        ix = ((starts[:, None] + np.arange(block)) % n).ravel()[:n]
        if counts[ix].sum():
            means.append(sums[ix].sum()/counts[ix].sum()*1e4)
    return np.percentile(means, [2.5, 97.5]).tolist()


def main():
    OUT.mkdir(exist_ok=True)
    summaries, ledgers, curves, annual, sensitivity, controls, attribution, vix_rows = [], [], [], [], [], [], [], []
    vix = pd.read_csv(CONTEXT / 'vix_daily.csv').set_index('date').close
    for symbol in ['QQQ', 'SPY']:
        frame = load_bars(symbol)
        signal, z, vol = signals(frame)
        vix_previous = vix.reindex(frame.index).shift(1)
        features = pd.DataFrame({'date': frame.index, 'z3': z.values, 'realized_vol20_annual_pct': vol.values*np.sqrt(252)*100,
                                 'vix_previous_session': vix_previous.values, 'signal': signal})
        features.to_csv(OUT / f'{symbol.lower()}_features.csv', index=False)
        for period, (lo, hi) in PERIODS.items():
            ids = np.flatnonzero((frame.index >= lo) & (frame.index <= hi))
            a, b = int(ids[0]), int(ids[-1])
            for mode in MODES:
                trades, daily, active = simulate(frame, signal, mode, a, b)
                stat = metrics(trades, daily, active)
                stat.update(symbol=symbol, period=period, mode=mode)
                if mode in ['ideal_close', 'causal_open']:
                    for block in [20, 60]:
                        low, high = block_trade_ci(trades, a, b, block, seed=104+block)
                        stat[f'ci{block}_low_bps'], stat[f'ci{block}_high_bps'] = low, high
                summaries.append(stat)
                if len(trades):
                    ledgers.append(trades.assign(symbol=symbol, period=period, mode=mode))
                if period == 'full':
                    curves.append(pd.DataFrame(dict(date=frame.index, symbol=symbol, mode=mode,
                                                    return_gross=daily, equity=np.cumprod(1+daily), active=active)))
                    yearly = pd.Series(daily, index=pd.to_datetime(frame.index)).groupby(lambda d: d.year).apply(lambda s: np.prod(1+s)-1)
                    annual.extend(dict(symbol=symbol, mode=mode, year=int(year), calendar_return_pct=float(value*100)) for year, value in yearly.items())
                if mode == 'ideal_close':
                    done = trades.loc[trades.complete]
                    attribution.append(dict(symbol=symbol, period=period, trades=len(done),
                        mean_total_log_bps=float((done.overnight_log+done.intraday_log).mean()*1e4),
                        mean_overnight_log_bps=float(done.overnight_log.mean()*1e4),
                        mean_intraday_log_bps=float(done.intraday_log.mean()*1e4)))
                    for label, lower, upper in [('below20', 0, 20), ('20to30', 20, 30), ('30plus', 30, np.inf)]:
                        values = done.loc[done.signal_i.map(lambda i: lower <= vix_previous.iloc[i] < upper), 'return_gross']
                        vix_rows.append(dict(symbol=symbol, period=period, vix_bin=label, trades=len(values),
                            mean_trade_bps=values.mean()*1e4, win_rate=(values>0).mean()))
            # Identical first-up exit without requiring a decline; high wins alone are not evidence.
            eligible = vol.notna().to_numpy()
            trades, daily, active = simulate(frame, eligible, 'ideal_close', a, b)
            controls.append(dict(symbol=symbol, period=period, control='always_enter_first_up_exit', **metrics(trades, daily, active)))
            ideal_trades, ideal_daily, _ = simulate(frame, signal, 'ideal_close', a, b)
            shifted_means = []
            local_signal = signal[a:b+1]
            for shift in range(21, len(local_signal)-20):
                shifted = np.zeros(len(signal), dtype=bool)
                shifted[a:b+1] = np.roll(local_signal, shift)
                _, rd, _ = simulate(frame, shifted, 'ideal_close', a, b)
                shifted_means.append(rd.mean()*1e4)
            controls.append(dict(symbol=symbol, period=period, control='signal_circular_shift',
                shifts=len(shifted_means), daily_mean_bps=ideal_daily.mean()*1e4,
                shift_median_bps=float(np.median(shifted_means)),
                shift_p95_bps=float(np.percentile(shifted_means, 95)),
                fraction_shifts_ge_observed=float(np.mean(np.array(shifted_means) >= ideal_daily.mean()*1e4))))
            # Fixed one-session response does not condition the exit on a subsequent up day.
            next_cc = frame.c.shift(-1)/frame.c-1
            next_gap = frame.o.shift(-1)/frame.c-1
            next_day = frame.c.shift(-1)/frame.o.shift(-1)-1
            for label, mask in [('selloff', signal), ('all_eligible', eligible)]:
                valid = mask.copy()
                valid[:a] = False
                valid[b:] = False
                controls.append(dict(symbol=symbol, period=period, control=f'fixed_one_day_{label}',
                    observations=int(valid.sum()), close_close_bps=next_cc[valid].mean()*1e4,
                    overnight_bps=next_gap[valid].mean()*1e4, intraday_bps=next_day[valid].mean()*1e4))
            for lookback in [10, 20, 60]:
                for threshold in [1., 1.5, 2.]:
                    for consecutive in [False, True]:
                        sig, _, _ = signals(frame, lookback, threshold, consecutive)
                        tr, dr, act = simulate(frame, sig, 'ideal_close', a, b)
                        sensitivity.append(dict(symbol=symbol, period=period, adjustment='all', lookback=lookback,
                            threshold=threshold, consecutive=consecutive, **metrics(tr, dr, act)))
            raw = load_bars(symbol, 'raw')
            raw_sig, _, _ = signals(raw)
            tr, dr, act = simulate(raw, raw_sig, 'ideal_close', a, b)
            sensitivity.append(dict(symbol=symbol, period=period, adjustment='raw', lookback=20,
                                    threshold=1.5, consecutive=False, **metrics(tr, dr, act)))
            bh = np.zeros(b-a+1)
            bh[1:] = frame.c.iloc[a+1:b+1].values/frame.c.iloc[a:b].values-1
            controls.append(dict(symbol=symbol, period=period, control='buy_hold_adjusted_proxy',
                total_return_pct=(np.prod(1+bh)-1)*100, cagr_pct=(np.prod(1+bh)**(252/len(bh))-1)*100,
                max_drawdown_pct=(np.r_[1,np.cumprod(1+bh)]/np.maximum.accumulate(np.r_[1,np.cumprod(1+bh)])-1).min()*100))
    for name, rows in [('summary', summaries), ('annual_returns', annual), ('sensitivity', sensitivity),
                       ('controls', controls), ('timing_attribution', attribution), ('vix_context', vix_rows)]:
        pd.DataFrame(rows).to_csv(OUT / f'{name}.csv', index=False)
    pd.concat(ledgers, ignore_index=True).to_csv(OUT / 'trades.csv', index=False)
    curve_frame = pd.concat(curves, ignore_index=True)
    curve_frame.to_csv(OUT / 'daily_curves.csv', index=False)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for i, symbol in enumerate(['QQQ', 'SPY']):
        for mode in MODES:
            part = curve_frame.loc[(curve_frame.symbol == symbol) & (curve_frame['mode'] == mode)]
            dates = pd.to_datetime(part.date)
            axes[i,0].plot(dates, part.equity, label=mode.replace('_', ' '), linewidth=1.1)
            axes[i,1].plot(dates, 100*(part.equity/part.equity.cummax()-1), linewidth=1.)
        axes[i,0].set_title(f'{symbol}: gross $1 sleeve, cash earns zero')
        axes[i,1].set_title(f'{symbol}: drawdown (%)')
        axes[i,0].legend(fontsize=8)
        for ax in axes[i]:
            ax.grid(alpha=.2)
    fig.suptitle('Three-day sell-off reversal: timing sensitivity (2016–Oct 2026)\nExploratory daily-bar proxies; same-close fills optimistic; no fees')
    fig.savefig(OUT / 'timing_and_drawdown.png', dpi=160)
    plt.close(fig)
    files = [Path(__file__), OUT / 'specification.json', CONTEXT / 'manifest.json',
             DATA / 'equity_daily_expanded_2016_2026-10-27/bars_all.csv',
             DATA / 'equity_daily_expanded_2016_2026-10-27/bars_raw.csv']
    files += sorted(OUT.glob('*.csv'))
    (OUT / 'run_manifest.json').write_text(json.dumps({
        'seed': 104, 'bootstrap_draws': 2000, 'fees': 'gross only',
        'sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    }, indent=2)+'\n')
    print(pd.DataFrame(summaries).loc[lambda d: (d.period == '2020-2026'),
          ['symbol','mode','trades','win_rate','mean_trade_bps','mean_hold','cagr_pct','ci20_low_bps','ci20_high_bps']].to_string(index=False))


if __name__ == '__main__':
    main()
