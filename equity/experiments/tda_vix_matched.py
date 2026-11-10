"""Matched forecast comparison: ordinary controls, VIX, then cached TDA features.

Run in tda. Uses frozen returns, features, anchors and completed-label memberships.
No new topology or trading policy is computed.
"""
import hashlib
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/tda-mpl')
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).with_suffix('')
OLD=ROOT/'equity/experiments/equity_full_basket_states'
CONTEXT=ROOT/'equity/literature/tda_regimes_vix_2026-11-04/cached_tda_vix_context.csv'
TARGETS={'risk':'target_logRMS','mean':'target_mean_bps'}
VIX=['vix_log_level','vix_completed_log_change','vix_band20to30']
SEED=2026102951
COLORS={'HistoryMean':'#888888','Controls':'#222222','ControlsVIX':'#8e44ad',
    'VIXRawLevel':'#247ba0','VIXRawChange':'#d97706','VIXResidualLevel':'#2a9d8f','VIXResidualChange':'#b85b72'}
NAMES={'HistoryMean':'Historical mean','Controls':'Ordinary controls','ControlsVIX':'Controls + VIX',
    'VIXRawLevel':'+ Raw levels','VIXRawChange':'+ Raw changes',
    'VIXResidualLevel':'+ Residual levels','VIXResidualChange':'+ Residual changes'}


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def setup():
    config=json.loads((OLD/'specification.json').read_text())
    base=config['ordinary_controls']; additions=config['augmentations']
    assert len(base)==33 and len(additions)==4
    models={'HistoryMean':[],'Controls':base,'ControlsVIX':base+VIX,
        **{'VIX'+name:base+VIX+cols for name,cols in additions.items()}}
    f=pd.read_csv(OLD/'state_features_and_targets.csv')
    v=pd.read_csv(CONTEXT)
    assert len(f)==len(v)==490
    f=f.merge(v[['formation_date','topology_feature_end','first_execution','vix_observation_date',
        'vix_close_before_entry','vix_log_change_before_entry','vix_band20to30']],
        on='formation_date',how='left',validate='one_to_one').sort_values('anchor').reset_index(drop=True)
    assert (f.history_end==f.topology_feature_end).all()
    assert (f.target_start==f.first_execution).all()
    assert (f.vix_observation_date==f.formation_date).all()
    assert (f.vix_observation_date<f.target_start).all()
    f['vix_log_level']=np.log(f.vix_close_before_entry)
    f['vix_completed_log_change']=f.vix_log_change_before_entry
    assert np.isfinite(f[VIX]).all().all()
    old_predictions=pd.read_csv(OLD/'walk_forward_predictions.csv')
    members=pd.read_csv(OLD/'training_membership.csv.gz')
    return f,old_predictions,members,models,additions


def ridge(x,y,current):
    mu=x.mean(axis=0);sd=x.std(axis=0,ddof=0);sd=np.where(sd>1e-10,sd,1.)
    z=(x-mu)/sd;intercept=y.mean()
    beta=np.linalg.solve(z.T@z+len(y)*np.eye(z.shape[1]),z.T@(y-intercept))
    return float(intercept+((current-mu)/sd)@beta)


def indices(n,period_index):
    rng=np.random.default_rng(SEED+period_index)
    starts=rng.integers(n,size=(1000,int(np.ceil(n/12))))
    return ((starts[:,:,None]+np.arange(12))%n).reshape(1000,-1)[:,:n]


def bands(values,ix):
    observed=values.mean(axis=0);boot=values[ix].mean(axis=1)
    low,high=np.quantile(boot,[.025,.975],axis=0)
    se=boot.std(axis=0,ddof=1)
    z=np.divide(boot-observed,se,out=np.zeros_like(boot),where=se>1e-12)
    critical=np.quantile(np.max(np.abs(z),axis=1),.95)
    return observed,low,high,observed-critical*se,observed+critical*se


