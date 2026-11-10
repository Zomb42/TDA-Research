"""Independent checks of local-shock PH, causal data, weighted fits and scores."""
import os
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[name]='1'
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from scipy.linalg import eigh
from scipy.sparse.csgraph import connected_components
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).with_name('tda_residual_shock')
DATA=ROOT/'market_data/datasets/equity_daily_expanded_2016_2026-10-27'


def check_tree(q,a,bars,owner,prominence,support):
    levels=np.unique(q[q>0]);thresholds=(np.r_[0.,levels]+np.r_[levels,levels[-1]+1])/2 if len(levels) else []
    for level in thresholds:
        take=np.flatnonzero(q>=level)
        expected=connected_components(a[np.ix_(take,take)],directed=False)[0] if len(take) else 0
        actual=int(((bars.birth>=level)&(bars.death<level)).sum())
        assert expected==actual,(level,expected,actual)
    for row in bars.itertuples():
        # Restore the exact source filtration level after CSV float round-tripping.
        death_level=0. if row.death==0 else float(q[np.argmin(abs(q-row.death))])
        assert abs(death_level-row.death)<1e-12
        peak=int(row.peak);take=np.flatnonzero(q>death_level)
        _,labels=connected_components(a[np.ix_(take,take)],directed=False)
        label=labels[np.flatnonzero(take==peak)[0]]
        assert int((labels==label).sum())==row.support
        assert np.isclose(q[peak],row.birth)
        assert bool(row.zero_censored)==(row.death==0)
    for i in np.flatnonzero(q>0):
        take=np.flatnonzero(q>=q[i]);_,labels=connected_components(a[np.ix_(take,take)],directed=False)
        members=take[labels==labels[np.flatnonzero(take==i)[0]]]
        peak=int(members[np.lexsort((members,-q[members]))[0]])
        assert owner[i]==peak
        b=bars.loc[bars.peak==peak].iloc[0]
        assert np.isclose(prominence[i],b.birth-b.death) and np.isclose(support[i],b.support/len(q))


def matrix(values,columns,names):
    return np.column_stack([values[:,names.index(c)] if not c.startswith('z_times_') else
        values[:,names.index('z')]*values[:,names.index(c[len('z_times_'):])] for c in columns])


