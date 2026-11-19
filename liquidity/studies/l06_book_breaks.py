"""Mirrored depth profiles, actual one-second band breaks, and a frozen-coordinate check."""
from collections import defaultdict
from functools import lru_cache
import json

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from l01_snapshots import CACHE, RESULTS
from l02_describe import GRID_CACHE, SIDES, plt
from l03_band_age import DAY, WEIGHTS, intervals, links, reachable_next
from l04_trade_tape import OUT
from l05_refill import CUTS, utc

Q = .90


def histograms(row, signed, weights, mid2, nrows, nbins):
    side = (signed>0).astype(int)
    dist2 = (2*np.abs(signed)-mid2[row])*np.where(side==1,1,-1)
    b = dist2*10000//np.maximum(1,mid2[row])
    keep = (b>=0)&(b<nbins)&(mid2[row]>0)
    ix = (row[keep]*2+side[keep])*nbins+b[keep]
    return np.bincount(ix,weights[keep],minlength=nrows*2*nbins).reshape(nrows,2,nbins)


def native_checks(grid,valid,mid2,pairs):
    n = len(grid)
    moved_only, book_only = np.zeros((n,2),np.uint32),np.zeros((n,2),np.uint32)
    cut = CUTS.loc[Q].to_numpy()[:,None]
    extended, extended_times = [], []
    indexed_profiles = defaultdict(list)
    flow_rows = []
    requests = defaultdict(list)
    for arm in ("event","calm"):
        for t,s,pre in zip(pairs[arm],pairs.side,pairs[arm+"_pre_usd"]):
            for lag in (-1,0,1,5,10,30,60):
                requests[t+lag].append((arm,t,s,lag,pre))
    fixed = []
    origin = 0
    manifest = json.loads((RESULTS/"snapshot_manifest.json").read_text())
    for h in manifest["hours"]:
        length = h["seconds"]
        if not length:
            continue
        table = pq.read_table(CACHE/(h["hour"]+".parquet"),columns=["signed_price_tick","size_100","added_100","removed_100","executed_100"]).combine_chunks()
        field = table["signed_price_tick"].chunk(0)
        offsets = field.offsets.to_numpy()
        p = field.values.to_numpy()
        qty = table["size_100"].chunk(0).values.to_numpy()
        value = np.abs(p)*qty/1e6
        flow = [table[k].chunk(0).values.to_numpy() for k in ("added_100","removed_100","executed_100")]
        i = np.arange(origin,origin+length)
        if i[-1]+1 >= DAY:
            row = np.repeat(np.arange(length),np.diff(offsets))
            # Execute both counterfactuals for the same transition, including at hourly seams.
            for target, center, shift in [(book_only,mid2[np.maximum(0,i-1)],0),
                                          (moved_only,mid2[np.minimum(n-1,i+1)],1)]:
                counts = histograms(row,p,value,center,length,25)
                mask = (counts>=cut).astype(np.uint32) @ WEIGHTS
                ok = i+shift < n
                target[i[ok]+shift] = mask[ok]
            for j,t in enumerate(i):
                on_clock = (t+1)%60 == 0 and t+1 >= DAY and valid[t]
                selected = [(arm,lag) for arm,e,s,lag,pre in requests.get(t,()) if lag in (-1,0,5,60)]
                if on_clock or selected:
                    sl = slice(offsets[j],offsets[j+1])
                    counts = histograms(np.zeros(offsets[j+1]-offsets[j],dtype=int),p[sl],value[sl],mid2[t:t+1],1,100)[0]
                    assert np.allclose(counts[:,:25],grid[t])
                    if on_clock:
                        extended.append(counts)
                        extended_times.append(t)
                    for arm,lag in selected:
                        indexed_profiles[(arm,lag)].append(counts)
                if t not in requests:
                    continue
                sl = slice(offsets[j],offsets[j+1])
                for arm,e,s,lag,pre in requests[t]:
                    m0 = mid2[e-1]
                    d = (2*np.abs(p[sl])-m0)*(1 if s else -1)
                    active = ((p[sl]>0)==s)&(d>=0)&(10000*d<5*m0)
                    fixed_ratio = value[sl][active].sum()/pre
                    moving_ratio = grid[t,s,:5].sum()/pre
                    if lag == 0:
                        amounts = [np.sum(np.abs(p[sl][active])*v[sl][active])/1e6 for v in flow]
                        loss = pre-value[sl][active].sum()
                        if not np.isclose(amounts[1]-amounts[0],loss,atol=1e-5):
                            raise ValueError("Gross flow failed the fixed-price depth identity")
                        flow_rows.append((arm,pre,loss,*amounts))
                    if lag == -1:
                        assert np.isclose(fixed_ratio,1) and np.isclose(moving_ratio,1)
                    fixed.append((arm,e,lag,fixed_ratio,moving_ratio))
        origin += length
    assert origin == n
    frame = pd.DataFrame(fixed,columns=["arm","index","lag","fixed","moving"])
    assert len(frame) == 2*len(pairs)*7
    frame.groupby(["arm","lag"],as_index=False).agg(pairs=("index","size"),median_fixed=("fixed","median"),
        median_moving=("moving","median"),depleted_fixed=("fixed",lambda x:(x<=.8).mean()),
        depleted_moving=("moving",lambda x:(x<=.8).mean())).to_csv(OUT/"fixed_price_refill.csv",index=False)
    flows = pd.DataFrame(flow_rows,columns=["arm","before","loss","added","removed","printed"])
    flow_stats = []
    for arm,group in flows.groupby("arm"):
        depleted = group[group.loss>=.2*group.before]
        flow_stats.append(dict(arm=arm,all_seconds=len(group),fixed_price_depleted=len(depleted),
              net_loss_exceeds_prints=int((depleted.loss>depleted.printed+.01).sum()),
              median_loss_usd=depleted.loss.median(),median_printed_usd=depleted.printed.median(),
              median_prints_over_loss=(depleted.printed/depleted.loss).median()))
    pd.DataFrame(flow_stats).to_csv(OUT/"fixed_price_flows.csv",index=False)
    extended = np.asarray(extended)
    samples = [("evaluation_minute",extended)]
    samples.extend((f"{arm} {lag:+d}s",np.asarray(profiles)) for (arm,lag),profiles in sorted(indexed_profiles.items()))
    days = (np.asarray(extended_times)+1)//DAY
    samples.extend((f"Nov {day+11}",extended[days==day]) for day in range(1,7))
    tall = []
    for sample,profiles in samples:
        med = np.median(profiles,axis=0)
        peaks = local_peak(profiles,20)&local_peak(profiles,24)
        near = 19 + np.argmax(profiles[:,:,19:22],axis=2)
        far = 23 + np.argmax(profiles[:,:,23:26],axis=2)
        ri,si = np.indices(near.shape)
        left,right = profiles[ri,si,near],profiles[ri,si,far]
        smaller = np.minimum(left,right)
        loc = np.arange(19,26)
        between = (loc>near[:,:,None]) & (loc<far[:,:,None])
        gap = np.where(between,profiles[:,:,19:26],np.inf).min(axis=2)
        two_zones = ((smaller>=CUTS.loc[.75].to_numpy()) & (gap<=smaller/2)
                     & (left>profiles[ri,si,near-1]) & (left>profiles[ri,si,near+1])
                     & (right>profiles[ri,si,far-1]) & (right>profiles[ri,si,far+1]))
        for s,side in enumerate(SIDES):
            bottom = 20+np.argmin(med[s,20:25])
            tall.append(dict(sample=sample,side=side,snapshots=len(profiles),ridge_20_usd=med[s,20],ridge_24_usd=med[s,24],
                             both_median_peaks=bool(local_peak(med[s],20)&local_peak(med[s],24)),saddle_bin=bottom,
                             saddle_usd=med[s,bottom],both_peaks_fraction=peaks[:,s].mean(),all_four_fraction=peaks.all(axis=1).mean(),
                             zone_pair_fraction=two_zones[:,s].mean(),bilateral_zone_pair_fraction=two_zones.all(axis=1).mean(),
                             median_23_to_26bp_usd=np.median(profiles[:,s,23:26].sum(axis=1))))
    pd.DataFrame(tall).to_csv(OUT/"outer_peaks.csv",index=False)
    median = np.median(extended,axis=0)
    wide = pd.DataFrame([(side,b,median[s,b]) for s,side in enumerate(SIDES) for b in range(100)],
                        columns=["side","bin","median_usd"])
    wide.to_csv(OUT/"extended_profile.csv",index=False)
    return book_only,moved_only


