# AGENTS.md — tests/

## Purpose

All tests: core unit tests, packaging checks, and the conformance suite that
runs every case against every implementation.

## Ownership

- `test_core.py` — core unit tests, through the core's public interface.
- `test_packaging.py` — packaged core copies identical to the source.
- `test_plugin.py` — the plugin's `sh` guard (fake interpreters on `PATH`) and
  hook I/O.
- `conformance/` — the harness (`harness.py`) and one folder per case under
  `conformance/cases/` (`before/`, `after/`, `case.json`; format in the
  harness docstring, with how each operation maps to a plugin hook).

## Local Contracts

- Stdlib `unittest` only, no dependencies; runnable from a clone with
  `python3 -m unittest`.
- Tests check external behaviour (files on disk, stdout, exit codes), never
  internal shapes or instruction wording.
- Fixtures are synthetic and English; dates come from `THREADS_TODAY`.
- Goldens change only through `python3 -m tests.conformance --update`, and the
  resulting diff is reviewed before committing. Empty fixture folders carry a
  `.gitkeep`, which the comparison ignores.

## Verification

- `python3 -m unittest` runs everything; `python3 -m tests.conformance` runs
  the conformance suite alone.
