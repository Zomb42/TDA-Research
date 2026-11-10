"""Labeled H0 relationship changes attached to frozen holdings. Run in tda."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/tda-mpl')
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
from pathlib import Path
import gzip
import hashlib
import json
import time
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage,cophenet,fcluster
from scipy.spatial.distance import squareform
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from tda_residual_shock import inputs,past_fit

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).with_suffix('')
DATA=ROOT/'market_data/datasets/equity_daily_expanded_2016_2026-10-27'
CFG=json.loads((OUT/'specification.json').read_text())
BASE=CFG['ordinary_features']
AVG=['average_log_tree_moment','average_signed_tree_change','average_weighted_membership_change']
H0=['h0_log_tree_moment','h0_signed_tree_change','h0_weighted_membership_change']
MODELS={'ControlsVIX':BASE,'AverageTree':BASE+AVG,'H0Tree':BASE+H0,'BothTrees':BASE+AVG+H0}
TARGETS=['second_moment','downside_moment','mean']
PAIRS=[('H0Tree','ControlsVIX'),('AverageTree','ControlsVIX'),('BothTrees','AverageTree')]
FLOOR=1e-8


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def hierarchy(corr,method):
    distance=np.sqrt(np.maximum(2*(1-np.clip(corr,-1,1)),0));np.fill_diagonal(distance,0)
    tree=linkage(squareform(distance,checks=False),method=method)
    kernel=1-squareform(cophenet(tree))/2
    return tree,kernel


def merge_integral(tree,v):
    n=len(v);mass=np.zeros(2*n-1);mass[:n]=v
    result=float(v@v)
    for j,(a,b,d,_) in enumerate(tree):
        a,b=int(a),int(b);result+=2*mass[a]*mass[b]*(1-d/2);mass[n+j]=mass[a]+mass[b]
    return result


def tree_features(k,kprev,v):
    diagonal=v@v
    value=float(v@k@v)
    assert value>-1e-9
    return [np.log(max(value,FLOOR)),float(v@(k-kprev)@v/max(diagonal,FLOOR)),
        float(np.sum(np.outer(abs(v),abs(v))*abs(k-kprev))/max(abs(v).sum()**2,FLOOR))]


def construction_checks():
    corr=np.eye(4);corr[0,1]=corr[1,0]=corr[2,3]=corr[3,2]=.8
    perm=np.array([0,2,1,3]);other=corr[np.ix_(perm,perm)];v=np.array([.25,.25,-.25,-.25])
    records=[]
    for method in ['single','average']:
        tree,k=hierarchy(corr,method);tree2,k2=hierarchy(other,method)
        assert np.allclose(np.linalg.eigvalsh(corr),np.linalg.eigvalsh(other))
        assert np.allclose(np.sort(cophenet(tree)),np.sort(cophenet(tree2)))
        assert np.allclose(k2,k[np.ix_(perm,perm)])
        assert np.isclose(v@k@v,merge_integral(tree,v))
        assert np.isclose(v@k@v,(-v)@k@(-v))
        assert np.isclose(v@k@v,v[perm]@k2@v[perm])
        assert not np.isclose(v@k@v,v@k2@v)
        assert np.linalg.eigvalsh(k).min()>-1e-12
        # Exact interval-weighted threshold partition integration, separate from the matrix formula.
        levels=np.r_[0,np.unique(tree[:,2]),2.];integral=0.
        for lo,hi in zip(levels[:-1],levels[1:]):
            labels=fcluster(tree,(lo+hi)/2,criterion='distance')
            integral+=(hi-lo)/2*sum(v[labels==label].sum()**2 for label in np.unique(labels))
        assert np.isclose(integral,v@k@v)
        records.append(dict(method=method,same_side_tree_proxy=float(v@k@v),opposite_side_tree_proxy=float(v@k2@v),
            same_side_covariance_variance=float(v@corr@v),opposite_side_covariance_variance=float(v@other@v)))
    (OUT/'construction_checks.json').write_text(json.dumps({'passed':True,'synthetic':True,'cases':records,
        'threshold_integration':True,'merge_integration':True,'signed_holdings_identity':True,
        'global_sign_invariance':True,'label_and_holdings_joint_permutation':True},indent=2)+'\n')
    fig,ax=plt.subplots(figsize=(8,4),layout='constrained')
    r=records[0]
    ax.bar(np.arange(2)-.15,[r['same_side_covariance_variance'],r['opposite_side_covariance_variance']],width=.3,label='Covariance risk')
    ax.bar(np.arange(2)+.15,[r['same_side_tree_proxy'],r['opposite_side_tree_proxy']],width=.3,label='Labeled H0 exposure proxy')
    ax.set_xticks([0,1],['Correlated pairs on same side','Correlated pairs on opposite sides'])
    ax.set(ylabel='Synthetic squared-return units',title='Identical unlabeled geometry; different alignment with fixed holdings')
    ax.legend();fig.savefig(OUT/'01_identity_control.png',dpi=160);plt.close(fig)


def features():
    symbols,sectors,panel,prices,vix,old,holdings=inputs()
    x=panel[symbols].to_numpy();market=panel.SPY.to_numpy();ts=np.arange(272,len(panel)-1)
    intraday=(prices['c']/prices['o']-1)*1e4
    n=len(ts);m=len(symbols);trees=np.full((n,2,2,m-1,4),np.nan)
    records=[];examples=[];begin=time.monotonic();maximum_return_error=0.
    for d,t in enumerate(ts):
        idx=np.flatnonzero(np.isfinite(x[t-272:t]).all(axis=0));h=holdings[d,idx]
        history=intraday[t-120:t,idx];older=intraday[t-125:t-5,idx]
        assert np.isfinite(history).all() and np.isfinite(older).all()
        lw=LedoitWolf().fit(history);prior=LedoitWolf().fit(older)
        close=LedoitWolf().fit(x[t-120:t,idx]*1e4)
        cov=lw.covariance_;covprev=prior.covariance_
        sd=np.maximum(history.std(axis=0,ddof=1),1.);v=h*sd;diag=float(v@v)
        offset=max(float(h@cov@h),FLOOR);close_risk=max(float(h@close.covariance_@h),FLOOR)
        _,_,corr,pc1=past_fit(x[t-120:t,idx],market[t-120:t])
        _,_,corrprev,_=past_fit(x[t-125:t-5,idx],market[t-125:t-5])
        sleeve=history@h;down=float(np.mean(np.minimum(sleeve,0)**2))
        centered=sleeve-sleeve.mean();variance=np.mean(centered**2)
        sector_sq=sum(h[sectors[idx]==s].sum()**2 for s in np.unique(sectors[idx]))
        date=str(panel.index[t].date());entry=str(panel.index[t+1].date());previous=str(panel.index[t-1].date())
        trailing=old.loc[old.date.le(date)].tail(20).gross_return.to_numpy()*1e4
        trmean=float(trailing.mean()) if len(trailing) else 0.
        trrms=np.log(max(float(np.mean(trailing**2)),FLOOR))/2 if len(trailing) else 0.
        trdown=np.log(max(float(np.mean(np.minimum(trailing,0)**2)),FLOOR))/2 if len(trailing) else 0.
        vx=float(vix.loc[date]);actual=float(h@intraday[t+1,idx])
        maximum_return_error=max(maximum_return_error,abs(actual-old.iloc[d].gross_return*1e4))
        assert abs(actual-old.iloc[d].gross_return*1e4)<1e-9
        row=dict(day=d,signal_index=int(t),signal_date=date,entry_date=entry,history_end=previous,
            older_history_end=str(panel.index[t-6].date()),stocks=len(idx),
            period='development' if entry<'2024-01-01' else 'later',gross_bps=actual,
            risk_offset=offset,second_moment=actual**2,downside_moment=min(actual,0)**2,mean=actual)
        raw=[np.log(offset),np.log(close_risk),np.log(max(diag,FLOOR)),
            float(np.sum(np.outer(abs(h),abs(h))*abs(cov-covprev))/max(diag,FLOOR)),
            float(h@(cov-covprev)@h/max(diag,FLOOR)),float(corr[np.triu_indices(len(idx),1)].mean()),pc1,
            float(abs(h).max()),float(h@h),float(sector_sq),np.log(max(down,FLOOR)),float(sleeve.mean()),
            float(np.mean(centered**4)/max(variance**2,FLOOR)-3),trmean,trrms,trdown,
            np.log(vx),float(np.log(vx/vix.loc[previous])),int(20<=vx<30),float(market[t-20:t].std(ddof=1)*np.sqrt(252))]
        row.update(zip(BASE,raw))
        for mi,(method,columns) in enumerate([('single',H0),('average',AVG)]):
            tree,k=hierarchy(corr,method);prev,kprev=hierarchy(corrprev,method)
            trees[d,mi,0,:len(idx)-1]=tree;trees[d,mi,1,:len(idx)-1]=prev
            assert np.isclose(v@k@v,merge_integral(tree,v),atol=1e-9)
            row.update(zip(columns,tree_features(k,kprev,v)))
            if date in ['2020-03-16','2024-08-05']:
                # Illustration only: fixed rho=.5 cut; forecasts integrate every threshold.
                labels=fcluster(tree,1.,criterion='distance')
                for label in np.unique(labels):
                    take=labels==label
                    examples.append(dict(signal_date=date,method=method,component=int(label),stocks=int(take.sum()),
                        net_weight=float(h[take].sum()),gross_weight=float(abs(h[take]).sum()),
                        net_sigma_weight=float(v[take].sum()),symbols='|'.join(symbols[idx[take]])))
        records.append(row)
        if (d+1)%300==0:print(f'Attached holdings to {d+1}/{n} labeled hierarchies in {time.monotonic()-begin:.1f}s',flush=True)
    frame=pd.DataFrame(records);frame.to_csv(OUT/'state_features_and_targets.csv',index=False)
    np.savez_compressed(OUT/'labeled_hierarchies.npz',trees=trees,symbols=symbols,signal_indices=ts)
    pd.DataFrame(examples).to_csv(OUT/'fixed_date_components.csv',index=False)
    return frame,maximum_return_error


def risk_loss_gradient(theta,z,offset,y):
    eta=offset+theta[0]+z@theta[1:]
    ratio=y*np.exp(-eta)
    value=np.mean(eta+ratio)+.5*(theta[1:]@theta[1:])
    gradient=np.r_[np.mean(1-ratio),z.T@(1-ratio)/len(y)+theta[1:]]
    return float(value),gradient


def risk_fit(z,offset,y):
    initial=np.r_[np.log(np.mean(y*np.exp(-offset))),np.zeros(z.shape[1])]
    result=minimize(risk_loss_gradient,initial,args=(z,offset,y),jac=True,method='L-BFGS-B',
        options={'ftol':1e-13,'gtol':1e-9,'maxiter':1000,'maxls':50})
    theta=result.x.copy();augmented=np.c_[np.ones(len(z)),z];polish=0
    # A function-change stop can precede gradient convergence; polish the same convex objective.
    for _ in range(12):
        value,g=risk_loss_gradient(theta,z,offset,y)
        if np.max(abs(g))<1e-8:break
        ratio=y*np.exp(-offset-augmented@theta)
        hessian=augmented.T@(ratio[:,None]*augmented)/len(y)+np.diag(np.r_[0.,np.ones(z.shape[1])])
        step=np.linalg.solve(hessian,g);rate=1.
        while rate>1e-8 and risk_loss_gradient(theta-rate*step,z,offset,y)[0]>value+1e-13:
            rate/=2
        theta-=rate*step;polish+=1
    grad=float(np.max(abs(risk_loss_gradient(theta,z,offset,y)[1])))
    assert np.isfinite(result.fun) and grad<2e-6,(result.message,grad)
    return theta,grad,int(result.nit)+polish


def forecast(frame):
    params=[];diagnostics=[];rows=[];current={};calibration={};base_mean=0.
    for d in range(504,len(frame)):
        now=frame.iloc[d]
        if (d-504)%20==0:
            if (d-504)%400==0:print(f'Fitting portfolio forecasts at day {d}/{len(frame)}',flush=True)
            train=frame.iloc[:d];assert train.entry_date.max()<=now.signal_date
            offset=np.log(train.risk_offset.to_numpy())
            calibration={target:float(np.mean(train[target]/train.risk_offset)) for target in TARGETS[:2]}
            base_mean=float(train.gross_bps.mean())
            for model,columns in MODELS.items():
                x=train[columns].to_numpy();mu=x.mean(axis=0);sd=x.std(axis=0,ddof=0);sd=np.where(sd>1e-10,sd,1.)
                z=(x-mu)/sd
                for target in TARGETS:
                    y=train[target].to_numpy()
                    if target=='mean':
                        intercept=float(y.mean());coef=np.linalg.solve(z.T@z+d*np.eye(len(columns)),z.T@(y-intercept))
                        theta=np.r_[intercept,coef];grad=0.;iterations=0
                    else:theta,grad,iterations=risk_fit(z,offset,y)
                    current[(model,target)]=(mu,sd,theta)
                    params.append(dict(fit_day=d,model=model,target=target,columns=columns,mu=mu.tolist(),sd=sd.tolist(),theta=theta.tolist()))
                    diagnostics.append(dict(fit_day=d,signal_date=now.signal_date,training_dates=d,
                        latest_training_execution=train.entry_date.max(),model=model,target=target,columns=len(columns),
                        max_gradient=grad,iterations=iterations))
        for target in TARGETS:
            actual=float(now[target])
            if target=='mean':baselines={'Zero':0.,'HistoryMean':base_mean}
            else:baselines={'RawLW':float(now.risk_offset),'CalibratedLW':calibration[target]*float(now.risk_offset)}
            forecasts=baselines.copy()
            for model,columns in MODELS.items():
                mu,sd,theta=current[(model,target)]
                linear=theta[0]+((now[columns].to_numpy(dtype=float)-mu)/sd)@theta[1:]
                forecasts[model]=float(linear if target=='mean' else np.exp(np.log(now.risk_offset)+linear))
            for model,prediction in forecasts.items():
                loss=(prediction-actual)**2 if target=='mean' else np.log(prediction)+actual/prediction
                rows.append(dict(day=d,signal_date=now.signal_date,entry_date=now.entry_date,period=now.period,
                    model=model,target=target,actual=actual,prediction=prediction,loss=float(loss)))
    predictions=pd.DataFrame(rows);predictions.to_csv(OUT/'walk_forward_predictions.csv',index=False)
    pd.DataFrame(diagnostics).to_csv(OUT/'fit_diagnostics.csv',index=False)
    with gzip.open(OUT/'fit_parameters.json.gz','wt') as f:json.dump(params,f)
    return predictions


def bootstrap_indices(n,pi):
    rng=np.random.default_rng(2026110519+pi);starts=rng.integers(n,size=(1000,int(np.ceil(n/60))))
    return ((starts[:,:,None]+np.arange(60))%n).reshape(1000,-1)[:,:n]


def score(predictions):
    metrics=[];comparisons=[]
    for pi,period in enumerate(['development','later']):
        for target in TARGETS:
            frame=predictions.loc[(predictions.period==period)&(predictions.target==target)]
            wide=frame.pivot(index='day',columns='model',values='loss').sort_index();ix=bootstrap_indices(len(wide),pi)
            for model,g in frame.groupby('model',sort=False):
                y=g.actual.to_numpy();p=g.prediction.to_numpy()
                metrics.append(dict(period=period,target=target,model=model,dates=len(g),score=float(g.loss.mean()),
                    score_type='MSE_bps2' if target=='mean' else 'QLIKE',
                    calibration_ratio=float(np.mean(y/p)) if target!='mean' else np.nan,
                    realized_RMS_bps=float(np.sqrt(y.mean())) if target!='mean' else np.nan,
                    predicted_RMS_bps=float(np.sqrt(p.mean())) if target!='mean' else np.nan,
                    mean_forecast_bps=float(p.mean()) if target=='mean' else np.nan))
            differences=np.column_stack([(wide[a]-wide[b]).to_numpy() for a,b in PAIRS]);center=differences.mean(axis=0)
            boot=differences[ix].mean(axis=1);sd=boot.std(axis=0,ddof=1)
            critical=np.quantile(np.max(abs((boot-center)/np.maximum(sd,1e-15)),axis=1),.95)
            low,high=np.quantile(boot,[.025,.975],axis=0)
            for j,(model,reference) in enumerate(PAIRS):
                comparisons.append(dict(period=period,target=target,model=model,reference=reference,dates=len(wide),
                    loss_difference=center[j],point95_low=low[j],point95_high=high[j],
                    simultaneous95_low=center[j]-critical*sd[j],simultaneous95_high=center[j]+critical*sd[j],
                    mean_MSE_improvement_pct=float(-center[j]/wide[reference].mean()*100) if target=='mean' else np.nan))
    metrics=pd.DataFrame(metrics);comparisons=pd.DataFrame(comparisons)
    metrics.to_csv(OUT/'forecast_metrics.csv',index=False);comparisons.to_csv(OUT/'paired_comparisons.csv',index=False)
    return metrics,comparisons


def plots(frame,predictions,comparisons):
    fig,axes=plt.subplots(2,3,figsize=(14,7),layout='constrained')
    labels=['H0 vs controls','Average vs controls','H0 vs controls + average']
    for row,period in enumerate(['development','later']):
        for col,target in enumerate(TARGETS):
            ax=axes[row,col];g=comparisons.loc[(comparisons.period==period)&(comparisons.target==target)]
            for j,r in enumerate(g.itertuples()):
                ax.errorbar(r.loss_difference,j,xerr=[[r.loss_difference-r.simultaneous95_low],
                    [r.simultaneous95_high-r.loss_difference]],fmt='o',capsize=3,color=['#247ba0','#777777','#b85b72'][j])
            ax.axvline(0,color='black',lw=.8);ax.set_yticks(range(3),labels,fontsize=8);ax.set_ylim(2.5,-.5)
            ax.set(title=f'{period}: '+{'second_moment':'squared return','downside_moment':'squared loss','mean':'mean return'}[target],
                xlabel='Loss difference (lower is better)');ax.grid(axis='x',alpha=.2)
    fig.suptitle('Labeled relationships and portfolio exposure: matched forecasting comparison\nSimultaneous three-comparison 95% bands; 60-date blocks; no trading gate')
    fig.savefig(OUT/'02_incremental_uncertainty.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(11,6),layout='constrained',sharex=True)
    later=predictions.loc[(predictions.period=='later')&(predictions.target=='second_moment')]
    for model in ['RawLW','ControlsVIX','AverageTree','BothTrees']:
        g=later.loc[later.model==model].sort_values('day');axes[0].plot(pd.to_datetime(g.entry_date),np.sqrt(g.prediction),label=model,lw=1)
    axes[0].set(ylabel='Forecast RMS return (bps)',title='Next-session risk forecasts; not changed portfolio exposure');axes[0].legend(ncol=4,fontsize=8)
    daily=frame.loc[frame.period=='later'].iloc[:len(g)]
    axes[1].plot(pd.to_datetime(daily.entry_date),daily.h0_weighted_membership_change,label='H0',lw=1)
    axes[1].plot(pd.to_datetime(daily.entry_date),daily.average_weighted_membership_change,label='Average linkage',lw=1)
    axes[1].set(ylabel='Holdings-weighted kernel change',title='Changing labeled relationships over five sessions');axes[1].legend(fontsize=8)
    fig.savefig(OUT/'03_forecasts_and_relationship_changes.png',dpi=160);plt.close(fig)
    examples=pd.read_csv(OUT/'fixed_date_components.csv')
    fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained')
    for row,date in enumerate(['2020-03-16','2024-08-05']):
        for col,method in enumerate(['single','average']):
            ax=axes[row,col];g=examples.loc[(examples.signal_date==date)&(examples.method==method)].sort_values('gross_weight',ascending=False).head(8)
            ax.bar(np.arange(len(g))-.15,g.gross_weight,width=.3,label='Gross weight')
            ax.bar(np.arange(len(g))+.15,g.net_weight,width=.3,label='Signed net weight')
            ax.set_xticks(range(len(g)),[str(s).split('|')[0]+f' ({n})' for s,n in zip(g.symbols,g.stocks)],rotation=25,ha='right',fontsize=8)
            ax.set(title=f'{date}: {method}',ylabel='Fraction of account equity');ax.axhline(0,color='black',lw=.7)
    axes[0,0].legend(fontsize=8)
    fig.suptitle('Fixed-date component exposures at rho=0.5 (illustration only)\nForecast features integrate all thresholds; labels show first ticker and component size')
    fig.savefig(OUT/'04_named_component_exposure.png',dpi=160);plt.close(fig)


def main():
    paths=[DATA/name for name in ['returns_log.csv','bars_raw.csv','universe.csv']]+[
        ROOT/'equity/experiments/equity_efa_vs_pca/daily_gross_returns.csv',
        ROOT/'equity/experiments/equity_efa_vs_pca/positions_and_loadings.npz',
        ROOT/'equity/experiments/tda_residual_shock.py',ROOT/'equity/experiments/tda_residual_shock/summary.json',
        ROOT/'market_data/datasets/mean_reversion_context_2026-11-04/vix_daily.csv']
    protected={str(p.relative_to(ROOT)):sha(p) for p in paths}
    construction_checks();frame,error=features();predictions=forecast(frame);metrics,comparisons=score(predictions);plots(frame,predictions,comparisons)
    for p in paths:assert sha(p)==protected[str(p.relative_to(ROOT))]
    summary=dict(source_dates=len(frame),forecast_dates=len(frame)-504,max_original_return_discrepancy_bps=error,
        protected_sha256=protected,original_strategy_unchanged=True,no_new_policy=True,
        output_sha256={str(p.relative_to(ROOT)):sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in ['summary.json','README.md','audit.json']})
    summary['output_sha256'][str(Path(__file__).resolve().relative_to(ROOT))]=sha(Path(__file__))
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(comparisons.to_string(index=False),flush=True)


if __name__=='__main__':main()
