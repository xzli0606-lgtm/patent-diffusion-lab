# Reproduction and known differences

The project follows the v3 study definitions and the repaired archived implementation.
The source-script SHA-256 values and extracted function names are in PROVENANCE.json.
These hashes identify private research sources; they are not download locations.
No full manuscript or real-data replication bundle is distributed here.

| Item | Handling |
|---|---|
| Cox score residuals vs matching-cell row indices | Reset index before clustering; preserves row alignment |
| No eligible donor arrays | Empty arrays returned explicitly, with unsupported strata recorded |
| Deterministic pair sampling | Sampled separately within complete 1/3/5Y cohorts; not full-cohort parity |
| Reference seeds | Fixed archived seeds are recorded independently of the sampling seed |
| Non-estimable piecewise fit on small synthetic samples | Record reason and retain available main comparisons; no substituted estimate |
| Synthetic demo | Explicit synthetic label; manuscript comparisons disabled |
| Public input validation | Reject null pair IDs, fractional/zero classified masks and non-boolean missing flags |
| Non-smoke computation | Enforce at least 2,000 bootstrap draws and 2,000–10,000 initial reference draws |

The historical 2026-10-07 full-data audit recorded 183 merged manuscript comparisons:
172 consistent, 9 inconsistent, 2 not testable. Its 408 scalar checks were 388 pass,
18 fail, 2 not testable. Different aggregation explains the different totals.
These are previously recorded audit counts, not rerun by this open-source build.

A known displayed discrepancy is the 5Y H3 gap: 85.31 − 78.93 = 6.38 from rounded
rates, while prose/Table 4 report 6.39 from underlying values. The package retains
the rounded rate targets and exposes arithmetic differences; it must not silently
claim exact agreement with every displayed manuscript gap. Other historical
differences include third-family, conditional-arrival and rebuilt-pool bootstrap
results; those sensitivities are outside the current CLI.

A smoke run on a small real sample checks portability, schema and program execution.
Differences from the full paper mix sample composition and implementation factors;
they cannot by themselves isolate a bug or validate a scientific conclusion.
