"""Frozen first Kalshi-perp return forecast pilot. Offline; use conda tda."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/tda-btc-predict-mpl')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from ripser import ripser
from sklearn.linear_model import Ridge

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix('')
SPEC = json.loads((OUT/'specification.json').read_text())
ORDINARY = SPEC['ordinary_features'] + ['ret60_x_std', 'ret60_x_acf', 'ret60_x_spectrum']
TDA = SPEC['tda_features']
INTERACTIONS = ['ret60_x_'+k for k in TDA]
MODELS = {'Ordinary18': ORDINARY, 'OrdinaryPlusTDA21': ORDINARY+TDA,
          'OrdinaryPlusTDAInteractions24': ORDINARY+TDA+INTERACTIONS}


def save_json(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stamp(value):
    return pd.Timestamp(value).value


def book_features(row, contract):
    book = row['book']
    bid = np.array(book['bid'], dtype=float)
    ask = np.array(book['ask'], dtype=float)
    best_bid, best_ask = bid[:, 0].max(), ask[:, 0].min()
    mid = (best_bid+best_ask)/2
    near = [float(np.sum(v[np.abs(v[:, 0]/mid-1) <= .001, 0] *
                         v[np.abs(v[:, 0]/mid-1) <= .001, 1])) for v in (bid, ask)]
    return dict(timestamp=stamp(row['received_at']), epoch=row['epoch'],
                mid=mid/contract, spread_bps=(best_ask-best_bid)/mid*10000,
                depth10_imbalance=(near[0]-near[1])/sum(near) if sum(near) else 0,
                valid=best_bid > 0 and best_ask > best_bid and book['ready'])


def extract():
    assert sha(ROOT/SPEC['metadata']) == SPEC['metadata_sha256']
    meta = json.loads((ROOT/SPEC['metadata']).read_text())['market']
    assert float(meta['underlying_multiplier']) == 1
    contract = float(meta['contract_size'])
    books, refs, trades, controls, validation = [], [], [], [], []
    for item in SPEC['inputs']:
        path = ROOT/item['path']
        assert sha(path) == item['sha256']
        n = 0
        with gzip.open(path, 'rt') as stream:
            for line in stream:
                n += 1
                if item['source'] == 'kalshi_perp' and not ('"control":' in line or '"type":"trade"' in line):
                    continue
                row = json.loads(line)
                control = row.get('control')
                if control in ('gap_start','gap_end','sequence_gap','trade_sequence_gap','book_invalid'):
                    controls.append(dict(source=item['source'], **row))
                if item['source'] == 'kalshi_perp':
                    if control == 'book_checkpoint':
                        books.append(book_features(row, contract))
                    event = row.get('message', {})
                    if event.get('type') == 'trade':
                        msg = event['msg']; side = msg['taker_side']
                        assert side in ('bid','ask')
                        usd = float(msg['count'])*float(msg['price'])
                        trades.append(dict(timestamp=stamp(row['received_at']), trade_id=msg['trade_id'],
                                           usd=usd, signed_usd=usd*(1 if side == 'bid' else -1)))
                elif row.get('type') == 'reference_sample':
                    quote = row.get('quote') or {}
                    refs.append(dict(timestamp=stamp(row['sampled_at']), epoch=row['epoch'],
                                     spot=float(row.get('midpoint', 'nan')),
                                     quote_age_ms=row.get('quote_age_ms', np.nan),
                                     valid=bool(row['connected'] and quote and not row.get('crossed_or_locked',True))))
        assert n == item['rows'], (path, n, item['rows'])
        validation.append(dict(**item, actual_rows=n, gzip_crc_passed=True, sha256_passed=True))
        print('Extracted', item['source'], path.name, n, flush=True)
    book = pd.DataFrame(books).sort_values('timestamp').drop_duplicates('timestamp')
    ref = pd.DataFrame(refs).sort_values('timestamp').drop_duplicates('timestamp')
    trade = pd.DataFrame(trades).sort_values('timestamp')
    duplicates = int(trade.trade_id.duplicated().sum())
    trade = trade.drop_duplicates('trade_id').reset_index(drop=True)
    book.to_parquet(OUT/'book_checkpoints.parquet', index=False)
    ref.to_parquet(OUT/'reference_samples.parquet', index=False)
    trade.to_parquet(OUT/'trades.parquet', index=False)
    save_json('source_controls.json', controls)
    save_json('input_validation.json', dict(files=validation, duplicate_trades_removed=duplicates,
                                          checkpoints=len(book), reference_samples=len(ref), trades=len(trade)))


def align():
    book = pd.read_parquet(OUT/'book_checkpoints.parquet')
    ref = pd.read_parquet(OUT/'reference_samples.parquet')
    trade = pd.read_parquet(OUT/'trades.parquet')
    step = 5_000_000_000
    lo = max(book.timestamp.min(), ref.timestamp.min())
    hi = min(book.timestamp.max(), ref.timestamp.max())
    clock = np.arange((lo+step-1)//step*step, hi//step*step+1, step, dtype=np.int64)
    grid = pd.DataFrame({'timestamp': clock})
    for frame, prefix, tolerance in [(book,'perp',7.5e9),(ref,'ref',1e9)]:
        renamed = frame.rename(columns={'timestamp':prefix+'_observed_at', 'epoch':prefix+'_epoch', 'valid':prefix+'_valid'})
        grid = pd.merge_asof(grid,renamed,left_on='timestamp',right_on=prefix+'_observed_at',direction='backward',tolerance=int(tolerance))
    grid['perp_age_s'] = (grid.timestamp-grid.perp_observed_at)/1e9
    grid['ref_age_s'] = (grid.timestamp-grid.ref_observed_at)/1e9
    grid['ref_total_quote_age_s'] = grid.ref_age_s+grid.quote_age_ms/1000
    grid['valid'] = (grid.perp_valid.eq(True) & grid.ref_valid.eq(True) &
                     grid.ref_total_quote_age_s.le(2) & grid.mid.gt(0) & grid.spot.gt(0))
    controls = json.loads((OUT/'source_controls.json').read_text())
    pending = {}
    for row in sorted(controls, key=lambda r: r['received_at']):
        t = stamp(row['received_at']); src = row['source']
        if row['control'] == 'gap_start':
            pending[src] = min(pending.get(src,t),t)
        elif row['control'] == 'gap_end':
            start = pending.pop(src, stamp(row.get('gap_started_at',row['received_at'])))
            grid.loc[grid.timestamp.between(start,t),'valid'] = False
        else:
            grid.loc[grid.timestamp.between(t,t+step),'valid'] = False
    for start in pending.values():
        grid.loc[grid.timestamp.ge(start),'valid'] = False
    tt = trade.timestamp.to_numpy()
    cumulative = np.r_[0., np.cumsum(trade.usd)]
    signed = np.r_[0., np.cumsum(trade.signed_usd)]
    right = np.searchsorted(tt, clock, side='right')
    left = np.searchsorted(tt, clock-60_000_000_000, side='right')
    total = cumulative[right]-cumulative[left]
    net = signed[right]-signed[left]
    grid['trade_usd60'] = total
    grid['trade_count60'] = right-left
    grid['taker_bid_minus_ask60'] = np.divide(net,total,out=np.zeros(len(total)),where=total>0)
    grid.to_parquet(OUT/'aligned_5s.parquet', index=False)
    return grid


def topo(x):
    scale = np.std(x)
    z = (x-np.mean(x))/scale if scale > 1e-12 else np.zeros_like(x)
    cloud = np.column_stack([z[4:],z[2:-2],z[:-4]])
    diagrams = ripser(cloud, maxdim=1)['dgms']
    d0 = diagrams[0][np.isfinite(diagrams[0][:,1]),1]
    finite = diagrams[1][np.isfinite(diagrams[1][:,1])]
    life = finite[:,1]-finite[:,0]
    return np.array([np.quantile(d0,.9) if len(d0) else 0,
                     life.max() if len(life) else 0, life@life]), cloud


def build_features():
    grid = align(); rows = []; exclusions = Counter()
    mid, spot = grid.mid.to_numpy(), grid.spot.to_numpy()
    valid = grid.valid.to_numpy()
    times = grid.timestamp.to_numpy()
    for i in np.flatnonzero(times % 60_000_000_000 == 0):
        if i < 120 or i+12 >= len(grid):
            exclusions['incomplete_window_or_label'] += 1; continue
        sl = slice(i-120,i+13)
        if not valid[sl].all():
            exclusions['missing_stale_or_gap'] += 1; continue
        if grid.perp_epoch.iloc[sl].nunique() != 1 or grid.ref_epoch.iloc[sl].nunique() != 1:
            exclusions['connection_epoch_change'] += 1; continue
        x = np.diff(np.log(mid[i-120:i+1]))*10000
        xc = x-x.mean(); denom = xc@xc
        power = np.abs(np.fft.rfft(xc))**2; power[0] = 0
        prob = power[power>0]/power.sum() if power.sum() else np.array([])
        td, _ = topo(x)
        ret60 = float(np.log(mid[i]/mid[i-12])*10000)
        row = dict(row_id=len(rows), grid_index=int(i), timestamp=int(times[i]),
                   decision_utc=pd.Timestamp(times[i],tz='UTC').isoformat(),
                   label_end_ns=int(times[i+12]), label_end_utc=pd.Timestamp(times[i+12],tz='UTC').isoformat(),
                   feature_start_ns=int(times[i-120]),
                   signed_bps=float(np.log(mid[i+12]/mid[i])*10000),
                   ret5_bps=float(x[-1]), ret30_bps=float(x[-6:].sum()),ret60_bps=ret60,
                   ret600_bps=float(x.sum()),std600_bps=float(x.std()),
                   acf1=float(xc[:-1]@xc[1:]/denom) if denom else 0,
                   spectral_max_share=float(power.max()/power.sum()) if power.sum() else 0,
                   spectral_entropy=float(-np.sum(prob*np.log(prob))) if len(prob) else 0,
                   spread_bps=float(grid.spread_bps.iloc[i]),depth10_imbalance=float(grid.depth10_imbalance.iloc[i]),
                   taker_bid_minus_ask60=float(grid.taker_bid_minus_ask60.iloc[i]),
                   log_trade_usd60=float(np.log1p(grid.trade_usd60.iloc[i])),
                   log_trade_count60=float(np.log1p(grid.trade_count60.iloc[i])),
                   spot_ret60_bps=float(np.log(spot[i]/spot[i-12])*10000),
                   basis_bps=float(np.log(mid[i]/spot[i])*10000))
        row.update(dict(zip(TDA,td)))
        row['absolute_bps'] = abs(row['signed_bps'])
        for key in TDA: row['ret60_x_'+key] = ret60*row[key]
        row.update(ret60_x_std=ret60*row['std600_bps'],ret60_x_acf=ret60*row['acf1'],
                   ret60_x_spectrum=ret60*row['spectral_max_share'])
        rows.append(row)
    data = pd.DataFrame(rows)
    assert len(data)>210, 'Insufficient eligible pilot history for frozen180-label warmup'
    assert np.isfinite(data.select_dtypes('number').to_numpy()).all()
    data.to_csv(OUT/'features_and_targets.csv', index=False)
    save_json('eligibility.json',dict(clock_slots=len(grid),valid_clock_slots=int(grid.valid.sum()),
                                    eligible_decisions=len(data),excluded=dict(exclusions),
                                    first=data.decision_utc.iloc[0],last=data.decision_utc.iloc[-1]))
    print('Eligible decisions',len(data),'exclusions',dict(exclusions),flush=True)
    return data


def fit(data):
    forecasts = []; memberships = []; coefficients = []; current = None; next_refit = -1
    ycols = ['signed_bps','absolute_bps']
    for k,row in data.iterrows():
        train = data.loc[data.label_end_ns.le(row.timestamp) & data.timestamp.lt(row.timestamp)]
        if len(train)<180: continue
        if current is None or k>=next_refit:
            fit_id = len(memberships); next_refit=k+30
            ids = train.row_id.astype(int).tolist()
            memberships.append(dict(fit_id=fit_id,decision_utc=row.decision_utc,decision_ns=int(row.timestamp),
                                    n_train=len(train),max_label_end_ns=int(train.label_end_ns.max()),train_row_ids=ids))
            current = {}
            for model,cols in MODELS.items():
                x = train[cols].to_numpy(); means=x.mean(0); scales=x.std(0); scales[scales<1e-10]=1
                reg = Ridge(alpha=len(train),fit_intercept=True,solver='svd').fit((x-means)/scales,train[ycols].to_numpy())
                current[model]=(means,scales,reg)
                for j,target in enumerate(ycols):
                    for c,mu,sd,beta in zip(cols,means,scales,reg.coef_[j]):
                        coefficients.append(dict(fit_id=fit_id,model=model,target=target,feature=c,mean=mu,scale=sd,
                                                 coefficient=beta,intercept=reg.intercept_[j]))
            hist = train[ycols].mean().to_numpy()
        fit_id = memberships[-1]['fit_id']
        for model in ['Zero','HistoryMean',*MODELS]:
            if model=='Zero': pred=np.zeros(2)
            elif model=='HistoryMean': pred=hist
            else:
                mu,sd,reg=current[model]
                pred=reg.predict(((row[MODELS[model]].to_numpy(dtype=float)-mu)/sd)[None,:])[0]
            for j,target in enumerate(ycols):
                forecasts.append(dict(row_id=int(row.row_id),fit_id=fit_id,decision_utc=row.decision_utc,
                                      timestamp=int(row.timestamp),target=target,model=model,
                                      actual=float(row[target]),prediction=float(pred[j])))
    pred=pd.DataFrame(forecasts)
    pred['squared_error']=(pred.prediction-pred.actual)**2
    pred['absolute_error']=np.abs(pred.prediction-pred.actual)
    pred.to_csv(OUT/'walk_forward_predictions.csv',index=False)
    pd.DataFrame(coefficients).to_csv(OUT/'coefficients.csv',index=False)
    save_json('training_membership.json',memberships)
    return pred


def boot(pred):
    timeline=np.arange(pred.timestamp.min(),pred.timestamp.max()+1,60_000_000_000,dtype=np.int64)
    losses=[]; names=[]; metrics=[]
    for (target,model),g in pred.groupby(['target','model'],sort=False):
        corr=float(g[['actual','prediction']].corr().iloc[0,1]) if g.prediction.std()>0 else None
        nonzero=g.actual.ne(0)
        metrics.append(dict(target=target,model=model,n=len(g),MSE=float(g.squared_error.mean()),
                            MAE=float(g.absolute_error.mean()),correlation=corr,
                            nonzero_actuals=int(nonzero.sum()),
                            direction_accuracy=float((np.sign(g.loc[nonzero,'prediction'])==np.sign(g.loc[nonzero,'actual'])).mean()) if target=='signed_bps' else None))
    for target in ['signed_bps','absolute_bps']:
        p=pred.loc[pred.target.eq(target)].pivot(index='timestamp',columns='model',values='squared_error').reindex(timeline)
        baseline=float(p.Ordinary18.mean())
        for model in ['OrdinaryPlusTDA21','OrdinaryPlusTDAInteractions24']:
            losses.append((p[model]-p.Ordinary18).to_numpy())
            names.append((target,model,baseline))
    loss=np.array(losses).T
    rng=np.random.default_rng(2026110507); n=len(timeline)
    starts=rng.integers(0,n,size=(2000,int(np.ceil(n/60))))
    draws=((starts[:,:,None]+np.arange(60))%n).reshape(2000,-1)[:,:n]
    draws_mean=np.nanmean(loss[draws],axis=1); center=np.nanmean(loss,axis=0)
    sd=draws_mean.std(axis=0,ddof=1); sd=np.maximum(sd,1e-15)
    critical=float(np.quantile(np.max(np.abs((draws_mean-center)/sd),axis=1),.95))
    comparisons=[]
    for j,(target,model,baseline) in enumerate(names):
        low,high=np.quantile(draws_mean[:,j],[.025,.975])
        lo,hi=center[j]-critical*sd[j],center[j]+critical*sd[j]
        comparisons.append(dict(target=target,model=model,comparator='Ordinary18',loss_difference=float(center[j]),
                                reduction_percent=float(-center[j]/baseline*100),point95_low=float(low),point95_high=float(high),
                                simultaneous95_low=float(lo),simultaneous95_high=float(hi),
                                reduction_sim95_low=float(-hi/baseline*100),reduction_sim95_high=float(-lo/baseline*100)))
    pd.DataFrame(metrics).to_csv(OUT/'forecast_metrics.csv',index=False)
    pd.DataFrame(comparisons).to_csv(OUT/'paired_comparisons.csv',index=False)
    np.savez_compressed(OUT/'bootstrap.npz',draws=draws,timeline=timeline,loss_differences=loss,
                        bootstrap_means=draws_mean,center=center,critical=critical)
    return pd.DataFrame(metrics),pd.DataFrame(comparisons)


def plots(data,pred,metrics,comparisons):
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    order=['Zero','HistoryMean',*MODELS]
    for ax,target in zip(axes,['signed_bps','absolute_bps']):
        m=metrics.loc[metrics.target.eq(target)].set_index('model').loc[order]
        ax.bar(np.arange(5),m.MSE,color=['#999999','#cccccc','#406c91','#d9a14b','#2b8c80'])
        ax.set_xticks(np.arange(5),['Zero','History\nmean','Ordinary','+ TDA\nlevels','+ TDA\ninteractions'])
        ax.set(title='Next-minute '+('signed return' if target=='signed_bps' else 'absolute return'),ylabel='Forecast MSE (bps squared); lower is better')
        ax.grid(axis='y',alpha=.2)
    fig.suptitle('Kalshi BTC-perp first chronological prediction pilot\nSame dates; fixed ridge; midpoint targets, no trading policy')
    fig.savefig(OUT/'01_forecast_errors.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    for ax,target in zip(axes,['signed_bps','absolute_bps']):
        c=comparisons.loc[comparisons.target.eq(target)]
        for i,(_,r) in enumerate(c.iterrows()):
            ax.errorbar(r.reduction_percent,i,xerr=[[r.reduction_percent-r.reduction_sim95_low],[r.reduction_sim95_high-r.reduction_percent]],fmt='o',capsize=4,color='#2b8c80')
        ax.axvline(0,color='black',lw=1);ax.set_yticks([0,1],['TDA levels','TDA levels +\nreturn interactions'])
        ax.set(title=target.replace('_bps',''),xlabel='MSE reduction versus ordinary (%)\nPositive favors TDA; simultaneous 95% intervals')
        ax.grid(axis='x',alpha=.2)
    fig.suptitle('Paired uncertainty across four declared comparisons\n60-minute calendar blocks; short pilot history')
    fig.savefig(OUT/'02_incremental_uncertainty.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(12,8),layout='constrained',sharex=True)
    calendar=np.arange(data.timestamp.min(),data.timestamp.max()+1,60_000_000_000,dtype=np.int64)
    regular=data.set_index('timestamp').reindex(calendar)
    dates=pd.to_datetime(calendar,unit='ns',utc=True)
    axes[0].plot(dates,regular.signed_bps,lw=.7,color='#777777',label='Actual next-minute return')
    for model in ['Ordinary18','OrdinaryPlusTDAInteractions24']:
        g=pred.loc[pred.target.eq('signed_bps') & pred.model.eq(model)]
        axes[0].plot(dates,g.set_index('timestamp').prediction.reindex(calendar),lw=1,label=model)
    axes[0].legend(fontsize=8);axes[0].set_ylabel('Signed bps')
    for key in TDA:axes[1].plot(dates,regular[key],label=key,lw=.9)
    axes[1].legend(fontsize=8);axes[1].set_ylabel('Standardized geometry')
    p=pred.loc[pred.target.eq('signed_bps')].pivot(index='timestamp',columns='model',values='squared_error')
    for model in ['OrdinaryPlusTDA21','OrdinaryPlusTDAInteractions24']:
        axes[2].plot(dates,(p[model]-p.Ordinary18).cumsum().reindex(calendar),label=model)
    axes[2].axhline(0,color='black',lw=.8);axes[2].legend(fontsize=8)
    axes[2].set(ylabel='Cumulative error difference\nNegative favors TDA',xlabel='Decision time UTC; missing windows excluded')
    fig.suptitle('Realized returns, persistence features and accumulated prediction error\nBottom panel is a forecast-loss diagnostic, not profit')
    fig.savefig(OUT/'03_forecasts_and_features.png',dpi=160);plt.close(fig)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['extract','features','fit','all'],default='all')
    args=parser.parse_args()
    if args.stage in ('extract','all'):extract()
    if args.stage in ('features','all'):data=build_features()
    else:data=None
    if args.stage in ('fit','all'):
        if data is None:data=pd.read_csv(OUT/'features_and_targets.csv')
        pred=fit(data);metrics,comparisons=boot(pred);plots(data,pred,metrics,comparisons)
        save_json('summary.json',dict(completed_at=datetime.now(timezone.utc).isoformat(),
                  specification_sha256=sha(OUT/'specification.json'),source_sha256=sha(__file__),
                  n_features=len(data),n_scored=int(pred.row_id.nunique()),
                  n_refits=len(json.loads((OUT/'training_membership.json').read_text())),
                  first_forecast=pred.decision_utc.min(),last_forecast=pred.decision_utc.max(),
                  metrics=json.loads(metrics.to_json(orient='records')),
                  comparisons=comparisons.to_dict('records')))
        print(metrics.to_string(index=False),flush=True);print(comparisons.to_string(index=False),flush=True)


if __name__=='__main__':main()
