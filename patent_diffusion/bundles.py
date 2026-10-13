"""Build and verify two complete, versioned study-input archives (local only)."""
import gzip
import hashlib
import json
from pathlib import Path
import zipfile

import pandas as pd

from .pipeline import FAMILY_COLUMNS, EDGE_COLUMNS, load_inputs


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def build(source, output):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    f, e = load_inputs(source/'canonical_families.parquet', source/'canonical_edges.parquet')
    # Only pre-outcome metadata is carried into the family input.
    f = f[sorted(FAMILY_COLUMNS | {'focus_patent_id'})].copy()
    with zipfile.ZipFile(source/'matched_ai_nonai_all_patent_data_20260908.zip') as z:
        with gzip.GzipFile(fileobj=z.open('matched_ai_nonai_all_patents_464516.csv.gz')) as stream:
            labels = pd.read_csv(stream, usecols=['docdb_family_id', 'ai_label_sources'])
    f = f.merge(labels, on='docdb_family_id', how='left', validate='one_to_one')
    scores = pd.read_csv(source/'aipat_scores.csv', usecols=['patent_id', 'AI_related'], dtype={'patent_id':str})
    if scores.groupby('patent_id').AI_related.nunique().gt(1).any():
        raise ValueError('Conflicting AIPat scores')
    f['focus_patent_id'] = f.focus_patent_id.astype(str)
    f = f.merge(scores.drop_duplicates('patent_id'), left_on='focus_patent_id', right_on='patent_id', how='left', validate='many_to_one').drop(columns='patent_id')
    # Retain source publication/application links where present for traceability.
    columns = sorted(EDGE_COLUMNS | (set(e.columns) & {'source_event_publn_set','source_event_appln_set','edge_type'}))
    e = e[columns].copy()
    dataset_id = sha256(source/'canonical_families.parquet')[:16]+'-'+sha256(source/'canonical_edges.parquet')[:16]
    reports = []
    for ai, name in [(1,'AI_patent_families'),(0,'nonAI_patent_families')]:
        folder = output/name
        folder.mkdir()
        ff = f.loc[f.ai_indicator.eq(ai)].copy()
        ee = e.loc[e.focus_docdb_family_id.isin(ff.docdb_family_id)].copy()
        ff.to_parquet(folder/'families.parquet',index=False)
        ee.to_parquet(folder/'edges.parquet',index=False)
        dictionary = {'families':{c:str(t) for c,t in ff.dtypes.items()},'edges':{c:str(t) for c,t in ee.dtypes.items()},
          'semantics':{'match_id':'Shared 1:1 pair identifier; preserve exact string for folds and pairing.',
          'docdb_family_id':'DOCDB simple family ID; global identity is retained across both bundles.',
          'focus_grant_date':'Earliest eligible focal US grant; timezone-naive calendar date.',
          'wipo35_field_nr':'Single primary focal WIPO35 field, integers 1..35.',
          'citing_wipo35_mask':'Complete set; bit 0 is field 1, bit 34 is field 35. Missing flag takes precedence.',
          'citing_wipo35_missing':'True means classification unavailable; never substitute no cross-field event.',
          'edge_event_date':'Earliest eligible publication date for the unique focal/citing-family edge.',
          'AI_related':'Released focal-grant AIPat score; not family-wide maximum or calibrated probability.',
          'ai_label_sources':'Original family AI-label source annotation.',
          'ai_indicator':'1 AI, 0 operational non-AI comparison group.',
          'zero_citation':'Families without edge rows are retained; only complete follow-up is coded as no event.'}}
        (folder/'DATA_DICTIONARY.json').write_text(json.dumps(dictionary,ensure_ascii=False,indent=2),encoding='utf-8')
        (folder/'README.md').write_text('''# Complete study input / 完整研究输入

Use BOTH AI_patent_families.zip and nonAI_patent_families.zip with the same dataset_id.
Both archives are required to reconstruct matched pairs and pooled donor distributions.
两包必须联合使用；保留零引用专利族、缺失分类事件和跨包一致的标识。

Cutoff: 2026-06-30, inclusive Gregorian 1/3/5-year anniversaries.
Outcomes are recomputed from events; no target outcome or coefficient is an input.
The family and edge inputs reuse the historical preprocessed research dataset.
They do not independently re-query PATSTAT or recreate source-roster selection.

Distribution status: LOCAL_REVIEW_ONLY_PENDING_SOURCE_PERMISSION.
No new data licence is granted. PATSTAT/TIP access terms and institutional rights
must be verified before public distribution or submission to third parties.
''',encoding='utf-8')
        files = {p.name:{'sha256':sha256(p),'bytes':p.stat().st_size} for p in sorted(folder.iterdir())}
        manifest = {'schema_version':1,'dataset_id':dataset_id,'group':name,'ai_indicator':ai,
          'families':len(ff),'edges':len(ee),'zero_citation_families':int((~ff.docdb_family_id.isin(ee.focus_docdb_family_id)).sum()),
          'files':files,'source_hashes':{n:sha256(source/n) for n in ['canonical_families.parquet','canonical_edges.parquet','aipat_scores.csv','matched_ai_nonai_all_patent_data_20260908.zip']},
          'redistribution_status':'UNVERIFIED_NOT_FOR_DISTRIBUTION','raw_preprocessing_reexecuted':False}
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        archive = output/(name+'.zip')
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p in sorted(folder.iterdir()): z.write(p,p.name)
        reports.append({'name':archive.name,'sha256':sha256(archive),'bytes':archive.stat().st_size,**{k:manifest[k] for k in ['families','edges','zero_citation_families']}})
    (output/'bundle_receipt.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
    return reports


def combine(archives, output):
    """Verify content before merging; do not extract arbitrary archive paths."""
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    families,edges, manifests = [],[],[]
    for i,path in enumerate(archives):
        with zipfile.ZipFile(path) as z:
            manifest=json.loads(z.read('manifest.json'))
            if not {'families.parquet','edges.parquet'}.issubset(manifest['files']):
                raise ValueError('Bundle manifest omits required inputs')
            for name,entry in manifest['files'].items():
                if Path(name).name != name or '/' in name or '\\' in name:
                    raise ValueError('Bundle entries must be flat filenames')
                content=z.read(name)
                if len(content)!=entry['bytes'] or hashlib.sha256(content).hexdigest()!=entry['sha256']:
                    raise ValueError(f'Bundle checksum failure: {name}')
            import io
            f=pd.read_parquet(io.BytesIO(z.read('families.parquet')))
            e=pd.read_parquet(io.BytesIO(z.read('edges.parquet')))
            if len(f)!=manifest['families'] or len(e)!=manifest['edges']:
                raise ValueError('Bundle row count mismatch')
            if not f.ai_indicator.eq(manifest['ai_indicator']).all():
                raise ValueError('Bundle group mismatch')
            for name in manifest['files']:
                if name.startswith('source_') and name.endswith('.parquet'):
                    dest=output/name
                    if dest.exists(): raise ValueError('Duplicate lineage file')
                    dest.write_bytes(z.read(name))
            families.append(f); edges.append(e); manifests.append(manifest)
    if len(manifests)!=2 or len({m['dataset_id'] for m in manifests})!=1 or {m['ai_indicator'] for m in manifests}!={0,1}:
        raise ValueError('Expected two complementary bundles from one dataset version')
    # Exact native ID types are preserved: converting numeric IDs to strings changes RNG order.
    f=pd.concat(families,ignore_index=True).sort_values(['match_id','ai_indicator'],kind='stable')
    e=pd.concat(edges,ignore_index=True).sort_values(['focus_docdb_family_id','edge_event_date','citing_docdb_family_id'],kind='stable')
    f.to_parquet(output/'families.parquet',index=False)
    e.to_parquet(output/'edges.parquet',index=False)
    load_inputs(output/'families.parquet',output/'edges.parquet')
    (output/'bundle_manifests.json').write_text(json.dumps(manifests,indent=2),encoding='utf-8')
    return output/'families.parquet', output/'edges.parquet'
