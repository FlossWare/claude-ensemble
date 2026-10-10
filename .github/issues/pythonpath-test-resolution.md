# Issue: Simplify Python module path resolution across sub-services

**Status:** OPEN
**Priority:** Low / Developer Experience

## Description
Currently, running `pytest` directly at root without setting `PYTHONPATH=.` causes `ModuleNotFoundError` or relative import errors due to sub-service modules (`caching`, `compression`, `cost_tracking`, `server`, etc.) expecting root or sibling directories in Python's module search path.

## Proposed Solution
- Add a root `conftest.py` or `pyproject.toml` configuration adding workspace directories to `pythonpath`.
- Standardize package imports across services to avoid reliance on shell `PYTHONPATH` prefixes.
