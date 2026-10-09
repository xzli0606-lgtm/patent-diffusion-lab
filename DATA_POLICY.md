# Code and data publication boundary

Apache-2.0 applies to this project's code, documentation and synthetic generator.
It does not relicense third-party dependencies, PATSTAT or other external data,
user-supplied files, the source manuscript, or private study outputs.

The demonstration uses artificial identifiers, dates and classifications generated
by code; it does not sample or disguise real patent records. Runtime-generated
Parquet inputs and reports stay in ignored output folders.

Obtain source data under the applicable provider/institutional agreement. Whether
a derived dataset can be shared depends on its contents and governing terms; this
project does not grant that permission. For PATSTAT, consult the agreement covering
your edition and access route, as well as the [EPO terms](https://www.epo.org/en/service-support/ordering/patstat-data-terms-and-conditions).

Do not submit raw data, real small samples, identifiers from private datasets,
credentials, or confidential results with issues or pull requests. Use a synthetic
reproducer and redact local paths from logs. The analysis commands run locally;
there is no hosted upload endpoint, telemetry or automatic database query.

Before distributing an archive or Git commit, inspect its actual file list.
.gitignore does not remove already tracked content. Source and wheel builds use
explicit package rules, and tools/check_release.py checks generated distributions.
