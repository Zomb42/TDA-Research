"""A matched event study of displayed depth after individual large aggressive trades."""
import json

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from l01_snapshots import CACHE, RESULTS, START
from l02_describe import GRID_CACHE, SIDES, plt
from l03_band_age import DAY, WEIGHTS, intervals, reachable_next
from l04_trade_tape import OUT, TAPE

HORIZON = 60
CUTS = pd.read_csv(RESULTS/"cutoffs.csv").pivot(index="quantile", columns="side", values="threshold_usd").loc[:, list(SIDES)]
FEATURES = ("log_depth", "log_spread", "log_vol")


def utc(t):
    offset = int(t) if np.ndim(t) == 0 else np.asarray(t)
    return pd.to_datetime(int(START.timestamp()) + offset, unit="s", utc=True)


def book_quotes():
    hours = json.loads((RESULTS/"snapshot_manifest.json").read_text())["hours"]
    pieces = [pq.read_table(CACHE/(r["hour"]+".parquet"), columns=["best_bid_tick","best_ask_tick"]).to_pandas()
              for r in hours if r["seconds"]]
    return pd.concat(pieces, ignore_index=True)


def matched_seconds(tape, grid, valid, mid2, ordinary=False):
    qty = tape.size_100.to_numpy()
    times = tape.t.to_numpy()
    threshold = np.quantile(qty[(times < DAY) & ~tape.block], .99)
    large = tape[(qty >= threshold) & ~tape.block].copy()
    large["delay_ms"] = large.received_us/1000-large.exchange_ms
    by_second = large.groupby("t").agg(side=("passive_side","first"), sides=("passive_side","nunique"),
                                        peak_size_100=("size_100","max"), delay_ms=("delay_ms","max"))
    ix = np.arange(len(grid))
    full = np.zeros(len(grid), bool)
    test = ix[(ix >= 61) & (ix + HORIZON < len(ix))]
    missing = np.r_[0, np.cumsum(~valid)]
    full[test] = missing[test+HORIZON+1] == missing[test-61]
    prior_large = np.searchsorted(by_second.index, ix)-np.searchsorted(by_second.index, ix-60)
    candidate = by_second[by_second.index >= DAY]
    isolated = candidate[(prior_large[candidate.index] == 0) & (candidate.sides == 1) & full[candidate.index]]
    no_trade = np.bincount(times, minlength=len(grid)) == 0
    small_side = np.zeros((len(grid),2),bool)
    ordinary_prints = tape[(qty < threshold) & ~tape.block]
    small_side[ordinary_prints.t.to_numpy(),ordinary_prints.passive_side.to_numpy()] = True
    index_large = np.isin(ix,by_second.index)
    calm = full & (~index_large if ordinary else no_trade) & (prior_large == 0) & (ix >= DAY)
    hour = ix//3600
    quotes = book_quotes()
    spread = 20000*(quotes.best_ask_tick-quotes.best_bid_tick).to_numpy()/np.maximum(mid2,1)
    change = np.diff(np.log(np.maximum(1,mid2)), prepend=np.log(mid2[0]))*10000
    vol = np.sqrt(pd.Series(change**2).rolling(60).sum().to_numpy())
    depth = grid[:, :, :5].sum(axis=2)
    peak = grid[:, :, :5].argmax(axis=2)
    covariates = np.stack([np.log1p(depth/1000), np.broadcast_to(np.log1p(spread)[:,None], depth.shape),
                           np.broadcast_to(np.log1p(vol)[:,None],depth.shape)],axis=-1)
    scale = np.nanstd(covariates[(ix < DAY) & valid], axis=(0,1))
    assert np.all(scale > 0)
    used = np.zeros(len(grid), bool)
    pairs = []
    for h, group in isolated.groupby(isolated.index//3600):
        pool = np.flatnonzero(calm & (hour == h))
        for e, row in group.iterrows():
            s = int(row.side)
            if depth[e-1,s] <= 0:
                continue
            candidates = pool[(~used[pool]) & (np.abs(pool-e)>HORIZON) & (depth[pool-1,s]>0)
                              & (peak[pool-1,s] == peak[e-1,s])]
            if ordinary:
                candidates = candidates[small_side[candidates,s]]
            if not len(candidates):
                continue
            diff = (covariates[candidates-1,s]-covariates[e-1,s])/scale
            eligible = np.max(np.abs(diff), axis=1) <= 1
            if not eligible.any():
                continue
            best = np.argmin((diff[eligible]**2).sum(axis=1))
            c = int(candidates[eligible][best])
            used[c] = True
            pairs.append((e,c,s,int(row.peak_size_100),row.delay_ms,int(peak[e-1,s])))
    pairs = pd.DataFrame(pairs,columns=["event","calm","side","largest_size_100","max_delay_ms","dominant_bin"])
    e, c, side = (pairs[k].to_numpy() for k in ["event","calm","side"])
    assert len(set(c)) == len(c) and np.all(e//3600 == c//3600)
    assert small_side[c,side].all() if ordinary else no_trade[c].all()
    assert np.all(peak[e-1,side] == peak[c-1,side]) and (prior_large[np.r_[e,c]] == 0).all()
    balance = []
    for j, name in enumerate(FEATURES):
        a, b = covariates[e-1,side,j], covariates[c-1,side,j]
        balance.append(dict(feature=name,mean_event=a.mean(),mean_calm=b.mean(),calibration_sd=scale[j],
                            standardized_difference=(a-b).mean()/scale[j]))
    large_flag = np.zeros(len(grid),int)
    large_flag[by_second.index] = 1
    prefix = np.r_[0,large_flag.cumsum()]
    stats = dict(calibration_prints=int(((times<DAY)&~tape.block).sum()), all_study_prints=len(tape),
                 large_cutoff_contracts=threshold/100, evaluation_large_prints=int((large.t>=DAY).sum()),
                 evaluation_large_seconds=len(candidate), isolated_unidirectional_valid=len(isolated), matched=len(pairs),
                 unique_controls=pairs.calm.nunique(), event_later_large=float(np.mean(prefix[e+61]>prefix[e+1])),
                 calm_later_large=float(np.mean(prefix[c+61]>prefix[c+1])),
                 matched_max_delay_ms_median=float(np.median(pairs.max_delay_ms)),
                 matched_max_delay_ms_p99=float(pairs.max_delay_ms.quantile(.99)))
    pd.DataFrame(balance).to_csv(OUT/("ordinary_match_balance.csv" if ordinary else "match_balance.csv"), index=False)
    return pairs, stats


def paired_interval(a,b,hours):
    table = pd.DataFrame({"diff":a.astype(float)-b.astype(float),"hour":hours})
    blocks = table.groupby("hour")["diff"].agg(["sum","size"])
    rng = np.random.default_rng(181126)
    sums, ns = np.zeros(2000), np.zeros(2000)
    for day in np.unique(hours//24):
        chunk = blocks.reindex(np.arange(day*24,(day+1)*24),fill_value=0)
        draw = rng.integers(len(chunk), size=(2000,len(chunk)))
        sums += chunk["sum"].to_numpy()[draw].sum(axis=1)
        ns += chunk["size"].to_numpy()[draw].sum(axis=1)
    return np.quantile(sums/ns,[.025,.975]).tolist()


def depth_recovery(pairs, grid):
    depth = grid[:,:,:5].sum(axis=2)
    h = np.arange(-1,HORIZON+1)
    curves, recovery, byday = [], [], []
    records = pairs.copy()
    for arm in ("event","calm"):
        ts, side = records[arm].to_numpy(), records.side.to_numpy()
        values = depth[ts[:,None]+h, side[:,None]]
        ratio = values/values[:,0,None]
        depleted = ratio[:,1] <= .8
        for group, take in [("all",np.ones(len(ts),bool)),("depleted",depleted)]:
            arr = ratio[take]
            for k, q25, median, q75 in zip(h,*np.quantile(arr,[.25,.5,.75],axis=0)):
                curves.append((arm,group,k,len(arr),q25,median,q75))
        records[arm+"_pre_usd"] = values[:,0]
        records[arm+"_end_ratio"] = ratio[:,1]
        records[arm+"_depleted"] = depleted
        high = ratio[:,1:] >= 1
        for run in (1,3):
            # Completion time of the first run of one or three above-baseline observations.
            hits = np.lib.stride_tricks.sliding_window_view(high,run,axis=1).all(axis=-1)
            first = np.where(hits.any(axis=1),hits.argmax(axis=1)+run-1,HORIZON+1)
            records[arm+f"_recovery_{run}s"] = np.where(depleted,first,-1)
            a = first[depleted]
            observed = np.sort(a)[(len(a)-1)//2] if len(a) else np.nan
            recovery.append((arm,run,len(a),int((a>HORIZON).sum()),observed,
                             *(np.mean(a<=n) for n in (1,5,10,30,60))))
    for day, grp in records.groupby(records.event//DAY):
        byday.append((int(day)+11,len(grp),grp.event_depleted.mean(),grp.calm_depleted.mean()))
    summary = []
    for sample,use in [("all",np.ones(len(records),bool)),("report_delay_below_100ms",records.max_delay_ms < 100)]:
        frame = records[use]
        a,b = frame.event_depleted.to_numpy(),frame.calm_depleted.to_numpy()
        summary.append(dict(sample=sample,pairs=len(frame),event_depleted=a.sum(),calm_depleted=b.sum(),
                            excess_risk=a.mean()-b.mean(),both_depleted=(a&b).sum(),
                            lo95=(ci:=paired_interval(a,b,frame.event.to_numpy()//3600))[0],hi95=ci[1]))
    pd.DataFrame(recovery,columns=["arm","consecutive_high_s","depleted","unrecovered_60s","median_s_61_is_censored",
                                    "fraction_1s","fraction_5s","fraction_10s","fraction_30s","fraction_60s"]).to_csv(OUT/"recovery.csv",index=False)
    pd.DataFrame(summary).to_csv(OUT/"depletion_comparison.csv",index=False)
    pd.DataFrame(byday,columns=["november_day","pairs","event_depleted_fraction","calm_depleted_fraction"]).to_csv(OUT/"daily.csv",index=False)
    curves = pd.DataFrame(curves,columns=["arm","sample","seconds_after_event_close","cases","q25_ratio","median_ratio","q75_ratio"])
    curves.to_csv(OUT/"refill_curves.csv",index=False)
    return records, curves


def refill_bands(pairs, masks):
    counts = []
    for arm in ("event","calm"):
        for t, side in zip(pairs[arm],pairs.side):
            m = masks[:,side]
            old, now = int(m[t-1]),int(m[t])
            lost = old & ~now
            if not lost:
                continue
            for lo,hi in intervals(old):
                initial = (1<<hi)-(1<<lo)
                missing = initial & lost
                if not missing:
                    continue
                own, any_old = reachable_next(initial,now), reachable_next(old,now)
                for k in range(1,HORIZON+1):
                    nxt = int(m[t+k])
                    own, any_old = reachable_next(own,nxt),reachable_next(any_old,nxt)
                    returning = nxt & missing
                    while returning:
                        bit = returning & -returning
                        b = bit.bit_length()-1
                        origin = "original_band" if bit & own else "other_prior_band" if bit & any_old else "no_prior_band"
                        counts.append((arm,b,k,origin))
                        returning ^= bit
                        missing ^= bit
                    if not missing:
                        break
                while missing:
                    bit = missing & -missing
                    counts.append((arm,bit.bit_length()-1,61,"unrecovered"))
                    missing ^= bit
    rows = pd.DataFrame(counts,columns=["arm","bin","return_s","origin"])
    rows["region"] = np.where(rows["bin"]<5,"0–5 bp","5–25 bp")
    return rows.groupby(["arm","region","origin"],as_index=False).agg(bin_events=("bin","size"),median_return_or_censor_s=("return_s","median"))


def plot_refill(curves, pairs):
    fig, (ax,bx) = plt.subplots(1,2,figsize=(9.5,3.8),layout="constrained")
    for arm,color in [("event","#984324"),("calm","#216c80")]:
        sub = curves[(curves.arm==arm)&(curves["sample"]=="depleted")]
        ax.plot(sub.seconds_after_event_close,100*sub.median_ratio,color=color,label=arm.title(),lw=2)
        times = pairs.loc[pairs[arm+"_depleted"],arm+"_recovery_1s"]
        ks = np.arange(61)
        bx.step(ks,[100*(times<=k).mean() for k in ks],where="post",color=color,lw=2,label=f"{arm.title()} (n={len(times):,})")
    ax.axhline(100,ls=":",color="#777")
    ax.set(ylabel="Median depth (% of pre-second depth)", title="A. Depth after a drop of at least 20%")
    bx.set(ylabel="Recovered at least once (%)",ylim=(-2,102),title="B. First return to starting depth")
    for a in (ax,bx):
        a.set_xlabel("Seconds after index second closes")
        a.legend(frameon=False)
        a.spines[["top","right"]].set_visible(False)
    fig.savefig(OUT/"refill.png",dpi=175)
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    with np.load(GRID_CACHE) as data:
        grid,valid,mid2 = (data[k] for k in ("grid","valid","mid2"))
    tape = pd.read_parquet(TAPE)
    pairs, stats = matched_seconds(tape,grid,valid,mid2)
    records,curves = depth_recovery(pairs,grid)
    masks = (grid>=CUTS.loc[.90].to_numpy()[None,:,None]).astype(np.uint32) @ WEIGHTS
    refill_bands(pairs,masks).to_csv(OUT/"band_refill.csv",index=False)
    # Global cutoffs select almost exclusively distant walls. Calibrate a separate near-touch graph per bin.
    calibration = (np.arange(len(grid))+1<DAY)&valid
    near_cut = np.quantile(grid[calibration,:,:5],.90,axis=0)
    assert (near_cut>0).all()
    near_masks = (grid[:,:,:5]>=near_cut).astype(np.uint32) @ WEIGHTS[:5]
    refill_bands(pairs,near_masks).to_csv(OUT/"near_band_refill.csv",index=False)
    pd.DataFrame(near_cut.T,columns=SIDES).rename_axis("bin").to_csv(OUT/"near_cutoffs.csv")
    ordinary, _ = matched_seconds(tape,grid,valid,mid2,ordinary=True)
    common = records.merge(ordinary[["event","calm"]].rename(columns={"calm":"ordinary"}),on="event")
    depth = grid[:,:,:5].sum(axis=2)
    for arm in ("event","calm","ordinary"):
        t,s = common[arm].to_numpy(),common.side.to_numpy()
        common[arm+"_loss"] = depth[t,s] <= .8*depth[t-1,s]
    summaries = []
    for arm in ("calm","ordinary"):
        a,b = common.event_loss.to_numpy(),common[arm+"_loss"].to_numpy()
        ci = paired_interval(a,b,common.event.to_numpy()//3600)
        summaries.append(dict(control=arm,pairs=len(a),event_lost=a.sum(),control_lost=b.sum(),risk_difference=a.mean()-b.mean(),
                              lo95=ci[0],hi95=ci[1]))
    pd.DataFrame(summaries).to_csv(OUT/"ordinary_trade_check.csv",index=False)
    records["event_start_utc"] = utc(records.event)
    records["calm_start_utc"] = utc(records.calm)
    records.to_csv(OUT/"matched_seconds.csv",index=False)
    (OUT/"selection.json").write_text(json.dumps(stats,indent=2)+"\n")
    plot_refill(curves,records)
    print(stats)


if __name__ == "__main__":
    main()
