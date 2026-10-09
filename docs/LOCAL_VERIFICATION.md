# Local verification — 2026-10-09

Environment: Windows, Python 3.12, pinned direct numerical dependencies.

- 19 unittest tests passed, including the synthetic CLI end-to-end test.
- 400 synthetic matched pairs completed 1Y, 3Y and 5Y analyses.
- The main reference had supported pairs and used the documented smoke draw counts.
- DataFrame milestone results agreed with the simulation scorer on synthetic histories.
- Same-day recurrence, previously reached fields, target-fold exclusion, minimum
  donor-family counts and focal-field fallback restrictions were checked.
- Cox cluster standard errors were invariant to reordered/gapped DataFrame indices.
- Null pair IDs, invalid masks/flags/dates, duplicate edges and within-family links
  were rejected. Input validation preserved source bytes; output overwrite was rejected.
- Standard source and wheel builds succeeded; twine metadata checks passed.
- A fresh virtual environment installed the wheel and its dependencies; the full
  synthetic demo passed with Python isolated mode, importing from site-packages
  rather than the source checkout.
- Distribution inspection found no input Parquet, private outputs, manuscript,
  local environment or credential files in the built archives.

These checks verify the software behaviors above, not the paper's empirical claims.
No full-cohort research rerun or new PATSTAT query was performed. Hosted GitHub
Actions results are separate from these local checks; Ubuntu is configured but
was not locally executed.
