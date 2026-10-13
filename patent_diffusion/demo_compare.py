"""Create synthetic portable inputs, with no real patent identifiers."""
import argparse
import json
from pathlib import Path
from .demo import make_demo_frames


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    out=p.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    f,e=make_demo_frames()
    f=f.rename(columns={'docdb_family_id':'family_id','focus_grant_date':'grant_date','wipo35_field_nr':'focal_field'})
    f['group']=f.ai_indicator.map({1:'Route A',0:'Route B'})
    f[['family_id','grant_date','focal_field','group']].to_csv(out/'families.csv',index=False)
    e=e.rename(columns={'focus_docdb_family_id':'family_id','citing_docdb_family_id':'citing_family_id','edge_event_date':'event_date','citing_wipo35_mask':'field_mask','citing_wipo35_missing':'classification_missing'})
    e[['family_id','citing_family_id','event_date','field_mask','classification_missing']].to_csv(out/'events.csv',index=False)
    c={'comparison_type':'technology','groups':['Route A','Route B'],'group_definition':'Synthetic example, not real patents','cutoff':'2026-06-30','windows':[1,3,5]}
    (out/'comparison.json').write_text(json.dumps(c,indent=2))


if __name__=='__main__':main()
