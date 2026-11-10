"""Actual TTK time-Reeb graphs of high displayed-liquidity regions.

Run in tda. Calls the existing compiled TTK executable, without installing VTK
or changing Python environments. The PL density superlevel domain is obtained
by clipping a consistently triangulated price/time grid at a stated threshold.
"""
import argparse
from pathlib import Path
import os
import subprocess
import json
import xml.etree.ElementTree as ET

import numpy as np

BASE=Path(__file__).resolve().parent/'btc_archive_initial_2026_11_05'


def clipped_mesh(field,prices,times,threshold):
    ny,nx=field.shape;values=field.ravel()
    raw=np.array([[t,p,0] for p in prices for t in times],float)
    points=[];cache={};triangles=[]
    def vertex(i):
        key=('v',i)
        if key not in cache:cache[key]=len(points);points.append(raw[i])
        return cache[key]
    def cut(i,j):
        if values[i]==threshold:return vertex(i)
        if values[j]==threshold:return vertex(j)
        key=('e',min(i,j),max(i,j))
        if key not in cache:
            w=(threshold-values[i])/(values[j]-values[i])
            cache[key]=len(points);points.append(raw[i]+w*(raw[j]-raw[i]))
        return cache[key]
    for y in range(ny-1):
        for x in range(nx-1):
            a=y*nx+x;b=a+1;c=a+nx;d=c+1
            for triangle in [(a,b,d),(a,d,c)]:
                polygon=[]
                for k,i in enumerate(triangle):
                    j=triangle[(k+1)%3];inside=values[i]>=threshold;next_inside=values[j]>=threshold
                    if inside:polygon.append(vertex(i))
                    if inside!=next_inside:polygon.append(cut(i,j))
                polygon=list(dict.fromkeys(polygon))
                for k in range(1,len(polygon)-1):
                    ids=[polygon[0],polygon[k],polygon[k+1]]
                    p0,p1,p2=(points[i] for i in ids)
                    area=(p1[0]-p0[0])*(p2[1]-p0[1])-(p1[1]-p0[1])*(p2[0]-p0[0])
                    if abs(area)>1e-12:triangles.append(ids)
    return np.asarray(points),np.asarray(triangles,dtype=int)


def write_vtu(path,points,triangles):
    root=ET.Element('VTKFile',type='UnstructuredGrid',version='0.1',byte_order='LittleEndian')
    grid=ET.SubElement(root,'UnstructuredGrid');piece=ET.SubElement(grid,'Piece',NumberOfPoints=str(len(points)),NumberOfCells=str(len(triangles)))
    data=ET.SubElement(piece,'PointData',Scalars='time')
    array=ET.SubElement(data,'DataArray',type='Float64',Name='time',format='ascii');array.text=' '.join(map(repr,points[:,0].tolist()))
    array=ET.SubElement(ET.SubElement(piece,'Points'),'DataArray',type='Float64',NumberOfComponents='3',format='ascii')
    array.text=' '.join(map(repr,points.ravel().tolist()))
    cells=ET.SubElement(piece,'Cells')
    for name,kind,values in [('connectivity','Int64',triangles.ravel()),('offsets','Int64',np.arange(1,len(triangles)+1)*3),('types','UInt8',np.full(len(triangles),5))]:
        arr=ET.SubElement(cells,'DataArray',type=kind,Name=name,format='ascii');arr.text=' '.join(map(str,values.tolist()))
    ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)


def native_environment():
    env=os.environ.copy();home=Path.home();runtime=home/'ttk-binary'
    env['DYLD_FRAMEWORK_PATH']='/opt/homebrew/Frameworks'
    env['DYLD_LIBRARY_PATH']=':'.join(str(p) for p in [runtime/'compat/graphviz-15.1.1/lib',runtime/'ttk-paraview/lib',runtime/'ttk/lib'])
    return env,runtime/'ttk/bin/ttkReebGraphCmd'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case');args=parser.parse_args()
    config=json.loads((BASE/'reeb_cases.json').read_text())
    cases=[c for c in config['cases'] if args.case is None or c['name']==args.case]
    env,binary=native_environment()
    for case in cases:
        data=np.load(BASE/case['input']);field=data['density'];threshold=float(data['threshold'])
        points,triangles=clipped_mesh(field,data['price_centers'],data['time_seconds'],threshold)
        out=BASE/'reeb'/case['name'];out.mkdir(parents=True,exist_ok=True)
        if not len(triangles):
            (out/'empty.json').write_text(json.dumps({'empty':True,'threshold':threshold})+'\n');continue
        input_path=out/'domain.vtu';write_vtu(input_path,points,triangles)
        command=[str(binary),'-i',str(input_path),'-a','time','-o',str(out/'graph'),'-t','1','-d','0','-s']
        with (out/'ttk.log').open('w') as log:
            result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
        print(case['name'],'mesh',len(points),'vertices',len(triangles),'triangles','exit',result.returncode,flush=True)
        if result.returncode:raise RuntimeError('TTK failed; see '+str(out/'ttk.log'))


if __name__=='__main__':main()
