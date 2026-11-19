"""Resolve each illustrated one-second split using every delivered book update inside it."""
from decimal import Decimal
import json
import subprocess

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from l01_snapshots import CACHE, SOURCE
from l02_describe import plt
from l03_band_age import intervals, reachable_next
from l04_trade_tape import OUT
from l05_refill import utc


def ladder(row):
    return {p:q for p,q in zip(row["signed_price_tick"],row["size_100"]) if q}


def state(book,side,cut):
    mid2 = -min(book)+min(p for p in book if p>0)
    depth = [0]*25
    for p,q in book.items():
        if (p>0) != (side=="ask"):
            continue
        dist = abs(2*abs(p)-mid2)*10000//mid2
        if dist<25:
            depth[dist] += abs(p)*q
    # The cutoff can lie between units of one microdollar.
    mask = sum(1<<b for b,value in enumerate(depth) if value/1e6>=cut)
    return mid2,mask,depth


def extended_replay(example):
    t = example["t"]
    stamp = utc(t)
    name = stamp.strftime("%Y-%m-%dT%H-00-00Z")
    second = stamp.minute*60+stamp.second
    assert second>0
    table = pq.read_table(CACHE/(name+".parquet"),columns=["book_seq","signed_price_tick","size_100","epoch","delta_count"])
    pre,post = table.slice(second-1,2).to_pylist()
    book = ladder(pre)
    side = example["side"]
    cut = example["cutoff"]
    lo,hi = example["parent"]
    assert hi-lo==3
    region = (1<<hi)-(1<<lo)
    center = 1<<(lo+1)
    flanks = region ^ center
    old_mid,mask,depth = state(book,side,cut)
    assert (lo,hi) in intervals(mask)
    assert np.allclose(np.array(depth[lo:hi])/1e6,example["previous_usd"])
    sequence = pre["book_seq"]
    native = SOURCE/"kalshi_perp"/(name+".jsonl.gz")
    data = subprocess.run(["rg","-z","-F","--no-filename",'"received_at":"'+stamp.strftime("%Y-%m-%dT%H:%M:%S"),str(native)],
                          capture_output=True,check=True)
    reached = region
    events, splits, deaths = [], [], []
    trace = [(0.0,old_mid/2,tuple(d/1e6 for d in depth[lo:hi]),True,False)]
    for line in data.stdout.splitlines():
        row = json.loads(line)
        msg = row.get("message",{})
        if msg.get("type")!="orderbook_delta":
            continue
        payload = msg["msg"]
        assert row["epoch"]==pre["epoch"] and msg["seq"]==sequence+1
        sequence = msg["seq"]
        tick = int(Decimal(payload["price"])*10000)*(-1 if payload["side"]=="bid" else 1)
        delta = int(Decimal(payload["delta"])*100)
        book[tick] = book.get(tick,0)+delta
        if book[tick]==0:
            del book[tick]
        mid2,newmask,depth = state(book,side,cut)
        us = int((pd.Timestamp(row["received_at"])-stamp).value//1000)
        assert 0<=us<1_000_000
        # A parent in the original lineage divides into two overlapping children on this update.
        divided = False
        for a,b in intervals(mask):
            parent = (1<<b)-(1<<a)
            if parent & reached and sum(max(a,c)<min(b,d) for c,d in intervals(newmask))>=2:
                divided = True
        next_reached = reachable_next(reached,newmask)
        flanks_split = (newmask & region)==flanks
        entry = dict(receipt_us=us,utc=row["received_at"],sequence=sequence,delta_side=payload["side"],
                     delta_price_usd_btc=abs(tick),delta_contracts=delta/100,mid_usd_btc=mid2/2,
                     previous_mid_usd_btc=old_mid/2, three_depths_usd=[d/1e6 for d in depth[lo:hi]])
        if divided:
            splits.append(entry)
        if reached and not next_reached:
            deaths.append(entry)
        if flanks_split and (mask & region)!=flanks:
            events.append(entry)
        trace.append((us/1e6,mid2/2,tuple(entry["three_depths_usd"]),bool(next_reached),flanks_split))
        mask,reached,old_mid = newmask,next_reached,mid2
    assert book==ladder(post) and sequence==post["book_seq"] and len(trace)-1==post["delta_count"]
    assert np.allclose(trace[-1][2],example["current_usd"]) and trace[-1][4]
    elapsed = np.diff([r[0] for r in trace]+[1.])
    share = sum(dt for dt,r in zip(elapsed,trace) if r[4])
    result = dict(side=side,second_start_utc=stamp.isoformat(),book_updates=len(trace)-1,
                first_both_flanks_high_middle_low=events[0],number_of_entries_into_that_state=len(events),
                fraction_of_second_with_separate_flanks=share,first_lineage_split=splits[0] if splits else None,
                number_of_lineage_splits=len(splits),loss_of_all_original_descendants=deaths[0] if deaths else None,
                original_lineage_reaches_left_flank_at_close=bool(reached & (1<<lo)),
                original_lineage_reaches_right_flank_at_close=bool(reached & (1<<(hi-1))),
                endpoint_ladder_and_sequence_verified=True)
    return result,trace


def draw_raw(example,result,trace):
    times = 1000*np.array([r[0] for r in trace]+[1.])
    d = np.asarray([r[2] for r in trace])
    active = np.column_stack([d>=example["cutoff"],[r[3] for r in trace]])
    fig,ax = plt.subplots(figsize=(9.5,3.2),layout="constrained")
    labels = [f"{b}–{b+1} bp" for b in range(*example["parent"])]+["Original band has descendants"]
    for j in range(active.shape[1]):
        changes = np.diff(np.r_[False,active[:,j],False].astype(int))
        begin,end = np.flatnonzero(changes==1),np.flatnonzero(changes==-1)
        spans = [(times[a],times[b]-times[a]) for a,b in zip(begin,end)]
        ax.broken_barh(spans,(j-.32,.64),facecolors="#216c80" if j<3 else "#799862")
    ax.axvline(result["first_lineage_split"]["receipt_us"]/1000,color="#8d3d20",lw=1.5,label="First split in recorded updates")
    native = example["native_splits_in_transition"][0]["utc"]
    interp_ms = (pd.Timestamp(native)-pd.Timestamp(result["second_start_utc"])).total_seconds()*1000
    ax.axvline(interp_ms,color="#8d3d20",ls="--",lw=1.3,label="Split from one-second interpolation")
    ax.set(xlim=(0,1000),ylim=(3.5,-.5),yticks=range(4),yticklabels=labels,
           xlabel="Milliseconds after 12:05:08 UTC on November 12",title="The same bid band through 292 delivered book updates")
    ax.legend(frameon=False,loc="upper center",bbox_to_anchor=(.5,-.24),ncol=2,fontsize=8)
    ax.spines[["right","top","left"]].set_visible(False)
    ax.tick_params(axis="y",length=0)
    fig.savefig(OUT/"inside_one_second.png",dpi=175)
    plt.close(fig)


def main():
    examples = json.loads((OUT/"native_split_examples.json").read_text())
    results = []
    for e in examples:
        result,trace = extended_replay(e)
        results.append(result)
        if e["side"]=="bid":
            draw_raw(e,result,trace)
    (OUT/"event_by_event_splits.json").write_text(json.dumps(results,indent=2)+"\n")
    print(json.dumps(results,indent=2))


if __name__=="__main__":
    main()
