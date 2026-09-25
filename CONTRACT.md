# The threads contract

The normative rules both implementations (the plugin and the skill) conform to,
so they can share one scope. The key words **must**, **must not** and **may**
are normative. Terms are defined in `CONTEXT.md`.

This document grows with the implementations: a rule lands here in the same
commit as the conformance cases that check it. Rules not written here are not
part of the contract yet.

Contract version: **1**.

## Scope layout

A scope is a folder holding a `.threads/` folder; its generated index
`THREADS.md` sits beside `.threads/`. The scope exists exactly when
`.threads/` exists: a plain `mkdir .threads` creates one, and everything else
below is created on demand.

- `.threads/` holds the active threads, one file per thread: `.threads/<id>.md`.
- `.threads/history/` is the archive of closed threads, with its generated
  index `.threads/history/INDEX.md`.
- `.threads/history/expired/` is the archive of retired proposed threads,
  with its generated index `.threads/history/expired/INDEX.md`.
- `.threads/.contract` holds the scope's contract version: the version as a
  decimal integer followed by one LF, so `1⏎` (the two bytes `31 0A`) for
  contract 1.
- `.threads/.state/notices/` is the retirement-notice queue (§ Retirement
  notices). Everything else under `.threads/.state/` is implementation-private
  (`.state/plugin/`, `.state/skill/`) and not part of the contract.

## Scope resolution

A session resolves exactly one scope, from the directory it starts in:

1. **Project scope.** Check the start directory, then each parent in turn;
   the first folder holding `.threads/` is the project scope.
   - Inside a git repository (a folder holding a `.git` entry), the git root
     is the last folder checked.
   - Outside git, below the home directory (`$HOME`), the walk stops just
     below it: the home directory itself is never checked.
   - Outside both, only the start directory is checked.
   - In a linked git worktree where nothing was found, the main worktree's
     root (the parent of `git rev-parse --git-common-dir`) is checked last.
     When git cannot answer, this step finds nothing.
2. **User scope.** Otherwise, the user root is `$THREADS_USER_ROOT` when that
   variable is an absolute path, and `~/.agents` otherwise (an empty or
   relative value is ignored). If it holds `.threads/`, it is the user scope.
3. Otherwise there is no scope: every operation is a silent no-op, writes
   nothing and prints nothing.

Scopes are never merged: a project scope found means the user scope is not
read at all.

## Thread files

- A thread file is UTF-8 text. A leading byte order mark is tolerated on read;
  implementations write LF line endings.
- It starts with a frontmatter block: a line `---`, then field lines, then a
  line `---`. The body after it holds dated notes (`## YYYY-MM-DD`),
  chronological and append-only.
- The frontmatter is a strict flat subset, **not YAML**: each non-blank line is
  `key: value`, with `key` matching `[a-z_][a-z0-9_]*`; the value is the rest
  of the line, trimmed. If the value both starts and ends with the same quote
  character (`"` or `'`), those two quotes are removed. Nothing else is
  interpreted: no block scalars, no lists, no comments, no duplicate keys.
  A CR before a line's LF is ignored on read.
- Required fields: `id`, `status`, `opened`, `touched`, `question`, each
  non-empty. Optional: `leaning`. Conditionally required, non-empty:
  `merged_into` when `status` is `merged`, and `expired` in
  `.threads/history/expired/`. A conditional field elsewhere is ignored,
  not an anomaly (a reopened retired proposal keeps its `expired`). There
  are no silent defaults.
- Dates (`opened`, `touched`, `expired`) are local `YYYY-MM-DD`; a malformed
  date is not an anomaly.
- Unknown fields are preserved and ignored; implementations never add fields,
  except `expired`, written by retirement only (§ Retirement).
- The **id** is kebab-case, matching `[a-z0-9]+(-[a-z0-9]+)*` in full, equal to
  the file name without `.md`, and unique across the three folders.

### Folders and states

| Folder                      | States it holds                                  |
| --------------------------- | ------------------------------------------------ |
| `.threads/`                 | `proposed`, `open`, `deferred` (active states)   |
| `.threads/history/`         | `resolved`, `abandoned`, `merged` (terminal)     |
| `.threads/history/expired/` | `proposed`, with `expired` (retired proposals)   |

The **thread files** of a folder are its regular files whose name ends in
`.md` and does not start with `.`, except each archive's own `INDEX.md`.
Nothing else is a thread file or an anomaly: dot entries (`.threads/.contract`,
`.threads/.state/`, …), other files and subfolders are not read as threads.

