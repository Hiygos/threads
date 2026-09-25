---
name: threads
description: Threads are open questions with a provisional position, kept as Markdown files in a `.threads/` folder so they survive across sessions until an outcome is declared. Use this skill whenever a `.threads/` folder or `THREADS.md` is present, when a question stays open with a position worth keeping, before any thread work (opening, updating, closing, deferring, rejecting, merging, reopening, fixing an anomaly, acknowledging a retirement), or when the user asks to set threads up.
license: MIT
compatibility: Requires Python 3 on PATH (stdlib only)
---

# Threads

A **thread** is an open question with a provisional position, kept across
sessions until an outcome is declared. Test before opening one:

- no position to hold → it is a **task**: put it in your task list;
- nothing left open → it is a **decision**: record it in the project docs;
- true regardless of the work in progress → it is a **fact**: put it in your
  durable memory or the project docs.

Be explicit rather than right: a wrong closure gets corrected, a silent
omission does not. Tell the user in one line whenever you open, close, defer,
merge or reopen a thread. Whoever touches a thread declares its outcome in
the same reply.

## The script

No hooks run for this skill: you run its one script yourself. It lives at
`scripts/threads` inside this skill's folder. Build its **absolute path**
from where this `SKILL.md` was loaded (never rely on a relative path or on a
harness variable), and run it from the directory the session works in: that
directory decides which scope it uses.

```
python3 /absolute/path/to/threads/scripts/threads <subcommand>
```

(`python` instead of `python3` where only that exists.) If it fails to start
(command not found, a syntax error from an old interpreter), tell the user
threads needs Python 3.9 or newer on `PATH`, standard library only, and stop
doing thread upkeep until they fix it. It never uses the network.

| Subcommand | When |
| --- | --- |
| `start` | at the start of every session; read and act on its briefing |
| `check` | before the final reply of any task that wrote to `.threads/` |
| `ack <id>` / `ack all` | only as printed by `start`, after telling the user |
| `regen` | after editing thread files, to rebuild `THREADS.md` and the indexes |
| `init` / `init user` | only when the user asks for a scope (see Setup) |
| `snippet <file>` | only on the user's yes during setup (see Setup) |

Every subcommand but `init` and `snippet` first does the upkeep: it retires
expired proposals and rebuilds the generated files. With no scope it prints
nothing.

## Session start and end of turn

**Start.** Run `start` once per session, before other work. It prints the
briefing: urgent sections first, then the active threads. Handle the urgent
sections as § What the briefing asks of you says.

**End of turn.** Before the final reply of any task that wrote to
`.threads/`, run `check`. For each thread it lists, declare its outcome in
that reply: resolved, deferred, abandoned, or still open with an updated
`leaning`, and set `touched` to today. If `check` says there is nothing to
compare with, run `start`.

## Layout and states

Paths are relative to the scope root the briefing names.

| Folder                      | States                                         |
| --------------------------- | ---------------------------------------------- |
| `.threads/`                 | `proposed`, `open`, `deferred` (active)        |
| `.threads/history/`         | `resolved`, `abandoned`, `merged` (terminal)   |
| `.threads/history/expired/` | `proposed` with `expired:` (retired proposals) |

- `proposed`: you opened it on your own initiative; `open` once the user
  confirms it. A thread the user asked for is born `open`.
- `open` ↔ `deferred`; any active state → a terminal state, moved to
  `.threads/history/`.
- A `proposed` thread unconfirmed for more than 3 days from `opened` is
  retired to `.threads/history/expired/` by the script's upkeep.
- `THREADS.md` and each archive's `INDEX.md` are generated: never edit them.
- Scope: the nearest `.threads/` walking up from the session's directory (to
  the git root) is the project scope; with none, `~/.agents/.threads/` (or
  `$THREADS_USER_ROOT/.threads/`) is the user scope. Never both.

## File anatomy

`.threads/<id>.md`, UTF-8, LF line endings:

```
---
id: cache-invalidation-strategy
status: open
opened: 2026-01-05
touched: 2026-01-07
question: Should the cache be invalidated by events or by TTL?
leaning: Events, with a long TTL as a safety net.
---

## 2026-01-05

Opened: both work; events need a publisher we do not have yet.
```

- The frontmatter is flat `key: value` lines, **not YAML**: no lists, block
  scalars, comments or duplicate keys; one line per value.
- Required, non-empty: `id`, `status`, `opened`, `touched`, `question`.
  Optional: `leaning`. `merged_into` only with `status: merged`.
- The id is kebab-case (`[a-z0-9]+(-[a-z0-9]+)*`), equals the file name
  without `.md`, and is unique across the three folders. No numeric suffixes.
