# Contributing

Use Python 3.12 in an isolated environment:

```sh
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
python -m patent_diffusion demo --output outputs/contribution-demo
```

For bugs, provide the version, command, traceback and a minimal **synthetic** input.
Include the expected milestone dates and the observed result. A small data example
with a hand-computable answer is especially useful for same-day, distinct-family,
multi-field, horizon and new-field cases.

Keep changes focused. Method changes need explicit documentation of their effect
on event definitions, samples or estimands, plus regression tests and a changelog
entry. Preserve the original algorithm provenance and report unavailable estimates.
Do not silently tune settings to match manuscript numbers.

Only submit code and material you are entitled to contribute. Contributions to
this project are under Apache-2.0 unless explicitly agreed otherwise. Credit
third-party code and preserve its license notices if it is ever incorporated.
Do not attach patent databases, genuine study samples, credentials or the manuscript.

Before a release:

```sh
python -m build
python -m twine check dist/*
python tools/check_release.py
```

Maintainers should verify the actual staged file list and installed-wheel demo.
The private legacy extraction helper is not needed to install or run this package.
