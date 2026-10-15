# Analysis specifications

Patent Diffusion Lab maintains two analysis specifications:

- **Paper reproduction:** `reproduce` uses the frozen study configuration, original matched inputs and prespecified sensitivity analyses. See [REPRODUCTION.md](docs/REPRODUCTION.md) for seeds, budgets and numerical verification.
- **Portable analysis:** `compare --profile portable_v1` prepares matched comparisons from standard inputs using the versioned [portable method contract](docs/PORTABLE_V1_METHODS.md).

## Shared event definitions

The four milestones use dated citations between distinct patent families. Field endpoints use complete WIPO35 field sets. Establishment requires a second distinct citing family in the same external field on a strictly later day; subsequent expansion requires first arrival in a new field after earliest establishment. Zero-citation focal families remain in the relevant population.

Observation windows use complete calendar years. Source coverage, grant origin, family definitions and classification mapping must be documented before analysis. Conditional comparisons and opportunity-reference residuals have observational interpretations.

## Versioned statistical choices

The paper profile preserves its original matching, bootstrap and reference settings for numerical reproduction. The portable profile defines its own matching-cell inference, effective-cluster guards, cross-fitted donor support and fixed-support donor-reweighting sensitivity. The two profiles are not interchangeable.

Prespecify the research groups, exclusion rules, matching cells, observation windows, random seeds and reference anchors. Retain unsupported and non-estimable results with their reasons; changes to a study design should be documented as a separate analysis.

## Computational provenance

[PROVENANCE.json](PROVENANCE.json) records the source hashes and extraction history of the research algorithms. Runs preserve input, configuration, code and output hashes. Numerical targets are reserved for verification after estimates have been computed.
