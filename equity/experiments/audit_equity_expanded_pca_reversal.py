"""Independent formation, ledger, horizon, PCA and interval reconstruction."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from scipy.spatial.distance import pdist, squareform

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"experiments/equity_expanded_pca_reversal"
DATA = ROOT/"market_data/datasets/equity_daily_expanded_2016_2026-10-27"
MODELS = ["SPY_only", "SPY_PCA3", "Sector11", "Average11", "SPY_PCA10"]


def main():
    result = json.loads((OUT/"summary.json").read_text())
    spec = result["configuration"]
    daily = pd.read_csv(OUT/"daily_gross_returns.csv", parse_dates=["signal_date", "date", "training_end"])
    events = pd.read_csv(OUT/"horizon_events.csv", parse_dates=["signal_date", "entry", "exit"])
    formations = pd.read_csv(OUT/"formation_dates.csv", parse_dates=["signal_date", "entry", "training_end", "eligibility_start"])
    performance = pd.read_csv(OUT/"gross_performance.csv")
    horizon_summary = pd.read_csv(OUT/"horizon_summary.csv")
    control = pd.read_csv(OUT/"paired_universe_differences.csv")
    universe = pd.read_csv(DATA/"universe.csv").query("role == 'equity'").set_index("symbol")
    positions = np.load(OUT/"positions.npz")
    symbols = positions["symbols"].tolist(); old_names = positions["original_symbols"].tolist()
    panel = pd.read_csv(DATA/"returns_log.csv", index_col="date", parse_dates=True).iloc[1:]
    raw_x = panel[symbols].to_numpy(); market = panel.SPY.to_numpy()
    signal_indices = panel.index.get_indexer(pd.to_datetime(positions["dates"]))
    assert (daily.training_end < daily.signal_date).all() and (daily.signal_date < daily.date).all()
    for f, t in zip(formations.itertuples(), signal_indices):
        expected = np.array(symbols)[np.isfinite(raw_x[t-272:t]).all(axis=0)].tolist()
        assert f.symbols.split("|") == expected and f.stocks == len(expected)
        assert panel.index[t-1] == f.training_end and panel.index[t-272] == f.eligibility_start
        assert panel.index[t+1] == f.entry
    prices = {}
    for mode in ["raw", "all"]:
        bars = pd.read_csv(DATA/f"bars_{mode}.csv", parse_dates=["date"])
        prices[mode] = {field: bars.pivot(index="date", columns="symbol", values=field).reindex(index=panel.index, columns=symbols).to_numpy() for field in ["o", "c"]}
    raw_future = prices["raw"]["c"][signal_indices+1]/prices["raw"]["o"][signal_indices+1]-1
    index_by_date = {str(d.date()): i for i, d in enumerate(pd.to_datetime(positions["dates"]))}
    max_ledger_error, max_reconstruction_error, max_slope_error = 0., 0., 0.
    for (name, window, model), frame in daily.groupby(["universe", "window", "model"]):
        frame = frame.sort_values("signal_date")
        h = positions["expanded"][:, [120,252].index(window), MODELS.index(model)] if name == "expanded200" else positions["original"][:, [120,252].index(window), MODELS[:2].index(model)]
        cols = np.arange(len(symbols)) if name == "expanded200" else np.array([symbols.index(s) for s in old_names])
        future = raw_future[:, cols]
        assert np.isfinite(future[abs(h)>1e-12]).all()
        # Zero terms for securities outside the admitted universe are excluded
        # from the sum; active missing returns are never replaced by zero.
        measured = np.sum(np.where(h != 0, h*np.nan_to_num(future), 0), axis=1)
        max_ledger_error = max(max_ledger_error, float(np.max(abs(measured-frame.gross_return.to_numpy()))))
        assert np.allclose(abs(h).sum(axis=1), 1) and np.allclose(h.sum(axis=1), 0, atol=1e-10)
    for (name, window, model, horizon), frame in events.groupby(["universe", "window", "model", "horizon"]):
        frame = frame.sort_values("signal_date")
        ids = np.array([index_by_date[str(d.date())] for d in frame.signal_date])
        t = signal_indices[ids]
        assert np.array_equal(panel.index[t+1], frame.entry)
        assert np.array_equal(panel.index[t+horizon], frame.exit)
        assert ((frame.entry < pd.Timestamp("2024-01-01")) == (panel.index[t+20] < pd.Timestamp("2024-01-01"))).all()
        h = positions["expanded"][ids, [120,252].index(window), MODELS.index(model)] if name == "expanded200" else positions["original"][ids, [120,252].index(window), MODELS[:2].index(model)]
        cols = np.arange(len(symbols)) if name == "expanded200" else np.array([symbols.index(s) for s in old_names])
        future = (prices["all"]["c"][t+horizon]/prices["all"]["o"][t+1]-1)[:, cols]
        assert np.isfinite(future[abs(h)>1e-12]).all()
        measured = np.sum(h*np.nan_to_num(future), axis=1)
        max_ledger_error = max(max_ledger_error, float(np.max(abs(measured-frame.gross_event_return.to_numpy()))))
    # Independently fit covariance eigenvectors and solve WLS normal equations,
    # unlike the primary script's SVD and least-squares constructor.
    for di in np.unique(np.linspace(0, len(formations)-1, 13).astype(int)):
        t = signal_indices[di]
        eligible = np.flatnonzero(np.isfinite(raw_x[t-272:t]).all(axis=0))
        for wi, window in enumerate([120,252]):
            for name, columns in [("expanded200",eligible),("original30",np.array([symbols.index(s) for s in old_names]))]:
                history = raw_x[t-window:t, columns]; m = market[t-window:t]
                fit = np.linalg.lstsq(np.c_[np.ones(window),m], history, rcond=None)[0]
                e_hist = history-np.c_[np.ones(window),m]@fit
                sigma = np.maximum(history.std(axis=0,ddof=1),.0001)
                residual_sigma = np.maximum(e_hist.std(axis=0,ddof=1),.0001)
                z = (e_hist-e_hist.mean(axis=0))/residual_sigma
                values,vectors = np.linalg.eigh(z.T@z/(window-1));vectors=vectors[:,np.argsort(values)[::-1]]
                base = np.c_[np.ones(len(columns)),fit[1]]
                exposures = {"SPY_only":base,"SPY_PCA3":np.c_[base,residual_sigma[:,None]*vectors[:,:3]]}
                if name == "expanded200":
                    sectors = pd.factorize(universe.iloc[columns].sector_snapshot,sort=False)[0]
                    distance = squareform(pdist(z.T/np.sqrt(window-1)))
                    average = cut_tree(linkage(squareform(distance),method="average"),n_clusters=[11])[:,0]
                    exposures.update(Sector11=np.c_[np.eye(11)[sectors],fit[1]],Average11=np.c_[np.eye(11)[average],fit[1]],SPY_PCA10=np.c_[base,residual_sigma[:,None]*vectors[:,:10]])
                weights=1/sigma**2
                for model,exposure in exposures.items():
                    coefficients=np.linalg.solve(exposure.T@(weights[:,None]*exposure),exposure.T@(weights*raw_x[t,columns]))
                    e=raw_x[t,columns]-exposure@coefficients
                    holding=-weights*e/abs(weights*e).sum()
                    saved=positions["expanded"][di,wi,MODELS.index(model),columns] if name=="expanded200" else positions["original"][di,wi,MODELS[:2].index(model)]
                    max_reconstruction_error=max(max_reconstruction_error,float(np.max(abs(holding-saved))))
                    assert np.max(abs(exposure.T@holding))<1e-9
                    frame=events.loc[events.signal_date.eq(panel.index[t])&events.universe.eq(name)&events.window.eq(window)&events.model.eq(model)]
                    for row in frame.itertuples():
                        future=prices["all"]["c"][t+row.horizon,columns]/prices["all"]["o"][t+1,columns]-1
                        future_residual=future-exposure@np.linalg.solve(exposure.T@(weights[:,None]*exposure),exposure.T@(weights*future))
                        cross=(e*weights)@future_residual
                        max_slope_error=max(max_slope_error,abs(cross-row.cross_product))
                        assert np.isclose((e*weights)@e,row.signal_squared)
    assert max_ledger_error<1e-10 and max_reconstruction_error<1e-8 and max_slope_error<1e-8
    old=pd.read_csv(ROOT/"experiments/equity_residual_backtest/evaluated/daily_returns_and_diagnostics.csv",parse_dates=["date"])
    sample=daily.loc[daily.universe.eq("original30")&daily.window.eq(120)].copy()
    sample["legacy_model"]=sample.model.map({"SPY_only":"SPY_only","SPY_PCA3":"SPY_plus_3_residual_PCs"})
    joined=sample.merge(old[["date","model","gross_return"]],left_on=["date","legacy_model"],right_on=["date","model"],suffixes=("","_old"))
    historical_error=float(abs(joined.gross_return-joined.gross_return_old).max())
    assert len(joined)==len(sample) and historical_error<1e-10
    # Reconstruct every reported daily/event mean, percentile interval, pooled
    # slope and paired universe difference from the recorded date sequence.
    for pi,period in enumerate(["development","later"]):
        def indices(n,seed):
            rng=np.random.default_rng(seed);starts=rng.integers(n,size=(1000,int(np.ceil(n/60))))
            return ((starts[:,:,None]+np.arange(60))%n).reshape(1000,-1)[:,:n]
        for row in performance.loc[performance.period.eq(period)].itertuples():
            f=daily.loc[daily.period.eq(period)&daily.universe.eq(row.universe)&daily.window.eq(row.window)&daily.model.eq(row.model)].sort_values("signal_date")
            values=f.gross_return.to_numpy();boot=values[indices(len(values),spec["seed"]+pi)].mean(axis=1)*1e4
            assert np.isclose(values.mean()*1e4,row.mean_daily_bps)
            assert np.allclose(np.quantile(boot,[.025,.975]),[row.mean_low,row.mean_high])
            equity=np.cumprod(1+values)
            assert np.isclose(equity[-1]-1,row.total_gross_return)
        for row in horizon_summary.loc[horizon_summary.period.eq(period)].itertuples():
            f=events.loc[events.period.eq(period)&events.universe.eq(row.universe)&events.window.eq(row.window)&events.model.eq(row.model)&events.horizon.eq(row.horizon)].sort_values("signal_date")
            sample=indices(len(f),spec["seed"]+100+pi)
            boot=f.gross_event_return.to_numpy()[sample].mean(axis=1)*1e4
            assert np.isclose(f.gross_event_return.mean()*1e4,row.mean_event_bps)
            assert np.allclose(np.quantile(boot,[.025,.975]),[row.mean_low,row.mean_high])
            slopes=f.cross_product.to_numpy()[sample].sum(axis=1)/f.signal_squared.to_numpy()[sample].sum(axis=1)
            assert np.isclose(f.cross_product.sum()/f.signal_squared.sum(),row.response_slope)
            assert np.allclose(np.quantile(slopes,[.025,.975]),[row.slope_low,row.slope_high])
        for row in control.loc[control.period.eq(period)].itertuples():
            f=daily.loc[daily.period.eq(period)&daily.window.eq(row.window)&daily.model.eq(row.model)]
            pivot=f.pivot(index="signal_date",columns="universe",values="gross_return")
            difference=(pivot.expanded200-pivot.original30).to_numpy()
            boot=difference[indices(len(difference),spec["seed"]+pi)].mean(axis=1)*1e4
            assert np.isclose(difference.mean()*1e4,row.expanded_minus_original_mean_bps)
            assert np.allclose(np.quantile(boot,[.025,.975]),[row.low,row.high])
    for row in result["descriptive_PCA"]:
        names=old_names if row["universe"]=="original30" else symbols
        frame=panel.loc[:"2023-12-31",names].dropna(axis=1)
        normalized=(frame-frame.mean())/frame.std(ddof=1)
        values=np.linalg.eigvalsh(normalized.corr().to_numpy())[::-1]
        assert len(frame.columns)==row["stocks"] and len(frame)==row["return_observations"]
        assert np.isclose(values[0]/values.sum(),row["PC1_fraction"])
        assert np.isclose(values[:10].sum()/values.sum(),row["PC10_cumulative"])
    for path,expected in result["protected_sha256"].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected
    report={"checks":{"past_only_common_admission_and_chronology":True,"all_daily_and_horizon_ledgers_reconciled":True,
        "initial_gross_and_dollar_constraints":True,"thirteen_dates_independently_reconstructed_with_covariance_eigenvectors_and_WLS_normal_equations":True,
        "future_relative_projection_slope_identity":True,"original30_all_overlap_dates_reproduce_frozen_strategy":True,
        "all_daily_event_slope_and_paired_universe_intervals_reproduced":True,"descriptive_PCA_independently_reproduced":True,
        "prior_data_sources_and_results_unchanged":True},"max_ledger_error":max_ledger_error,
        "max_independent_position_error":max_reconstruction_error,"max_independent_cross_product_error":max_slope_error,
        "historical_daily_return_reproduction_error":historical_error,"historical_rows_checked":len(joined),
        "audit_source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/"independent_audit.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
