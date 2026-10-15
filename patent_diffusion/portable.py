"""Auditable portable_v1 pipeline. Only local inputs; no paper-target readers."""
import hashlib
import copy
import html
import importlib.metadata
import json
import platform
import time
from pathlib import Path
import numpy as np
import pandas as pd
from . import __version__, _diagnostics
from .portable_config import resolve, contract, digest, write
from .portable_inputs import load, match, window
from .portable_models import binary, cox, holm_prespecified


def source_info(c,base):
    value=c['inputs'].get('source_manifest')
    if not value: raise ValueError('inputs.source_manifest required: document local data provenance')
    path=Path(value); path=path if path.is_absolute() else base/path
    manifest=json.loads(path.read_text(encoding='utf-8'))
    for key in ('dataset_kind','source','snapshot','family_definition','group_assignment','classification_mapping','grant_rule'):
        if not isinstance(manifest.get(key),str) or not manifest[key].strip(): raise ValueError('Source manifest requires '+key)
    if manifest['dataset_kind'] not in ('synthetic','researcher_supplied'): raise ValueError('Unknown dataset_kind')
    if manifest['family_definition']!='DOCDB simple family': raise ValueError('Only DOCDB simple family profile supported')
    if 'grant_office_scope' in manifest and set(manifest['grant_office_scope'])!=set(c['comparison']['grant_office_scope']):
        raise ValueError('Source grant office scope differs from comparison contract')
    if 'cutoff' in manifest and pd.Timestamp(manifest['cutoff'])<pd.Timestamp(c['comparison']['cutoff']):
        raise ValueError('Comparison cutoff exceeds declared source coverage')
    record={'source_manifest':{'sha256':digest(path),'dataset_kind':manifest['dataset_kind']},'declarations':manifest}
    mapping=c['inputs'].get('classification_mapping_manifest')
    if mapping:
        p=Path(mapping); p=p if p.is_absolute() else base/p
        record['classification_mapping_manifest']={'sha256':digest(p),'contents':json.loads(p.read_text(encoding='utf-8'))}
    return record


def frame_hash(frame):
    # Sorted, platform-neutral semantic input receipt; originals have separate byte hashes.
    return hashlib.sha256(frame.to_json(orient='split',date_format='iso',index=False).encode()).hexdigest()


def validate(families,edges,config):
    config=Path(config); c=resolve(json.loads(config.read_text(encoding='utf-8')))
    source_info(c,config.parent); f,e=load(families,edges,c); mf,me,audit=match(f,e,c)
    windows={str(y):window(mf,me,y,c['comparison']['cutoff'])[3] for y in c['comparison']['windows_years']}
    return {'status':'INPUTS_VALID','matching':audit,'windows':windows}


def describe(frame,col,groups):
    return [{'group':name,'events':int(frame.loc[frame.ai_indicator.eq(i),col].sum()),
        'families':int(frame.ai_indicator.eq(i).sum()),
        'incidence_pct':float(frame.loc[frame.ai_indicator.eq(i),col].mean()*100) if frame.ai_indicator.eq(i).any() else None}
        for i,name in [(1,groups[0]),(0,groups[1])]]


