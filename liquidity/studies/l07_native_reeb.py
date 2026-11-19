"""Native continuous time-Reeb graphs on frozen hourly windows and two attributed splits."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from l01_snapshots import ROOT
from l02_describe import GRID_CACHE, SIDES, plt
from l03_band_age import DAY, graph_edges
from l04_trade_tape import OUT
from l05_refill import CUTS, utc

sys.path.insert(0,str(ROOT/"liquidity/experiments"))
from btc_reeb_graphs_2026_11_05 import clipped_mesh, native_environment, write_vtu
from btc_reeb_report_2026_11_05 import read_vtu, graph_topology, mesh_topology, simplify


def solve_mesh(pts,tris,dirpath,single):
    folder = Path(dirpath)
    domain = folder/"domain.vtu"
    write_vtu(domain,pts,tris)
    env,binary = native_environment()
    subprocess.run([str(binary),"-i",str(domain),"-a","time","-o",str(folder/"graph"),"-t","1","-d","0"] + (["-s"] if single else []),
                   env=env,capture_output=True,check=True)
    data = read_vtu(folder/"graph_port_1.vtu")
    point = data["Points"]["Points"].astype(float)
    conn = data["Cells"]["connectivity"].reshape(-1,2)
    edges = []
    for i,(a,b) in enumerate(conn):
        a,b = int(a),int(b)
        if point[a,0]>point[b,0]:
            a,b = b,a
        edges.append(dict(source=a,target=b,arc_id=i,path=[point[a,:2].tolist(),point[b,:2].tolist()]))
    raw = graph_topology(len(point),[(e["source"],e["target"]) for e in edges])
    mesh = mesh_topology(read_vtu(domain))
    if (raw["components"],raw["cycles"]) != (mesh["components"],mesh["holes"]):
        return None
    reduced = simplify(point,edges)
    if any(reduced["topology"][k]!=raw[k] for k in ("components","cycles")):
        return None
    return reduced["nodes"],reduced["arcs"],raw


def native(field,cut,folder,diagonal):
    bins = np.arange(field.shape[1])
    if diagonal=="opposite":
        bins = bins[::-1]
    pts,tris = clipped_mesh(field[:,bins].T,bins+.5,np.arange(len(field)),cut)
    if not len(tris):
        return [],[],dict(components=0,cycles=0), "empty"
    # Give degeneracies in time a consistent spatial tie order without perturbing the actual time field.
    order = np.lexsort((pts[:,1],pts[:,0]))
    old_to_new = np.argsort(order)
    pts,tris = pts[order],old_to_new[tris]
    for single in (True,False):
        result = solve_mesh(pts,tris,folder,single)
        if result is not None:
            return (*result,"single" if single else "dual")
    # Independent components have disjoint Reeb graphs. Retry each mesh component separately.
    edges = coo_matrix((np.ones(tris.size),(tris.ravel(),np.roll(tris,1,axis=1).ravel())),shape=(len(pts),len(pts)))
    _, labels = connected_components(edges,directed=False)
    nodes,arcs = [],[]
    components = cycles = 0
    for tag in np.unique(labels[tris[:,0]]):
        rows = tris[labels[tris[:,0]]==tag]
        used = np.unique(rows)
        part = np.searchsorted(used,rows)
        result = solve_mesh(pts[used],part,folder,True)
        if result is None:
            result = solve_mesh(pts[used],part,folder,False)
        if result is None:
            return [],[],dict(components=np.nan,cycles=np.nan),"failed_topology_check"
        local,local_arcs,topology = result
        ids = {n["id"]:len(nodes)+j for j,n in enumerate(local)}
        nodes.extend(dict(n,id=ids[n["id"]]) for n in local)
        arcs.extend(dict(a,source=ids[a["source"]],target=ids[a["target"]]) for a in local_arcs)
        components += topology["components"]
        cycles += topology["cycles"]
    return nodes,arcs,dict(components=components,cycles=cycles),"separate_components"


def measure(job):
    field,side,start,kind,diagonal = job
    cut = CUTS.loc[.9,side]
    with tempfile.TemporaryDirectory() as tmp:
        nodes,arcs,topology,method = native(field,cut,tmp,diagonal)
    interior = [n for n in nodes if 1e-6<n["time"]<len(field)-1-1e-6]
    _,sampled = graph_edges(field>=cut)
    row = dict(sample=kind,side=side,diagonal=diagonal,verification=method,start_utc=utc(start+1).isoformat(),seconds=len(field)-1,
               components=topology["components"],cycles=topology["cycles"],
               native_splits=sum(n["out_degree"]>1 for n in interior), native_merges=sum(n["in_degree"]>1 for n in interior),
               native_births=sum(n["in_degree"]==0 for n in interior), native_deaths=sum(n["out_degree"]==0 for n in interior),
               sampled_splits=sampled["splits"],sampled_deaths=sampled["deaths"])
    if method=="failed_topology_check":
        for key in ("native_splits","native_merges","native_births","native_deaths"):
            row[key] = np.nan
    return row,nodes,arcs


def example_figure(field,example,start,nodes):
    # Attribute native splits by time and source coordinate. Native interpolation can move a split off a clock boundary.
    t = example["t"]
    lo,hi = example["parent"]
    offset = t-start
    within = [n for n in nodes if n["out_degree"]>1 and offset-1-1e-5<=n["time"]<=offset+1e-5
              and lo<=n["price"]<=hi]
    return [dict(utc=(utc(start+1)+pd.Timedelta(seconds=float(n["time"]))).isoformat(),
                 distance_bp=n["price"],time_s=n["time"],in_degree=n["in_degree"],out_degree=n["out_degree"]) for n in within]


def draw(example,grid):
    s = SIDES.index(example["side"])
    t = example["t"]
    fig,(ax,bx) = plt.subplots(1,2,figsize=(10.5,4),layout="constrained")
    bins = np.arange(max(0,example["parent"][0]-2),min(25,example["parent"][1]+2))
    cut = example["cutoff"]/1e6
    for row,color in [(t-1,"#216c80"),(t,"#984324")]:
        ax.plot(bins+.5,grid[row,s,bins]/1e6,marker="o",label=utc(row+1).strftime("%H:%M:%S UTC"),color=color)
    ax.axhline(cut,color="#444",ls="--",label="High-depth cutoff")
    ax.set(xlabel="Bid distance from midpoint (bp)",ylabel="Displayed USD millions per bin",title="A. The middle bin falls below the cutoff")
    ax.legend(frameon=False,fontsize=8)
    # Exact same clipped and triangulated field used by TTK.
    field = grid[t-4:t+5,s,bins].T / 1e6
    x,y = np.meshgrid(np.arange(-4,5),bins+.5)
    triangles = []
    stride = x.shape[1]
    for j in range(x.shape[0]-1):
        for i in range(stride-1):
            a = j*stride+i
            triangles.extend([[a,a+1,a+stride+1],[a,a+stride+1,a+stride]])
    bx.tricontourf(x.ravel(),y.ravel(),triangles,field.ravel(),levels=[cut,field.max()+1],colors=["#76a8b2"])
    bx.tricontour(x.ravel(),y.ravel(),triangles,field.ravel(),levels=[cut],colors=["#245265"],linewidths=.85)
    for n in example["native_splits_in_transition"]:
        when = (pd.Timestamp(n["utc"])-utc(t+1)).total_seconds()
        bx.scatter(when,n["distance_bp"],s=55,marker="X",color="#a03c1d",label="Native Reeb split",zorder=3)
    bx.set(xlabel="Seconds relative to "+utc(t+1).strftime("%H:%M:%S UTC"),ylabel="Bid distance from midpoint (bp)",
           title="B. Connected region above threshold")
    if example["native_splits_in_transition"]:
        bx.legend(frameon=False,fontsize=8)
    for a in (ax,bx):
        a.spines[["top","right"]].set_visible(False)
    fig.savefig(OUT/"reeb_split.png",dpi=180)
    plt.close(fig)


def main():
    with np.load(GRID_CACHE) as z:
        grid,valid = z["grid"],z["valid"]
    jobs = []
    for start in range(DAY-1,len(grid)-60,3600):
        if not valid[start:start+61].all():
            raise ValueError("Clock-selected window overlaps a gap")
        for s,side in enumerate(SIDES):
            for diagonal in ("original","opposite"):
                jobs.append((grid[start:start+61,s],side,start,"hour_start",diagonal))
    examples = json.loads((OUT/"split_examples.json").read_text())
    for e in examples:
        start = e["t"]-10
        for diagonal in ("original","opposite"):
            jobs.append((grid[start:start+21,SIDES.index(e["side"])],e["side"],start,"split_example",diagonal))
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for job,(row,nodes,arcs) in zip(jobs,pool.map(measure,jobs)):
            rows.append(row)
            field,side,start,kind,diagonal = job
            if kind=="split_example":
                e = next(x for x in examples if x["side"]==side)
                tagged = example_figure(field,e,start,nodes)
                if diagonal=="opposite":
                    e["opposite_diagonal_splits_in_transition"] = tagged
                    continue
                e["native_splits_in_transition"] = tagged
                e["native_graph_window_start_utc"] = utc(start+1).isoformat()
                e["native_nodes"] = nodes
                e["native_arcs"] = arcs
    pd.DataFrame(rows).to_csv(OUT/"native_reeb_windows.csv",index=False)
    (OUT/"native_split_examples.json").write_text(json.dumps(examples,indent=2)+"\n")
    draw(examples[0],grid)
    print(pd.DataFrame(rows).query("sample=='hour_start'").groupby(["diagonal","side"]).sum(numeric_only=True))


if __name__=="__main__":
    main()
