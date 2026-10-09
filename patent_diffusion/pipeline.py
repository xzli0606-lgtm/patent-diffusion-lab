"""Portable pipeline for experimental citation-diffusion analyses."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import _reference, _study
from ._piecewise import fit as fit_piecewise

CUTOFF = pd.Timestamp("2026-06-30")
FOLD_SEED, SIM_SEED, BOOT_SEED = 20260918, 20260919, 20260920
FAMILY_COLUMNS = {"match_id", "ai_indicator", "docdb_family_id", "focus_grant_date",
                  "grant_quarter", "primary_cpc4", "wipo35_field_nr", "matching_cell"}
EDGE_COLUMNS = {"focus_docdb_family_id", "citing_docdb_family_id", "edge_event_date",
                "focal_wipo35_field_nr", "citing_wipo35_mask", "citing_wipo35_missing"}
PUBLISHED = {
    "H1": {"1Y": (67.23, 60.77, 1.332), "3Y": (90.57, 86.64, 1.488), "5Y": (95.18, 92.84, 1.528)},
    "H3": {"1Y": (51.06, 41.36, 1.503), "3Y": (77.39, 68.82, 1.581), "5Y": (85.31, 78.93, 1.578)},
    "H4": {"1Y": (23.92, 16.17, 1.658), "3Y": (52.89, 40.54, 1.692), "5Y": (65.12, 53.13, 1.685)},
    "H5": {"1Y": (8.80, 5.17, 1.788), "3Y": (28.28, 19.01, 1.725), "5Y": (39.97, 29.18, 1.653)},
}


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate(f, e):
    missing = FAMILY_COLUMNS - set(f.columns)
    if missing:
        raise ValueError(f"families input missing columns: {sorted(missing)}")
    missing = EDGE_COLUMNS - set(e.columns)
    if missing:
        raise ValueError(f"edges input missing columns: {sorted(missing)}")
    if f.match_id.isna().any():
        raise ValueError("match_id cannot be null")
    if f.docdb_family_id.isna().any() or f.docdb_family_id.duplicated().any():
        raise ValueError("families must contain one row per nonmissing DOCDB family")
    if not f.ai_indicator.isin([0, 1]).all():
        raise ValueError("ai_indicator must contain only 0 and 1")
    pair = f.groupby("match_id").agg(n=("docdb_family_id", "size"), ai=("ai_indicator", "sum"))
    if not (pair.n.eq(2) & pair.ai.eq(1)).all():
        raise ValueError("each match_id must have exactly one AI and one non-AI family")
    if f[["focus_grant_date", "grant_quarter", "primary_cpc4", "matching_cell", "wipo35_field_nr"]].isna().any().any():
        raise ValueError("matched-family dates, strata, and focal fields must be complete")
    pair_fields = f.groupby("match_id").agg(quarters=("grant_quarter", "nunique"),
        cpc4=("primary_cpc4", "nunique"), cells=("matching_cell", "nunique"))
    if not (pair_fields.quarters.eq(1) & pair_fields.cpc4.eq(1) & pair_fields.cells.eq(1)).all():
        raise ValueError("matched pairs must agree on grant quarter, primary CPC4, and matching cell")
    if not (f.wipo35_field_nr.between(1, 35) & f.wipo35_field_nr.mod(1).eq(0)).all():
        raise ValueError("focal WIPO35 fields must be numbered 1 through 35")
    key = ["focus_docdb_family_id", "citing_docdb_family_id"]
    if e[key + ["edge_event_date"]].isna().any().any() or e.duplicated(key).any():
        raise ValueError("edge IDs/dates must be complete and family-pair edges unique")
    if e.focus_docdb_family_id.eq(e.citing_docdb_family_id).any():
        raise ValueError("within-family citation edges are not eligible")
    if not e.focus_docdb_family_id.isin(set(f.docdb_family_id)).all():
        raise ValueError("an edge refers to a focal family absent from the family input")
    if e.citing_wipo35_missing.isna().any() or not pd.api.types.is_bool_dtype(e.citing_wipo35_missing):
        raise ValueError("citing_wipo35_missing must contain non-null booleans")
    if e.edge_event_date.gt(CUTOFF).any():
        raise ValueError("citation event dates cannot exceed the frozen cutoff")
    grant_dates = f.set_index("docdb_family_id").focus_grant_date
    if e.edge_event_date.lt(e.focus_docdb_family_id.map(grant_dates)).any():
        raise ValueError("citation event precedes the focal-family grant date")
    focal_field = f.set_index("docdb_family_id").wipo35_field_nr
    if not e.focal_wipo35_field_nr.eq(e.focus_docdb_family_id.map(focal_field)).all():
        raise ValueError("citation edge focal WIPO35 field does not match its family")
    mask = e.loc[~e.citing_wipo35_missing, "citing_wipo35_mask"]
    if mask.isna().any() or not (mask.between(1, (1 << 35) - 1) & mask.mod(1).eq(0)).all():
        raise ValueError("classified WIPO35 masks must be nonzero 35-bit integers")



def load_inputs(families_path, edges_path):
    """Read and validate the canonical preprocessed tables; never write to inputs."""
    f, e = pd.read_parquet(families_path), pd.read_parquet(edges_path)
    for label, frame, required in (("families", f, FAMILY_COLUMNS), ("edges", e, EDGE_COLUMNS)):
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{label} input missing columns: {sorted(missing)}")
    for frame, column in ((f, "focus_grant_date"), (e, "edge_event_date")):
        frame[column] = pd.to_datetime(frame[column], errors="raise")
        if frame[column].dt.tz is not None or not frame[column].eq(frame[column].dt.normalize()).all():
            raise ValueError(f"{column} must contain nonmissing, timezone-naive calendar dates")
    _validate(f, e)
    return f, e


def validate_inputs(families_path, edges_path):
    """Validate schema and full-input classification gates, without fitting models."""
    f, e = load_inputs(families_path, edges_path)
    windows = {f"{years}Y": _classification_gate(f, e, years) for years in (1, 3, 5)}
    if not all(gate["passes"] for gate in windows.values()):
        raise ValueError(f"full-input WIPO35 classification gate failed: {windows}")
    return {"status": "INPUTS_VALID", "families": len(f), "edges": len(e), "windows": windows,
            "note": "Schema and coverage only; model estimability and reference support are checked during analysis."}

def _sample(f, years, n_pairs, seed):
    cohort = f.loc[(f.focus_grant_date + pd.DateOffset(years=years)).le(CUTOFF)].copy()
    sizes = cohort.groupby("match_id").size()
    cohort = cohort.loc[cohort.match_id.isin(sizes.index[sizes.eq(2)])]
    ids = cohort.drop_duplicates("match_id").match_id.astype(str)
    keep = set(sorted(ids, key=lambda x: _sha(f"{seed}|{x}"))[:n_pairs])
    if not keep:
        raise ValueError(f"no pairs have complete {years}-year follow-up")
    return cohort.loc[cohort.match_id.astype(str).isin(keep)].copy()


def _classification_gate(f, e, years):
    cohort = f.loc[(f.focus_grant_date + pd.DateOffset(years=years)).le(CUTOFF)]
    sizes = cohort.groupby("match_id").size()
    cohort = cohort.loc[cohort.match_id.isin(sizes.index[sizes.eq(2)])]
    end = cohort.set_index("docdb_family_id").focus_grant_date + pd.DateOffset(years=years)
    edges = e.loc[e.focus_docdb_family_id.isin(end.index)].copy()
    edges = edges.loc[edges.edge_event_date.le(edges.focus_docdb_family_id.map(end))]
    if edges.empty:
        raise ValueError(f"no candidate edges for the {years}-year classification gate")
    ai = cohort.set_index("docdb_family_id").ai_indicator
    missing = edges.groupby(edges.focus_docdb_family_id.map(ai)).citing_wipo35_missing.mean()
    coverage = 1 - float(edges.citing_wipo35_missing.mean())
    gap = abs(float(missing.get(1, 0)) - float(missing.get(0, 0)))
    return {"eligible_pairs": int(cohort.match_id.nunique()), "eligible_edges": int(len(edges)),
            "coverage": coverage, "AI_nonAI_missing_rate_gap": gap,
            "passes": coverage >= .985 and gap < .01}


def _models(frame, years, name, outcome, event_date):
    result = _study.conditional_binary(frame, outcome, name)
    result["cox"] = _study.fit_cox(frame, event_date, name + "-time")
    if result["cox"]["ph_diagnostic"]["trigger_piecewise"]:
        import warnings
        from statsmodels.tools.sm_exceptions import ConvergenceWarning
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", ConvergenceWarning)
                result["piecewise_cox"] = fit_piecewise(frame, event_date, years, name + "-piecewise")
        except (np.linalg.LinAlgError, ConvergenceWarning, OverflowError, ZeroDivisionError) as exc:
            result["piecewise_cox"] = {"status": "not_estimable", "reason": str(exc),
                                       "note": "No estimate substituted; main matched comparison is retained."}
    return result


def _opportunity(frame, edges, years, smoke, requested_reps, boot_reps):
    fam = frame.sort_values(["match_id", "ai_indicator"], kind="stable").reset_index(drop=True).copy()
    fam["fold"] = fam.match_id.map(lambda x: int(_sha(f"{FOLD_SEED}|{x}")[:8], 16) % 5)
    meta = fam.set_index("docdb_family_id")
    end = meta.focus_grant_date + pd.DateOffset(years=years)
    e = edges.loc[edges.focus_docdb_family_id.isin(meta.index)].copy()
    e = e.loc[e.edge_event_date.le(e.focus_docdb_family_id.map(end))]
    e = e.loc[~e.citing_wipo35_missing].copy()
    e["match_id"] = e.focus_docdb_family_id.map(meta.match_id)
    e["ai"] = e.focus_docdb_family_id.map(meta.ai_indicator).astype(np.int8)
    e["fold"] = e.focus_docdb_family_id.map(meta.fold).astype(np.int8)
    e["focal"] = e.focal_wipo35_field_nr.astype(np.int16)
    e["citing_id"] = e.citing_docdb_family_id
    e["mask"] = e.citing_wipo35_mask.astype(np.uint64)
    ann1 = meta.focus_grant_date + pd.DateOffset(years=1)
    ann3 = meta.focus_grant_date + pd.DateOffset(years=3)
    e["lag_band"] = np.select([e.edge_event_date.le(e.focus_docdb_family_id.map(ann1)),
                               e.edge_event_date.le(e.focus_docdb_family_id.map(ann3))], [0, 1], 2).astype(np.int8)
    e["calendar_band"] = ((e.edge_event_date.dt.year - 2019) // 3).astype(np.int8)
    e = e.sort_values(["match_id", "ai", "edge_event_date", "citing_id"], kind="stable").reset_index(drop=True)
    order = pd.Series(np.arange(len(fam)), index=fam.docdb_family_id)
    e["family_pos"] = e.focus_docdb_family_id.map(order).astype(np.int32)
    e = e.sort_values(["family_pos", "edge_event_date", "citing_id"], kind="stable").reset_index(drop=True)
    offsets = np.zeros(len(fam) + 1, np.int64)
    offsets[1:] = np.cumsum(np.bincount(e.family_pos, minlength=len(fam)))
    days = (e.edge_event_date - pd.Timestamp("1970-01-01")).dt.days.to_numpy(np.int32)
    focal = fam.wipo35_field_nr.to_numpy(np.int16)
    observed = _reference.outcomes(offsets, days, e["mask"].to_numpy(np.uint64), focal)
    starts, counts, donor, unsupported = _reference.build_pools(e)
    affected = set(e.loc[unsupported, "focus_docdb_family_id"])
    bad_pairs = set(fam.loc[fam.docdb_family_id.isin(affected), "match_id"])
    valid_pair = ~fam.drop_duplicates("match_id").match_id.isin(bad_pairs).to_numpy()
    valid_family = np.repeat(valid_pair, 2)
    if not valid_pair.any():
        return {"status": "NO_SUPPORTED_PAIRS", "candidate_pairs": int(fam.match_id.nunique()),
                "supported_pairs": 0, "unsupported_pairs": len(bad_pairs), "unsupported_edges": int(unsupported.sum()),
                "minimum_pool_edges": 200, "minimum_distinct_citing_families": 50}
    starts[unsupported] = 0
    counts[unsupported] = 1
    ai = fam.ai_indicator.to_numpy() == 1
    refs = np.zeros((len(fam), 3), np.float64)
    diffs = []
    target = min(requested_reps, 50) if smoke else requested_reps
    total = target
    while True:
        for b in range(len(diffs), total):
            sim = _reference.draw_and_score(offsets, days, focal, starts, counts, donor, SIM_SEED + b)
            refs += sim
            diffs.append(sim[valid_family & ai].mean(axis=0) - sim[valid_family & ~ai].mean(axis=0))
        draw = np.asarray(diffs)
        mcse = draw.std(axis=0, ddof=1) / np.sqrt(len(draw)) * 100
        if smoke or max(mcse[1:]) <= .1 or total >= 10000:
            break
        total = min(total + 2000, 10000)
    ref_prob = refs / total
    ref_diff = draw.mean(axis=0)
    obs_diff = observed[valid_family & ai].mean(axis=0) - observed[valid_family & ~ai].mean(axis=0)
    pair_obs = observed[valid_family].reshape(-1, 2, 3)
    pair_ref = ref_prob[valid_family].reshape(-1, 2, 3)
    pair_values = (pair_obs[:, 1].astype(float) - pair_obs[:, 0].astype(float)) - (pair_ref[:, 1] - pair_ref[:, 0])
    reps = min(boot_reps, 200) if smoke else boot_reps
    ci, _ = _reference.bootstrap_interval(pair_values, BOOT_SEED, reps)
    result = {}
    for i, name in enumerate(("H3", "H4", "H5")):
        result[name] = {"observed_difference_pp": float(obs_diff[i] * 100),
                        "reference_difference_pp": float(ref_diff[i] * 100),
                        "excess_difference_pp": float((obs_diff[i] - ref_diff[i]) * 100),
                        "excess_ci95_pp": [float(x * 100) for x in ci[i]],
                        "mcse_pp": float(mcse[i])}
    return {"status": "EXPERIMENTAL_SMOKE" if smoke else ("COMPLETE" if max(mcse[1:]) <= .1 else "MCSE_GATE_FAILED"),
            "candidate_pairs": int(fam.match_id.nunique()), "supported_pairs": int(valid_pair.sum()),
            "unsupported_pairs": int(len(bad_pairs)), "unsupported_edges": int(unsupported.sum()),
            "replicates": total, "bootstrap_replicates": reps, "MCSE_gate_pp": .1,
            "results": result}


def _report(manifest):
    lines = ["# Experimental citation-diffusion run", "",
             f"Status: {manifest['status']}", "",
             ("SYNTHETIC DATA: artificial identifiers and events generated locally. These results are not empirical findings or comparisons with the paper." if manifest.get("dataset_kind") == "synthetic" else "This deterministic sample is a software diagnostic, not a full-cohort reproduction. Estimates remain observational. Smoke-mode uncertainty does not pass the formal Monte Carlo gate by itself."), "",
             "## Matched comparisons", "",
             "| Window | Endpoint | Sample AI % | Sample non-AI % | Sample gap (pp) | Sample OR | Published full-cohort gap (pp) | Sample minus paper (pp) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    if manifest.get("dataset_kind") == "synthetic":
        lines[-2:] = ["| Window | Endpoint | Synthetic AI % | Synthetic non-AI % | Gap (pp) | OR |",
                      "|---|---|---:|---:|---:|---:|"]
    for h, window in manifest["windows"].items():
        for name in ("H1", "H3", "H4", "H5"):
            if manifest.get("dataset_kind") == "synthetic":
                m = window["models"][name]
                lines.append(f"| {h} | {name} | {100*m['raw_rate_ai']:.2f} | {100*m['raw_rate_nonai']:.2f} | {100*m['absolute_rate_difference']:.2f} | {m['estimate']:.3f} |")
                continue
            r = window["comparison_with_paper"][name]
            target = r["published_full_cohort"]
            paper_gap = target["ai_rate_pct"] - target["nonai_rate_pct"]
            lines.append(f"| {h} | {name} | {r['sample_ai_rate_pct']:.2f} | {r['sample_nonai_rate_pct']:.2f} | {r['sample_difference_pp']:.2f} | {r['sample_or']:.3f} | {paper_gap:.2f} | {r['sample_difference_vs_paper_pp']:.2f} |")
    lines += ["", "## Opportunity-conditioned reference", "",
              "| Window | Supported pairs | Unsupported pairs | Draws | H4 MCSE (pp) | H4 excess (pp) | H4 interval (pp) | H5 MCSE (pp) | H5 excess (pp) | H5 interval (pp) |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for h, window in manifest["windows"].items():
        r = window["opportunity_reference"]
        if "results" not in r:
            lines.append(f"| {h} | 0 | {r['unsupported_pairs']} | 0 | — | — | — | — | — | — |")
            continue
        h4, h5 = r["results"]["H4"], r["results"]["H5"]
        lines.append(f"| {h} | {r['supported_pairs']} | {r['unsupported_pairs']} | {r['replicates']} | {h4['mcse_pp']:.3f} | {h4['excess_difference_pp']:.2f} | {h4['excess_ci95_pp'][0]:.2f}–{h4['excess_ci95_pp'][1]:.2f} | {h5['mcse_pp']:.3f} | {h5['excess_difference_pp']:.2f} | {h5['excess_ci95_pp'][0]:.2f}–{h5['excess_ci95_pp'][1]:.2f} |")
    lines += ["", "## Inputs", "", f"Families SHA-256: `{manifest['families_sha256']}`", "",
              f"Citation edges SHA-256: `{manifest['edges_sha256']}`", "",
              "The reference residual is not a causal effect, mediation share, or mechanism share. Unavailable piecewise fits are recorded in run.json; no estimate is substituted.", ""]
    return "\n".join(lines)


def run(families_path: Path, edges_path: Path, output: Path, n_pairs=10000,
        seed=20261009, replicates=2000, bootstrap=2000, smoke=False, *, synthetic=False):
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    if n_pairs < 1 or replicates < 2 or bootstrap < 2:
        raise ValueError("pairs must be positive; replicates and bootstrap must be at least 2")
    if not smoke and (replicates < 2000 or replicates > 10000 or bootstrap < 2000):
        raise ValueError("non-smoke runs require 2000-10000 reference draws and at least 2000 bootstrap draws")
    f, e = load_inputs(families_path, edges_path)
    if smoke and (replicates >= 2000 or bootstrap >= 2000):
        replicates, bootstrap = min(replicates, 50), min(bootstrap, 200)
    output.mkdir(parents=True)
    from . import __version__
    import importlib.metadata
    import platform
    manifest = {"status": "SMOKE_ONLY" if smoke else "EXPERIMENTAL_ANALYSIS",
                "dataset_kind": "synthetic" if synthetic else "user_preprocessed",
                "software_version": __version__, "python_version": platform.python_version(),
                "dependency_versions": {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "scipy", "statsmodels", "numba", "pyarrow")},
                "reference_contract_sha256": _reference.digest(Path(__file__).with_name("reference_contract.json")),
                "seeds": {"sample": seed, "fold": FOLD_SEED, "simulation": SIM_SEED, "bootstrap": BOOT_SEED},
                "reference_scope": "Main pooled reference and bootstrap conditional on estimated pools only; contract sensitivities are not run.",
                "scope": "Deterministic sample from preprocessed data; not a full-cohort reproduction.",
                "families_sha256": _reference.digest(families_path), "edges_sha256": _reference.digest(edges_path),
                "cutoff": str(CUTOFF.date()), "sample_seed": seed, "requested_pairs_per_window": n_pairs,
                "reference_replicates": replicates, "bootstrap_replicates": bootstrap,
                "interpretation": "Observational software diagnostic; reference residuals are not causal effects or mechanism shares.",
                "windows": {}}
    for years in (1, 3, 5):
        h = f"{years}Y"
        gate = _classification_gate(f, e, years)
        if not gate["passes"]:
            raise ValueError(f"full-input WIPO35 coverage gate failed for {h}: {gate}")
        sample = _sample(f, years, n_pairs, seed)
        sample["horizon_end"] = sample.focus_grant_date + pd.DateOffset(years=years)
        end = sample.set_index("docdb_family_id").focus_grant_date + pd.DateOffset(years=years)
        ew = e.loc[e.focus_docdb_family_id.isin(end.index)].copy()
        ew = ew.loc[ew.edge_event_date.le(ew.focus_docdb_family_id.map(end))]
        counts = ew.groupby("focus_docdb_family_id").size()
        first = ew.groupby("focus_docdb_family_id").edge_event_date.min().rename("first_citation_date")
        sample = sample.drop(columns=["first_citation_date"], errors="ignore")
        sample["citation_count"] = sample.docdb_family_id.map(counts).fillna(0).astype(int)
        sample["h1"] = sample.citation_count.gt(0).astype(np.int8)
        sample = sample.merge(first, left_on="docdb_family_id", right_index=True, how="left", validate="one_to_one")
        missing = set(ew.loc[ew.citing_wipo35_missing, "focus_docdb_family_id"])
        sample["classified"] = ~sample.docdb_family_id.isin(missing)
        pair_ok = sample.groupby("match_id").classified.all()
        base = sample.loc[sample.match_id.isin(pair_ok.index[pair_ok])].copy()
        eb = ew.loc[ew.focus_docdb_family_id.isin(base.docdb_family_id)].copy()
        events = _study.milestones(eb) if len(eb) else pd.DataFrame(columns=["focus_docdb_family_id"])
        base = base.merge(events, left_on="docdb_family_id", right_on="focus_docdb_family_id", how="left", validate="one_to_one")
        for name, col in (("h3", "arrival_date"), ("h4", "establishment_date"), ("h5", "expansion_date")):
            base[name] = base[col].notna().astype(np.int8)
        for col in ("established_field_count", "new_field_count"):
            base[col] = base[col].fillna(0).astype(int)
        models = {"H1": _models(sample, years, f"H1-{h}", "h1", "first_citation_date")}
        for name, col in (("H3", "arrival_date"), ("H4", "establishment_date"), ("H5", "expansion_date")):
            models[name] = _models(base, years, f"{name}-{h}", name.lower(), col)
        models["counts"] = {c: _study.conditional_count(base, c, f"{c}-{h}")
                            for c in ("established_field_count", "new_field_count")}
        ref = _opportunity(base, eb, years, smoke, replicates, bootstrap)
        comparison = {}
        for name in ("H1", "H3", "H4", "H5"):
            m = models[name]
            ai_rate, nonai_rate, target_or = PUBLISHED[name][h]
            comparison[name] = {
                "sample_ai_rate_pct": 100 * m["raw_rate_ai"],
                "sample_nonai_rate_pct": 100 * m["raw_rate_nonai"],
                "sample_difference_pp": 100 * m["absolute_rate_difference"],
                "sample_or": m["estimate"],
                "published_full_cohort": {"ai_rate_pct": ai_rate, "nonai_rate_pct": nonai_rate, "or": target_or},
                "sample_difference_vs_paper_pp": 100 * m["absolute_rate_difference"] - (ai_rate - nonai_rate),
                "sample_or_difference_vs_paper": m["estimate"] - target_or,
                "warning": "Sample-to-full-cohort descriptive comparison; not a replication test.",
            }
        window = {"full_input_classification_gate": gate, "sampled_pairs": int(sample.match_id.nunique()),
                  "classified_sample_pairs": int(base.match_id.nunique()), "models": models,
                  "opportunity_reference": ref, "comparison_with_paper": None if synthetic else comparison}
        manifest["windows"][h] = window
        (output / f"{h}.json").write_text(json.dumps(window, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    tests = [(f"{name}-{h}", manifest["windows"][h]["models"][name]["p_two_sided"])
             for h in ("1Y", "3Y", "5Y") for name in ("H4", "H5")]
    manifest["holm_H4_H5"] = _study.holm(tests)
    if not smoke and any(w["opportunity_reference"]["status"] != "COMPLETE" for w in manifest["windows"].values()):
        manifest["status"] = "INCOMPLETE_REFERENCE"
    manifest["input_rows"] = {"families": len(f), "edges": len(e)}
    (output / "run.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    (output / "report.md").write_text(_report(manifest), encoding="utf-8")
    return manifest
