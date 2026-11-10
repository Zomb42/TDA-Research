"""Fixed post-discovery 20<=prior VIX<30 gate on frozen factor-neutral returns.

Use tda Python. This is an exploratory follow-up, not a new untouched test.
"""
import hashlib
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/tda-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from factor_reversal_vix import hac_ols

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).with_suffix('')
SOURCE=OUT.parent/'factor_reversal_vix/aligned_daily_panel.csv'
MODELS=['PCA3','EFA3']
LABELS=['below15','15to20','20to30','30plus']
SEED=2026110418
DRAWS=2000


def masks(dates):
    return {'full':np.ones(len(dates),dtype=bool),'earlier':np.array(dates<'2024-01-01'),
            'later':np.array(dates>='2024-01-01')}


def sample_indices(n,block):
    rng=np.random.default_rng(SEED+block)
    starts=rng.integers(0,n,size=(DRAWS,int(np.ceil(n/block))))
    return ((starts[:,:,None]+np.arange(block))%n).reshape(DRAWS,-1)[:,:n]


def describe(r,exposure):
    wealth=np.r_[1.,np.cumprod(1+r)]
    vol=np.std(r,ddof=1)
    return dict(days=len(r),active_days=int(np.count_nonzero(exposure)),
        mean_gross_exposure=float(np.mean(exposure)),max_gross_exposure=float(np.max(exposure)),
        mean_calendar_bps=r.mean()*1e4,mean_active_bps=r[exposure>0].mean()*1e4,
        total_return_pct=(wealth[-1]-1)*100,ending_100k=wealth[-1]*100000,
        cagr_pct=(wealth[-1]**(252/len(r))-1)*100,annual_vol_pct=vol*np.sqrt(252)*100,
        sharpe_zero=r.mean()/vol*np.sqrt(252) if vol else np.nan,
        max_drawdown_pct=(wealth/np.maximum.accumulate(wealth)-1).min()*100)


def simultaneous(observed,draws):
    valid=np.isfinite(draws).all(axis=1)
    values=draws[valid]
    se=values.std(axis=0,ddof=1)
    critical=np.percentile(np.max(np.abs((values-observed)/se),axis=1),95)
    return observed-critical*se,observed+critical*se,int(valid.sum())


