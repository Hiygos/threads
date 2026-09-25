# AGENTS.md — skill/

## Purpose

The skill: the implementation of the contract for any harness. This folder is
the skill as installed (`~/.agents/skills/threads/`), so it must work on its
own, with nothing from the rest of the repo. The release zip is this folder
minus `AGENTS.md`/`CLAUDE.md`, dotfiles and `__pycache__`.

## Ownership

- `SKILL.md` — the standard Agent Skills entry point (frontmatter: `name`,
  `description`, `license`, `compatibility` only): the full agent-facing
  contract and procedures for a harness without hooks, setup, and the
  "What this skill cannot guarantee" section. Instructions, not contract.
- `VERSION` — the product semver and one LF; always equal to the plugin
  manifest's `version` (`scripts/AGENTS.md`).
- `references/` — loaded on demand from `SKILL.md`: `merge.md`, `reopen.md`,
  `migrate.md` (adapted from the plugin's, never copied blindly),
  `harnesses.md` (install link and always-loaded instructions file per
  harness; unverified rows say "ask") and `porting.md` (optional hook
  wiring for `start`/`check`; nothing ships for it).
- `scripts/threads` — the script the agent runs; a thin adapter over the core.
- `scripts/threads_core.py` — packaged copy of `core/threads_core.py`; never
  edited here (see `core/AGENTS.md`).

## Local Contracts

- The script has the core resolve the scope from the current directory
  (`CONTRACT.md` § Scope resolution) and is silent when none exists; `init`
  is the exception, since it creates one.
- Subcommands: `init [user]` (exits 1 on a refusal), `snippet [<file>]`,
  `start`, `check`, `regen`, `ack <id>|all` (exits 2 on a target that is
  neither). Each one except `init` and `snippet` runs the core's upkeep
  first (`CONTRACT.md` § Operations).
- `init` prints the core's outcome, then (on a refusal too) skill-only text
  starting at a blank line and a `# ` line: the lost-guarantees notice
  (`LIMITS`, exactly once) and the recommended snippet with how to write it.
  The conformance harness compares only the outcome.
- `snippet` alone prints the snippet (`SNIPPET`, a pointer, not contract,
  between `<!-- threads:begin -->` / `<!-- threads:end -->`); `snippet
  <file>` writes it idempotently: the first marked block is replaced, later
  ones removed, otherwise it is appended after a blank line; a missing file
  (and its folders) is created, a symlink's target is written, line endings
  and mode are kept. Unpaired markers: nothing written, exit 1.
- In a read-only scope (`CONTRACT.md` § Contract version) nothing is
  written: `regen` prints the contract-version warning and exits 0, `ack`
  refuses and exits 1, `start` takes no snapshot and `check` prints the
  warning and exits 0.
- `start` prints the briefing's data sections only; the always-on rules are
  not printed, they belong in `SKILL.md`. Its ack command lines are
  `cd <scope root> && <interpreter> <absolute path of this script> ack <id>`,
  with `<interpreter>` the absolute path of the Python running the script
  (`sys.executable`, else `python3`), all shell-quoted.
- `start` also overwrites the one snapshot of `.threads/` at
  `.threads/.state/skill/snapshot.json`, shared by every skill session of
  the scope (the last `start` wins). `check` prints nothing when no thread
  hangs, otherwise a `# Hanging threads` section: a short instruction, then
  one `` - `<id>` (<status>, touched <touched>) — <question> `` line per
  thread of the core's hanging set. Without a snapshot it prints one line
  asking to run `threads start` and exits 1.

## Verification

- `python3 -m unittest`: the conformance cases and `tests/test_skill.py` run
  the script; `test_skill.py` also checks `SKILL.md`'s frontmatter and links,
  and runs `start` from a copy of this folder alone.
