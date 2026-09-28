# Generated Artifacts Policy

Claude Ensemble separates source and deterministic fixtures from runtime-generated state.

## Generated and disposable

The following paths are runtime, test, cache, or experiment output and must not be committed:

- `alerts/`
- `caching/test_results/`
- `ga_tuning/results/`
- `learning/autonomous_outcomes/`
- `learning/post_task_outcomes/`
- `results/`

These files may be created locally or in CI and can be deleted when no longer needed.

## Retained history

If an experiment or report is intentionally retained for historical reference, place it under a clearly documented archive/history location and treat it as documentation, not live runtime state.

## Test fixtures

Deterministic fixtures that are required to exercise tests belong in source control, but tests must create disposable outputs in temporary directories or ignored paths rather than depending on previously generated files.

## Clean-workspace rule

A fresh checkout must be sufficient to run the test suite. Tests and tools must not require artifacts from a previous local run.