def policies_and_inference(panel):
    metrics=[];curves=[];inference=[];families=[];annual=[]
    for period,mask in masks(panel.index).items():
        sub=panel.loc[mask];gate=sub.vix_lag.ge(20)&sub.vix_lag.lt(30)
        indices={b:sample_indices(len(sub),b) for b in [60,20]}
        family_values={kind:[] for kind in ['conditional_mean','calendar_mean','gate_minus_always']}
        family_draws={(kind,b):[] for kind in family_values for b in [60,20]}
        keys=[]
        for model in MODELS:
            r=sub[model].to_numpy();g=gate.to_numpy();target=r*g
            fraction=g.mean();risk_fraction=target.std(ddof=1)/r.std(ddof=1)
            exposures={'AlwaysOn':np.ones(len(sub)),'Target20to30':g.astype(float),
                'Outside20to30':(~g).astype(float),'ConstantExposureMatch':np.full(len(sub),fraction),
                'ConstantVolatilityMatch':np.full(len(sub),risk_fraction)}
            for label in LABELS:
                if label!='20to30':exposures[f'Only_{label}']=sub.vix_bin.eq(label).to_numpy().astype(float)
            for policy,exposure in exposures.items():
                rr=r*exposure
                metrics.append(dict(model=model,period=period,policy=policy,**describe(rr,exposure)))
                if period=='full':
                    curves.append(pd.DataFrame(dict(date=sub.index,model=model,policy=policy,return_gross=rr,
                        gross_exposure=exposure,equity_100k=100000*np.cumprod(1+rr))))
                    for year in sorted(set(sub.index.str[:4])):
                        take=sub.index.str.startswith(year)
                        annual.append(dict(model=model,policy=policy,year=year,
                            return_pct=(np.prod(1+rr[take])-1)*100,active_days=int((exposure[take]>0).sum()),
                            mean_calendar_bps=rr[take].mean()*1e4,sum_arithmetic_bps=rr[take].sum()*1e4))
            definitions={'target_conditional_mean':(r[g].mean(),None),
                'target_calendar_mean':(target.mean(),target),
                'gate_minus_always':((target-r).mean(),target-r),
                'gate_minus_exposure_match':((target-fraction*r).mean(),target-fraction*r),
                'gate_minus_volatility_match':((target-risk_fraction*r).mean(),target-risk_fraction*r),
                'band_minus_outside_conditional':(r[g].mean()-r[~g].mean(),None)}
            for name,(observed,values) in definitions.items():
                row=dict(model=model,period=period,statistic=name,estimate_bps=observed*1e4)
                for block,ix in indices.items():
                    rr=r[ix];gg=g[ix]
                    if name=='target_conditional_mean':draw=(rr*gg).sum(axis=1)/gg.sum(axis=1)
                    elif name=='band_minus_outside_conditional':
                        draw=(rr*gg).sum(axis=1)/gg.sum(axis=1)-(rr*(~gg)).sum(axis=1)/(~gg).sum(axis=1)
                    else:draw=values[ix].mean(axis=1)
                    row[f'ci{block}_low'],row[f'ci{block}_high']=np.percentile(draw*1e4,[2.5,97.5])
                inference.append(row)
            for label in LABELS:
                active=sub.vix_bin.eq(label).to_numpy()
                values=r*active
                keys.append((model,label,int(active.sum())))
                obs={'conditional_mean':r[active].mean(),'calendar_mean':values.mean(),
                     'gate_minus_always':(values-r).mean()}
                for kind in family_values:family_values[kind].append(obs[kind]*1e4)
                for block,ix in indices.items():
                    count=active[ix].sum(axis=1)
                    conditional=np.divide(values[ix].sum(axis=1),count,
                        out=np.full(DRAWS,np.nan),where=count>0)*1e4
                    draws={'conditional_mean':conditional,'calendar_mean':values[ix].mean(axis=1)*1e4,
                           'gate_minus_always':(values-r)[ix].mean(axis=1)*1e4}
                    for kind in draws:family_draws[(kind,block)].append(draws[kind])
        for kind,observed in family_values.items():
            observed=np.array(observed)
            result={b:simultaneous(observed,np.column_stack(family_draws[(kind,b)])) for b in [60,20]}
            for i,(model,label,days) in enumerate(keys):
                row=dict(period=period,model=model,bin=label,days=days,statistic=kind,estimate_bps=observed[i])
                for block,(lo,hi,valid) in result.items():
                    row[f'sim{block}_low'],row[f'sim{block}_high']=lo[i],hi[i]
                    row[f'valid_draws_{block}']=valid
                families.append(row)
    return pd.DataFrame(metrics),pd.concat(curves,ignore_index=True),pd.DataFrame(inference),pd.DataFrame(families),pd.DataFrame(annual)


