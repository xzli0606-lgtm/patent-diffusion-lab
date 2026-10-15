"""Portable inference guards; does not alter frozen paper estimation."""
import math
import warnings
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.duration.hazard_regression import PHReg


def result(frame,method):
    sizes=frame.groupby('matching_cell').match_id.nunique()
    return {'status':'NOT_ESTIMABLE','reason_code':None,'estimate':None,'ci95':None,'p_value':None,
        'n_pairs':int(frame.match_id.nunique()),'n_events':0,'n_informative_pairs':0,
        'n_clusters_total':len(sizes),'n_clusters_effective':0,'convergence':None,'inference_method':method,
        'cluster_pair_counts':{'min':int(sizes.min()) if len(sizes) else 0,'median':float(sizes.median()) if len(sizes) else 0,'max':int(sizes.max()) if len(sizes) else 0}}


def normal_p(z):
    # Avoid reporting numerical underflow as a mathematically zero tail probability.
    return max(float(2*stats.norm.sf(abs(z))),float(np.nextafter(0.,1.)))


def finish(out,beta,se):
    out['estimate']=float(np.exp(beta)) if np.isfinite(beta) and abs(beta)<700 else None
    if out['estimate'] is None: out['reason_code']='NONFINITE_ESTIMATE'; return out
    if out['n_clusters_effective']<30: out['reason_code']='FEWER_THAN_30_EFFECTIVE_CLUSTERS'; return out
    if not np.isfinite(se) or se <= np.finfo(float).eps*max(1.,abs(beta))*32:
        out['reason_code']='DEGENERATE_COVARIANCE'; return out
    limits=np.array([beta-1.959963984540054*se,beta+1.959963984540054*se])
    if np.max(np.abs(limits))>=700: out['reason_code']='NONFINITE_INTERVAL'; return out
    out.update(status='OK',reason_code=None,ci95=np.exp(limits).tolist(),p_value=normal_p(beta/se),se_cluster=float(se))
    return out


def binary(frame,outcome):
    out=result(frame,'conditional_logit_matching_cell_clustered')
    out['n_events']=int(frame[outcome].sum())
    wide=frame.pivot(index='match_id',columns='ai_indicator',values=outcome)
    if frame.empty: out['reason_code']='EMPTY_SAMPLE'; return out
    rates=[float(frame.loc[frame.ai_indicator.eq(i),outcome].mean()) for i in [1,0]]
    out.update(group_a_rate=rates[0],group_b_rate=rates[1],difference_pp=100*(rates[0]-rates[1]))
    informative=wide.loc[wide[0].ne(wide[1])]
    b=int((informative[1]==1).sum()); d=len(informative)-b
    cells=frame.drop_duplicates('match_id').set_index('match_id').matching_cell.loc[informative.index]
    out.update(n_informative_pairs=len(informative),n_clusters_effective=int(cells.nunique()),discordant_a=b,discordant_b=d)
    if not b or not d: out['reason_code']='NO_FINITE_CONDITIONAL_OR'; return out
    beta=math.log(b/d); p=b/(b+d)
    score=informative[1].astype(float)-p
    cs=score.groupby(cells).sum(); bread=1/(len(informative)*p*(1-p))
    out['convergence']=True
    return finish(out,beta,float(bread*np.sqrt((cs**2).sum())))


