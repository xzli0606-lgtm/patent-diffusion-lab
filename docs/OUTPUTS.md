# Reading a run

`demo` writes synthetic inputs under `inputs/` and analysis outputs under `results/`.
`analyze` writes directly into the requested new output directory.

| File | Contents |
|---|---|
| report.md | Matched rates and main opportunity-reference summary |
| run.json | Complete manifest, all windows, software/dependency versions, seeds, input and contract hashes |
| 1Y.json / 3Y.json / 5Y.json | Full-input coverage, sampled/classified pairs, models, reference support and results |

`dataset_kind=synthetic` labels generated data; its `comparison_with_paper` is null.
User-preprocessed runs include manuscript reference rates/ORs and descriptive
differences. The code cannot determine whether arbitrary user input corresponds
to the paper cohort; manuscript comparisons should only be interpreted for
appropriately constructed data from that study.

Top-level `SMOKE_ONLY` means reduced computational diagnostics, never a validated
inference. `EXPERIMENTAL_ANALYSIS` means the main non-smoke pipeline ran;
it does not assert a full manuscript replication. `INCOMPLETE_REFERENCE` produces
exit code 2 after saving available results when non-smoke support/precision fails.

Reference statuses include `EXPERIMENTAL_SMOKE`, `COMPLETE`, `NO_SUPPORTED_PAIRS`
and `MCSE_GATE_FAILED`. Interpret `COMPLETE` only as completion of the main
reference and its precision rule. Examine candidate/supported/unsupported pairs;
reference and incidence estimates may describe different retained samples.

`not_estimable` piecewise results carry a reason. A 1Y piecewise trigger also has
only one frozen interval and cannot estimate piecewise contrasts. Main-model
failures stop the run, possibly leaving earlier window outputs; without run.json
and report.md, do not treat a directory as a completed run. Existing output folders
are never overwritten, including failed runs; use a new path.

Estimates and intervals for synthetic/smoke runs illustrate software behavior.
They are not validation of the paper's empirical claims. H4/H5 Holm values refer
to incidence OR tests, not reference-residual significance tests.
