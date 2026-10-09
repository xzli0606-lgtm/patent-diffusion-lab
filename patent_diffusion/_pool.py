"""Study algorithms extracted for the local prototype; see PROVENANCE.json."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import numba as nb
import numpy as np
import pandas as pd
EDGE_SHA=None
FAMILY_SHA=None

def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()

def load_main(path):
    spec = importlib.util.spec_from_file_location("step3main", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def pools_with_pair(edges):
    starts = np.empty(len(edges), np.int64)
    counts = np.empty(len(edges), np.int32)
    unsupported = np.zeros(len(edges), bool)
    mask_parts, pair_parts, base = [], [], 0
    for fold in range(5):
        donors = edges.loc[edges.fold.ne(fold)]
        pools = {}
        for keys, g in donors.groupby(["focal", "lag_band", "calendar_band"], sort=False): pools[("exact",) + keys] = g
        for keys, g in donors.groupby(["focal", "lag_band"], sort=False): pools[("no_calendar",) + keys] = g
        for key, g in donors.groupby("focal", sort=False): pools[("field", key)] = g
        cached = {}
        target = edges.loc[edges.fold.eq(fold)]
        for keys, ix in target.groupby(["focal", "lag_band", "calendar_band"], sort=False).groups.items():
            chosen = None
            for key in [("exact",) + keys, ("no_calendar", keys[0], keys[1]), ("field", keys[0])]:
                g = pools.get(key)
                if g is not None and len(g) >= 200 and g.citing_id.nunique() >= 50:
                    chosen = key; break
            if chosen is None:
                unsupported[ix] = True; continue
            if chosen not in cached:
                g = pools[chosen]
                masks = g["mask"].to_numpy(np.uint64)
                pairs = g["pair_pos"].to_numpy(np.int32)
                cached[chosen] = (base, len(masks))
                mask_parts.append(masks); pair_parts.append(pairs); base += len(masks)
            starts[ix], counts[ix] = cached[chosen]
    return starts, counts, (np.concatenate(mask_parts) if mask_parts else np.empty(0, np.uint64)), (np.concatenate(pair_parts) if pair_parts else np.empty(0, np.int32)), unsupported

@nb.njit
def weighted_draw_and_score(offsets, days, focal, starts, counts, donor_masks, donor_pairs, weights, edge_supported, seed):
    np.random.seed(seed)
    sampled = np.empty(len(days), np.uint64)
    maxw = max(weights)
    zero_pool = 0
    for j in range(len(days)):
        accepted = False
        for _ in range(1000):
            z = starts[j] + np.random.randint(counts[j])
            w = weights[donor_pairs[z]]
            if w > 0 and np.random.randint(maxw) < w:
                sampled[j] = donor_masks[z]; accepted = True; break
        if not accepted:
            sampled[j] = donor_masks[starts[j] + np.random.randint(counts[j])]
            if edge_supported[j]: zero_pool += 1
    # Embedded frozen milestone algorithm.
    n = len(focal); result = np.zeros((n, 3), np.uint8)
    for i in range(n):
        first = np.full(35, -1, np.int32); t0 = -1
        fbit = np.uint64(1) << np.uint64(focal[i] - 1)
        for j in range(offsets[i], offsets[i + 1]):
            day = days[j]; bits = sampled[j] & ~fbit
            if bits == 0: continue
            result[i, 0] = 1
            for k in range(35):
                bit = np.uint64(1) << np.uint64(k)
                if bits & bit:
                    if first[k] < 0:
                        if t0 >= 0 and day > t0: result[i, 2] = 1
                        first[k] = day
                    elif day > first[k] and t0 < 0:
                        t0 = day; result[i, 1] = 1
    return result, zero_pool

def main():
    p = argparse.ArgumentParser()
    for x in ("edge", "family", "baseline", "main_script", "output"): p.add_argument("--" + x.replace("_", "-"), required=True)
    p.add_argument("--horizon", choices=["1Y", "3Y", "5Y"], required=True)
    p.add_argument("--replicates", type=int, default=200)
    a = p.parse_args(); out = Path(a.output)
    if out.exists(): raise RuntimeError("output exists")
    if digest(a.edge) != EDGE_SHA or digest(a.family) != FAMILY_SHA: raise RuntimeError("input hash mismatch")
    mainmod = load_main(a.main_script)
    fcols = ["match_id", "ai_indicator", "docdb_family_id", "horizon_label", "horizon_end", "focus_grant_date", "wipo35_field_nr"]
    fam = pd.read_parquet(a.family, columns=fcols); fam = fam.loc[fam.horizon_label.eq(a.horizon)].copy()
    fam["fold"] = fam.match_id.map(lambda s: int(hashlib.sha256(("20260918|" + s).encode()).hexdigest()[:8], 16) % 5)
    meta = fam.set_index("docdb_family_id")
    cols = ["focus_docdb_family_id", "citing_docdb_family_id", "edge_event_date", "focal_wipo35_field_nr", "citing_wipo35_mask", "citing_wipo35_missing"]
    e = pd.read_parquet(a.edge, columns=cols); e = e.loc[e.focus_docdb_family_id.isin(meta.index)].copy()
    e = e.loc[e.edge_event_date.le(e.focus_docdb_family_id.map(meta.horizon_end))].copy()
    missing = set(e.loc[e.citing_wipo35_missing, "focus_docdb_family_id"])
    fam["classified"] = ~fam.docdb_family_id.isin(missing)
    keep = fam.groupby("match_id").classified.all(); fam = fam.loc[fam.match_id.isin(keep.index[keep])].sort_values(["match_id", "ai_indicator"]).reset_index(drop=True)
    meta = fam.set_index("docdb_family_id"); e = e.loc[e.focus_docdb_family_id.isin(meta.index)].copy()
    e["fold"] = e.focus_docdb_family_id.map(meta.fold); e["focal"] = e.focal_wipo35_field_nr.astype(np.int16); e["citing_id"] = e.citing_docdb_family_id; e["mask"] = e.citing_wipo35_mask.astype(np.uint64)
    first_ann = meta.focus_grant_date + pd.DateOffset(years=1); third_ann = meta.focus_grant_date + pd.DateOffset(years=3)
    e["lag_band"] = np.select([e.edge_event_date.le(e.focus_docdb_family_id.map(first_ann)), e.edge_event_date.le(e.focus_docdb_family_id.map(third_ann))], [0, 1], 2).astype(np.int8)
    e["calendar_band"] = ((e.edge_event_date.dt.year - 2019) // 3).astype(np.int8)
    family_order = fam.docdb_family_id.to_numpy(); pos = pd.Series(np.arange(len(fam)), index=family_order)
    e["family_pos"] = e.focus_docdb_family_id.map(pos).astype(np.int32); e["pair_pos"] = (e.family_pos // 2).astype(np.int32)
    e["date_day"] = (e.edge_event_date - pd.Timestamp("1970-01-01")).dt.days.astype(np.int32)
    e = e.sort_values(["family_pos", "edge_event_date", "citing_docdb_family_id"]).reset_index(drop=True)
    offsets = np.zeros(len(fam) + 1, np.int64); offsets[1:] = np.cumsum(np.bincount(e.family_pos, minlength=len(fam)))
    days = e.date_day.to_numpy(np.int32); focal = fam.wipo35_field_nr.to_numpy(np.int16)
    observed = mainmod.outcomes(offsets, days, e["mask"].to_numpy(np.uint64), focal)
    baseline = pd.read_parquet(a.baseline, columns=["docdb_family_id", "h4", "h5"]).set_index("docdb_family_id")
    if not np.array_equal(observed[:, 1:], baseline.loc[family_order, ["h4", "h5"]].to_numpy(np.uint8)): raise RuntimeError("H4/H5 parity failed")
    starts, counts, donor_masks, donor_pairs, unsupported = pools_with_pair(e)
    affected = set(e.loc[unsupported, "focus_docdb_family_id"]); badpairs = set(fam.loc[fam.docdb_family_id.isin(affected), "match_id"])
    valid_pair = ~fam.drop_duplicates("match_id").match_id.isin(badpairs).to_numpy()
    unsupported_family = fam.docdb_family_id.isin(affected).to_numpy(); unsupported_edge = unsupported.copy()
    edge_supported = ~e.family_pos.map(pd.Series(unsupported_family)).to_numpy(bool)
    starts[unsupported_edge] = 0; counts[unsupported_edge] = 1
    pair_obs = observed.reshape(-1, 2, 3); n_pairs = len(pair_obs); draws = np.empty((a.replicates, 3)); zero_fallback = 0
    rng = np.random.default_rng(20260921)
    for b in range(a.replicates):
        w = np.bincount(rng.integers(0, n_pairs, size=n_pairs), minlength=n_pairs).astype(np.int32)
        sim, zero = weighted_draw_and_score(offsets, days, focal, starts, counts, donor_masks, donor_pairs, w, edge_supported, 20260921 + b)
        zero_fallback += zero; pair_sim = sim.reshape(-1, 2, 3)
        usew = w * valid_pair; den = usew.sum()
        draws[b] = ((pair_obs[:, 1].astype(float) - pair_obs[:, 0].astype(float) - pair_sim[:, 1].astype(float) + pair_sim[:, 0].astype(float)) * usew[:, None]).sum(axis=0) / den
        if (b + 1) % 20 == 0: print(f"{a.horizon}: {b+1}/{a.replicates}", flush=True)
    result = {"status": "COMPLETE", "horizon": a.horizon, "replicates": a.replicates, "method": "matched-pair nonparametric bootstrap; donor edges reweighted by resampled matched-pair multiplicity within fixed cross-fitted support strata; one field-path realization per bootstrap", "reference_supported_pairs": int(valid_pair.sum()), "zero_weight_pool_fallback_edges_total": int(zero_fallback), "outcomes": {}}
    for k, name in enumerate(["H3", "H4", "H5"]):
        result["outcomes"][name] = {"mean_excess_pp": float(draws[:, k].mean() * 100), "rebuild_pool_ci95_pp": [float(x * 100) for x in np.quantile(draws[:, k], [0.025, 0.975])], "bootstrap_mcse_of_mean_pp": float(draws[:, k].std(ddof=1) / np.sqrt(a.replicates) * 100)}
    out.mkdir(parents=True); (out / "RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
