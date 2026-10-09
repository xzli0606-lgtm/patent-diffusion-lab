"""Study algorithms extracted for the local prototype; see PROVENANCE.json."""
import math
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.duration.hazard_regression import PHReg
Z975=1.959963984540054

def effect_result(label, effect_type, beta, se, extra):
    z = beta / se
    out = {
        "label": label, "effect_type": effect_type,
        "estimate": math.exp(beta), "log_effect": beta, "se_cluster": se,
        "ci95_low": math.exp(beta - Z975 * se), "ci95_high": math.exp(beta + Z975 * se),
        "p_two_sided": float(2 * stats.norm.sf(abs(z))),
        "cluster_covariance": "model bread x matching-cell summed score outer-product meat x model bread; no small-sample scaling",
    }
    out.update(extra)
    return out

def conditional_binary(frame, outcome, label):
    wide = frame.pivot(index="match_id", columns="ai_indicator", values=outcome)
    cells = frame.drop_duplicates("match_id").set_index("match_id")["matching_cell"]
    used = wide.loc[wide[0].ne(wide[1])]
    b = int(((used[1] == 1) & (used[0] == 0)).sum())
    c = int(((used[1] == 0) & (used[0] == 1)).sum())
    if not b or not c:
        raise RuntimeError(f"finite conditional estimate unavailable: {label}")
    beta = math.log(b / c)
    p = b / (b + c)
    score = used[1].astype(float) - p
    cs = score.groupby(cells.loc[used.index], observed=True).sum()
    bread = 1.0 / (len(used) * p * (1 - p))
    se = math.sqrt(bread * bread * float((cs ** 2).sum()))
    return effect_result(label, "conditional_OR", beta, se, {
        "pairs_total": int(len(wide)), "pairs_informative": int(len(used)),
        "discordant_ai_one_control_zero": b, "discordant_ai_zero_control_one": c,
        "both": int(((wide[1] == 1) & (wide[0] == 1)).sum()),
        "neither": int(((wide[1] == 0) & (wide[0] == 0)).sum()),
        "raw_rate_ai": float(frame.loc[frame.ai_indicator.eq(1), outcome].mean()),
        "raw_rate_nonai": float(frame.loc[frame.ai_indicator.eq(0), outcome].mean()),
        "absolute_rate_difference": float(frame.loc[frame.ai_indicator.eq(1), outcome].mean() - frame.loc[frame.ai_indicator.eq(0), outcome].mean()),
    })

def conditional_count(frame, outcome, label):
    wide = frame.pivot(index="match_id", columns="ai_indicator", values=outcome).astype(float)
    cells = frame.drop_duplicates("match_id").set_index("match_id")["matching_cell"]
    total = wide[0] + wide[1]
    used = wide.loc[total.gt(0)]
    used_total = total.loc[used.index]
    ai_total, co_total = float(used[1].sum()), float(used[0].sum())
    if ai_total <= 0 or co_total <= 0:
        raise RuntimeError(f"finite conditional count estimate unavailable: {label}")
    beta = math.log(ai_total / co_total)
    p = ai_total / (ai_total + co_total)
    score = used[1] - used_total * p
    cs = score.groupby(cells.loc[used.index], observed=True).sum()
    bread = 1.0 / float((used_total * p * (1 - p)).sum())
    se = math.sqrt(bread * bread * float((cs ** 2).sum()))
    return effect_result(label, "conditional_count_ratio", beta, se, {
        "pairs_total": int(len(wide)), "pairs_informative": int(len(used)),
        "total_count_ai": int(wide[1].sum()), "total_count_nonai": int(wide[0].sum()),
        "raw_mean_ai": float(wide[1].mean()), "raw_mean_nonai": float(wide[0].mean()),
    })

def fit_cox(frame, date_col, label):
    x = frame.sort_values(["match_id", "ai_indicator"], kind="stable").reset_index(drop=True)
    event = x[date_col].notna() & x[date_col].le(x["horizon_end"])
    stop = x[date_col].where(event, x["horizon_end"])
    x["duration"] = (stop - x["focus_grant_date"]).dt.days + 1
    x["event"] = event.astype(int)
    model = PHReg(x["duration"].to_numpy(float), x[["ai_indicator"]].to_numpy(float),
                  status=x["event"].to_numpy(int), strata=x["match_id"].astype(str).to_numpy(), ties="efron")
    result = model.fit(disp=False)
    beta = float(result.params[0])
    bread = float(np.asarray(result.cov_params())[0, 0])
    sr = np.asarray(result.score_residuals)[:, 0]
    nonfinite = int((~np.isfinite(sr)).sum())
    sr = np.where(np.isfinite(sr), sr, 0.0)
    cs = pd.Series(sr).groupby(x["matching_cell"].astype(str), observed=True).sum()
    se = math.sqrt(bread * bread * float((cs ** 2).sum()))
    sch = np.asarray(result.schoenfeld_residuals)[:, 0]
    ok = x["event"].eq(1).to_numpy() & np.isfinite(sch)
    scaled = sch[ok] * bread * int(ok.sum())
    ranks = stats.rankdata(x.loc[ok, "duration"].to_numpy(float), method="average") / (ok.sum() + 1.0)
    ph_r, ph_p = stats.pearsonr(ranks, scaled) if np.std(scaled) and np.std(ranks) else (0.0, 1.0)
    return effect_result(label, "stratified_Cox_HR", beta, se, {
        "rows": int(len(x)), "pairs": int(x.match_id.nunique()), "events": int(x.event.sum()),
        "ties": "efron", "score_residual_nonfinite_as_zero": nonfinite,
        "ph_diagnostic": {"correlation": float(ph_r), "p_two_sided": float(ph_p), "trigger_piecewise": bool(ph_p < 0.05)},
    })

