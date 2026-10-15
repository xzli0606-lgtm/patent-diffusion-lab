# Patent Diffusion Lab

[中文](README.zh-CN.md) · [Portable methods](docs/PORTABLE_V1_METHODS.md) · [Preparation and tutorial](docs/PREPARE_V1.md) · [Standard inputs](docs/INPUT_SCHEMA_V1.md) · [Result interpretation](docs/VALIDATION_V1.md)

**School of Management, Zhengzhou University · Hongbing Jiang、Xuze Li**

**Version 1.0.0 · Python 3.12 · Apache-2.0**

Patent Diffusion Lab analyses patent citation diffusion from local family and event records. It provides citation milestones, matched two-group comparisons and cross-fitted opportunity references, with traceable inputs, reproducible configurations and numerical reports.

Use `compare --profile portable_v1` for standard-input studies and `reproduce` for the associated paper's frozen analysis. The workflows have distinct statistical specifications; see [Paper reproduction](docs/REPRODUCTION.md) and the [portable method contract](docs/PORTABLE_V1_METHODS.md).

## Install and run

Create and activate a Python 3.12 virtual environment. From this source tree:

```sh
python -m pip install -r requirements.lock
python -m pip install --no-deps .
python -m patent_diffusion --version
python -m patent_diffusion.demo_v1 --output tutorial
python -m patent_diffusion prepare --source patstat-local --manifest tutorial/manifest.json --output tutorial/prepared
python -m patent_diffusion validate --profile portable_v1 --families tutorial/prepared/families.parquet --edges tutorial/prepared/events.parquet --config tutorial/comparison.json
python -m patent_diffusion compare --families tutorial/prepared/families.parquet --edges tutorial/prepared/events.parquet --config tutorial/comparison.json --output tutorial/result
python -m patent_diffusion ui --workdir local-ui
```

For a supplied wheel, replace the source installation command with `python -m pip install --no-deps path/to/patent_diffusion_lab-1.0.0-py3-none-any.whl`. Installation requires the dependencies; analysis itself is offline. Use a new output directory for each execution. No automatic resume or overwrite is supported.

The tutorial creates six **synthetic** relational tables and processes them through the actual local PATSTAT adapter. It has 320 focal families, 1,004 canonical citation events and 62 zero-citation families. Its four-entry IPC mapping is artificial and must never be used for real classification. The default is **smoke**, with no inferential claim. Change `execution.mode` to `formal` in the configuration before executing a new study; formal precision budgets are immutable.

Read `report.html`, `results.json`, `method_contract.json`, `run.json` and `output_manifest.json`. `COMPLETED_WITH_LIMITATIONS` means at least one method cannot provide valid inference or precision; it is not full success. CLI exit 0 means processing completed, including limitations; FAILED exits 2. Inspect module statuses when interpreting a report.

## Supported scope

- DOCDB simple families, WIPO35, two researcher-defined groups, exact 1:1 matching without replacement within declared cells including focal field; complete calendar-year windows from 1 to 5 years.
- Standard CSV/Parquet input or **local PATSTAT export** preparation. No database login, remote extraction or automatic source access.
- H1 first external-family citation; H3 first external-field arrival; H4 a second distinct family in the same external field on a strictly later day; H5 a previously unreached field first reached strictly after earliest H4. These are observable citation events, not adoption or causal mechanisms.
- Pair-stratified conditional OR and Cox timing, with effective-cluster and estimability guards; counts and descriptive rates remain available when inference is unsupported.
- Five-fold pair cross-fitting, same-field donor fallback, whole-field-set sampling, prespecified precision, matching-cell bootstrap, and fixed-support donor-reweighting sensitivity. See the method contract for interpretation and limitations.

The browser uploads local files, imports/exports configuration, runs the same CLI/core, shows progress, cancels processing and downloads summary reports. The PATSTAT preparation step uses the CLI. Default downloads omit family/event tables. Source declarations and aggregate results can still contain sensitive information; users determine sharing rights.

## Paper reproduction

Follow [Paper reproduction](docs/REPRODUCTION.md) to calculate the study results from the paired input archives. The numerical reference is read only by the subsequent verification command. The original analysis settings and seeds are preserved.

Earlier generic comparison configurations remain available through `compare --profile legacy_v0_2`. Use `portable_v1` for new standard-input studies. The statistical differences between workflows, including donor reweighting, are documented in the [method contract](docs/PORTABLE_V1_METHODS.md).

## Development and reproducibility

```sh
python -m unittest discover -s tests -v
python -m build
python tools/check_release.py
python -m twine check dist/*
```

See [Result interpretation](docs/VALIDATION_V1.md) for status codes, precision requirements and reproducibility records. Researchers supply their own authorised local records; see the [data policy](DATA_POLICY.md) and [source requirements](docs/DISTRIBUTION_REVIEW.md). Synthetic tutorial data are generated by the package. Use [CITATION.cff](CITATION.cff) to cite the software.
