"""Synthetic mathematical illustrations for a literature review; no market backtest.

Run with the existing tda environment. Manual finite barcodes and hypothetical
correlation matrices illustrate preserved/lost information, not economic regimes.
"""
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/tda-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.sparse.csgraph import minimum_spanning_tree

OUT=Path(__file__).resolve().parent


def landscape(diagram,grid):
    tents=np.maximum(0,np.minimum(grid[None,:]-diagram[:,0,None],diagram[:,1,None]-grid[None,:]))
    return np.sort(tents,axis=0)[::-1]


def main():
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    a=np.array([[1.,4.],[2.,3.]])
    diagrams={'A':a,'Shifted':a+1.5,'Scaled':2*a}
    grid=np.linspace(0,10,20001);curves={name:landscape(d,grid) for name,d in diagrams.items()}
    metrics={}
    for name,d in diagrams.items():
        life=d[:,1]-d[:,0]
        norm1=np.trapezoid(curves[name].sum(axis=0),grid)
        norm2_squared=np.trapezoid((curves[name]**2).sum(axis=0),grid)
        assert np.isclose(norm1,(life**2).sum()/4,atol=1e-8)
        assert np.isclose(norm2_squared,(life**3).sum()/12,atol=1e-6)
        metrics[name]={'diagram':d.tolist(),'L1':float(norm1),'L2_squared':float(norm2_squared)}
    assert np.isclose(metrics['A']['L1'],metrics['Shifted']['L1'])
    assert np.isclose(metrics['Scaled']['L1'],4*metrics['A']['L1'])
    distance=np.sqrt(np.trapezoid(((curves['A']-curves['Shifted'])**2).sum(axis=0),grid))
    assert distance>0
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    ax=axes[0,0]
    for i,(b,d) in enumerate(a):
        ax.plot([b,d],[i+1,i+1],lw=6,color=['#247ba0','#d97706'][i],solid_capstyle='butt')
        ax.text((b+d)/2,i+1.16,f'birth {b:g}, death {d:g}; lifetime {d-b:g}',ha='center',fontsize=9)
    ax.set(xlim=(0,5),ylim=(.5,2.6),xlabel='Filtration distance scale (not calendar time)',yticks=[1,2],
        yticklabels=['Feature 1','Feature 2'],title='1. Finite persistence bars')
    ax=axes[0,1]
    for i,line in enumerate(curves['A']):ax.plot(grid,line,label=f'Landscape layer {i+1}',color=['#247ba0','#d97706'][i])
    ax.set(xlim=(0,5),xlabel='Filtration distance scale',ylabel='Tent height',title='2. Bars become ordered triangular functions')
    ax.legend()
    ax=axes[1,0]
    for name,color,style in [('A','#247ba0','-'),('Shifted','#9a4f96','--')]:
        for i,line in enumerate(curves[name]):
            ax.plot(grid,line,color=color,ls=style,label=f'{name}: L1 = {metrics[name]["L1"]:.1f}' if i==0 else None)
    ax.set(xlim=(0,7),xlabel='Filtration distance scale',ylabel='Landscape height',title='3. Same L1 norm, different full curves')
    ax.legend();ax.text(.02,.96,f'Full L2 landscape distance = {distance:.2f}',transform=ax.transAxes,va='top')
    ax=axes[1,1]
    for name,color in [('A','#247ba0'),('Scaled','#c0392b')]:
        for i,line in enumerate(curves[name]):
            ax.plot(grid,line,color=color,label=f'{name}: L1 = {metrics[name]["L1"]:.1f}' if i==0 else None)
    ax.set(xlim=(0,9),xlabel='Filtration distance scale',ylabel='Landscape height',title='4. Double every distance: L1 increases fourfold')
    ax.legend()
    for ax in axes.ravel():ax.grid(alpha=.2)
    fig.suptitle('Persistence landscapes: function, size summary, and change are different objects\nSynthetic finite diagrams only; these are not measured market states',fontsize=13)
    fig.savefig(OUT/'landscapes_explained.png',dpi=160,bbox_inches='tight');plt.close(fig)

    block=np.array([[1,.8,.2,.2],[.8,1,.2,.2],[.2,.2,1,.8],[.2,.2,.8,1.]])
    uniform=np.full((4,4),.4);np.fill_diagonal(uniform,1)
    corr={'Two groups':block,'Uniform links':uniform}
    positions=np.array([[-1,1],[-1,-1],[1,1],[1,-1]])
    fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    for col,(name,c) in enumerate(corr.items()):
        assert np.linalg.eigvalsh(c).min()>0
        assert np.isclose(c[np.triu_indices(4,1)].mean(),.4)
        d=np.sqrt(np.maximum(0,2*(1-c)))
        death=np.sort(minimum_spanning_tree(d).data)
        metrics[name]={'correlation':c.tolist(),'average_correlation':.4,'H0_merge_distances':death.tolist()}
        ax=axes[0,col]
        for i in range(4):
            for j in range(i+1,4):
                strong=c[i,j]>.6
                ax.plot(positions[[i,j],0],positions[[i,j],1],color='#247ba0' if strong else '#aeb6bf',
                    lw=5*c[i,j],alpha=.9 if strong else .6)
                mid=(positions[i]+positions[j])/2
                if (i,j)!=(1,2):ax.text(mid[0]+.05,mid[1]+.07,f'{c[i,j]:.1f}',fontsize=9)
        ax.scatter(positions[:,0],positions[:,1],s=550,color='#f2d7a6',edgecolor='#333',zorder=3)
        for i,label in enumerate('ABCD'):ax.text(*positions[i],label,ha='center',va='center',zorder=4)
        ax.set(title=name,xlim=(-1.6,1.6),ylim=(-1.5,1.5));ax.axis('off')
        ax=axes[1,col]
        ax.bar(np.arange(3),death,color='#247ba0' if col==0 else '#d97706')
        ax.set(xticks=np.arange(3),xticklabels=['1st merge','2nd merge','Final merge'],ylim=(0,1.5),
            ylabel='Correlation distance at H0 merge',title='Connectivity across all distance thresholds')
        ax.grid(axis='y',alpha=.2)
    fig.suptitle('Same hypothetical VIX = 24 and average correlation = 0.40; different stock relationships\nBoth matrices have equal per-stock variance. VIX is assigned context, not inferred from these matrices.',fontsize=12)
    fig.supxlabel('H0 merges equal minimum-spanning-tree edges. Ordinary covariance/network controls also distinguish these examples.',fontsize=9)
    fig.savefig(OUT/'vix_and_structure_explained.png',dpi=160,bbox_inches='tight');plt.close(fig)
    metrics['illustration_status']='Synthetic mathematical examples, no market data or predictive claim'
    metrics['shifted_full_landscape_L2_distance']=float(distance)
    (OUT/'illustration_checks.json').write_text(json.dumps(metrics,indent=2)+'\n')
    print('Synthetic landscape identities and correlation-matrix checks passed.')


if __name__=='__main__':main()
