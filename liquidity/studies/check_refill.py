"""Check matched depth outcomes, graph denominators and the raw/continuous split witnesses."""
import json

import numpy as np
import pandas as pd
from scipy.ndimage import label

from l02_describe import GRID_CACHE, SIDES
from l04_trade_tape import OUT
from l05_refill import CUTS
from l06_book_breaks import transition


def slice_count(before,after,u,cut,diagonal):
    heights = np.empty(2*len(before)-1)
    heights[::2] = before+(after-before)*u
    a,b = (before[:-1],after[1:]) if diagonal=="original" else (before[1:],after[:-1])
    heights[1::2] = a+(b-a)*u
    return label(heights>=cut)[1]


def main():
    pairs = pd.read_csv(OUT/"matched_seconds.csv")
    with np.load(GRID_CACHE) as z:
        grid,valid = z["grid"],z["valid"]
    for arm in ["event","calm"]:
        for row in pairs.itertuples():
            t,s = getattr(row,arm),row.side
            assert valid[t-61:t+61].all()
            trace = np.sum(grid[t-1:t+61,s,:5],axis=1)
            drop = trace[1]<=.8*trace[0]
            assert drop == getattr(row,arm+"_depleted")
            for run in (1,3):
                hits = [k for k in range(run-1,61) if (trace[k-run+2:k+2]>=trace[0]).all()]
                expected = (hits[0] if hits else 61) if drop else -1
                assert expected == getattr(row,arm+f"_recovery_{run}s")
    # All possible pairs of 5-bin masks against a separate component-label implementation.
    for old in range(32):
        prev,nprev = label([(old>>b)&1 for b in range(5)])
        for new in range(32):
            nxt,nnext = label([(new>>b)&1 for b in range(5)])
            degrees = [len(set(nxt[prev==i])-{0}) for i in range(1,nprev+1)]
            stuff = transition(old,new)
            assert (stuff[0],stuff[2].bit_count(),stuff[3].bit_count()) == (nprev,degrees.count(0),sum(k>1 for k in degrees))
    native = pd.read_csv(OUT/"native_reeb_windows.csv")
    clock = native[native["sample"]=="hour_start"]
    assert len(clock)==576 and clock.native_splits.notna().all()
    raw = json.loads((OUT/"event_by_event_splits.json").read_text())
    audits = pd.read_csv(OUT/"all_split_replays.csv")
    assert len(audits)==pd.read_csv(OUT/"graph_transitions.csv").query("quantile==.9 and sample=='evaluation'").splits.sum()
    examples = json.loads((OUT/"native_split_examples.json").read_text())
    for e,r in zip(examples,raw):
        t,s = e["t"],SIDES.index(e["side"])
        a = audits[(audits.t==t)&(audits.side==e["side"])].iloc[0]
        assert a.first_us==r["first_lineage_split"]["receipt_us"] and a.lost_us==r["loss_of_all_original_descendants"]["receipt_us"]
        for orientation,key in [("original","native_splits_in_transition"),("opposite","opposite_diagonal_splits_in_transition")]:
            node = e[key][0]
            u = (pd.Timestamp(node["utc"])-pd.Timestamp(e["before_end_utc"])).total_seconds()
            f,g = grid[t-1,s],grid[t,s]
            # A new interval is present immediately beyond the reported interpolation crossing.
            assert slice_count(f,g,u+.0001,CUTS.loc[.9,e["side"]],orientation) == 1+slice_count(f,g,u-.0001,CUTS.loc[.9,e["side"]],orientation)
    check = dict(matched_pairs_checked=len(pairs),independently_checked_bin_transitions=32**2,
                 verified_native_hour_side_diagonal_windows=len(clock),full_message_split_windows=len(audits),
                 example_split_times_checked_in_both_mesh_orientations=len(examples),
                 unique_source_updates_in_split_seconds=int(audits.drop_duplicates("t").updates.sum()))
    (OUT/"verification.json").write_text(json.dumps(check,indent=2)+"\n")
    print(check)


if __name__=="__main__":
    main()