def local_peak(x,b):
    return (x[...,b]>x[...,b-1]) & (x[...,b]>x[...,b+1])


def mountain_summary(grid,valid,pairs):
    rows,shape = [],[]
    def describe(name, sample):
        xs = grid[sample]
        if len(xs)==0:
            return
        med = np.median(xs,axis=0)
        peaks = local_peak(xs,6) & local_peak(xs,20)
        for s,side in enumerate(SIDES):
            shape.extend((name,side,b,v) for b,v in enumerate(med[s]))
            valley = int(6+np.argmin(med[s,6:21]))
            rows.append((name,side,len(xs),med[s,6],med[s,20],valley,med[s,valley],local_peak(med[s],6),
                         local_peak(med[s],20),peaks[:,s].mean(),peaks.all(axis=1).mean()))
    days = (np.arange(len(grid))+1)//DAY
    describe("evaluation",valid&(days>=1))
    for day in range(1,7):
        describe(f"Nov {11+day}",valid&(days==day))
    for arm in ("event","calm"):
        for lag in (-1,0,5,60):
            describe(f"{arm} {lag:+d}s",pairs[arm].to_numpy()+lag)
    data = pd.DataFrame(rows,columns=["sample","side","seconds","near_usd","outer_usd","saddle_bin","saddle_usd",
                                      "median_near_peak","median_outer_peak","both_peaks_fraction","all_four_fraction"])
    data.to_csv(OUT/"mountains.csv",index=False)
    pd.DataFrame(shape,columns=["sample","side","bin","median_usd"]).to_csv(OUT/"profiles.csv",index=False)
    return data


