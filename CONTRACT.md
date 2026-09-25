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
`THREADS.md` sits beside `.threads/`.

- `.threads/` holds the active threads, one file per thread: `.threads/<id>.md`.

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

## Operations

Every implementation must offer:

- **Regenerate**: rebuild the generated files of the resolved scope.
