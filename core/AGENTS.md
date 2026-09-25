# AGENTS.md — core/

## Purpose

The single source of the shared core (`threads_core.py`, ADR 0003): parsing,
rendering of generated files, and every rule that must behave identically in
both implementations.

## Ownership

- `threads_core.py` — the only editable copy of the core.

## Local Contracts

- Python ≥3.9, standard library only.
- **Packaged copies are never edited.** After changing `threads_core.py`, copy
  it over each packaged location: `skill/scripts/threads_core.py`,
  `plugin/scripts/threads_core.py`. A new
  location is added here and to `COPIES` in `tests/test_packaging.py`.
- A behaviour that is part of the contract changes with `CONTRACT.md` and its
  conformance cases in the same commit.
- Adapters call the public functions only; anything they need that is not
  public is added here, not reimplemented in an adapter.

## Verification

- `python3 -m unittest` (core tests in `tests/test_core.py`, copy check in
  `tests/test_packaging.py`).
