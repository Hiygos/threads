# threads

> Status: **early setup** — nothing here runs yet.

A Claude Code plugin that gives an agent a memory for **open questions**.

A *thread* is an open question with a provisional position. It is not a
task (no position to hold), not a decision (nothing left open), and not a
fact (true regardless of the work in progress). Threads live as plain
Markdown files in a `.threads/` folder (see [Where threads live](#where-threads-live)),
and the plugin keeps them
honest across sessions:

- **At session start** the agent sees the open threads, the stale ones, and
  its own unconfirmed proposals.
- **At the end of a turn** the agent cannot silently leave a thread it
  touched: it has to declare an outcome — resolved, deferred, abandoned,
  or still open with an updated position.
- **Before every prompt** the proposals the agent made and the user
  skipped are caught instead of lost.
- **Proposals expire** after a few days if nobody confirms them, and the
  expiry is announced — never silent.
- **Overlapping threads get merged** through a review the agent proposes
  and the user approves, keeping full traceability.

## Goal

Ship `threads` as an installable Claude Code plugin: hooks + a skill +
commands, self-contained, with no edits required to the user's
`CLAUDE.md`.

The hooks are the point: they are what makes the layer self-enforcing.
A provider-agnostic version (skill and contract only, no hooks) is **out of
scope** for now.

## Where threads live

The user chooses where to start a `.threads/` folder. There are two scopes:

- **Project**: `<project>/.threads/`, with `<project>/THREADS.md`.
- **User**: `~/.claude/.threads/`, with `~/.claude/THREADS.md`. This is shared
  by every project that has no `.threads/` of its own.

Resolution rule, applied at every session:

1. If the project root has a `.threads/`, the project scope is used, and the
   user scope is **not read at all**. The two scopes are never merged.
2. Otherwise, if `~/.claude/.threads/` exists, the user scope is used.
3. Otherwise the plugin stays inactive.

The project root is the directory Claude Code was started in, not a
subfolder the session later works in, so a subfolder never grows a second
`.threads/`. All state (indexes, session markers, the queue of expiry
notices) lives inside the resolved scope, so two scopes never share state.

A scope is created explicitly by the user (e.g. an init command), never by the
plugin on its own. The provider-agnostic skill follows the same rule, stated
as instructions instead of enforced by hooks.

## Origin

Extracted from a working setup used daily in a personal workspace, where
the mechanism was designed, reviewed, and hardened before being packaged.

## License

MIT — see [LICENSE](LICENSE).
