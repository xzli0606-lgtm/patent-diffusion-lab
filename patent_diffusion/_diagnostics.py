"""Supplementary event functions; extracted without archived result readers."""
import numpy as np
import pandas as pd

def third_family_by_field(edges):
    e = edges.loc[~edges.citing_wipo35_missing]
    masks = e.citing_wipo35_mask.to_numpy(dtype=np.uint64)
    focal = e.focal_wipo35_field_nr.to_numpy(dtype=np.int16)
    parts = []
    for field in range(1, 36):
        hit = (((masks >> np.uint64(field - 1)) & np.uint64(1)) == 1) & (focal != field)
        if hit.any():
            p = e.loc[hit, ["focus_docdb_family_id", "citing_docdb_family_id", "edge_event_date"]].copy()
            p["receiving_field"] = np.int8(field)
            parts.append(p)
    if not parts:
        return pd.DataFrame(columns=["focus_docdb_family_id", "third_family_date"])
    keys = ["focus_docdb_family_id", "receiving_field"]
    long = pd.concat(parts, ignore_index=True).drop_duplicates(keys + ["citing_docdb_family_id"])
    dates = long.groupby(keys + ["edge_event_date"], sort=True).size().rename("families_on_date").reset_index()
    dates = dates.sort_values(keys + ["edge_event_date"])
    dates["date_order"] = dates.groupby(keys, sort=False).cumcount()
    dates["families_so_far"] = dates.groupby(keys, sort=False).families_on_date.cumsum()
    h4_field = dates.loc[dates.date_order.eq(1), keys + ["edge_event_date"]].rename(
        columns={"edge_event_date": "h4_field_date"})
    dates = dates.merge(h4_field, on=keys, how="left")
    eligible = dates.loc[dates.families_so_far.ge(3) &
                         dates.edge_event_date.ge(dates.h4_field_date)]
    return eligible.groupby("focus_docdb_family_id", sort=False).edge_event_date.min().rename(
        "third_family_date").reset_index()

def field_histories(edges):
    e = edges.loc[~edges.citing_wipo35_missing]
    masks = e.citing_wipo35_mask.to_numpy(dtype=np.uint64)
    focal = e.focal_wipo35_field_nr.to_numpy(dtype=np.int16)
    parts = []
    for field in range(1, 36):
        hit = (((masks >> np.uint64(field - 1)) & np.uint64(1)) == 1) & (focal != field)
        if hit.any():
            p = e.loc[hit, ["focus_docdb_family_id", "citing_docdb_family_id", "edge_event_date"]].copy()
            p["receiving_field"] = np.int8(field)
            parts.append(p)
    if not parts:
        return pd.DataFrame(columns=["focus_docdb_family_id", "field", "field_arrival", "field_h4"]), 0
    keys = ["focus_docdb_family_id", "receiving_field"]
    long = pd.concat(parts, ignore_index=True)
    before = len(long)
    long = long.sort_values("edge_event_date").drop_duplicates(keys + ["citing_docdb_family_id"])
    duplicate_projections = before - len(long)
    dates = long.drop_duplicates(keys + ["edge_event_date"]).sort_values(keys + ["edge_event_date"])
    dates["date_order"] = dates.groupby(keys, sort=False).cumcount()
    arrival = dates.loc[dates.date_order.eq(0), keys + ["edge_event_date"]].rename(
        columns={"edge_event_date": "field_arrival"})
    h4 = dates.loc[dates.date_order.eq(1), keys + ["edge_event_date"]].rename(
        columns={"edge_event_date": "field_h4"})
    return arrival.merge(h4, on=keys, how="left").rename(columns={"receiving_field": "field"}), duplicate_projections

def quantiles(values):
    x = pd.Series(values).dropna()
    if x.empty:
        return {"n": 0, "q25": None, "median": None, "q75": None, "p90": None}
    return {"n": int(len(x)), "q25": float(x.quantile(.25)), "median": float(x.median()),
            "q75": float(x.quantile(.75)), "p90": float(x.quantile(.90))}

def state_occupancy(frame):
    rows=[]
    for frac in [.25,.5,.75,1.0]:
        cutoff=frame.focus_grant_date+(frame.horizon_end-frame.focus_grant_date)*frac
        arr=frame.arrival_date.notna() & frame.arrival_date.le(cutoff)
        est=frame.establishment_date.notna() & frame.establishment_date.le(cutoff)
        exp=frame.expansion_date.notna() & frame.expansion_date.le(cutoff)
        state=np.select([~arr,arr&~est,est&~exp,exp],["S0","S1","S2","S3"])
        for ai in [0,1]:
            s=pd.Series(state[frame.ai_indicator.eq(ai).to_numpy()]).value_counts(normalize=True)
            rows.append({"fraction_of_horizon":frac,"ai_indicator":ai,**{k:float(s.get(k,0)) for k in ["S0","S1","S2","S3"]}})
    return rows

