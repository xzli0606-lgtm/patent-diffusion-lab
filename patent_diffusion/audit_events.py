"""Independent chronological scanner for full-sample milestone-date validation.

This verifier does not call either production milestone implementation.
"""
import argparse
from pathlib import Path
import pandas as pd
from .reproduce import write


def scan(edges):
    result = {}
    ordered = edges.sort_values(['focus_docdb_family_id','edge_event_date','citing_docdb_family_id'])
    columns=['focus_docdb_family_id','citing_docdb_family_id','edge_event_date',
             'focal_wipo35_field_nr','citing_wipo35_mask','citing_wipo35_missing']
    current=None
    for family,citing,date,focal,mask,missing in ordered[columns].itertuples(index=False,name=None):
        if family!=current:
            current=family; first={}; second=None; fourth=None; arrival=None
            result[family]=[date,None,None,None]
        if missing:
            continue
        fields=int(mask) & ~(1 << (int(focal)-1))
        while fields:
            bit=fields & -fields; fields-=bit
            if bit not in first:
                first[bit]=(date,citing)
                if arrival is None: arrival=date
                if second is not None and date>second and fourth is None: fourth=date
            elif citing!=first[bit][1] and date>first[bit][0]:
                if second is None: second=date
        result[family][1:]=[arrival,second,fourth]
    return pd.DataFrame.from_dict(result,orient='index',columns=[
        'first_citation_date','arrival_date','establishment_date','expansion_date'])


def audit(root):
    root=Path(root)
    e=pd.read_parquet(root/'inputs/edges.parquet')
    if e.duplicated(['focus_docdb_family_id','citing_docdb_family_id']).any():
        raise ValueError('Duplicate family edge')
    expected=scan(e)
    actual=pd.read_parquet(root/'outputs/milestone_events.parquet').set_index('docdb_family_id')
    expected=expected.reindex(actual.index)
    mismatches={}
    for c in expected:
        left=pd.to_datetime(expected[c]); right=pd.to_datetime(actual[c])
        mismatches[c]=int((~(left.eq(right)|(left.isna()&right.isna()))).sum())
    windows={}
    for y in [1,3,5]:
        frame=pd.read_parquet(root/f'outputs/h45_family_outcomes_{y}Y.parquet').set_index('docdb_family_id')
        counts={}
        for h,c in zip(['h1','h3','h4','h5'],expected.columns):
            rebuilt=pd.to_datetime(expected.loc[frame.index,c]).le(frame.horizon_end).astype('int8')
            counts[h]=int(rebuilt.ne(frame[h]).sum())
        windows[str(y)]=counts
    report={'families':len(actual),'edges':len(e),'date_mismatches':mismatches,
            'window_indicator_mismatches':windows,
            'status':'PASS' if not any(mismatches.values()) and not any(v for w in windows.values() for v in w.values()) else 'FAIL'}
    write(root/'independent_event_audit.json',report)
    if report['status']!='PASS':raise RuntimeError('Independent event audit failed')
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    print(audit(p.parse_args().output))


if __name__=='__main__':main()
