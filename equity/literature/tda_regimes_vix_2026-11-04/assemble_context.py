"""Align existing cached TDA features with entry-available VIX for this review.

No topology is recomputed; no predictor is fitted and no trading result is changed.
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

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
FEATURES=ROOT/'equity/experiments/equity_full_basket_states/state_features_and_targets.csv'
VIX=ROOT/'market_data/datasets/mean_reversion_context_2026-11-04/vix_daily.csv'
CALENDAR=ROOT/'market_data/datasets/equity_daily_expanded_2016_2026-10-27/close_all.csv'
RETURNS=ROOT/'equity/experiments/equity_efa_vs_pca/daily_gross_returns.csv'


def main():
    protected=[FEATURES,VIX,CALENDAR,RETURNS]
    before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    features=pd.read_csv(FEATURES)
    calendar=pd.read_csv(CALENDAR,usecols=['date']).date.tolist()
    lookup={date:i for i,date in enumerate(calendar)}
    vix=pd.read_csv(VIX).set_index('date').close
    names=['formation_date','history_end','target_start','raw_H1_max_bps','raw_H1_sum_squared_bps2',
        'raw_H1_W1_bps','raw_H1_W1_shape','residual_H1_W1_shape','raw_log_scale','raw_covariance_change5']
    panel=features[names].copy().rename(columns={'history_end':'topology_feature_end','target_start':'first_execution'})
    observations=[calendar[lookup[date]-1] for date in panel.first_execution]
    preceding=[calendar[lookup[date]-2] for date in panel.first_execution]
    panel['vix_observation_date']=observations
    panel['vix_close_before_entry']=vix.loc[observations].to_numpy()
    panel['vix_log_change_before_entry']=np.log(vix.loc[observations].to_numpy()/vix.loc[preceding].to_numpy())
    panel['vix_band20to30']=(panel.vix_close_before_entry.ge(20)&panel.vix_close_before_entry.lt(30)).astype(int)
    assert len(panel)==490 and not panel.isna().any().any()
    assert (panel.vix_observation_date<panel.first_execution).all()
    assert (panel.topology_feature_end<panel.first_execution).all()
    assert (panel.vix_observation_date==panel.formation_date).all()
    panel.to_csv(OUT/'cached_tda_vix_context.csv',index=False)
    fig,axes=plt.subplots(3,1,figsize=(12,8),sharex=True,layout='constrained')
    dates=pd.to_datetime(panel.first_execution)
    axes[0].plot(dates,panel.vix_close_before_entry,color='#6a4c93',lw=1)
    axes[0].set_ylabel('Prior-session VIX')
    axes[1].plot(dates,panel.raw_H1_W1_bps,color='#247ba0',lw=1)
    axes[1].set_ylabel('Raw H1 diagram change\n(return-bps distance)')
    axes[2].plot(dates,panel.raw_H1_W1_shape,label='Raw-return cloud, normalized',color='#247ba0',lw=1)
    axes[2].plot(dates,panel.residual_H1_W1_shape,label='Residual cloud, normalized',color='#d97706',lw=1)
    axes[2].set_ylabel('H1 diagram change\n(normalized-distance units)');axes[2].legend(fontsize=8)
    for ax in axes:
        ax.axvline(pd.Timestamp('2024-01-01'),ls='--',lw=.8,color='#777')
        ax.grid(alpha=.2);ax.margins(x=.01)
    fig.suptitle('Existing TDA state-change features alongside entry-available VIX\n490 cached formation anchors; no new model, gate, or predictive claim',fontsize=13)
    axes[2].set_xlabel('First execution date; each topology value retains its original older feature-end timestamp')
    fig.savefig(OUT/'cached_tda_and_vix.png',dpi=160,bbox_inches='tight');plt.close(fig)
    after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    assert before==after
    (OUT/'context_validation.json').write_text(json.dumps(dict(
        status='Read-only alignment and plot; not a new strategy/forecast experiment',rows=len(panel),
        first_execution=panel.first_execution.min(),last_execution=panel.first_execution.max(),
        missing_context_rows=0,source_files_unchanged=True,sha256=before,
        information_timing='VIX uses last completed equity-session close before first_execution; TDA retains original topology_feature_end',
        no_future_return_labels_in_output=True),indent=2)+'\n')
    print(f'Aligned {len(panel)} cached TDA anchors with prior-session VIX; no missing rows; sources unchanged.')


if __name__=='__main__':main()
