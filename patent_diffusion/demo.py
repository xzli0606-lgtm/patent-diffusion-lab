"""Deterministic synthetic demonstration; contains no source-study records."""
import json
from pathlib import Path

import numpy as np
import pandas as pd


def make_demo_frames(seed=20261009, pairs=400):
    """Create a cohort large enough to exercise the frozen donor-pool thresholds."""
    rng = np.random.default_rng(seed)
    families, edges = [], []
    for pair in range(pairs):
        quarter = pair % 8
        grant = pd.Timestamp("2019-01-01") + pd.DateOffset(months=3 * quarter)
        field = 1 + pair % 2
        cpc = ("G06F", "H04L", "G06N")[pair % 3]
        for ai in (0, 1):
            family = f"synthetic-f-{pair:04d}-{ai}"
            families.append({"match_id": f"synthetic-p-{pair:04d}", "ai_indicator": ai,
                "docdb_family_id": family, "focus_grant_date": grant,
                "grant_quarter": str(grant.to_period("Q")), "primary_cpc4": cpc,
                "wipo35_field_nr": field, "matching_cell": f"{grant.to_period('Q')}|{cpc}"})
            if rng.random() > .76 + .05 * ai:
                continue
            count = int(rng.integers(2, 9))
            days = np.sort(np.clip(rng.exponential(330, count).astype(int) + 1, 1, 1790))
            for j, day in enumerate(days):
                receiving = int(rng.choice([field, 3, 4, 5], p=[.30, .30, .25, .15]))
                mask = 1 << (receiving - 1)
                if rng.random() < .15:
                    mask |= 1 << (int(rng.integers(1, 6)) - 1)
                edges.append({"focus_docdb_family_id": family,
                    "citing_docdb_family_id": f"synthetic-c-{pair:04d}-{ai}-{j}",
                    "edge_event_date": grant + pd.Timedelta(days=int(day)),
                    "focal_wipo35_field_nr": field, "citing_wipo35_mask": mask,
                    "citing_wipo35_missing": False})
    return pd.DataFrame(families), pd.DataFrame(edges)


def write_demo_inputs(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    families, edges = make_demo_frames()
    fp, ep = directory / "families.parquet", directory / "edges.parquet"
    families.to_parquet(fp, index=False)
    edges.to_parquet(ep, index=False)
    (directory / "DATA_ORIGIN.json").write_text(json.dumps({
        "kind": "synthetic", "seed": 20261009, "pairs": 400,
        "source": "patent_diffusion.demo.make_demo_frames",
        "note": "Artificial identifiers, dates and classifications. No PATSTAT or study records."}, indent=2), encoding="utf-8")
    return fp, ep
