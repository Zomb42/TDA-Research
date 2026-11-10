"""Frozen factor-neutral reversal versus VIX: descriptive and causal forecast checks.

Run with tda Python. No new market download, portfolio refit, sizing or trading gate.
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
from scipy.stats import spearmanr, norm

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix('')
RETURNS = ROOT / 'equity/experiments/equity_efa_vs_pca/daily_gross_returns.csv'
VIX = ROOT / 'market_data/datasets/mean_reversion_context_2026-11-04/vix_daily.csv'
PRICES = ROOT / 'market_data/datasets/equity_daily_expanded_2016_2026-10-27/close_all.csv'
MODELS = ['PCA3', 'EFA3']
SEED = 2026110407
DRAW = 2000
CONTROLS = ['log_spy_rv20_lag', 'spy_return_lag']
VIX_FEATURES = ['log_vix_lag', 'vix_log_change_lag']
SETS = {'Constant': [], 'Controls': CONTROLS, 'ControlsVIX': CONTROLS+VIX_FEATURES}
LABELS = ['below15', '15to20', '20to30', '30plus']


def period_masks(dates):
    return {'full': np.ones(len(dates), dtype=bool),
            'earlier': np.asarray(dates < '2024-01-01'), 'later': np.asarray(dates >= '2024-01-01')}


def build_panel():
    daily = pd.read_csv(RETURNS)
    prices = pd.read_csv(PRICES, index_col='date').SPY
    vix = pd.read_csv(VIX, index_col='date').close.reindex(prices.index)
    r = prices.pct_change(fill_method=None)
    features = pd.DataFrame({'vix_close': vix, 'vix_lag': vix.shift(1),
        'log_vix_lag': np.log(vix).shift(1),
        'vix_log_change_same': np.log(vix).diff(),
        'vix_log_change_lag': np.log(vix).diff().shift(1),
        'vix_pct_change_same': vix.pct_change(fill_method=None),
        'spy_return_lag': r.shift(1),
        'log_spy_rv20_lag': np.log(r.rolling(20).std(ddof=1)*np.sqrt(252)).shift(1),
        'previous_session': pd.Series(prices.index, index=prices.index).shift(1)})
    wide = daily.pivot(index='date', columns='model', values='gross_return').sort_index()
    assert list(wide.columns) == ['EFA3', 'PCA3'] and len(wide) == 2446
    panel = wide.join(features, how='left')
    assert not panel.isna().any().any(), panel.isna().sum().to_dict()
    assert (panel.previous_session.to_numpy() < panel.index.to_numpy()).all()
    for model in MODELS:
        original = daily.loc[daily.model == model].set_index('date').sort_index()
        assert np.array_equal(panel[model].values, original.gross_return.values)
        assert np.array_equal(panel.previous_session.values, original.signal_date.values)
    panel['vix_bin'] = pd.cut(panel.vix_lag, [0,15,20,30,np.inf], right=False, labels=LABELS)
    panel['same_change_bin'] = pd.cut(panel.vix_pct_change_same, [-np.inf,-.05,0,.05,np.inf],
        right=False, labels=['below-5pct','-5pct_to0','0to5pct','5pct_plus'])
    panel.index.name = 'date'
    return panel


def resample_indices(n, block, seed):
    rng = np.random.default_rng(seed)
    starts = rng.integers(0,n,size=(DRAW,int(np.ceil(n/block))))
    return ((starts[:,:,None]+np.arange(block)) % n).reshape(DRAW,-1)[:,:n]


def conditional_stats(panel):
    rows, contrasts, corrs, regressions = [], [], [], []
    for period, mask in period_masks(panel.index).items():
        sub = panel.loc[mask]
        bootstrap = {b: resample_indices(len(sub),b,SEED+b) for b in [60,20]}
        for model in MODELS:
            r = sub[model].to_numpy()*1e4
            for category, labels in [('vix_bin',LABELS), ('same_change_bin',['below-5pct','-5pct_to0','0to5pct','5pct_plus'])]:
                for label in labels:
                    selected = sub[category].eq(label).to_numpy()
                    values = r[selected]
                    row = dict(model=model,period=period,category=category,bin=label,days=len(values),
                        mean_bps=values.mean(), median_bps=np.median(values), win_rate=np.mean(values>0),
                        mean_abs_bps=np.mean(np.abs(values)), daily_std_bps=values.std(ddof=1),
                        annualized_conditional_vol_pct=values.std(ddof=1)*np.sqrt(252)/100,
                        worst_bps=values.min(), best_bps=values.max())
                    for block, ix in bootstrap.items():
                        count=selected[ix].sum(axis=1)
                        boot=np.divide((r*selected)[ix].sum(axis=1),count,
                                       out=np.full(DRAW,np.nan),where=count>0)
                        row[f'ci{block}_low'],row[f'ci{block}_high']=np.nanpercentile(boot,[2.5,97.5])
                        row[f'valid_bootstrap_draws_{block}']=int((count>0).sum())
                    rows.append(row)
            high = sub.vix_lag.ge(20).to_numpy()
            row = dict(model=model,period=period,contrast='VIX>=20_minus_below20',
                       high_days=int(high.sum()),low_days=int((~high).sum()),
                       difference_bps=r[high].mean()-r[~high].mean())
            for block, ix in bootstrap.items():
                hi=high[ix]; rr=r[ix]
                diff=(rr*hi).sum(axis=1)/hi.sum(axis=1)-(rr*(~hi)).sum(axis=1)/(~hi).sum(axis=1)
                row[f'ci{block}_low'],row[f'ci{block}_high']=np.percentile(diff,[2.5,97.5])
            contrasts.append(row)
            for feature in ['vix_lag','vix_log_change_lag','vix_log_change_same']:
                for target, y in [('return',r),('absolute_return',np.abs(r))]:
                    x=sub[feature].to_numpy()
                    corrs.append(dict(model=model,period=period,feature=feature,target=target,
                        pearson=np.corrcoef(x,y)[0,1],spearman=spearmanr(x,y).statistic,days=len(y)))
            designs = {'VIXOnly':VIX_FEATURES,'Controls':CONTROLS,'ControlsVIX':CONTROLS+VIX_FEATURES,
                       'SameDayDiagnostic':CONTROLS+VIX_FEATURES+['vix_log_change_same']}
            for target,y in [('return',r),('absolute_return',np.abs(r))]:
                for design,columns in designs.items():
                    x=np.column_stack([np.ones(len(sub)),sub[columns].to_numpy()])
                    beta,se,r2=hac_ols(x,y)
                    for name,b,s in zip(['intercept']+columns,beta,se):
                        regressions.append(dict(model=model,period=period,target=target,design=design,
                            term=name,coefficient=b,hac20_se=s,ci_low=b-1.96*s,ci_high=b+1.96*s,
                            normal_p_descriptive=2*norm.sf(abs(b/s)) if s>0 else np.nan,r_squared=r2,
                            observations=len(y),condition_number=np.linalg.cond(x)))
    return pd.DataFrame(rows),pd.DataFrame(contrasts),pd.DataFrame(corrs),pd.DataFrame(regressions)


def hac_ols(x,y,lags=20):
    beta=np.linalg.lstsq(x,y,rcond=None)[0]
    resid=y-x@beta; scores=x*resid[:,None]
    meat=scores.T@scores
    for lag in range(1,min(lags,len(y)-1)+1):
        cross=scores[lag:].T@scores[:-lag]
        meat+=(1-lag/(lags+1))*(cross+cross.T)
    bread=np.linalg.inv(x.T@x)
    cov=bread@meat@bread*len(y)/(len(y)-x.shape[1])
    se=np.sqrt(np.maximum(0,np.diag(cov)))
    return beta,se,1-np.sum(resid**2)/np.sum((y-y.mean())**2)


def forecasts(panel):
    records=[]
    for start in range(504,len(panel),21):
        train=panel.iloc[:start]; test=panel.iloc[start:start+21]
        for model in MODELS:
            for target in ['return','absolute_return']:
                yt=train[model].to_numpy()*1e4
                yy=test[model].to_numpy()*1e4
                if target=='absolute_return':
                    yt=np.abs(yt); yy=np.abs(yy)
                for design,columns in SETS.items():
                    # Scaling uses training information only; intercept is unpenalized.
                    mu=train[columns].mean().to_numpy(); sd=train[columns].std(ddof=1).to_numpy()
                    x=np.column_stack([np.ones(len(train)),(train[columns].to_numpy()-mu)/sd])
                    xx=np.column_stack([np.ones(len(test)),(test[columns].to_numpy()-mu)/sd])
                    beta=np.linalg.lstsq(x,yt,rcond=None)[0]
                    pred=xx@beta
                    if target=='absolute_return': pred=np.maximum(0,pred)
                    for date,actual,predicted in zip(test.index,yy,pred):
                        records.append(dict(date=date,model=model,target=target,design=design,
                            training_end=train.index[-1],training_n=len(train),
                            actual_bps=actual,predicted_bps=predicted,
                            squared_error=(actual-predicted)**2))
    pred=pd.DataFrame(records)
    metrics=[]; comparisons=[]
    for period,mask in period_masks(np.array(sorted(pred.date.unique()))).items():
        dates=np.array(sorted(pred.date.unique()))[mask]
        subset=pred.loc[pred.date.isin(dates)]
        effects=[]; keys=[]
        for model in MODELS:
            for target in ['return','absolute_return']:
                p=subset.loc[(subset.model==model)&(subset.target==target)]
                for design in SETS:
                    a=p.loc[p.design==design]
                    metrics.append(dict(model=model,target=target,period=period,design=design,
                        days=len(a),mse_bps_squared=a.squared_error.mean(),
                        mae_bps=np.abs(a.actual_bps-a.predicted_bps).mean(),
                        actual_mean_bps=a.actual_bps.mean(),predicted_mean_bps=a.predicted_bps.mean()))
                w=p.pivot(index='date',columns='design',values='squared_error').sort_index()
                diff=(w.ControlsVIX-w.Controls).to_numpy()
                effects.append(diff); keys.append((model,target,w.Controls.mean()))
        diffs=np.column_stack(effects); observed=diffs.mean(axis=0)
        intervals={}
        for block in [60,20]:
            ix=resample_indices(len(dates),block,SEED+100+block)
            means=diffs[ix].mean(axis=1)
            se=means.std(axis=0,ddof=1)
            max_stat=np.max(np.abs((means-observed)/se),axis=1)
            critical=np.percentile(max_stat,95)
            intervals[block]=(np.percentile(means,[2.5,97.5],axis=0),observed-critical*se,observed+critical*se)
        for i,(model,target,base_mse) in enumerate(keys):
            row=dict(model=model,target=target,period=period,days=len(dates),
                loss_difference_bps_squared=observed[i],mse_improvement_pct=-observed[i]/base_mse*100)
            for block,(point,low,high) in intervals.items():
                row[f'ci{block}_low'],row[f'ci{block}_high']=point[:,i]
                row[f'sim{block}_low'],row[f'sim{block}_high']=low[i],high[i]
            comparisons.append(row)
    return pred,pd.DataFrame(metrics),pd.DataFrame(comparisons)


def figures(panel,bins,forecast,forecast_metrics):
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    dates=pd.to_datetime(panel.index)
    fig,axes=plt.subplots(3,1,figsize=(12,9),sharex=True,layout='constrained',height_ratios=[1.3,1,1])
    for model,color in [('PCA3','#247ba0'),('EFA3','#ed9b40')]:
        axes[0].plot(dates,100000*np.cumprod(1+panel[model]),label=model,color=color)
    axes[0].set_ylabel('Account value from $100,000'); axes[0].legend()
    axes[1].plot(dates,panel.vix_lag,color='#6a4c93',lw=.8)
    axes[1].set_ylabel('Previous-session VIX')
    axes[2].plot(dates,panel.PCA3.abs()*1e4,color='#247ba0',alpha=.35,lw=.5,label='Daily absolute return')
    axes[2].plot(dates,panel.PCA3.abs().rolling(20).mean()*1e4,color='#c0392b',label='20-session mean absolute return')
    axes[2].set_ylabel('PCA absolute return (bps)'); axes[2].legend()
    for ax in axes:
        ax.axvline(pd.Timestamp('2024-01-01'),ls='--',color='#777',lw=.8)
        ax.grid(alpha=.2); ax.margins(x=.01)
    fig.suptitle('Frozen factor-neutral strategy and VIX\nGross/pre-fee, unit gross; no new gate. Dashed line: previously examined later period')
    fig.savefig(OUT/'01_returns_and_vix.png',dpi=160); plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
    for j,period in enumerate(['full','earlier','later']):
        for model,offset,color in [('PCA3',-.12,'#247ba0'),('EFA3',.12,'#ed9b40')]:
            q=bins.loc[(bins.model==model)&(bins.period==period)&(bins.category=='vix_bin')].set_index('bin').loc[LABELS]
            xx=np.arange(4)+offset
            axes[0,j].errorbar(xx,q.mean_bps,yerr=np.vstack([q.mean_bps-q.ci60_low,q.ci60_high-q.mean_bps]),
                fmt='o',capsize=3,color=color,label=model)
            axes[1,j].plot(xx,q.annualized_conditional_vol_pct,'o-',color=color,label=model)
            if model=='PCA3':
                axes[0,j].set_xticks(np.arange(4),[f'{name}\nn={n}' for name,n in zip(LABELS,q.days)],fontsize=8)
        axes[0,j].set_title(period); axes[0,j].axhline(0,color='#777',lw=.8)
        axes[1,j].set_xticks(np.arange(4),LABELS,fontsize=8)
        axes[0,j].set_ylabel('Mean gross return (bps/day)')
        axes[1,j].set_ylabel('Conditional annualized volatility (%)')
        for ax in axes[:,j]:ax.grid(alpha=.2)
    axes[0,0].legend()
    fig.suptitle('Prior-session VIX: mean return and risk are different questions\nPointwise 95% block60 intervals; fixed bins; conditional annualization is a scale summary, not a portfolio CAGR')
    fig.savefig(OUT/'02_lagged_vix_bins.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    for j,(feature,label) in enumerate([('vix_log_change_lag','Previous-session VIX log change (%) — known before entry'),
                                      ('vix_log_change_same','Same-day VIX log change (%) — descriptive only')]):
        x=panel[feature].to_numpy()*100
        for i,(y,label_y) in enumerate([(panel.PCA3.to_numpy()*1e4,'PCA signed return (bps)'),
                                       (np.abs(panel.PCA3.to_numpy())*1e4,'PCA absolute return (bps)')]):
            axes[i,j].scatter(x,y,s=7,alpha=.2,color='#247ba0')
            slope,intercept=np.polyfit(x,y,1); lim=np.array([x.min(),x.max()])
            axes[i,j].plot(lim,intercept+slope*lim,color='#c0392b')
            axes[i,j].set(xlabel=label,ylabel=label_y);axes[i,j].grid(alpha=.2)
            axes[i,j].text(.02,.96,f'Pearson r = {np.corrcoef(x,y)[0,1]:+.3f}',transform=axes[i,j].transAxes,va='top')
    fig.suptitle('VIX changes versus frozen PCA returns: timing of information matters')
    fig.savefig(OUT/'03_vix_change_scatter.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,5.2),layout='constrained')
    for ax,target,title in zip(axes,['return','absolute_return'],['Mean-return forecast','Absolute-return (risk) forecast']):
        q=forecast.loc[(forecast.model=='PCA3')&(forecast.target==target)].set_index('period').loc[['full','earlier','later']]
        base=forecast_metrics.loc[(forecast_metrics.model=='PCA3')&(forecast_metrics.target==target)&
            (forecast_metrics.design=='Controls')].set_index('period').loc[q.index,'mse_bps_squared']
        lower=-q.sim60_high/base*100;upper=-q.sim60_low/base*100
        ax.bar(np.arange(3),q.mse_improvement_pct,color='#247ba0',yerr=np.vstack([
            q.mse_improvement_pct-lower,upper-q.mse_improvement_pct]),capsize=4)
        ax.set_xticks(np.arange(3),['All forecast dates','Before 2024','2024 onward'])
        ax.axhline(0,color='#555',lw=.8);ax.set_title(title);ax.set_ylabel('MSE reduction from adding lagged VIX (%)')
        ax.grid(axis='y',alpha=.2)
    fig.suptitle('Expanding PCA forecasts: adding lagged VIX to ordinary controls\nPositive bars mean lower error; simultaneous 95% block60 intervals\nNo forecast is used to trade',fontsize=11)
    fig.savefig(OUT/'04_forecast_comparison.png',dpi=160,bbox_inches='tight');plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    panel=build_panel();panel.to_csv(OUT/'aligned_daily_panel.csv')
    panel.loc[panel.vix_lag.ge(30)].to_csv(OUT/'high_vix_days.csv')
    bins,contrasts,corrs,reg=conditional_stats(panel)
    pred,metrics,comparison=forecasts(panel)
    for name,frame in [('conditional_returns',bins),('high_low_contrast',contrasts),('correlations',corrs),
                       ('regressions_hac',reg),('forecast_predictions',pred),('forecast_metrics',metrics),('forecast_comparisons',comparison)]:
        frame.to_csv(OUT/f'{name}.csv',index=False)
    annual=[]
    for year,sub in panel.groupby(panel.index.str[:4]):
        for model in MODELS:
            r=sub[model].values
            annual.append(dict(year=year,model=model,days=len(sub),return_pct=(np.prod(1+r)-1)*100,
                mean_bps=r.mean()*1e4,vol_pct=r.std(ddof=1)*np.sqrt(252)*100,
                mean_prior_vix=sub.vix_lag.mean(),high_vix_fraction=sub.vix_lag.ge(30).mean()))
    pd.DataFrame(annual).to_csv(OUT/'annual_context.csv',index=False)
    figures(panel,bins,comparison,metrics)
    inputs=[RETURNS,VIX,PRICES,Path(__file__),OUT/'specification.json']
    outputs=sorted(OUT.glob('*.csv'))+sorted(OUT.glob('*.png'))
    manifest=dict(bootstrap_draws=DRAW,seed=SEED,source_strategy_unchanged=True,
        days=len(panel),start=panel.index.min(),end=panel.index.max(),
        forecast_start=pred.date.min(),forecast_end=pred.date.max(),
        sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs+outputs})
    (OUT/'run_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('PCA lagged VIX bins:')
    print(bins.loc[(bins.model=='PCA3')&(bins.category=='vix_bin'),
        ['period','bin','days','mean_bps','ci60_low','ci60_high','annualized_conditional_vol_pct']].to_string(index=False))
    print('Forecast comparisons:')
    print(comparison[['model','target','period','days','mse_improvement_pct','loss_difference_bps_squared','sim60_low','sim60_high']].to_string(index=False))


if __name__=='__main__':main()