### Anomalies

A thread file breaking a rule above is an **anomaly**. Anomalies are listed in
`THREADS.md` (§ Generated files), never listed as threads, and never moved,
deleted or rewritten. Each anomaly has one reason: the first that
applies, in this order, with this exact text (`<…>` filled in, backticks
literal):

| Rule broken                                    | Reason                                              |
| ---------------------------------------------- | --------------------------------------------------- |
| The file cannot be opened or read              | `cannot be read`                                    |
| The bytes are not UTF-8                        | `not UTF-8 text`                                    |
| No frontmatter block, or not the flat subset   | `frontmatter missing or not the flat subset`        |
| Required fields missing or empty               | `` missing required field `<f>` `` or `` missing required fields `<f>`, `<g>` `` |
| The id is not kebab-case                       | `` invalid id `<id>` ``                             |
| The id differs from the file name              | `` id `<id>` does not match the file name ``       |
| The status does not belong in the folder       | `` status `<status>` does not belong in `<folder>` `` |
| Another folder holds a file with the same name | `` id `<id>` also used by `<path>`, `<path>` ``     |
| An expired proposal's retirement destination exists and is not a thread file | `` cannot be retired: `<path>` already exists `` |

Missing fields are named in the order `id`, `status`, `opened`, `touched`,
`question`, `merged_into`, `expired`. `<folder>` and `<path>` are relative to
the scope root and `/`-separated, a folder ending in `/`
(`.threads/history/`); the other paths are
sorted in Unicode code point order. Every file sharing a name across folders
is an anomaly; each reports its own earlier reason if it has one. A
retirement whose destination is a thread file is therefore reported with the
shared-name reason, on both files; the last row covers any other entry at the
destination (a folder, a broken link, …), reported on the active file only.

## Generated files

Generated files are always recomputed from the folders, never edited by hand,
and must be byte-identical whichever implementation wrote them. They are
written through a temp file in the same folder, then renamed.

Regeneration writes `THREADS.md` and the `INDEX.md` of each archive folder
that exists; it never creates a folder. Threads are sorted by `id`, and
anomalies by path, in Unicode code point order.

### `THREADS.md`

Lists the anomalies of the whole scope, then the threads of `.threads/`
that are not anomalies. Its exact text is, with `⏎` marking each line end
(LF):

```
# THREADS⏎
⏎
> Generated from `.threads/`. Do not edit by hand: edit the thread files,⏎
> and this index is rebuilt on the next upkeep.⏎
```

followed, when the scope has at least one anomaly, by

```
⏎
## Anomalies⏎
⏎
> These files are not read as threads and are left untouched: fix them by hand.⏎
⏎
<one line per anomaly>
```

each line being `` - `<path>` — <reason>⏎ `` (path relative to the scope
root, reason from § Anomalies), then by one group per state that has at
least one thread, in this order and with these labels:

| State      | Label                              |
| ---------- | ---------------------------------- |
| `open`     | `Open`                             |
| `deferred` | `Deferred`                         |
| `proposed` | `Proposed (awaiting confirmation)` |

Each group is:

```
⏎
## <label>⏎
⏎
<one entry per thread>
```

each entry being

```
- **[<id>](.threads/<id>.md)** — <question>⏎
```

followed, when `leaning` is non-empty, by

```
  - leaning: <leaning>⏎
```

The separator in the entry is ` — ` (space, U+2014, space). With no active
thread, the groups are replaced by `⏎No active threads.⏎`.

### `.threads/history/INDEX.md` and `.threads/history/expired/INDEX.md`

Each archive index is a header in the style of `THREADS.md`'s, followed by
its body. For `.threads/history/INDEX.md` the header is

```
# History⏎
⏎
> Generated from `.threads/history/`. Do not edit by hand: edit the thread files,⏎
> and this index is rebuilt on the next upkeep.⏎
```

and for `.threads/history/expired/INDEX.md`

```
# Expired⏎
⏎
> Generated from `.threads/history/expired/`. Do not edit by hand: edit the thread files,⏎
> and this index is rebuilt on the next upkeep.⏎
```

`.threads/history/INDEX.md` lists the threads of `.threads/history/` that
are not anomalies, in one group per state that has at least one, in this
order and with these labels, each group shaped as in `THREADS.md`:

