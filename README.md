# threads

A memory for **open questions** that an AI agent carries across sessions.

A *thread* is an open question with a provisional position. It is not a
task (no position to hold), not a decision (nothing left open), and not a
fact (true regardless of the work in progress). Threads live as plain
Markdown files in a `.threads/` folder (see [Where threads live](#where-threads-live)),
and `threads` keeps them honest across sessions:

- **At session start** the agent sees the open threads, the stale ones, its
  own unconfirmed proposals, and any file it cannot read.
- **At the end of a turn** the agent cannot silently leave a thread it
  touched: it has to declare an outcome — resolved, deferred, abandoned,
  or still open with an updated position.
- **Before every prompt** the proposals the agent made and the user
  skipped are caught instead of lost.
- **Proposals expire** after 3 days if nobody confirms them, and the
  expiry is announced — never silent.
- **Overlapping threads get merged** through a review the agent proposes
  and the user approves, keeping full traceability.

## Two implementations, one contract

`threads` ships as two implementations of one contract
([`CONTRACT.md`](CONTRACT.md), [ADR 0001](docs/adr/0001-two-implementations-one-contract.md)),
so both can share one `.threads/` folder (say, Claude Code and Codex in one
repository):

- **The plugin**, for Claude Code: hooks do the upkeep and enforce the
  rules, with no edit to your `CLAUDE.md`.
- **The skill**, for any other harness: the instructions plus a `threads`
  script the agent runs itself, since no hooks do it for it.

## Install

### Claude Code: the plugin

This repository is its own plugin marketplace:

```
/plugin marketplace add Hiygos/threads
/plugin install threads@threads
```

(or `claude plugin marketplace add Hiygos/threads` and
`claude plugin install threads@threads` from a shell). Updates come through
the marketplace (`/plugin marketplace update threads`). Then create a scope
with `/threads:init` (project) or `/threads:init user` (user scope).

### Other harnesses: the skill

Download `threads-skill-<version>.zip` from the
[latest release](https://github.com/Hiygos/threads/releases/latest) and
unpack it into `~/.agents/skills/threads/` (or copy or link `skill/` from a
clone there). Codex, Gemini CLI, Cursor, OpenCode, OpenClaw and GitHub
Copilot read that folder; for a harness that does not, add the link listed in
[`skill/references/harnesses.md`](skill/references/harnesses.md). Then ask
the agent to set threads up: it runs `threads init`, and proposes a short
snippet for the harness's always-loaded instructions file, so that every
session starts with the briefing.

The skill cannot guarantee what the plugin's hooks do:

- **Nothing expires unless a script runs**: a proposal is retired at the
  first `start`, `check`, `regen` or `ack` after its 3 days, not on time.
- **No forced outcome at end of turn**: `check` lists what is left hanging,
  but nothing stops a reply that skips it.
- **Retirement notices surface only at the next `start`.**
- **No skipped-proposal detection**: a proposal the user leaves unanswered
  is not caught.

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
   checked). Outside both, only the start directory is checked. In a linked
   git worktree with no `.threads/` found, the main worktree's root is
   checked too. The first `.threads/` found is the project scope, and the
   user scope is **not read at all**. The two scopes are never merged.
2. Otherwise, if the user-scope `.threads/` exists, the user scope is used.
3. Otherwise threads stay inactive.

All state (indexes, session markers, the queue of retirement notices) lives
inside the resolved scope, so two scopes never share state.

A scope exists exactly when its `.threads/` folder exists; everything else
inside it is created or rebuilt on demand. A scope is created only on the
user's explicit request (`init`, or a plain `mkdir .threads`), never by the
plugin or the skill on their own.

Writing to the user scope happens outside the project, so some harnesses ask
for approval on those writes (Claude Code outside its working directory,
Codex in its default sandbox); allow the folder once in the harness's
settings to avoid it.

## Platforms

macOS and Linux; on Windows, under Git Bash only (native Windows without Git
Bash is unsupported). Both implementations need Python ≥3.9 on `PATH`
(`python3`, or `python`), standard library only; without it the plugin
stays inactive and says so at session start.

## Origin

Extracted from a working setup used daily in a personal workspace, where
the mechanism was designed, reviewed, and hardened before being packaged.

## License

MIT — see [LICENSE](LICENSE).