def fit(f,old,members,models):
    indexed=f.set_index('anchor'); groups=members.groupby('prediction_anchor',sort=False)
    predictions=[];diagnostics=[];maximum_old_error=0.
    for p in old.itertuples():
        current=indexed.loc[p.anchor]
        train_ids=groups.get_group(p.anchor).training_anchor.to_numpy()
        train=indexed.loc[train_ids]
        assert len(train)==p.training_labels and len(train)>=104
        assert (train.formation_date<p.formation_date).all()
        assert (train.target_end<=p.formation_date).all()
        assert train.target_end.max()==p.latest_training_target_end
        assert train[list(TARGETS.values())].notna().all().all()
        row={name:getattr(p,name) for name in ['anchor','signal_index','formation_date','target_start',
            'target_end','target_mean_bps','score_period','training_labels','latest_training_target_end']}
        row.update(target_logRMS=current.target_logRMS,target_RMS_bps=current.target_RMS_bps,
            vix_observation_date=current.vix_observation_date,vix_close_before_entry=current.vix_close_before_entry,
            topology_feature_end=current.topology_feature_end)
        for target,column in TARGETS.items():
            y=train[column].to_numpy()
            for model,cols in models.items():
                if cols:
                    x=train[cols].to_numpy();now=current[cols].to_numpy(dtype=float)
                    assert np.isfinite(x).all() and np.isfinite(now).all()
                    prediction=ridge(x,y,now)
                else:prediction=float(y.mean())
                row[target+'_'+model]=prediction
                diagnostics.append(dict(anchor=p.anchor,target=target,model=model,features=len(cols),
                    training_labels=len(train),latest_training_target_end=train.target_end.max(),
                    first_execution=p.target_start,prediction=prediction))
                if model in ['HistoryMean','Controls']:
                    err=abs(prediction-getattr(p,target+'_'+model));maximum_old_error=max(maximum_old_error,err)
                    assert err<1e-10
        predictions.append(row)
    return pd.DataFrame(predictions),pd.DataFrame(diagnostics),maximum_old_error


def summarize(predictions,models,additions):
    metrics=[];comparisons=[];losses=[]
    for pi,period in enumerate(['development','later']):
        p=predictions.loc[predictions.score_period.eq(period)&predictions.target_mean_bps.notna()].sort_values('formation_date')
        assert len(p)==(233 if period=='development' else 138)
        ix=indices(len(p),pi)
        for target,column in TARGETS.items():
            y=p[column].to_numpy();errors={name:(p[target+'_'+name].to_numpy()-y)**2 for name in models}
            for model in models:
                forecast=p[target+'_'+model].to_numpy();boot=errors[model][ix].mean(axis=1)
                metrics.append(dict(period=period,target=target,model=model,forecasts=len(p),
                    MSE=errors[model].mean(),MSE_low=np.quantile(boot,.025),MSE_high=np.quantile(boot,.975),
                    MAE_native=np.abs(forecast-y).mean(),
                    RMS_MAE_bps=np.abs(np.exp(forecast)-np.exp(y)).mean() if target=='risk' else np.nan,
                    improvement_vs_Controls_pct=(1-errors[model].mean()/errors['Controls'].mean())*100,
                    improvement_vs_ControlsVIX_pct=(1-errors[model].mean()/errors['ControlsVIX'].mean())*100))
                losses.extend(dict(anchor=a,formation_date=date,period=period,target=target,model=model,
                    actual=actual,prediction=prediction,squared_error=loss)
                    for a,date,actual,prediction,loss in zip(p.anchor,p.formation_date,y,forecast,errors[model]))
            families=[('VIX_increment','Controls',['ControlsVIX']),
                ('TDA_beyond_VIX','ControlsVIX',['VIX'+name for name in additions]),
                ('joint_beyond_Controls','Controls',['VIX'+name for name in additions])]
            for family,reference,names in families:
                matrix=np.column_stack([errors[name]-errors[reference] for name in names])
                b=bands(matrix,ix)
                for i,name in enumerate(names):
                    # A single VIX comparison uses the pointwise percentile interval.
                    lo,hi=(b[1][i],b[2][i]) if len(names)==1 else (b[3][i],b[4][i])
                    denominator=errors[reference].mean()
                    comparisons.append(dict(period=period,target=target,family=family,model=name,
                        reference=reference,forecasts=len(p),loss_difference=b[0][i],point95_low=b[1][i],
                        point95_high=b[2][i],family95_low=lo,family95_high=hi,
                        improvement_pct=-b[0][i]/denominator*100,
                        improvement_low_pct=-hi/denominator*100,improvement_high_pct=-lo/denominator*100,
                        better_direction='negative_loss_difference'))
    return pd.DataFrame(metrics),pd.DataFrame(comparisons),pd.DataFrame(losses)