def concentration(panel):
    g=panel.vix_lag.ge(20)&panel.vix_lag.lt(30)
    numbered=(g & ~g.shift(1,fill_value=False)).cumsum().where(g,0).astype(int)
    episode_rows=[];state_rows=[];loo=[];tails=[];daily=[]
    for number in sorted(set(numbered)-{0}):
        positions=np.flatnonzero(numbered.eq(number));first=positions[0]
        prior=panel.vix_lag.iloc[first-1] if first else np.nan
        origin='from_below20' if prior<20 else 'from30plus' if prior>=30 else 'initial_unknown'
        for model in MODELS:
            r=panel[model].iloc[positions].to_numpy()
            episode_rows.append(dict(model=model,episode=int(number),start=panel.index[first],end=panel.index[positions[-1]],
                days=len(r),origin=origin,return_pct=(np.prod(1+r)-1)*100,sum_arithmetic_bps=r.sum()*1e4,
                mean_active_bps=r.mean()*1e4))
        for age,i in enumerate(positions,1):
            daily.append(dict(date=panel.index[i],episode=int(number),age=age,origin=origin,
                age_bin='1' if age==1 else '2to5' if age<=5 else '6to20' if age<=20 else '21plus'))
    episode_daily=pd.DataFrame(daily).set_index('date')
    for period,mask in masks(panel.index).items():
        sub=panel.loc[mask];gate=g.loc[sub.index].to_numpy()
        selected=sub.loc[gate].join(episode_daily)
        for model in MODELS:
            r=sub[model].to_numpy();rr=r*gate
            for group in ['origin','age_bin']:
                for label,part in selected.groupby(group):
                    vals=part[model].to_numpy()*1e4
                    state_rows.append(dict(model=model,period=period,group=group,state=label,days=len(vals),
                        episodes=part.episode.nunique(),mean_bps=vals.mean(),std_bps=vals.std(ddof=1),
                        sum_arithmetic_bps=vals.sum()))
            best=np.flatnonzero(gate)[np.argsort(r[gate])[-5:]]
            worst=np.flatnonzero(gate)[np.argsort(r[gate])[:5]]
            for name,excluded in [('none',np.array([],dtype=int)),('remove5_best',best),('remove5_worst',worst)]:
                keep=gate.copy();keep[excluded]=False
                trimmed=r*keep
                tails.append(dict(model=model,period=period,diagnostic=name,removed_days=len(excluded),
                    removed_sum_arithmetic_bps=r[excluded].sum()*1e4,
                    **describe(trimmed,keep.astype(float))))
            for year in sorted(set(sub.index.str[:4])):
                take=~sub.index.str.startswith(year)
                a=describe(rr[take],gate[take].astype(float));b=describe(r[take],np.ones(take.sum()))
                loo.append(dict(model=model,period=period,omitted_year=year,active_days=a['active_days'],
                    gate_mean_active_bps=a['mean_active_bps'],gate_cagr_pct=a['cagr_pct'],
                    always_cagr_pct=b['cagr_pct'],cagr_difference_pct=a['cagr_pct']-b['cagr_pct']))
    return pd.DataFrame(episode_rows),episode_daily,pd.DataFrame(state_rows),pd.DataFrame(loo),pd.DataFrame(tails)


def regress_and_forecast(panel):
    controls=['log_spy_rv20_lag','spy_return_lag']
    linear=controls+['log_vix_lag','vix_log_change_lag']
    frame=panel.copy();frame['band20to30']=(frame.vix_lag.ge(20)&frame.vix_lag.lt(30)).astype(float)
    reg=[];pred=[];comparison=[]
    for period,mask in masks(frame.index).items():
        sub=frame.loc[mask]
        for model in MODELS:
            for design,cols in [('ControlsBand',controls+['band20to30']),('LinearVIXBand',linear+['band20to30'])]:
                x=np.column_stack([np.ones(len(sub)),sub[cols]])
                beta,se,r2=hac_ols(x,sub[model].to_numpy()*1e4)
                for name,b,s in zip(['intercept']+cols,beta,se):
                    reg.append(dict(model=model,period=period,design=design,term=name,coefficient=b,
                        hac20_se=s,ci_low=b-1.96*s,ci_high=b+1.96*s,r_squared=r2))
    for start in range(504,len(frame),21):
        train=frame.iloc[:start];test=frame.iloc[start:start+21]
        for model in MODELS:
            y=train[model].to_numpy()*1e4;actual=test[model].to_numpy()*1e4
            for design,cols in [('LinearVIX',linear),('LinearVIXBand',linear+['band20to30'])]:
                mu=train[cols].mean().to_numpy();sd=train[cols].std(ddof=1).to_numpy()
                sd=np.where(sd>0,sd,1.)
                x=np.column_stack([np.ones(len(train)),(train[cols].to_numpy()-mu)/sd])
                xx=np.column_stack([np.ones(len(test)),(test[cols].to_numpy()-mu)/sd])
                forecast=xx@np.linalg.lstsq(x,y,rcond=None)[0]
                for date,a,p in zip(test.index,actual,forecast):
                    pred.append(dict(date=date,model=model,design=design,training_end=train.index[-1],
                        training_n=len(train),actual_bps=a,predicted_bps=p,squared_error=(a-p)**2))
    pred=pd.DataFrame(pred)
    dates=np.array(sorted(pred.date.unique()))
    for period,mask in masks(dates).items():
        sub=pred.loc[pred.date.isin(dates[mask])];deltas=[];base=[]
        for model in MODELS:
            q=sub.loc[sub.model==model].pivot(index='date',columns='design',values='squared_error').sort_index()
            deltas.append((q.LinearVIXBand-q.LinearVIX).to_numpy());base.append(q.LinearVIX.mean())
        matrix=np.column_stack(deltas);obs=matrix.mean(axis=0)
        boot={b:matrix[sample_indices(len(matrix),b)].mean(axis=1) for b in [60,20]}
        family={b:simultaneous(obs,draws) for b,draws in boot.items()}
        for i,model in enumerate(MODELS):
            row=dict(model=model,period=period,days=len(matrix),linear_mse=base[i],
                band_model_mse=base[i]+obs[i],loss_difference_bps_squared=obs[i],
                improvement_pct=-obs[i]/base[i]*100)
            for block in [60,20]:
                row[f'ci{block}_low'],row[f'ci{block}_high']=np.percentile(boot[block][:,i],[2.5,97.5])
                row[f'sim{block}_low'],row[f'sim{block}_high']=family[block][0][i],family[block][1][i]
            comparison.append(row)
    return pd.DataFrame(reg),pred,pd.DataFrame(comparison)


