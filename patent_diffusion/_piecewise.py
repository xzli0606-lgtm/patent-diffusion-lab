"""Study algorithms extracted for the local prototype; see PROVENANCE.json."""
import math
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.duration.hazard_regression import PHReg
Z975=1.959963984540054

def anniversary(d,years):
    x=d+pd.DateOffset(years=years)
    if d.month==2 and d.day==29 and x.month==3: x=x.replace(month=2,day=28)
    return x

def fit(frame,date_col,years,label):
    cuts=[x for x in (1,3,5) if x<=years]
    if len(cuts)<2:return {"status":"not_estimable_under_frozen_intervals","reason":"one interval in 1Y"}
    names=[]; prev=0
    for x in cuts:names.append(f"grant_to_{x}Y" if prev==0 else f"{prev}Y_to_{x}Y");prev=x
    rows=[]
    for r in frame[["match_id","matching_cell","ai_indicator","focus_grant_date","horizon_end",date_col]].itertuples(index=False,name=None):
        match,cell,ai,grant,end,event_date=r; observed=pd.notna(event_date) and event_date<=end; stop_date=event_date if observed else end; stop=(stop_date-grant).days+1
        bounds=[(anniversary(grant,x)-grant).days+1 for x in cuts]; start=0
        for idx,bound in enumerate(bounds):
            interval_end=min(stop,bound)
            if interval_end>start:
                cov=[0.0]*len(names);cov[idx]=float(ai);rows.append((match,cell,start,interval_end,int(observed and interval_end==stop),*cov))
            if stop<=bound:break
            start=bound
    split=pd.DataFrame(rows,columns=["match_id","matching_cell","entry","duration","event",*names])
    model=PHReg(split.duration.to_numpy(float),split[names].to_numpy(float),status=split.event.to_numpy(int),entry=split.entry.to_numpy(float),strata=split.match_id.astype(str).to_numpy(),ties="efron")
    result=model.fit(disp=False);beta=np.asarray(result.params,float);bread=np.asarray(result.cov_params(),float);score=np.asarray(result.score_residuals,float);nonfinite=int((~np.isfinite(score)).sum());score=np.where(np.isfinite(score),score,0)
    sf=pd.DataFrame(score,columns=names);sf["matching_cell"]=split.matching_cell.astype(str).to_numpy();cs=sf.groupby("matching_cell",observed=True)[names].sum().to_numpy();cov=bread@(cs.T@cs)@bread;se=np.sqrt(np.diag(cov)); intervals=[]
    for i,n in enumerate(names):
        z=beta[i]/se[i];intervals.append({"interval":n,"estimate":math.exp(beta[i]),"se_cluster":se[i],"ci95_low":math.exp(beta[i]-Z975*se[i]),"ci95_high":math.exp(beta[i]+Z975*se[i]),"p_two_sided":float(2*stats.norm.sf(abs(z)))})
    return {"status":"complete","label":label,"rows_split":len(split),"events":int(split.event.sum()),"score_residual_nonfinite_as_zero":nonfinite,"intervals":intervals}
