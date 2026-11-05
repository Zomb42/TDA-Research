"""Read-only reconstruction of original30 returns, H0 pilot and structural cuts."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.spatial.distance import pdist

EQ = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
EXP = EQ/"experiments"
DATA = EQ/"market_data/datasets/equity_daily_30_2016_2026-10-27"


def metrics(r):
    r = np.asarray(r); curve = np.cumprod(1+r); sd = r.std(ddof=1)
    centered = r-r.mean(); n = len(r)
    lr = centered@centered/n
    for lag in range(1, 6): lr += 2*(1-lag/6)*(centered[lag:]@centered[:-lag]/n)
    se = np.sqrt(max(lr, 0)/n)
    return {"days": n, "mean_daily_bps": r.mean()*1e4, "mean_daily_bps_hac95_low": (r.mean()-1.96*se)*1e4,
        "mean_daily_bps_hac95_high": (r.mean()+1.96*se)*1e4, "annualized_arithmetic_mean": r.mean()*252,
        "annualized_volatility": sd*np.sqrt(252), "sharpe_vs_zero": r.mean()/sd*np.sqrt(252),
        "compound_annual_growth": curve[-1]**(252/n)-1, "total_compound_return": curve[-1]-1,
        "max_drawdown": (curve/np.maximum.accumulate(np.r_[1., curve])[1:]-1).min(), "positive_day_fraction": (r>0).mean()}


def fit(history, market):
    mc = market-market.mean(); hc = history-history.mean(axis=0)
    beta = mc@hc/(mc@mc); residual = hc-mc[:, None]*beta
    sigma = residual.std(axis=0, ddof=1); z = residual/sigma
    values, vectors = np.linalg.eigh(z.T@z/(len(z)-1)); v = vectors[:, np.argsort(values)[::-1]]
    return beta, sigma, v, 1/np.maximum(history.std(axis=0, ddof=1), .0001)**2, z


def holding(signal, exposure, weights):
    e = signal-exposure@np.linalg.solve(exposure.T@(weights[:, None]*exposure), exposure.T@(weights*signal))
    return -weights*e/abs(weights*e).sum()


def main():
    panel = pd.read_csv(DATA/"returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    names = pd.read_csv(DATA/"universe.csv").query("role=='equity'").symbol.tolist()
    x = panel[names].to_numpy(); m = panel.SPY.to_numpy()
    bars = pd.read_csv(DATA/"bars_raw.csv", parse_dates=["date"])
    opens = bars.pivot(index="date", columns="symbol", values="o").reindex(index=panel.index, columns=names).to_numpy()
    closes = bars.pivot(index="date", columns="symbol", values="c").reindex(index=panel.index, columns=names).to_numpy()
    future = closes/opens-1
    baseline = pd.read_csv(EXP/"equity_residual_backtest/gross_report/daily_returns_and_diagnostics.csv", parse_dates=["date","signal_date","training_end"])
    pos = pd.read_csv(EXP/"equity_residual_backtest/evaluated/daily_positions.csv", parse_dates=["date"])
    pos = pos.pivot(index=["date","model"], columns="symbol", values="unit_gross_target_dollars").reindex(columns=names)
    pilot = pd.read_csv(EXP/"equity_h0_peers/daily_gross_and_structure.csv", parse_dates=["date","signal_date","training_end"])
    group = pd.read_csv(EXP/"equity_h0_peers/daily_group_assignments.csv", parse_dates=["date"]).set_index(["date","model"])
    base_lookup = baseline.set_index(["date","model"]); pilot_lookup = pilot.set_index(["date","model"])
    sensitivity = pd.read_csv(EXP/"equity_residual_diagnostics/component_sensitivity_daily.csv", parse_dates=["date"]).set_index(["date","residual_pcs"])
    max_return_error = 0.; max_holding_error = 0.; label_checks = 0
    for t in range(120, len(panel)-1):
        beta, scale, v, weights, z = fit(x[t-120:t], m[t-120:t])
        base = np.c_[np.ones(30), beta]; date = panel.index[t+1]
        matrices = {"SPY_only":base,"SPY_plus_3_residual_PCs":np.c_[base, scale[:, None]*v[:,:3]]}
        for model, exposure in matrices.items():
            h = holding(x[t], exposure, weights)
            max_holding_error = max(max_holding_error, float(abs(h-pos.loc[(date, model)].to_numpy()).max()))
            max_return_error = max(max_return_error, abs(h@future[t+1]-base_lookup.loc[(date, model),"gross_return"]))
            assert base_lookup.loc[(date,model),"training_end"] == panel.index[t-1]
        for k in [0,1,3,5,10]:
            h = holding(x[t], np.c_[base,scale[:,None]*v[:,:k]], weights)
            max_return_error = max(max_return_error,abs(h@future[t+1]-sensitivity.loc[(date,k),"gross_return"]))
        for model in ["Manual6","Average6","Single6","H0_6","PCA5"]:
            if model == "PCA5": exposure = np.c_[base,scale[:,None]*v[:,:5]]
            else:
                labels = group.loc[(date,model),names].to_numpy(dtype=int)
                exposure = np.c_[np.eye(6)[labels],beta]
                if t in [120,500,1000,1500,2000,len(panel)-2] and model in ["Average6","Single6","H0_6"]:
                    method = "average" if model=="Average6" else "single"
                    expected = cut_tree(linkage(pdist(z.T/np.sqrt(119)),method=method),n_clusters=[6])[:,0]
                    assert np.array_equal(labels[:,None]==labels,expected[:,None]==expected)
                    label_checks+=1
            h = holding(x[t], exposure, weights)
            max_return_error = max(max_return_error,abs(h@future[t+1]-pilot_lookup.loc[(date,model),"gross_return"]))
        assert np.isclose(pilot_lookup.loc[(date,"Single6"),"gross_return"],pilot_lookup.loc[(date,"H0_6"),"gross_return"],atol=1e-12)
    assert max_return_error < 1e-10 and max_holding_error < 1e-9
    max_metric_error = 0.
    for folder,ledger,filename in [("equity_residual_backtest/gross_report",baseline,"performance.csv"),("equity_h0_peers",pilot,"gross_performance_and_structure.csv")]:
        saved = pd.read_csv(EXP/folder/filename).set_index(["period","model"])
        for key, frame in ledger.groupby(["period","model"]):
            for field, value in metrics(frame.sort_values("date").gross_return).items():
                err=abs(saved.loc[key,field]-value); max_metric_error=max(max_metric_error,err)
                assert np.isclose(saved.loc[key,field],value,atol=1e-9)
    # Every original hierarchy cut: independent distances and future correlations.
    anchors = pd.read_csv(EXP/"equity_h0_scale_robustness/anchors.csv",parse_dates=["fit_start","fit_end","signal_date","future_start","future_end"])
    cuts = pd.read_csv(EXP/"equity_h0_scale_robustness/all_cut_measurements.csv").set_index(["anchor","method","groups"])
    ii,jj=np.triu_indices(30,1); max_gap_error=0.
    for a in anchors.itertuples():
        t=panel.index.get_loc(a.signal_date); beta,scale,v,w,z=fit(x[t-120:t],m[t-120:t])
        assert a.fit_end==panel.index[t-1] and a.future_start==panel.index[t+1] and a.future_end==panel.index[t+20]
        intercept=x[t-120:t].mean(axis=0)-m[t-120:t].mean()*beta
        residual=x[t+1:t+21]-intercept-m[t+1:t+21,None]*beta
        correlations=np.corrcoef(residual,rowvar=False)[ii,jj]
        for method,label in [("single","Single_H0"),("average","Average")]:
            tree=linkage(pdist(z.T/np.sqrt(119)),method=method)
            for k in range(1,31):
                labels=np.arange(30) if k==30 else cut_tree(tree,n_clusters=[k])[:,0]
                mask=labels[ii]==labels[jj]; saved=cuts.loc[(a.anchor,label,k)]
                assert saved.within_pairs==mask.sum() and saved.largest_group==np.bincount(labels).max()
                if k in [1,30]: assert pd.isna(saved.future_gap)
                else:
                    gap=correlations[mask].mean()-correlations[~mask].mean()
                    max_gap_error=max(max_gap_error,abs(gap-saved.future_gap))
    assert max_gap_error<1e-10
    # Original descriptive PCA, using only its stated 2016-2023 input sample.
    dev=panel.loc[:"2023-12-31",names];z=((dev-dev.mean())/dev.std(ddof=1)).to_numpy()
    u,s,vt=np.linalg.svd(z,full_matrices=False);fraction=s*s/np.sum(s*s)
    old=json.loads((EXP/"equity_correlation_pca/summary.json").read_text())
    assert np.allclose(fraction,old["pca_variance_share"])
    assert np.isclose(abs(np.corrcoef(z@vt[0],panel.loc[dev.index,"SPY"])[0,1]),abs(old["pc1_spy_correlation"]))
    result={"checks":{"all_original30_daily_holdings_and_returns_reconstructed":True,"all_five_PC_sensitivity_return_series_reconstructed":True,
        "all_H0_peer_pilot_returns_reconstructed":True,"selected_daily_peer_labels_reconstructed":True,"all_30_cuts_for_127_structural_anchors_reconstructed":True,
        "original_PCA_variance_and_SPY_correlation_recomputed":True,"all_legacy_gross_performance_and_HAC_intervals_recomputed":True},
        "original_daily_dates":len(baseline)//2,"label_checks":label_checks,"structural_anchors":len(anchors),
        "max_holding_error":max_holding_error,"max_return_error":max_return_error,"max_metric_error":max_metric_error,"max_gap_error":max_gap_error}
    (OUT/"legacy_checks.json").write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result,indent=2),flush=True)


if __name__=="__main__": main()