def figures(panel,metrics,curves,annual,episodes,loo):
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    names={'AlwaysOn':'Always trade','Target20to30':'VIX 20–30 only',
        'ConstantVolatilityMatch':'Equal volatility','ConstantExposureMatch':'Equal average exposure'}
    fig,axes=plt.subplots(3,1,figsize=(12,9),sharex=True,layout='constrained',height_ratios=[1.5,1,.8])
    colors={'AlwaysOn':'#247ba0','Target20to30':'#d97706','ConstantVolatilityMatch':'#658b45'}
    for policy,color in colors.items():
        q=curves.loc[(curves.model=='PCA3')&(curves.policy==policy)]
        dates=pd.to_datetime(q.date);wealth=q.equity_100k.to_numpy()
        axes[0].plot(dates,wealth,label=names[policy],color=color)
        peak=np.maximum.accumulate(np.r_[100000.,wealth])[1:]
        axes[1].plot(dates,(wealth/peak-1)*100,color=color)
    axes[0].legend();axes[0].set_ylabel('Account value from $100,000')
    axes[1].set_ylabel('Daily marked drawdown (%)')
    dates=pd.to_datetime(panel.index);g=panel.vix_lag.ge(20)&panel.vix_lag.lt(30)
    axes[2].plot(dates,panel.vix_lag,color='#6a4c93',lw=.8)
    axes[2].fill_between(dates,20,30,where=g,color='#d97706',alpha=.35,label='Target gate active')
    axes[2].set_ylabel('Prior-session VIX');axes[2].legend()
    for ax in axes:
        ax.axvline(pd.Timestamp('2024-01-01'),color='#777',ls='--',lw=.8)
        ax.grid(alpha=.2);ax.margins(x=.01)
    fig.suptitle('Fixed 20 <= prior VIX < 30 filter on frozen PCA strategy\nExploratory selection after viewing bins; gross/pre-fee; cash earns zero\nGreen: hindsight constant strategy fraction matching full-period volatility',fontsize=12)
    fig.savefig(OUT/'01_gate_equity_and_drawdown.png',dpi=160,bbox_inches='tight');plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained')
    years=sorted(annual.year.unique());x=np.arange(len(years))
    for policy,offset,color in [('AlwaysOn',-.18,'#247ba0'),('Target20to30',.18,'#d97706')]:
        q=annual.loc[(annual.model=='PCA3')&(annual.policy==policy)].set_index('year').loc[years]
        axes[0,0].bar(x+offset,q.return_pct,.36,label=names[policy],color=color)
    axes[0,0].set_xticks(x,years,rotation=45);axes[0,0].set_ylabel('Calendar-year gross return (%)');axes[0,0].legend()
    q=annual.loc[(annual.model=='PCA3')&(annual.policy=='Target20to30')].set_index('year').loc[years]
    axes[1,0].bar(x,q.active_days,color='#d97706');axes[1,0].set_xticks(x,years,rotation=45)
    axes[1,0].set_ylabel('Active sessions')
    q=episodes.loc[episodes.model=='PCA3'].sort_values('sum_arithmetic_bps',ascending=False)
    axes[0,1].bar(np.arange(len(q)),q.sum_arithmetic_bps,color=np.where(q.sum_arithmetic_bps>=0,'#d97706','#247ba0'))
    axes[0,1].set(xlabel='All contiguous active episodes, ranked after outcomes',ylabel='Sum of daily episode returns (bps)')
    q=loo.loc[(loo.model=='PCA3')&(loo.period=='full')]
    axes[1,1].bar(q.omitted_year.astype(str),q.gate_mean_active_bps,color='#d97706')
    axes[1,1].tick_params(axis='x',rotation=45);axes[1,1].set(xlabel='Year omitted',ylabel='Remaining active-day mean (bps)')
    for ax in axes.ravel():ax.axhline(0,color='#777',lw=.8);ax.grid(axis='y',alpha=.2)
    fig.suptitle('Concentration diagnostics for the fixed VIX 20–30 band\nAll years and episodes reported; exclusion/ranking diagnostics are not trading rules')
    fig.savefig(OUT/'02_years_episodes_and_omissions.png',dpi=160,bbox_inches='tight');plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(13,4.8),layout='constrained')
    choices=['AlwaysOn','Target20to30','ConstantExposureMatch','ConstantVolatilityMatch']
    for ax,period in zip(axes,['full','earlier','later']):
        q=metrics.loc[(metrics.model=='PCA3')&(metrics.period==period)].set_index('policy').loc[choices]
        ax.scatter(q.annual_vol_pct,q.cagr_pct,s=50)
        for policy,row in q.iterrows():ax.annotate(names[policy],(row.annual_vol_pct,row.cagr_pct),fontsize=8,xytext=(3,5),textcoords='offset points')
        ax.set(title=period,xlabel='Annualized daily volatility (%)',ylabel='Whole-calendar gross CAGR (%)')
        ax.axhline(0,color='#777',lw=.8);ax.grid(alpha=.2);ax.margins(.25)
    fig.suptitle('Timing versus simply reducing the existing strategy exposure\nConstant fractions use hindsight calibration separately per period; no leverage or cash interest',fontsize=11)
    fig.savefig(OUT/'03_return_risk_comparison.png',dpi=160,bbox_inches='tight');plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    panel=pd.read_csv(SOURCE,index_col='date')
    assert len(panel)==2446 and not panel.isna().any().any()
    assert np.array_equal(panel.vix_bin.eq('20to30'),panel.vix_lag.ge(20)&panel.vix_lag.lt(30))
    metrics,curves,inference,families,annual=policies_and_inference(panel)
    episodes,episode_daily,states,loo,tails=concentration(panel)
    reg,pred,forecast=regress_and_forecast(panel)
    for name,frame in [('performance',metrics),('daily_curves',curves),('inference',inference),
        ('original_band_simultaneous',families),('annual_returns',annual),('episodes',episodes),
        ('episode_daily',episode_daily.reset_index()),('episode_states',states),('leave_year_out',loo),
        ('tail_sensitivity',tails),('band_regressions',reg),('forecast_predictions',pred),('forecast_comparison',forecast)]:
        frame.to_csv(OUT/f'{name}.csv',index=False)
    figures(panel,metrics,curves,annual,episodes,loo)
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_hash
    files=[SOURCE,Path(__file__),OUT/'specification.json',OUT.parent/'factor_reversal_vix.py']
    files+=sorted(OUT.glob('*.csv'))+sorted(OUT.glob('*.png'))
    (OUT/'run_manifest.json').write_text(json.dumps(dict(source_unchanged=True,seed=SEED,
        bootstrap_draws=DRAWS,selected_band_after_prior_results=True,
        sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2)+'\n')
    print(metrics.loc[(metrics.model=='PCA3')&metrics.policy.isin(['AlwaysOn','Target20to30','ConstantExposureMatch','ConstantVolatilityMatch']),
        ['period','policy','active_days','mean_gross_exposure','mean_calendar_bps','mean_active_bps','cagr_pct','annual_vol_pct','sharpe_zero','max_drawdown_pct','ending_100k']].to_string(index=False))
    print(forecast.to_string(index=False))


if __name__=='__main__':main()