- Dates are local `YYYY-MM-DD`. Set `touched` to today on every edit.
- Never add other fields; keep unknown fields exactly as they are.
- Notes are `## YYYY-MM-DD` sections, chronological and append-only: add at
  the end, never rewrite or delete an earlier note.

**Writing it.** `question` is one line, understandable without the
conversation. `leaning` is your current position in one line, with its main
reason. Write `question`, `leaning` and notes in the conversation's language.
When your position changes, update `leaning` and `touched` and append a note
saying why.

**Re-read the file right before every edit**: another session, or another
harness, may have changed it. After editing thread files, run `regen`.

## Procedures

**Open.** First look for the id (and close synonyms) in `.threads/`,
`.threads/history/` and `.threads/history/expired/`. If it exists anywhere,
reopen it instead ([reopen](references/reopen.md)). Otherwise write
`.threads/<id>.md` with `opened` and `touched` today and a first note.

**Close** (resolved or abandoned):

1. Set `status: resolved` or `status: abandoned` and `touched`; append a
   dated note with the outcome, or the reason it was dropped.
2. Move it without overwriting, then verify:
   `mkdir -p .threads/history && mv -n .threads/<id>.md .threads/history/<id>.md`,
   then check the file is in `.threads/history/` and gone from `.threads/`.
3. If `.threads/history/<id>.md` already exists, stop: leave both files as
   they are and tell the user.

**Defer.** Set `status: deferred` and `touched`, and append a dated note with
why it waits and what would bring it back. It stays in `.threads/`. Back to
work: `status: open` with a note.

**Reject a false-positive proposal.** When the user says a `proposed` thread
is not a thread: set `status: abandoned` and `touched`, append a dated note
`Rejected: not a thread (<why>).`, and move it to `.threads/history/` as in
Close. If it was really a task, a decision or a fact, put it where that
belongs.

**Merge** two overlapping threads: only with the user's approval —
[merge](references/merge.md).

**Reopen** from either archive: [reopen](references/reopen.md).

**Migrate** a hand-rolled threads setup onto this skill:
[migrate](references/migrate.md).

## What the briefing asks of you

- **Retired proposals**: tell the user about each one (it can be brought back
  with [reopen](references/reopen.md)). Only after telling them, run the ack
  command printed beside it, exactly as printed.
- **Anomalies** are files the contract cannot read or in the wrong folder.
  Report each one to the user; never fix, move or delete one silently. Fix it
  by hand only when the user asks.
- **Read-only scope** (a newer or unreadable contract): change no file in it.
- **Merge review**: look for overlapping threads and propose merges.
- **Stale threads**: ask the user whether each still matters, then update,
  defer or close it.

## Setup

Set threads up when the user asks, or propose it once when this skill is
invoked and `start` prints nothing (no scope exists). Never create a scope
the user did not ask for.

1. Ask which scope: the **project** (`init`, created at the git root, or the
   current directory outside git) or the **user** scope shared by projects
   without their own (`init user`). Run it from the session's directory.
2. Relay its outcome, then what this skill cannot guarantee (below), once.
3. Propose the recommended snippet it prints, as strongly recommended: it
   makes every session run `start`. Find the instructions file the harness
   always loads for that scope in [harnesses](references/harnesses.md); when
   unsure, ask the user. For a project file, say it is committed with the
   repository. Write it only on a yes, with `snippet <absolute file path>`:
   it adds the snippet between `<!-- threads:begin -->` and
   `<!-- threads:end -->`, or replaces an earlier copy, never duplicating it.
4. If the skill is not in a folder this harness reads, the same reference
   says which link to add.

A harness with hooks can run `start` and `check` for you:
[porting](references/porting.md) (optional; nothing ships for it).

## What this skill cannot guarantee

Compared with a harness where hooks run the upkeep, this skill relies on you
running the script:

- **Nothing expires unless a script runs.** A proposal is retired at the
  first `start`, `check`, `regen` or `ack` after its 3 days, not on time.
- **No forced outcome at end of turn.** `check` lists what is left hanging;
  nothing stops a reply that skips it.
- **Retirement notices surface only at the next `start`.**
- **No skipped-proposal detection.** A proposal the user leaves unanswered
  is not caught: keep your proposals visible and ask again when it matters.

## Never

- Edit `THREADS.md` or an `INDEX.md`, or anything under `.threads/.state/`
  or `.threads/.contract`, except through the script or a migration the
  user asked for.
- Create a scope (`.threads/`) the user did not ask for.
- Delete a thread file, overwrite a file in an archive, or reuse an id.
- Add fields, drop unknown fields, or rewrite earlier notes.
- Move a file to `.threads/history/` without a terminal status, or leave a
  terminal status in `.threads/`.
- Fix an anomaly silently.
