"""Labeled H0 peer pilot: representation controls, structural checks, gross WLS.

Follow-up exploration on previously examined data. No fees or orders. H0 and
single linkage are verified as the same construction, not independent alpha.
"""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from ripser import ripser
from scipy.cluster.hierarchy import cut_tree, dendrogram, linkage
from scipy.spatial.distance import pdist, squareform
from scipy.sparse.csgraph import connected_components, minimum_spanning_tree
from sklearn.metrics import adjusted_rand_score

from equity_residual_backtest import DATA, construct, load_data, performance

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/equity_h0_peers"
CONFIG = {"status": "exploratory after original evaluation was examined",
          "lookback": 120, "clusters": 6, "residual_pcs": 5,
          "geometry": "sample correlation distance of prior SPY-regression residuals",
          "distance": "sqrt(2*(1-rho)); stock vertices, dates are coordinates",
          "signal": "one-day adjusted close-to-close log return",
          "holding": "next vendor daily-bar raw open to close; ideal dollar fills",
          "weights": "inverse prior total-return variance; daily sigma floor 0.0001",
          "gross_target": 1., "fees": "excluded entirely",
          "models": ["Manual6", "Average6", "Single6", "H0_6", "PCA5"],
          "future_structure": "20 non-overlapping future-return blocks; fixed prior SPY betas; omit boundary-crossing blocks",
          "snapshot_fit_ends": ["2019-12-31", "2020-03-31", "2023-12-29"],
          "no_parameter_search": True}
COLORS = {"Manual6":"#6c757d", "Average6":"#f8961e", "Single6":"#43aa8b", "H0_6":"#43aa8b", "PCA5":"#277da1"}
NAMES = {"Manual6":"Manual groups", "Average6":"Average linkage", "Single6":"Single linkage / H0", "H0_6":"H0 control", "PCA5":"5 residual PCs"}


def geometry(history, market):
    design = np.column_stack([np.ones(len(market)), market])
    fit = np.linalg.lstsq(design, history, rcond=None)[0]
    residual = history-design@fit
    sigma = residual.std(axis=0, ddof=1)
    if np.min(sigma) <= 1e-10:
        raise ValueError("Near-constant residual history")
    z = (residual-residual.mean(axis=0))/sigma
    c = z.T@z/(len(z)-1)
    d = np.sqrt(np.maximum(2*(1-c),0)); np.fill_diagonal(d,0)
    assert np.allclose(d, squareform(pdist(z.T/np.sqrt(len(z)-1))), atol=1e-10)
    values, vectors = np.linalg.eigh(c)
    order = np.argsort(values)[::-1]
    values, vectors = values[order], vectors[:,order]
    loadings = vectors*np.sqrt(np.maximum(values,0))
    assert np.allclose(d,squareform(pdist(loadings)),atol=1e-10)
    return d, z, sigma, values, vectors, fit


def clusters_and_h0(d):
    condensed = squareform(d, checks=True)
    single = linkage(condensed, method="single", optimal_ordering=True)
    average = linkage(condensed, method="average", optimal_ordering=True)
    n, k = len(d), CONFIG["clusters"]
    lower, upper = single[n-k-1,2], single[n-k,2]
    if not lower < upper:
        raise ValueError("Tied cut height: six clusters not unique at a filtration threshold")
    threshold = float((lower+upper)/2)
    count, h0_labels = connected_components(d<=threshold, directed=False)
    single_labels = cut_tree(single,n_clusters=[k])[:,0]
    average_labels = cut_tree(average,n_clusters=[k])[:,0]
    assert count==k and adjusted_rand_score(h0_labels,single_labels)==1
    mst_deaths = np.sort(minimum_spanning_tree(d).data)
    assert len(mst_deaths)==n-1 and np.allclose(mst_deaths,single[:,2],atol=1e-10)
    return {"Average6":average_labels, "Single6":single_labels, "H0_6":h0_labels}, single, threshold, mst_deaths


def group_exposures(labels, beta):
    indicator = np.eye(CONFIG["clusters"])[labels]
    return np.column_stack([indicator,beta]) # All group indicators already span dollars.


