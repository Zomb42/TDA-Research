"""Initial descriptive analysis of frozen closed BTC archive segments in tda.

Never touches the recorder or live partial files. TTK graphs are a separate
bounded visualization of the first ten minutes of the last complete UTC hour.
"""
from collections import Counter
from datetime import datetime,timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('MPLCONFIGDIR','/private/tmp/tda-archive-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'market_data'))
from assess_perp_capture import linear_book_metrics
from decimal import Decimal as D

OUT=Path(__file__).with_suffix('')


def stats(series):
    values=np.asarray(series,dtype=float);values=values[np.isfinite(values)]
    return dict(n=len(values),min=float(values.min()),median=float(np.median(values)),max=float(values.max()),
                p10=float(np.quantile(values,.1)),p90=float(np.quantile(values,.9))) if len(values) else None


def main():
    OUT.mkdir(exist_ok=True)
    frozen=json.loads((OUT/'closed_segment_validation.json').read_text())
    checkpoints=[];trades=[];reference=[];gaps=[];anchors=[];metadata=None
    for name in frozen['frozen_files']:
        path=Path(name);source=path.parent.name
        if metadata is None:
            metadata=json.loads((path.parent.parent/'kalshi_market.json').read_text())['market']
        with gzip.open(path,'rt') as stream:
            for line in stream:
                # Most rows are already independently validated individual book deltas.
                if source=='kalshi_perp' and not ('"control":' in line or '"type":"trade"' in line):continue
                row=json.loads(line);control=row.get('control')
                if source=='kalshi_perp' and control=='book_checkpoint':
                    checkpoints.append(row)
                if source=='kalshi_perp' and control=='segment_start' and row.get('book_anchor'):
                    anchors.append(row)
                event=row.get('message',{})
                if source=='kalshi_perp' and event.get('type')=='trade':
                    msg=event['msg'];trades.append(dict(timestamp=row['received_at'],trade_id=msg['trade_id'],
                        btc=float(D(msg['count'])*D(metadata['contract_size'])),notional_usd=float(D(msg['count'])*D(msg['price']))))
                if source=='coinbase_reference' and row.get('type')=='reference_sample':
                    q=row.get('quote') or {}
                    reference.append(dict(timestamp=row['sampled_at'],connected=row['connected'],epoch=row['epoch'],
                        bid=float(q.get('best_bid','nan')),ask=float(q.get('best_ask','nan')),
                        midpoint=float(row.get('midpoint','nan')),quote_age_ms=row.get('quote_age_ms'),
                        trade_count=row['trade_count'],trade_btc=float(row['trade_btc']),
                        trade_notional_usd=float(row['trade_notional_usd']),interval_seconds=row['interval_seconds']))
                if control in ('gap_start','gap_end','sequence_gap','trade_sequence_gap','book_invalid'):
                    gaps.append(dict(source=source,**row))
        print('Extracted',source,path.name,flush=True)
    contract=D(metadata['contract_size'])
    records=[]
    for row in checkpoints:
        sides={s:{D(p):D(q) for p,q in row['book'][s]} for s in ['bid','ask']}
        records.append(dict(timestamp=row['received_at'],seq=row['book']['seq'],epoch=row['epoch'],
                            **linear_book_metrics(sides,contract)))
    table=pd.DataFrame(records);table.timestamp=pd.to_datetime(table.timestamp,utc=True);table=table.sort_values('timestamp')
    ref=pd.DataFrame(reference);ref.timestamp=pd.to_datetime(ref.timestamp,utc=True);ref=ref.sort_values('timestamp')
    trade=pd.DataFrame(trades);trade.timestamp=pd.to_datetime(trade.timestamp,utc=True)
    duplicate_trades=int(trade.trade_id.duplicated().sum());trade=trade.drop_duplicates('trade_id')
    table.to_csv(OUT/'perp_checkpoints.csv',index=False);ref.to_csv(OUT/'coinbase_reference.csv',index=False)
    trade.set_index('timestamp')[['btc','notional_usd']].resample('1min').sum().to_csv(OUT/'perp_trade_volume_1min.csv')
    # Uniform, backwards/as-of clocks; no interpolation through stale observations.
    clock=pd.DataFrame({'timestamp':pd.date_range(table.timestamp.min().ceil('5s'),table.timestamp.max().floor('5s'),freq='5s')})
    p=table[['timestamp','mid_usd_btc','spread_bps','total_within_10bps_usd','total_notional_usd']].rename(columns={'timestamp':'perp_observed_at'})
    aligned=pd.merge_asof(clock,p,left_on='timestamp',right_on='perp_observed_at',direction='backward',tolerance=pd.Timedelta(seconds=7.5))
    c=ref.loc[ref.connected,['timestamp','midpoint','quote_age_ms']].rename(columns={'timestamp':'spot_observed_at','midpoint':'spot_mid'})
    aligned=pd.merge_asof(aligned,c,left_on='timestamp',right_on='spot_observed_at',direction='backward',tolerance=pd.Timedelta(seconds=1))
    aligned['spot_total_age_ms']=aligned.quote_age_ms+(aligned.timestamp-aligned.spot_observed_at).dt.total_seconds()*1000
    aligned.loc[aligned.spot_total_age_ms>2000,'spot_mid']=np.nan
    aligned['basis_bps']=(aligned.mid_usd_btc/aligned.spot_mid-1)*10000
    aligned['perp_return_bps']=aligned.mid_usd_btc.pct_change(fill_method=None)*10000
    aligned['spot_return_bps']=aligned.spot_mid.pct_change(fill_method=None)*10000
    aligned.to_csv(OUT/'aligned_5s.csv',index=False)
    paired=aligned[['perp_return_bps','spot_return_bps']].dropna()
    # Fixed source choice: first ten minutes of the most recent fully closed hour.
    full_hours=[pd.Timestamp(Path(p).name.split('.jsonl')[0].replace('-00-00Z',':00:00Z'))
                for p in frozen['frozen_files'] if Path(p).parent.name=='kalshi_perp']
    start=max(full_hours);times=pd.date_range(start,periods=120,freq='5s')
    selection=pd.merge_asof(pd.DataFrame({'timestamp':times}),table[['timestamp']].rename(columns={'timestamp':'observed_at'}),
                           left_on='timestamp',right_on='observed_at',direction='backward',tolerance=pd.Timedelta(seconds=7.5))
    if selection.observed_at.isna().any():raise ValueError('Missing/stale book observation in chosen topology window')
    checkpoint_map={pd.Timestamp(row['received_at']):row['book'] for row in checkpoints}
    chosen=[checkpoint_map[t] for t in selection.observed_at]
    (OUT/'chosen_books.json').write_text(json.dumps(dict(
        timestamps=[t.isoformat() for t in times],observed_at=[t.isoformat() for t in selection.observed_at],
        books=chosen),separators=(',',':'))+'\n')
    first=chosen[0];first_mid=(float(first['bid'][0][0])+float(first['ask'][0][0]))/2/float(contract)
    mids=np.array([(float(book['bid'][0][0])+float(book['ask'][0][0]))/2/float(contract) for book in chosen])
    cases=[]
    for bin_usd in [10,20]:
        anchor=np.round(first_mid/20)*20;edges=np.arange(anchor-400,anchor+400+bin_usd,bin_usd)
        centers=(edges[:-1]+edges[1:])/2
        for side in ['bid','ask']:
            density=np.zeros((len(centers),len(times)))
            for j,book in enumerate(chosen):
                # Stay inside the observed outer span of the full reported two-sided ladder.
                lo=min(float(p)/float(contract) for p,q in book['bid'])
                hi=max(float(p)/float(contract) for p,q in book['ask'])
                if edges[0]<lo or edges[-1]>hi:raise ValueError('Window exceeds observed book coverage')
                levels=book[side];prices=np.array([float(p)/float(contract) for p,q in levels])
                weights=np.array([float(p)*float(q) for p,q in levels])
                density[:,j]=np.histogram(prices,bins=edges,weights=weights)[0]/bin_usd
            smooth=gaussian_filter(density,sigma=(10/bin_usd,1),mode='nearest')
            for threshold in ([10000,25000,50000] if side=='bid' else [25000]):
                name=f'{side}_bin{bin_usd}_threshold{threshold}'
                np.savez(OUT/(name+'.npz'),density=smooth,raw_density=density,price_centers=centers,
                         time_seconds=np.arange(len(times))*5,threshold=threshold)
                cases.append(dict(name=name,input=name+'.npz',side=side,bin_usd=bin_usd,threshold=threshold,
                                  smoothing_price_usd=10,smoothing_time_seconds=5))
            if bin_usd==10:
                name=f'{side}_bin10_raw_threshold25000'
                np.savez(OUT/(name+'.npz'),density=density,raw_density=density,price_centers=centers,
                         time_seconds=np.arange(len(times))*5,threshold=25000)
                cases.append(dict(name=name,input=name+'.npz',side=side,bin_usd=10,threshold=25000,
                                  smoothing_price_usd=0,smoothing_time_seconds=0))
                relative_edges=np.arange(-400,410,10);relative_centers=(relative_edges[:-1]+relative_edges[1:])/2
                relative=np.zeros_like(density)
                for j,book in enumerate(chosen):
                    levels=book[side]
                    prices=np.array([float(p)/float(contract)-mids[j] for p,q in levels])
                    weights=np.array([float(p)*float(q) for p,q in levels])
                    relative[:,j]=np.histogram(prices,bins=relative_edges,weights=weights)[0]/10
                relative_smooth=gaussian_filter(relative,sigma=(1,1),mode='nearest')
                name=f'{side}_midrelative_bin10_threshold25000'
                np.savez(OUT/(name+'.npz'),density=relative_smooth,raw_density=relative,price_centers=relative_centers,
                         time_seconds=np.arange(len(times))*5,threshold=25000)
                cases.append(dict(name=name,input=name+'.npz',side=side,bin_usd=10,threshold=25000,
                                  smoothing_price_usd=10,smoothing_time_seconds=5,coordinate='midpoint-relative USD'))
                translated=np.column_stack([np.interp(centers-(mids[j]-mids[0]),centers,density[:,0],left=0,right=0)
                                            for j in range(len(times))])
                name=f'{side}_translation_control_bin10_threshold25000'
                np.savez(OUT/(name+'.npz'),density=gaussian_filter(translated,sigma=(1,1),mode='nearest'),raw_density=translated,
                         price_centers=centers,time_seconds=np.arange(len(times))*5,threshold=25000)
                cases.append(dict(name=name,input=name+'.npz',side=side,bin_usd=10,threshold=25000,
                                  smoothing_price_usd=10,smoothing_time_seconds=5,translation_control=True))
    # Synthetic domains with known time-Reeb structure.
    for name,bridges,two in [('control_one_band',[],False),('control_two_bands',[],True),('control_loop',[8,22],True)]:
        field=np.zeros((17,31));field[3:6,:]=2
        if two:field[11:14,:]=2
        for x in bridges:field[5:12,x:x+3]=2
        np.savez(OUT/(name+'.npz'),density=field,raw_density=field,price_centers=np.arange(17),time_seconds=np.arange(31),threshold=1)
        cases.append(dict(name=name,input=name+'.npz',control=True))
    config=dict(window_start_utc=start.isoformat(),window_end_utc=(start+pd.Timedelta(minutes=10)).isoformat(),
                coordinate='Fixed absolute USD/BTC price bins; time in seconds from start',
                scalar_for_reeb='Time on the clipped superlevel domain of displayed notional density',
                density_units='USD displayed limit-price notional per $1/BTC price width',
                cases=cases,centered_smoothing_is_noncausal=True,all_data_development=True,
                sampling='Backwards as-of full-book checkpoints at 5-second times, maximum age 7.5 seconds')
    (OUT/'reeb_cases.json').write_text(json.dumps(config,indent=2)+'\n')
    storage=[]
    for result in frozen['results']:
        path=Path(result['file']);m=json.loads(path.with_suffix('.manifest.json').read_text());storage.append(m)
    controls=Counter(row['control'] for row in gaps)
    gap_pairs=[];pending={}
    for row in gaps:
        key=row['source']
        if row['control']=='gap_start':pending[key]=pd.Timestamp(row['received_at'])
        if row['control']=='gap_end' and key in pending:
            gap_pairs.append(dict(source=key,start=pending[key].isoformat(),end=row['received_at'],
                                  seconds=(pd.Timestamp(row['received_at'])-pending.pop(key)).total_seconds()))
    metrics=['spread_bps','total_btc','total_notional_usd','total_within_10bps_usd','total_within_25bps_usd','top_two_sided_notional_usd','total_levels']
    summary=dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(),analysis_start_utc=table.timestamp.min().isoformat(),
        analysis_end_utc=table.timestamp.max().isoformat(),perp_checkpoints=len(table),coinbase_samples=len(ref),
        validation_checkpoints=sum(r['checkpoints_matched'] for r in frozen['results']),
        perp_metrics={k:stats(table[k]) for k in metrics},
        first_perp_mid=float(table.mid_usd_btc.iloc[0]),last_perp_mid=float(table.mid_usd_btc.iloc[-1]),
        min_perp_mid=float(table.mid_usd_btc.min()),max_perp_mid=float(table.mid_usd_btc.max()),
        basis_bps=stats(aligned.basis_bps),paired_5s_return_correlation=float(paired.corr().iloc[0,1]),paired_return_rows=len(paired),
        coinbase_quote_age_ms=stats(ref.quote_age_ms),coinbase_rows_quote_over_2s=int((ref.quote_age_ms>2000).sum()),
        duplicate_perp_trade_ids=duplicate_trades,perp_traded_btc=float(trade.btc.sum()),perp_traded_notional_usd=float(trade.notional_usd.sum()),
        gap_controls=dict(controls),gap_intervals=gap_pairs,closed_storage_bytes=sum(x['compressed_bytes'] for x in storage),
        closed_uncompressed_bytes=sum(x['uncompressed_bytes'] for x in storage),graph_window=config,
        limitations=['Only a few hours, all exploratory/development data','Different venue/feed clocks and quote freshness limit basis/lead-lag interpretation',
                     'Coinbase is a sampled reference, not full-depth or an exact raw-trade tape','Displayed quantities are not order identities or guaranteed executable liquidity',
                     'Time Reeb graphs depend on depth threshold, binning, smoothing, triangulation and window boundaries'])
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    # Initial overview: aligned prices, relative quote difference, nearby depth and spread.
    fig,axes=plt.subplots(4,1,figsize=(12,10),sharex=True,layout='constrained')
    axes[0].plot(aligned.timestamp,aligned.mid_usd_btc,label='Kalshi perp midpoint',lw=1)
    axes[0].plot(aligned.timestamp,aligned.spot_mid,label='Coinbase spot midpoint',lw=1,alpha=.8)
    axes[0].set_ylabel('USD/BTC');axes[0].legend(loc='upper left',ncol=2)
    axes[1].plot(aligned.timestamp,aligned.basis_bps,color='#7755aa',lw=.8);axes[1].axhline(0,color='grey',lw=.5)
    axes[1].set_ylabel('Perp / spot\ndifference (bps)')
    axes[2].plot(table.timestamp,table.bid_within_10bps_usd/1e6,label='Bid within 10 bps',lw=.8)
    axes[2].plot(table.timestamp,table.ask_within_10bps_usd/1e6,label='Ask within 10 bps',lw=.8)
    axes[2].set_ylabel('Displayed USD\nnotional (millions)');axes[2].legend(loc='upper left',ncol=2)
    axes[3].plot(table.timestamp,table.spread_bps,color='#333333',lw=.7);axes[3].set_ylabel('Perp spread (bps)')
    axes[3].set_xlabel('UTC — closed segments only')
    for ax in axes:ax.grid(alpha=.15)
    fig.suptitle('First BTC archive check — descriptive quotes and displayed liquidity',fontsize=14)
    fig.savefig(OUT/'01_market_overview.png',dpi=160);plt.close(fig)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['graph_window','perp_metrics']},indent=2),flush=True)


if __name__=='__main__':main()
