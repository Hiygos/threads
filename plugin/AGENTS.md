# AGENTS.md — plugin/

## Purpose

The plugin: the implementation of the contract for Claude Code. This folder is
the plugin as installed (the marketplace entry in `/.claude-plugin/` points
here), so it must work on its own, with nothing from the rest of the repo.

## Ownership

- `.claude-plugin/plugin.json` — the plugin manifest.
- `hooks/hooks.json` — hook declarations; every command runs through the guard.
- `skills/init/SKILL.md` — `/threads:init [user]`, user-invoked only; its body
  runs `guard.sh init $ARGUMENTS` through `!` injection and the model only
  reports the output.
- `scripts/guard.sh` — the `sh` guard: finds Python ≥3.9 (`python3`, then
  `python`) and runs `hook.py`; without one, SessionStart injects the single
  "inactive" line, `init` prints it as plain text, and every other hook
  exits 0 silently.
- `scripts/hook.py` — the adapter, a thin layer over the core: hook entry
  points (`hook.py <HookEventName>`) and `hook.py init [user]`.
- `scripts/threads_core.py` — packaged copy of `core/threads_core.py`; never
  edited here (see `core/AGENTS.md`).

## Local Contracts

- No state under the plugin root: it is a versioned cache copy replaced on
  update. The guard runs Python with `-B` for the same reason.
- The scope is resolved by the core from the hook input's `cwd`
  (`CONTRACT.md` § Scope resolution); every hook is silent when none exists.
- `guard.sh` uses shell builtins only (it must run with a bare `PATH`).
- Hooks so far: SessionStart (every source) regenerates the generated files
  and injects `THREADS.md`'s text (anomalies, then the listing) as
  `additionalContext`.
- `/threads:init` resolves from the session's current directory and always
  exits 0, a refusal included: a non-zero exit in `!` injection makes Claude
  Code fail the skill instead of passing the outcome to the model.

## Verification

- `python3 -m unittest`: `tests/test_plugin.py` (guard, hook I/O) and the
  conformance suite's `plugin` adapter.
