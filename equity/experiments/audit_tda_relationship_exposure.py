"""Independent mathematical, source, fit and score checks for labeled exposure."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
from pathlib import Path
import json,gzip,hashlib
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cophenet,fcluster,linkage
from scipy.spatial.distance import squareform
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.optimize import minimize
from sklearn.linear_model import Ridge

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).with_name('tda_relationship_exposure')
DATA=ROOT/'market_data/datasets/equity_daily_expanded_2016_2026-10-27'
FLOOR=1e-8


def independent_lw(values):
    x=values-values.mean(axis=0);n,p=x.shape
    empirical=x.T@x/n;mu=np.trace(empirical)/p
    delta=np.sum((empirical-mu*np.eye(p))**2)/p
    beta=(np.mean(np.sum(x*x,axis=1)**2)-np.sum(empirical**2))/(p*n)
    shrink=min(max(beta,0),delta)/delta if delta else 0.
    return (1-shrink)*empirical+shrink*mu*np.eye(p)


def independent_corr(values,market):
    design=np.c_[np.ones(len(market)),market]
    coefficients=np.linalg.solve(design.T@design,design.T@values)
    residual=values-design@coefficients
    return np.corrcoef(residual,rowvar=False)


def mst_minimax(distance):
    work=distance.copy();n=len(work)
    # Sparse MST treats explicit zeros as absent; retain zero-distance edges numerically.
    work[(work==0)&~np.eye(n,dtype=bool)]=1e-14
    tree=minimum_spanning_tree(work).toarray();tree=tree+tree.T
    result=np.zeros((n,n))
    for start in range(n):
        seen={start};stack=[start]
        while stack:
            i=stack.pop()
            for j in np.flatnonzero(tree[i]):
                if j not in seen:
                    result[start,j]=max(result[start,i],tree[i,j]);seen.add(j);stack.append(j)
        assert len(seen)==n
    return result


def objective(theta,design,offset,y):
    eta=offset+design@theta;ratio=y*np.exp(-eta)
    penalty=np.r_[0.,theta[1:]]
    return float(np.mean(eta+ratio)+.5*np.sum(theta[1:]**2)),design.T@(1-ratio)/len(y)+penalty


def main():
    summary=json.loads((OUT/'summary.json').read_text());frame=pd.read_csv(OUT/'state_features_and_targets.csv')
    predictions=pd.read_csv(OUT/'walk_forward_predictions.csv');metrics=pd.read_csv(OUT/'forecast_metrics.csv')
    comparisons=pd.read_csv(OUT/'paired_comparisons.csv');diagnostics=pd.read_csv(OUT/'fit_diagnostics.csv')
    with gzip.open(OUT/'fit_parameters.json.gz','rt') as f:parameters=json.load(f)
    archive=np.load(OUT/'labeled_hierarchies.npz');trees=archive['trees'];symbols=archive['symbols'];ts=archive['signal_indices']
    raw=pd.read_csv(DATA/'returns_log.csv',index_col='date',parse_dates=True).iloc[1:]
    x=raw[symbols].to_numpy();market=raw.SPY.to_numpy()
    bars=pd.read_csv(DATA/'bars_raw.csv',parse_dates=['date'])
    prices={key:bars.pivot(index='date',columns='symbol',values=key).reindex(index=raw.index,columns=symbols).to_numpy() for key in ['o','c']}
    intraday=(prices['c']/prices['o']-1)*1e4
    positions=np.load(ROOT/'equity/experiments/equity_efa_vs_pca/positions_and_loadings.npz')['holdings'][:,0]
    frozen=pd.read_csv(ROOT/'equity/experiments/equity_efa_vs_pca/daily_gross_returns.csv').query("model=='PCA3'").reset_index(drop=True)
    vix=pd.read_csv(ROOT/'market_data/datasets/mean_reversion_context_2026-11-04/vix_daily.csv').set_index('date').close
    samples=sorted(set([0,1,19,503,504,505,750,1004,1234,1504,1738,2004,2200,2444,2445]+
        frame.loc[frame.signal_date.isin(['2020-03-16','2024-08-05']),'day'].tolist()))
    maximum_feature=0.;maximum_mst=0.;kernels_checked=0
    for d,t in enumerate(ts):
        row=frame.iloc[d];idx=np.flatnonzero(np.isfinite(x[t-272:t]).all(axis=0));h=positions[d,idx]
        assert row.signal_date==str(raw.index[t].date()) and row.entry_date==str(raw.index[t+1].date())
        assert row.history_end==str(raw.index[t-1].date()) and row.older_history_end==str(raw.index[t-6].date())
        assert row.older_history_end<row.history_end<row.signal_date<row.entry_date
        assert row.stocks==len(idx) and np.isclose(abs(h).sum(),1)
        assert abs(h@intraday[t+1,idx]-row.gross_bps)<1e-9
        assert abs(row.gross_bps-frozen.iloc[d].gross_return*1e4)<1e-9
        assert np.isclose(row.second_moment,row.gross_bps**2) and np.isclose(row.downside_moment,min(row.gross_bps,0)**2)
        assert np.isclose(row.vix_log,np.log(vix.loc[row.signal_date]))
        assert np.isclose(row.vix_change,np.log(vix.loc[row.signal_date]/vix.loc[row.history_end]))
        assert row.vix_band20to30==int(20<=vix.loc[row.signal_date]<30)
        trailing=frame.gross_bps.iloc[max(0,d-20):d].to_numpy()
        assert np.isclose(row.strategy_mean20,trailing.mean() if len(trailing) else 0)
        if d not in samples:continue
        current=intraday[t-120:t,idx];older=intraday[t-125:t-5,idx]
        c=independent_lw(current);cp=independent_lw(older);cc=independent_lw(x[t-120:t,idx]*1e4)
        sigma=np.maximum(current.std(axis=0,ddof=1),1.);v=h*sigma
        for expected,actual in [(h@c@h,row.risk_offset),(h@cc@h,np.exp(row.log_LW_closeclose)),
            (v@v,np.exp(row.log_diagonal)),(np.sum(np.outer(abs(h),abs(h))*abs(c-cp))/(v@v),row.weighted_cov_change5),
            (h@(c-cp)@h/(v@v),row.signed_cov_change5)]:
            error=float(abs(expected-actual));maximum_feature=max(maximum_feature,error)
            assert np.isclose(expected,actual,rtol=1e-9,atol=1e-8),(d,expected,actual)
        for mi,prefix in [(0,'h0'),(1,'average')]:
            kernels=[]
            for lag in [0,1]:
                shift=5*lag;cor=independent_corr(x[t-120-shift:t-shift,idx],market[t-120-shift:t-shift])
                distance=np.sqrt(np.maximum(2*(1-np.clip(cor,-1,1)),0));np.fill_diagonal(distance,0)
                tree=trees[d,mi,lag,:len(idx)-1]
                co=squareform(cophenet(tree));k=1-co/2;kernels.append(k)
                if mi==0:
                    independent=mst_minimax(distance);error=float(np.max(abs(independent-co)));maximum_mst=max(maximum_mst,error)
                    assert error<1e-8
                else:
                    rebuilt=linkage(squareform(distance,checks=False),method='average')
                    assert np.allclose(cophenet(rebuilt),cophenet(tree),rtol=1e-8,atol=1e-8)
                assert np.linalg.eigvalsh(k).min()>-1e-8
                levels=np.r_[0.,np.unique(tree[:,2]),2.];integral=0.
                for lo,hi in zip(levels[:-1],levels[1:]):
                    labels=fcluster(tree,(lo+hi)/2,criterion='distance')
                    integral+=(hi-lo)/2*sum(v[labels==label].sum()**2 for label in np.unique(labels))
                assert np.isclose(integral,v@k@v,rtol=1e-10,atol=1e-9)
                kernels_checked+=1
            k,kp=kernels
            expected=[np.log(max(v@k@v,FLOOR)),v@(k-kp)@v/(v@v),
                np.sum(np.outer(abs(v),abs(v))*abs(k-kp))/abs(v).sum()**2]
            actual=row[[prefix+'_log_tree_moment',prefix+'_signed_tree_change',prefix+'_weighted_membership_change']].to_numpy(dtype=float)
            assert np.allclose(expected,actual,rtol=1e-9,atol=1e-9)
    print(f'Source and hierarchy checks passed: {len(samples)} reconstructions, {kernels_checked} kernel integrations',flush=True)
    maximum_prediction=0.;maximum_gradient=0.;maximum_optimizer=0.;selected_risk=0;selected_mean=0
    for rec in parameters:
        d=rec['fit_day'];target=rec['target'];model=rec['model'];cols=rec['columns']
        train=frame.iloc[:d];xtrain=train[cols].to_numpy();mu=xtrain.mean(axis=0);sd=xtrain.std(axis=0,ddof=0);sd=np.where(sd>1e-10,sd,1.)
        assert np.allclose(mu,rec['mu']) and np.allclose(sd,rec['sd'])
        assert train.entry_date.max()<=frame.iloc[d].signal_date
        z=(xtrain-mu)/sd;design=np.c_[np.ones(d),z];theta=np.array(rec['theta']);y=train[target].to_numpy()
        if target=='mean':
            expected=Ridge(alpha=d,fit_intercept=True,solver='cholesky').fit(z,y)
            assert np.allclose(theta,np.r_[expected.intercept_,expected.coef_],atol=1e-9)
            selected_mean+=1
        else:
            offset=np.log(train.risk_offset.to_numpy());value,gradient=objective(theta,design,offset,y)
            g=float(np.max(abs(gradient)));maximum_gradient=max(maximum_gradient,g);assert g<2e-6
            if d in [504,1504,2444]:
                def hessian(b,design,offset,y):
                    ratio=y*np.exp(-offset-design@b)
                    return design.T@(ratio[:,None]*design)/d+np.diag(np.r_[0.,np.ones(len(cols))])
                initial=np.r_[np.log(np.mean(y*np.exp(-offset))),np.zeros(len(cols))]
                fit=minimize(objective,initial,args=(design,offset,y),method='trust-exact',jac=True,hess=hessian,
                    options={'gtol':1e-8,'maxiter':200})
                assert np.max(abs(objective(fit.x,design,offset,y)[1]))<2e-6
                error=float(np.max(abs(fit.x-theta)));maximum_optimizer=max(maximum_optimizer,error);assert error<1e-5
                selected_risk+=1
        block=frame.iloc[d:min(d+20,len(frame))];znow=(block[cols].to_numpy()-mu)/sd
        expected=theta[0]+znow@theta[1:]
        if target!='mean':expected=np.exp(np.log(block.risk_offset.to_numpy())+expected)
        actual=predictions.loc[(predictions.model==model)&(predictions.target==target)&predictions.day.between(d,d+19)].sort_values('day')
        assert len(actual)==len(block)
        error=float(np.max(abs(expected-actual.prediction)));maximum_prediction=max(maximum_prediction,error)
        assert np.allclose(expected,actual.prediction,rtol=1e-10,atol=1e-8)
    assert len(parameters)==len(diagnostics)==1176
    assert (diagnostics.latest_training_execution<=diagnostics.signal_date).all()
    print('All saved fits/forecasts and independent optimizer checks passed',flush=True)
    for (target,model),g in predictions.groupby(['target','model']):
        rows=frame.set_index('day').loc[g.day]
        assert np.allclose(g.actual,rows[target])
        if target=='mean':expected=(g.actual-g.prediction)**2
        else:
            assert (g.prediction>0).all();expected=np.log(g.prediction)+g.actual/g.prediction
        assert np.allclose(expected,g.loss,atol=1e-10)
        if model in ['RawLW','CalibratedLW','Zero','HistoryMean']:
            for fitday in range(504,len(frame),20):
                take=g.loc[g.day.between(fitday,fitday+19)]
                if model=='Zero':want=np.zeros(len(take))
                elif model=='HistoryMean':want=np.full(len(take),frame.gross_bps.iloc[:fitday].mean())
                else:
                    want=frame.risk_offset.iloc[take.day].to_numpy()
                    if model=='CalibratedLW':want*=np.mean(frame[target].iloc[:fitday]/frame.risk_offset.iloc[:fitday])
                assert np.allclose(want,take.prediction,rtol=1e-10,atol=1e-9)
    for row in metrics.itertuples():
        take=predictions.loc[(predictions.model==row.model)&(predictions.target==row.target)&(predictions.period==row.period)]
        assert len(take)==row.dates and np.isclose(take.loss.mean(),row.score)
        if row.target!='mean':assert np.isclose(np.mean(take.actual/take.prediction),row.calibration_ratio)
    maximum_interval=0.
    for pi,period in enumerate(['development','later']):
        for target in ['second_moment','downside_moment','mean']:
            wide=predictions.loc[(predictions.period==period)&(predictions.target==target)].pivot(index='day',columns='model',values='loss').sort_index()
            n=len(wide);rng=np.random.default_rng(2026110519+pi);starts=rng.integers(n,size=(1000,int(np.ceil(n/60))))
            ix=np.array([np.concatenate([(np.arange(60)+s)%n for s in row])[:n] for row in starts])
            g=comparisons.loc[(comparisons.period==period)&(comparisons.target==target)]
            diff=np.column_stack([(wide[r.model]-wide[r.reference]).to_numpy() for r in g.itertuples()])
            center=diff.mean(axis=0);boot=diff[ix].mean(axis=1);sd=boot.std(axis=0,ddof=1)
            critical=np.quantile(np.max(abs((boot-center)/np.maximum(sd,1e-15)),axis=1),.95)
            low,high=np.quantile(boot,[.025,.975],axis=0)
            for expected,actual in [(center,g.loss_difference),(low,g.point95_low),(high,g.point95_high),
                (center-critical*sd,g.simultaneous95_low),(center+critical*sd,g.simultaneous95_high)]:
                error=float(np.max(abs(expected-actual)));maximum_interval=max(maximum_interval,error);assert error<1e-10
    for family in ['protected_sha256','output_sha256']:
        for path,want in summary[family].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==want,path
    result=dict(passed=True,all_original_portfolio_dates=len(frame),forecast_dates=1942,
        independently_reconstructed_source_dates=len(samples),independent_kernel_integrations=kernels_checked,
        max_independent_feature_discrepancy=maximum_feature,max_MST_minimax_discrepancy=maximum_mst,
        fits_checked=len(parameters),independent_sklearn_mean_fits=selected_mean,independent_trust_exact_risk_fits=selected_risk,
        max_risk_stationarity_gradient=maximum_gradient,max_independent_optimizer_coefficient_discrepancy=maximum_optimizer,
        max_saved_forecast_discrepancy=maximum_prediction,daily_loss_rows_checked=len(predictions),
        metrics_checked=len(metrics),paired_comparisons_checked=len(comparisons),max_interval_discrepancy=maximum_interval,
        original_strategy_unchanged=True,no_new_policy=True,
        audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
