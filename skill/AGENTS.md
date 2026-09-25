# AGENTS.md — skill/

## Purpose

The skill: the implementation of the contract for any harness. This folder is
the skill as installed (`~/.agents/skills/threads/`), so it must work on its
own, with nothing from the rest of the repo.

## Ownership

- `scripts/threads` — the script the agent runs; a thin adapter over the core.
- `scripts/threads_core.py` — packaged copy of `core/threads_core.py`; never
  edited here (see `core/AGENTS.md`).

## Local Contracts

- The script resolves the scope from the current directory and is silent when
  none exists.
- Subcommands so far: `regen`.

## Verification

- Conformance cases run the script: `python3 -m unittest`.
