"""Full-study analysis from supplied inputs. No historical output lookup."""
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import optimize, special
from . import _study as H, _piecewise as P, _diagnostics as D, _diagnostics as T, _reference

ROOT = None
C = None
INPUTS = None

def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=lambda x: x.item())+'\n', encoding='utf-8')

def inputs():
    return INPUTS

def configure(root, families, edges, config):
    global ROOT, C, INPUTS
    ROOT, C = Path(root), config
    INPUTS = {'families': Path(families), 'edges': Path(edges)}
    for folder in ['outputs', 'outputs/sensitivity', 'outputs/model_results']:
        (ROOT/folder).mkdir(parents=True, exist_ok=True)

def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)

def load():
    paths = inputs()
    f = pd.read_parquet(paths["families"])
    e = pd.read_parquet(paths["edges"])
    return f, e

def stage4(smoke=0):
    f, e = load()
    if smoke:
        ids = set(sorted(f.match_id.unique())[:smoke])
        f = f.loc[f.match_id.isin(ids)].copy()
        e = e.loc[e.focus_docdb_family_id.isin(f.docdb_family_id)].copy()
    m = H.milestones(e)
    first = e.groupby("focus_docdb_family_id").edge_event_date.min()
    f = f.drop(columns=["first_citation_date"], errors="ignore").merge(m, left_on="docdb_family_id", right_on="focus_docdb_family_id", how="left", validate="one_to_one")
    f["first_citation_date"] = f.docdb_family_id.map(first)
    for col in ["established_field_count", "new_field_count"]:
        f[col] = f[col].fillna(0).astype(int)
    require((f.establishment_date.isna() | f.establishment_date.gt(f.arrival_date)).all(), "Establishment not strictly after arrival")
    require((f.expansion_date.isna() | f.expansion_date.gt(f.establishment_date)).all(), "New-field arrival not strictly after establishment")
    p = ROOT / ("outputs/smoke/milestone_events.parquet" if smoke else "outputs/milestone_events.parquet")
    p.parent.mkdir(parents=True, exist_ok=True)
    f.to_parquet(p, index=False)
    if not smoke:
        field, dup = D.field_histories(e)
        require(dup == 0, "Duplicate family-field projection")
        field.to_parquet(ROOT / "outputs/receiving_field_events.parquet", index=False)
    print("stage4 computed", len(f), "families", flush=True)

def window_frame(f, e, years, check_global=True):
    h = str(years) + "Y"
    cutoff = pd.Timestamp(C["citation_cutoff"])
    complete = (f.focus_grant_date + pd.DateOffset(years=years)).le(cutoff)
    keep = complete.groupby(f.match_id).all()
    sample = f.loc[f.match_id.isin(keep.index[keep])].copy()
    sample["horizon_label"] = h
    sample["horizon_years"] = years
    sample["horizon_end"] = sample.focus_grant_date + pd.DateOffset(years=years)
    cols = ["arrival_date", "establishment_date", "expansion_date", "established_field_count", "new_field_count", "focus_docdb_family_id"]
    sample = sample.drop(columns=cols, errors="ignore")
    end = sample.set_index("docdb_family_id").horizon_end
    ew = e.loc[e.focus_docdb_family_id.isin(end.index)].copy()
    ew = ew.loc[ew.edge_event_date.le(ew.focus_docdb_family_id.map(end))].copy()
    counts = ew.groupby("focus_docdb_family_id").size()
    sample["citation_count"] = sample.docdb_family_id.map(counts).fillna(0).astype(int)
    sample["h1"] = sample.citation_count.gt(0).astype(np.int8)
    missing = ew.groupby("focus_docdb_family_id").citing_wipo35_missing.any()
    sample["classification_complete_family"] = ~sample.docdb_family_id.map(missing).fillna(False).astype(bool)
    pc = sample.groupby("match_id").classification_complete_family.all()
    sample["classification_complete_pair"] = sample.match_id.map(pc)
    group_missing = ew.groupby(ew.focus_docdb_family_id.map(sample.set_index("docdb_family_id").ai_indicator)).citing_wipo35_missing.mean()
    coverage = 1 - float(ew.citing_wipo35_missing.mean())
    gap = abs(float(group_missing.get(1, 0)) - float(group_missing.get(0, 0)))
    if check_global:
        require(coverage >= .985 and gap < .01, "Candidate edge classification gate failed " + h)
    base = sample.loc[sample.classification_complete_pair].copy()
    eb = ew.loc[ew.focus_docdb_family_id.isin(base.docdb_family_id)].copy()
    base = base.merge(H.milestones(eb), left_on="docdb_family_id", right_on="focus_docdb_family_id", how="left", validate="one_to_one")
    for k, col in [("h3", "arrival_date"), ("h4", "establishment_date"), ("h5", "expansion_date")]:
        base[k] = base[col].notna().astype(np.int8)
    for col in ["established_field_count", "new_field_count"]:
        base[col] = base[col].fillna(0).astype(int)
    audit = {"window": h, "candidate_pairs": int(sample.match_id.nunique()), "classification_complete_pairs": int(base.match_id.nunique()), "candidate_edges": len(ew), "coverage_pct": 100 * coverage, "missing_edge_gap_pp": 100 * gap, "unclassified_edges": int(ew.citing_wipo35_missing.sum())}
    return sample, base, eb, audit

