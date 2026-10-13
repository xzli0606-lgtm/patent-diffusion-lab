# Patent Diffusion Lab

[中文说明](README.zh-CN.md) · [Methods](docs/METHODS.md) · [Input schema](docs/INPUT_SCHEMA.md) · [Related tools](docs/RELATED_PROJECTS.md)

**郑州大学管理学院 · 姜红丙、李旭泽**

School of Management, Zhengzhou University

An offline research tool for **four cumulative patent-citation milestones**, matched
AI/non-AI comparisons, and an opportunity-conditioned field reference. It turns
preprocessed DOCDB-family citation events into auditable JSON and Markdown reports.

**Version 0.2.0, Python 3.12.** Includes a full-sample paper execution profile,
a generic matched two-group CLI, and a local browser interface. See
[reproduction and acceptance scope](docs/REPRODUCTION.md),
[English/中文 portable guide](docs/PORTABLE_GUIDE.md), and
[data redistribution review](docs/DISTRIBUTION_REVIEW.md).

Full-sample and cold-start checks: **410/410 manuscript targets, 59/59 parsed
result files, 26 tests**. See [executed acceptance and limitations](docs/ACCEPTANCE.md).
The real AI/non-AI archives remain local and are not included in this code release.

```sh
python -m pip install -r requirements.lock
python -m pip install --no-deps .
python -m patent_diffusion ui --workdir outputs/local-ui
```

## What it measures

| Code | Milestone | Event rule |
|---|---|---|
| H1 | Citation-network entry | First citation from an external DOCDB family |
| H3 | First cross-field arrival | First citation into a non-focal WIPO35 field |
| H4 | Receiving-field establishment | Another distinct citing family reaches the same external field on a strictly later date |
| H5 | Post-establishment new-field arrival | A previously unreached external field is first reached strictly after the earliest H4 date |

H2 is the historical label for first-citation timing, not a fifth milestone.
The milestones are nested cumulative outcomes, not independent state transitions.
The reference preserves citation counts and dates while resampling whole WIPO35
field sets. Residual contrasts are descriptive, not causal or mediation estimates.

## Try it with synthetic data

```sh
git clone https://github.com/xzli0606-lgtm/patent-diffusion-lab.git
cd patent-diffusion-lab
```

Download or clone this repository, enter its directory, then use a Python 3.12
environment. On Windows, `py -3.12 -m venv .venv` creates one; on Linux/macOS use
`python3.12 -m venv .venv`. Activate that environment before these commands:

```sh
python -m pip install -e .
python -m patent_diffusion demo --output outputs/demo
```

The demo generates **400 artificial matched pairs** locally and runs 1-, 3-, and
5-year windows with the same main algorithms. It requires no account, API key,
PATSTAT connection, or source-study data. Installed dependencies are required;
Numba compilation makes the first run slower. The default demo uses 50 reference
draws and 200 bootstrap draws and is a software check, not research evidence.

Read `outputs/demo/results/report.md` and `outputs/demo/results/run.json`.
Synthetic results are labelled and are not compared with manuscript values.
Choose a new output directory each time: existing outputs are never overwritten.

## Analyze your own preprocessed data

Prepare the two Parquet tables described in [the schema](docs/INPUT_SCHEMA.md).
Matching, AI labelling, family consolidation and source-data acquisition must
already be complete.

```sh
patent-diffusion validate --families data/families.parquet --edges data/edges.parquet
patent-diffusion analyze --families data/families.parquet --edges data/edges.parquet --output outputs/my-run --pairs 10000 --smoke
```

The interface reads local files and writes a new output folder. It does not contact
patent databases. **The complete input tables are loaded into memory before the
pair sample is selected**; `--pairs` is not an input-memory limit. Keep real-data
runs local and begin with a suitably prepared, classification-checked input.

Omit `--smoke` for 2,000–10,000 reference draws subject to the frozen MCSE rule,
and 2,000 pair-bootstrap draws. This is more expensive and still does not execute
all manuscript sensitivities. The cutoff is fixed at **2026-06-30**; this version
is intentionally specific to the study's complete Gregorian-year windows.

## Outputs and interpretation

- `1Y.json`, `3Y.json`, `5Y.json`: matched incidence estimates, Cox diagnostics,
  field counts, reference support, precision and manuscript comparisons.
- `run.json`: input hashes, package/Python/dependency versions, sampling and
  reference seeds, contract hash, six-test Holm adjustment, and all windows.
- `report.md`: readable matched comparisons and reference residuals.

See [the output guide](docs/OUTPUTS.md). Non-estimable piecewise diagnostics are
explicitly marked. Very small or perfectly separated samples can have no finite
main estimate; the program stops with an explanation. Smoke completion is not a
formal inference or full-cohort replication pass.

## Development

```sh
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
python -m build
python -m twine check dist/*
python tools/check_release.py
```

GitHub Actions is configured to test Python 3.12 on Windows and Ubuntu. Local
verification and hosted CI are different: a configured workflow is not a hosted
passing badge. See [contribution guidance](CONTRIBUTING.md).

## Methods, provenance and citation

[Methods and implementation coverage](docs/METHODS.md) explain the exact H4/H5
boundaries and reference support rules. [Reproduction differences](docs/REPRODUCTION.md)
separate historical audits from new demo runs. `PROVENANCE.json` records source
function names and hashes; [ANALYSIS_DECISIONS.md](ANALYSIS_DECISIONS.md) records
project decisions. Use [CITATION.cff](CITATION.cff) for software citation; no paper
DOI or public release URL is asserted until assigned.

## License and data

Code, project documentation and the synthetic generator use **Apache-2.0**;
see [LICENSE](LICENSE) and [NOTICE](NOTICE). Third-party dependencies keep their
licenses. No PATSTAT database, real study sample, manuscript, credential or
private result is included. Users obtain and license their data separately.
[Data policy](DATA_POLICY.md) explains the boundary.
