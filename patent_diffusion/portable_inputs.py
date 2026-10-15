"""Strict portable inputs, deterministic matching and window construction."""
import hashlib
import csv
import json
import re
from pathlib import Path
import numpy as np
import pandas as pd
from . import _study


def read_table(path, mapping=None):
    path=Path(path)
    if path.suffix.lower()=='.csv':
        with path.open(encoding='utf-8-sig',newline='') as stream: header=next(csv.reader(stream),[])
        if len(set(header))!=len(header): raise ValueError('Duplicate CSV header')
        frame=pd.read_csv(path,dtype=str,keep_default_na=False)
    elif path.suffix.lower()=='.parquet': frame=pd.read_parquet(path)
    else: raise ValueError('Use CSV or Parquet')
    mapping=mapping or {}
    if not set(mapping).issubset(frame): raise ValueError('Mapped source columns missing')
    frame=frame.rename(columns=mapping)
    if frame.columns.duplicated().any(): raise ValueError('Column map collision')
    return frame


def identifiers(series):
    def one(x):
        if pd.isna(x) or isinstance(x,(float,np.floating,bool,np.bool_)): raise ValueError('Missing/float identifier')
        if not isinstance(x,(str,int,np.integer)): raise ValueError('Identifier must be string or integer')
        s=str(x)
        if not s or s.strip()!=s or re.fullmatch(r'[+-]?(?:\d+\.\d*|\d*\.\d+|\d+[eE][+-]?\d+)',s):
            raise ValueError('Blank/whitespace/float-like identifier')
        return s
    return series.map(one).astype(str)


def dates(series):
    x=pd.to_datetime(series,errors='raise')
    if x.isna().any() or x.dt.tz is not None or not x.eq(x.dt.normalize()).all(): raise ValueError('Timezone-naive calendar dates required')
    return x


def load(families,edges,c):
    f=read_table(families,c['inputs']['family_columns']); e=read_table(edges,c['inputs']['edge_columns'])
    for table,cols in [(f,['family_id','grant_date','focal_field','group']),(e,['family_id','citing_family_id','event_date','field_mask','classification_missing'])]:
        if not set(cols).issubset(table): raise ValueError('Required columns: '+', '.join(cols))
    f['family_id']=identifiers(f.family_id)
    if f.family_id.duplicated().any(): raise ValueError('Duplicate focal family')
    for col in ['family_id','citing_family_id']: e[col]=identifiers(e[col])
    if e.duplicated(['family_id','citing_family_id']).any() or e.family_id.eq(e.citing_family_id).any(): raise ValueError('Duplicate or within-family edge')
    if not e.family_id.isin(f.family_id).all(): raise ValueError('Unknown focal family')
    f['grant_date']=dates(f.grant_date); e['event_date']=dates(e.event_date)
    f['focal_field']=pd.to_numeric(f.focal_field,errors='raise')
    if not (f.focal_field.between(1,35)&f.focal_field.mod(1).eq(0)).all(): raise ValueError('WIPO35 integer field 1..35 required')
    f['focal_field']=f.focal_field.astype(int)
    if f.group.isna().any() or f.group.astype(str).str.strip().eq('').any(): raise ValueError('Missing group label')
    f['group']=f.group.astype(str)
    flags=e.classification_missing.astype(str).str.lower().map({'true':True,'false':False,'1':True,'0':False})
    if flags.isna().any(): raise ValueError('Boolean classification_missing required')
    e['classification_missing']=flags.astype(bool)
    masks=pd.to_numeric(e.field_mask.replace('',0),errors='raise').fillna(0)
    if not (masks.between(0,2**35-1)&masks.mod(1).eq(0)).all() or (masks.eq(0)&~e.classification_missing).any(): raise ValueError('Invalid 35-bit field mask')
    if (masks.ne(0)&e.classification_missing).any(): raise ValueError('Missing classification must have empty mask')
    e['field_mask']=masks.astype('uint64')
    cutoff=pd.Timestamp(c['comparison']['cutoff'])
    if f.grant_date.gt(cutoff).any(): raise ValueError('Grant exceeds data cutoff')
    if e.event_date.lt(e.family_id.map(f.set_index('family_id').grant_date)).any(): raise ValueError('Pre-grant event')
    if e.event_date.gt(cutoff).any(): raise ValueError('Event exceeds data cutoff')
    f['grant_quarter']=f.grant_date.dt.to_period('Q').astype(str)
    return f,e