def stage5(smoke=0):
    paths = inputs()
    prefix = "outputs/smoke" if smoke else "outputs"
    f = pd.read_parquet(ROOT / prefix / "milestone_events.parquet")
    e = pd.read_parquet(paths["edges"])
    if smoke:
        # The first 1000 deterministic IDs form a small grant-quarter subset;
        # population coverage thresholds must be checked on the full dataset.
        full = pd.read_parquet(paths["families"])
        meta = full.set_index("docdb_family_id")
        for y in C["horizons"]:
            complete = (full.focus_grant_date + pd.DateOffset(years=y)).le(pd.Timestamp(C["citation_cutoff"]))
            pk = complete.groupby(full.match_id).all()
            ff = full.loc[full.match_id.isin(pk.index[pk])]
            ee = e.loc[e.focus_docdb_family_id.isin(ff.docdb_family_id)]
            ends = ff.set_index("docdb_family_id").focus_grant_date + pd.DateOffset(years=y)
            ee = ee.loc[ee.edge_event_date.le(ee.focus_docdb_family_id.map(ends))]
            coverage = 1 - float(ee.citing_wipo35_missing.mean())
            rates = ee.groupby(ee.focus_docdb_family_id.map(meta.ai_indicator)).citing_wipo35_missing.mean()
            gap = abs(float(rates[1]) - float(rates[0]))
            require(coverage >= .985 and gap < .01, "Full-source classification gate failed before smoke " + str(y))
            print("full-source gate before smoke", y, coverage, gap, flush=True)
    e = e.loc[e.focus_docdb_family_id.isin(f.docdb_family_id)].copy()
    samples, audits = [], []
    for years in C["horizons"]:
        s, b, eb, a = window_frame(f, e, years, check_global=not smoke)
        samples.append(s)
        audits.append(a)
        b.to_parquet(ROOT / prefix / f"h45_family_outcomes_{years}Y.parquet", index=False)
    pd.concat(samples, ignore_index=True).to_parquet(ROOT / prefix / "window_samples.parquet", index=False)
    dump(ROOT / prefix / "window_audit.json", audits)
    print("stage5", audits, flush=True)

def paired_bootstrap(frame, columns, n=2000, seed=None):
    wide = frame.pivot(index="match_id", columns="ai_indicator", values=columns)
    diff = np.column_stack([(wide[col][1] - wide[col][0]).to_numpy(float) for col in columns])
    ci, se = _reference.bootstrap_interval(diff, (C["seeds"]["conditional_bootstrap"] if seed is None else seed), n)
    return {col: {"difference_ci95_pp": [100 * x for x in ci[k]], "bootstrap_se_pp": float(100 * se[k])} for k, col in enumerate(columns)}

def cox(frame, date_col, label):
    # Reset indices before score aggregation: the legacy H45 function groups a
    # default-index score Series against the sorted frame's retained index.
    return H.fit_cox(frame.sort_values(["match_id", "ai_indicator"]).reset_index(drop=True), date_col, label)

