"""Whole-hierarchy structural diagnostics; no trading changes or fee model.

Exploratory follow-up on already viewed data. All cuts, fixed perturbations,
size-matched random labels, and future blocks are reported without P&L selection.
"""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.spatial.distance import squareform

from equity_h0_peers import geometry
from equity_residual_backtest import DATA, load_data

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"experiments/equity_h0_scale_robustness"
KS=np.arange(1,31)
PAIR_I,PAIR_J=np.triu_indices(30,1)
PAIR_COUNT=len(PAIR_I)
CONFIG={"status":"post-evaluation exploratory structural experiment; no trading selection",
        "base_window":120,"all_group_counts":list(range(1,31)),
        "methods":["Single_H0","Average"],
        "perturbations":{"shorter":100,"longer":140,"older_shift_sessions":5},
        "history_bootstrap_repetitions":40,"history_bootstrap_block_sessions":5,
        "random_label_repetitions":250,"random_seed":20261028,
        "future_block_sessions":20,"anchor_stride":20,"first_signal_index":140,
        "future_residuals":"use frozen base-window SPY coefficients",
        "period_boundary":"2024-01-01; exclude crossing future blocks",
        "mean_uncertainty_bootstrap_repetitions":1000,"anchor_bootstrap_block_length":6,
        "bands":"pointwise percentile and max-standardized simultaneous approximate 95% across cuts",
        "stable_local_branch":{"size_min":3,"size_max":8,"exact_bootstrap_recovery_min":.75,
                               "window_perturbation_recovery_min":2/3},
        "fees":"no performance or fee calculations in this structural experiment",
        "trading_changes":False,"parameter_selection_by_PnL":False}
COLORS={"Single_H0":"#43aa8b","Average":"#f8961e","Manual":"#6c757d"}
NAMES={"Single_H0":"Single linkage / H0","Average":"Average linkage","Manual":"Manual groups (K=6)"}


def hierarchy(d,method):
    tree=linkage(squareform(d),method=method)
    # This installed SciPy version mishandles the no-merge endpoint when it is
    # requested alongside all other cuts. Construct K=N explicitly.
    labels=np.vstack([cut_tree(tree,n_clusters=KS[:-1]).T,np.arange(len(d))])
    masks=labels[:,PAIR_I]==labels[:,PAIR_J]
    assert np.array_equal(np.array([len(set(row)) for row in labels]),KS)
    assert masks[0].all() and not masks[-1].any()
    counts=masks.sum(axis=1)
    assert np.all(np.diff(counts)<=0)
    sizes=[np.bincount(row) for row in labels]
    metrics={"largest_group":np.array([s.max() for s in sizes]),
             "singleton_stocks":np.array([(s==1).sum() for s in sizes]),
             "within_pairs":counts}
    sets=[1<<i for i in range(len(d))];branches=[]
    for left,right,height,size in tree:
        bitmask=sets[int(left)]|sets[int(right)];sets.append(bitmask)
        if int(size)<len(d):
            branches.append({"bitmask":bitmask,"size":int(size),"merge_distance":float(height)})
    return labels,masks,metrics,branches


def partition_agreement(a,b):
    # Coassignment-pair form of adjusted Rand; invariant to label numbering.
    count_a=a.sum(axis=-1);count_b=b.sum(axis=-1)
    intersection=np.logical_and(a,b).sum(axis=-1)
    expected=count_a*count_b/PAIR_COUNT
    denominator=.5*(count_a+count_b)-expected
    return np.divide(intersection-expected,denominator,
                     out=np.ones_like(denominator,dtype=float),where=abs(denominator)>1e-12)


def correlation_gap(masks,corr_pairs):
    counts=masks.sum(axis=-1)
    within=np.einsum("...p,p->...",masks,corr_pairs,optimize=False)
    outside=PAIR_COUNT-counts
    gap=np.full(np.shape(within),np.nan)
    valid=(counts>0)&(outside>0)
    np.divide(within,counts,out=gap,where=valid)
    other=np.zeros_like(gap)
    np.divide(corr_pairs.sum()-within,outside,out=other,where=valid)
    return np.where(valid,gap-other,np.nan)