| State       | Label       |
| ----------- | ----------- |
| `resolved`  | `Resolved`  |
| `abandoned` | `Abandoned` |
| `merged`    | `Merged`    |

Each entry is

```
- **[<id>](<id>.md)** — <question>⏎
```

followed, when `leaning` is non-empty, by `  - leaning: <leaning>⏎`, then,
for a `merged` thread, by `  - merged into: <merged_into>⏎`.

`.threads/history/expired/INDEX.md` lists the threads of
`.threads/history/expired/` that are not anomalies, with no group: the header
is followed by `⏎`, then one entry per thread, shaped as in the history
index, followed by the `leaning` line when non-empty, then
`  - expired: <expired>⏎`.

With no thread to list, the header is followed by `⏎No closed threads.⏎`
(history) or `⏎No expired threads.⏎` (expired).

## Retirement

A `proposed` thread in `.threads/` that is not an anomaly **expires** when its
age exceeds 3 calendar days: today's local date minus its `opened` date is
greater than 3 days (opened on the 6th: still active on the 9th, expired on
the 10th). An `opened` that is not a valid `YYYY-MM-DD` date counts as
expired; an `opened` in the future does not. The TTL is fixed.

Upkeep **retires** every expired thread: it moves `.threads/<id>.md` to
`.threads/history/expired/<id>.md`, creating that folder when missing, with
`status: proposed` kept and exactly two changes, everything else kept byte
for byte (encoding, BOM, line endings, unknown fields, body):

1. The field `expired: <today>` (one line, LF): when the frontmatter already
   has an `expired` line (a proposal moved back after an earlier
   retirement), that line is replaced in place; otherwise the line is
   inserted just before the closing `---`.
2. A dated note appended at the end of the file: if the file does not end
   with LF, one LF first; then

   ```
   ⏎
   ## <today>⏎
   ⏎
   Retired: unconfirmed for more than 3 days.⏎
   ```

The new file is written through a temp file in the destination folder and
then given its name without ever replacing an existing entry; only then is
the source removed. Retirement is idempotent:

- A source that has vanished (moved by another session) counts as done:
  no error, nothing written, no notice.
- A destination that exists is never overwritten: the move is refused and
  the file stays in `.threads/`, reported as an anomaly (§ Anomalies).

A retired file moved back to `.threads/` with one `mv` is a normal thread
again (its `expired` field is ignored there); still `proposed` with the same
`opened`, it retires again at the next upkeep unless its status changes.

## Retirement notices

Each retirement queues one notice for the user: an empty file
`.threads/.state/notices/<id>`, created (with its folders) by the upkeep
that moved the file, and by no other. Creating the file queues the notice;
deleting it acknowledges it. The queue is shared by every implementation: a
notice queued by one is shown and acknowledged by the other. Entries whose
name is not a valid id are ignored. A notice stays queued, and is shown at
every session start, until an agent acknowledges it after telling the user.

## Operations

Every operation on a scope (upkeep and acknowledge) runs the upkeep first.
Every implementation must offer:

- **Upkeep**: retire every expired proposal (§ Retirement), then rebuild the
  generated files of the resolved scope. It writes nothing else: other
  thread files, anomalies included, are left untouched.
- **Acknowledge notices** (`ack <id>` or `ack all`): delete the notice of
  `<id>`, or every queued notice, after the upkeep. Acknowledging a notice
  that is not queued is not an error (it may have been acknowledged through
  the other implementation); a target that is neither `all` nor a valid id
  is refused. An id literally named `all` is acknowledged with `ack all`.
- **Create scope** (`init`), and **create the user scope** (`init user`),
  run on the user's explicit request only:
  - The project scope is created at the git root when the current directory
    is inside a git repository (the folder holding the `.git` entry found by
    the walk-up of § Scope resolution), at the current directory otherwise.
    The user scope is created at the user root of § Scope resolution, which
    is created too if missing.
  - It writes exactly the skeleton: `.threads/`, `.threads/history/`,
    `.threads/history/expired/`, `.threads/.contract` (current contract
    version) and the three generated files, each in its empty form. Nothing
    else is written, inside or outside the scope.
  - It refuses, writing nothing and printing the covering scope's root path,
    when a project scope already covers the current directory (as resolved
    by § Scope resolution, main worktree included). `init user` refuses the
    same way when the user scope already exists. An existing user scope does
    not block creating a project scope, and a project scope does not block
    `init user`.
  - After creating the user scope, it tells the user once that writes to it
    may trigger the harness's approval prompts.