def cox(frame):
    out=result(frame,'pair_stratified_cox_efron_matching_cell_clustered')
    if frame.empty: out['reason_code']='EMPTY_SAMPLE'; return out
    x=frame.sort_values(['match_id','ai_indicator']).reset_index(drop=True)
    event=x.first_citation_date.notna() & x.first_citation_date.le(x.horizon_end)
    out['n_events']=int(event.sum())
    if not event.any(): out['reason_code']='ZERO_EVENTS'; return out
    duration=(x.first_citation_date.where(event,x.horizon_end)-x.focus_grant_date).dt.days+1
    # At least one observed event while both pair members remain at risk is needed.
    minima=duration.groupby(x.match_id).transform('min')
    info=event & duration.eq(minima)
    out['n_informative_pairs']=int(x.loc[info,'match_id'].nunique())
    if not info.any(): out['reason_code']='NO_INFORMATIVE_RISK_SETS'; return out
    try:
        model=PHReg(duration.to_numpy(float),x[['ai_indicator']].to_numpy(float),status=event.to_numpy(int),strata=x.match_id.to_numpy(),ties='efron')
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always'); fit=model.fit(disp=False)
        if any('converg' in str(w.message).lower() for w in caught):
            out.update(reason_code='NONCONVERGENCE',convergence=False); return out
        beta=float(fit.params[0]); bread=float(np.asarray(fit.cov_params())[0,0])
        if not np.isfinite(beta) or not np.isfinite(bread) or bread<=0:
            out['reason_code']='NONFINITE_COVARIANCE'; return out
        sr=np.asarray(fit.score_residuals)[:,0]
        # Residuals can be undefined for strata without events; other nonfinite scores fail.
        event_strata=x.match_id.isin(x.loc[event,'match_id']).to_numpy()
        if (~np.isfinite(sr)&event_strata).any(): out['reason_code']='NONFINITE_EVENT_SCORE'; return out
        sr=np.nan_to_num(sr,nan=0.)
        cs=pd.Series(sr).groupby(x.matching_cell).sum()
        scale=max(float(np.abs(sr).sum()),1.)
        contributing=pd.Series(np.abs(sr)>np.finfo(float).eps*scale).groupby(x.matching_cell).any()
        out['n_clusters_effective']=int(contributing.sum()); out['convergence']=True
        out=finish(out,beta,float(bread*np.sqrt((cs**2).sum())))
        sch=np.asarray(fit.schoenfeld_residuals)[:,0]; ok=event.to_numpy()&np.isfinite(sch)
        if ok.sum()>=3 and np.std(sch[ok])>0 and np.std(duration[ok])>0:
            corr,p=stats.pearsonr(stats.rankdata(duration[ok]),sch[ok])
            out['ph_diagnostic']={'p_value':float(p),'correlation':float(corr),'violation':bool(p<.05)}
            if p<.05: out['interpretation_warning']='PH_VIOLATION_SINGLE_HR_REQUIRES_CAUTION'
        else: out['ph_diagnostic']={'p_value':None,'violation':None,'reason':'INSUFFICIENT_DIAGNOSTIC_VARIATION'}
        return out
    except (ValueError,RuntimeError,ZeroDivisionError,IndexError,np.linalg.LinAlgError,OverflowError) as exc:
        out.update(reason_code='FIT_FAILED_'+type(exc).__name__,convergence=False)
        return out


def cluster_bootstrap(values,cells,reps,seed):
    """Resample whole cells; ratio of sums preserves the pair-weighted estimand."""
    values=np.asarray(values,float); cells=np.asarray(cells)
    names,ix=np.unique(cells,return_inverse=True)
    if not len(names): return np.empty((0,values.shape[1])),0
    counts=np.bincount(ix); sums=np.zeros((len(names),values.shape[1]))
    np.add.at(sums,ix,values)
    rng=np.random.default_rng(seed); draws=np.empty((reps,values.shape[1]))
    for b in range(reps):
        sample=rng.integers(0,len(names),len(names))
        draws[b]=sums[sample].sum(axis=0)/counts[sample].sum()
    return draws,len(names)


def interval(draws,estimate,nclusters):
    if nclusters<30: return {'status':'NOT_ESTIMABLE','reason_code':'FEWER_THAN_30_EFFECTIVE_CLUSTERS','ci95_pp':None,'p_value':None}
    se=float(np.std(draws,ddof=1))
    if not np.isfinite(se) or se<=np.finfo(float).eps*max(1.,abs(estimate))*32:
        return {'status':'NOT_ESTIMABLE','reason_code':'DEGENERATE_BOOTSTRAP','ci95_pp':None,'p_value':None}
    return {'status':'OK','reason_code':None,'ci95_pp':(100*np.quantile(draws,[.025,.975])).tolist(),
            'bootstrap_se_pp':100*se,'p_value':normal_p(estimate/se)}


def holm_prespecified(items):
    vals=[1. if p is None else p for _,p in items]; n=len(vals); adjusted=[None]*n; running=0.
    for rank,i in enumerate(sorted(range(n),key=lambda i:vals[i])):
        running=max(running,min(1.,(n-rank)*vals[i]))
        if items[i][1] is not None: adjusted[i]=running
    return [{'test':name,'p_value':p,'holm_p_value':a,'family_size':n} for (name,p),a in zip(items,adjusted)]