def stage6(years, smoke=0):
    h = str(years) + "Y"
    prefix = "outputs/smoke" if smoke else "outputs"
    sample = pd.read_parquet(ROOT / prefix / "window_samples.parquet")
    sample = sample.loc[sample.horizon_label.eq(h)].copy()
    base = pd.read_parquet(ROOT / prefix / f"h45_family_outcomes_{h}.parquet")
    res = {"window": h, "binary": {}, "cox": {}, "piecewise": {}, "count": {}, "state_occupancy": D.state_occupancy(base), "scope": "SMOKE_REAL_SUBSET" if smoke else "FULL_DATA"}
    for name, frame, date_col in [("H1", sample, "first_citation_date"), ("H3", base, "arrival_date"), ("H4", base, "establishment_date"), ("H5", base, "expansion_date")]:
        print(h, name, "conditional logistic", flush=True)
        z = H.conditional_binary(frame, name.lower(), name + "-" + h)
        z.update(paired_bootstrap(frame, [name.lower()], 30 if smoke else C["bootstrap"]["conditional"])[name.lower()])
        res["binary"][name] = z
        print(h, name, "Cox Efron", flush=True)
        res["cox"][name] = cox(frame, date_col, name + "-time-" + h)
        if res["cox"][name]["ph_diagnostic"]["trigger_piecewise"]:
            print(h, name, "PH triggered; piecewise", flush=True)
            res["piecewise"][name] = P.fit(frame, date_col, years, name + "-piecewise-" + h)
    for col in ["established_field_count", "new_field_count"]:
        res["count"][col] = H.conditional_count(base, col, col + "-" + h)
    dump(ROOT / prefix / "model_results" / (h + ".json"), res)
    print("stage6", h, "COMPLETE", flush=True)

def benchmark():
    f, e = load()
    counts = e.groupby("focus_docdb_family_id").size()
    f["count"] = f.docdb_family_id.map(counts).fillna(0).astype(int)
    f["exposure"] = ((pd.Timestamp(C["citation_cutoff"]) - f.focus_grant_date).dt.days + 1) / 365.25
    w = f.pivot(index="match_id", columns="ai_indicator", values=["count", "exposure"])
    total = w["count"][0] + w["count"][1]
    use = total.gt(0)
    a = w["count"][1][use].to_numpy(float)
    n = total[use].to_numpy(float)
    off = np.log((w["exposure"][1] / w["exposure"][0])[use].to_numpy())
    beta = optimize.brentq(lambda x: float((a - n * special.expit(x + off)).sum()), -30, 30, xtol=1e-14)
    prob = special.expit(beta + off)
    score = a - n * prob
    cells = f.drop_duplicates("match_id").set_index("match_id").matching_cell.loc[w.index[use]]
    cs = pd.Series(score, index=cells.index).groupby(cells).sum()
    bread = 1 / float((n * prob * (1 - prob)).sum())
    se = math.sqrt(float((cs ** 2).sum())) * bread
    r = H.effect_result("Cumulative citation intensity", "within_pair_IRR", beta, se, {"pairs": int(len(w)), "informative_pairs": int(use.sum()), "exposure": "inclusive days / 365.25", "sandwich_small_sample_scaling": False})
    dump(ROOT / "outputs/model_results/benchmark.json", r)
    print("benchmark COMPLETE", r, flush=True)

