# Current v4 execution decisions

The current full-sample interface is `reproduce`; see [REPRODUCTION.md](docs/REPRODUCTION.md) for exact seeds, source boundaries and numerical acceptance. Current comparisons use the latest v4 manuscript. The historical prototype decisions below describe 0.1.0, not the expanded 0.2.0 scope.

## Historical 0.1.0 experiment

- User-approved scope: the four milestones, basic matched comparison, and the opportunity-conditioned field reference.
- User-approved baseline: retain the v3 paper definitions, use the repaired reproduction implementation, and report differences against the paper.
- Input: read existing hash-identified preprocessed family and dated-edge Parquet files only. The PATSTAT preprocessing and remote queries are outside this experiment.
- Cohorts: complete Gregorian 1-, 3-, and 5-year windows through 2026-06-30.
- Classification gate: candidate-edge coverage at least 98.5%; the absolute AI/non-AI missing-edge-rate gap is below 1 percentage point.
- Matching inference: conditional logistic estimates and pair-stratified Cox with Efron ties; cluster Cox score residuals by matching cell after resetting row indices.
- Field milestones require the frozen WIPO35 sets and distinct external citing families. H4 requires a strictly later event date. H5 requires an event after the earliest H4 date.
- Opportunity reference: five-fold cross-fitting at matched-pair level; donor-pool fallback remains within focal field; minimum 200 edges and 50 distinct citing families; preserve each family's citation-event dates and draw whole WIPO35 masks.
- Full run settings: 2,000 reference draws, extending by 2,000 to 10,000 until H4/H5 MCSE is no greater than 0.1 percentage points; 2,000 pair-bootstrap draws.
- Smoke settings: at most 50 reference draws and 200 bootstrap draws. Smoke output is explicitly not inferential or a paper replication.
- Outputs: new folder only, containing input hashes, per-window estimates, reference support and precision, and descriptive comparisons with the full-cohort v3 targets.
- Interpretation remains observational; the reference residual is not a causal, mediation, or mechanism-share estimate.

## Already documented reproduction differences

The 20261007 full-data reproduction report recorded 183 merged manuscript comparisons: 172 consistent, 9 inconsistent, and 2 not testable. The archived audit reports 408 scalar checks: 388 pass, 18 fail, and 2 not testable; these counts differ because the tables aggregate at different levels. Specific differences include the printed five-year H3 gap (6.38 in Fig. 3 versus 6.39 in the prose/Table 4), some third-family and conditional-arrival bootstrap results, and pool-rebuild bootstrap values after the authorized seed update. These full-data audit counts are cited as historical records, not regenerated in the current sample experiment.

## Open-source preparation (2026-10-09)

- Apache-2.0 selected by the project owner; attribution: 郑州大学管理学院，姜红丙、李旭泽.
- Public entry points are demo, validate and analyze; offline Python 3.12 package.
- Synthetic examples use generated records only and do not compare their rates with the manuscript.
- Related repositories inform packaging/documentation patterns; no third-party implementation was copied.
- The public CLI executes the main pooled reference only. Archived sensitivities remain explicitly outside current coverage.
- Small-sample non-estimable piecewise fits are recorded with a reason while retaining main comparisons.