def figures(p,metrics,comparisons,models):
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    names=list(models)
    fig,axes=plt.subplots(2,2,figsize=(14,9),layout='constrained')
    for i,period in enumerate(['development','later']):
        for j,target in enumerate(TARGETS):
            q=metrics.loc[(metrics.period==period)&(metrics.target==target)].set_index('model').loc[names]
            relative=100*(1-q.improvement_vs_Controls_pct/100)
            axes[i,j].scatter(np.arange(len(names)),relative,c=[COLORS[name] for name in names],s=45)
            axes[i,j].axhline(100,color='#555',ls='--',lw=.8)
            axes[i,j].set_xticks(np.arange(len(names)),[NAMES[name] for name in names],rotation=30,ha='right',fontsize=8)
            axes[i,j].set(title=f'{period}: '+('future log-RMS risk' if target=='risk' else 'future mean return'),
                ylabel='Squared forecast error: ordinary controls = 100')
            axes[i,j].grid(axis='y',alpha=.2)
    fig.suptitle('Matched forecast accuracy: ordinary controls, VIX, then cached TDA\nLower is better; point estimates only. Paired uncertainty is shown separately.',fontsize=13)
    fig.savefig(OUT/'01_matched_forecast_errors.png',dpi=160,bbox_inches='tight');plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(14,8),layout='constrained')
    ordered=['ControlsVIX']+['VIX'+name for name in ['RawLevel','RawChange','ResidualLevel','ResidualChange']]
    labels=['VIX added to ordinary controls','Raw levels added to VIX baseline','Raw changes added to VIX baseline',
        'Residual levels added to VIX baseline','Residual changes added to VIX baseline']
    for i,period in enumerate(['development','later']):
        for j,target in enumerate(TARGETS):
            q=comparisons.loc[(comparisons.period==period)&(comparisons.target==target)&
                comparisons.family.isin(['VIX_increment','TDA_beyond_VIX'])].set_index('model').loc[ordered]
            ax=axes[i,j]
            for k,(name,row) in enumerate(q.iterrows()):
                ax.errorbar(row.improvement_pct,k,xerr=[[row.improvement_pct-row.improvement_low_pct],
                    [row.improvement_high_pct-row.improvement_pct]],fmt='o',color=COLORS[name],capsize=3)
            ax.set_yticks(np.arange(5),labels,fontsize=8);ax.invert_yaxis()
            ax.axvline(0,color='#555',lw=.9);ax.grid(axis='x',alpha=.2)
            ax.set(title=f'{period}: '+('risk forecast' if target=='risk' else 'mean-return forecast'),
                xlabel='Reduction in matched squared forecast error (%)')
    fig.suptitle('Incremental prediction: positive means lower error\n95% pointwise interval for VIX; simultaneous four-addition intervals for TDA. No trading gate.',fontsize=12)
    fig.savefig(OUT/'02_incremental_uncertainty.png',dpi=160,bbox_inches='tight');plt.close(fig)
    later=p.loc[p.score_period.eq('later')&p.target_mean_bps.notna()].sort_values('formation_date')
    dates=pd.to_datetime(later.target_start)
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True,layout='constrained')
    for ax,target,column in zip(axes,TARGETS,['target_RMS_bps','target_mean_bps']):
        ax.plot(dates,later[column],color='#999',lw=1,label='Realized next20 outcome')
        for model in ['Controls','ControlsVIX']:
            values=np.exp(later['risk_'+model]) if target=='risk' else later['mean_'+model]
            ax.plot(dates,values,color=COLORS[model],lw=1.2,label=NAMES[model])
        ax.set_ylabel('Next20 RMS (bps)' if target=='risk' else 'Next20 mean (bps/day)')
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Later outcomes versus the two ordinary baselines\nPredictions use only completed past labels; overlapping next20 outcomes are not independent',fontsize=12)
    fig.savefig(OUT/'03_baseline_predictions.png',dpi=160,bbox_inches='tight');plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    inputs=[OLD/'specification.json',OLD/'state_features_and_targets.csv',OLD/'walk_forward_predictions.csv',
        OLD/'training_membership.csv.gz',OLD/'forecast_metrics.csv',CONTEXT,
        ROOT/'equity/experiments/equity_efa_vs_pca/daily_gross_returns.csv']
    protected={str(path.relative_to(ROOT)):digest(path) for path in inputs}
    f,old,members,models,additions=setup()
    f.to_csv(OUT/'state_features_with_vix.csv',index=False)
    predictions,diagnostics,max_error=fit(f,old,members,models)
    metrics,comparisons,losses=summarize(predictions,models,additions)
    for name,frame in [('walk_forward_predictions',predictions),('fit_diagnostics',diagnostics),
        ('forecast_metrics',metrics),('paired_comparisons',comparisons),('scored_losses',losses)]:
        frame.to_csv(OUT/f'{name}.csv',index=False)
    # Archived ordinary-control point losses must reproduce exactly on matched score dates.
    old_metrics=pd.read_csv(OLD/'forecast_metrics.csv')
    for row in metrics.loc[metrics.model.isin(['HistoryMean','Controls'])].itertuples():
        archived=old_metrics.loc[(old_metrics.period==row.period)&(old_metrics.target==row.target)&
            (old_metrics.model==row.model)].iloc[0]
        assert np.isclose(row.MSE,archived.MSE,rtol=1e-12,atol=1e-12)
    figures(predictions,metrics,comparisons,models)
    assert all(digest(ROOT/path)==value for path,value in protected.items())
    config=json.loads((OUT/'specification.json').read_text());config['model_columns']=models
    (OUT/'executed_configuration.json').write_text(json.dumps(config,indent=2)+'\n')
    outputs=sorted(OUT.glob('*.csv'))+sorted(OUT.glob('*.png'))+[OUT/'executed_configuration.json',OUT/'specification.json',Path(__file__)]
    summary=dict(predictions=len(predictions),fits=len(diagnostics),feature_rows=len(f),
        first_prediction=predictions.formation_date.min(),last_prediction=predictions.formation_date.max(),
        max_archived_forecast_difference=max_error,score_counts={'development':233,'later':138},
        original_strategy_unchanged=True,no_new_gate=True,protected_sha256=protected,
        output_sha256={str(path.relative_to(ROOT)):digest(path) for path in outputs})
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('FORECAST METRICS\n'+metrics[['period','target','model','MSE','RMS_MAE_bps','improvement_vs_Controls_pct',
        'improvement_vs_ControlsVIX_pct']].round(6).to_string(index=False))
    print('INCREMENTS\n'+comparisons.loc[comparisons.family!='joint_beyond_Controls',
        ['period','target','family','model','improvement_pct','family95_low','family95_high']].round(6).to_string(index=False))
    print('Archived forecast max difference',max_error)


if __name__=='__main__':main()
