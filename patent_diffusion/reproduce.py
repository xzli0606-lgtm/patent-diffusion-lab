"""Offline full-sample execution from two checked bundles, with stage receipts."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from .bundles import combine, sha256

CONFIG = {
    'profile':'paper_v4_20261012','citation_cutoff':'2026-06-30','horizons':[1,3,5],
    'ai_sensitivity_threshold':0.9,
    'seeds':{'fold':20260918,'simulation_base':20260919,'conditional_bootstrap':20260920,
             'pool_bootstrap':20260921,'pool_field_draw':20270000,
             'third_family_bootstrap':20260930,'arrival_bootstrap':20260930},
    'simulation':{'initial':2000,'increment':2000,'maximum':10000,'mcse_max_pp':0.1},
    'bootstrap':{'conditional':2000,'pool':200},
    'tolerances':{'counts':'exact','indicators':'exact','display':'round to printed precision',
                  'raw_float_rtol':1e-8,'raw_float_atol':1e-10},
    'interpretation':'Conditional observational contrasts; no causal or prediction claim',
    'scope':'Recompute analyses from historical preprocessed matched family/event inputs; raw source selection separately audited',
}


def write(path, value):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')


def reference(root, years, kind, config):
    from . import _reference, _pool
    root=Path(root)
    edges=root/'inputs/edges.parquet'
    families=root/'outputs/window_samples.parquet'
    baseline=root/f'outputs/h45_family_outcomes_{years}Y.parquet'
    m=_pool if kind=='rebuilt' else _reference
    m.EDGE_SHA=sha256(edges); m.FAMILY_SHA=sha256(families)
    original_argv=sys.argv[:]
    try:
        if kind=='rebuilt':
            # Frozen original source uses a separate field-draw seed, not the pair seed.
            m.FIELD_DRAW_SEED=config['seeds']['pool_field_draw']
            out=root/f'outputs/opportunity_reference/rebuilt_{years}Y'
            sys.argv=['pool','--edge',str(edges),'--family',str(families),'--baseline',str(baseline),
                      '--main-script',str(Path(_reference.__file__)),'--output',str(out),
                      '--horizon',f'{years}Y','--replicates',str(config['bootstrap']['pool'])]
            m.main()
        else:
            contract=Path(__file__).with_name('reference_contract.json')
            for reps in range(config['simulation']['initial'],config['simulation']['maximum']+1,config['simulation']['increment']):
                out=root/f'outputs/opportunity_reference/{kind}_{years}Y_B{reps}'
                sys.argv=['reference','--edge',str(edges),'--family',str(families),'--baseline',str(baseline),
                          '--contract',str(contract),'--output',str(out),'--horizon',f'{years}Y','--replicates',str(reps)]
                if kind=='nonai': sys.argv.append('--donor-nonai-only')
                if kind=='grant': sys.argv.append('--grant-cohort')
                m.main()
                result=json.loads((out/'RESULT.json').read_text(encoding='utf-8'))
                if result['status']=='COMPLETE':
                    write(root/f'outputs/opportunity_reference/{kind}_{years}Y_selected.json',
                          {'result_path':str(out.relative_to(root)/'RESULT.json'),'replicates':reps,'sha256':sha256(out/'RESULT.json')})
                    break
            else: raise RuntimeError('Monte Carlo precision threshold not met')
    finally:
        sys.argv=original_argv


def labels(root,config):
    import pandas as pd
    from . import _study
    f=pd.read_parquet(root/'inputs/families.parquet')
    if not {'AI_related','ai_label_sources'}.issubset(f): raise ValueError('Label sensitivity inputs missing')
    result={'definition':'Fixed original pairs selected by focal-grant score; not family-wide relabelling','windows':{}}
    for y in config['horizons']:
        s=pd.read_parquet(root/f'outputs/h45_family_outcomes_{y}Y.parquet')
        s=s.drop(columns=['AI_related','ai_label_sources'],errors='ignore').merge(f[['docdb_family_id','AI_related','ai_label_sources']],on='docdb_family_id',validate='one_to_one')
        w=s.pivot(index='match_id',columns='ai_indicator',values='AI_related')
        scopes={'ai_ge_090':w.index[w[1].ge(.9)],'ai_ge_090_nonai_lt_010':w.index[w[1].ge(.9)&w[0].lt(.1)]}
        result['windows'][f'{y}Y']={name:{k:_study.conditional_binary(s.loc[s.match_id.isin(ids)],k.lower(),name+'-'+k) for k in ['H1','H3','H4','H5']} for name,ids in scopes.items()}
    write(root/'outputs/sensitivity/ai_label.json',result)


def adjust(root):
    from ._study import holm
    binary=[]; residual=[]
    for y in [1,3,5]:
        r=json.loads((root/f'outputs/model_results/{y}Y.json').read_text())
        selected=json.loads((root/f'outputs/opportunity_reference/main_{y}Y_selected.json').read_text())
        ref=json.loads((root/selected['result_path']).read_text())
        for h in ['H4','H5']:
            binary.append((f'{h}-{y}Y',r['binary'][h]['p_two_sided']))
            residual.append((f'{h}-{y}Y',ref['outcomes'][h]['bootstrap_normal_p_two_sided']))
    r=json.loads((root/'outputs/model_results/5Y.json').read_text())
    primary=[('H1-5Y',r['binary']['H1']['p_two_sided']),('H2-5Y',r['cox']['H1']['p_two_sided']),('H3-5Y',r['binary']['H3']['p_two_sided'])]
    write(root/'outputs/holm.json',{'primary_5Y':holm(primary),'H4_H5_incidence':holm(binary),'H4_H5_reference_residuals':holm(residual)})


def worker(root,stage,years,kind):
    from . import study
    root=Path(root).resolve()
    config=json.loads((root/'config.json').read_text())
    study.configure(root,root/'inputs/families.parquet',root/'inputs/edges.parquet',config)
    if stage=='events': study.stage4()
    elif stage=='windows': study.stage5()
    elif stage=='models': study.stage6(years)
    elif stage=='sensitivity': study.sensitivity(years)
    elif stage=='benchmark': study.benchmark()
    elif stage=='labels': labels(root,config)
    elif stage=='reference': reference(root,years,kind,config)
    elif stage=='adjust': adjust(root)
    else: raise ValueError(stage)


def execute(root,stage,years=0,kind='main'):
    label=f'{stage}_{years}_{kind}'
    receipt_path=root/f'logs/{label}.json'
    if receipt_path.exists():
        prior=json.loads(receipt_path.read_text())
        if prior.get('exit_code')==0:
            for relative, digest in prior.get('output_hashes',{}).items():
                if sha256(root/relative)!=digest: raise RuntimeError('Completed output changed: '+relative)
            return
    command=[sys.executable,'-m','patent_diffusion.reproduce','--worker',stage,'--output',str(root),'--years',str(years),'--kind',kind]
    env=os.environ.copy()
    env.update({'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1'})
    start=time.time()
    print('START',label,flush=True)
    with (root/f'logs/{label}.stdout').open('wb') as out,(root/f'logs/{label}.stderr').open('wb') as err:
        result=subprocess.run(command,stdout=out,stderr=err,env=env)
    patterns={
        'events':['milestone_events.parquet','receiving_field_events.parquet'],
        'windows':['window_samples.parquet','window_audit.json','h45_family_outcomes_*Y.parquet'],
        'models':[f'model_results/{years}Y.json'],
        'benchmark':['model_results/benchmark.json'],
        'sensitivity':[f'sensitivity/{years}Y.json',f'sensitivity/third_family_{years}Y.parquet'],
        'labels':['sensitivity/ai_label.json'], 'adjust':['holm.json'],
        'reference':[f'opportunity_reference/{kind}_{years}Y*/*',f'opportunity_reference/{kind}_{years}Y_selected.json']}
    owned={p for pattern in patterns[stage] for p in (root/'outputs').glob(pattern) if p.is_file()}
    changed={str(p.relative_to(root)):sha256(p) for p in sorted(owned)}
    write(receipt_path,{'stage':label,'command':command,'start_unix':start,'seconds':time.time()-start,'exit_code':result.returncode,'output_hashes':changed})
    print('END',label,result.returncode,round(time.time()-start,1),flush=True)
    if result.returncode: raise RuntimeError('Stage failed; see '+str(root/f'logs/{label}.stderr'))


def run(archives,root,jobs=3,resume=False):
    root=Path(root).resolve()
    if resume:
        config=json.loads((root/'config.json').read_text())
        if config!=CONFIG: raise ValueError('Resume configuration changed')
        manifest=json.loads((root/'input_receipt.json').read_text())
        for name,entry in manifest.items():
            if sha256(root/'inputs'/name)!=entry['sha256']: raise ValueError('Resume input changed')
    else:
        root.mkdir(parents=True,exist_ok=False)
        write(root/'config.json',CONFIG)
        f,e=combine(archives,root/'inputs')
        write(root/'input_receipt.json',{p.name:{'sha256':sha256(p),'bytes':p.stat().st_size} for p in [f,e]})
        write(root/'environment.json',{'python':sys.version,'platform':platform.platform(),'packages':{n:importlib.metadata.version(n) for n in ['numpy','pandas','scipy','statsmodels','numba','pyarrow']}})
    (root/'logs').mkdir(exist_ok=True); (root/'outputs').mkdir(exist_ok=True)
    source={p.name:sha256(p) for p in Path(__file__).parent.glob('*.py')}
    if resume and json.loads((root/'code_hashes.json').read_text())!=source:
        raise ValueError('Resume code changed; start a new run')
    write(root/'code_hashes.json',source)
    try:
        execute(root,'events'); execute(root,'windows')
        tasks=[('models',y,'main') for y in [1,3,5]]+[('benchmark',0,'main')]
        tasks += [('reference',y,k) for k in ['main','nonai','grant','rebuilt'] for y in [1,3,5]]
        tasks += [('sensitivity',y,'main') for y in [1,3,5]]+[('labels',0,'main')]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures=[pool.submit(execute,root,*task) for task in tasks]
            errors=[]
            for f in futures:
                try: f.result()
                except Exception as e: errors.append(str(e))
        if errors: raise RuntimeError('\n'.join(errors))
        execute(root,'adjust')
        from .reporting import compile_results
        compile_results(root)
        write(root/'run_status.json',{'status':'ANALYSES_COMPUTED_PENDING_MANUSCRIPT_VALIDATION','full_sample':True,'raw_source_construction_reexecuted':False})
    except Exception:
        write(root/'run_status.json',{'status':'FAILED','error':traceback.format_exc()})
        raise


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--ai',type=Path); p.add_argument('--nonai',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--jobs',type=int,default=3)
    p.add_argument('--resume',action='store_true')
    p.add_argument('--worker'); p.add_argument('--years',type=int,default=0); p.add_argument('--kind',default='main')
    a=p.parse_args()
    if a.worker: worker(a.output,a.worker,a.years,a.kind)
    else:
        if not 1<=a.jobs<=3: p.error('--jobs must be 1..3')
        if not a.resume and not (a.ai and a.nonai): p.error('Both archives are required')
        run([a.ai,a.nonai],a.output,a.jobs,a.resume)


if __name__=='__main__': main()
