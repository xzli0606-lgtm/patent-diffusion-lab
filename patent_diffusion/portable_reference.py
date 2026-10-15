"""Cross-fitted whole-field references under an explicit portable contract."""
import hashlib
import numpy as np
import pandas as pd
import numba as nb
from ._reference import outcomes
from .portable_models import cluster_bootstrap, interval


def seed(base,*parts):
    return int.from_bytes(hashlib.sha256('|'.join(map(str,(base,)+parts)).encode()).digest()[:4],'little')


@nb.njit
def score(offsets,days,masks,focal,rule):
    work=masks.copy()
    for i in range(len(focal)):
        bit=np.uint64(1)<<np.uint64(focal[i]-1)
        for j in range(offsets[i],offsets[i+1]):
            if rule==1 and (work[j] & (work[j]-np.uint64(1))) != 0: work[j]=0
            if rule==2 and (work[j] & bit) != 0: work[j]=0
    return outcomes(offsets,days,work,focal)


@nb.njit
def draw(offsets,days,focal,original,pool_id,starts,counts,donor_masks,cdf,rng_seed,rule):
    np.random.seed(rng_seed); masks=original.copy()
    for j in range(len(masks)):
        p=pool_id[j]
        if p<0: continue  # excluded target pair; this path never contributes to estimates
        lo=starts[p]; n=counts[p]; total=cdf[lo+n-1]
        u=np.random.random()*total
        k=np.searchsorted(cdf[lo:lo+n],u,side='right')
        masks[j]=donor_masks[lo+min(k,n-1)]
    return score(offsets,days,masks,focal,rule)