@lru_cache(maxsize=65536)
def transition(old,new):
    before,after = intervals(old),intervals(new)
    outgoing = [0]*len(before)
    incoming = [0]*len(after)
    for i,j in links(old,new):
        outgoing[i] += 1
        incoming[j] += 1
    # Store parent IDs by their leftmost bin so the same parent can be compared under two coordinate choices.
    deaths = sum(1<<lo for (lo,_),deg in zip(before,outgoing) if deg==0)
    splits = sum(1<<lo for (lo,_),deg in zip(before,outgoing) if deg>1)
    return (len(before),sum(hi-lo>=3 for lo,hi in before),deaths,splits,
            sum(x==0 for x in incoming),sum(x>1 for x in incoming))


def transition_arrays(before,after):
    keys = (before.astype(np.int64)<<25)|after
    unique,inv = np.unique(keys,return_inverse=True)
    metrics = np.array([transition(int(k>>25),int(k & ((1<<25)-1))) for k in unique],dtype=np.int32)
    return metrics[inv]


def countbits(x):
    return np.bitwise_count(x.astype(np.uint32))


def lifetimes(mask,sample,valid):
    rows = []
    for t in sample:
        if not valid[t-1:t+61].all():
            continue
        old,now = int(mask[t-1]),int(mask[t])
        for lo,hi in intervals(now):
            reached = (1<<hi)-(1<<lo)
            fresh = not (old & reached)
            lifetime = 61
            for k in range(1,61):
                reached = reachable_next(reached,int(mask[t+k]))
                if not reached:
                    lifetime = k
                    break
            rows.append((fresh,lifetime))
    return rows


