"""Two-group comparison with explicit meanings, matching and a shared milestone core."""
import hashlib
import html
import json
from pathlib import Path
import numpy as np
import pandas as pd
from . import _study
from .study import window_frame
from .reproduce import write


def read_table(path):
    path=Path(path)
    if path.suffix.lower()=='.parquet': return pd.read_parquet(path)
    if path.suffix.lower()=='.csv': return pd.read_csv(path,keep_default_na=False)
    raise ValueError('Use CSV or Parquet inputs')


def prepare(families,edges,config):
    f=read_table(families).rename(columns=config.get('family_columns',{}))
    e=read_table(edges).rename(columns=config.get('edge_columns',{}))
    required={'family_id','grant_date','focal_field','group'}
    if not required.issubset(f): raise ValueError('Family columns required: '+', '.join(sorted(required)))
    required_e={'family_id','citing_family_id','event_date','field_mask','classification_missing'}
    if not required_e.issubset(e): raise ValueError('Edge columns required: '+', '.join(sorted(required_e)))
    if config.get('comparison_type') not in {'country','technology','other'}: raise ValueError('Specify comparison_type')
    if not config.get('group_definition','').strip(): raise ValueError('Explain the meaning/source of the group labels')
    if config.get('comparison_type')=='country' and config.get('country_basis') not in {'applicant','inventor','priority','grant_office','other_explicit'}:
        raise ValueError('Country basis must be explicit')
    groups=config.get('groups',[])
    if len(groups)!=2 or groups[0]==groups[1]: raise ValueError('Specify two different group labels; result is first minus second')
    if f.family_id.isna().any() or f.family_id.astype(str).eq('').any() or f.family_id.duplicated().any():
        raise ValueError('One unique row per patent family required; overlapping groups or duplicate jurisdictions must be resolved')
    f['family_id']=f.family_id.astype(str)
    if f.family_id.duplicated().any(): raise ValueError('Family identifiers collide after string normalization')
    if e[['family_id','citing_family_id']].isna().any().any(): raise ValueError('Missing edge identifiers')
    for col in ['family_id','citing_family_id']: e[col]=e[col].astype(str)
    if e[['family_id','citing_family_id','event_date']].isna().any().any() or e.citing_family_id.eq('').any(): raise ValueError('Missing edge identifiers/dates')
    if e.duplicated(['family_id','citing_family_id']).any() or e.family_id.eq(e.citing_family_id).any(): raise ValueError('Duplicate or within-family edge')
    if not e.family_id.isin(f.family_id).all(): raise ValueError('Unknown focal family in edges')
    f['grant_date']=pd.to_datetime(f.grant_date,errors='raise')
    e['event_date']=pd.to_datetime(e.event_date,errors='raise')
    cutoff=pd.Timestamp(config['cutoff'])
    for col in [f.grant_date,e.event_date]:
        if col.isna().any() or col.dt.tz is not None or not col.eq(col.dt.normalize()).all(): raise ValueError('Timezone-naive calendar dates required')
    if not (f.focal_field.between(1,35)&f.focal_field.mod(1).eq(0)).all(): raise ValueError('focal_field must use WIPO35 integers 1..35')
    if e.classification_missing.dtype!=bool:
        flags=e.classification_missing.astype(str).str.lower().map({'true':True,'false':False,'1':True,'0':False})
        if flags.isna().any(): raise ValueError('classification_missing must be boolean')
        e['classification_missing']=flags.astype(bool)
    mask=pd.to_numeric(e.field_mask,errors='coerce')
    valid=~e.classification_missing
    if not (mask[valid].notna()&mask[valid].between(1,(1<<35)-1)&mask[valid].mod(1).eq(0)).all(): raise ValueError('Classified masks must be nonzero 35-bit integers')
    e['field_mask']=mask.fillna(0).astype('uint64')
    if e.event_date.lt(e.family_id.map(f.set_index('family_id').grant_date)).any(): raise ValueError('Pre-grant event')
    if e.event_date.gt(cutoff).any(): raise ValueError('Events exceed configured data cutoff; supply the intended snapshot')
    if not all(type(x) is int and x>0 for x in config.get('windows',[])): raise ValueError('Positive integer-year windows required')
    if not config.get('windows'): raise ValueError('At least one window required')
    f['grant_quarter']=f.grant_date.dt.to_period('Q').astype(str)
    chosen=f.loc[f.group.isin(groups)].copy()
    excluded_other_groups=len(f)-len(chosen)
    fields=config.get('focal_fields')
    if fields: chosen=chosen.loc[chosen.focal_field.isin(fields)].copy()
    if chosen.group.isna().any(): raise ValueError('Missing group labels')
    strata=config.get('matching_columns',['grant_quarter','focal_field'])
    if 'focal_field' not in strata: raise ValueError('Same-field comparisons require focal_field in matching_columns')
    if not set(strata).issubset(chosen): raise ValueError('Unknown matching columns')
    if chosen[strata].isna().any().any() or chosen[strata].astype(str).eq('').any().any(): raise ValueError('Missing matching stratum')
    chosen['matching_cell']=chosen[strata].apply(lambda r:json.dumps(r.tolist(),ensure_ascii=False,default=str),axis=1)
    chosen['ai_indicator']=chosen.group.map({groups[0]:1,groups[1]:0})
    selected=[]; support=[]; seed=config.get('matching_seed',20260907)
    for cell,g in chosen.groupby('matching_cell',sort=True):
        sides=[]
        for indicator in [1,0]:
            rows=g.loc[g.ai_indicator.eq(indicator)].copy()
            rows['sort_key']=rows.family_id.map(lambda x:hashlib.sha256(f'{seed}|{x}'.encode()).hexdigest())
            sides.append(rows.sort_values(['sort_key','family_id']))
        n=min(map(len,sides))
        support.append({'stratum':cell,'group_a_candidates':len(sides[0]),'group_b_candidates':len(sides[1]),'matched_pairs':n})
        if n:
            a,b=sides[0].iloc[:n].copy(),sides[1].iloc[:n].copy()
            pairs=[hashlib.sha256((cell+'|'+x+'|'+z).encode()).hexdigest() for x,z in zip(a.family_id,b.family_id)]
            a['match_id']=pairs;b['match_id']=pairs
            selected.extend([a,b])
    if not selected: raise ValueError('No exact common-support pairs; no paired model was fitted')
    f=pd.concat(selected,ignore_index=True).drop(columns='sort_key')
    f=f.rename(columns={'family_id':'docdb_family_id','grant_date':'focus_grant_date','focal_field':'wipo35_field_nr'})
    # ai_indicator is an internal binary adapter only: output labels retain user group meanings.
    e=e.loc[e.family_id.isin(f.docdb_family_id)].rename(columns={'family_id':'focus_docdb_family_id','citing_family_id':'citing_docdb_family_id','event_date':'edge_event_date','field_mask':'citing_wipo35_mask','classification_missing':'citing_wipo35_missing'})
    e['focal_wipo35_field_nr']=e.focus_docdb_family_id.map(f.set_index('docdb_family_id').wipo35_field_nr)
    f['first_citation_date']=f.docdb_family_id.map(e.groupby('focus_docdb_family_id').edge_event_date.min())
    return f,e,{'strata':support,'other_group_rows_excluded':excluded_other_groups,'eligible_candidates':len(chosen),'matched_pairs':len(f)//2,'unmatched_families':len(chosen)-len(f),'unmatched_fraction':1-len(f)/len(chosen)}


def neutral(value):
    if isinstance(value,dict):
        import re
        return {re.sub(r'(?<![a-z])ai(?![a-z])','group_a',re.sub(r'(?<![a-z])nonai(?![a-z])','group_b',k)):neutral(v) for k,v in value.items()}
    if isinstance(value,list): return [neutral(v) for v in value]
    return value


def run(families,edges,config_path,output):
    from . import study
    output=Path(output)
    if output.exists(): raise FileExistsError('Output already exists')
    config=json.loads(Path(config_path).read_text(encoding='utf-8'))
    f,e,audit=prepare(families,edges,config)
    output.mkdir(parents=True)
    write(output/'configuration.json',config);write(output/'matching_audit.json',audit)
    pd.DataFrame(audit['strata']).to_csv(output/'matching_strata.csv',index=False)
    f.to_parquet(output/'matched_families.parquet',index=False)
    study.C={'citation_cutoff':config['cutoff']}
    results={}; rates=[]
    for y in config['windows']:
        s,b,eb,a=window_frame(f,e,y,check_global=False)
        if s.empty:
            results[str(y)]={'status':'NO_COMPLETE_PAIRS','audit':a};continue
        models={}
        for h,frame in [('H1',s),('H3',b),('H4',b),('H5',b)]:
            col=h.lower()
            if frame.empty:
                models[h]={'status':'NO_CLASSIFICATION_COMPLETE_PAIRS'};continue
            for indicator,name in [(1,config['groups'][0]),(0,config['groups'][1])]:
                g=frame.loc[frame.ai_indicator.eq(indicator),col]
                rates.append({'window_years':y,'milestone':h,'group':name,'events':int(g.sum()),'families':len(g),'incidence_pct':100*float(g.mean())})
            try: models[h]=neutral(_study.conditional_binary(frame,col,h))
            except (RuntimeError,ZeroDivisionError) as exc: models[h]={'status':'NOT_ESTIMABLE','reason':str(exc)}
        try: timing=neutral(_study.fit_cox(s,'first_citation_date','Entry time'))
        except (RuntimeError,ValueError,np.linalg.LinAlgError,ZeroDivisionError) as exc: timing={'status':'NOT_ESTIMABLE','reason':str(exc)}
        results[str(y)]={'status':'COMPUTED','audit':neutral(a),'incidence_models':models,'entry_timing':timing}
        b.to_parquet(output/f'milestones_{y}Y.parquet',index=False)
    write(output/'results.json',{'groups':config['groups'],'difference_direction':'first group minus second','windows':results,'reference_analysis':'Not requested by this generic command; paper reproduce includes pooled and alternative references','interpretation':'Observational comparison on exact common support'})
    pd.DataFrame(rates).to_csv(output/'incidence.csv',index=False)
    table=pd.DataFrame(rates).to_html(index=False,float_format=lambda v:f'{v:.3f}',escape=True)
    body=f'<html><meta charset="utf-8"><title>Patent citation comparison</title><style>body{{font:16px system-ui;max-width:1100px;margin:40px auto}}td,th{{padding:8px}}table{{border-collapse:collapse}}</style><h1>{html.escape(config["groups"][0])} / {html.escape(config["groups"][1])}</h1><p>{html.escape(config["group_definition"])}</p><p>Matched pairs: {len(f)//2:,}. Unmatched families: {audit["unmatched_families"]:,}. Different windows may use different cohorts. Incidence denominators appear below.</p>{table}<h2>Models and audits</h2><pre>{html.escape(json.dumps(results,indent=2,ensure_ascii=False))}</pre></html>'
    (output/'report.html').write_text(body,encoding='utf-8')
    return results
