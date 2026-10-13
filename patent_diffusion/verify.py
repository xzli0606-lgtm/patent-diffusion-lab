"""Read targets only after computation, and retain every failed/missing item."""
import argparse
from pathlib import Path
import pandas as pd
from .reproduce import write


def verify(root, targets):
    root = Path(root)
    t = pd.read_json(targets) if Path(targets).suffix == '.json' else pd.read_csv(targets)
    a = pd.read_csv(root / 'validation_actual.csv')
    result = t.merge(a, on='actual_key', how='left', validate='many_to_one')
    result['difference'] = result.actual_value - result.target_value
    result['status'] = 'PASS'
    result.loc[result.difference.abs() > result.absolute_tolerance + 1e-12, 'status'] = 'FAIL'
    result.loc[result.actual_value.isna(), 'status'] = 'MISSING'
    result.to_csv(root / 'validation_report.csv', index=False, encoding='utf-8-sig')
    counts = {str(k): int(v) for k, v in result.status.value_counts().items()}
    write(root / 'validation_summary.json', {
        'counts': counts, 'all_listed_targets_pass': bool(result.status.eq('PASS').all()),
        'scope': 'Listed numeric targets only; source provenance, narrative coverage and redistribution are separate audits',
    })
    return counts


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--targets', type=Path, required=True)
    a = p.parse_args()
    counts = verify(a.output, a.targets)
    print(counts)
    if counts.get('FAIL', 0) or counts.get('MISSING', 0):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