def check_controls():
    rng=np.random.default_rng(813)
    factors=rng.normal(size=(120,3))
    groups=np.repeat(np.arange(3),3)
    toy=factors[:,groups]+.03*rng.normal(size=(120,9))
    z=(toy-toy.mean(axis=0))/toy.std(axis=0,ddof=1)
    toy_dist=squareform(pdist(z.T/np.sqrt(119)))
    labels=cut_tree(linkage(squareform(toy_dist),method="single"),n_clusters=[3])[:,0]
    assert adjusted_rand_score(labels,groups)==1
    chain=np.arange(6)[:,None]*.9
    distances=squareform(pdist(chain))
    components,_=connected_components(distances<=1,directed=False)
    assert components==1 and distances[0,-1]>4
    _,_,_,eig,vec,_=geometry(rng.normal(size=(120,30)),rng.normal(size=120))
    assert np.allclose(pdist(vec),np.sqrt(2),atol=1e-12)
    return {"synthetic_three_groups_recovered":True,"chain_can_join_distant_endpoints":True,
            "unweighted_full_eigenvector_rows_are_equidistant":True,
            "stock_return_geometry_equals_correlation_distance":True,
            "full_eigenvalue_weighted_coordinates_preserve_distances":True}


def representation_checks(snapshot, symbols):
    d=snapshot["distance"]; eig=snapshot["eigenvalues"]; vec=snapshot["eigenvectors"]
    idx=np.triu_indices(len(d),1)
    loading=vec*np.sqrt(np.maximum(eig,0))
    variants={"Full weighted PCA":squareform(pdist(loading)),
              "Five weighted PCs":squareform(pdist(loading[:,:5])),
              "Full unweighted eigenvectors":squareform(pdist(vec))}
    h=snapshot["history"]
    raw_z=(h-h.mean(axis=0))/h.std(axis=0,ddof=1)
    variants["Original returns (SPY retained)"]=squareform(pdist(raw_z.T/np.sqrt(len(h)-1)))
    records=[]
    original_neighbors=np.argsort(d,axis=1)[:,1:4]
    original_labels=cut_tree(linkage(squareform(d),method="single"),n_clusters=[6])[:,0]
    for name,dist in variants.items():
        neighbors=np.argsort(dist,axis=1)[:,1:4]
        overlap=np.mean([len(set(a)&set(b))/3 for a,b in zip(original_neighbors,neighbors)])
        labels=cut_tree(linkage(squareform(dist),method="single"),n_clusters=[6])[:,0]
        records.append({"representation":name,"max_pair_distance_change":float(np.max(abs(dist-d))),
                        "relative_pair_distance_error":float(np.linalg.norm((dist-d)[idx])/np.linalg.norm(d[idx])),
                        "mean_top3_neighbor_overlap":float(overlap),
                        "six_group_ARI_vs_primary":float(adjusted_rand_score(original_labels,labels))})
    return pd.DataFrame(records),variants


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    config_path=OUT/"specification.json"
    if config_path.exists() and json.loads(config_path.read_text())!=CONFIG:
        raise ValueError("Existing pilot specification differs")
    config_path.write_text(json.dumps(CONFIG,indent=2)+"\n")
    checks=check_controls()
    symbols,panel,opens,closes=load_data(False)
    universe=pd.read_csv(DATA/"universe.csv").set_index("symbol").loc[symbols]
    group_names=list(dict.fromkeys(universe.research_group))
    manual=np.array([group_names.index(g) for g in universe.research_group])
    x=panel[symbols].to_numpy();market=panel.SPY.to_numpy();future_return=(closes/opens-1).to_numpy()
    upper=np.triu(np.ones((30,30),dtype=bool),1)
    previous={}; daily=[]; assignments=[]; barcode_rows=[]; forward=[]; snapshots={}
    max_identity_error=0.; max_exposure_error=0.
    for t in range(120,len(panel)-1):
        history=x[t-120:t]; m=market[t-120:t]
        d,z,res_sigma,eig,vec,fit=geometry(history,m)
        labels,single,threshold,deaths=clusters_and_h0(d)
        labels["Manual6"]=manual
        beta=fit[1];weights=1/np.maximum(history.std(axis=0,ddof=1),.0001)**2
        matrices={name:group_exposures(lab,beta) for name,lab in labels.items()}
        matrices["PCA5"]=np.column_stack([np.ones(30),beta,res_sigma[:,None]*vec[:,:5]])
        period="development" if panel.index[t+1]<pd.Timestamp("2024-01-01") else "evaluation"
        holdings={}
        for name in CONFIG["models"]:
            exposure=matrices[name]
            h,e,error,condition=construct(x[t],exposure,weights)
            rank=int(np.linalg.matrix_rank(exposure))
            assert rank==7
            max_exposure_error=max(max_exposure_error,error)
            holdings[name]=h
            row={"date":panel.index[t+1],"signal_date":panel.index[t],"training_end":panel.index[t-1],
                 "period":period,"model":name,"gross_return":float(h@future_return[t+1]),
                 "exposure_rank":rank,"max_exposure_error":error,"max_abs_position":float(abs(h).max()),
                 "active_stocks":int((abs(h)>1e-9).sum()),
                 "effective_gross_breadth":float(1/np.sum(h*h)) if np.sum(h*h)>0 else 0.,
                 "largest_group":np.nan,"singleton_groups":np.nan,"ARI_previous_day":np.nan,
                 "ARI_manual":np.nan,"changed_pair_fraction":np.nan}
            if name in labels:
                lab=labels[name];sizes=np.bincount(lab,minlength=6)
                same=np.equal.outer(lab,lab)
                row.update(largest_group=int(sizes.max()),singleton_groups=int((sizes==1).sum()),
                           ARI_manual=float(adjusted_rand_score(manual,lab)))
                if name in previous:
                    row["ARI_previous_day"]=float(adjusted_rand_score(previous[name],lab))
                    row["changed_pair_fraction"]=float(np.mean((same!=np.equal.outer(previous[name],previous[name]))[upper]))
                previous[name]=lab.copy()
                assignments.append({"date":panel.index[t+1],"model":name,**dict(zip(symbols,lab.tolist()))})
                singleton_stocks=np.isin(lab,np.flatnonzero(sizes==1))
                assert np.allclose(h[singleton_stocks],0,atol=1e-9)
            daily.append(row)
        max_identity_error=max(max_identity_error,float(np.max(abs(holdings["Single6"]-holdings["H0_6"]))))
        assert np.allclose(holdings["Single6"],holdings["H0_6"],atol=1e-10)
        barcode_rows.append({"fit_end":panel.index[t-1],"six_group_cut_threshold":threshold,
                             **{f"death_{j+1}":float(v) for j,v in enumerate(deaths)}})
        fit_end=str(panel.index[t-1].date())
        if fit_end in CONFIG["snapshot_fit_ends"]:
            diagram=ripser(d,distance_matrix=True,maxdim=0)["dgms"][0]
            finite=np.sort(diagram[np.isfinite(diagram[:,1]),1])
            assert len(finite)==29 and np.isinf(diagram[:,1]).sum()==1
            assert np.allclose(finite,deaths,atol=1e-6)
            snapshots[fit_end]={"distance":d,"labels":{k:v.copy() for k,v in labels.items()},
                               "single_tree":single,"threshold":threshold,"deaths":deaths,
                               "history":history,"eigenvalues":eig,"eigenvectors":vec}
            pd.DataFrame(diagram,columns=["birth","death"]).to_csv(OUT/f"H0_diagram_{fit_end}.csv",index=False)
        if (t-120)%20==0 and t+21<=len(panel):
            start,end=panel.index[t+1],panel.index[t+20]
            if (start<pd.Timestamp("2024-01-01")) != (end<pd.Timestamp("2024-01-01")):
                continue
            future=x[t+1:t+21]-np.column_stack([np.ones(20),market[t+1:t+21]])@fit
            future_corr=np.corrcoef(future,rowvar=False)
            for name,lab in labels.items():
                within=np.equal.outer(lab,lab)&upper;between=~np.equal.outer(lab,lab)&upper
                forward.append({"model":name,"period":period,"start_date":start,"end_date":end,
                                "within_pairs":int(within.sum()),"between_pairs":int(between.sum()),
                                "future_within_correlation":float(future_corr[within].mean()),
                                "future_between_correlation":float(future_corr[between].mean()),
                                "future_peer_gap":float(future_corr[within].mean()-future_corr[between].mean())})
    assert len(snapshots)==3
    daily=pd.DataFrame(daily);forward=pd.DataFrame(forward)
    daily.to_csv(OUT/"daily_gross_and_structure.csv",index=False)
    pd.DataFrame(assignments).to_csv(OUT/"daily_group_assignments.csv",index=False)
    pd.DataFrame(barcode_rows).to_csv(OUT/"daily_H0_deaths.csv",index=False)
    forward.to_csv(OUT/"future_coherence_blocks.csv",index=False)
    rows=[]
    for (period,name),frame in daily.groupby(["period","model"]):
        rows.append({"period":period,"model":name,**performance(frame.gross_return),
                     "mean_active_stocks":float(frame.active_stocks.mean()),
                     "mean_effective_breadth":float(frame.effective_gross_breadth.mean()),
                     "mean_largest_group":float(frame.largest_group.mean()) if name!="PCA5" else None,
                     "mean_singletons":float(frame.singleton_groups.mean()) if name!="PCA5" else None,
                     "mean_adjacent_ARI":float(frame.ARI_previous_day.mean()) if name!="PCA5" else None,
                     "max_abs_position":float(frame.max_abs_position.max())})
    metrics=pd.DataFrame(rows);metrics.to_csv(OUT/"gross_performance_and_structure.csv",index=False)
    coherence=forward.groupby(["period","model"]).agg(blocks=("future_peer_gap","size"),
               mean_future_within=("future_within_correlation","mean"),
               mean_future_between=("future_between_correlation","mean"),mean_future_peer_gap=("future_peer_gap","mean"),
               mean_within_pairs=("within_pairs","mean")).reset_index()
    coherence.to_csv(OUT/"future_coherence_summary.csv",index=False)
    reps,variants=representation_checks(snapshots["2023-12-29"],symbols)
    reps.to_csv(OUT/"representation_checks.csv",index=False)
    members=[]
    for date,snapshot in snapshots.items():
        for name,lab in snapshot["labels"].items():
            for group in sorted(set(lab)):
                members.append({"fit_end":date,"method":name,"cluster":int(group),
                                "stocks":", ".join(np.array(symbols)[lab==group]),"size":int((lab==group).sum())})
    pd.DataFrame(members).to_csv(OUT/"snapshot_cluster_members.csv",index=False)
    checks.update(H0_equals_single_linkage_partitions_and_holdings=True,
                  MST_deaths_equal_single_linkage_heights=True,Ripser_snapshot_deaths_match=True,
                  seven_independent_exposures_every_model=True,singleton_positions_zero=True)
    result={"configuration":CONFIG,"checks":checks,"max_H0_single_holdings_difference":max_identity_error,
            "max_scaled_exposure_error":max_exposure_error,"gross_results":json.loads(metrics.to_json(orient="records")),
            "future_structure":json.loads(coherence.to_json(orient="records")),
            "representation_checks":json.loads(reps.to_json(orient="records")),
            "source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "input_returns_sha256":hashlib.sha256((DATA/"returns_log.csv").read_bytes()).hexdigest()}
    (OUT/"summary.json").write_text(json.dumps(result,indent=2)+"\n")
    plot_results(daily,metrics,coherence,snapshots,variants,symbols,universe)
    print(metrics[["period","model","mean_daily_bps","sharpe_vs_zero","mean_active_stocks","mean_largest_group","mean_singletons","mean_adjacent_ARI"]].round(4).to_string(index=False))
    print("FORWARD STRUCTURE\n",coherence.round(4).to_string(index=False))
    print("REPRESENTATIONS\n",reps.round(5).to_string(index=False))


def plot_results(daily,metrics,coherence,snapshots,variants,symbols,universe):
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    group_names=list(dict.fromkeys(universe.research_group))
    palette=dict(zip(group_names,["#277da1","#f8961e","#43aa8b","#d1495b","#7b61a8","#6c757d"]))
    fig,axes=plt.subplots(3,2,figsize=(14,12),layout="constrained")
    for row,(date,snapshot) in enumerate(snapshots.items()):
        ax=axes[row,0]
        dendrogram(snapshot["single_tree"],labels=symbols,ax=ax,leaf_rotation=90,leaf_font_size=7,
                   color_threshold=0,above_threshold_color="#526777")
        ax.axhline(snapshot["threshold"],ls="--",color="#d1495b",lw=.8)
        ax.set(title=f"Single-linkage hierarchy · fit ends {date}",ylabel="Correlation distance")
        for label in ax.get_xticklabels():label.set_color(palette[universe.loc[label.get_text(),"research_group"]])
        ax=axes[row,1];ax.plot([0,2],[0,2],color="gray",lw=.7)
        ax.scatter(np.zeros(29),snapshot["deaths"],color="#43aa8b",s=25,alpha=.5)
        ax.axhline(snapshot["threshold"],ls="--",color="#d1495b",lw=.8)
        ax.set(title="H0 diagram · 29 finite deaths, one infinite component omitted",xlabel="Birth distance",ylabel="Death / merge distance",xlim=(-.1,2),ylim=(0,2))
    fig.suptitle("The same component-merging structure, with and without stock labels\nVertices all appear at distance zero; persistence is threshold range, not time or statistical significance",fontsize=13)
    fig.savefig(OUT/"01_labeled_hierarchy_and_H0.png",dpi=170,bbox_inches="tight");plt.close(fig)
    last=snapshots["2023-12-29"];idx=np.triu_indices(30,1)
    fig,axes=plt.subplots(1,2,figsize=(12,5),layout="constrained")
    axes[0].scatter(last["distance"][idx],variants["Full weighted PCA"][idx],s=12,alpha=.5,label="All weighted PCs")
    axes[0].scatter(last["distance"][idx],variants["Five weighted PCs"][idx],s=12,alpha=.4,label="First five weighted PCs")
    axes[0].plot([0,2],[0,2],color="gray",lw=.7)
    axes[0].set(xlabel="Original residual-correlation distance",ylabel="Distance in PCA coordinate space",title="A full weighted basis preserves geometry; truncation changes it")
    axes[0].legend(fontsize=8)
    for j,name in enumerate(["Manual6","Average6","Single6"]):
        lab=last["labels"][name]
        axes[1].scatter(np.arange(30),np.full(30,j),c=lab,cmap="tab10",vmin=0,vmax=9,s=90)
    axes[1].set_xticks(range(30),symbols,rotation=90,fontsize=7)
    axes[1].set_yticks(range(3),[NAMES[n] for n in ["Manual6","Average6","Single6"]])
    axes[1].set(title="Six groups in each method · cluster colors are local to each row",ylim=(-.5,2.5))
    fig.suptitle("Representation choices and peer membership · fit ends 2023-12-29",fontsize=13)
    fig.savefig(OUT/"02_coordinates_and_groups.png",dpi=170,bbox_inches="tight");plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(12,9),sharex=True,layout="constrained")
    for name in ["Manual6","Average6","Single6"]:
        frame=daily.loc[daily.model.eq(name)]
        for ax,field in zip(axes,["ARI_previous_day","largest_group","singleton_groups"]):
            ax.plot(frame.date,frame[field].rolling(63,min_periods=1).mean(),label=NAMES[name],color=COLORS[name],lw=1)
    axes[0].set(title="Adjacent-day assignment agreement (ARI)",ylabel="63-session mean ARI")
    axes[1].set(title="Does a six-group cut actually produce balanced peers?",ylabel="Largest group size")
    axes[2].set(title="Singleton groups constrain those stocks to zero holdings",ylabel="Singleton count",xlabel="Execution date; each group estimate ends before the signal")
    axes[0].legend(ncol=3,fontsize=8)
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle("Stability and chaining diagnostics · static manual groups are fixed by design",fontsize=13)
    fig.savefig(OUT/"03_structure_over_time.png",dpi=170,bbox_inches="tight");plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout="constrained")
    for ax,period in zip(axes,["development","evaluation"]):
        for name in ["Manual6","Average6","Single6","PCA5"]:
            frame=daily.loc[daily.period.eq(period)&daily.model.eq(name)]
            ax.plot(frame.date,(1+frame.gross_return).cumprod(),label=NAMES[name],color=COLORS[name],lw=1.2)
        ax.axhline(1,color="gray",lw=.7);ax.grid(alpha=.2)
        ax.set(title=period,ylabel="Gross equity per initial $1 · 1x gross");ax.legend(fontsize=8)
    fig.suptitle("Same signal, weighting, holding interval and seven exposure constraints\nH0 and single linkage have identical holdings; this is exploratory and entirely pre-fee",fontsize=12)
    fig.savefig(OUT/"04_gross_peer_comparison.png",dpi=170,bbox_inches="tight");plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout="constrained")
    for ax,period in zip(axes,["development","evaluation"]):
        frame=coherence.loc[coherence.period.eq(period)&coherence.model.isin(["Manual6","Average6","Single6"])].set_index("model").reindex(["Manual6","Average6","Single6"])
        ax.bar(range(3),frame.mean_future_peer_gap,color=[COLORS[n] for n in frame.index])
        ax.set_xticks(range(3),[NAMES[n] for n in frame.index],fontsize=9)
        ax.set(title=period,ylabel="Mean future within-minus-between correlation")
        ax.axhline(0,color="gray",lw=.7);ax.grid(axis="y",alpha=.2)
    fig.suptitle("Groups formed from past data, assessed in 20-session future blocks\nDescriptive structural generalization; group sizes/pair counts differ; no significance claim",fontsize=12)
    fig.savefig(OUT/"05_future_peer_coherence.png",dpi=170,bbox_inches="tight");plt.close(fig)


if __name__=="__main__":
    main()
