> Historical paper/0.2 schema. Use [portable_v1 standard inputs](INPUT_SCHEMA_V1.md) for the current default.

# Input schema

The canonical paper profile reads **Parquet**. The generic `compare` interface also reads CSV; see [portable schema](PORTABLE_GUIDE.md). It expects the study's preprocessed matched
DOCDB families and dated external-family citation edges. A row in `edges` means
**citing family -> focal (cited) family**. The paper profile preserves the frozen pairs; the generic profile performs explicit exact matching. No PATSTAT extraction is performed. All identifiers must be consistently typed in both tables;
preserve the original native types in paper bundles, because sort order affects deterministic sampling. Do not use float identifiers.

## Families: one row per focal DOCDB family

| Column | Type / constraint | Meaning |
|---|---|---|
| match_id | Non-null string | Exactly two rows per pair |
| ai_indicator | Integer 0 or 1 | Exactly one member of each group per pair |
| docdb_family_id | Unique non-null identifier | Focal family |
| focus_grant_date | Timezone-naive date, midnight | Focal grant date |
| grant_quarter | Non-null string, e.g. 2019Q1 | Precomputed matching quarter |
| primary_cpc4 | Non-null string | Four-character primary CPC matching stratum |
| wipo35_field_nr | Integer 1–35 | One focal WIPO35 field |
| matching_cell | Non-null string | Grant-quarter × primary-CPC4 cluster |

Pair members must agree on quarter, primary CPC4 and matching cell. These fields
must be constructed correctly upstream: the tool verifies pair agreement but
does not reconstruct classifications or certify the matching procedure.
Complete pairs are retained jointly for each 1/3/5-year anniversary at cutoff
2026-06-30. A pair may therefore be eligible for 1Y but not 5Y.

## Edges: one row per focal/citing family pair

| Column | Type / constraint | Meaning |
|---|---|---|
| focus_docdb_family_id | Non-null identifier present in families | Cited family |
| citing_docdb_family_id | Non-null identifier different from focal | External citing family |
| edge_event_date | Timezone-naive date, midnight | Canonical dated citation event |
| focal_wipo35_field_nr | Integer matching the focal row | Focal field |
| citing_wipo35_mask | Integer in 1…2^35−1 when classified | Full citing-family field set |
| citing_wipo35_missing | Non-null boolean | Whether classification is unavailable |

Choose the canonical event for each family-pair edge upstream. Duplicates are
rejected rather than silently deduplicated. Event dates must be on/after focal
grant and on/before cutoff. When classification is missing, the mask can be 0 or
null; do not mark a zero mask as classified.

WIPO35 uses bit zero for field 1. For example, fields {1, 3} give mask
`(1 << 0) | (1 << 2) = 5`. A multi-field citing family remains one citation event;
its entire field set is retained. Receiving-field "arrival" follows citation
origin classification and must not be interpreted as observed technology use.

## Validation and exclusion

`patent-diffusion validate` checks schema, dates, pair consistency, unique external
edges and the full-input classification gates. Before any sampling, classified
candidate-edge coverage must be at least 98.5% in each window; the absolute
AI/non-AI missing-edge-rate difference must be below 1 percentage point.

H1 uses all sampled complete pairs. For field-path endpoints, a family with an
unclassified in-window edge causes its entire matched pair to be excluded.
Reference donor support can cause additional joint pair exclusions, reported
separately. Passing validation does not guarantee finite statistical estimates
or supported donor pools. Missing follow-up or zero candidate edges can stop the
analysis. No source records are edited.
