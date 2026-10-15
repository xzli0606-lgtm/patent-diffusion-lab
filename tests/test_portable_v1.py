import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd
from patent_diffusion.portable_config import DEFAULTS, resolve, write, digest
from patent_diffusion.portable_inputs import identifiers, load, match, window
from patent_diffusion.portable_models import binary, cox, cluster_bootstrap, holm_prespecified
from patent_diffusion.portable import run
from patent_diffusion.demo_v1 import generate
from patent_diffusion.prepare import run as prepare
from patent_diffusion.portable_reference import plan, run_variant, weighted_cdf, score, seed


def configuration(root,reference=False):
    c=copy.deepcopy(DEFAULTS)
    c['comparison'].update(group_definition='Synthetic test labels',cutoff='2026-06-30',grant_office_scope=['US'],windows_years=[1])
    c['reference']['enabled']=reference; c['execution']['mode']='smoke'
    c['inputs']['source_manifest']='source.json'
    write(root/'source.json',{'dataset_kind':'synthetic','source':'test generator','snapshot':'test-v1','family_definition':'DOCDB simple family',
        'group_assignment':'synthetic A/B','classification_mapping':'synthetic WIPO fields','grant_rule':'synthetic first US grant'})
    write(root/'config.json',c)
    return c


def basic(root,pairs=10):
    f=pd.DataFrame([{'family_id':f'{g}{i:03}','grant_date':'2020-01-01','focal_field':1,'group':g} for g in ['A','B'] for i in range(pairs)])
    e=pd.DataFrame(columns=['family_id','citing_family_id','event_date','field_mask','classification_missing'])
    f.to_csv(root/'f.csv',index=False); e.to_csv(root/'e.csv',index=False)
    return f,e


