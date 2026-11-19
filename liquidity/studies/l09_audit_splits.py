"""Replay every apparent one-second split at the original message cadence."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from functools import lru_cache
import json
from pathlib import Path
import subprocess
import tempfile

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from l01_snapshots import CACHE, SOURCE
from l02_describe import GRID_CACHE, SIDES
from l03_band_age import DAY, WEIGHTS, intervals, reachable_next
from l04_trade_tape import OUT
from l05_refill import CUTS, utc
from l06_book_breaks import transition_arrays, transition
from l08_split_replay import ladder, state


def selections():
    with np.load(GRID_CACHE) as z:
        grid,valid = z["grid"],z["valid"]
    ix = np.arange(1,len(valid))
    ok = (ix+1 >= DAY)&valid[ix-1]&valid[ix]
    groups = defaultdict(lambda: defaultdict(list))
    for s,side in enumerate(SIDES):
        cut = CUTS.loc[.9,side]
        m = (grid[:,s]>=cut).astype(np.uint32) @ WEIGHTS
        splitmask = transition_arrays(m[:-1],m[1:])[:,3]
        for t in ix[(splitmask>0)&ok]:
            bits = int(splitmask[t-1])
            for lo,hi in intervals(int(m[t-1])):
                if bits & (1<<lo):
                    children = [((1<<b)-(1<<a)) for a,b in intervals(int(m[t])) if max(lo,a)<min(hi,b)]
                    groups[int(t)//3600][int(t)].append((side,lo,hi,children))
    return groups


@lru_cache(maxsize=32768)
def split_parents(old,new):
    return transition(old,new)[3]


def replay_second(t,specs,pre,post,lines):
    book = ladder(pre)
    original = []
    sides = sorted({v[0] for v in specs})
    masks = {s:state(book,s,CUTS.loc[.9,s])[1] for s in sides}
    for s,lo,hi,children in specs:
        assert (lo,hi) in intervals(masks[s]) and len(children)>1
        original.append(dict(side=s,lo=lo,hi=hi,children=children,reach=(1<<hi)-(1<<lo),
                             first_us=None,first_source=None,midpoint_changed=None,lost_us=None))
    seq = pre["book_seq"]
    old_mid = -min(book)+min(p for p in book if p>0)
    for row in lines:
        msg = row["message"]
        payload = msg["msg"]
        seq += 1
        assert msg["seq"]==seq and row["epoch"]==pre["epoch"]
        key = int(Decimal(payload["price"])*10000)*(-1 if payload["side"]=="bid" else 1)
        book[key] = book.get(key,0)+int(Decimal(payload["delta"])*100)
        assert book[key]>=0
        if book[key]==0:
            del book[key]
        new_mid = -min(book)+min(p for p in book if p>0)
        for s in sides:
            if new_mid==old_mid and payload["side"]!=s:
                continue
            newmask = state(book,s,CUTS.loc[.9,s])[1]
            old = masks[s]
            if old==newmask:
                continue
            branching = split_parents(old,newmask)
            for node in original:
                if node["side"]!=s or not node["reach"]:
                    continue
                # The leftmost bit identifies the parent interval. Reach contains all its bins.
                old_reach = node["reach"]
                next_reach = reachable_next(old_reach,newmask)
                us = int((row["received_at"].split(".")[1].split("+")[0]).ljust(6,"0"))
                if node["first_us"] is None and branching & old_reach:
                    node.update(first_us=us,first_source=payload["side"],midpoint_changed=new_mid!=old_mid)
                if not next_reach:
                    node["lost_us"] = us
                node["reach"] = next_reach
            masks[s] = newmask
        old_mid = new_mid
    assert len(lines)==post["delta_count"] and seq==post["book_seq"] and book==ladder(post)
    rows = []
    for node in original:
        children = node.pop("children")
        reached = node.pop("reach")
        count = sum(bool(child&reached) for child in children)
        assert not (count>=2 and node["first_us"] is None)
        rows.append(dict(t=t,start_utc=utc(t).isoformat(),updates=len(lines),sampled_children=len(children),
                         reached_children=count,**node))
    return rows


def audit_hour(job):
    h,specs = job
    stamp = utc(h*3600)
    name = stamp.strftime("%Y-%m-%dT%H-00-00Z")
    columns = ["epoch","book_seq","delta_count","signed_price_tick","size_100"]
    table = pq.read_table(CACHE/(name+".parquet"),columns=columns)
    source = SOURCE/"kalshi_perp"/(name+".jsonl.gz")
    with tempfile.TemporaryDirectory() as tmp:
        patterns = Path(tmp)/"seconds.txt"
        patterns.write_text("\n".join('"received_at":"'+utc(t).strftime("%Y-%m-%dT%H:%M:%S") for t in specs)+"\n")
        raw = subprocess.run(["rg","-z","-F","--no-filename","-f",str(patterns),str(source)],capture_output=True,check=True).stdout
    rows = defaultdict(list)
    for line in raw.splitlines():
        if b'"type":"orderbook_delta"' in line:
            row = json.loads(line)
            ts = row["received_at"]
            rows[h*3600+int(ts[14:16])*60+int(ts[17:19])].append(row)
    audits = []
    for t,items in sorted(specs.items()):
        j = t%3600
        if j:
            pre,post = table.slice(j-1,2).to_pylist()
        else:
            prev = (stamp-pd.Timedelta(hours=1)).strftime("%Y-%m-%dT%H-00-00Z")
            pre = pq.read_table(CACHE/(prev+".parquet"),columns=columns).slice(3599,1).to_pylist()[0]
            post = table.slice(0,1).to_pylist()[0]
        audits.extend(replay_second(t,items,pre,post,rows[t]))
    return audits


def main():
    targets = selections()
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = [r for hour in pool.map(audit_hour,sorted(targets.items())) for r in hour]
    frame = pd.DataFrame(rows)
    expected = pd.read_csv(OUT/"graph_transitions.csv").query("sample=='evaluation' and quantile==0.9")
    assert len(frame)==expected.splits.sum()
    frame.to_csv(OUT/"all_split_replays.csv",index=False)
    print(frame.groupby(["side","reached_children"]).size().to_string())
    print("First genuine split by source and midpoint change")
    print(frame.groupby([frame.first_source==frame.side,"midpoint_changed"]).size().to_string())


if __name__=="__main__":
    main()