def holm(items):
    order = sorted(range(len(items)), key=lambda i: items[i][1])
    adj = [None] * len(items); running = 0.0; n = len(items)
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (n - rank) * items[idx][1])); adj[idx] = running
    return [{"label": x[0], "raw_p_two_sided": float(x[1]), "holm_adjusted_p": float(a)} for x, a in zip(items, adj)]

def milestones(edges, allow_same_day=False, unique_field_only=False, cross_only=False, gap_days=0):
    e = edges.loc[~edges.citing_wipo35_missing].copy()
    if unique_field_only:
        e = e.loc[e.citing_wipo35_mask.map(lambda x: int(x).bit_count()).eq(1)]
    if cross_only:
        masks_for_filter = e.citing_wipo35_mask.to_numpy(dtype=np.uint64)
        focal_bits = np.array(
            [np.uint64(1) << np.uint64(int(value) - 1) for value in e.focal_wipo35_field_nr],
            dtype=np.uint64,
        )
        e = e.loc[(masks_for_filter & focal_bits) == np.uint64(0)]
    parts=[]; masks=e.citing_wipo35_mask.to_numpy(np.uint64); focal=e.focal_wipo35_field_nr.to_numpy(np.int16)
    for field in range(1,36):
        hit=(((masks >> np.uint64(field-1)) & np.uint64(1)) == 1) & (focal != field)
        if hit.any():
            z=e.loc[hit,["focus_docdb_family_id","citing_docdb_family_id","edge_event_date"]].copy(); z["receiving_field"]=np.int8(field); parts.append(z)
    cols=["focus_docdb_family_id","arrival_date","establishment_date","expansion_date","established_field_count","new_field_count"]
    if not parts: return pd.DataFrame(columns=cols)
    long=pd.concat(parts,ignore_index=True).drop_duplicates(["focus_docdb_family_id","receiving_field","citing_docdb_family_id"])
    first=long.groupby(["focus_docdb_family_id","receiving_field"],sort=False).edge_event_date.min().rename("arrival_date")
    if gap_days:
        first_frame = first.reset_index()
        ordered = long.merge(first_frame, on=["focus_docdb_family_id", "receiving_field"], how="left")
        ordered = ordered.loc[(ordered.edge_event_date - ordered.arrival_date).dt.days.ge(gap_days)]
        second = ordered.groupby(["focus_docdb_family_id", "receiving_field"], sort=False).edge_event_date.min().rename("establishment_date")
    elif allow_same_day:
        ordered=long.sort_values(["focus_docdb_family_id","receiving_field","edge_event_date","citing_docdb_family_id"])
        ordered["ord"]=ordered.groupby(["focus_docdb_family_id","receiving_field"],sort=False).cumcount()
        second=ordered.loc[ordered.ord.eq(1)].set_index(["focus_docdb_family_id","receiving_field"]).edge_event_date.rename("establishment_date")
    else:
        ordered=long.drop_duplicates(["focus_docdb_family_id","receiving_field","edge_event_date"]).sort_values(["focus_docdb_family_id","receiving_field","edge_event_date"])
        ordered["ord"]=ordered.groupby(["focus_docdb_family_id","receiving_field"],sort=False).cumcount()
        second=ordered.loc[ordered.ord.eq(1)].set_index(["focus_docdb_family_id","receiving_field"]).edge_event_date.rename("establishment_date")
    field=pd.concat([first,second],axis=1).reset_index()
    est=field.groupby("focus_docdb_family_id",sort=False).establishment_date.min().rename("establishment_date")
    established_count=field.loc[field.establishment_date.notna()].groupby("focus_docdb_family_id").size().rename("established_field_count")
    field=field.merge(est,left_on="focus_docdb_family_id",right_index=True,how="inner",suffixes=("_field",""))
    after=field.loc[field.arrival_date.gt(field.establishment_date)]
    if gap_days: after=after.loc[(after.arrival_date-after.establishment_date).dt.days >= gap_days]
    expansion=after.groupby("focus_docdb_family_id").arrival_date.min().rename("expansion_date")
    new_count=after.groupby("focus_docdb_family_id").size().rename("new_field_count")
    arrival=first.groupby("focus_docdb_family_id").min().rename("arrival_date")
    return pd.concat([arrival,est,expansion,established_count,new_count],axis=1).fillna({"established_field_count":0,"new_field_count":0}).reset_index()
