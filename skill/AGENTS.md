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

- The script has the core resolve the scope from the current directory
  (`CONTRACT.md` § Scope resolution) and is silent when none exists; `init`
  is the exception, since it creates one.
- Subcommands so far: `init [user]` (exits 1 on a refusal), `regen`,
  `ack <id>|all` (exits 2 on a target that is neither). Each one except
  `init` runs the core's upkeep first (`CONTRACT.md` § Operations).

## Verification

- Conformance cases run the script: `python3 -m unittest`.
