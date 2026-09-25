# AGENTS.md — plugin/

## Purpose

The plugin: the implementation of the contract for Claude Code. This folder is
the plugin as installed (the marketplace entry in `/.claude-plugin/` points
here), so it must work on its own, with nothing from the rest of the repo.

## Ownership

- `.claude-plugin/plugin.json` — the plugin manifest.
- `hooks/hooks.json` — hook declarations (SessionStart, Stop); every command
  runs through the guard.
- `skills/init/SKILL.md` — `/threads:init [user]`, user-invoked only; its body
  runs `guard.sh init $ARGUMENTS` through `!` injection and the model only
  reports the output.
- `scripts/guard.sh` — the `sh` guard: finds Python ≥3.9 (`python3`, then
  `python`) and runs `hook.py`; without one, SessionStart injects the single
  "inactive" line, `init` and `ack` print it as plain text, and every other
  hook exits 0 silently.
- `scripts/hook.py` — the adapter, a thin layer over the core: hook entry
  points (`hook.py <HookEventName>`), `hook.py init [user]` and
  `hook.py ack <id>|all`.
- `scripts/threads_core.py` — packaged copy of `core/threads_core.py`; never
  edited here (see `core/AGENTS.md`).

## Local Contracts

- No state under the plugin root: it is a versioned cache copy replaced on
  update. The guard runs Python with `-B` for the same reason.
- The scope is resolved by the core from the hook input's `cwd`
  (`CONTRACT.md` § Scope resolution); every hook is silent when none exists.
- `guard.sh` uses shell builtins only (it must run with a bare `PATH`).
- Hooks so far: SessionStart (every source) runs the core's upkeep and
  injects as `additionalContext` the briefing (`CONTRACT.md` § Briefing):
  the core's urgent sections, then the always-on rules (`RULES` in
  `hook.py`: adapter text, not contract; ~1.5k chars), then the listing.
- SessionStart also writes the session marker
  `.threads/.state/plugin/sessions/<session_id>.json` (`{"snapshot", "blocked"}`,
  JSON): a fresh snapshot of `.threads/` on `startup`/`clear`, the existing one
  kept on `resume`/`compact`. It prunes markers untouched for
  `MARKER_MAX_AGE_DAYS` (7); a kept marker is touched. A session id outside
  `[A-Za-z0-9][A-Za-z0-9_-]*` gets no marker.
- Stop runs the upkeep (so generated files are rebuilt on every Stop), then,
  unless `stop_hook_active` or no session id, blocks with `STOP_REASON` on
  the core's hanging set against the session's snapshot, minus the marker's
  `blocked` ids, which it then records: each thread blocks at most once per
  session. With no marker it writes one and lets the turn end.
- The gate compares with the session's own snapshot: a thread another session
  changed before this one started is never reported, but one another session
  changes concurrently, without setting today's `touched`, is indistinguishable
  and is reported (once).
- `CONTEXT_CAP` (10,000 characters) and `LEANING_MAX` are `hook.py`
  constants. Only the listing is cut to fit: whole entry lines from its end,
  never its header, replaced by one marker line pointing at `THREADS.md`.
  Urgent sections and rules are never cut, so when they alone exceed the
  cap the context does too.
- Each retirement notice carries the exact command line the agent runs to
  acknowledge it: `cd <scope root> && sh <absolute path of guard.sh> ack <id>`
  (paths shell-quoted), built from the installed plugin's own location,
  since `${CLAUDE_PLUGIN_ROOT}` is not in the agent's shell.
- In a read-only scope (`CONTRACT.md` § Contract version) nothing is
  written, `.state/plugin/` included: SessionStart only injects the
  briefing, Stop is silent, and `ack` refuses and exits 1.
- `/threads:init` resolves from the session's current directory and always
  exits 0, a refusal included: a non-zero exit in `!` injection makes Claude
  Code fail the skill instead of passing the outcome to the model.

## Verification

- `python3 -m unittest`: `tests/test_plugin.py` (guard, hook I/O) and the
  conformance suite's `plugin` adapter.
