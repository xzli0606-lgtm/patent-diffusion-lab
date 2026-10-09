"""Study algorithms extracted for the local prototype; see PROVENANCE.json."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numba as nb
import numpy as np
import pandas as pd
EDGE_SHA=None
FAMILY_SHA=None

def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()

@nb.njit
def outcomes(offsets, days, masks, focal):
    n = len(focal)
    result = np.zeros((n, 3), dtype=np.uint8)
    for i in range(n):
        first = np.full(35, -1, dtype=np.int32)
        t0 = -1
        fbit = np.uint64(1) << np.uint64(focal[i] - 1)
        for j in range(offsets[i], offsets[i + 1]):
            day = days[j]
            bits = masks[j] & ~fbit
            if bits == 0:
                continue
            result[i, 0] = 1
            for k in range(35):
                bit = np.uint64(1) << np.uint64(k)
                if bits & bit:
                    if first[k] < 0:
                        if t0 >= 0 and day > t0:
                            result[i, 2] = 1
                        first[k] = day
                    elif day > first[k]:
                        if t0 < 0:
                            t0 = day
                            result[i, 1] = 1
    return result

@nb.njit
def draw_and_score(offsets, days, focal, pool_start, pool_count, donor_masks, seed):
    np.random.seed(seed)
    sampled = np.empty(len(days), dtype=np.uint64)
    for j in range(len(days)):
        sampled[j] = donor_masks[pool_start[j] + np.random.randint(pool_count[j])]
    return outcomes(offsets, days, sampled, focal)

def build_pools(edges, donor_ai_only=False, grant_cohort=False):
    # A pool is estimated without the target matched pair's entire fold.
    starts = np.empty(len(edges), dtype=np.int64)
    counts = np.empty(len(edges), dtype=np.int32)
    unsupported = np.zeros(len(edges), dtype=bool)
    donor_arrays = []
    base = 0
    for fold in range(5):
        donors = edges.loc[edges.fold.ne(fold)]
        if donor_ai_only:
            donors = donors.loc[donors.ai.eq(0)]
        pools = {}
        exact_cols = ["focal", "lag_band", "calendar_band"] + (["grant_band"] if grant_cohort else [])
        for keys, grp in donors.groupby(exact_cols, sort=False):
            pools[("exact",) + keys] = grp
        middle_cols = ["focal", "lag_band"] + (["grant_band"] if grant_cohort else [])
        for keys, grp in donors.groupby(middle_cols, sort=False):
            pools[("no_calendar",) + keys] = grp
        final_cols = ["focal", "grant_band"] if grant_cohort else ["focal"]
        for keys, grp in donors.groupby(final_cols, sort=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            pools[("field",) + keys] = grp
        mapping = {}
        target = edges.loc[edges.fold.eq(fold)]
        for keys, ix in target.groupby(exact_cols, sort=False).groups.items():
            chosen = None
            candidates = [("exact",) + keys, ("no_calendar", keys[0], keys[1]) + ((keys[3],) if grant_cohort else ()), ("field", keys[0]) + ((keys[3],) if grant_cohort else ())]
            for pool_key in candidates:
                candidate = pools.get(pool_key)
                if candidate is not None and len(candidate) >= 200 and candidate.citing_id.nunique() >= 50:
                    chosen = pool_key
                    break
            if chosen is None:
                unsupported[ix] = True
                continue
            if chosen not in mapping:
                values = pools[chosen]["mask"].to_numpy(np.uint64)
                mapping[chosen] = (base, len(values))
                donor_arrays.append(values)
                base += len(values)
            starts[ix], counts[ix] = mapping[chosen]
    return starts, counts, (np.concatenate(donor_arrays) if donor_arrays else np.empty(0, np.uint64)), unsupported

def bootstrap_interval(pair_values, seed, reps=2000):
    rng = np.random.default_rng(seed)
    n = len(pair_values)
    draws = np.empty((reps, pair_values.shape[1]))
    for b in range(reps):
        sample = rng.integers(0, n, size=n)
        draws[b] = pair_values[sample].mean(axis=0)
    return np.quantile(draws, [0.025, 0.975], axis=0).T.tolist(), draws.std(axis=0, ddof=1)

def main():
    p = argparse.ArgumentParser()
    for x in ("edge", "family", "contract", "output"):
        p.add_argument("--" + x, required=True)
    p.add_argument("--horizon", choices=["1Y", "3Y", "5Y"], required=True)
    p.add_argument("--baseline", required=True)
    p.add_argument("--replicates", type=int, default=2000)
    p.add_argument("--donor-nonai-only", action="store_true")
    p.add_argument("--grant-cohort", action="store_true")
    args = p.parse_args()
    path = {x: Path(getattr(args, x)) for x in ("edge", "family", "contract", "output")}
    if digest(path["edge"]) != EDGE_SHA or digest(path["family"]) != FAMILY_SHA:
        raise RuntimeError("input SHA256 mismatch")
    contract = json.loads(path["contract"].read_text(encoding="utf-8"))
    if contract["status"] != "FROZEN_BEFORE_NEW_EFFECTS":
        raise RuntimeError("contract not frozen")
    if path["output"].exists():
        raise RuntimeError("output exists")
    cols = ["focus_docdb_family_id", "citing_docdb_family_id", "edge_event_date", "focal_wipo35_field_nr", "citing_wipo35_mask", "citing_wipo35_missing"]
    e = pd.read_parquet(path["edge"], columns=cols)
    fcols = ["match_id", "ai_indicator", "docdb_family_id", "horizon_label", "horizon_end", "focus_grant_date", "wipo35_field_nr"]
    fam = pd.read_parquet(path["family"], columns=fcols)
    fam = fam.loc[fam.horizon_label.eq(args.horizon)].copy()
    fam["fold"] = fam.match_id.map(lambda s: int(hashlib.sha256(("20260918|" + s).encode()).hexdigest()[:8], 16) % 5)
    meta = fam.set_index("docdb_family_id")
    e = e.loc[e.focus_docdb_family_id.isin(meta.index)].copy()
    e["horizon_end"] = e.focus_docdb_family_id.map(meta.horizon_end)
    e = e.loc[e.edge_event_date.le(e.horizon_end)].copy()
    candidate_edges = len(e)
    missing_edges = int(e.citing_wipo35_missing.sum())
    group_missing = e.groupby(e.focus_docdb_family_id.map(meta.ai_indicator)).citing_wipo35_missing.mean().to_dict()
    coverage = 1 - missing_edges / candidate_edges
    gap = abs(float(group_missing.get(1, 0)) - float(group_missing.get(0, 0)))
    if coverage < 0.985 or gap >= 0.01:
        raise RuntimeError("frozen H4/H5 classification gate failed")
    missing_ids = set(e.loc[e.citing_wipo35_missing, "focus_docdb_family_id"])
    fam["classified"] = ~fam.docdb_family_id.isin(missing_ids)
    keep_pair = fam.groupby("match_id").classified.all()
    fam = fam.loc[fam.match_id.isin(keep_pair.index[keep_pair])].copy()
    e = e.loc[e.focus_docdb_family_id.isin(fam.docdb_family_id)].copy()
    audit = {"candidate_pairs": int(len(meta) // 2), "classified_pairs": int(len(fam) // 2), "candidate_edges": int(candidate_edges), "unclassified_candidate_edges": missing_edges, "candidate_edge_coverage": coverage, "missing_rate_ai_nonai_gap": gap}
    if e.citing_wipo35_missing.any() or fam.groupby("match_id").size().ne(2).any():
        raise RuntimeError("classification or pair gate failure")
    fam = fam.sort_values(["match_id", "ai_indicator"]).reset_index(drop=True)
    if fam.groupby("match_id").ai_indicator.sum().ne(1).any():
        raise RuntimeError("invalid AI pair")
    meta = fam.set_index("docdb_family_id")
    e["match_id"] = e.focus_docdb_family_id.map(meta.match_id)
    e["ai"] = e.focus_docdb_family_id.map(meta.ai_indicator)
    e["fold"] = e.focus_docdb_family_id.map(meta.fold)
    e["focal"] = e.focal_wipo35_field_nr.astype(np.int16)
    e["citing_id"] = e.citing_docdb_family_id
    e["mask"] = e.citing_wipo35_mask.astype(np.uint64)
    first_anniversary = meta.focus_grant_date + pd.DateOffset(years=1)
    third_anniversary = meta.focus_grant_date + pd.DateOffset(years=3)
    e["lag_band"] = np.select([e.edge_event_date.le(e.focus_docdb_family_id.map(first_anniversary)), e.edge_event_date.le(e.focus_docdb_family_id.map(third_anniversary))], [0, 1], 2).astype(np.int8)
    e["calendar_band"] = ((e.edge_event_date.dt.year - 2019) // 3).astype(np.int8)
    e["grant_band"] = ((e.focus_docdb_family_id.map(meta.focus_grant_date).dt.year - 2019) // 3).astype(np.int8)
    e = e.sort_values(["focus_docdb_family_id", "edge_event_date", "citing_docdb_family_id"]).reset_index(drop=True)
    e["date_day"] = (e.edge_event_date - pd.Timestamp("1970-01-01")).dt.days.astype(np.int32)
    family_order = fam.docdb_family_id.to_numpy()
    order = pd.Series(np.arange(len(family_order)), index=family_order)
    e["family_pos"] = e.focus_docdb_family_id.map(order).astype(np.int32)
    e = e.sort_values(["family_pos", "edge_event_date", "citing_docdb_family_id"]).reset_index(drop=True)
    offsets = np.zeros(len(fam) + 1, dtype=np.int64)
    offsets[1:] = np.cumsum(np.bincount(e.family_pos, minlength=len(fam)))
    days = e.date_day.to_numpy(np.int32)
    focal = fam.wipo35_field_nr.to_numpy(np.int16)
    observed = outcomes(offsets, days, e["mask"].to_numpy(np.uint64), focal)
    baseline = pd.read_parquet(args.baseline, columns=["docdb_family_id", "h4", "h5"]).set_index("docdb_family_id")
    if not np.array_equal(observed[:, 1:], baseline.loc[family_order, ["h4", "h5"]].to_numpy(np.uint8)):
        raise RuntimeError("original H4/H5 family-level parity failed")
    starts, counts, donor, unsupported = build_pools(e, args.donor_nonai_only, args.grant_cohort)
    affected = set(e.loc[unsupported, "focus_docdb_family_id"])
    bad_pairs = set(fam.loc[fam.docdb_family_id.isin(affected), "match_id"])
    valid = ~fam.match_id.isin(bad_pairs).to_numpy()
    audit.update({"reference_unsupported_edges": int(unsupported.sum()), "reference_unsupported_families": len(affected), "reference_unsupported_pairs": len(bad_pairs), "reference_retained_pairs": int(valid.sum() // 2)})
    if not valid.any():
        raise RuntimeError("no supported reference pairs")
    if unsupported.any():
        starts[unsupported] = 0
        counts[unsupported] = 1
    sum_ref = np.zeros((len(fam), 3), dtype=np.float64)
    diff_ref = np.empty((args.replicates, 3), dtype=np.float64)
    ai = fam.ai_indicator.to_numpy() == 1
    for r in range(args.replicates):
        sim = draw_and_score(offsets, days, focal, starts, counts, donor, 20260919 + r)
        sum_ref += sim
        diff_ref[r] = sim[valid & ai].mean(axis=0) - sim[valid & ~ai].mean(axis=0)
        if (r + 1) % 100 == 0:
            print(f"{args.horizon}: {r + 1}/{args.replicates}", flush=True)
    ref_prob = sum_ref / args.replicates
    actual_diff = observed[valid & ai].mean(axis=0) - observed[valid & ~ai].mean(axis=0)
    ref_diff = diff_ref.mean(axis=0)
    excess = actual_diff - ref_diff
    mcse_pp = diff_ref.std(axis=0, ddof=1) / np.sqrt(args.replicates) * 100
    wide_obs = observed[valid].reshape(-1, 2, 3)
    wide_ref = ref_prob[valid].reshape(-1, 2, 3)
    pair_excess = (wide_obs[:, 1].astype(np.float64) - wide_obs[:, 0].astype(np.float64)) - (wide_ref[:, 1] - wide_ref[:, 0])
    if not np.allclose(pair_excess.mean(axis=0), excess, atol=1e-10):
        raise RuntimeError("pair-level excess parity failed")
    ci, boot_se = bootstrap_interval(pair_excess, 20260920, 2000)
    result = {"status": "COMPLETE" if max(mcse_pp[1:]) <= 0.1 else "MCSE_NOT_MET", "horizon": args.horizon, "donor_nonai_only": args.donor_nonai_only, "grant_cohort": args.grant_cohort, "input_hashes": {k: digest(path[k]) for k in ("edge", "family", "contract")}, "audit": audit, "replicates": args.replicates, "outcomes": {}}
    for k, name in enumerate(["H3", "H4", "H5"]):
        z = float(excess[k] / boot_se[k]) if boot_se[k] > 0 else math.inf
        result["outcomes"][name] = {"observed_ai_rate": float(observed[valid & ai, k].mean()), "observed_nonai_rate": float(observed[valid & ~ai, k].mean()), "reference_ai_rate": float(ref_prob[valid & ai, k].mean()), "reference_nonai_rate": float(ref_prob[valid & ~ai, k].mean()), "observed_difference_pp": float(actual_diff[k] * 100), "reference_difference_pp": float(ref_diff[k] * 100), "excess_difference_pp": float(excess[k] * 100), "excess_ci95_pp": [float(x * 100) for x in ci[k]], "bootstrap_se_pp": float(boot_se[k] * 100), "bootstrap_normal_p_two_sided": math.erfc(abs(z) / math.sqrt(2)), "mcse_pp": float(mcse_pp[k])}
    path["output"].mkdir(parents=True)
    diagnostic = fam[["match_id", "ai_indicator", "docdb_family_id"]].copy()
    diagnostic["reference_supported_pair"] = valid
    for k, name in enumerate(["H3", "H4", "H5"]):
        diagnostic[f"{name}_observed"] = observed[:, k]
        diagnostic[f"{name}_reference_probability"] = ref_prob[:, k]
    diagnostic.to_parquet(path["output"] / "FAMILY_REFERENCE_PROBABILITIES.parquet", index=False)
    (path["output"] / "RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "horizon": args.horizon, "audit": audit, "outcomes": result["outcomes"]}, ensure_ascii=False), flush=True)