def circular_indices(rng,length,block,repetitions):
    starts=rng.integers(0,length,size=(repetitions,int(np.ceil(length/block))))
    return ((starts[:,:,None]+np.arange(block))%length).reshape(repetitions,-1)[:,:length]


def curve_bands(values,indices):
    mean=np.mean(values,axis=0)
    boot=values[indices].mean(axis=1)
    low,high=np.quantile(boot,[.025,.975],axis=0)
    se=boot.std(axis=0,ddof=1)
    z=np.divide(boot-mean,se,out=np.zeros_like(boot),where=se>1e-12)
    radius=float(np.quantile(np.max(abs(z),axis=1),.95))
    return mean,low,high,mean-radius*se,mean+radius*se


def check_controls():
    from sklearn.metrics import adjusted_rand_score
    rng=np.random.default_rng(31)
    a=rng.integers(0,5,size=(12,30));b=rng.integers(0,5,size=(12,30))
    ari=partition_agreement(a[:,PAIR_I]==a[:,PAIR_J],b[:,PAIR_I]==b[:,PAIR_J])
    assert np.allclose(ari,[adjusted_rand_score(x,y) for x,y in zip(a,b)])
    same=np.array([[True]*PAIR_COUNT,[False]*PAIR_COUNT])
    assert np.array_equal(partition_agreement(same,same),[1,1])
    assert np.isnan(correlation_gap(same,np.ones(PAIR_COUNT))).all()
    d=np.abs(np.arange(30)[:,None]-np.arange(30)[None,:]).astype(float)
    labels,masks,metrics,branches=hierarchy(d,"single")
    assert len(branches)==28 and metrics["largest_group"][0]==30
    assert metrics["singleton_stocks"][-1]==30
    tree=linkage(squareform(d),method="single")
    for k in [2,6,29,30]:
        independent=cut_tree(tree,n_clusters=[k])[:,0]
        assert np.array_equal(masks[k-1],independent[PAIR_I]==independent[PAIR_J])
    return {"fast_ARI_matches_sklearn":True,"degenerate_cut_gaps_undefined":True,
            "all_cuts_have_requested_group_count":True,"complete_tree_has_28_nonroot_branches":True}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    spec=OUT/"specification.json"
    if spec.exists() and json.loads(spec.read_text())!=CONFIG:raise ValueError("Specification changed")
    spec.write_text(json.dumps(CONFIG,indent=2)+"\n")
    checks=check_controls();rng=np.random.default_rng(CONFIG["random_seed"])
    symbols,panel,_,_=load_data(False)
    x=panel[symbols].to_numpy();market=panel.SPY.to_numpy()
    universe=pd.read_csv(DATA/"universe.csv").set_index("symbol").loc[symbols]
    names=list(dict.fromkeys(universe.research_group));manual=np.array([names.index(g) for g in universe.research_group])
    manual_mask=manual[PAIR_I]==manual[PAIR_J]
    rows=[];branch_rows=[];manual_rows=[];anchors=[];null_curves=[]
    for t in range(140,len(panel)-20,20):
        start,end=panel.index[t+1],panel.index[t+20]
        if (start<pd.Timestamp("2024-01-01")) != (end<pd.Timestamp("2024-01-01")):continue
        period="development" if start<pd.Timestamp("2024-01-01") else "evaluation"
        anchor=len(anchors)
        anchors.append({"anchor":anchor,"period":period,"fit_start":panel.index[t-120],
                        "fit_end":panel.index[t-1],"signal_date":panel.index[t],
                        "future_start":start,"future_end":end})
        history=x[t-120:t];m=market[t-120:t]
        d,_,_,_,_,fit=geometry(history,m)
        future=x[t+1:t+21]-np.column_stack([np.ones(20),market[t+1:t+21]])@fit
        corr_pairs=np.corrcoef(future,rowvar=False)[PAIR_I,PAIR_J]
        permutations=np.array([rng.permutation(30) for _ in range(CONFIG["random_label_repetitions"])])
        altered={"100_sessions":geometry(x[t-100:t],market[t-100:t])[0],
                 "140_sessions":geometry(x[t-140:t],market[t-140:t])[0],
                 "5_sessions_older":geometry(x[t-125:t-5],market[t-125:t-5])[0]}
        bootstrap_indices=circular_indices(rng,120,5,CONFIG["history_bootstrap_repetitions"])
        bootstrap_distances=[geometry(history[idx],m[idx])[0] for idx in bootstrap_indices]
        for name,method in [("Single_H0","single"),("Average","average")]:
            labels,masks,metrics,branches=hierarchy(d,method)
            future_gap=correlation_gap(masks,corr_pairs)
            # A common relabeling across all cuts preserves hierarchy nesting
            # and every cut's group sizes in each reference replication.
            permuted=labels[:,permutations].transpose(1,0,2)
            null_masks=permuted[:,:,PAIR_I]==permuted[:,:,PAIR_J]
            random_gaps=correlation_gap(null_masks,corr_pairs)
            null_curves.append(random_gaps)
            assert np.array_equal(null_masks.sum(axis=2),np.broadcast_to(metrics["within_pairs"],random_gaps.shape))
            reference={b["bitmask"]:i for i,b in enumerate(branches)}
            branch_window=np.zeros(len(branches));branch_boot=np.zeros(len(branches))
            perturb_ari={}
            for perturb_name,dist in altered.items():
                _,other_masks,_,other_branches=hierarchy(dist,method)
                perturb_ari[perturb_name]=partition_agreement(masks,other_masks)
                available={b["bitmask"] for b in other_branches}
                branch_window += [b["bitmask"] in available for b in branches]
            boot_ari=[]
            for dist in bootstrap_distances:
                _,other_masks,_,other_branches=hierarchy(dist,method)
                boot_ari.append(partition_agreement(masks,other_masks))
                available={b["bitmask"] for b in other_branches}
                branch_boot += [b["bitmask"] in available for b in branches]
            boot_ari=np.mean(boot_ari,axis=0)
            for i,k in enumerate(KS):
                finite=1<k<30
                ref=random_gaps[:,i]
                rows.append({"anchor":anchor,"period":period,"method":name,"groups":int(k),
                             "largest_group":int(metrics["largest_group"][i]),
                             "singleton_stocks":int(metrics["singleton_stocks"][i]),
                             "within_pairs":int(metrics["within_pairs"][i]),
                             "ARI_100_sessions":float(perturb_ari["100_sessions"][i]),
                             "ARI_140_sessions":float(perturb_ari["140_sessions"][i]),
                             "ARI_5_sessions_older":float(perturb_ari["5_sessions_older"][i]),
                             "ARI_block_bootstrap":float(boot_ari[i]),
                             "future_gap":float(future_gap[i]) if finite else None,
                             "random_gap_mean":float(np.mean(ref)) if finite else None,
                             "random_gap_q025":float(np.quantile(ref,.025)) if finite else None,
                             "random_gap_q975":float(np.quantile(ref,.975)) if finite else None,
                             "excess_vs_size_matched_random":float(future_gap[i]-np.mean(ref)) if finite else None,
                             "null_above_fraction":float(np.mean(ref>=future_gap[i])) if finite else None})
            for i,b in enumerate(branches):
                membership=((b["bitmask"]>>np.arange(30))&1).astype(bool)
                within=membership[PAIR_I]&membership[PAIR_J]
                cross=membership[PAIR_I]!=membership[PAIR_J]
                recovery=float(branch_boot[i]/len(bootstrap_distances))
                windows=float(branch_window[i]/len(altered))
                local=3<=b["size"]<=8
                branch_rows.append({"anchor":anchor,"period":period,"method":name,
                                    "stocks":", ".join(np.array(symbols)[membership]),"size":b["size"],
                                    "merge_distance":b["merge_distance"],
                                    "exact_bootstrap_recovery":recovery,"window_recovery":windows,
                                    "local_size_3_to_8":local,
                                    "stable_local_candidate":bool(local and recovery>=.75 and windows>=2/3),
                                    "future_within_correlation":float(corr_pairs[within].mean()),
                                    "future_member_to_outside_correlation":float(corr_pairs[cross].mean()),
                                    "future_local_gap":float(corr_pairs[within].mean()-corr_pairs[cross].mean())})
        manual_permuted=manual[permutations]
        manual_random=correlation_gap(manual_permuted[:,PAIR_I]==manual_permuted[:,PAIR_J],corr_pairs)
        manual_rows.append({"anchor":anchor,"period":period,"groups":6,
                            "future_gap":float(correlation_gap(manual_mask,corr_pairs)),
                            "random_gap_mean":float(manual_random.mean())})
        if (anchor+1)%20==0:print(f"Completed {anchor+1} structural anchors",flush=True)
    anchors=pd.DataFrame(anchors);curves=pd.DataFrame(rows);branches=pd.DataFrame(branch_rows);manual=pd.DataFrame(manual_rows)
    anchors.to_csv(OUT/"anchors.csv",index=False);curves.to_csv(OUT/"all_cut_measurements.csv",index=False)
    branches.to_csv(OUT/"all_internal_branches.csv",index=False);manual.to_csv(OUT/"manual_reference.csv",index=False)
    null=np.stack(null_curves).reshape(len(anchors),2,CONFIG["random_label_repetitions"],30)
    np.savez_compressed(OUT/"size_matched_random_curves.npz",gaps=null)
    aggregated,paired,manual_summary=summarize(anchors,curves,null,manual)
    aggregated.to_csv(OUT/"cut_summary.csv",index=False);paired.to_csv(OUT/"paired_method_differences.csv",index=False)
    manual_summary.to_csv(OUT/"manual_summary.csv",index=False)
    catalogue=branches.groupby(["period","method","stocks","size"]).agg(
        observed_anchors=("anchor","size"),mean_bootstrap_recovery=("exact_bootstrap_recovery","mean"),
        mean_window_recovery=("window_recovery","mean"),stable_candidate_anchors=("stable_local_candidate","sum"),
        mean_future_local_gap=("future_local_gap","mean")).reset_index()
    catalogue.to_csv(OUT/"named_branch_catalogue.csv",index=False)
    counts=branches.groupby(["period","method","anchor"]).agg(
        local_branches=("local_size_3_to_8","sum"),stable_local_branches=("stable_local_candidate","sum")).reset_index()
    counts.to_csv(OUT/"stable_branch_counts.csv",index=False)
    plot_results(aggregated,paired,manual_summary,branches,counts)
    checks.update(random_labels_preserve_every_cluster_size=True,
                  future_blocks_nonoverlapping=True,past_only_branch_candidate_selection=True,
                  all_cut_endpoints_reported_but_not_scored_for_coherence=True)
    result={"configuration":CONFIG,"checks":checks,"anchor_counts":anchors.groupby("period").size().to_dict(),
            "stable_branch_counts":json.loads(counts.groupby(["period","method"])[["local_branches","stable_local_branches"]].mean().reset_index().to_json(orient="records")),
            "source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "input_returns_sha256":hashlib.sha256((DATA/"returns_log.csv").read_bytes()).hexdigest()}
    (OUT/"summary.json").write_text(json.dumps(result,indent=2)+"\n")
    print("ANCHORS",result["anchor_counts"])
    print("LOCAL BRANCH COUNTS\n",pd.DataFrame(result["stable_branch_counts"]).round(3).to_string(index=False))
    print("SIX-CUT COMPARISON\n",aggregated.loc[aggregated.groups.eq(6),["period","method","mean_largest_group","mean_singleton_stocks","mean_bootstrap_ARI","future_gap_mean","future_gap_sim95_low","future_gap_sim95_high"]].round(4).to_string(index=False))


def summarize(anchors,curves,null,manual):
    rng=np.random.default_rng(901)
    records=[];paired=[];manual_records=[]
    for period in ["development","evaluation"]:
        ids=anchors.loc[anchors.period.eq(period),"anchor"].to_numpy()
        bootstrap=circular_indices(rng,len(ids),CONFIG["anchor_bootstrap_block_length"],CONFIG["mean_uncertainty_bootstrap_repetitions"])
        period_values={}
        for method_index,method in enumerate(CONFIG["methods"]):
            frame=curves.loc[curves.period.eq(period)&curves.method.eq(method)]
            values=frame.pivot(index="anchor",columns="groups",values="future_gap").loc[ids,KS[1:-1]].to_numpy()
            period_values[method]=values
            mean,low,high,sim_low,sim_high=curve_bands(values,bootstrap)
            random_mean=null[ids,method_index,:,1:-1].mean(axis=0)
            null_mean=random_mean.mean(axis=0);null_sd=random_mean.std(axis=0,ddof=1)
            null_z=np.divide(random_mean-null_mean,null_sd,out=np.zeros_like(random_mean),where=null_sd>1e-12)
            null_radius=np.quantile(np.max(abs(null_z),axis=1),.95)
            for k in KS:
                sub=frame.loc[frame.groups.eq(k)]
                row={"period":period,"method":method,"groups":int(k),"anchors":len(ids),
                     "mean_largest_group":float(sub.largest_group.mean()),
                     "mean_singleton_stocks":float(sub.singleton_stocks.mean()),
                     "mean_bootstrap_ARI":float(sub.ARI_block_bootstrap.mean()),
                     "mean_100_ARI":float(sub.ARI_100_sessions.mean()),
                     "mean_140_ARI":float(sub.ARI_140_sessions.mean()),
                     "mean_shift_ARI":float(sub.ARI_5_sessions_older.mean())}
                if 1<k<30:
                    j=k-2
                    row.update(future_gap_mean=mean[j],future_gap_point95_low=low[j],future_gap_point95_high=high[j],
                               future_gap_sim95_low=sim_low[j],future_gap_sim95_high=sim_high[j],
                               random_gap_mean=null_mean[j],random_sim95_low=null_mean[j]-null_radius*null_sd[j],
                               random_sim95_high=null_mean[j]+null_radius*null_sd[j],
                               excess_vs_size_matched_random=mean[j]-null_mean[j])
                records.append(row)
        diff=period_values["Single_H0"]-period_values["Average"]
        mean,low,high,sim_low,sim_high=curve_bands(diff,bootstrap)
        for j,k in enumerate(KS[1:-1]):
            paired.append({"period":period,"groups":int(k),"H0_minus_average_gap":mean[j],
                           "point95_low":low[j],"point95_high":high[j],
                           "sim95_low":sim_low[j],"sim95_high":sim_high[j]})
        values=manual.loc[manual.period.eq(period)].set_index("anchor").loc[ids,"future_gap"].to_numpy()
        boots=values[bootstrap].mean(axis=1)
        manual_records.append({"period":period,"groups":6,"anchors":len(ids),"future_gap_mean":float(values.mean()),
                               "point95_low":float(np.quantile(boots,.025)),"point95_high":float(np.quantile(boots,.975))})
    return pd.DataFrame(records),pd.DataFrame(paired),pd.DataFrame(manual_records)


def plot_results(summary,paired,manual,branches,counts):
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    fig,axes=plt.subplots(2,2,figsize=(13,8),layout="constrained")
    for col,period in enumerate(["development","evaluation"]):
        for method in CONFIG["methods"]:
            f=summary.loc[summary.period.eq(period)&summary.method.eq(method)]
            axes[0,col].plot(f.groups,f.mean_largest_group,label=NAMES[method],color=COLORS[method])
            axes[1,col].plot(f.groups,f.mean_singleton_stocks,label=NAMES[method],color=COLORS[method])
        axes[0,col].set(title=period,ylabel="Mean largest group (of 30 stocks)")
        axes[1,col].set(xlabel="Number of groups K",ylabel="Mean stocks in singleton groups")
        for ax in axes[:,col]:ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle("Does chaining disappear at another cut? Entire hierarchy shown\nK=1 is one giant group; K=30 is all singletons, both by construction",fontsize=13)
    fig.savefig(OUT/"01_balance_all_cuts.png",dpi=170,bbox_inches="tight");plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(13,8),layout="constrained")
    for col,period in enumerate(["development","evaluation"]):
        for method in CONFIG["methods"]:
            f=summary.loc[summary.period.eq(period)&summary.method.eq(method)&summary.groups.between(2,29)]
            axes[0,col].plot(f.groups,f[["mean_100_ARI","mean_140_ARI","mean_shift_ARI"]].mean(axis=1),label=NAMES[method],color=COLORS[method])
            axes[1,col].plot(f.groups,f.mean_bootstrap_ARI,label=NAMES[method],color=COLORS[method])
        axes[0,col].set(title=period,ylabel="Mean ARI across three window perturbations")
        axes[1,col].set(xlabel="Number of groups K",ylabel="Mean ARI under 5-session block resampling")
        for ax in axes[:,col]:ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle("Repeatability at the same cut count · higher means more similar assignments\nOverlapping windows share much data; resampling is a robustness diagnostic, not an independent market history",fontsize=12)
    fig.savefig(OUT/"02_stability_all_cuts.png",dpi=170,bbox_inches="tight");plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(14,9),layout="constrained")
    for col,period in enumerate(["development","evaluation"]):
        for method in CONFIG["methods"]:
            f=summary.loc[summary.period.eq(period)&summary.method.eq(method)&summary.groups.between(2,29)]
            x=f.groups.to_numpy();color=COLORS[method]
            axes[0,col].plot(x,f.future_gap_mean,label=NAMES[method],color=color)
            axes[0,col].fill_between(x,f.future_gap_sim95_low,f.future_gap_sim95_high,color=color,alpha=.12)
            axes[0,col].fill_between(x,f.random_sim95_low,f.random_sim95_high,color=color,alpha=.20,hatch="//")
        m=manual.loc[manual.period.eq(period)].iloc[0]
        axes[0,col].errorbar([6],[m.future_gap_mean],yerr=[[m.future_gap_mean-m.point95_low],[m.point95_high-m.future_gap_mean]],fmt="o",color=COLORS["Manual"],capsize=4,label="Manual groups at K=6")
        axes[0,col].set(title=period,ylabel="Mean future within-minus-between correlation")
        d=paired.loc[paired.period.eq(period)]
        axes[1,col].plot(d.groups,d.H0_minus_average_gap,color="#526777")
        axes[1,col].fill_between(d.groups,d.sim95_low,d.sim95_high,color="#526777",alpha=.2)
        axes[1,col].set(xlabel="Number of groups K",ylabel="H0 minus average-linkage future gap")
        for ax in axes[:,col]:ax.axhline(0,color="gray",lw=.7);ax.grid(alpha=.2)
        axes[0,col].legend(fontsize=7)
    fig.suptitle("Future coherence across all nondegenerate cuts · no profit-selected threshold\nSolid shading: approximate simultaneous bootstrap bands across cuts; hatched near zero: size-matched random-label envelope",fontsize=12)
    fig.savefig(OUT/"03_future_coherence_and_random_controls.png",dpi=170,bbox_inches="tight");plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,5),layout="constrained")
    for ax,period in zip(axes,["development","evaluation"]):
        for method in CONFIG["methods"]:
            f=branches.loc[branches.period.eq(period)&branches.method.eq(method)]
            by_size=f.groupby("size").exact_bootstrap_recovery.mean()
            ax.plot(by_size.index,by_size.values,"o-",ms=3,color=COLORS[method],label=NAMES[method])
        ax.axvspan(3,8,color="gray",alpha=.08)
        ax.set(title=period,xlabel="Branch size (number of member stocks)",ylabel="Mean exact leaf-set recovery in resampled trees",ylim=(0,1.02))
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle("Named branches: do the exact same stocks recur anywhere in the perturbed tree?\nAll nonroot internal branches shown; shaded sizes 3–8 define the prespecified local-peer diagnostic",fontsize=12)
    fig.savefig(OUT/"04_branch_recovery_by_size.png",dpi=170,bbox_inches="tight");plt.close(fig)


if __name__=="__main__":main()
