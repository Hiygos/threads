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

Ship `threads` as two implementations of one contract
([ADR 0001](docs/adr/0001-two-implementations-one-contract.md)):

- **The plugin**: an installable Claude Code plugin (hooks + a lean skill +
  commands), self-contained, with no edits required to the user's
  `CLAUDE.md`. The hooks are the point: they make the layer self-enforcing.
- **The skill**: for any agent harness, carrying the instructions and the
  scripts the agent runs itself, since no hooks do it for it.

Both follow the same contract, so they can share one `.threads/` folder.
Plugins for harnesses other than Claude Code are **out of scope** for now.

## Where threads live

The user chooses where to start a `.threads/` folder. There are two scopes:

- **Project**: `<project>/.threads/`, with `<project>/THREADS.md`.
- **User**: `~/.agents/.threads/`, with `~/.agents/THREADS.md`. This is shared
  by every project that has no `.threads/` of its own, and it is the same
  folder for the plugin and the skill, whatever the harness. Set
  `THREADS_USER_ROOT` to an absolute path to move it (to
  `$THREADS_USER_ROOT/.threads/` and `$THREADS_USER_ROOT/THREADS.md`).

Resolution rule, applied at every session:

1. Starting from the directory the session starts in, look for a `.threads/`
   there and in each parent. Stop at the git root (checked) or, outside a git
   repository, just below the home directory (the home itself is not
   checked). Outside both, only the start directory is checked. The first
   `.threads/` found is the project scope, and the user scope is **not read
   at all**. The two scopes are never merged.
2. Otherwise, if the user-scope `.threads/` exists, the user scope is used.
3. Otherwise threads stay inactive.

All state (indexes, session markers, the queue of expiry notices) lives inside
the resolved scope, so two scopes never share state.

A scope exists exactly when its `.threads/` folder exists; everything else
inside it is created or rebuilt on demand. A scope is created only on the
user's explicit request (a plain `mkdir .threads` is enough), never by the
plugin or the skill on their own.

Writing to the user scope happens outside the project, so some harnesses ask
for approval on those writes (Claude Code outside its working directory,
Codex in its default sandbox); allow the folder once in the harness's
settings to avoid it.

## Origin

Extracted from a working setup used daily in a personal workspace, where
the mechanism was designed, reviewed, and hardened before being packaged.

## License

MIT — see [LICENSE](LICENSE).
