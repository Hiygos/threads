# AGENTS.md — tests/

## Purpose

All tests: core unit tests, packaging checks, and the conformance suite that
runs every case against every implementation.

## Ownership

- `test_core.py` — core unit tests, through the core's public interface.
- `test_packaging.py` — packaged core copies identical to the source.
- `test_plugin.py` — the plugin's `sh` guard (fake interpreters on `PATH`) and
  hook I/O, including the briefing's order, the context cap, the Stop gate
  (hanging threads, once per thread, `stop_hook_active`, snapshot kept or
  retaken per source, marker pruning), the skipped-question stash (candidate
  extraction and caps, consumed by UserPromptSubmit, never stale, orphan
  pruning; `CLAUDE_PLUGIN_DATA` is a temp folder), and a read-only scope left untouched
  down to `.state/plugin/` and mtimes (which conformance does not compare),
  and the `threads` skill's files (frontmatter, linked references present,
  no mechanism term such as `snapshot` or `stash` in its text).
- `test_skill.py` — the skill script's `start` snapshot and `check`.
- `conformance/` — the harness (`harness.py`) and one folder per case under
  `conformance/cases/` (`before/`, `after/`, `case.json`; format in the
  harness docstring, with how each operation maps to a plugin entry point:
  a hook, the command a plugin skill runs through `!` injection, or a
  command the agent runs itself, such as `ack`). A
  case's fixtures are a sandbox; optional `case.json` keys set the start
  directory (`cwd`), git repos (`git`), linked worktrees (`worktrees`),
  environment (`env`, `{sandbox}` expanded), a silence check (`silent`)
  and an operation run first through the other adapter (`prepare`).
  Implementation-private state (`.threads/.state/plugin|skill/`, and a
  `.threads/.state/` holding nothing else) is left out of the comparison.
  Adapter output is compared with the sandbox path written as `{sandbox}`,
  and each adapter's ack command prefix as `{threads}`. `start` is compared
  on the briefing's data sections: the plugin's SessionStart context minus
  its rules section (the `# ` section right before the listing).

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