def match(f,e,c):
    groups=c['comparison']['groups']; columns=c['matching']['columns']
    chosen=f.loc[f.group.isin(groups)].copy()
    if not set(columns).issubset(chosen): raise ValueError('Missing matching column')
    if chosen[columns].isna().any().any() or chosen[columns].astype(str).apply(lambda x:x.str.strip().eq('')).any().any(): raise ValueError('Empty matching value')
    chosen['matching_cell']=chosen[columns].apply(lambda r:json.dumps(r.tolist(),ensure_ascii=False,default=str),axis=1)
    chosen['ai_indicator']=chosen.group.map({groups[0]:1,groups[1]:0})
    selected=[]; support=[]
    for cell,g in chosen.groupby('matching_cell',sort=True):
        sides=[]
        for indicator in [1,0]:
            z=g.loc[g.ai_indicator.eq(indicator)].copy()
            z['_sort']=z.family_id.map(lambda x:hashlib.sha256(f'{c["matching"]["seed"]}|{x}'.encode()).hexdigest())
            sides.append(z.sort_values(['_sort','family_id']))
        n=min(map(len,sides)); support.append({'cell':cell,'a_candidates':len(sides[0]),'b_candidates':len(sides[1]),'pairs':n})
        if n:
            a,b=[s.iloc[:n].copy() for s in sides]
            ids=[hashlib.sha256(json.dumps([cell,x,y],ensure_ascii=False).encode()).hexdigest() for x,y in zip(a.family_id,b.family_id)]
            a['match_id']=ids; b['match_id']=ids; selected.extend([a,b])
    f2=pd.concat(selected,ignore_index=True).drop(columns='_sort') if selected else chosen.assign(match_id=pd.Series(dtype=str)).iloc[:0]
    f2=f2.rename(columns={'family_id':'docdb_family_id','grant_date':'focus_grant_date','focal_field':'wipo35_field_nr'})
    f2=f2.sort_values(['match_id','ai_indicator']).reset_index(drop=True)
    e2=e.loc[e.family_id.isin(f2.docdb_family_id)].rename(columns={'family_id':'focus_docdb_family_id','citing_family_id':'citing_docdb_family_id','event_date':'edge_event_date','field_mask':'citing_wipo35_mask','classification_missing':'citing_wipo35_missing'}).copy()
    e2['focal_wipo35_field_nr']=e2.focus_docdb_family_id.map(f2.set_index('docdb_family_id').wipo35_field_nr).astype(int)
    e2=e2.sort_values(['focus_docdb_family_id','edge_event_date','citing_docdb_family_id']).reset_index(drop=True)
    audit={'candidate_counts':{g:int(chosen.group.eq(g).sum()) for g in groups},'other_group_rows_excluded':len(f)-len(chosen),
        'matched_pairs':len(f2)//2,'unmatched_families':len(chosen)-len(f2),
        'unmatched_fraction':1-len(f2)/len(chosen) if len(chosen) else None,'strata':support}
    return f2,e2,audit


def window(f,e,years,cutoff):
    eligible=(f.focus_grant_date+pd.DateOffset(years=years)).le(pd.Timestamp(cutoff))
    keep=eligible.groupby(f.match_id).all()
    s=f.loc[f.match_id.isin(keep.index[keep])].copy()
    s['horizon_end']=s.focus_grant_date+pd.DateOffset(years=years)
    end=s.set_index('docdb_family_id').horizon_end
    ew=e.loc[e.focus_docdb_family_id.isin(end.index)].copy()
    ew=ew.loc[ew.edge_event_date.le(ew.focus_docdb_family_id.map(end))].copy()
    counts=ew.groupby('focus_docdb_family_id').size()
    s['citation_count']=s.docdb_family_id.map(counts).fillna(0).astype(int)
    s['h1']=s.citation_count.gt(0).astype(int)
    s['first_citation_date']=pd.to_datetime(s.docdb_family_id.map(ew.groupby('focus_docdb_family_id').edge_event_date.min()))
    missing=set(ew.loc[ew.citing_wipo35_missing,'focus_docdb_family_id'])
    bad=set(s.loc[s.docdb_family_id.isin(missing),'match_id'])
    base=s.loc[~s.match_id.isin(bad)].copy()
    eb=ew.loc[ew.focus_docdb_family_id.isin(base.docdb_family_id)].copy()
    milestones=_study.milestones(eb)
    base=base.merge(milestones,left_on='docdb_family_id',right_on='focus_docdb_family_id',how='left',validate='one_to_one')
    for h,col in [('h3','arrival_date'),('h4','establishment_date'),('h5','expansion_date')]:
        base[col]=pd.to_datetime(base[col]); base[h]=base[col].notna().astype(int)
    group=ew.focus_docdb_family_id.map(s.set_index('docdb_family_id').ai_indicator)
    coverage={str(i):1-float(ew.loc[group.eq(i),'citing_wipo35_missing'].mean()) if group.eq(i).any() else None for i in [0,1]}
    gap=abs(coverage['0']-coverage['1']) if all(v is not None for v in coverage.values()) else None
    # A no-edge group has no unclassified events; overall zero edges is a valid zero-rate case.
    quality=all(v is None or v>=.985 for v in coverage.values()) and (gap is None or gap<.01)
    audit={'complete_pairs':len(s)//2,'classification_complete_pairs':len(base)//2,'candidate_edges':len(ew),
        'coverage_by_group':coverage,'missing_rate_gap':gap,'field_quality_pass':quality,
        'no_candidate_edges':ew.empty,'unclassified_edges':int(ew.citing_wipo35_missing.sum()),
        'cohort_by_field_year':s.groupby(['wipo35_field_nr',s.focus_grant_date.dt.year,'group']).size().rename('families').reset_index().rename(columns={'wipo35_field_nr':'focal_field','focus_grant_date':'grant_year'}).to_dict('records')}
    return s,base,eb,audit