def sensitivity(years):
    h = str(years) + "Y"
    f = pd.read_parquet(ROOT / "outputs/window_samples.parquet")
    e = pd.read_parquet(inputs()["edges"])
    base = pd.read_parquet(ROOT / "outputs" / f"h45_family_outcomes_{h}.parquet")
    eb = e.loc[e.focus_docdb_family_id.isin(base.docdb_family_id)].copy()
    eb = eb.loc[eb.edge_event_date.le(eb.focus_docdb_family_id.map(base.set_index("docdb_family_id").horizon_end))]
    res = {"window": h, "variants": {}, "diagnostics": {}}
    variants = {"main": {}, "pure_cross_field": {"cross_only": True}, "single_field": {"unique_field_only": True}}
    for name, kw in variants.items():
        b = base.drop(columns=["focus_docdb_family_id", "arrival_date", "establishment_date", "expansion_date", "established_field_count", "new_field_count"], errors="ignore")
        b = b.merge(H.milestones(eb, **kw), left_on="docdb_family_id", right_on="focus_docdb_family_id", how="left")
        stats = {}
        for nameh, col in [("H3", "arrival_date"), ("H4", "establishment_date"), ("H5", "expansion_date")]:
            b[nameh.lower()] = b[col].notna().astype(np.int8)
            stats[nameh] = H.conditional_binary(b, nameh.lower(), name + "-" + nameh + "-" + h)
        res["variants"][name] = stats
    third = T.third_family_by_field(eb)
    b = base.merge(third, left_on="docdb_family_id", right_on="focus_docdb_family_id", how="left", suffixes=("", "_third"))
    b["third_family"] = b.third_family_date.notna().astype(np.int8)
    require(b.third_family.le(b.h4).all(), "Third-family endpoint not nested within original establishment")
    require((b.third_family_date.isna() | b.third_family_date.ge(b.establishment_date)).all(), "Third-family date precedes original establishment")
    third_result = H.conditional_binary(b, "third_family", "third-family-" + h)
    third_result.update(paired_bootstrap(b, ["third_family"], seed=C["seeds"]["third_family_bootstrap"])["third_family"])
    res["third_family"] = third_result
    b[["docdb_family_id", "third_family", "third_family_date"]].to_parquet(ROOT / "outputs/sensitivity" / ("third_family_" + h + ".parquet"), index=False)
    fixed = set(f.loc[f.horizon_label.eq("5Y") & f.classification_complete_pair, "match_id"])
    counts = base.citation_count
    cutoff = float(counts.quantile(.99, interpolation="higher"))
    bad = set(base.loc[counts.ge(cutoff), "match_id"])
    for name, b in [("fixed5_cohort", base.loc[base.match_id.isin(fixed)]), ("high_citation_exclusion_top1pct", base.loc[~base.match_id.isin(bad)])]:
        res[name] = {k: H.conditional_binary(b, k.lower(), name + "-" + k + "-" + h) for k in ["H3", "H4", "H5"]}
    h1sample = f.loc[f.horizon_label.eq(h) & f.match_id.isin(set(f.loc[f.horizon_label.eq("5Y"), "match_id"]))]
    res["fixed5_H1"] = H.conditional_binary(h1sample, "h1", "fixed5-H1-" + h)
    res["high_citation_threshold"] = cutoff
    allf = f.loc[f.horizon_label.eq(h)].copy()
    for k in ["h3", "h4", "h5"]:
        allf[k] = allf.docdb_family_id.map(base.set_index("docdb_family_id")[k])
    res["missing_extreme_bounds"] = {}
    for k in ["h3", "h4", "h5"]:
        missing = allf[k].isna()
        bounds = {}
        for label, ai_value in [("lower", 0), ("upper", 1)]:
            z = allf.copy()
            z.loc[missing & z.ai_indicator.eq(1), k] = ai_value
            z.loc[missing & z.ai_indicator.eq(0), k] = 1 - ai_value
            bounds[label] = H.conditional_binary(z, k, label + "-" + k + "-" + h)
        res["missing_extreme_bounds"][k] = bounds
    fields, _ = D.field_histories(eb)
    chosen = fields.loc[fields.field_h4.notna()].sort_values(["focus_docdb_family_id", "field_h4", "field_arrival", "field"]).drop_duplicates("focus_docdb_family_id")
    z = base.merge(chosen[["focus_docdb_family_id", "field_arrival", "field_h4", "field"]], left_on="docdb_family_id", right_on="focus_docdb_family_id", how="left", suffixes=("", "_receiver"))
    require(z.establishment_date.fillna(pd.Timestamp("1900-01-01")).eq(z.field_h4.fillna(pd.Timestamp("1900-01-01"))).all(), "Receiving-field earliest establishment mismatch")
    res["diagnostics"]["groups"] = {}
    for ai in [0, 1]:
        g = z.loc[z.ai_indicator.eq(ai)]
        arrival = g.loc[g.h3.eq(1)]
        established = g.loc[g.h4.eq(1)]
        res["diagnostics"]["groups"][str(ai)] = {
            "establishment_among_arrivals_pct": 100 * float(arrival.h4.mean()),
            "grant_to_arrival_days": D.quantiles((arrival.arrival_date - arrival.focus_grant_date).dt.days),
            "remaining_observation_days": D.quantiles((arrival.horizon_end - arrival.arrival_date).dt.days),
            "global_arrival_to_establishment_days": D.quantiles((established.establishment_date - established.arrival_date).dt.days),
            "same_field_arrival_to_establishment_days": D.quantiles((established.establishment_date - established.field_arrival).dt.days)}
    rng = np.random.default_rng(C["seeds"]["arrival_bootstrap"])
    wide = base.sort_values(["match_id", "ai_indicator"])[["h3", "h4"]].to_numpy().reshape(-1, 2, 2)
    ds = []
    for bidx in range(C["bootstrap"]["conditional"]):
        bsample = wide[rng.integers(len(wide), size=len(wide))]
        ds.append(100 * (bsample[:, 1, 1].sum() / bsample[:, 1, 0].sum() - bsample[:, 0, 1].sum() / bsample[:, 0, 0].sum()))
    res["diagnostics"]["arrival_conditioned_difference_ci95_pp"] = np.quantile(ds, [.025, .975]).tolist()
    dump(ROOT / "outputs/sensitivity" / (h + ".json"), res)
    print("sensitivity", h, "COMPLETE", flush=True)
