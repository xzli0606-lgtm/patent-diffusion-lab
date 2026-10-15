"""Generate public synthetic inputs through the same local PATSTAT adapter."""
import argparse
import copy
from pathlib import Path
import numpy as np
import pandas as pd
from .portable_config import DEFAULTS, write, digest


def generate(output,clusters=40,pairs_per_cluster=4,deterministic=False,missing_classification=False):
    out=Path(output); out.mkdir(parents=True,exist_ok=False)
    rng=np.random.default_rng(20261014)
    applications=[]; publications=[]; citations=[]; classifications=[]; roster=[]
    for cell in range(clusters):
        grant=pd.Timestamp('2010-01-01')+pd.DateOffset(months=cell*3)
        for pair in range(pairs_per_cluster):
            for group in ['A','B']:
                fid=f'F{cell:03}_{pair:03}_{group}'; aid='APP_'+fid; pub='PUB_'+fid
                applications.append({'appln_id':aid,'docdb_family_id':fid})
                publications.append({'pat_publn_id':pub,'appln_id':aid,'publn_date':str(grant.date()),'publn_auth':'US','publn_first_grant':'Y'})
                classifications.append({'appln_id':aid,'ipc_class_symbol':'A01B 1/00'})
                roster.append({'docdb_family_id':fid,'group':group,'primary_ipc_class_symbol':'A01B 1/00'})
                n=3 if deterministic else (int(rng.integers(1,8)) if rng.random()<(0.85 if group=='A' else .7) else 0)
                for j in range(n):
                    cf=f'C_{fid}_{j}'; ca='APP_'+cf; cp='PUB_'+cf
                    day=[10,30,120,400,700,1100,1500][j]
                    date=grant+pd.Timedelta(days=day)
                    applications.append({'appln_id':ca,'docdb_family_id':cf})
                    publications.append({'pat_publn_id':cp,'appln_id':ca,'publn_date':str(date.date()),'publn_auth':'EP','publn_first_grant':'N'})
                    citations.append({'pat_publn_id':cp,'cited_pat_publn_id':pub,'cited_appln_id':'0'})
                    fields=[2] if deterministic else list(rng.choice([1,2,3,4],size=int(rng.integers(1,3)),replace=False))
                    for field in fields: classifications.append({'appln_id':ca,'ipc_class_symbol':f'A01B {int(field)}/00'})
    # Relation-level examples: duplicate citation and a second granting office in one family.
    if citations: citations.append(dict(citations[0]))
    if missing_classification and citations:
        # One intentionally unmapped IPC must mark the entire citing-family set incomplete.
        citing_app=next(x['appln_id'] for x in publications if x['pat_publn_id']==citations[0]['pat_publn_id'])
        classifications.append({'appln_id':citing_app,'ipc_class_symbol':'A01B 99/00'})
    first=roster[0]['docdb_family_id']; applications.append({'appln_id':'OTHER_APP','docdb_family_id':first})
    publications.append({'pat_publn_id':'OTHER_PUB','appln_id':'OTHER_APP','publn_date':'2010-02-01','publn_auth':'EP','publn_first_grant':'Y'})
    classifications.append({'appln_id':'OTHER_APP','ipc_class_symbol':'A01B 1/00'})
    data={'applications':applications,'publications':publications,'citations':citations,'classifications':classifications,
          'mapping':[{'ipc_maingroup_symbol':f'A01B {i}/00','techn_field_nr':i} for i in range(1,5)],'roster':roster}
    specs={}
    for name,rows in data.items():
        p=out/(name+'.csv'); pd.DataFrame(rows).to_csv(p,index=False)
        specs[name]={'path':p.name,'sha256':digest(p)}
    manifest={'adapter_version':'patstat_local_v1','catalog_version':'5.25','dataset_kind':'synthetic','snapshot':'synthetic-v1-seed-20261014',
        'grant_office_scope':['US'],'cutoff':'2026-06-30','group_definition':'Artificial A and B labels; no research evidence',
        'classification_version':'Artificial four-main-group mapping for software testing, not official classification content',
        'export_completeness':'All artificially generated records are included','pregrant_policy':'exclude_records','invalid_date_policy':'stop','tables':specs}
    write(out/'manifest.json',manifest)
    c=copy.deepcopy(DEFAULTS); c['metadata']={'dataset':'synthetic tutorial'}
    c['comparison'].update(group_definition=manifest['group_definition'],cutoff=manifest['cutoff'],grant_office_scope=['US'])
    c['inputs'].update(source_manifest='prepared/source_manifest.json',classification_mapping_manifest='prepared/classification_mapping_manifest.json')
    c['execution']['mode']='smoke'
    write(out/'comparison.json',c)
    return out/'manifest.json',out/'comparison.json'


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--deterministic',action='store_true',help='Constant field-set precision fixture, not scientific evidence')
    parser.add_argument('--missing-classification',action='store_true',help='Include an unmapped IPC to exercise classification lineage and pair exclusion')
    a=parser.parse_args(); generate(a.output,deterministic=a.deterministic,missing_classification=a.missing_classification)


if __name__=='__main__': main()