def render(output,result):
    rows=[]; lines=['# Patent Diffusion Lab portable comparison','',f'Status: {result["status"]}',
        f'Dataset: {result.get("dataset_kind","unknown")}',f'Mode: {result.get("mode","unknown")}',
        'Matched pairs: '+str(result.get('matching',{}).get('matched_pairs',0)),'',
        'Observational, pair-weighted comparisons. MCSE is simulation error, not sampling uncertainty.',
        'Incomplete/unsupported modules must not be interpreted as successful inference.','']
    for y,w in result.get('windows',{}).items():
        lines.extend([f'## {y}-year window',f'Status: {w["status"]}',json.dumps(w['sample_flow'],ensure_ascii=False),''])
        for h,rates in w.get('incidence',{}).items():
            for row in rates: rows.append({'window_years':int(y),'milestone':h,**row})
    pd.DataFrame(rows).to_csv(output/'incidence.csv',index=False)
    lines+=['## Models, references and limitations','```json',json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'```']
    (output/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    title='Patent Diffusion Lab — '+result['status']
    table=pd.DataFrame(rows).to_html(index=False,escape=True) if rows else '<p>No estimable cohort.</p>'
    body=f'<!doctype html><html lang="en"><meta charset="utf-8"><title>{html.escape(title)}</title><style>body{{font:16px system-ui;max-width:1100px;margin:40px auto}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}td,th{{padding:8px}}.status{{padding:16px;background:#fff0ca}}</style><h1>{html.escape(title)}</h1><p class="status">{html.escape(result.get("mode",""))} / {html.escape(result.get("dataset_kind",""))}. Inspect module limitations before using estimates. 查看模块限制后再使用估计。</p><p>Matched pairs: {result.get("matching",{}).get("matched_pairs",0)}. Observational comparisons; simulation MCSE is not sampling uncertainty.</p>{table}<h2>Audits, models and reference support</h2><pre>{html.escape(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))}</pre></html>'
    (output/'report.html').write_text(body,encoding='utf-8')


def run(families,edges,config,output,include_data=False):
    output=Path(output); config=Path(config)
    if output.exists(): raise FileExistsError('Output exists; use a new directory. Resume is not supported in portable_v1.')
    output.mkdir(parents=True); started=time.monotonic(); c=None
    code={p.name:digest(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
    def progress(**v): write(output/'progress.json',v)
    result={'status':'FAILED','windows':{},'publication_acceptance':'NOT_ESTABLISHED_BY_THIS_RUN'}
    try:
        c=resolve(json.loads(config.read_text(encoding='utf-8')))
        # Freeze resolved design before reading new-study outcomes.
        public_config=copy.deepcopy(c)
        for key in ['families','edges','source_manifest','classification_mapping_manifest']:
            if key in public_config['inputs']:
                public_config['inputs'][key]=key+('.parquet' if key in ['families','edges'] else '.json')
        write(output/'configuration.json',public_config); write(output/'method_contract.json',contract(public_config))
        progress(stage='validate')
        info=source_info(c,config.parent)
        write(output/'source_manifest.json',info['declarations'])
        if 'classification_mapping_manifest' in info:
            write(output/'classification_mapping_manifest.json',info['classification_mapping_manifest']['contents'])
        originals={'families':{'sha256':digest(families)},'edges':{'sha256':digest(edges)},'configuration':{'sha256':digest(config)},**info}
        f,e=load(families,edges,c)
        mf,me,matching=match(f,e,c)
        originals['standardized']={'families_sha256':frame_hash(f.sort_values('family_id').reset_index(drop=True)),
                                    'events_sha256':frame_hash(e.sort_values(['family_id','citing_family_id']).reset_index(drop=True))}
        write(output/'input_manifest.json',originals); write(output/'matching_audit.json',matching)
        write(output/'validation_report.json',{'status':'INPUTS_VALID','family_rows':len(f),'edge_rows':len(e)})
        result.update(status='COMPLETED',dataset_kind=info['source_manifest']['dataset_kind'],mode=c['execution']['mode'],
                      groups=c['comparison']['groups'],difference_direction='first group minus second',matching=matching)
        if include_data:
            mf.to_parquet(output/'matched_families.parquet',index=False); me.to_parquet(output/'matched_events.parquet',index=False)
        for y in c['comparison']['windows_years']:
            progress(stage='window',window=y)
            s,b,eb,flow=window(mf,me,y,c['comparison']['cutoff'])
            w={'status':'OK','sample_flow':flow,'incidence':{},'models':{},'reference':{'status':'NOT_REQUESTED'}}
            result['windows'][str(y)]=w
            if s.empty:
                w['status']='NO_COMMON_SUPPORT' if mf.empty else 'NO_COMPLETE_PAIRS'; continue
            for h,frame in [('H1',s),('H3',b),('H4',b),('H5',b)]:
                w['incidence'][h]=describe(frame,h.lower(),result['groups'])
                if h!='H1' and not flow['field_quality_pass']:
                    w['models'][h]={'status':'INSUFFICIENT_CLASSIFICATION','reason_code':'FIELD_QUALITY_GATE','estimate':None,'ci95':None,'p_value':None}
                else: w['models'][h]=binary(frame,h.lower())
            w['entry_timing']=cox(s)
            if not flow['field_quality_pass']:
                w['status']='INSUFFICIENT_CLASSIFICATION'; w['field_incidence_interpretation']='Exploratory complete-classification subsample only'
            else:
                third=_diagnostics.third_family_by_field(eb)
                bt=b.copy(); bt['third_family']=bt.docdb_family_id.isin(third.focus_docdb_family_id).astype(int)
                w['third_family_sensitivity']={'incidence':describe(bt,'third_family',result['groups']),'model':binary(bt,'third_family')}
                if c['reference']['enabled']:
                    from .portable_reference import run_all
                    w['reference']=run_all(b,eb,c,y,progress) if not b.empty else {'status':'NO_REFERENCE_SUPPORT'}
            if include_data: b.to_parquet(output/f'milestones_{y}Y.parquet',index=False)
        # Same longest-window complete cohort, per-window classification exclusions remain visible.
        longest=max(c['comparison']['windows_years'])
        fixed,_,_,_=window(mf,me,longest,c['comparison']['cutoff'])
        fixed_ids=set(fixed.match_id)
        result['fixed_longest_cohort']={}
        for y in c['comparison']['windows_years']:
            s,b,_,flow=window(mf.loc[mf.match_id.isin(fixed_ids)],me,y,c['comparison']['cutoff'])
            result['fixed_longest_cohort'][str(y)]={'sample_flow':flow,'incidence':{h:describe(fr,h.lower(),result['groups']) for h,fr in [('H1',s),('H3',b),('H4',b),('H5',b)]}}
        tests=[]
        for y in c['comparison']['windows_years']:
            main=result['windows'][str(y)]['reference'].get('main',{}).get('outcomes',{})
            for h in ['H4','H5']: tests.append((f'{h}_{y}Y',main.get(h,{}).get('p_value')))
        result['reference_primary_tests']=holm_prespecified(tests)
        def limitations(v):
            if isinstance(v,dict):
                if v.get('status') not in (None,'OK','COMPLETED','NOT_REQUESTED'): return True
                if v.get('interpretation_warning'): return True
                return any(limitations(x) for x in v.values())
            if isinstance(v,list): return any(limitations(x) for x in v)
            return False
        if c['execution']['mode']=='smoke' or limitations(result['windows']): result['status']='COMPLETED_WITH_LIMITATIONS'
    except (ValueError,KeyError,TypeError,OSError,RuntimeError) as exc:
        result.update(status='FAILED',reason_code=type(exc).__name__,message=str(exc))
        write(output/'validation_report.json',{'status':'FAILED','reason_code':type(exc).__name__,'message':str(exc)})
    finally:
        changed=[name for name,sha in code.items() if digest(Path(__file__).parent/name)!=sha]
        if changed:
            result['reproducibility_warning']={'reason_code':'CODE_CHANGED_DURING_RUN','files':changed}
            if result['status']=='COMPLETED': result['status']='COMPLETED_WITH_LIMITATIONS'
        write(output/'results.json',result); render(output,result)
        environment={name:importlib.metadata.version(name) for name in ['numpy','pandas','scipy','statsmodels','numba','pyarrow']}
        receipt={'status':result['status'],'software_version':__version__,'python':platform.python_version(),'platform':platform.system(),
            'dependencies':environment,'code_hashes':code,'code_changed_during_run':changed,'elapsed_seconds':time.monotonic()-started,
            'include_data':include_data,'publication_acceptance':'NOT_ESTABLISHED_BY_THIS_RUN'}
        for name in ['configuration.json','method_contract.json','input_manifest.json']:
            if (output/name).exists(): receipt[name+'_sha256']=digest(output/name)
        write(output/'run.json',receipt); progress(stage='finished',status=result['status'])
        write(output/'output_manifest.json',{p.name:digest(p) for p in sorted(output.iterdir()) if p.is_file() and p.name!='output_manifest.json'})
    return result
