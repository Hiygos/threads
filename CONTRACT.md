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
  line `---`. The body after it holds dated notes.
- The frontmatter is a strict flat subset, **not YAML**: each non-blank line is
  `key: value`, with `key` matching `[a-z_][a-z0-9_]*`; the value is the rest
  of the line, trimmed. If the value both starts and ends with the same quote
  character (`"` or `'`), those two quotes are removed. Nothing else is
  interpreted: no block scalars, no lists, no comments, no duplicate keys.
- Required fields: `id`, `status`, `opened`, `touched`, `question`, each
  non-empty. Optional: `leaning`.
- Unknown fields are preserved and ignored.
- Active states: `proposed`, `open`, `deferred`.

## Generated files

Generated files are always recomputed from the folders, never edited by hand,
and must be byte-identical whichever implementation wrote them. They are
written through a temp file in the same folder, then renamed.

### `THREADS.md`

Lists the well-formed threads in `.threads/` whose `status` is an active state.
Its exact text is, with `⏎` marking each line end (LF):

```
# THREADS⏎
⏎
> Generated from `.threads/`. Do not edit by hand: edit the thread files,⏎
> and this index is rebuilt on the next upkeep.⏎
```

followed by one group per state that has at least one thread, in this order
and with these labels:

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

with threads sorted by `id` in Unicode code point order, each entry being

```
- **[<id>](.threads/<id>.md)** — <question>⏎
```

followed, when `leaning` is non-empty, by

```
  - leaning: <leaning>⏎
```

The separator in the entry is ` — ` (space, U+2014, space). With no active
thread, the header is followed by `⏎No active threads.⏎`.

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

With no thread in the archive, the header is followed by
`⏎No closed threads.⏎` (history) or `⏎No expired threads.⏎` (expired). The
entries of a non-empty archive are not part of the contract yet.

## Operations

Every implementation must offer:

- **Regenerate**: rebuild the generated files of the resolved scope.
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
