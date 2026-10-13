import json
from pathlib import Path
import tempfile
import unittest
import pandas as pd
from patent_diffusion.compare import prepare, neutral, run
from patent_diffusion._diagnostics import third_family_by_field
from patent_diffusion.demo import write_demo_inputs


class PortableTests(unittest.TestCase):
    def test_third_family_respects_tied_first_date(self):
        e=pd.DataFrame({'focus_docdb_family_id':['f']*4,'citing_docdb_family_id':['a','b','c','d'],
          'edge_event_date':pd.to_datetime(['2020-01-01']*3+['2020-01-02']),
          'focal_wipo35_field_nr':[1]*4,'citing_wipo35_mask':[2]*4,'citing_wipo35_missing':[False]*4})
        self.assertTrue(third_family_by_field(e.iloc[:3]).empty)
        self.assertEqual(third_family_by_field(e).iloc[0].third_family_date,pd.Timestamp('2020-01-02'))

    def test_neutral_names_preserve_pairs(self):
        self.assertEqual(neutral({'pairs_total':2,'raw_rate_ai':.5,'raw_rate_nonai':.4}),
                         {'pairs_total':2,'raw_rate_group_a':.5,'raw_rate_group_b':.4})

    def test_country_and_technology_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fp,ep=write_demo_inputs(root/'source')
            f=pd.read_parquet(fp).rename(columns={'docdb_family_id':'family_id','focus_grant_date':'grant_date','wipo35_field_nr':'focal_field'})
            f['group']=f.ai_indicator.map({1:'A',0:'B'})
            e=pd.read_parquet(ep).rename(columns={'focus_docdb_family_id':'family_id','citing_docdb_family_id':'citing_family_id','edge_event_date':'event_date','citing_wipo35_mask':'field_mask','citing_wipo35_missing':'classification_missing'})
            f.to_parquet(root/'f.parquet');e.to_parquet(root/'e.parquet')
            c={'groups':['A','B'],'comparison_type':'country','country_basis':'applicant','group_definition':'Synthetic applicant-country labels','cutoff':'2026-06-30','windows':[1],'matching_columns':['grant_quarter','focal_field']}
            a,b,audit=prepare(root/'f.parquet',root/'e.parquet',c)
            self.assertEqual(a.groupby('match_id').size().unique().tolist(),[2])
            self.assertEqual(a.groupby('match_id').wipo35_field_nr.nunique().max(),1)
            c['comparison_type']='technology';c['group_definition']='Synthetic route labels'
            (root/'config.json').write_text(json.dumps(c))
            result=run(root/'f.parquet',root/'e.parquet',root/'config.json',root/'out')
            self.assertEqual(result['1']['status'],'COMPUTED')
            self.assertTrue((root/'out/report.html').exists())
            c['comparison_type']='country';c.pop('country_basis')
            with self.assertRaisesRegex(ValueError,'Country basis'):prepare(root/'f.parquet',root/'e.parquet',c)

    def test_no_common_field_support(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            pd.DataFrame({'family_id':['a','b'],'grant_date':['2020-02-29']*2,'focal_field':[1,2],'group':['A','B']}).to_csv(root/'f.csv',index=False)
            pd.DataFrame({'family_id':['a'],'citing_family_id':['c'],'event_date':['2021-02-28'],'field_mask':[2],'classification_missing':[False]}).to_csv(root/'e.csv',index=False)
            c={'groups':['A','B'],'comparison_type':'technology','group_definition':'routes','cutoff':'2026-06-30','windows':[1]}
            with self.assertRaisesRegex(ValueError,'No exact common-support'):prepare(root/'f.csv',root/'e.csv',c)


if __name__=='__main__':unittest.main()
