"""Independent checks of the fixed VIX-band policy and nonlinear forecast follow-up."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).with_name('factor_vix_20_30')


def main():
    panel=pd.read_csv(OUT.parent/'factor_reversal_vix/aligned_daily_panel.csv',index_col='date')
    panel['band20to30']=((panel.vix_lag>=20)&(panel.vix_lag<30)).astype(float)
    original=ROOT/'equity/experiments/equity_efa_vs_pca/daily_gross_returns.csv'
    provenance=json.loads((ROOT/'equity/experiments/equity_efa_overall_profit/provenance.json').read_text())
    assert hashlib.sha256(original.read_bytes()).hexdigest()==provenance['source_sha256']
    boundary=np.array([19.99,20.,29.999,30.,30.01])
    assert ((boundary>=20)&(boundary<30)).tolist()==[False,True,True,False,False]
    perf=pd.read_csv(OUT/'performance.csv');curves=pd.read_csv(OUT/'daily_curves.csv')
    def subperiod(period):
        if period=='full':return panel
        return panel.loc[panel.index<'2024-01-01'] if period=='earlier' else panel.loc[panel.index>='2024-01-01']
    for row in perf.itertuples():
        sub=subperiod(row.period);r=sub[row.model].to_numpy();g=sub.band20to30.to_numpy()
        if row.policy=='AlwaysOn':exposure=np.ones(len(r))
        elif row.policy=='Target20to30':exposure=g
        elif row.policy=='Outside20to30':exposure=1-g
        elif row.policy=='ConstantExposureMatch':exposure=np.full(len(r),g.mean())
        elif row.policy=='ConstantVolatilityMatch':exposure=np.full(len(r),np.std(r*g,ddof=1)/np.std(r,ddof=1))
        else:exposure=sub.vix_bin.eq(row.policy.removeprefix('Only_')).to_numpy().astype(float)
        rr=r*exposure;wealth=100000.;peak=wealth;max_drawdown=0.
        for value in rr:
            wealth*=1+value;peak=max(peak,wealth);max_drawdown=min(max_drawdown,wealth/peak-1)
        assert np.isclose(wealth,row.ending_100k)
        assert np.isclose((wealth/100000)**(252/len(rr))-1,row.cagr_pct/100)
        assert np.isclose(max_drawdown,row.max_drawdown_pct/100)
        assert np.isclose(np.std(rr,ddof=1)*np.sqrt(252)*100,row.annual_vol_pct)
        assert np.isclose(rr.mean()*1e4,row.mean_calendar_bps)
        assert np.isclose(exposure.mean(),row.mean_gross_exposure)
        assert np.count_nonzero(exposure)==row.active_days
        if row.policy=='ConstantVolatilityMatch':assert np.isclose(np.std(rr,ddof=1),np.std(r*g,ddof=1))
        if row.period=='full':
            saved=curves.loc[(curves.model==row.model)&(curves.policy==row.policy)]
            assert np.array_equal(saved.date.values,sub.index.values)
            assert np.allclose(saved.return_gross,rr,rtol=1e-12,atol=1e-16)
            assert np.allclose(saved.equity_100k,100000*np.cumprod(1+rr))
    annual=pd.read_csv(OUT/'annual_returns.csv')
    for row in annual.itertuples():
        daily=curves.loc[(curves.model==row.model)&(curves.policy==row.policy)&curves.date.str.startswith(str(row.year))]
        assert np.isclose((np.prod(1+daily.return_gross)-1)*100,row.return_pct)
        assert (daily.gross_exposure>0).sum()==row.active_days
    # Reconstruct contiguous episode boundaries and known-at-entry ages from a scalar scan.
    expected=[];number=0;age=0;origin=None
    for i,(date,row) in enumerate(panel.iterrows()):
        if row.band20to30:
            if age==0:
                number+=1
                prior=panel.vix_lag.iloc[i-1] if i else np.nan
                origin='from_below20' if prior<20 else 'from30plus' if prior>=30 else 'initial_unknown'
            age+=1
            expected.append((date,number,age,origin))
        else:age=0
    episode_days=pd.read_csv(OUT/'episode_daily.csv')
    assert len(expected)==len(episode_days)==625
    for row,(date,n,age,origin) in zip(episode_days.itertuples(),expected):
        assert (row.date,row.episode,row.age,row.origin)==(date,n,age,origin)
    episode=pd.read_csv(OUT/'episodes.csv')
    for row in episode.itertuples():
        dates=episode_days.loc[episode_days.episode==row.episode,'date']
        rr=panel.loc[dates,row.model]
        assert len(rr)==row.days and dates.iloc[0]==row.start and dates.iloc[-1]==row.end
        assert np.isclose((np.prod(1+rr)-1)*100,row.return_pct)
    loo=pd.read_csv(OUT/'leave_year_out.csv')
    for row in loo.itertuples():
        sub=subperiod(row.period)
        sub=sub.loc[~sub.index.str.startswith(str(row.omitted_year))]
        g=sub.band20to30.values;rr=sub[row.model].to_numpy()
        assert np.isclose(rr[g>0].mean()*1e4,row.gate_mean_active_bps)
        assert np.isclose((np.prod(1+rr*g)**(252/len(sub))-1)*100,row.gate_cagr_pct)
    linear=['log_spy_rv20_lag','spy_return_lag','log_vix_lag','vix_log_change_lag']
    reg=pd.read_csv(OUT/'band_regressions.csv')
    for keys,rows in reg.groupby(['model','period','design']):
        model,period,design=keys;sub=subperiod(period)
        cols=(linear if design=='LinearVIXBand' else linear[:2])+['band20to30']
        fit=sm.OLS(sub[model].values*1e4,sm.add_constant(sub[cols].values)).fit(
            cov_type='HAC',cov_kwds={'maxlags':20,'use_correction':True})
        assert np.allclose(fit.params,rows.coefficient,rtol=1e-8,atol=1e-8)
        assert np.allclose(fit.bse,rows.hac20_se,rtol=1e-8,atol=1e-8)
    pred=pd.read_csv(OUT/'forecast_predictions.csv');checked=0
    for keys,rows in pred.groupby(['model','design','training_end']):
        model,design,end=keys;train=panel.loc[panel.index<=end];test=panel.loc[rows.date]
        cols=linear+(['band20to30'] if design=='LinearVIXBand' else [])
        fit=sm.OLS(train[model].values*1e4,sm.add_constant(train[cols].values,has_constant='add')).fit()
        expected=fit.predict(sm.add_constant(test[cols].values,has_constant='add'))
        assert len(train)==rows.training_n.iloc[0] and (rows.training_end<rows.date).all()
        assert rows.date.iloc[0]==panel.index[len(train)]
        assert np.allclose(expected,rows.predicted_bps,rtol=1e-8,atol=1e-8)
        assert np.allclose((rows.actual_bps-expected)**2,rows.squared_error)
        checked+=len(rows)
    comp=pd.read_csv(OUT/'forecast_comparison.csv')
    for row in comp.itertuples():
        sub=pred.loc[pred.model==row.model]
        if row.period=='earlier':sub=sub.loc[sub.date<'2024-01-01']
        elif row.period=='later':sub=sub.loc[sub.date>='2024-01-01']
        loss=sub.pivot(index='date',columns='design',values='squared_error')
        assert np.isclose((loss.LinearVIXBand-loss.LinearVIX).mean(),row.loss_difference_bps_squared)
    manifest=json.loads((OUT/'run_manifest.json').read_text())
    for path,digest in manifest['sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    result=dict(passed=True,performance_rows_checked=len(perf),curve_rows_checked=len(curves),
        annual_rows_checked=len(annual),episodes_checked=len(episode),active_date_rows_checked=len(episode_days),
        leave_year_out_rows_checked=len(loo),hac_models_checked=12,forecast_rows_refitted=checked,
        strategy_source_matches_frozen_provenance=True,hashes_checked=len(manifest['sha256']),
        checks=['20 included and30 excluded','whole-calendar wealth/drawdown/exposure',
                'hindsight control calibration','annual decomposition','contiguous episodes and entry-available origins/ages',
                'year deletion diagnostics','independent statsmodels HAC and all nonlinear forecasts',
                'past-only forecast chronology','paired forecast losses','source/output hashes'])
    (OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