def plan(frame,edges,c,variant,years):
    r=c['reference']; f=frame.sort_values(['match_id','ai_indicator']).reset_index(drop=True)
    if not f.groupby('match_id').ai_indicator.apply(lambda x:x.tolist()==[0,1]).all(): raise ValueError('Reference requires sorted complete pairs')
    f['fold']=f.match_id.map(lambda x:seed(r['fold_seed'],x)%5)
    f['pair_pos']=np.arange(len(f))//2
    cell_names,cell_index=np.unique(f.matching_cell,return_inverse=True)
    f['cell_pos']=cell_index
    e=edges.copy(); meta=f.set_index('docdb_family_id')
    e['pos']=e.focus_docdb_family_id.map(pd.Series(np.arange(len(f)),index=f.docdb_family_id))
    e=e.sort_values(['pos','edge_event_date','citing_docdb_family_id']).reset_index(drop=True)
    for name,col in [('fold','fold'),('cell','cell_pos'),('ai','ai_indicator'),('pair','pair_pos')]: e[name]=e.focus_docdb_family_id.map(meta[col]).astype(int)
    e['focal']=e.focal_wipo35_field_nr.astype(int)
    grant=e.focus_docdb_family_id.map(meta.focus_grant_date)
    e['lag']=np.select([e.edge_event_date.le(grant+pd.DateOffset(years=1)),e.edge_event_date.le(grant+pd.DateOffset(years=3))],[0,1],2)
    e['calendar']=(e.edge_event_date.dt.year-r['calendar_anchor_year'])//r['calendar_block_years']
    e['cohort']=(grant.dt.year-r['grant_cohort_anchor_year'])//r['grant_cohort_block_years']
    extra=['cohort'] if variant=='additional_grant_cohort_stratum' else []
    levels=[['focal','lag','calendar']+extra,['focal','lag']+extra,['focal']+extra]
    pool_ids=np.full(len(e),-1,dtype=np.int64); pools=[]; audit=[]; level_counts={'exact':0,'no_calendar':0,'field':0,'unsupported':0}
    for fold in range(5):
        donors=e.loc[e.fold.ne(fold)]
        if variant=='group_b_only_donors': donors=donors.loc[donors.ai.eq(0)]
        dictionaries=[]
        for cols in levels:
            dictionaries.append({(key if isinstance(key,tuple) else (key,)):g.index.to_numpy() for key,g in donors.groupby(cols,sort=True)})
        cached={}
        for key,target in e.loc[e.fold.eq(fold)].groupby(levels[0],sort=True):
            chosen=None
            for level,cols in enumerate(levels):
                lookup=tuple(target.iloc[0][col] for col in cols); ix=dictionaries[level].get(lookup)
                if ix is not None and len(ix)>=r['minimum_donor_edges'] and e.loc[ix,'citing_docdb_family_id'].nunique()>=r['minimum_distinct_citing_families']:
                    chosen=(level,lookup,ix); break
            if chosen is None: level_counts['unsupported']+=len(target); continue
            level,key,ix=chosen; cachekey=(level,key)
            if cachekey not in cached:
                cached[cachekey]=len(pools); pools.append(ix)
                audit.append({'pool_id':len(pools)-1,'target_fold':fold,'level':['exact','no_calendar','field'][level],
                    'stratum':list(map(int,key)),'donor_edges':len(ix),'distinct_citing_families':int(e.loc[ix,'citing_docdb_family_id'].nunique()),
                    'donor_group_a_edges':int(e.loc[ix,'ai'].sum()),'donor_folds':sorted(map(int,e.loc[ix,'fold'].unique()))})
            pool_ids[target.index]=cached[cachekey]; level_counts[['exact','no_calendar','field'][level]]+=len(target)
    unsupported=set(e.loc[pool_ids<0,'pair'])
    valid=np.array([i not in unsupported for i in range(len(f)//2)],bool)
    offsets=np.zeros(len(f)+1,dtype=np.int64)
    offsets[1:]=np.cumsum(np.bincount(e.pos.to_numpy(int),minlength=len(f)))
    counts=np.array([len(ix) for ix in pools],dtype=np.int64)
    starts=np.r_[0,np.cumsum(counts)[:-1]].astype(np.int64) if len(counts) else np.empty(0,dtype=np.int64)
    donor_ix=np.concatenate(pools) if pools else np.empty(0,dtype=int)
    cdf=np.concatenate([np.arange(1,n+1,dtype=float) for n in counts]) if len(counts) else np.empty(0)
    p={'frame':f,'edges':e,'offsets':offsets,'days':(e.edge_event_date-pd.Timestamp('1970-01-01')).dt.days.to_numpy(np.int32),
       'focal':f.wipo35_field_nr.to_numpy(np.int16),'masks':e.citing_wipo35_mask.to_numpy(np.uint64),
       'pool_ids':pool_ids,'starts':starts,'counts':counts,'donor_ix':donor_ix,'cdf':cdf,'valid':valid,
       'pair_cells':f.iloc[::2].cell_pos.to_numpy(int),'cell_count':len(cell_names),
       'rule':1 if variant=='unique_field_event_rule' else 2 if variant=='cross_only_event_rule' else 0}
    p['donor_masks']=p['masks'][donor_ix]
    observed=score(offsets,p['days'],p['masks'],p['focal'],p['rule']).reshape(-1,2,3)
    p['observed']=observed[:,1].astype(float)-observed[:,0].astype(float)
    p['observed_group']=observed
    support={'pairs_before':len(valid),'pairs_retained':int(valid.sum()),'pairs_excluded':int((~valid).sum()),
        'families_excluded':int(2*(~valid).sum()),'unsupported_edges':int((pool_ids<0).sum()),
        'coverage':float(valid.mean()) if len(valid) else None,'levels':level_counts,'pools':audit,
        'citing_families_across_folds':int(e.groupby('citing_docdb_family_id').fold.nunique().gt(1).sum()),
        'independence_note':'Pair-fold exclusion does not remove all shared-citing-family dependence',
        'endpoint_rule':variant if p['rule'] else 'original', 'donor_rule':'group_b' if variant=='group_b_only_donors' else 'pooled'}
    p['support']=support
    return p


def simulate(p,rng_seed,cdf=None):
    return draw(p['offsets'],p['days'],p['focal'],p['masks'],p['pool_ids'],p['starts'],p['counts'],p['donor_masks'],p['cdf'] if cdf is None else cdf,rng_seed,p['rule']).reshape(-1,2,3)


def summarize(p,prob,c,reps,mcse,diagnostic=False):
    valid=p['valid']; obs=p['observed'][valid].mean(axis=0)
    pair_ref=prob[:,1]-prob[:,0]; ref=pair_ref[valid].mean(axis=0); residual=obs-ref
    pair_residual=p['observed']-pair_ref
    cells=p['pair_cells'][valid]; nclusters=len(np.unique(cells)); out={}
    draws=None
    if nclusters>=30 and not diagnostic:
        draws,_=cluster_bootstrap(pair_residual[valid],cells,c['reference']['inference']['bootstrap_replicates'],c['reference']['inference']['bootstrap_seed'])
    for k,h in enumerate(['H3','H4','H5']):
        inf=interval(draws[:,k],residual[k],nclusters) if draws is not None else {'status':'NOT_ESTIMABLE','reason_code':'SMOKE_DIAGNOSTIC' if diagnostic else 'FEWER_THAN_30_EFFECTIVE_CLUSTERS','ci95_pp':None,'p_value':None}
        if mcse[k]>.1:
            inf={'status':'PRECISION_NOT_MET','reason_code':'MCSE_LIMIT','ci95_pp':None,'p_value':None}
        out[h]={'group_a_observed_rate':float(p['observed_group'][valid,1,k].mean()),'group_b_observed_rate':float(p['observed_group'][valid,0,k].mean()),
            'group_a_reference_rate':float(prob[valid,1,k].mean()),'group_b_reference_rate':float(prob[valid,0,k].mean()),
            'observed_difference_pp':float(obs[k]*100),'reference_difference_pp':float(ref[k]*100),
            'residual_difference_pp':float(residual[k]*100),'mcse_pp':float(mcse[k]),'n_clusters_effective':nclusters,**inf}
    status='PRECISION_NOT_MET' if max(mcse[1:])>.1 else 'OK'
    return {'status':status,'diagnostic_only':diagnostic,'replicates':reps,'support':p['support'],'outcomes':out,
        'interval_scope':'conditional on estimated pools; matching-cell resampling; pair-weighted mean'},pair_ref


def run_variant(frame,edges,c,variant,years,progress=lambda **kw:None):
    p=plan(frame,edges,c,variant,years)
    if not p['valid'].any(): return {'status':'NO_REFERENCE_SUPPORT','support':p['support']},p,None
    smoke=c['execution']['mode']=='smoke'; cfg=c['reference']['simulation']
    maximum=50 if smoke else cfg['maximum']; initial=50 if smoke else cfg['initial']; increment=50 if smoke else cfg['increment']
    total=np.zeros((len(frame)//2,2,3)); diffs=[]; mcse=np.full(3,np.inf)
    for i in range(maximum):
        sim=simulate(p,seed(cfg['seed_base'],years,variant,i)); total+=sim
        diffs.append((sim[p['valid'],1].astype(float)-sim[p['valid'],0].astype(float)).mean(axis=0))
        n=i+1
        if n%100==0 or n==maximum: progress(stage='reference',variant=variant,window=years,completed=n,maximum=maximum)
        if n>=initial and (n-initial)%increment==0:
            mcse=np.std(diffs,axis=0,ddof=1)/np.sqrt(n)*100
            if max(mcse[1:])<=cfg['mcse_target_pp']: break
    res,pair_ref=summarize(p,total/n,c,n,mcse,smoke)
    return res,p,pair_ref


def weighted_cdf(p,weights):
    e=p['edges']; donor_weights=weights[e.iloc[p['donor_ix']].cell.to_numpy(int)]
    cdf=np.empty(len(donor_weights)); zero=[]
    for i,(start,n) in enumerate(zip(p['starts'],p['counts'])):
        seg=np.cumsum(donor_weights[start:start+n],dtype=float); cdf[start:start+n]=seg
        if not len(seg) or seg[-1]<=0: zero.append(i)
    # Only pools needed by positively weighted supported target pairs matter.
    use=p['valid'][e.pair.to_numpy(int)] & (weights[e.cell.to_numpy(int)]>0)
    active=set(p['pool_ids'][use]); failed=sorted(active.intersection(zero))
    return cdf,failed


def reweighted(p,c,years,progress=lambda **kw:None):
    valid=p['valid']; nclusters=len(np.unique(p['pair_cells'][valid]))
    if not valid.any(): return {'status':'NO_REFERENCE_SUPPORT'}
    if nclusters<30: return {'status':'NOT_ESTIMABLE','reason_code':'FEWER_THAN_30_EFFECTIVE_CLUSTERS','n_clusters_effective':nclusters}
    smoke=c['execution']['mode']=='smoke'; cfg=c['reference']['reweighted_pool']; inner=cfg['inner_simulation']
    B=200 if smoke else cfg['bootstrap_replicates']; max_inner=50 if smoke else inner['maximum']
    rng=np.random.default_rng(seed(cfg['bootstrap_seed'],years)); draws=[]; audit=[]
    for b in range(B):
        weights=np.bincount(rng.integers(0,p['cell_count'],p['cell_count']),minlength=p['cell_count'])
        pairw=weights[p['pair_cells']]*valid; denominator=pairw.sum()
        cdf,failed=weighted_cdf(p,weights)
        if denominator==0 or failed:
            return {'status':'NOT_ESTIMABLE','reason_code':'ZERO_WEIGHT_POOL_OR_TARGET','failed_draw':b,
                'zero_weight_pools':failed,'completed_draws':len(draws),'ci95_pp':None,'draw_audit':audit}
        # Inactive pools may have zero mass; exclude their events from this draw.
        temporary=dict(p); ids=p['pool_ids'].copy()
        e=p['edges']; active_targets=(pairw[e.pair.to_numpy(int)]>0)
        ids[~active_targets]=-1; temporary['pool_ids']=ids
        values=[]; mcse=np.full(3,np.inf)
        for j in range(max_inner):
            sim=simulate(temporary,seed(cfg['field_seed_base'],years,b,j),cdf)
            difference=p['observed']-(sim[:,1].astype(float)-sim[:,0].astype(float))
            values.append((difference*pairw[:,None]).sum(axis=0)/denominator)
            n=j+1
            if n>=inner['initial'] and (n-inner['initial'])%inner['increment']==0:
                mcse=np.std(values,axis=0,ddof=1)/np.sqrt(n)*100
                if max(mcse[1:])<=inner['mcse_target_pp']: break
        audit.append({'draw':b,'inner_replicates':n,'inner_mcse_pp':mcse.tolist()})
        if max(mcse[1:])>inner['mcse_target_pp']:
            return {'status':'PRECISION_NOT_MET','reason_code':'INNER_MCSE_LIMIT','failed_draw':b,'completed_draws':len(draws),'ci95_pp':None,'draw_audit':audit}
        draws.append(np.mean(values,axis=0)); progress(stage='reweighted',window=years,completed=b+1,maximum=B)
    a=np.asarray(draws)
    return {'status':'OK','diagnostic_only':smoke,'method':'reweighted_pool_fixed_support',
        'bootstrap_unit':'matching_cell','replicates':B,'n_clusters_effective':nclusters,'draw_audit':audit,
        'outcomes':{h:{'mean_residual_pp':float(a[:,k].mean()*100),**(interval(a[:,k],a[:,k].mean(),nclusters) if not smoke else {'status':'NOT_ESTIMABLE','reason_code':'SMOKE_DIAGNOSTIC','ci95_pp':None,'p_value':None})} for k,h in enumerate(['H3','H4','H5'])}}


def run_all(frame,edges,c,years,progress=lambda **kw:None):
    results={}; plans={}; refs={}
    for variant in ['main']+[v for v in c['reference']['sensitivities'] if v!='reweighted_pool_fixed_support']:
        res,p,ref=run_variant(frame,edges,c,variant,years,progress)
        results[variant]=res; plans[variant]=p; refs[variant]=ref
    if 'reweighted_pool_fixed_support' in c['reference']['sensitivities']:
        results['reweighted_pool_fixed_support']=reweighted(plans['main'],c,years,progress)
    intersection={}; main=plans['main']
    for name,p in plans.items():
        if name=='main' or refs[name] is None or refs['main'] is None: continue
        use=main['valid']&p['valid']; entries={}
        if use.any():
            for label,pp,rr in [('main',main,refs['main']),(name,p,refs[name])]:
                obs=pp['observed'][use].mean(axis=0); ref=rr[use].mean(axis=0)
                entries[label]={'observed_difference_pp':(100*obs).tolist(),'reference_difference_pp':(100*ref).tolist(),'residual_difference_pp':(100*(obs-ref)).tolist()}
        intersection[name]={'pairs':int(use.sum()),'outcomes_order':['H3','H4','H5'],'comparison':entries}
    results['intersection_support']=intersection
    return results
