"""Independent source alignment, statistics, HAC and chronological forecast checks."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).with_name('factor_reversal_vix')


def main():
    panel=pd.read_csv(OUT/'aligned_daily_panel.csv').set_index('date')
    prices=pd.read_csv(ROOT/'market_data/datasets/equity_daily_expanded_2016_2026-10-27/close_all.csv').set_index('date').SPY
    vix=pd.read_csv(ROOT/'market_data/datasets/mean_reversion_context_2026-11-04/vix_daily.csv').set_index('date').close
    source_path=ROOT/'equity/experiments/equity_efa_vs_pca/daily_gross_returns.csv'
    source=pd.read_csv(source_path)
    frozen=json.loads((ROOT/'equity/experiments/equity_efa_overall_profit/provenance.json').read_text())
    assert hashlib.sha256(source_path.read_bytes()).hexdigest()==frozen['source_sha256']
    for row in panel.itertuples():
        i=prices.index.get_loc(row.Index)
        prior=prices.index[i-1]; earlier=prices.index[i-2]
        assert row.previous_session==prior
        assert np.isclose(row.vix_lag,vix.loc[prior])
        assert np.isclose(row.log_vix_lag,np.log(vix.loc[prior]))
        assert np.isclose(row.vix_log_change_lag,np.log(vix.loc[prior]/vix.loc[earlier]))
        assert np.isclose(row.vix_log_change_same,np.log(vix.loc[row.Index]/vix.loc[prior]))
        assert np.isclose(row.spy_return_lag,prices.iloc[i-1]/prices.iloc[i-2]-1)
        past=prices.iloc[i-21:i].to_numpy()
        rv=np.std(past[1:]/past[:-1]-1,ddof=1)*np.sqrt(252)
        assert np.isclose(row.log_spy_rv20_lag,np.log(rv))
    for model in ['PCA3','EFA3']:
        original=source.loc[source.model==model].sort_values('date')
        assert np.array_equal(original.date.values,panel.index.values)
        assert np.array_equal(original.gross_return.values,panel[model].values)
    conditional=pd.read_csv(OUT/'conditional_returns.csv')
    def subset(period):
        if period=='full':return panel
        return panel.loc[panel.index<'2024-01-01'] if period=='earlier' else panel.loc[panel.index>='2024-01-01']
    for row in conditional.itertuples():
        sub=subset(row.period)
        values=sub.loc[sub[row.category]==row.bin,row.model].to_numpy()*1e4
        assert len(values)==row.days
        assert np.isclose(values.mean(),row.mean_bps)
        assert np.isclose(np.std(values,ddof=1)*np.sqrt(252)/100,row.annualized_conditional_vol_pct)
    # Independent library HAC, including the finite-sample correction.
    regression=pd.read_csv(OUT/'regressions_hac.csv')
    design_columns={'VIXOnly':['log_vix_lag','vix_log_change_lag'],
        'Controls':['log_spy_rv20_lag','spy_return_lag'],
        'ControlsVIX':['log_spy_rv20_lag','spy_return_lag','log_vix_lag','vix_log_change_lag'],
        'SameDayDiagnostic':['log_spy_rv20_lag','spy_return_lag','log_vix_lag','vix_log_change_lag','vix_log_change_same']}
    for keys,rows in regression.groupby(['model','period','target','design']):
        model,period,target,design=keys
        sub=subset(period);columns=design_columns[design]
        y=sub[model].to_numpy()*1e4
        if target=='absolute_return':y=np.abs(y)
        fit=sm.OLS(y,sm.add_constant(sub[columns].to_numpy())).fit(cov_type='HAC',cov_kwds={'maxlags':20,'use_correction':True})
        assert np.allclose(fit.params,rows.coefficient,rtol=1e-8,atol=1e-8)
        assert np.allclose(fit.bse,rows.hac20_se,rtol=1e-8,atol=1e-8)
    pred=pd.read_csv(OUT/'forecast_predictions.csv')
    assert (pred.training_end<pred.date).all()
    assert len(pred)==1942*2*2*3
    checked=0
    forecast_design={'Constant':[],**{k:v for k,v in design_columns.items() if k in ['Controls','ControlsVIX']}}
    # Refitting every saved training window independently verifies chronology and all forecasts.
    for keys,rows in pred.groupby(['model','target','design','training_end']):
        model,target,design,end=keys
        train=panel.loc[panel.index<=end];test=panel.loc[rows.date]
        assert len(train)==rows.training_n.iloc[0] and len(rows)<=21
        assert rows.date.iloc[0]==panel.index[len(train)]
        cols=forecast_design[design]
        x=sm.add_constant(train[cols].to_numpy(),has_constant='add')
        xx=sm.add_constant(test[cols].to_numpy(),has_constant='add')
        y=train[model].to_numpy()*1e4
        if target=='absolute_return':y=np.abs(y)
        fit=sm.OLS(y,x).fit()
        expected=fit.predict(xx)
        if target=='absolute_return':expected=np.maximum(0,expected)
        assert np.allclose(expected,rows.predicted_bps,rtol=1e-8,atol=1e-8)
        actual=test[model].values*1e4
        if target=='absolute_return':actual=np.abs(actual)
        assert np.allclose(actual,rows.actual_bps)
        assert np.allclose((actual-expected)**2,rows.squared_error)
        checked+=len(rows)
    comparisons=pd.read_csv(OUT/'forecast_comparisons.csv')
    for row in comparisons.itertuples():
        mask=(pred.model==row.model)&(pred.target==row.target)
        if row.period=='earlier':mask&=pred.date<'2024-01-01'
        elif row.period=='later':mask&=pred.date>='2024-01-01'
        wide=pred.loc[mask].pivot(index='date',columns='design',values='squared_error')
        delta=(wide.ControlsVIX-wide.Controls).mean()
        assert len(wide)==row.days and np.isclose(delta,row.loss_difference_bps_squared)
        assert np.isclose(-delta/wide.Controls.mean()*100,row.mse_improvement_pct)
    manifest=json.loads((OUT/'run_manifest.json').read_text())
    for path,digest in manifest['sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    report={'passed':True,'strategy_source_matches_frozen_provenance':True,
        'daily_feature_rows_independently_checked':len(panel),
        'forecast_rows_independently_refitted':checked,'hac_regressions_checked':48,
        'conditional_rows_checked':len(conditional),'input_output_hashes_checked':len(manifest['sha256']),
        'checks':['full equity-calendar lag alignment','all frozen PCA/EFA returns unchanged',
                  'independent source-based feature reconstruction','conditional statistics',
                  'all OLS/HAC fits versus statsmodels','every expanding forecast versus raw-feature statsmodels OLS',
                  'training ends before execution','all paired forecast losses','manifest hashes']}
    (OUT/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
