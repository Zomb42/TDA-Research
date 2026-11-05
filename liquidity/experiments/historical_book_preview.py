"""Render an actual historical binary-contract book without trading code.

Exact decimal replay remains separate from explicit 0.001-dollar display bins.
Uses one single-snapshot session; refuses ambiguous reconnect/timestamp ordering.
"""
from datetime import datetime, timezone
from decimal import Decimal
import json
import math
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/tda-btc-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "market_data/datasets/hft_kalshi_archive_inventory/files.jsonl"
ELIGIBLE = [json.loads(line) for line in INVENTORY.open()]
ELIGIBLE = [r for r in ELIGIBLE if r["snapshot_count"] == 1 and r["whole_file_book_replay_passed"] and r["first_event_time"] and r["last_event_time"]]
# Choose duration, not a depth/topology value, for an informative full-session view.
SOURCE = Path(max(ELIGIBLE,key=lambda r:datetime.fromisoformat(r["last_event_time"])-datetime.fromisoformat(r["first_event_time"]))["path"])
OUT = Path(__file__).with_suffix("")


def timestamp(msg):
    value = msg.get("ts")
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    if msg.get("ts_ms") is not None:
        return float(msg["ts_ms"])/1000
    return float(value) if value is not None else None


def public_books():
    with SOURCE.open() as stream:
        for line in stream:
            event = json.loads(line)
            if event.get("type") in ("orderbook_snapshot", "orderbook_delta"):
                yield event


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    first = last = previous = None
    snapshots = deltas = 0
    for event in public_books():
        if event["type"] == "orderbook_snapshot":
            snapshots += 1
            continue
        t = timestamp(event["msg"])
        if t is None or (previous is not None and t < previous):
            raise ValueError("Missing or decreasing book timestamps; do not silently reorder")
        first = t if first is None else first
        last = previous = t
        deltas += 1
    if snapshots != 1:
        raise ValueError("This preview requires one initial snapshot; segment reconnect sessions separately")
    times = np.arange(math.ceil(first/5)*5, math.floor(last/5)*5+1, 5.)
    edges = np.linspace(0,1,1001)
    bid_grid = np.zeros((1000,len(times)))
    ask_grid = np.zeros_like(bid_grid)
    best_bid = np.full(len(times),np.nan)
    best_ask = np.full(len(times),np.nan)
    books = {"yes": {}, "no": {}}
    next_column = 0
    selected_book = None
    selected_column = len(times)//2
    last_seq = sid = None

    def sample(column):
        nonlocal selected_book
        for side,grid,complement in [("yes",bid_grid,False),("no",ask_grid,True)]:
            levels = books[side]
            prices = np.array([float(1-p if complement else p) for p in levels])
            quantities = np.array([float(q) for q in levels.values()])
            grid[:,column] = np.histogram(prices,bins=edges,weights=quantities)[0]
            np.testing.assert_allclose(grid[:,column].sum(), quantities.sum(),rtol=1e-12,atol=1e-8)
        if books["yes"]:best_bid[column]=float(max(books["yes"]))
        if books["no"]:best_ask[column]=float(1-max(books["no"]))
        if column == selected_column:
            selected_book = {side:dict(levels) for side,levels in books.items()}

    for event in public_books():
        msg = event["msg"]
        if event["type"] == "orderbook_snapshot":
            books = {"yes": {}, "no": {}}
            for side in books:
                for price,quantity in msg.get(side+"_dollars_fp",[]) or []:
                    p,q=Decimal(price),Decimal(quantity)
                    if q:books[side][p]=q
            sid,last_seq=event["sid"],event["seq"]
            continue
        t=timestamp(msg)
        while next_column < len(times) and times[next_column] < t:
            sample(next_column)
            next_column += 1
        if event["sid"] != sid or event["seq"] != last_seq+1:
            raise ValueError("Sequence gap")
        side=msg["side"]
        price,delta=Decimal(msg["price_dollars"]),Decimal(msg["delta_fp"])
        quantity=books[side].get(price,Decimal(0))+delta
        if quantity<0:raise ValueError("Negative quantity")
        if quantity:books[side][price]=quantity
        else:books[side].pop(price,None)
        last_seq=event["seq"]
    while next_column<len(times):
        sample(next_column);next_column+=1
    assert selected_book is not None
    selected_time=datetime.fromtimestamp(times[selected_column],timezone.utc).isoformat()
    full=[]
    for side in ["yes","no"]:
        for p,q in selected_book[side].items():
            full.append(dict(display_side="bid" if side=="yes" else "ask",yes_price_dollars=str(p if side=="yes" else 1-p),
                             quantity_contracts=str(q),source_side=side,source_bid_price_dollars=str(p),timestamp_utc=selected_time))
    table=pd.DataFrame(full)
    table.to_csv(OUT/"selected_book_exact.csv",index=False)
    top={}
    for side,reverse in [("bid",True),("ask",False)]:
        rows=sorted([r for r in full if r["display_side"]==side],key=lambda r:Decimal(r["yes_price_dollars"]),reverse=reverse)
        top[side]=rows[:5]
    (OUT/"selected_top_levels.json").write_text(json.dumps(top,indent=2)+"\n")
    np.savez_compressed(OUT/"depth_grid.npz",times_epoch_seconds=times,price_edges_dollars=edges,
                        yes_bid_contracts=bid_grid,implied_yes_ask_contracts=ask_grid)
    minutes=(times-times[0])/60
    time_edges=np.r_[minutes[0]-5/120,(minutes[:-1]+minutes[1:])/2,minutes[-1]+5/120]
    fig,axes=plt.subplots(2,1,figsize=(13,8),sharex=True,sharey=True)
    vmax=float(np.log1p(max(bid_grid.max(),ask_grid.max())))
    for ax,grid,title in zip(axes,[bid_grid,ask_grid],["Displayed YES bids","Displayed YES asks, derived from NO bids"]):
        im=ax.pcolormesh(time_edges,edges,np.log1p(grid),shading="flat",cmap="magma",vmin=0,vmax=vmax,rasterized=True)
        ax.plot(minutes,best_bid,color="cyan",lw=0.8,label="best YES bid")
        ax.plot(minutes,best_ask,color="lime",lw=0.8,label="best YES ask")
        ax.axvline(minutes[selected_column],color="white",ls="--",lw=0.9)
        ax.set_ylabel("YES contract price ($)")
        ax.set_title(title)
        ax.set_ylim(0,1)
    axes[0].legend(loc="upper left",fontsize=8)
    axes[-1].set_xlabel(f"Minutes since {datetime.fromtimestamp(times[0],timezone.utc):%Y-%m-%d %H:%M:%S} UTC")
    fig.suptitle(f"Actual historical Kalshi BTC event-contract liquidity\n{SOURCE.stem}; five-second samples, $0.001 display bins",fontsize=13)
    fig.subplots_adjust(top=.87,bottom=.1,left=.08,right=.86,hspace=.25)
    color_axis=fig.add_axes([.89,.16,.02,.62])
    fig.colorbar(im,cax=color_axis,label="log(1 + displayed contracts)")
    fig.savefig(OUT/"historical_depth.png",dpi=150)
    plt.close(fig)
    report=dict(source=str(SOURCE),instrument="BTC 15-minute binary event contract",snapshots=snapshots,deltas=deltas,
                samples=len(times),sample_seconds=5,display_price_bin_dollars=.001,
                sample_start_utc=datetime.fromtimestamp(times[0],timezone.utc).isoformat(),
                sample_end_utc=datetime.fromtimestamp(times[-1],timezone.utc).isoformat(),selected_book_time_utc=selected_time,
                exact_yes_levels=len(selected_book["yes"]),exact_no_levels=len(selected_book["no"]),
                total_depth_preserved_in_every_display_column=True,book_timestamp_regressions=0,
                limitations=["Single binary contract session; price is event-contract probability price, not USD per BTC.",
                             "Five-second sampling and $0.001 bins are display choices; exact selected book is saved separately.",
                             "Timing uses recorded exchange timestamps because original local receipt times are unavailable.",
                             "An empty initial snapshot is valid; zero displayed quantity is not missing data in the replayed book."])
    (OUT/"summary.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    print(json.dumps(top,indent=2))


if __name__=="__main__":main()
