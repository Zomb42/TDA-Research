"""Read native TTK Reeb outputs in tda and render attributed graph examples."""
import base64
from collections import Counter
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET
import zlib

os.environ.setdefault('MPLCONFIGDIR','/private/tmp/tda-archive-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent/'btc_archive_initial_2026_11_05'
DTYPES={'Float32':'f4','Float64':'f8','Int8':'i1','UInt8':'u1','Int32':'i4','UInt32':'u4','Int64':'i8','UInt64':'u8'}


def read_vtu(path):
    root=ET.parse(path).getroot();app=root.find('AppendedData')
    encoded=''.join((app.text or '').split())[1:] if app is not None else None
    endian='<' if root.get('byte_order')=='LittleEndian' else '>'
    header=np.dtype(endian+DTYPES[root.get('header_type','UInt32')]);size=header.itemsize
    def read(array):
        dtype=np.dtype(endian+DTYPES[array.get('type')])
        if array.get('format')=='ascii':data=np.fromstring(array.text or '',sep=' ',dtype=dtype)
        else:
            text=encoded[int(array.get('offset')):]
            first=base64.b64decode(text[:((size+2)//3)*4]);blocks=int(np.frombuffer(first[:size],dtype=header)[0])
            nchars=((size*(3+blocks)+2)//3)*4
            values=np.frombuffer(base64.b64decode(text[:nchars]),dtype=header)
            lengths=values[3:].astype(int);payload=base64.b64decode(text[nchars:nchars+((int(lengths.sum())+2)//3)*4])
            chunks=[];offset=0
            for length in lengths:
                chunks.append(zlib.decompress(payload[offset:offset+length]));offset+=length
            raw=b''.join(chunks)
            expected=(blocks-1)*int(values[1])+int(values[2]) if blocks else 0
            if len(raw)!=expected:raise ValueError('VTK block length differs')
            data=np.frombuffer(raw,dtype=dtype)
        components=int(array.get('NumberOfComponents','1'))
        return data.reshape((-1,components)) if components>1 else data
    result={}
    for group in ['PointData','CellData','Points','Cells']:
        result[group]={a.get('Name',group):read(a) for a in root.findall('.//Piece/'+group+'/DataArray')}
    return result


def graph_topology(n,edges):
    parent=list(range(n))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for a,b in edges:
        a,b=find(a),find(b)
        if a!=b:parent[b]=a
    components=len({find(i) for i in range(n)})
    return dict(nodes=n,arcs=len(edges),components=components,cycles=len(edges)-n+components)


def mesh_topology(data):
    triangles=data['Cells']['connectivity'].reshape((-1,3))
    used=np.unique(triangles);mapping={int(v):i for i,v in enumerate(used)}
    edges=set()
    for tri in triangles:
        for a,b in [(tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0])]:edges.add(tuple(sorted((mapping[int(a)],mapping[int(b)]))))
    connected=graph_topology(len(used),list(edges))
    euler=len(used)-len(edges)+len(triangles)
    return dict(components=connected['components'],holes=connected['components']-euler,
                vertices=len(used),edges=len(edges),triangles=len(triangles),euler_characteristic=euler)


def simplify(points,edges):
    parent=list(range(len(points)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for edge in edges:
        a,b=edge['source'],edge['target']
        if abs(points[a,0]-points[b,0])<1e-6:
            a,b=find(a),find(b)
            if a!=b:parent[b]=a
    groups={}
    for i in range(len(points)):groups.setdefault(find(i),[]).append(i)
    nodes={key:dict(id=key,time=float(points[value,0].mean()),price=float(points[value,1].mean()),members=value)
           for key,value in groups.items()}
    arcs=[]
    for edge in edges:
        a,b=find(edge['source']),find(edge['target'])
        if a==b:continue
        path=edge['path']
        if nodes[a]['time']>nodes[b]['time']:a,b=b,a;path=path[::-1]
        arcs.append(dict(source=a,target=b,path=path,raw_arc_ids=[edge['arc_id']]))
    # Degree-two suppression changes representation, not connectivity/cycle rank.
    while True:
        candidate=None
        for node in nodes:
            incoming=[i for i,e in enumerate(arcs) if e['target']==node]
            outgoing=[i for i,e in enumerate(arcs) if e['source']==node]
            if len(incoming)==len(outgoing)==1 and incoming[0]!=outgoing[0]:candidate=(node,incoming[0],outgoing[0]);break
        if candidate is None:break
        node,i,j=candidate;a,b=arcs[i],arcs[j]
        merged=dict(source=a['source'],target=b['target'],path=a['path']+b['path'][1:],raw_arc_ids=a['raw_arc_ids']+b['raw_arc_ids'])
        arcs=[e for k,e in enumerate(arcs) if k not in [i,j]]+[merged];del nodes[node]
    for node in nodes.values():
        incoming=sum(e['target']==node['id'] for e in arcs);outgoing=sum(e['source']==node['id'] for e in arcs)
        node.update(in_degree=incoming,out_degree=outgoing,
                    event='merge/split' if incoming>1 and outgoing>1 else 'merge' if incoming>1 else 'split' if outgoing>1 else 'start' if incoming==0 else 'end')
    ids={value:i for i,value in enumerate(nodes)}
    topology=graph_topology(len(nodes),[(ids[e['source']],ids[e['target']]) for e in arcs])
    return dict(nodes=list(nodes.values()),arcs=arcs,topology=topology)


def case_report(case):
    folder=BASE/'reeb'/case['name']
    nodes=read_vtu(folder/'graph_port_0.vtu');arcs=read_vtu(folder/'graph_port_1.vtu')
    seg=read_vtu(folder/'graph_port_2.vtu');domain=read_vtu(folder/'domain.vtu')
    points=arcs['Points']['Points'].astype(float);connect=arcs['Cells']['connectivity'];offsets=arcs['Cells']['offsets']
    if len(points)!=len(nodes['Points']['Points']):raise ValueError('Unexpected omitted/isolated skeleton nodes')
    edges=[];previous=0
    data=np.load(BASE/case['input']);dt=float(np.median(np.diff(data['time_seconds'])))
    segmentation=seg['PointData']['ArcId'];locations=seg['Points']['Points']
    for index,last in enumerate(offsets):
        ids=connect[previous:last];previous=last
        if len(ids)!=2:raise ValueError('Expected native unsampled skeleton arcs')
        a,b=map(int,ids);arc_id=int(arcs['CellData']['ArcId'][index])
        if points[a,0]>points[b,0]:a,b=b,a
        region=locations[segmentation==arc_id]
        region=region[(region[:,0]>points[a,0])&(region[:,0]<points[b,0])]
        path=[points[a,:2].tolist()]
        if len(region):
            bins=np.floor(region[:,0]/dt).astype(int)
            for bucket in sorted(set(bins)):
                local=region[bins==bucket]
                path.append(local[:,:2].mean(axis=0).tolist())
        path.append(points[b,:2].tolist())
        edges.append(dict(source=a,target=b,arc_id=arc_id,path=path))
    raw=graph_topology(len(points),[(e['source'],e['target']) for e in edges]);mesh=mesh_topology(domain)
    # For this planar domain and coordinate-time function, fibers are intervals.
    if raw['components']!=mesh['components'] or raw['cycles']!=mesh['holes']:
        raise ValueError(f"Reeb/domain topology mismatch in {case['name']}: {raw} / {mesh}")
    reduced=simplify(points,edges)
    if reduced['topology']['components']!=raw['components'] or reduced['topology']['cycles']!=raw['cycles']:
        raise ValueError('Zero-time contraction changed graph homology')
    result=dict(case=case,raw_topology=raw,domain_topology=mesh,display_graph=reduced,
                graph_method='Native ttkReebGraphCmd, time scalar on clipped PL superlevel density domain',
                display_reduction='Contract zero-time arcs and suppress directed 1-in/1-out nodes; parallel arcs retained',
                path_layout='Mean source-segmentation vertex coordinates within time bins; not order trajectories')
    (folder/'graph.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def draw(ax,case,result,thresholded=False):
    data=np.load(BASE/case['input']);z=data['density'];p=data['price_centers'];t=data['time_seconds']/60
    if case.get('control'):
        ax.imshow(z,origin='lower',aspect='auto',extent=[t.min(),t.max(),p.min(),p.max()],cmap='Greys',alpha=.4)
    else:
        image=ax.pcolormesh(t,p,np.maximum(z,1),shading='nearest',norm=LogNorm(vmin=1000,vmax=200000),cmap='magma')
        if not thresholded:plt.colorbar(image,ax=ax,label='Displayed USD notional / $1 price width',pad=.01)
        else:ax.contour(t,p,z,levels=[float(data['threshold'])],colors=['#00c9a7'],linewidths=.8)
    for edge in result['display_graph']['arcs']:
        path=np.asarray(edge['path']);ax.plot(path[:,0]/60,path[:,1],color='#45f1c2' if not case.get('control') else '#1f77b4',lw=1.4,alpha=.9)
    graph_nodes=result['display_graph']['nodes']
    if graph_nodes:
        xy=np.array([[n['time']/60,n['price']] for n in graph_nodes]);ax.scatter(xy[:,0],xy[:,1],s=13,c='#e9fff9',edgecolors='#087f68',lw=.6,zorder=5)
    topo=result['display_graph']['topology']
    label=case['name'] if case.get('control') else (case['side'].capitalize()+' side')
    ax.set_title(f"{label}: {topo['components']} connected region(s), {topo['cycles']} independent graph cycles",fontsize=10)
    ax.set_xlabel('Minutes from window start')
    ylabel='Distance from current midpoint (USD)' if case.get('coordinate') else 'Price (USD/BTC)'
    ax.set_ylabel(ylabel if not case.get('control') else 'Synthetic price coordinate')
    if not case.get('control') and not case.get('coordinate'):
        books=json.loads((BASE/'chosen_books.json').read_text())['books']
        mid=[(float(b['bid'][0][0])+float(b['ask'][0][0]))/2/.0001 for b in books]
        ax.plot(t,mid,ls='--',lw=1,color='white',alpha=.8,label='Perp midpoint')
        ax.legend(loc='upper right',fontsize=8)


def main():
    config=json.loads((BASE/'reeb_cases.json').read_text());results={};rows=[]
    for case in config['cases']:
        result=case_report(case);results[case['name']]=result
        row={k:case.get(k) for k in ['name','side','bin_usd','threshold','smoothing_price_usd','smoothing_time_seconds','control','coordinate','translation_control']}
        row.update(result['raw_topology']);row.update(display_nodes=result['display_graph']['topology']['nodes'],display_arcs=result['display_graph']['topology']['arcs'])
        rows.append(row);print(case['name'],result['raw_topology'],flush=True)
    expected={'control_one_band':(1,0),'control_two_bands':(2,0),'control_loop':(1,1)}
    for name,(components,cycles) in expected.items():
        actual=results[name]['raw_topology'];assert actual['components']==components and actual['cycles']==cycles
    pd.DataFrame(rows).to_csv(BASE/'reeb_sensitivity.csv',index=False)
    (BASE/'reeb_validation.json').write_text(json.dumps(dict(known_controls_passed=True,
        all_reeb_components_and_cycles_match_clipped_mesh_homology=True,
        all_display_reductions_preserve_components_and_cycles=True,case_count=len(results)),indent=2)+'\n')
    fig,axes=plt.subplots(2,1,figsize=(13,9),layout='constrained')
    for ax,name in zip(axes,['bid_bin10_threshold25000','ask_bin10_threshold25000']):
        case=results[name]['case'];draw(ax,case,results[name])
    fig.suptitle('Time-Reeb graphs of high displayed liquidity — 05:00–05:10 UTC\n10 USD price bins; 25,000 USD notional per 1 USD price width; centered smoothing',fontsize=12)
    fig.savefig(BASE/'02_liquidity_reeb_overlay.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(14,4),layout='constrained')
    for ax,name in zip(axes,expected):draw(ax,results[name]['case'],results[name])
    fig.suptitle('Known controls: one band, two separate bands, and a split–rejoin loop')
    fig.savefig(BASE/'03_reeb_controls.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(15,9),layout='constrained')
    for ax,name in zip(axes.ravel(),['bid_bin10_threshold25000','bid_midrelative_bin10_threshold25000',
                                    'ask_bin10_threshold25000','ask_translation_control_bin10_threshold25000']):
        draw(ax,results[name]['case'],results[name])
        if 'translation_control' in name:ax.set_title('Fixed ask profile shifted with the observed midpoint\n'+str(results[name]['raw_topology']['cycles'])+' cycles after binning and smoothing',fontsize=10)
    fig.suptitle('Coordinate and translation checks — identical density cutoff and smoothing scales',fontsize=13)
    fig.savefig(BASE/'04_coordinate_checks.png',dpi=150);plt.close(fig)
    shape={}
    for side in ['bid','ask']:
        shape[side]={}
        for label,name in [('absolute',side+'_bin10_threshold25000'),('relative',side+'_midrelative_bin10_threshold25000')]:
            x=np.load(BASE/(name+'.npz'))['density'];first=x[:,0]
            cosine=(x.T@first)/(np.linalg.norm(x,axis=0)*np.linalg.norm(first))
            shape[side][label+'_profile_cosine_to_first']=dict(median=float(np.median(cosine)),min=float(cosine.min()))
    (BASE/'coordinate_checks.json').write_text(json.dumps(shape,indent=2)+'\n')


if __name__=='__main__':main()