class PortableV1Tests(unittest.TestCase):
    def test_policy_rejects_unknown_threshold_and_cluster_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=configuration(Path(tmp)); resolve(c)
            for change in ['unknown','threshold','clusters','window','float_seed']:
                z=copy.deepcopy(c)
                if change=='unknown': z['magic']=True
                if change=='threshold': z['quality']['minimum_effective_clusters_for_inference']=1
                if change=='clusters': z['matching']['cluster_columns']=['focal_field']
                if change=='window': z['comparison']['windows_years']=[6]
                if change=='float_seed': z['matching']['seed']=1.5
                with self.subTest(change=change),self.assertRaises(ValueError): resolve(z)

    def test_identifiers_and_mapping_collisions(self):
        self.assertEqual(identifiers(pd.Series(['001','9007199254740993',42])).tolist(),['001','9007199254740993','42'])
        for ids in [[1.0],['1.5'],['1e10'],[''],[' x'],[None]]:
            with self.subTest(ids=ids),self.assertRaises(ValueError): identifiers(pd.Series(ids))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); c=configuration(root); f,e=basic(root)
            f['group']=f.group.map({'A':'1','B':'0'}); f.to_csv(root/'f.csv',index=False)
            c['comparison']['groups']=['1','0']; a,b=load(root/'f.csv',root/'e.csv',c)
            self.assertEqual(match(a,b,c)[2]['matched_pairs'],10)
            c['inputs']['family_columns']={'family_id':'group'}
            with self.assertRaisesRegex(ValueError,'collision'): load(root/'f.csv',root/'e.csv',c)

    def test_single_cluster_seven_three_and_zero_event_report(self):
        rows=[]
        for i in range(10):
            for side in [0,1]: rows.append({'match_id':str(i),'ai_indicator':side,'matching_cell':'one','h1':int(side==(1 if i<7 else 0))})
        r=binary(pd.DataFrame(rows),'h1')
        self.assertAlmostEqual(r['estimate'],7/3); self.assertIsNone(r['ci95']); self.assertIsNone(r['p_value'])
        self.assertEqual(r['n_clusters_effective'],1)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); configuration(root); basic(root)
            r=run(root/'f.csv',root/'e.csv',root/'config.json',root/'out')
            self.assertEqual(r['status'],'COMPLETED_WITH_LIMITATIONS')
            self.assertEqual(r['windows']['1']['entry_timing']['reason_code'],'ZERO_EVENTS')
            self.assertEqual(r['windows']['1']['incidence']['H1'][0]['incidence_pct'],0)
            self.assertTrue((root/'out/report.html').exists())
            json.loads((root/'out/results.json').read_text(),parse_constant=lambda x:self.fail('nonfinite JSON'))
            self.assertFalse(list((root/'out').glob('*.parquet')))
            with self.assertRaises(FileExistsError): run(root/'f.csv',root/'e.csv',root/'config.json',root/'out')

    def test_separation_and_information_clusters(self):
        f=pd.DataFrame([{'match_id':str(i),'ai_indicator':side,'matching_cell':str(i),'h1':side} for i in range(40) for side in [0,1]])
        self.assertEqual(binary(f,'h1')['reason_code'],'NO_FINITE_CONDITIONAL_OR')
        f.loc[f.match_id.astype(int).ge(20),'h1']=1-f.loc[f.match_id.astype(int).ge(20),'h1']
        r=binary(f,'h1'); self.assertEqual(r['status'],'OK'); self.assertEqual(r['estimate'],1.)
        f.loc[f.match_id.astype(int).ge(10),'h1']=0
        self.assertEqual(binary(f,'h1')['n_clusters_effective'],10)

    def test_classification_zero_and_unknown_fields_fail_audibly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); configuration(root); f,_=basic(root)
            e=pd.DataFrame([{'family_id':x,'citing_family_id':'c'+x,'event_date':'2020-02-01','field_mask':0,'classification_missing':True} for x in f.family_id])
            e.to_csv(root/'e.csv',index=False)
            r=run(root/'f.csv',root/'e.csv',root/'config.json',root/'out')
            w=r['windows']['1']; self.assertEqual(w['status'],'INSUFFICIENT_CLASSIFICATION')
            self.assertEqual(w['sample_flow']['classification_complete_pairs'],0)
            self.assertEqual(w['models']['H4']['status'],'INSUFFICIENT_CLASSIFICATION')
            e.loc[0,'classification_missing']=False; e.to_csv(root/'e.csv',index=False)
            bad=run(root/'f.csv',root/'e.csv',root/'config.json',root/'bad')
            self.assertEqual(bad['status'],'FAILED'); self.assertTrue((root/'bad/validation_report.json').exists())

    def test_no_support_and_no_followup_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); configuration(root); f,_=basic(root)
            f.loc[f.group.eq('B'),'focal_field']=2; f.to_csv(root/'f.csv',index=False)
            r=run(root/'f.csv',root/'e.csv',root/'config.json',root/'no_support')
            self.assertEqual(r['windows']['1']['status'],'NO_COMMON_SUPPORT')
            f['focal_field']=1; f['grant_date']='2026-01-01'; f.to_csv(root/'f.csv',index=False)
            r=run(root/'f.csv',root/'e.csv',root/'config.json',root/'no_followup')
            self.assertEqual(r['windows']['1']['status'],'NO_COMPLETE_PAIRS')

    def test_leap_boundary_and_row_order_invariance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); c=configuration(root); f,_=basic(root); f['grant_date']='2020-02-29'
            f.to_csv(root/'f.csv',index=False)
            e=pd.DataFrame([{'family_id':'A000','citing_family_id':'external','event_date':'2021-02-28','field_mask':2,'classification_missing':False}])
            e.to_csv(root/'e.csv',index=False)
            a,b=load(root/'f.csv',root/'e.csv',c); mf,me,_=match(a,b,c)
            s,base,_,_=window(mf,me,1,c['comparison']['cutoff'])
            self.assertEqual(int(s.h1.sum()),1); self.assertEqual(int(base.h3.sum()),1)
            x,y,_=match(a.sample(frac=1,random_state=2),b,c)
            pd.testing.assert_frame_equal(x,mf); pd.testing.assert_frame_equal(y,me)

    def test_cluster_bootstrap_pair_weighting_and_holm_family(self):
        draws,n=cluster_bootstrap(np.array([[0.],[1.],[1.]]),['a','b','b'],4000,19)
        self.assertEqual(n,2)
        self.assertEqual(set(draws[:,0]),{0.,2/3,1.})
        self.assertAlmostEqual(float(np.mean(draws[:,0]==2/3)),.5,delta=.03)
        h=holm_prespecified([('one',.01),('two',None),('three',.04)])
        self.assertAlmostEqual(h[0]['holm_p_value'],.03); self.assertAlmostEqual(h[2]['holm_p_value'],.08)
        self.assertIsNone(h[1]['holm_p_value']); self.assertEqual(h[1]['family_size'],3)

    def test_independent_hand_event_sequence(self):
        # Same-day second family cannot establish; new field on establishment day cannot expand.
        offsets=np.array([0,5],np.int64); days=np.array([10,10,20,20,21],np.int32)
        masks=np.array([2,2,2,4,8],np.uint64); focal=np.array([1],np.int16)
        np.testing.assert_array_equal(score(offsets,days,masks,focal,0),[[1,1,1]])
        np.testing.assert_array_equal(score(np.array([0,4]),days[:4],masks[:4],focal,0),[[1,1,0]])
        np.testing.assert_array_equal(score(np.array([0,2]),days[:2],masks[:2],focal,0),[[1,0,0]])

    def test_adapter_lineage_hash_and_float_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); manifest,config=generate(root/'raw',clusters=2,pairs_per_cluster=2,deterministic=True)
            a=prepare(manifest,root/'raw/prepared')
            self.assertEqual(a['families'],8); self.assertEqual(a['events'],24); self.assertEqual(a['duplicate_citation_records'],1)
            self.assertTrue((root/'raw/prepared/classification_lineage.csv').exists())
            f=pd.read_parquet(root/'raw/prepared/families.parquet'); self.assertEqual(f.grant_date.min(),pd.Timestamp('2010-01-01'))
            with (root/'raw/applications.csv').open('a') as stream: stream.write('\n')
            with self.assertRaisesRegex(ValueError,'hash mismatch'): prepare(manifest,root/'tampered')

    def test_reference_support_folds_and_exact_constant_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); manifest,config=generate(root/'raw',deterministic=True)
            prepare(manifest,root/'raw/prepared'); c=resolve(json.loads(config.read_text()))
            f,e=load(root/'raw/prepared/families.parquet',root/'raw/prepared/events.parquet',c)
            mf,me,_=match(f,e,c); _,b,eb,_=window(mf,me,1,c['comparison']['cutoff'])
            r,p,ref=run_variant(b,eb,c,'main',1)
            self.assertEqual(r['support']['pairs_retained'],160); self.assertEqual(r['status'],'OK')
            for pool in r['support']['pools']:
                self.assertNotIn(pool['target_fold'],pool['donor_folds'])
                self.assertGreaterEqual(pool['donor_edges'],200); self.assertGreaterEqual(pool['distinct_citing_families'],50)
            for h in ['H3','H4','H5']:
                self.assertEqual(r['outcomes'][h]['residual_difference_pp'],0.)
                self.assertEqual(r['outcomes'][h]['mcse_pp'],0.)
            self.assertEqual(r['outcomes']['H4']['group_a_reference_rate'],1.)
            self.assertEqual(r['outcomes']['H5']['group_a_reference_rate'],0.)
            shuffled=plan(b.sample(frac=1,random_state=3),eb.sample(frac=1,random_state=4),c,'main',1)
            np.testing.assert_array_equal(p['pool_ids'],shuffled['pool_ids'])
            _,failed=weighted_cdf(p,np.zeros(p['cell_count'],int))
            self.assertEqual(failed,[]) # no positively weighted targets
            weights=np.ones(p['cell_count'],int); cdf,failed=weighted_cdf(p,weights)
            self.assertEqual(failed,[]); np.testing.assert_array_equal(cdf,p['cdf'])
            few=eb.iloc[:20].copy(); small=plan(b,few,c,'main',1)
            self.assertGreater(small['support']['pairs_excluded'],0)
            self.assertEqual(small['support']['pools'],[])


if __name__=='__main__': unittest.main()
