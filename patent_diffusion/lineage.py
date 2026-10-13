"""Count supplied source records; no account, network, or target-result access."""
from pathlib import Path
import pandas as pd
from .reproduce import write


def count(root):
    root = Path(root)
    def table(name):
        return pd.read_parquet(root / 'inputs' / ('source_' + name + '.parquet'))
    roster = table('ai_roster')
    mapping = table('mapping')
    early = table('pre2019')
    ai = table('eligible_ai')
    nonai = table('eligible_nonai')
    missing = table('missing_ai_cpc')
    matched = pd.read_parquet(root / 'inputs/families.parquet')
    if ai.docdb_family_id.duplicated().any() or nonai.docdb_family_id.duplicated().any():
        raise ValueError('Duplicate eligible source family')
    if set(nonai.docdb_family_id) & set(mapping.docdb_family_id):
        raise ValueError('Known AI family in non-AI source pool')
    if set(ai.docdb_family_id) != set(mapping.docdb_family_id) - set(early.docdb_family_id):
        raise ValueError('AI eligibility lineage does not reconcile')
    if not set(missing.docdb_family_id).issubset(set(ai.docdb_family_id)):
        raise ValueError('Missing-CPC family outside AI eligibility roster')
    source = roster.ai_label_source.fillna('').astype(str)
    unmatched = set(ai.docdb_family_id) - set(matched.docdb_family_id) - set(missing.docdb_family_id)
    counts = {
        'aipd_ai_grants': int(source.str.contains('AIPD', case=False).sum()),
        'aipat_ai_grants': int(source.str.contains('AIPat', case=False).sum()),
        'ai_grants_before_type_exclusion': len(roster),
        'reissue_excluded': int(roster.patent_id.str.startswith('RE').sum()),
        'mapped_ai_records': len(mapping),
        'mapped_ai_families': int(mapping.docdb_family_id.nunique()),
        'pre2019_ai_families_excluded': int(early.docdb_family_id.nunique()),
        'eligible_ai_families': len(ai), 'non_ai_pool': len(nonai),
        'missing_ai_primary_cpc4': len(missing), 'ai_no_common_support': len(unmatched),
    }
    write(root / 'outputs/reused_source_counts.json', {
        'counts': counts,
        'scope': 'Counts from supplied historical source records; database retrieval and original matching are not rerun',
    })
