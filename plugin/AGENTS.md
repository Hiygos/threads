# AGENTS.md — plugin/

## Purpose

The plugin: the implementation of the contract for Claude Code. This folder is
the plugin as installed (the marketplace entry in `/.claude-plugin/` points
here), so it must work on its own, with nothing from the rest of the repo.

## Ownership

- `.claude-plugin/plugin.json` — the plugin manifest.
- `hooks/hooks.json` — hook declarations; every command runs through the guard.
- `scripts/guard.sh` — the `sh` guard: finds Python ≥3.9 (`python3`, then
  `python`) and runs `hook.py`; without one, SessionStart injects the single
  "inactive" line and every other hook exits 0 silently.
- `scripts/hook.py` — the hook adapter, a thin layer over the core.
- `scripts/threads_core.py` — packaged copy of `core/threads_core.py`; never
  edited here (see `core/AGENTS.md`).

## Local Contracts

- No state under the plugin root: it is a versioned cache copy replaced on
  update. The guard runs Python with `-B` for the same reason.
- The scope is resolved from the hook input's `cwd`; every hook is silent when
  none exists.
- `guard.sh` uses shell builtins only (it must run with a bare `PATH`).
- Hooks so far: SessionStart (every source) regenerates the generated files
  and injects the thread listing as `additionalContext`.

## Verification

- `python3 -m unittest`: `tests/test_plugin.py` (guard, hook I/O) and the
  conformance suite's `plugin` adapter.
