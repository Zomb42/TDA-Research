"""Canonical metric definitions and aligned-calendar plots from audited ledgers."""
from pathlib import Path
import base64
import hashlib
import json
import re
from datetime import timedelta
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nbformat
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
EQ = OUT.parents[1]
EXP = EQ/"experiments"


def perf(r):
    r=np.asarray(r);curve=np.cumprod(1+r);sd=r.std(ddof=1)
    return {"days":len(r),"mean_bps_day":float(r.mean()*1e4),"CAGR_pct":float((curve[-1]**(252/len(r))-1)*100),
        "volatility_pct":float(sd*np.sqrt(252)*100),"Sharpe_vs_zero":float(r.mean()/sd*np.sqrt(252)),
        "total_return_pct":float((curve[-1]-1)*100),"max_drawdown_pct":float((curve/np.maximum.accumulate(np.r_[1.,curve])[1:]-1).min()*100)}


def main():
    daily={};metadata={};cross_checks={}
    def add(key,label,frame,column,source,tda,role="strategy",universe="expanded200",lookback=120):
        series=frame.set_index("date")[column].sort_index()
        assert series.index.is_unique and np.isfinite(series).all()
        daily[key]=series;metadata[key]={"label":label,"source":source,"persistence_features":tda,"role":role,"universe":universe,"fit_sessions":lookback}
    e=pd.read_csv(EXP/"equity_efa_vs_pca/daily_gross_returns.csv",parse_dates=["date"])
    for model,key in [("PCA3","PCA120"),("EFA3","EFA120")]:
        add(key,model+" ungated",e.loc[e.model.eq(model)],"gross_return","equity_efa_vs_pca/daily_gross_returns.csv",False)
    expanded=pd.read_csv(EXP/"equity_expanded_pca_reversal/daily_gross_returns.csv",parse_dates=["date"])
    for (universe,window,model),frame in expanded.groupby(["universe","window","model"]):
        if universe=="expanded200" and window==120 and model=="SPY_PCA3":
            assert np.allclose(frame.set_index("date").gross_return.sort_index(),daily["PCA120"],atol=1e-12)
            continue
        key=f"{universe}_{model}_{window}"
        add(key,key,frame,"gross_return","equity_expanded_pca_reversal/daily_gross_returns.csv",False,universe=universe,lookback=int(window))
    legacy=pd.read_csv(EXP/"equity_residual_backtest/gross_report/daily_returns_and_diagnostics.csv",parse_dates=["date"])
    for model,frame in legacy.groupby("model"):
        add("legacy30_"+model,"Original30 "+model,frame,"gross_return","equity_residual_backtest/gross_report/daily_returns_and_diagnostics.csv",False,universe="original30")
    peers=pd.read_csv(EXP/"equity_h0_peers/daily_gross_and_structure.csv",parse_dates=["date"])
    for model,frame in peers.groupby("model"):
        add("peer30_"+model,"Peer30 "+model,frame,"gross_return","equity_h0_peers/daily_gross_and_structure.csv",model=="H0_6",universe="original30")
    groups={
        "scalar":("equity_persistence_regimes",{"Simple":"SimpleGate","SimplePlusStockPD":"StockPDGate","SimplePlusLagPD":"LagPDGate","HistoryMean":"HistoryMeanGate"}),
        "image":("equity_persistence_images",{"PersistenceImage20":"ImageGate","Ordinary20":"Ordinary20Gate"}),
        "basket":("equity_full_basket_states",{"Controls":"BasketControlsGate","RawLevel":"BasketRawLevelGate","RawChange":"BasketRawChangeGate","ResidualLevel":"BasketResidualLevelGate","ResidualChange":"BasketResidualChangeGate"})}
    gate_frames={}
    for group,(folder,columns) in groups.items():
        f=pd.read_csv(EXP/folder/"daily_gate_returns.csv",parse_dates=["date"]);gate_frames[group]=f
        assert np.allclose(f.AlwaysOn,daily["PCA120"].loc[f.date],atol=1e-12)
        for column,key in columns.items():
            is_tda=key in {"StockPDGate","LagPDGate","ImageGate","BasketRawLevelGate","BasketRawChangeGate","BasketResidualLevelGate","BasketResidualChangeGate"}
            add(key,key,f,column,folder+"/daily_gate_returns.csv",is_tda,"mean-forecast gate on PCA120")
    for column in ["Simple","SimplePlusStockPD"]:
        assert np.allclose(gate_frames["image"][column],gate_frames["scalar"][column],atol=1e-12)
    common=gate_frames["scalar"].date
    assert all(pd.DatetimeIndex(gate_frames[k].date).equals(pd.DatetimeIndex(common)) for k in groups)
    common_dates=pd.DatetimeIndex(common)
    records=[]
    for key,series in daily.items():
        scopes={"native_all":series,"native_before2024":series.loc[series.index<pd.Timestamp("2024-01-01")],
            "later2024":series.loc[series.index>=pd.Timestamp("2024-01-01")],"common_gate_all":series.loc[common_dates],
            "common_gate_before2024":series.loc[common_dates[common_dates<pd.Timestamp("2024-01-01")]]}
        for scope,selected in scopes.items():
            records.append({"strategy_id":key,"scope":scope,"start":str(selected.index.min().date()),"end":str(selected.index.max().date()),
                **metadata[key],**perf(selected),"active_fraction":1.})
    table=pd.DataFrame(records)
    # Add actual active fractions from the saved gate decisions, not nonzero P&L.
    for group,(folder,columns) in groups.items():
        f=gate_frames[group].set_index("date")
        for column,key in columns.items():
            for i,row in table.loc[table.strategy_id.eq(key)].iterrows():
                subset=f.loc[row.start:row.end]
                table.loc[i,"active_fraction"]=subset[column+"_active"].mean()
    table.to_csv(OUT/"canonical_return_metrics.csv",index=False)
    curves=pd.concat([pd.DataFrame({"date":common_dates,"strategy_id":key,"gross_return":series.loc[common_dates].to_numpy(),
        "equity_from100k":100000*np.cumprod(1+series.loc[common_dates].to_numpy())}) for key,series in daily.items()],ignore_index=True)
    curves.to_csv(OUT/"common_calendar_returns_and_equity.csv",index=False)
    # Reconcile return metrics against every current study's native-period table.
    max_metric_error=0.
    sources=[("equity_efa_vs_pca/gross_performance.csv",{"PCA3":"PCA120","EFA3":"EFA120"},None),
        ("equity_persistence_regimes/gate_performance.csv",{v:k for v,k in groups["scalar"][1].items()},"gate"),
        ("equity_persistence_images/gate_performance.csv",{"PersistenceImage20":"ImageGate","Ordinary20":"Ordinary20Gate"},"gate"),
        ("equity_full_basket_states/gate_performance.csv",{v:k for v,k in groups["basket"][1].items()},"gate")]
    indexed=table.set_index(["strategy_id","scope"])
    for path,mapping,kind in sources:
        f=pd.read_csv(EXP/path)
        for r in f.itertuples():
            if r.model not in mapping:continue
            scope="native_before2024" if r.period=="development" else "later2024";actual=indexed.loc[(mapping[r.model],scope)]
            for key,expected in [("CAGR_pct",r.gross_CAGR*100),("volatility_pct",r.annualized_volatility*100),("Sharpe_vs_zero",r.sharpe_vs_zero),("max_drawdown_pct",r.max_drawdown*100)]:
                error=abs(actual[key]-expected);max_metric_error=max(max_metric_error,error);assert error<1e-9,(path,r.model,key,error)
    # Risk forecasting is a separate table; it never supplies a P&L series.
    p=pd.read_csv(EXP/"equity_full_basket_states/walk_forward_predictions.csv")
    metric=pd.read_csv(EXP/"equity_full_basket_states/forecast_metrics.csv")
    paired=pd.read_csv(EXP/"equity_full_basket_states/paired_incremental_comparisons.csv")
    risk=[]
    for period in ["development","later"]:
        f=p.loc[p.score_period.eq(period)&p.target_logRMS.notna()]
        baseline=np.mean((f.risk_Controls-f.target_logRMS)**2)
        for model in ["Controls","RawLevel","RawChange","ResidualLevel","ResidualChange"]:
            loss=float(np.mean((f["risk_"+model]-f.target_logRMS)**2))
            saved=metric.loc[metric.period.eq(period)&metric.target.eq("risk")&metric.model.eq(model)].iloc[0]
            assert np.isclose(loss,saved.MSE,atol=1e-12)
            pair=paired.loc[paired.period.eq(period)&paired.metric.eq("logRMS_MSE")&paired.model.eq(model)]
            risk.append({"period":period,"model":model,"forecasts":len(f),"log_RMS_MSE":loss,
                "forecast_error_reduction_pct":float((1-loss/baseline)*100),"realized_portfolio_risk_reduction_claimed":False,
                "model_minus_control_loss":loss-baseline,"sim95_low":float(pair.sim95_low.iloc[0]) if len(pair) else np.nan,
                "sim95_high":float(pair.sim95_high.iloc[0]) if len(pair) else np.nan,"target_strategy":"PCA120 ungated","used_for_position_sizing":False})
    risk=pd.DataFrame(risk);risk.to_csv(OUT/"canonical_risk_forecast_metrics.csv",index=False)
    # Notebook outputs: check execution/errors and whether sidecar PNGs match embedded bytes.
    notebook_rows=[]
    all_pngs={hashlib.sha256(q.read_bytes()).hexdigest() for q in EXP.rglob("*.png") if OUT not in q.parents}
    for path in sorted(EQ.glob("*.ipynb")):
        n=nbformat.read(path,as_version=4);nbformat.validate(n)
        cells=[c for c in n.cells if c.cell_type=="code"]
        errors=[o for c in cells for o in c.get("outputs",[]) if o.output_type=="error"]
        assert not errors and all(c.execution_count is not None for c in cells),path.name
        images=[o["data"]["image/png"] for c in cells for o in c.get("outputs",[]) if "image/png" in o.get("data",{})]
        folder=EXP/path.stem
        png_hashes={hashlib.sha256(q.read_bytes()).hexdigest() for q in folder.glob("*.png")} if folder.is_dir() else set()
        matched=sum(hashlib.sha256(base64.b64decode(im)).hexdigest() in png_hashes for im in images)
        project_matched=sum(hashlib.sha256(base64.b64decode(im)).hexdigest() in all_pngs for im in images)
        notebook_rows.append({"notebook":path.name,"code_cells":len(cells),"embedded_figures":len(images),"matching_direct_sidecar_pngs":matched,
            "matching_any_project_sidecar_pngs":project_matched,"no_execution_errors":True,"all_code_executed":True,"sidecar_note":"Inline-computed images need not match direct file sidecars"})
    pd.DataFrame(notebook_rows).to_csv(OUT/"notebook_output_inventory.csv",index=False)
    # Same calendar, same initial capital, no resets: each panel has its matched controls.
    panels=[("Ungated factor strategies",["PCA120","EFA120"]),
        ("Scalar diagram gates on PCA",["PCA120","SimpleGate","StockPDGate","LagPDGate"]),
        ("Image comparison on PCA",["PCA120","SimpleGate","StockPDGate","Ordinary20Gate","ImageGate"]),
        ("Full-basket mean gates on PCA",["PCA120","BasketControlsGate","BasketRawLevelGate","BasketRawChangeGate","BasketResidualLevelGate","BasketResidualChangeGate"])]
    colors={"PCA120":"#777777","EFA120":"#e58a20","SimpleGate":"#277da1","StockPDGate":"#e58a20","LagPDGate":"#228b64","Ordinary20Gate":"#7b2cbf","ImageGate":"#d65f5f",
        "BasketControlsGate":"#222222","BasketRawLevelGate":"#277da1","BasketRawChangeGate":"#e58a20","BasketResidualLevelGate":"#7b2cbf","BasketResidualChangeGate":"#228b64"}
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    fig,axes=plt.subplots(2,2,figsize=(15,9),sharex=True,sharey=True,layout="constrained")
    first=pd.Timestamp(str(common_dates[0])).to_pydatetime()-timedelta(days=1)
    for ax,(title,keys) in zip(axes.ravel(),panels):
        for key in keys:
            r=daily[key].loc[common_dates].to_numpy();curve=(np.cumprod(1+r)-1)*100
            ax.plot(pd.DatetimeIndex([first,*common_dates]),np.r_[0.,curve],label=metadata[key]["label"],color=colors[key],lw=1.4)
        ax.axhline(0,color="black",lw=.5);ax.axvline(pd.Timestamp("2024-01-01"),color="black",ls="--",lw=.7)
        ax.set(title=title,ylabel="Cumulative gross return (%)");ax.legend(fontsize=8,ncol=2);ax.grid(axis="y",alpha=.2)
    fig.suptitle(f"Aligned comparisons: {common_dates.min().date()} to {common_dates.max().date()} | {len(common_dates)} common sessions\nSame dates, same $100,000 starting equity, all flat days retained, no reset; pre-fee",fontsize=13)
    fig.savefig(OUT/"01_common_calendar_profit.png",dpi=170);fig.savefig(OUT/"01_common_calendar_profit.svg");plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout="constrained")
    later=risk.loc[risk.period.eq("later")];labels=later.model.tolist();values=later.log_RMS_MSE.to_numpy()
    axes[0].bar(range(len(labels)),values,color=["#555555","#277da1","#e58a20","#7b2cbf","#228b64"])
    axes[0].set(xticks=range(len(labels)),xticklabels=labels,ylabel="Mean squared log-RMS forecast error",title="Later 138 forecasts | lower error is better")
    axes[0].tick_params(axis="x",rotation=25)
    row=later.loc[later.model.eq("RawChange")].iloc[0]
    axes[1].plot([row.sim95_low,row.sim95_high],[0,0],lw=4,color="#e58a20");axes[1].scatter(row.model_minus_control_loss,0,color="black",zorder=3)
    axes[1].axvline(0,color="black",ls="--");axes[1].set(yticks=[],xlabel="RawChange minus Controls: squared log-error",title="Paired simultaneous 95% interval includes zero")
    fig.suptitle("Risk forecast accuracy is not trading profit or realized risk reduction",fontsize=13)
    fig.savefig(OUT/"02_risk_forecast_accuracy.png",dpi=170);plt.close(fig)
    result={"checks":{"underlying_PCA_identical_across_all_gate_ledgers":True,"Simple_and_stockPD_identical_between_scalar_and_image_studies":True,
        "all_native_period_return_metrics_reproduce":True,"risk_losses_recomputed_from_predictions_and_targets":True,"all_notebooks_executed_without_saved_errors":True},
        "return_metric_rows":len(table),"strategies":len(daily),"common_calendar_start":str(common_dates.min().date()),"common_calendar_end":str(common_dates.max().date()),"common_calendar_days":len(common_dates),
        "max_return_metric_error":max_metric_error,"risk_reduction_RawChange_later_pct":float(row.forecast_error_reduction_pct),"notebooks":len(notebook_rows)}
    (OUT/"ledger_validation.json").write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result,indent=2))
    audit_runs=json.loads((OUT/"audit_reruns.json").read_text())
    legacy=json.loads((OUT/"legacy_checks.json").read_text())
    assert audit_runs["all_passed"] and not audit_runs["changed_original_files"] and all(legacy["checks"].values())
    assert all(r["matching_any_project_sidecar_pngs"]==r["embedded_figures"] for r in notebook_rows)
    def money_table(keys,scope):
        lines=["| Strategy | Start | Days | Gross CAGR | Realized annualized volatility | Sharpe vs zero | Active days |",
            "|---|---|---:|---:|---:|---:|---:|"]
        for key in keys:
            row=indexed.loc[(key,scope)]
            lines.append(f"| {metadata[key]['label']} | {row.start} | {int(row.days)} | {row.CAGR_pct:.2f}% | {row.volatility_pct:.2f}% | {row.Sharpe_vs_zero:.2f} | {row.active_fraction*100:.1f}% |")
        return "\n".join(lines)
    later_table=money_table(["PCA120","EFA120","SimpleGate","StockPDGate","ImageGate","BasketControlsGate","BasketRawChangeGate"],"later2024")
    common_table=money_table(["PCA120","EFA120","SimpleGate","StockPDGate","ImageGate","BasketControlsGate","BasketRawChangeGate"],"common_gate_all")
    native_table=money_table(["PCA120","EFA120"],"native_all")
    report=f'''# Equity results: validated definitions and comparison ledger

Validated October 29, 2026. **Use this page for current performance/risk numbers.** The [research log](EQUITY_RESEARCH_LOG.md) preserves the sequence of experiments; this page reconciles their different scopes. No strategy was retuned and no return ledger was changed.

## The direct answer about TDA and risk

There are two separate favorable later point observations:

1. **Realized portfolio volatility:** the stock-loading-diagram mean gate has 3.21% annualized volatility versus 3.80% for always running PCA. Its point CAGR is 3.39% versus 3.37%, and Sharpe 1.06 versus 0.89. It trades only 69.4% of calendar days. The ordinary SimpleGate has 3.18% volatility while active 67.2% of days. Lower exposure through flat days can reduce measured volatility without establishing a uniquely useful topological signal.
2. **Accuracy of a risk forecast:** full-basket RawChange lowers later squared log-RMS forecast error by **{row.forecast_error_reduction_pct:.2f}%** relative to its 33-control model. That forecast was **not used to size, hedge, or switch off the portfolio**. This is neither a {row.forecast_error_reduction_pct:.2f}% return nor a demonstrated reduction in realized portfolio risk.

Both point observations are valid. The declared paired uncertainty intervals include zero; a reliable incremental TDA benefit over matched conventional controls remains unestablished. Saying simply “TDA improves risk” omits these essential distinctions.

## 1. Same later period: January 2, 2024–October 27, 2026

Every row below uses **the same 708 trading sessions**. All returns are gross/pre-fee, with no cash-interest return, 1× gross exposure on active days, and flat days included as zero. CAGR means annualized compounded return, not total profit.

{later_table}

PCA120 and EFA120 are **ungated and use no persistence features**. Every gate shown acts on the fixed PCA120 underlying strategy, not EFA. StockPDGate uses the three stock-loading diagram summaries; ImageGate uses the H0 bins and H1 image; BasketRawChangeGate uses full-basket day-diagram changes. SimpleGate and BasketControlsGate are different ordinary-control feature sets. The basket control includes conventional MST/H0-equivalent summaries. Compare additions to their own control, not unrelated rows as though one feature alone changed.

The stock-PD gate's paired later mean increment over SimpleGate remains +0.411 bps/day, simultaneous interval [−0.213,+1.035]. The basket RawChange mean gate instead trails its own control in point returns. The risk predictor and the mean-return gate are fitted to different targets.

## 2. What “overall” means

Full native baseline history, **February 3, 2017–October 27, 2026**:

{native_table}

The 3.54% EFA CAGR applies only to the later subperiod. Its full native-history CAGR is 0.66%, with 17.14% maximum drawdown; $100,000 becomes approximately $106,550. This does not contradict a 3.54% recent-period CAGR.

The gates need completed training labels and first trade on **April 22, 2019**. Their native “full” period therefore starts later. They have no generated decisions before that date. We do not fabricate early gate returns or prepend zeros and call that an equivalent strategy.

For comparison, every row below is restarted at the same capital on **April 22, 2019**, then compounded continuously through October 27, 2026: **1,891 common sessions**, with no reset at 2024.

{common_table}

![Same calendar and starting capital](experiments/equity_validation_review_2026_10_29/01_common_calendar_profit.png)

Those common-period gate point returns can exceed the ungated point return. That is a descriptive result, not established TDA-specific alpha: ordinary gates also change performance, and all originally declared paired TDA-versus-control intervals remain unresolved. The common-calendar table is a reporting alignment, not a newly selected test or a fresh holdout.

## 3. The exact risk-forecast result

**Underlying target strategy:** ungated PCA120. **Forecast target:** log of the next twenty daily gross strategy returns' RMS, measured in bps. RMS is the square root of average squared returns; both large gains and large losses raise it. It is different from expected return, downside-only risk, and portfolio volatility after applying a policy.

On the later **138 completed, non-boundary forecast targets**:

| Risk predictor | Squared log-RMS forecast error | Meaning |
|---|---:|---|
| Ordinary 33 controls | 0.06924038 | Baseline prediction error |
| Same controls + RawChange | 0.06686171 | 3.435% lower point prediction error |

The percentage is `(0.06924038 − 0.06686171) / 0.06924038 × 100`. The paired loss difference is **−0.00237868**, approximate simultaneous 95% interval **[−0.00600227,+0.00124491]**, including zero. Earlier point reduction is only 0.43%. All four declared additions' primary simultaneous intervals span zero in both periods.

As a secondary metric, RMS absolute forecast error is 4.844 versus 4.792 bps. Different loss functions give different percentage changes; these are not interchangeable definitions of “risk improvement.” No allocation rule based on these risk predictions was evaluated.

![Risk prediction error, separate from profit](experiments/equity_validation_review_2026_10_29/02_risk_forecast_accuracy.png)

## 4. Why earlier numbers or plots differ

| Difference | What must be held fixed before comparing |
|---|---|
| 0.66% versus 3.54% EFA CAGR | Full 2017-onward history versus the 2024-onward subperiod |
| Ungated versus TDA-gated profit | Different trading policies; the latest EFA curve has no TDA gate |
| 2017 baseline versus 2019 gate start | Admission/history warmup differs from completed-label forecasting warmup |
| Original thirty versus expanded two hundred stocks | Different universes; the original negative result remains valid for its basket |
| 120 versus 252 factor-fit sessions | Separate fixed lookbacks; no winning setting has been validated |
| Daily 708 later executions versus 689 event formations | The 1/5/20-session event study uses common complete20 dates and omits nineteen tail dates |
| Raw daily P&L versus adjusted event returns | Different saved price conventions; both are pre-fee |
| A curve beginning at zero in each panel versus a continuous curve | The former resets capital for each displayed subperiod; the latter does not |
| Dollar profit versus percentage total return versus CAGR | Different units; $100k capital and the 252-session annualization must be stated |
| Active-day mean versus calendar mean | Our gate performance includes all inactive zero-return days |
| Different confidence endpoints on identical point returns | Earlier HAC5 intervals versus block-bootstrap intervals, and different seeds/comparison families; no underlying return change is implied |
| Ordinary pointwise versus simultaneous intervals | Several isolated secondary pointwise results exclude zero but do not survive their declared comparison family |

Dollar neutrality also does not mean zero gross stock exposure. A $100,000 account at 1× gross initially has roughly $50,000 long and $50,000 short. Estimated SPY beta and three factor exposures balance at formation, but other risks and later exposure changes remain.

## 5. What was revalidated

- **Eight audit reruns passed:** full expanded data pagination/returns/coverage, expanded PCA and its price ledger, scalar diagram forecasts/gates, images, full-basket states and both targets, EFA/PCA, expanded peer structure, and the earlier direct response study. They ran in isolated report directories. At audit completion, all {audit_runs['original_files_checked']} snapshotted original files were unchanged.
- **Additional independent legacy reconstruction passed:** all 2,598 original thirty-stock daily portfolios, all five PC-sensitivity return series, every H0 peer-pilot return, selected daily peer labels, all thirty cuts at all 127 original hierarchy anchors, original descriptive PCA, and gross performance/HAC intervals.
- The same underlying PCA return series matches every gate's AlwaysOn ledger. Scalar and image studies' shared Simple/StockPD gates match exactly. All native-period CAGR, volatility, Sharpe and drawdown figures reproduce to numerical tolerance.
- All **11 existing notebooks** have executed code and no saved execution errors. All **50 embedded figures** match current saved project PNGs byte for byte. This rules out stale embedded versus sidecar image mismatches; it does not make their differently scoped graphs comparable automatically.
- Forecast risk losses were recalculated directly from saved predictions and actual target labels. The underlying daily returns were separately reconciled against prices and holdings by the audit chain.

**No numerical discrepancy was found in these audited returns, losses or metrics. The reporting problem was switching among valid but differently scoped quantities without keeping the distinctions prominent.** This page and its machine-readable ledger now make those scopes explicit. Historical source tables/graphs are preserved; documentation was clarified rather than changing strategy outcomes.

This validates implementation and internal consistency, not an economic edge. It does not independently certify every vendor price/corporate-action adjustment, realistic fills, point-in-time universe membership, or future generalization. Current-survivor selection, examined evaluation dates, short time history, overlapping labels, conditional bootstrap inference and multiple historical experiments remain limitations. No trading costs were introduced in this review.

## Evidence and reproduction

- [All return metrics with strategy, universe, lookback, scope, dates and counts](experiments/equity_validation_review_2026_10_29/canonical_return_metrics.csv)
- [Separate risk-forecast metrics](experiments/equity_validation_review_2026_10_29/canonical_risk_forecast_metrics.csv)
- [Common-calendar daily returns and equity](experiments/equity_validation_review_2026_10_29/common_calendar_returns_and_equity.csv)
- [Audit rerun results/log paths](experiments/equity_validation_review_2026_10_29/audit_reruns.json), [legacy checks](experiments/equity_validation_review_2026_10_29/legacy_checks.json), [ledger checks](experiments/equity_validation_review_2026_10_29/ledger_validation.json), [notebook/image inventory](experiments/equity_validation_review_2026_10_29/notebook_output_inventory.csv)
- [Audit runner](experiments/revalidate_equity_research.py), [legacy reconstruction](experiments/equity_validation_review_2026_10_29/check_legacy_results.py), [ledger/report generator](experiments/equity_validation_review_2026_10_29/build_comparison_ledger.py)

No new TDA/EFA combination, risk-sizing policy, strategy tuning or external data collection was run. This is a validation and reporting reconciliation of existing equity work.
'''
    (EQ/"EQUITY_VALIDATION.md").write_text(report)
    print(table.loc[table.strategy_id.isin(["PCA120","EFA120","SimpleGate","StockPDGate","ImageGate","BasketControlsGate","BasketRawChangeGate"])&table.scope.isin(["native_all","common_gate_all","later2024"]),["strategy_id","scope","start","end","days","CAGR_pct","volatility_pct","Sharpe_vs_zero","active_fraction"]].round(5).to_string(index=False))


if __name__=="__main__":main()
