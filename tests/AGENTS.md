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
  harness docstring, with how each operation maps to a plugin entry point:
  a hook, the command a plugin skill runs through `!` injection, or a
  command the agent runs itself, such as `ack`). A
  case's fixtures are a sandbox; optional `case.json` keys set the start
  directory (`cwd`), git repos (`git`), linked worktrees (`worktrees`),
  environment (`env`, `{sandbox}` expanded), a silence check (`silent`)
  and an operation run first through the other adapter (`prepare`).
  Adapter output is compared with the sandbox path written as `{sandbox}`.

## Local Contracts

- Stdlib `unittest` only, no dependencies; runnable from a clone with
  `python3 -m unittest`.
- Tests check external behaviour (files on disk, stdout, exit codes), never
  internal shapes or instruction wording.
- Fixtures are synthetic and English; dates come from `THREADS_TODAY`.
- Every test that runs an adapter or resolves a scope sets `HOME` to a
  temporary folder, so a real user scope on the machine is never read or
  written. Tests needing the `git` binary are skipped without it.
- Goldens change only through `python3 -m tests.conformance --update`, and the
  resulting diff is reviewed before committing. Empty fixture folders carry a
  `.gitkeep`, which the comparison ignores.

## Verification

- `python3 -m unittest` runs everything; `python3 -m tests.conformance` runs
  the conformance suite alone.
