import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import zipfile
import numpy as np
import pandas as pd
from patent_diffusion.demo_v1 import generate
from patent_diffusion.prepare import run as prepare
from patent_diffusion.portable import run
from patent_diffusion.portable_config import resolve, write, digest
from patent_diffusion.portable_inputs import load, match, window
from patent_diffusion.portable_reference import plan, reweighted, run_variant, weighted_cdf, simulate
from patent_diffusion.portable_models import interval, cox


class PortableAcceptanceTests(unittest.TestCase):
    def fixture(self,root,constant=True):
        manifest, config=generate(root/'raw',deterministic=constant)
        prepare(manifest,root/'raw/prepared')
        c=resolve(json.loads(config.read_text()))
        f,e=load(root/'raw/prepared/families.parquet',root/'raw/prepared/events.parquet',c)
        mf,me,_=match(f,e,c); _,b,eb,_=window(mf,me,1,c['comparison']['cutoff'])
        return c,b,eb,config

    def test_nonuniform_weight_cdf_and_explicit_zero_pool(self):
        # Hand pool: donor cells [0,1,1], multiplicities [2,1,0] => probabilities [1/2,1/4,1/4].
        p={'edges':pd.DataFrame({'cell':[0,1,1,2],'pair':[0,1,1,2]}),'donor_ix':np.array([0,1,2]),
           'starts':np.array([0]),'counts':np.array([3]),'valid':np.array([True]*3),'pool_ids':np.zeros(4,int)}
        cdf,failed=weighted_cdf(p,np.array([2,1,0])); np.testing.assert_array_equal(cdf,[2,3,4]); self.assertEqual(failed,[])
        cdf,failed=weighted_cdf(p,np.array([0,0,1])); self.assertEqual(failed,[0]); np.testing.assert_array_equal(cdf,[0,0,0])
        # No implicit uniform fallback: an active zero pool fails the whole sensitivity.
        with tempfile.TemporaryDirectory() as tmp:
            c,b,e,_=self.fixture(Path(tmp)); p=plan(b,e,c,'main',1)
            with patch('patent_diffusion.portable_reference.weighted_cdf',return_value=(p['cdf'],[0])):
                r=reweighted(p,c,1)
            self.assertEqual(r['reason_code'],'ZERO_WEIGHT_POOL_OR_TARGET'); self.assertEqual(r['completed_draws'],0)

    def test_precision_cap_and_degenerate_inference(self):
        self.assertEqual(interval(np.zeros(2000),0.,40)['reason_code'],'DEGENERATE_BOOTSTRAP')
        with tempfile.TemporaryDirectory() as tmp:
            c,b,e,_=self.fixture(Path(tmp)); c['execution']['mode']='formal'
            calls=[0]
            def noisy(p,*args,**kwargs):
                calls[0]+=1; a=np.zeros((len(b)//2,2,3),np.uint8); a[:,calls[0]%2,:]=1; return a
            with patch('patent_diffusion.portable_reference.simulate',side_effect=noisy):
                r,p,ref=run_variant(b,e,c,'main',1)
            self.assertEqual(calls[0],10000); self.assertEqual(r['status'],'PRECISION_NOT_MET')
            self.assertIsNone(r['outcomes']['H4']['p_value'])
            calls[0]=0
            with patch('patent_diffusion.portable_reference.simulate',side_effect=noisy): r=reweighted(p,c,1)
            self.assertEqual(r['reason_code'],'INNER_MCSE_LIMIT'); self.assertEqual(r['draw_audit'][0]['inner_replicates'],2000)
            self.assertEqual(r['completed_draws'],0)

    def test_exact_support_boundary_cohort_and_no_cross_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            c,b,e,_=self.fixture(Path(tmp)); p=plan(b,e,c,'main',1)
            target_fold=0
            ids=set(p['frame'].loc[p['frame'].fold.eq(target_fold),'docdb_family_id'])
            targets=e.loc[e.focus_docdb_family_id.isin(ids)].iloc[:1]
            donors=e.loc[~e.focus_docdb_family_id.isin(ids)].iloc[:200].copy()
            # Exactly 200 edges, 50 citing families; full field fallback permitted.
            donors['citing_docdb_family_id']=['C'+str(i%50) for i in range(200)]
            pp=plan(b,pd.concat([targets,donors]),c,'main',1)
            pools=[x for x in pp['support']['pools'] if x['target_fold']==target_fold]
            self.assertTrue(pools); self.assertTrue(any(x['donor_edges']==200 and x['distinct_citing_families']==50 for x in pools))
            for bad in [donors.iloc[:199],donors.assign(citing_docdb_family_id=['C'+str(i%49) for i in range(200)])]:
                z=plan(b,pd.concat([targets,bad]),c,'main',1)
                self.assertFalse([x for x in z['support']['pools'] if x['target_fold']==target_fold])
            z=plan(b,e,c,'additional_grant_cohort_stratum',1)
            for pool in z['support']['pools']:
                self.assertGreaterEqual(len(pool['stratum']),2) # focal AND cohort even final fallback
            b2=b.copy(); b2.loc[b2.docdb_family_id.isin(ids),'wipo35_field_nr']=35
            e2=e.copy(); e2.loc[e2.focus_docdb_family_id.isin(ids),'focal_wipo35_field_nr']=35
            z=plan(b2,e2,c,'main',1)
            self.assertFalse([x for x in z['support']['pools'] if x['target_fold']==target_fold and x['stratum'][0]==35])

    def test_adapter_pregrant_unknown_date_primary_and_office_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); manifest,config=generate(root/'raw',clusters=2,pairs_per_cluster=2,deterministic=True)
            m=json.loads(manifest.read_text()); pubs=root/'raw/publications.csv'; p=pd.read_csv(pubs,dtype=str)
            p.loc[p.pat_publn_id.str.startswith('PUB_C_') & p.pat_publn_id.str.endswith('_0'),'publn_date']='2009-01-01'
            p.to_csv(pubs,index=False); m['tables']['publications']['sha256']=digest(pubs); write(manifest,m)
            a=prepare(manifest,root/'excluded'); self.assertEqual(a['excluded']['pregrant'],9) # duplicate source record included
            m['pregrant_policy']='stop'; write(manifest,m)
            with self.assertRaisesRegex(ValueError,'Pre-grant'): prepare(manifest,root/'stopped')
            m['pregrant_policy']='exclude_records'; p.loc[1,'publn_date']='9999-12-31'; p.to_csv(pubs,index=False)
            m['tables']['publications']['sha256']=digest(pubs); write(manifest,m)
            with self.assertRaisesRegex(ValueError,'Invalid publication date'): prepare(manifest,root/'sentinel')
            m['invalid_date_policy']='exclude_records'; write(manifest,m)
            self.assertEqual(prepare(manifest,root/'date_excluded')['excluded']['invalid_publication_dates'],1)
            roster=root/'raw/roster.csv'; r=pd.read_csv(roster,dtype=str); r.loc[0,'primary_ipc_class_symbol']='A01B 2/00'; r.to_csv(roster,index=False)
            m['tables']['roster']['sha256']=digest(roster); write(manifest,m)
            with self.assertRaisesRegex(ValueError,'absent'): prepare(manifest,root/'bad_primary')

    def test_audit_hashes_relocation_shuffle_and_contract_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); c,b,e,config=self.fixture(root); c['reference']['enabled']=False; c['comparison']['windows_years']=[1]; write(config,c)
            fpath=root/'raw/prepared/families.parquet'; epath=root/'raw/prepared/events.parquet'
            first=run(fpath,epath,config,root/'one')
            f=pd.read_parquet(fpath); e=pd.read_parquet(epath)
            f.sample(frac=1,random_state=5).to_parquet(root/'f.parquet',index=False); e.sample(frac=1,random_state=6).to_parquet(root/'e.parquet',index=False)
            second=run(root/'f.parquet',root/'e.parquet',config,root/'two')
            self.assertEqual(first,second)
            for out in [root/'one',root/'two']:
                manifest=json.loads((out/'output_manifest.json').read_text())
                for name,sha in manifest.items(): self.assertEqual(digest(out/name),sha)
            receipts=[json.loads((root/x/'input_manifest.json').read_text()) for x in ['one','two']]
            self.assertEqual(receipts[0]['standardized'],receipts[1]['standardized'])
            self.assertNotEqual(receipts[0]['families']['sha256'],receipts[1]['families']['sha256'])
            c['comparison']['grant_office_scope']=['EP']; write(config,c)
            bad=run(fpath,epath,config,root/'bad')
            self.assertEqual(bad['status'],'FAILED'); self.assertIn('office scope',bad['message'])
            self.assertTrue((root/'bad/method_contract.json').exists())

    def test_missing_classification_tutorial_and_date_endpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); manifest,config=generate(root/'raw',missing_classification=True)
            prepare(manifest,root/'raw/prepared'); c=resolve(json.loads(config.read_text()))
            f,e=load(root/'raw/prepared/families.parquet',root/'raw/prepared/events.parquet',c)
            self.assertEqual(int(e.classification_missing.sum()),1)
            mf,me,_=match(f,e,c); _,b,eb,flow=window(mf,me,1,c['comparison']['cutoff'])
            self.assertEqual(flow['classification_complete_pairs'],159); self.assertTrue(flow['field_quality_pass'])
            # Grant day included, cutoff day included, day after anniversary excluded from 1Y.
            pair=mf.loc[mf.match_id.eq(mf.match_id.iloc[0])].copy(); pair['focus_grant_date']=pd.Timestamp('2020-02-29')
            events=me.iloc[:0].copy()
            rows=[]
            for day,cf in [('2020-02-29','d0'),('2021-02-28','d365'),('2021-03-01','d366')]:
                rows.append({'focus_docdb_family_id':pair.docdb_family_id.iloc[0],'citing_docdb_family_id':cf,'edge_event_date':pd.Timestamp(day),'citing_wipo35_mask':2,'citing_wipo35_missing':False,'focal_wipo35_field_nr':1})
            events=pd.DataFrame(rows); ss,bb,ee,flow=window(pair,events,1,'2021-02-28')
            self.assertEqual(len(ee),2); self.assertEqual(int(ss.citation_count.sum()),2); self.assertEqual(int(bb.h4.sum()),1)

    def test_cox_explicit_nonconvergence_and_singular_guards(self):
        from unittest.mock import MagicMock
        import warnings
        with tempfile.TemporaryDirectory() as tmp:
            c,b,e,_=self.fixture(Path(tmp),constant=False)
            model=MagicMock()
            def nonconverge(*args,**kwargs):
                warnings.warn('Maximum likelihood failed to converge'); return MagicMock()
            model.fit.side_effect=nonconverge
            with patch('patent_diffusion.portable_models.PHReg',return_value=model): r=cox(b)
            self.assertEqual(r['reason_code'],'NONCONVERGENCE'); self.assertIsNone(r['ci95'])
            model.fit.side_effect=np.linalg.LinAlgError('singular')
            with patch('patent_diffusion.portable_models.PHReg',return_value=model): r=cox(b)
            self.assertEqual(r['reason_code'],'FIT_FAILED_LinAlgError'); self.assertIsNone(r['p_value'])

    def test_portable_ui_all_modules_download_and_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); manifest,config=generate(root/'raw'); prepare(manifest,root/'raw/prepared')
            process=subprocess.Popen([sys.executable,'-m','patent_diffusion','ui','--workdir',str(root/'ui'),'--port','0'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            try:
                base=re.search(r'http://127\.0\.0\.1:\d+',process.stdout.readline()).group()
                page=urlopen(base).read().decode(); token=re.search("const token='([^']+)'",page).group(1)
                def post(path,data):
                    with urlopen(Request(base+path,data=data,headers={'X-Local-Token':token})) as response: return json.loads(response.read())
                payload={'config':json.loads(config.read_text())}; payload['config']['comparison']['windows_years']=[1]
                for name,file in [('families','families.parquet'),('edges','events.parquet'),('source_manifest','source_manifest.json'),('mapping_manifest','classification_mapping_manifest.json')]:
                    p=root/'raw/prepared'/file; payload[name]=post('/upload?name='+name+'&ext='+p.suffix[1:],p.read_bytes())['path']
                post('/run',json.dumps(payload).encode())
                deadline=time.monotonic()+90
                while time.monotonic()<deadline:
                    status=json.loads(urlopen(base+'/status').read())
                    if status['status'] not in ['RUNNING','CANCELLING']: break
                    time.sleep(.1)
                self.assertEqual(status['status'],'COMPLETED_WITH_LIMITATIONS',status)
                self.assertIn(b'Matched pairs',urlopen(base+'/report').read())
                with zipfile.ZipFile(io.BytesIO(urlopen(base+'/download').read())) as z:
                    self.assertFalse(any(x.endswith('.parquet') for x in z.namelist()))
                    result=json.loads(z.read('results.json')); self.assertIn('reweighted_pool_fixed_support',result['windows']['1']['reference'])
                    self.assertIn('method_contract.json',z.namelist()); self.assertIn('source_manifest.json',z.namelist())
                payload['config']['execution']['mode']='formal'
                post('/run',json.dumps(payload).encode()); post('/cancel',b'{}')
                deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    status=json.loads(urlopen(base+'/status').read())
                    if status['status']=='CANCELLED': break
                    time.sleep(.05)
                self.assertEqual(status['status'],'CANCELLED',status)
                with self.assertRaises(HTTPError): urlopen(base+'/download')
            finally:
                process.terminate(); process.wait(timeout=10); process.stdout.close()

if __name__=='__main__': unittest.main()
