"""Local PATSTAT relational export adapter, checked against EPO catalog v5.25."""
import json
import re
from pathlib import Path
import pandas as pd
from .portable_config import digest, write
from .portable_inputs import read_table, identifiers

CATALOG='https://link.epo.org/web/searching-for-patents/business/patstat/data-catalog-patsat-global-spring-en.pdf'
TABLES={
    'applications':['appln_id','docdb_family_id'],
    'publications':['pat_publn_id','appln_id','publn_date','publn_auth','publn_first_grant'],
    'citations':['pat_publn_id','cited_pat_publn_id','cited_appln_id'],
    'classifications':['appln_id','ipc_class_symbol'],
    'mapping':['ipc_maingroup_symbol','techn_field_nr'],
    'roster':['docdb_family_id','group','primary_ipc_class_symbol']}


def main_group(symbol):
    s=re.sub(r'\s+','',str(symbol)).upper()
    m=re.fullmatch(r'([A-H]\d{2}[A-Z])(\d+)/(\d+)',s)
    return m[1]+str(int(m[2]))+'/00' if m else None


def run(manifest,output):
    output=Path(output); path=Path(manifest)
    if output.exists(): raise FileExistsError('Output exists')
    output.mkdir(parents=True)
    audit={'status':'FAILED','tables':{},'excluded':{}}
    try:
        m=json.loads(path.read_text(encoding='utf-8'))
        allowed={'adapter_version','catalog_version','dataset_kind','snapshot','grant_office_scope','cutoff','group_definition','classification_version','export_completeness','pregrant_policy','invalid_date_policy','tables'}
        if set(m)-allowed: raise ValueError('Unknown adapter manifest keys')
        if m.get('adapter_version')!='patstat_local_v1' or m.get('catalog_version')!='5.25': raise ValueError('Adapter is verified against EPO catalog 5.25; other schemas need explicit verification')
        for k in ['snapshot','group_definition','classification_version','export_completeness']:
            if not isinstance(m.get(k),str) or not m[k].strip(): raise ValueError('Declare '+k)
        if m.get('dataset_kind') not in ['synthetic','researcher_supplied']: raise ValueError('Declare dataset_kind')
        if m.get('pregrant_policy') not in ['exclude_records','stop'] or m.get('invalid_date_policy') not in ['exclude_records','stop']: raise ValueError('Explicit pregrant and invalid-date policies required')
        if not isinstance(m.get('grant_office_scope'),list) or not m['grant_office_scope'] or any(not isinstance(x,str) or not re.fullmatch('[A-Z]{2}',x) for x in m['grant_office_scope']): raise ValueError('Grant office scope requires a list of two-letter office codes')
        cutoff=pd.Timestamp(m['cutoff'])
        if pd.isna(cutoff) or cutoff.tz is not None or cutoff!=cutoff.normalize(): raise ValueError('Calendar cutoff required')
        frames={}
        if set(m['tables'])!=set(TABLES): raise ValueError('All six local tables required')
        for name,required in TABLES.items():
            spec=m['tables'][name]
            if set(spec)-{'path','sha256','columns'}: raise ValueError('Unknown table specification')
            p=Path(spec['path']); p=p if p.is_absolute() else path.parent/p
            if digest(p)!=spec['sha256']: raise ValueError('Input hash mismatch: '+name)
            t=read_table(p,spec.get('columns',{})); t.columns=t.columns.str.lower()
            if t.columns.duplicated().any() or not set(required).issubset(t): raise ValueError('Required '+name+' fields: '+','.join(required))
            for col in [x for x in required if x.endswith('_id')]: t[col]=identifiers(t[col])
            frames[name]=t; audit['tables'][name]={'rows':len(t),'sha256':digest(p),'columns':list(t.columns)}
        a,p,c,cl,mp,ro=[frames[n] for n in ['applications','publications','citations','classifications','mapping','roster']]
        if a.appln_id.duplicated().any() or p.pat_publn_id.duplicated().any() or ro.docdb_family_id.duplicated().any(): raise ValueError('Duplicate application/publication/roster family identifier')
        if a[['appln_id','docdb_family_id']].eq('0').any().any(): raise ValueError('Dummy application/family IDs must be excluded explicitly upstream')
        fam=a.set_index('appln_id').docdb_family_id
        if not p.appln_id.isin(fam.index).all() or not cl.appln_id.isin(fam.index).all() or not ro.docdb_family_id.isin(a.docdb_family_id).all(): raise ValueError('Incomplete application/family export links')
        p=p.copy(); p['family_id']=p.appln_id.map(fam)
        p['date']=pd.to_datetime(p.publn_date,errors='coerce')
        invalid=p.date.isna()
        if (p.date.dropna()!=p.date.dropna().dt.normalize()).any() or p.date.dt.tz is not None: raise ValueError('Calendar publication dates required')
        audit['excluded']['invalid_publication_dates']=int(invalid.sum())
        if invalid.any() and m['invalid_date_policy']=='stop': raise ValueError('Invalid publication date, including PATSTAT 9999-12-31 sentinel')
        if not p.publn_first_grant.isin(['Y','N']).all(): raise ValueError('PUBLN_FIRST_GRANT must be Y/N')
        grants=p.loc[p.publn_first_grant.eq('Y')&p.publn_auth.isin(m['grant_office_scope'])&p.date.notna()&p.date.le(cutoff)]
        first=grants.groupby('family_id').date.min()
        if not ro.docdb_family_id.isin(first.index).all(): raise ValueError('Roster family lacks eligible dated grant in declared office scope')
        mp=mp.copy(); mp['main']=mp.ipc_maingroup_symbol.map(main_group)
        mp['techn_field_nr']=pd.to_numeric(mp.techn_field_nr,errors='raise')
        if mp.main.isna().any() or not (mp.techn_field_nr.between(1,35)&mp.techn_field_nr.mod(1).eq(0)).all(): raise ValueError('Invalid WIPO mapping')
        if mp.groupby('main').techn_field_nr.nunique().gt(1).any(): raise ValueError('Ambiguous main-group mapping')
        mapping=mp.drop_duplicates('main').set_index('main').techn_field_nr.astype(int)
        focal=ro.primary_ipc_class_symbol.map(main_group).map(mapping)
        if focal.isna().any(): raise ValueError('Roster primary IPC has no unique mapped field; no arbitrary fallback')
        f=pd.DataFrame({'family_id':ro.docdb_family_id,'group':ro.group.astype(str),'grant_date':ro.docdb_family_id.map(first),'focal_field':focal.astype(int)})
        if f.group.str.strip().eq('').any(): raise ValueError('Explicit group assignment required')
        cl=cl.copy(); cl['family_id']=cl.appln_id.map(fam); cl['main_group']=cl.ipc_class_symbol.map(main_group); cl['field']=cl.main_group.map(mapping)
        # Roster selection is a researcher decision, but the declared IPC must exist in the export.
        normalize=lambda x: re.sub(r'\s+','',str(x)).upper()
        actual=set(zip(cl.family_id,cl.ipc_class_symbol.map(normalize)))
        if any((fid,normalize(ipc)) not in actual for fid,ipc in zip(ro.docdb_family_id,ro.primary_ipc_class_symbol)):
            raise ValueError('Roster primary IPC is absent from its DOCDB family classification records')
        missing_families=set(cl.loc[cl.field.isna(),'family_id']) | (set(a.docdb_family_id)-set(cl.family_id))
        masks={fid:sum(1<<(int(x)-1) for x in sorted(set(g.field.dropna()))) for fid,g in cl.groupby('family_id')}
        for fid in missing_families: masks[fid]=0
        pub=p.set_index('pat_publn_id'); c=c.copy(); c['source_row']=range(len(c))
        if not c.pat_publn_id.isin(pub.index).all(): raise ValueError('Missing citing publication in export')
        cited_pub=c.cited_pat_publn_id.ne('0'); cited_app=c.cited_appln_id.ne('0')
        if not c.loc[cited_pub,'cited_pat_publn_id'].isin(pub.index).all() or not c.loc[~cited_pub&cited_app,'cited_appln_id'].isin(fam.index).all(): raise ValueError('Unresolved cited patent identifiers')
        c['family_id']=c.cited_pat_publn_id.map(pub.family_id)
        c.loc[~cited_pub,'family_id']=c.loc[~cited_pub,'cited_appln_id'].map(fam)
        both=cited_pub&cited_app
        if both.any() and not c.loc[both,'family_id'].eq(c.loc[both,'cited_appln_id'].map(fam)).all(): raise ValueError('Cited publication/application family conflict')
        c['citing_family_id']=c.pat_publn_id.map(pub.family_id); c['event_date']=c.pat_publn_id.map(pub.date)
        c['disposition']='eligible'
        c.loc[~c.family_id.isin(f.family_id),'disposition']='non_focal_or_nonpatent'
        c.loc[c.family_id.eq(c.citing_family_id),'disposition']='within_family'
        c.loc[c.event_date.isna(),'disposition']='invalid_date'
        c.loc[c.event_date.gt(cutoff),'disposition']='after_cutoff'
        pre=c.event_date.lt(c.family_id.map(first))&c.family_id.isin(f.family_id)
        if pre.any() and m['pregrant_policy']=='stop': raise ValueError('Pre-grant citation record')
        c.loc[pre,'disposition']='pregrant'
        audit['excluded'].update({k:int(v) for k,v in c.loc[c.disposition.ne('eligible'),'disposition'].value_counts().items()})
        good=c.loc[c.disposition.eq('eligible')].sort_values(['family_id','citing_family_id','event_date','pat_publn_id','source_row'])
        canonical=good.drop_duplicates(['family_id','citing_family_id'])
        c.loc[good.index,'disposition']='duplicate_later_or_tied'; c.loc[canonical.index,'disposition']='canonical'
        e=canonical[['family_id','citing_family_id','event_date']].copy()
        e['field_mask']=e.citing_family_id.map(masks).fillna(0).astype('uint64')
        e['classification_missing']=e.field_mask.eq(0)
        f=f.sort_values('family_id').reset_index(drop=True); e=e.sort_values(['family_id','citing_family_id']).reset_index(drop=True)
        f.to_parquet(output/'families.parquet',index=False); e.to_parquet(output/'events.parquet',index=False)
        c.to_csv(output/'citation_lineage.csv',index=False)
        grants.loc[grants.family_id.isin(f.family_id),['family_id','pat_publn_id','appln_id','publn_auth','date']].to_csv(output/'grant_lineage.csv',index=False)
        cl.to_csv(output/'classification_lineage.csv',index=False)
        a.loc[a.docdb_family_id.isin(set(f.family_id)|set(e.citing_family_id))].to_csv(output/'family_lineage.csv',index=False)
        write(output/'source_manifest.json',{'dataset_kind':m['dataset_kind'],'source':'PATSTAT local exports; catalog 5.25 adapter',
            'snapshot':m['snapshot'],'family_definition':'DOCDB simple family','group_assignment':m['group_definition'],
            'classification_mapping':m['classification_version'],'grant_rule':'Earliest Y first-grant publication in '+','.join(m['grant_office_scope']),
            'grant_office_scope':m['grant_office_scope'],'cutoff':m['cutoff'],
            'export_completeness_declaration':m['export_completeness'],'pregrant_policy':m['pregrant_policy'],
            'invalid_date_policy':m['invalid_date_policy'],'limitations':'Completeness is researcher-declared, not certified by the adapter.'})
        write(output/'classification_mapping_manifest.json',{'source':CATALOG,'version':m['classification_version'],'mapping_sha256':audit['tables']['mapping']['sha256'],
            'rule':'IPC main-group exact join; whole DOCDB-family union; any unmapped IPC makes family classification incomplete'})
        audit.update(status='PREPARED',families=len(f),events=len(e),zero_citation_families=int((~f.family_id.isin(e.family_id)).sum()),
            duplicate_citation_records=len(good)-len(canonical),catalog=CATALOG,catalog_version='5.25',adapter_manifest_sha256=digest(path))
        write(output/'preparation_audit.json',audit)
        write(output/'output_manifest.json',{x.name:digest(x) for x in sorted(output.iterdir()) if x.is_file()})
        return audit
    except (ValueError,KeyError,TypeError,OSError) as exc:
        audit['error']=str(exc); write(output/'preparation_audit.json',audit); raise
