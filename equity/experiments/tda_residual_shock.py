"""Causal local residual-shock merge trees; no new trading policy. Run in tda."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/tda-mpl')
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[name]='1'
from pathlib import Path
import hashlib
import json
import time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.sparse.csgraph import connected_components
from equity_residual_backtest import construct

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).with_suffix('')
DATA=ROOT/'market_data/datasets/equity_daily_expanded_2016_2026-10-27'
CFG=json.loads((OUT/'specification.json').read_text())
CORE=CFG['ordinary_core'];GRAPH=CFG['ordinary_graph'];TDA=CFG['TDA'];FEATURES=CORE+GRAPH+TDA
MODELS={'CoreVIX':CORE,'GraphVIX':CORE+GRAPH,'GraphVIXTDA':FEATURES}
SEED=2026110507


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def project(y,x,w):
    xn=x/np.sqrt(np.mean(x*x,axis=0))
    beta=np.linalg.lstsq(np.sqrt(w)[:,None]*xn,np.sqrt(w)*y,rcond=None)[0]
    return y-xn@beta


def past_fit(history,market):
    design=np.c_[np.ones(len(market)),market]
    market_beta=np.linalg.lstsq(design,history,rcond=None)[0]
    residual=history-design@market_beta
    scale=np.maximum(residual.std(axis=0,ddof=1),.0001)
    standardized=(residual-residual.mean(axis=0))/scale
    _,s,vt=np.linalg.svd(standardized,full_matrices=False)
    exposure=np.c_[np.ones(history.shape[1]),market_beta[1],scale[:,None]*vt[:3].T]
    sigma=np.maximum(history.std(axis=0,ddof=1),.0001)
    corr=standardized.T@standardized/(len(history)-1)
    np.fill_diagonal(corr,1.)
    return exposure,sigma,corr,float(s[0]**2/np.sum(s*s))


def graph_from_corr(corr):
    n=len(corr);a=np.zeros((n,n),dtype=bool)
    for i in range(n):
        peers=np.flatnonzero((corr[i]>0)&(np.arange(n)!=i))
        order=np.lexsort((peers,-corr[i,peers]))
        a[i,peers[order[:5]]]=True
    return a|a.T


def merge_tree(severity,adj):
    """Superlevel H0 elder rule, local owners, components immediately before death."""
    n=len(severity);parent=np.arange(n);size=np.ones(n,dtype=int)
    active=np.zeros(n,dtype=bool);owner=np.full(n,-1,dtype=int)
    birth=severity.copy();death=np.zeros(n);support=np.zeros(n,dtype=int)
    censored=np.zeros(n,dtype=bool);born=np.zeros(n,dtype=bool)
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    order=np.lexsort((np.arange(n),-severity))
    for i in order:
        if severity[i]<=0:break
        roots={find(j) for j in np.flatnonzero(adj[i]&active)}
        if not roots:
            born[i]=True;owner[i]=i;active[i]=True
            continue
        elder=min(roots,key=lambda r:(-birth[r],r))
        # Kill every younger component before adding the new saddle vertex.
        for r in sorted(roots):
            if r!=elder:
                death[r]=severity[i];support[r]=size[r]
                parent[r]=elder;size[elder]+=size[r]
        parent[i]=elder;size[elder]+=1;owner[i]=elder;active[i]=True
    for r in np.flatnonzero(born):
        if find(r)==r:
            support[r]=size[r];censored[r]=True
    prominence=np.zeros(n);fraction=np.zeros(n)
    ok=owner>=0
    prominence[ok]=birth[owner[ok]]-death[owner[ok]]
    fraction[ok]=support[owner[ok]]/n
    bars=pd.DataFrame({'peak':np.flatnonzero(born),'birth':birth[born],'death':death[born],
        'support':support[born],'zero_censored':censored[born]})
    return prominence,fraction,owner,bars


def topology(z,adj):
    values=np.zeros((len(z),2));owners=np.full(len(z),-1,dtype=int);bars=[]
    for sign in [-1,1]:
        a,b,o,table=merge_tree(np.maximum(sign*z,0),adj)
        take=sign*z>0;values[take]=np.c_[a,b][take];owners[take]=o[take]
        table['sign']=sign;bars.append(table)
    return values,owners,pd.concat(bars,ignore_index=True)


def controls():
    # Same shock histogram on a fixed chain; no outcome data involved.
    a=np.zeros((6,6),dtype=bool)
    for i in range(5):a[i,i+1]=a[i+1,i]=True
    connected=np.array([3.,2.8,2.6,.2,.1,.05])
    separated=np.array([3.,.2,2.8,.1,2.6,.05])
    records=[]
    for label,q in [('connected',connected),('separated',separated)]:
        p,s,o,b=merge_tree(q,a)
        assert np.all(p>=0) and np.all(s<=1)
        p2,s2,_,_=merge_tree(q*7,a)
        assert np.allclose(p2,p*7) and np.allclose(s2,s)
        perm=np.array([3,0,5,1,4,2]);pp,ss,_,_=merge_tree(q[perm],a[np.ix_(perm,perm)])
        assert np.allclose(pp,p[perm]) and np.allclose(ss,s[perm])
        tv,_,_=topology(q,a);flipped,_,_=topology(-q,a)
        assert np.allclose(tv,flipped)
        records.append({'case':label,'births':len(b),'positive_lifetimes':int((b.birth>b.death).sum()),
            'total_prominence':float((b.birth-b.death).sum()),'same_histogram':True})
    assert records[0]['total_prominence']!=records[1]['total_prominence']
    (OUT/'construction_checks.json').write_text(json.dumps({'passed':True,'cases':records,
        'sign_reflection':True,'stock_permutation_unique_severity':True,'amplitude_scaling':True,
        'root_zero_censor_explicit':True},indent=2)+'\n')
    fig,axes=plt.subplots(2,2,figsize=(10,5),layout='constrained')
    for row,(label,q) in enumerate([('Connected shocks',connected),('Separated shocks',separated)]):
        axes[row,0].plot(np.arange(6),q,'o-');axes[row,0].set(title=label,ylabel='Shock severity',xlabel='Vertex on fixed chain')
        b=merge_tree(q,a)[3]
        for j,v in enumerate(b.itertuples()):axes[row,1].plot([v.death,v.birth],[j,j],lw=4)
        axes[row,1].set(title='H0 branches; surviving root capped at zero',xlabel='Severity contrast, not time',ylabel='Branch')
    fig.suptitle('Synthetic control: identical shock histogram, different location on the same graph')
    fig.savefig(OUT/'01_construction_control.png',dpi=160);plt.close(fig)


def inputs():
    universe=pd.read_csv(DATA/'universe.csv').query("role == 'equity'").set_index('symbol')
    symbols=universe.index.to_numpy(dtype=str);sector=universe.sector_snapshot.to_numpy()
    panel=pd.read_csv(DATA/'returns_log.csv',index_col='date',parse_dates=True).iloc[1:]
    bars=pd.read_csv(DATA/'bars_raw.csv',parse_dates=['date'])
    prices={key:bars.pivot(index='date',columns='symbol',values=key).reindex(index=panel.index,columns=symbols).to_numpy() for key in ['o','c']}
    vix=pd.read_csv(ROOT/'market_data/datasets/mean_reversion_context_2026-11-04/vix_daily.csv').set_index('date').close
    old=pd.read_csv(ROOT/'equity/experiments/equity_efa_vs_pca/daily_gross_returns.csv').query("model == 'PCA3'").reset_index(drop=True)
    saved=np.load(ROOT/'equity/experiments/equity_efa_vs_pca/positions_and_loadings.npz')
    assert np.array_equal(symbols,saved['symbols'])
    return symbols,sector,panel,prices,vix,old,saved['holdings'][:,0]


def build_panel():
    symbols,sectors,panel,prices,vix,old,saved_positions=inputs()
    x=panel[symbols].to_numpy();market=panel.SPY.to_numpy();ts=np.arange(272,len(panel)-1)
    n=len(ts);m=len(symbols)
    feature=np.full((n,m,len(FEATURES)),np.nan);target=np.full((n,m),np.nan)
    position=np.zeros((n,m));owner=np.full((n,m),-1,dtype=np.int16)
    graph=np.zeros((n,m,m),dtype=bool);rows=[];all_bars=[];start=time.monotonic()
    max_position_error=0.;max_return_error=0.
    for d,t in enumerate(ts):
        idx=np.flatnonzero(np.isfinite(x[t-272:t]).all(axis=0));history=x[t-120:t,idx]
        X,sigma,corr,pc1=past_fit(history,market[t-120:t])
        w=1/sigma**2;h,e,_,_=construct(x[t,idx],X,w);z=e/sigma
        a=graph_from_corr(corr);tv,own,bt=topology(z,a)
        future=prices['c'][t+1,idx]/prices['o'][t+1,idx]-1
        relative=project(future,X,w);y=relative/sigma
        assert np.isfinite(y).all() and np.allclose(h@future,h@relative,atol=1e-12)
        expected=old.iloc[d]
        assert expected.signal_date==str(panel.index[t].date()) and expected.date==str(panel.index[t+1].date())
        err=float(abs(h@future-expected.gross_return));max_return_error=max(max_return_error,err)
        pe=float(np.max(abs(h-saved_positions[d,idx])));max_position_error=max(max_position_error,pe)
        assert err<1e-10 and pe<1e-9
        date=str(panel.index[t].date());prev=str(panel.index[t-1].date())
        vx=float(vix.loc[date]);vc=float(np.log(vx/vix.loc[prev]))
        sector_mean=np.zeros(len(idx));sector_abs=np.zeros(len(idx))
        for sec in np.unique(sectors[idx]):
            take=sectors[idx]==sec;sector_mean[take]=z[take].mean();sector_abs[take]=abs(z[take]).mean()
        trailing=old.loc[old.date.le(date)].tail(20).gross_return.to_numpy()*1e4
        assert len(trailing)==20 or d<20
        if len(trailing):tr_mean=trailing.mean();tr_risk=np.log(max(np.sqrt(np.mean(trailing**2)),1e-12))
        else:tr_mean=0.;tr_risk=0.
        # These early feature rows are training only; a past-observed neutral fallback avoids missing histories.
        degree=a.sum(axis=1);den=np.maximum(degree,1)
        cc=np.zeros(len(idx))
        for sign in [-1,1]:
            selected=np.flatnonzero(sign*z>=1)
            if len(selected):
                _,lab=connected_components(a[np.ix_(selected,selected)],directed=False)
                cc[selected]=np.bincount(lab)[lab]/len(idx)
        columns=[z,abs(z),sigma,sector_mean,sector_abs,np.full(len(idx),z.std()),
            np.full(len(idx),market[t-20:t].std(ddof=1)*np.sqrt(252)),
            np.full(len(idx),market[t-5:t].sum()),np.full(len(idx),pc1),
            np.full(len(idx),np.log(vx)),np.full(len(idx),vc),np.full(len(idx),int(20<=vx<30)),
            np.full(len(idx),tr_mean),np.full(len(idx),tr_risk),a@z/den,a@abs(z)/den,
            ((np.sign(z)[:,None]==np.sign(z)[None,:])*a).sum(axis=1)/den,
            (a*corr).sum(axis=1)/den,degree/len(idx),cc,tv[:,0],tv[:,1]]
        feature[d,idx]=np.column_stack(columns);target[d,idx]=y;position[d,idx]=h
        owner[d,idx]=np.where(own>=0,idx[np.maximum(own,0)],-1)
        graph[d][np.ix_(idx,idx)]=a
        bt['signal_date']=date;bt['peak_symbol']=symbols[idx[bt.peak.to_numpy()]]
        all_bars.append(bt.drop(columns='peak'))
        rows.append(dict(day=d,signal_index=t,signal_date=date,entry_date=str(panel.index[t+1].date()),
            history_end=prev,stocks=len(idx),period='development' if panel.index[t+1]<pd.Timestamp('2024-01-01') else 'later',
            edges=int(a.sum()/2),components=int(connected_components(a,directed=False)[0]),
            frozen_gross_return=float(h@future),signal_squared=float(z@z),cross_product=float(z@y),
            tda_mean_prominence=float(tv[:,0].mean()),tda_max_prominence=float(tv[:,0].max())))
        if (d+1)%300==0:print(f'Built {d+1}/{n} daily graphs in {time.monotonic()-start:.1f}s',flush=True)
    np.savez_compressed(OUT/'state_panel.npz',features=feature,target=target,positions=position,
        graph=graph,owner=owner,symbols=symbols,feature_names=np.array(FEATURES),signal_indices=ts)
    pd.DataFrame(rows).to_csv(OUT/'daily_context.csv',index=False)
    pd.concat(all_bars,ignore_index=True).to_csv(OUT/'merge_tree_bars.csv.gz',index=False)
    return {'source_dates':n,'stock_events':int(np.isfinite(target).sum()),'max_original_holdings_error':max_position_error,
        'max_original_return_error':max_return_error}


def design(f,columns):
    idx=[FEATURES.index(c) for c in columns];base=f[:,idx]
    return np.c_[base,base[:,1:]*base[:,0,None]]


def moment_fit(n,sx,sxx,sy,sxy):
    mu=sx/n;var=np.maximum(np.diag(sxx)/n-mu**2,0.)
    sd=np.sqrt(var);sd=np.where(sd>1e-10,sd,1.)
    cov=(sxx/n-np.outer(mu,mu))/np.outer(sd,sd)
    rhs=(sxy/n-mu[:,None]*sy[None,:]/n)/sd[:,None]
    beta=np.linalg.solve(cov+np.eye(len(mu)),rhs)
    return mu,sd,sy/n,beta


def forecast():
    data=np.load(OUT/'state_panel.npz');features=data['features'];target=data['target']
    context=pd.read_csv(OUT/'daily_context.csv')
    models=list(MODELS);n,m=target.shape
    predictions=np.full((n,m,len(models)+1,2),np.nan);diags=[]
    accum={}
    for model,cols in MODELS.items():
        p=len(cols)*2-1;accum[model]=[np.zeros(p),np.zeros((p,p)),np.zeros(2),np.zeros((p,2))]
    initial=features[:504,:,FEATURES.index('branch_prominence')]
    median=float(np.nanmedian(initial));fits={}
    for d in range(n):
        active=np.isfinite(target[d]);ys=np.c_[target[d,active],abs(target[d,active])]
        if d>=504:
            if (d-504)%20==0:
                for name,(sx,sxx,sy,sxy) in accum.items():
                    fits[name]=moment_fit(d,sx,sxx,sy,sxy)
                    diags.append(dict(prediction_start=d,model=name,training_dates=d,
                        training_stock_events=int(np.isfinite(target[:d]).sum()),
                        first_signal=context.iloc[d].signal_date,latest_training_execution=context.iloc[d-1].entry_date,
                        columns=len(sx)))
                # Exactly the same completed labels/refit schedule as feature models.
                baseline_abs=accum['CoreVIX'][2][1]/d
                assert context.iloc[d-1].entry_date<=context.iloc[d].signal_date
            predictions[d,active,0,0]=0.;predictions[d,active,0,1]=baseline_abs
            for j,(name,cols) in enumerate(MODELS.items(),1):
                mu,sd,intercept,beta=fits[name]
                predictions[d,active,j]=intercept+(design(features[d,active],cols)-mu)/sd@beta
        # Add today's labels only after predicting; they enter only a future refit.
        for name,cols in MODELS.items():
            x=design(features[d,active],cols);sx,sxx,sy,sxy=accum[name]
            sx+=x.mean(axis=0);sxx+=x.T@x/len(x);sy+=ys.mean(axis=0);sxy+=x.T@ys/len(x)
    np.savez_compressed(OUT/'stock_predictions.npz',predictions=predictions,models=np.array(['Baseline']+models),
        targets=np.array(['mean','absolute_move']))
    pd.DataFrame(diags).to_csv(OUT/'fit_diagnostics.csv',index=False)
    (OUT/'forecast_configuration.json').write_text(json.dumps({'models':{name:cols+['z_times_'+c for c in cols[1:]] for name,cols in MODELS.items()},
        'initial_training_dates':504,'refit_every_dates':20,'training_branch_prominence_median':median},indent=2)+'\n')
    return score(features,target,predictions,context,median)


def bootstrap_ix(n,pi):
    rng=np.random.default_rng(SEED+pi);starts=rng.integers(n,size=(1000,int(np.ceil(n/60))))
    return ((starts[:,:,None]+np.arange(60))%n).reshape(1000,-1)[:,:n]


def score(features,target,predictions,context,median):
    models=['Baseline']+list(MODELS);loss=[];metrics=[];paired=[];responses=[]
    for d in range(504,len(context)):
        active=np.isfinite(target[d]);z=features[d,active,0];y=target[d,active]
        topo=features[d,active,FEATURES.index('branch_prominence')]
        for j,model in enumerate(models):
            for k,tname in enumerate(['mean','absolute_move']):
                actual=y if k==0 else abs(y);pred=predictions[d,active,j,k]
                loss.append(dict(day=d,date=context.iloc[d].entry_date,period=context.iloc[d].period,
                    model=model,target=tname,stocks=int(active.sum()),MSE=float(np.mean((pred-actual)**2)),
                    MAE=float(np.mean(abs(pred-actual))),negative_forecasts=int((pred<0).sum()) if k else 0))
        for label,take in [('all',np.ones(len(z),dtype=bool)),('lower_prominence',topo<=median),('higher_prominence',topo>median)]:
            responses.append(dict(day=d,period=context.iloc[d].period,group=label,stocks=int(take.sum()),
                numerator=float(z[take]@y[take]),denominator=float(z[take]@z[take]),
                ordinary_numerator=float(z[take]@predictions[d,active,2,0][take]),
                tda_numerator=float(z[take]@predictions[d,active,3,0][take])))
    losses=pd.DataFrame(loss);response_daily=pd.DataFrame(responses)
    for pi,period in enumerate(['development','later']):
        days=sorted(losses.loc[losses.period==period,'day'].unique());ix=bootstrap_ix(len(days),pi)
        for target_name in ['mean','absolute_move']:
            subset=losses.loc[(losses.period==period)&(losses.target==target_name)]
            wide=subset.pivot(index='day',columns='model',values='MSE').loc[days]
            for model in models:
                g=subset.loc[subset.model==model]
                metrics.append(dict(period=period,target=target_name,model=model,dates=len(days),
                    stock_events=int(g.stocks.sum()),MSE=float(wide[model].mean()),MAE=float(g.MAE.mean()),
                    improvement_vs_GraphVIX_pct=float(100*(1-wide[model].mean()/wide.GraphVIX.mean())),
                    negative_forecasts=int(g.negative_forecasts.sum())))
            pairs=[('GraphVIX','CoreVIX'),('GraphVIXTDA','GraphVIX')]
            differences=np.column_stack([(wide[a]-wide[b]).to_numpy() for a,b in pairs])
            center=differences.mean(axis=0);boot=differences[ix].mean(axis=1);sd=boot.std(axis=0,ddof=1)
            critical=np.quantile(np.max(abs((boot-center)/np.maximum(sd,1e-15)),axis=1),.95)
            pointlow,pointhigh=np.quantile(boot,[.025,.975],axis=0)
            for j,(a,b) in enumerate(pairs):
                lo=center[j]-critical*sd[j];hi=center[j]+critical*sd[j];den=wide[b].mean()
                paired.append(dict(period=period,target=target_name,model=a,reference=b,dates=len(days),
                    loss_difference=center[j],point95_low=pointlow[j],point95_high=pointhigh[j],
                    simultaneous95_low=lo,simultaneous95_high=hi,improvement_pct=-center[j]/den*100,
                    improvement_low_pct=-hi/den*100,improvement_high_pct=-lo/den*100))
        for group in ['all','lower_prominence','higher_prominence']:
            g=response_daily.loc[(response_daily.period==period)&(response_daily.group==group)].set_index('day').loc[days]
            denominator=g.denominator.to_numpy();num=g.numerator.to_numpy()
            boot=num[ix].sum(axis=1)/denominator[ix].sum(axis=1);lo,hi=np.quantile(boot,[.025,.975])
            responses.append(dict(period=period,group=group,dates=len(days),stock_events=int(g.stocks.sum()),
                response_slope=num.sum()/denominator.sum(),point95_low=lo,point95_high=hi,
                ordinary_implied_slope=g.ordinary_numerator.sum()/denominator.sum(),
                tda_implied_slope=g.tda_numerator.sum()/denominator.sum()))
    # Only the appended aggregate dictionaries contain response_slope.
    aggregate=pd.DataFrame([r for r in responses if 'response_slope' in r])
    for name,frame in [('daily_losses',losses),('forecast_metrics',pd.DataFrame(metrics)),
        ('paired_comparisons',pd.DataFrame(paired)),('response_daily',response_daily),('response_summary',aggregate)]:
        frame.to_csv(OUT/(name+'.csv'),index=False)
    result=pd.DataFrame(paired);plot_results(result,aggregate)
    return {'forecast_dates':len(context)-504,'forecast_stock_events':int(np.isfinite(target[504:]).sum()),
        'scores':result.to_dict('records')}


def plot_results(comparisons,responses):
    fig,axes=plt.subplots(2,2,figsize=(11,6),layout='constrained')
    for row,period in enumerate(['development','later']):
        for col,target in enumerate(['mean','absolute_move']):
            ax=axes[row,col];g=comparisons.loc[(comparisons.period==period)&(comparisons.target==target)]
            for j,r in enumerate(g.itertuples()):
                ax.errorbar(r.improvement_pct,j,xerr=[[r.improvement_pct-r.improvement_low_pct],
                    [r.improvement_high_pct-r.improvement_pct]],fmt='o',capsize=4,color=['#777777','#247ba0'][j])
            ax.axvline(0,color='black',lw=.8);ax.set_yticks([0,1],['Peer graph beyond core + VIX','TDA beyond peer graph + VIX'])
            ax.set(title=f'{period}: {target}',xlabel='Reduction in squared forecast error (%)');ax.grid(axis='x',alpha=.2)
    fig.suptitle('Local residual-shock forecasts: paired 60-date block uncertainty\nSimultaneous two-comparison 95% intervals; no trading policy')
    fig.savefig(OUT/'02_incremental_forecasts.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    groups=['all','lower_prominence','higher_prominence']
    for ax,period in zip(axes,['development','later']):
        g=responses.loc[responses.period==period].set_index('group').loc[groups]
        ax.errorbar(np.arange(3),g.response_slope,yerr=[g.response_slope-g.point95_low,g.point95_high-g.response_slope],
            fmt='o',capsize=4,label='Observed response')
        ax.scatter(np.arange(3)-.06,g.ordinary_implied_slope,marker='x',label='Ordinary forecast')
        ax.scatter(np.arange(3)+.06,g.tda_implied_slope,marker='+',label='TDA forecast')
        ax.set_xticks(np.arange(3),['All','Lower prominence','Higher prominence'],rotation=15)
        ax.axhline(0,color='black',lw=.8);ax.set(title=period,ylabel='Slope of future relative return on current residual')
    axes[0].legend(fontsize=8)
    fig.suptitle('Descriptive signal response; negative means reversal\nTraining-fixed split; unadjusted groups do not establish an incremental effect')
    fig.savefig(OUT/'03_signal_response.png',dpi=160);plt.close(fig)


def real_examples():
    data=np.load(OUT/'state_panel.npz');context=pd.read_csv(OUT/'daily_context.csv')
    bars=pd.read_csv(OUT/'merge_tree_bars.csv.gz');examples=[]
    fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained')
    for row,date in enumerate(['2020-03-16','2024-08-05']):
        d=int(context.loc[context.signal_date==date,'day'].iloc[0]);ok=np.isfinite(data['target'][d])
        z=data['features'][d,ok,0];symbols=data['symbols'][ok];own=data['owner'][d,ok]
        g=bars.loc[(bars.signal_date==date)&(bars.sign==-1)].sort_values('birth',ascending=False)
        selected=np.argsort(z)[:12];ax=axes[row,0]
        ax.barh(np.arange(12),z[selected],color='#b85b72');ax.set_yticks(np.arange(12),symbols[selected]);ax.invert_yaxis()
        ax.set(title=f'{date}: most negative residuals',xlabel='Signal residual / prior total sigma')
        ax=axes[row,1]
        for j,r in enumerate(g.head(10).itertuples()):ax.plot([r.death,r.birth],[j,j],lw=4)
        ax.set_yticks(np.arange(min(10,len(g))),g.head(10).peak_symbol);ax.invert_yaxis()
        ax.set(title='Negative-shock H0 branches (largest births)',xlabel='Severity; death at zero is censored')
        for i in selected:
            original=np.flatnonzero(ok)[i];o=int(own[i]);examples.append(dict(signal_date=date,symbol=symbols[i],
                z=float(z[i]),branch_peak=str(data['symbols'][o]) if o>=0 else '',
                branch_prominence=float(data['features'][d,original,FEATURES.index('branch_prominence')]),
                branch_support_fraction=float(data['features'][d,original,FEATURES.index('branch_support_fraction')])))
    fig.suptitle('Fixed-date source examples: current shock geometry, selected without future outcomes')
    fig.savefig(OUT/'04_named_shock_examples.png',dpi=160);plt.close(fig)
    pd.DataFrame(examples).to_csv(OUT/'named_shock_examples.csv',index=False)


def main():
    protected=[DATA/name for name in ['returns_log.csv','bars_raw.csv','universe.csv']]+[
        ROOT/'market_data/datasets/mean_reversion_context_2026-11-04/vix_daily.csv',
        ROOT/'equity/experiments/equity_efa_vs_pca/daily_gross_returns.csv',
        ROOT/'equity/experiments/equity_efa_vs_pca/positions_and_loadings.npz',
        ROOT/'equity/experiments/tda_vix_matched/summary.json']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in protected}
    controls();summary=build_panel();summary.update(forecast());real_examples()
    for p in protected:assert sha(p)==hashes[str(p.relative_to(ROOT))]
    summary.update(protected_sha256=hashes,no_new_policy=True,original_strategy_unchanged=True,
        output_sha256={str(p.relative_to(ROOT)):sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in ['summary.json','README.md','audit.json']})
    summary['output_sha256'][str(Path(__file__).resolve().relative_to(ROOT))]=sha(Path(__file__))
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['protected_sha256','output_sha256']},indent=2),flush=True)


if __name__=='__main__':main()
