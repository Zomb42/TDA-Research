"""Independent numerical and source checks for frozen BTC forecast pilot."""
from decimal import Decimal as D
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import numpy as np
import pandas as pd
from ripser import ripser

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent/'kalshi_perp_return_prediction_2026_11_05'


def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    spec=json.loads((OUT/'specification.json').read_text())
    summary=json.loads((OUT/'summary.json').read_text())
    assert digest(OUT/'specification.json')==summary['specification_sha256']
    assert digest(OUT.with_suffix('.py'))==summary['source_sha256']
    for item in spec['inputs']:assert digest(ROOT/item['path'])==item['sha256']
    assert digest(ROOT/spec['metadata'])==spec['metadata_sha256']
    data=pd.read_csv(OUT/'features_and_targets.csv').set_index('row_id',drop=False)
    pred=pd.read_csv(OUT/'walk_forward_predictions.csv')
    grid=pd.read_parquet(OUT/'aligned_5s.parquet')
    books=pd.read_parquet(OUT/'book_checkpoints.parquet')
    refs=pd.read_parquet(OUT/'reference_samples.parquet')
    trades=pd.read_parquet(OUT/'trades.parquet')
    assert not trades.trade_id.duplicated().any()
    tda=spec['tda_features'];ordinary=spec['ordinary_features']+['ret60_x_std','ret60_x_acf','ret60_x_spectrum']
    models={'Ordinary18':ordinary,'OrdinaryPlusTDA21':ordinary+tda,
            'OrdinaryPlusTDAInteractions24':ordinary+tda+['ret60_x_'+c for c in tda]}
    ycols=['signed_bps','absolute_bps']
    memberships=json.loads((OUT/'training_membership.json').read_text())
    max_forecast_error=max_coefficient_error=0.
    coef=pd.read_csv(OUT/'coefficients.csv')
    fit_count=0
    for entry in memberships:
        train=data.loc[entry['train_row_ids']]
        intended=data.loc[data.label_end_ns.le(entry['decision_ns']) & data.timestamp.lt(entry['decision_ns'])]
        assert train.index.tolist()==intended.index.tolist()
        assert len(train)==entry['n_train']>=180
        assert train.label_end_ns.max()<=entry['decision_ns']
        part=pred.loc[pred.fit_id.eq(entry['fit_id'])]
        for model,cols in models.items():
            x=train[cols].to_numpy();mu=x.mean(0);sd=x.std(0);sd[sd<1e-10]=1
            z=(x-mu)/sd;y=train[ycols].to_numpy();intercept=y.mean(0)
            beta=np.linalg.solve(z.T@z+len(train)*np.eye(len(cols)),z.T@(y-intercept))
            for j,target in enumerate(ycols):
                g=part.loc[part.model.eq(model)&part.target.eq(target)]
                current=data.loc[g.row_id,cols].to_numpy()
                reconstructed=(current-mu)/sd@beta[:,j]+intercept[j]
                err=float(np.max(np.abs(g.prediction-reconstructed)))
                max_forecast_error=max(max_forecast_error,err)
                stored=coef.loc[coef.fit_id.eq(entry['fit_id'])&coef.model.eq(model)&coef.target.eq(target)].set_index('feature').loc[cols]
                max_coefficient_error=max(max_coefficient_error,float(np.max(np.abs(stored.coefficient-beta[:,j]))))
                np.testing.assert_allclose(stored['mean'],mu,atol=1e-12,rtol=1e-12)
                np.testing.assert_allclose(stored.scale,sd,atol=1e-12,rtol=1e-12)
                assert err<1e-9
                fit_count+=1
        for target in ycols:
            for model in ['Zero','HistoryMean']:
                g=part.loc[part.model.eq(model)&part.target.eq(target)]
                wanted=0 if model=='Zero' else float(train[target].mean())
                np.testing.assert_allclose(g.prediction,wanted,atol=1e-12)
    label_error=0.;topology_error=0.
    selected=set(np.linspace(0,len(data)-1,9).round().astype(int).tolist())
    def independent_topology(returns):
        sd=returns.std();z=(returns-returns.mean())/sd if sd>1e-12 else np.zeros_like(returns)
        points=np.array([[z[k],z[k-2],z[k-4]] for k in range(4,len(z))])
        dg=ripser(points,maxdim=1)['dgms']
        deaths=np.sort(dg[0][np.isfinite(dg[0][:,1]),1])
        h1=dg[1][np.isfinite(dg[1][:,1])];life=h1[:,1]-h1[:,0]
        return np.array([np.quantile(deaths,.9) if len(deaths) else 0,max(life,default=0),sum(v*v for v in life)])
    for j,(_,row) in enumerate(data.iterrows()):
        i=int(row.grid_index);window=grid.iloc[i-120:i+13]
        assert window.valid.all()
        assert window.perp_epoch.nunique()==window.ref_epoch.nunique()==1
        assert row.timestamp==grid.timestamp.iloc[i]
        assert row.label_end_ns==grid.timestamp.iloc[i+12]
        assert (window.perp_observed_at<=window.timestamp).all() and (window.ref_observed_at<=window.timestamp).all()
        assert window.perp_age_s.le(7.5).all() and window.ref_age_s.le(1).all()
        assert window.ref_total_quote_age_s.le(2).all()
        actual=10000*np.log(grid.mid.iloc[i+12]/grid.mid.iloc[i])
        label_error=max(label_error,abs(actual-row.signed_bps))
        assert abs(row.absolute_bps-abs(actual))<1e-10
        trade=trades.loc[trades.timestamp.gt(row.timestamp-60_000_000_000)&trades.timestamp.le(row.timestamp)]
        total=float(trade.usd.sum());net=float(trade.signed_usd.sum())
        wanted=net/total if total else 0
        np.testing.assert_allclose(row.taker_bid_minus_ask60,wanted,atol=2e-10)
        assert abs(np.expm1(row.log_trade_count60)-len(trade))<1e-8
        np.testing.assert_allclose(row.log_trade_usd60,np.log1p(total),atol=2e-10)
        assert abs(row.ret60_bps-10000*np.log(grid.mid.iloc[i]/grid.mid.iloc[i-12]))<1e-10
        for c in tda:assert abs(row['ret60_x_'+c]-row.ret60_bps*row[c])<1e-8
        if j in selected:
            # Inputs physically truncated at decision; future target prices cannot enter the cloud.
            available=grid.loc[grid.timestamp.le(row.timestamp)].tail(121)
            r=np.diff(np.log(available.mid.to_numpy()))*10000
            wanted=independent_topology(r)
            topology_error=max(topology_error,float(np.max(np.abs(wanted-row[tda].to_numpy(dtype=float)))))
            np.testing.assert_allclose(wanted,row[tda].to_numpy(dtype=float),atol=1e-7)
            np.testing.assert_allclose(independent_topology(-r),wanted,atol=1e-6)
            np.testing.assert_allclose(independent_topology(3*r),wanted,atol=1e-6)
    assert label_error<1e-10
    np.testing.assert_allclose(independent_topology(np.zeros(120)),0,atol=0)
    # Independently verify all grid selections are the latest observation available at that clock.
    for obs,key,age in [(books,'perp_observed_at',7.5),(refs,'ref_observed_at',1.)]:
        ix=np.searchsorted(obs.timestamp.to_numpy(),grid.timestamp.to_numpy(),side='right')-1
        okay=ix>=0;expected=np.full(len(grid),np.nan)
        expected[okay]=obs.timestamp.to_numpy()[ix[okay]]
        expected[(grid.timestamp.to_numpy()-expected)/1e9>age]=np.nan
        np.testing.assert_allclose(grid[key],expected,atol=0,rtol=0,equal_nan=True)
    metrics=pd.read_csv(OUT/'forecast_metrics.csv')
    for _,row in metrics.iterrows():
        g=pred.loc[pred.target.eq(row.target)&pred.model.eq(row.model)]
        mse=np.mean((g.prediction-g.actual)**2);mae=np.mean(np.abs(g.prediction-g.actual))
        np.testing.assert_allclose([row.MSE,row.MAE],[mse,mae],atol=1e-10)
    # Rebuild paired differences and bootstrap draws from the saved forecast ledger.
    artifact=np.load(OUT/'bootstrap.npz');timeline=artifact['timeline'];differences=[]
    for target in ycols:
        matrix=pred.loc[pred.target.eq(target)].pivot(index='timestamp',columns='model',values='squared_error').reindex(timeline)
        for model in ['OrdinaryPlusTDA21','OrdinaryPlusTDAInteractions24']:
            differences.append((matrix[model]-matrix.Ordinary18).to_numpy())
    loss=np.column_stack(differences)
    np.testing.assert_allclose(loss,artifact['loss_differences'],atol=1e-10,equal_nan=True)
    rng=np.random.default_rng(2026110507);n=len(timeline)
    starts=rng.integers(n,size=(2000,int(np.ceil(n/60))))
    draws=np.concatenate([(starts[:,k,None]+np.arange(60)[None,:])%n for k in range(starts.shape[1])],axis=1)[:,:n]
    np.testing.assert_array_equal(draws,artifact['draws'])
    means=np.array([np.nanmean(loss[idx],axis=0) for idx in draws]);center=np.nanmean(loss,axis=0)
    sd=np.maximum(means.std(axis=0,ddof=1),1e-15)
    critical=np.quantile(np.max(np.abs((means-center)/sd),axis=1),.95)
    comparisons=pd.read_csv(OUT/'paired_comparisons.csv')
    interval_error=0.
    for j,(_,row) in enumerate(comparisons.iterrows()):
        point=np.quantile(means[:,j],[.025,.975]);sim=center[j]+np.array([-1,1])*critical*sd[j]
        got=np.array([row.point95_low,row.point95_high,row.simultaneous95_low,row.simultaneous95_high])
        interval_error=max(interval_error,float(np.max(np.abs(got-np.r_[point,sim]))))
    assert interval_error<1e-9
    # Selected raw stream prefixes independently replay deltas using exact-decimal source tooling.
    sys.path.insert(0,str(ROOT/'market_data'))
    from btc_archive_control import inspect
    source_files=[ROOT/x['path'] for x in spec['inputs'] if x['source']=='kalshi_perp']
    replay=[]
    for k in sorted(set([0,len(source_files)//2,len(source_files)-1])):
        replay.append(inspect(source_files[k],limit=250000))
    result=dict(passed=True,independent_ridge_fits=fit_count,refits=len(memberships),
                forecast_rows=len(pred),eligible_labels_checked=len(data),
                max_forecast_discrepancy=max_forecast_error,max_coefficient_discrepancy=max_coefficient_error,
                max_label_discrepancy=label_error,max_topology_discrepancy=topology_error,
                max_interval_discrepancy=interval_error,geometry_windows_checked=len(selected),
                reflection_scale_constant_controls_passed=True,past_only_geometry_checked=True,
                all_input_hashes_rechecked=True,all_asof_joins_checked=True,
                selected_raw_replay=replay,
                limit='Raw independent replay is selected250k-row prefixes, not every delta. Full frozen files passed production gzip CRC/row/hash checks. Short-history bootstrap does not establish future generalization.')
    (OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
