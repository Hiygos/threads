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
- Subcommands so far: `init [user]` (exits 1 on a refusal), `start`,
  `check`, `regen`, `ack <id>|all` (exits 2 on a target that is neither). Each one
  except `init` runs the core's upkeep first (`CONTRACT.md` § Operations).
- In a read-only scope (`CONTRACT.md` § Contract version) nothing is
  written: `regen` prints the contract-version warning and exits 0, `ack`
  refuses and exits 1, `start` takes no snapshot and `check` prints the
  warning and exits 0.
- `start` prints the briefing's data sections only; the always-on rules are
  not printed, they belong in `SKILL.md`. Its ack command lines are
  `cd <scope root> && python3 <absolute path of this script> ack <id>`.
- `start` also overwrites the one snapshot of `.threads/` at
  `.threads/.state/skill/snapshot.json`, shared by every skill session of
  the scope (the last `start` wins). `check` prints nothing when no thread
  hangs, otherwise a `# Hanging threads` section: a short instruction, then
  one `` - `<id>` (<status>, touched <touched>) — <question> `` line per
  thread of the core's hanging set. Without a snapshot it prints one line
  asking to run `threads start` and exits 1.

## Verification

- `python3 -m unittest`: the conformance cases and `tests/test_skill.py` run the script.