def main():
    summary=json.loads((OUT/'summary.json').read_text());cfg=json.loads((OUT/'forecast_configuration.json').read_text())
    data=np.load(OUT/'state_panel.npz');f=data['features'];y=data['target'];pos=data['positions']
    graphs=data['graph'];owner=data['owner'];symbols=data['symbols'];names=data['feature_names'].tolist()
    context=pd.read_csv(OUT/'daily_context.csv');bt=pd.read_csv(OUT/'merge_tree_bars.csv.gz')
    saved=np.load(OUT/'stock_predictions.npz');pred=saved['predictions'];models=saved['models'].tolist()
    assert f.shape[:2]==y.shape==pos.shape==owner.shape and len(context)==2446
    assert np.isfinite(y).sum()==summary['stock_events'] and len(context)-504==summary['forecast_dates']
    raw=pd.read_csv(DATA/'returns_log.csv',index_col='date',parse_dates=True).iloc[1:]
    source=raw[symbols].to_numpy();market=raw.SPY.to_numpy();ts=data['signal_indices']
    bars=pd.read_csv(DATA/'bars_raw.csv',parse_dates=['date'])
    op=bars.pivot(index='date',columns='symbol',values='o').reindex(index=raw.index,columns=symbols).to_numpy()
    cl=bars.pivot(index='date',columns='symbol',values='c').reindex(index=raw.index,columns=symbols).to_numpy()
    vix=pd.read_csv(ROOT/'market_data/datasets/mean_reversion_context_2026-11-04/vix_daily.csv').set_index('date').close
    frozen=pd.read_csv(ROOT/'equity/experiments/equity_efa_vs_pca/daily_gross_returns.csv').query("model == 'PCA3'").reset_index(drop=True)
    frozen_h=np.load(ROOT/'equity/experiments/equity_efa_vs_pca/positions_and_loadings.npz')['holdings'][:,0]
    samples=sorted(set([0,1,19,503,504,505,750,1004,1234,1500,1738,1750,2004,2200,2444,2445]+
        context.loc[context.signal_date.isin(['2020-03-16','2024-08-05']),'day'].tolist()))
    trees_checked=0;maximum_reconstruction=0.
    for d,t in enumerate(ts):
        idx=np.flatnonzero(np.isfinite(y[d]));date=context.iloc[d].signal_date
        assert date==str(raw.index[t].date()) and context.iloc[d].history_end==str(raw.index[t-1].date())
        assert context.iloc[d].entry_date==str(raw.index[t+1].date())
        assert context.iloc[d].history_end<date<context.iloc[d].entry_date
        assert np.array_equal(idx,np.flatnonzero(np.isfinite(source[t-272:t]).all(axis=0)))
        assert np.allclose(pos[d],frozen_h[d],atol=1e-12)
        actual=cl[t+1,idx]/op[t+1,idx]-1
        assert np.isclose(pos[d,idx]@actual,frozen.iloc[d].gross_return,atol=1e-12)
        assert np.isclose(context.iloc[d].frozen_gross_return,frozen.iloc[d].gross_return,atol=1e-12)
        assert np.allclose(f[d,idx,names.index('vix_log')],np.log(vix.loc[date]))
        assert np.allclose(f[d,idx,names.index('vix_change')],np.log(vix.loc[date]/vix.loc[str(raw.index[t-1].date())]))
        assert np.all(f[d,idx,names.index('vix_band20to30')]==int(20<=vix.loc[date]<30))
        assert np.array_equal(graphs[d],graphs[d].T) and not np.diag(graphs[d]).any()
        assert np.isfinite(f[d,idx]).all() and np.isnan(f[d,np.setdiff1d(np.arange(len(symbols)),idx)]).all()
        if d not in samples:continue
        hist=source[t-120:t,idx];design=np.c_[np.ones(120),market[t-120:t]]
        coeff=np.linalg.solve(design.T@design,design.T@hist);e=hist-design@coeff
        residual_sd=np.maximum(e.std(axis=0,ddof=1),.0001)
        standardized=(e-e.mean(axis=0))/residual_sd
        corr=np.corrcoef(standardized,rowvar=False)
        _,vectors=eigh(corr,subset_by_index=[len(idx)-3,len(idx)-1])
        X=np.c_[np.ones(len(idx)),coeff[1],residual_sd[:,None]*vectors]
        sigma=np.maximum(hist.std(axis=0,ddof=1),.0001);w=1/sigma**2
        normalized=X/np.sqrt(np.mean(X*X,axis=0))
        def residualize(value):
            beta=np.linalg.solve(normalized.T@(w[:,None]*normalized),normalized.T@(w*value))
            return value-normalized@beta
        residual=residualize(source[t,idx]);z=residual/sigma
        for expected,got in [(z,f[d,idx,0]),(residualize(actual)/sigma,y[d,idx])]:
            maximum_reconstruction=max(maximum_reconstruction,float(np.max(abs(expected-got))))
            assert np.allclose(expected,got,atol=1e-9)
        a=np.zeros((len(idx),len(idx)),dtype=bool)
        for i in range(len(idx)):
            peers=np.argsort(-corr[i],kind='stable')
            peers=peers[(peers!=i)&(corr[i,peers]>0)][:5];a[i,peers]=True
        a|=a.T
        assert np.array_equal(a,graphs[d][np.ix_(idx,idx)])
        for sign in [-1,1]:
            q=np.maximum(sign*f[d,idx,0],0)
            table=bt.loc[(bt.signal_date==date)&(bt.sign==sign)].copy()
            table['peak']=[list(symbols[idx]).index(s) for s in table.peak_symbol]
            owners=np.array([np.flatnonzero(idx==p)[0] if p>=0 else -1 for p in owner[d,idx]])
            check_tree(q,a,table,owners,f[d,idx,names.index('branch_prominence')],f[d,idx,names.index('branch_support_fraction')])
            trees_checked+=1
    print(f'Source and topology checks passed on {len(samples)} sampled reconstructions, {trees_checked} complete trees',flush=True)
    # Extra boundary cases; expected components independently counted at all levels.
    from tda_residual_shock import merge_tree
    for q,a in [(np.zeros(4),np.zeros((4,4),bool)),(np.array([3.,2.,1.,.5]),np.zeros((4,4),bool)),
        (np.array([3.,1.,2.,.5]),np.ones((4,4),bool)^np.eye(4,dtype=bool))]:
        p,s,o,b=merge_tree(q,a);check_tree(q,a,b,o,p,s)
    # All predictions through an independently solved raw-coefficient ridge system.
    maximum_forecast=0.;fitchecks=0;checks_sklearn=0
    for mi,(model,columns) in enumerate(cfg['models'].items(),1):
        p=len(columns);sx=np.zeros(p);sxx=np.zeros((p,p));sy=np.zeros(2);sxy=np.zeros((p,2))
        for d in range(len(context)):
            active=np.isfinite(y[d]);x=matrix(f[d,active],columns,names);outcome=np.c_[y[d,active],abs(y[d,active])]
            if d>=504:
                if (d-504)%20==0:
                    mu=sx/d;sd2=np.maximum(np.diag(sxx)/d-mu*mu,0);sd2=np.where(sd2>1e-20,sd2,1.)
                    beta=np.linalg.solve(sxx-np.outer(sx,sx)/d+d*np.diag(sd2),sxy-np.outer(sx,sy)/d)
                    intercept=sy/d;fitchecks+=1
                    if d in [504,1004,2004,2444]:
                        xx=[];yy=[];ww=[]
                        for j in range(d):
                            act=np.isfinite(y[j]);xx.append(matrix(f[j,act],columns,names))
                            yy.append(np.c_[y[j,act],abs(y[j,act])]);ww.append(np.full(act.sum(),1/act.sum()))
                        xx=np.concatenate(xx);yy=np.concatenate(yy);ww=np.concatenate(ww)
                        scaler=StandardScaler().fit(xx,sample_weight=ww)
                        scaler.scale_=np.where(scaler.scale_>1e-10,scaler.scale_,1.)
                        fitted=Ridge(alpha=d,fit_intercept=True,solver='cholesky').fit(scaler.transform(xx),yy,sample_weight=ww)
                        check=fitted.predict(scaler.transform(x))
                        assert np.allclose(check,pred[d,active,mi],atol=1e-8)
                        checks_sklearn+=1
                reconstructed=intercept+(x-mu)@beta
                discrepancy=float(np.max(abs(reconstructed-pred[d,active,mi])));maximum_forecast=max(maximum_forecast,discrepancy)
                assert discrepancy<1e-8
                if mi==1:
                    assert np.all(pred[d,active,0,0]==0)
                    assert np.allclose(pred[d,active,0,1],intercept[1])
            sx+=np.sum(x/len(x),axis=0);sxx+=np.einsum('ni,nj->ij',x,x)/len(x)
            sy+=np.sum(outcome/len(x),axis=0);sxy+=np.einsum('ni,nj->ij',x,outcome)/len(x)
        print(f'Independent fits passed: {model}',flush=True)
    diagnostics=pd.read_csv(OUT/'fit_diagnostics.csv')
    assert len(diagnostics)==fitchecks
    assert (diagnostics.latest_training_execution<=diagnostics.first_signal).all()
    assert np.isnan(pred[:504]).all()
    losses=pd.read_csv(OUT/'daily_losses.csv')
    for row in losses.itertuples():
        d=row.day;active=np.isfinite(y[d]);mi=models.index(row.model);k=0 if row.target=='mean' else 1
        expected=y[d,active] if k==0 else abs(y[d,active]);got=pred[d,active,mi,k]
        assert np.isclose(np.mean((expected-got)**2),row.MSE,atol=1e-12)
        assert np.isclose(np.mean(abs(expected-got)),row.MAE,atol=1e-12)
    metrics=pd.read_csv(OUT/'forecast_metrics.csv');comparisons=pd.read_csv(OUT/'paired_comparisons.csv')
    response_daily=pd.read_csv(OUT/'response_daily.csv');responses=pd.read_csv(OUT/'response_summary.csv')
    median=cfg['training_branch_prominence_median']
    for row in response_daily.itertuples():
        active=np.isfinite(y[row.day]);z=f[row.day,active,0]
        prominence=f[row.day,active,names.index('branch_prominence')]
        take=np.ones(len(z),bool) if row.group=='all' else (prominence<=median if row.group=='lower_prominence' else prominence>median)
        assert int(take.sum())==row.stocks
        assert np.isclose(z[take]@y[row.day,active][take],row.numerator)
        assert np.isclose(z[take]@z[take],row.denominator)
        assert np.isclose(z[take]@pred[row.day,active,2,0][take],row.ordinary_numerator)
        assert np.isclose(z[take]@pred[row.day,active,3,0][take],row.tda_numerator)
    for row in metrics.itertuples():
        take=losses.loc[(losses.period==row.period)&(losses.model==row.model)&(losses.target==row.target)]
        assert len(take)==row.dates and int(take.stocks.sum())==row.stock_events
        assert np.isclose(take.MSE.mean(),row.MSE) and np.isclose(take.MAE.mean(),row.MAE)
    maximum_interval=0.
    for pi,period in enumerate(['development','later']):
        n=1234 if pi==0 else 708
        rng=np.random.default_rng(2026110507+pi);starts=rng.integers(n,size=(1000,int(np.ceil(n/60))))
        ix=np.array([np.concatenate([(np.arange(60)+s)%n for s in r])[:n] for r in starts])
        for target in ['mean','absolute_move']:
            g=comparisons.loc[(comparisons.period==period)&(comparisons.target==target)]
            wide=losses.loc[(losses.period==period)&(losses.target==target)].pivot(index='day',columns='model',values='MSE').sort_index()
            diff=np.column_stack([(wide[r.model]-wide[r.reference]).to_numpy() for r in g.itertuples()])
            center=diff.mean(axis=0);boot=diff[ix].mean(axis=1);sd=boot.std(axis=0,ddof=1)
            critical=np.quantile(np.max(abs((boot-center)/np.maximum(sd,1e-15)),axis=1),.95)
            low,high=np.quantile(boot,[.025,.975],axis=0)
            for expected,actual in [(center,g.loss_difference),(low,g.point95_low),(high,g.point95_high),
                (center-critical*sd,g.simultaneous95_low),(center+critical*sd,g.simultaneous95_high)]:
                error=float(np.max(abs(expected-actual)));maximum_interval=max(maximum_interval,error)
                assert error<1e-10
        for r in responses.loc[responses.period==period].itertuples():
            daily=response_daily.loc[(response_daily.period==period)&(response_daily.group==r.group)].sort_values('day')
            num=daily.numerator.to_numpy();den=daily.denominator.to_numpy()
            boot=num[ix].sum(axis=1)/den[ix].sum(axis=1);lo,hi=np.quantile(boot,[.025,.975])
            assert np.isclose(num.sum()/den.sum(),r.response_slope)
            assert np.allclose([lo,hi],[r.point95_low,r.point95_high],atol=1e-12)
    assert np.isclose(np.nanmedian(f[:504,:,names.index('branch_prominence')]),cfg['training_branch_prominence_median'])
    for collection in ['protected_sha256','output_sha256']:
        for path,want in summary[collection].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==want,path
    result={'passed':True,'all_source_dates':len(context),'all_stock_events':int(np.isfinite(y).sum()),
        'sampled_independent_PCA_WLS_graph_dates':len(samples),'independently_checked_trees':trees_checked,
        'maximum_independent_outcome_discrepancy':maximum_reconstruction,'independent_ridge_refits':fitchecks,
        'sklearn_weighted_multioutput_refits':checks_sklearn,'maximum_all_prediction_discrepancy':maximum_forecast,
        'daily_loss_rows_checked':len(losses),'metric_rows_checked':len(metrics),'paired_rows_checked':len(comparisons),
        'descriptive_response_rows_checked':len(response_daily),'response_summary_rows_checked':len(responses),
        'maximum_interval_discrepancy':maximum_interval,'original_strategy_unchanged':True,'no_new_policy':True,
        'audit_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
