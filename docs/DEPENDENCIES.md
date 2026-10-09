# Dependencies and license boundaries

This is a Python dependency declaration, not a vendored bundle. The wheel contains
only Patent Diffusion Lab code and its archived method specification. pip obtains
third-party packages separately. If distributing a bundled executable or container
later, review the license/NOTICE files shipped with every included dependency.

The following runtime versions were inspected through installed distribution
metadata on 2026-10-09. Labels such as "BSD" below are metadata labels, not a
substitute for the full license text (including bundled native libraries).

| Package | Version | Inspected metadata / license family |
|---|---|---|
| numpy | 1.26.4 | BSD family; native wheel has additional notices |
| pandas | 2.2.2 | BSD-3-Clause |
| scipy | 1.13.1 | BSD family; native wheel has additional notices |
| statsmodels | 0.14.2 | BSD |
| numba | 0.60.0 | BSD |
| pyarrow | 24.0.0 | Apache-2.0 |
| llvmlite | 0.43.0 | BSD metadata; see native/LLVM notices |
| patsy | 1.0.3 | BSD-2-Clause |
| python-dateutil | 2.9.0.post0 | Dual license; see distribution LICENSE |
| pytz | 2026.5 | MIT |
| tzdata | 2026.5 | Apache-2.0 metadata; see included database notices |
| six | 1.17.0 | MIT |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |

Direct dependencies are pinned in pyproject.toml and requirements.txt. Transitive
versions are recorded in the development environment but not all are currently
locked; numerical dependencies are recorded in each run manifest. Future releases
should revalidate behavior before updating the analysis stack.

The related-project survey is design research. Its listed third-party programs
are not dependencies and no source from them was copied into this distribution.
