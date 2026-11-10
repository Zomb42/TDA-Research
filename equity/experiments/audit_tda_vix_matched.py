"""Independent audit of source timing, labels, memberships, ridge fits and losses."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).with_name('tda_vix_matched')
OLD=OUT.parent/'equity_full_basket_states'


def main():
    cfg=json.loads((OUT/'executed_configuration.json').read_text());models=cfg['model_columns']
    f=pd.read_csv(OUT/'state_features_with_vix.csv').set_index('anchor')
    p=pd.read_csv(OUT/'walk_forward_predictions.csv')
    members=pd.read_csv(OLD/'training_membership.csv.gz')
    old=pd.read_csv(OLD/'walk_forward_predictions.csv').set_index('anchor')
    source=pd.read_csv(ROOT/'equity/experiments/equity_efa_vs_pca/daily_gross_returns.csv')
    ledger=source.loc[source.model=='PCA3'].set_index('date').sort_index()
    vix=pd.read_csv(ROOT/'market_data/datasets/mean_reversion_context_2026-11-04/vix_daily.csv').set_index('date').close
    calendar=pd.read_csv(ROOT/'market_data/datasets/equity_daily_expanded_2016_2026-10-27/close_all.csv',usecols=['date']).date.tolist()
    for row in f.itertuples():
        i=calendar.index(row.target_start);prior,preceding=calendar[i-1],calendar[i-2]
        assert prior==row.vix_observation_date==row.formation_date
        assert row.history_end==row.topology_feature_end<row.target_start
        assert np.isclose(row.vix_log_level,np.log(vix.loc[prior]))
        assert np.isclose(row.vix_completed_log_change,np.log(vix.loc[prior]/vix.loc[preceding]))
        assert row.vix_band20to30==int(20<=vix.loc[prior]<30)
        if pd.notna(row.target_end):
            values=ledger.loc[row.target_start:row.target_end,'gross_return'].to_numpy()*1e4
            assert len(values)==20
            assert np.isclose(values.mean(),row.target_mean_bps,atol=1e-10)
            rms=np.sqrt(np.mean(values**2))
            assert np.isclose(rms,row.target_RMS_bps) and np.isclose(np.log(rms),row.target_logRMS)
    memberships={anchor:group.training_anchor.to_numpy() for anchor,group in members.groupby('prediction_anchor')}
    targets={'risk':'target_logRMS','mean':'target_mean_bps'};checked=0;max_error=0.
    for row in p.itertuples():
        current=f.loc[row.anchor];train=f.loc[memberships[row.anchor]]
        assert len(train)==row.training_labels and len(train)>=104
        assert (train.target_end<=row.formation_date).all()
        assert (train.formation_date<row.formation_date).all()
        assert train.target_end.max()==row.latest_training_target_end
        assert np.array_equal(memberships[row.anchor],members.loc[members.prediction_anchor==row.anchor,'training_anchor'])
        for target,column in targets.items():
            y=train[column].to_numpy()
            for model,cols in models.items():
                if cols:
                    scaler=StandardScaler().fit(train[cols])
                    # StandardScaler uses population SD; match the specified explicit near-zero floor.
                    scaler.scale_=np.where(train[cols].std(ddof=0).to_numpy()>1e-10,scaler.scale_,1.)
                    x=scaler.transform(train[cols]);now=scaler.transform(current[cols].to_frame().T)
                    fitted=Ridge(alpha=len(y),fit_intercept=True,solver='cholesky').fit(x,y)
                    predicted=float(fitted.predict(now)[0])
                else:predicted=float(y.mean())
                value=getattr(row,target+'_'+model)
                error=abs(predicted-value);max_error=max(max_error,error)
                assert error<1e-9
                if model in ['Controls','HistoryMean']:
                    assert np.isclose(value,old.loc[row.anchor,target+'_'+model],atol=1e-10)
                checked+=1
    metrics=pd.read_csv(OUT/'forecast_metrics.csv')
    comparisons=pd.read_csv(OUT/'paired_comparisons.csv')
    scored=pd.read_csv(OUT/'scored_losses.csv')
    for row in metrics.itertuples():
        take=p.loc[(p.score_period==row.period)&p.target_mean_bps.notna()].sort_values('formation_date')
        y=take[targets[row.target]].to_numpy();forecast=take[row.target+'_'+row.model].to_numpy()
        assert len(take)==row.forecasts and np.isclose(np.mean((y-forecast)**2),row.MSE)
        assert np.isclose(np.mean(np.abs(y-forecast)),row.MAE_native)
        if row.target=='risk':assert np.isclose(np.mean(np.abs(np.exp(y)-np.exp(forecast))),row.RMS_MAE_bps)
    # Independent resampling reconstruction: explicit circular block concatenation.
    max_interval_error=0.
    for pi,period in enumerate(['development','later']):
        n=233 if pi==0 else 138
        rng=np.random.default_rng(2026102951+pi)
        starts=rng.integers(n,size=(1000,int(np.ceil(n/12))))
        ix=np.array([np.concatenate([np.arange(start,start+12)%n for start in row])[:n] for row in starts])
        for target in targets:
            losses=scored.loc[(scored.period==period)&(scored.target==target)].pivot(
                index='anchor',columns='model',values='squared_error').sort_index()
            assert len(losses)==n
            for family,group in comparisons.loc[(comparisons.period==period)&(comparisons.target==target)].groupby('family',sort=False):
                names=group.model.tolist();reference=group.reference.iloc[0]
                differences=losses[names].to_numpy()-losses[reference].to_numpy()[:,None]
                center=differences.mean(axis=0);boot=differences[ix].mean(axis=1)
                low,high=np.quantile(boot,[.025,.975],axis=0)
                std=boot.std(axis=0,ddof=1)
                z=np.divide(boot-center,std,out=np.zeros_like(boot),where=std>1e-12)
                radius=np.quantile(np.max(np.abs(z),axis=1),.95)
                family_low,family_high=(low,high) if len(names)==1 else (center-radius*std,center+radius*std)
                for expected,actual in [(center,group.loss_difference),(low,group.point95_low),(high,group.point95_high),
                    (family_low,group.family95_low),(family_high,group.family95_high)]:
                    delta=np.max(np.abs(expected-actual));max_interval_error=max(max_interval_error,delta)
                    assert np.allclose(expected,actual,rtol=1e-10,atol=1e-10)
    summary=json.loads((OUT/'summary.json').read_text())
    for collection in ['protected_sha256','output_sha256']:
        for path,digest in summary[collection].items():
            assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    result=dict(passed=True,source_alignment_rows=len(f),forecast_anchors=len(p),independent_ridge_fits=checked,
        max_independent_forecast_difference=max_error,metric_rows_checked=len(metrics),
        paired_comparison_rows_checked=len(comparisons),max_interval_difference=max_interval_error,
        forecast_scores_per_model_target={'development':233,'later':138},
        original_HistoryMean_and_Controls_reproduced=True,source_strategy_unchanged=True,
        no_new_policy=True,checks=['VIX source/calendar lag alignment','all completed20-session labels from frozen PCA returns',
        'exact saved completed-label memberships','training-only population standardization',
        'all predictions via independent sklearn Ridge','all forecast metrics','paired losses and all bootstrap families',
        'original input/output hashes'])
    (OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
