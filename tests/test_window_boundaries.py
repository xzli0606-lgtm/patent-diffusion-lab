import unittest
import pandas as pd
from patent_diffusion import study


class WindowBoundaryTests(unittest.TestCase):
    def test_leap_anniversary_zero_citations_and_pair_exclusion(self):
        study.C={'citation_cutoff':'2021-02-28'}
        f=pd.DataFrame({'docdb_family_id':['a','b','c','d'], 'match_id':['p','p','q','q'],
                        'ai_indicator':[1,0,1,0], 'wipo35_field_nr':[1]*4,
                        'focus_grant_date':pd.to_datetime(['2020-02-29','2020-02-29','2020-02-29','2020-03-01'])})
        e=pd.DataFrame({'focus_docdb_family_id':['a','a'], 'citing_docdb_family_id':['x','y'],
                        'edge_event_date':pd.to_datetime(['2021-02-28','2021-03-01']),
                        'focal_wipo35_field_nr':[1,1], 'citing_wipo35_mask':[2,2],
                        'citing_wipo35_missing':[False,False]})
        s,b,_,_=study.window_frame(f,e,1,check_global=False)
        self.assertEqual(set(s.docdb_family_id),{'a','b'})
        self.assertEqual(s.set_index('docdb_family_id').h1.to_dict(),{'a':1,'b':0})
        self.assertEqual(b.set_index('docdb_family_id').h4.to_dict(),{'a':0,'b':0})
        e.loc[0,'citing_wipo35_missing']=True
        s,b,_,_=study.window_frame(f,e,1,check_global=False)
        self.assertEqual(len(s),2)
        self.assertTrue(b.empty)

    def test_establishment_day_new_field_is_not_fourth_milestone(self):
        from patent_diffusion._study import milestones
        e=pd.DataFrame({'focus_docdb_family_id':['f']*4,'citing_docdb_family_id':['a','b','c','d'],
                        'edge_event_date':pd.to_datetime(['2020-01-01','2020-01-02','2020-01-02','2020-01-03']),
                        'focal_wipo35_field_nr':[1]*4,'citing_wipo35_mask':[2,2,12,4],
                        'citing_wipo35_missing':[False]*4})
        r=milestones(e).iloc[0]
        self.assertEqual(r.establishment_date,pd.Timestamp('2020-01-02'))
        self.assertTrue(pd.isna(r.expansion_date))
        self.assertEqual(r.established_field_count,2)


if __name__=='__main__':unittest.main()