def graph_summary(grid,valid,mid2,pairs,book_only,moved_only):
    ix = np.arange(len(grid))
    prior = np.maximum(0,ix-1)
    eligible = valid & valid[prior] & (ix+1>=DAY)
    speed = 10000*np.abs(mid2-mid2[prior])/np.maximum(mid2[prior],1)
    records, causes, life, examples = [],[],[],[]
    for quantile,cuts in CUTS.iterrows():
        masks = (grid>=cuts.to_numpy()[:,None]).astype(np.uint32) @ WEIGHTS
        for s,side in enumerate(SIDES):
            m = masks[:,s]
            meta = transition_arrays(m[prior],m)
            deaths,splits = countbits(meta[:,2]),countbits(meta[:,3])
            stages = {"evaluation":np.flatnonzero(eligible)}
            for arm in ("event","calm"):
                ts = pairs.loc[pairs.side==s,arm].to_numpy()
                stages[arm+" index"] = ts
                stages[arm+" previous"] = ts-1
                stages[arm+" next 5s"] = (ts[:,None]+np.arange(1,6)).ravel()
            stages["move <0.25bp"] = np.flatnonzero(eligible & (speed<.25))
            stages["move 0.25–1bp"] = np.flatnonzero(eligible & (speed>=.25)&(speed<1))
            stages["move >=1bp"] = np.flatnonzero(eligible & (speed>=1))
            for name,t in stages.items():
                assert eligible[t].all()
                nparents,wide = meta[t,:2].sum(axis=0)
                records.append((quantile,side,name,len(t),nparents,wide,deaths[t].sum(),splits[t].sum(),
                                meta[t,4].sum(),meta[t,5].sum()))
            if quantile==Q:
                # At fixed midpoint both counterfactuals have exact expected identities.
                same = eligible & (mid2==mid2[prior])
                assert np.array_equal(book_only[same,s],m[same])
                assert np.array_equal(moved_only[same,s],m[prior[same]])
                for kind,target in [("current_book_old_mid",book_only[:,s]),("old_book_current_mid",moved_only[:,s])]:
                    alt = transition_arrays(m[prior],target)
                    for event,j,raw in [("death",2,deaths),("split",3,splits)]:
                        same_parent = countbits(meta[:,j] & alt[:,j])
                        for name in ["evaluation","event index","calm index"]:
                            t = stages[name]
                            causes.append((side,name,event,kind,raw[t].sum(),same_parent[t].sum()))
                # Find first split after noon on day 1 of evaluation, for an attributed graph illustration.
                t = int(np.flatnonzero(eligible&(ix+1>=DAY+12*3600)&(splits>0))[0])
                bit = int(meta[t,3]); lo = (bit & -bit).bit_length()-1
                parent = next((a,b) for a,b in intervals(int(m[t-1])) if a==lo)
                children = [(a,b) for a,b in intervals(int(m[t])) if max(a,parent[0]) < min(b,parent[1])]
                bins = np.arange(parent[0],parent[1])
                examples.append(dict(side=side,cutoff=float(cuts.iloc[s]),t=t,before_end_utc=utc(t).isoformat(),
                    after_end_utc=utc(t+1).isoformat(),parent=parent,children=children,
                    previous_usd=grid[t-1,s,bins].tolist(),current_usd=grid[t,s,bins].tolist()))
            sample = ix[(ix+1>=DAY)&((ix+1)%60==0)&(ix+60<len(ix))]
            times = np.array(lifetimes(m,sample,valid))
            for name,group in [("all_at_minute",times[:,1]),("born_at_minute",times[times[:,0]==1,1])]:
                life.append((quantile,side,name,len(group),int(np.quantile(group,.5,method="inverted_cdf")),
                             int(np.quantile(group,.9,method="inverted_cdf")),np.mean(group>1),np.mean(group>5),np.mean(group>60)))
    pd.DataFrame(records,columns=["quantile","side","sample","seconds","parent_exposures","width_3plus","deaths","splits",
                                  "births","merges"]).to_csv(OUT/"graph_transitions.csv",index=False)
    pd.DataFrame(causes,columns=["side","sample","event","counterfactual","actual","same_parent_same_event"]).to_csv(OUT/"reanchor.csv",index=False)
    pd.DataFrame(life,columns=["quantile","side","sample","lineages","median_to_loss_s","p90_to_loss_s",
                               "alive_1s","alive_5s","alive_60s"]).to_csv(OUT/"lineage_life.csv",index=False)
    (OUT/"split_examples.json").write_text(json.dumps(examples,indent=2)+"\n")


def plot():
    profile = pd.read_csv(OUT/"profiles.csv")
    wide = pd.read_csv(OUT/"extended_profile.csv")
    fig,(ax,bx) = plt.subplots(1,2,figsize=(11,4),layout="constrained")
    for side,sign,color in [("bid",-1,"#216c80"),("ask",1,"#984324")]:
        med = profile[(profile["sample"]=="evaluation")&(profile.side==side)]
        post = profile[(profile["sample"]=="event +0s")&(profile.side==side)]
        ax.plot(sign*(med.bin+.5),med.median_usd/1e6,color=color,lw=2,label=side.title()+" all seconds")
        ax.plot(sign*(post.bin+.5),post.median_usd/1e6,color=color,ls=":",lw=1.6,label=side.title()+" after trade")
        sub = wide[wide.side==side]
        bx.plot(sign*(sub.bin+.5),sub.median_usd/1e6,color=color,lw=1.5)
    ax.legend(frameon=False,fontsize=8,ncol=2)
    ax.set_title("A. Ridges inside 25 bp")
    bx.set_title("B. The same book out to 100 bp")
    for a in (ax,bx):
        a.axvline(0,color="grey",lw=.6)
        a.set(xlabel="Distance from midpoint (bp)    bids ← 0 → asks",ylabel="Median USD millions per 1-bp bin")
        a.spines[["right","top"]].set_visible(False)
    fig.savefig(OUT/"mountains.png",dpi=175)
    plt.close(fig)


def main():
    with np.load(GRID_CACHE) as z:
        grid,valid,mid2 = (z[k] for k in ("grid","valid","mid2"))
    pairs = pd.read_csv(OUT/"matched_seconds.csv")
    book_only,moved_only = native_checks(grid,valid,mid2,pairs)
    mountain_summary(grid,valid,pairs)
    graph_summary(grid,valid,mid2,pairs,book_only,moved_only)
    plot()


if __name__=="__main__":
    main()
