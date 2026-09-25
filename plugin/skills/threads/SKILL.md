---
name: threads
description: How to work with threads, the open questions with a provisional position kept in `.threads/` across sessions. Load it before any thread work beyond a plain edit of `status` and `touched` — opening a thread, closing and archiving it, deferring, rejecting a proposed thread, merging, reopening one from an archive, fixing an anomaly, acknowledging retirement notices, or migrating an existing threads setup onto this plugin.
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
merge or reopen a thread.

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
- `THREADS.md` and each archive's `INDEX.md` are generated: never edit them.

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

**Writing it.** `question` is one line ending in `?`, understandable without
the conversation. `leaning` is your current position in one line, with its
main reason. Write `question`, `leaning` and notes in the conversation's
language. When your position changes, update `leaning` and `touched` and
append a note saying why.

**Re-read the file right before every edit**: another session may have
changed it.

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

**Migrate** a hand-rolled threads setup onto this plugin:
[migrate](references/migrate.md).

## What the briefing asks of you

- **Anomalies** are files the contract cannot read or in the wrong folder.
  Report each one to the user; never fix, move or delete one silently. Fix it
  by hand only when the user asks.
- **Retired proposals**: tell the user about each one (it can be brought back
  with [reopen](references/reopen.md)). Only after telling them, run the ack
  command printed beside it, exactly as printed.
- **Stale threads**: ask the user whether each still matters, then update,
  defer or close it.
- **Merge review**: look for overlapping threads and propose merges.
- **Read-only scope** (a newer or unreadable contract): change no file in it.

## Done for you

- Upkeep: at every session start and end of turn, expired proposals are
  retired and the generated files rebuilt.
- Retirement: a `proposed` thread unconfirmed for more than 3 days moves to
  `.threads/history/expired/` and is announced in the briefing.
- End of turn: threads you changed this session and left hanging are listed
  for you to settle.
- Skipped questions: questions from your last reply that the user left
  unanswered are listed with your next prompt.

## Never

- Edit `THREADS.md` or an `INDEX.md`, or anything under `.threads/.state/`
  or `.threads/.contract`, except through the ack command or a migration
  the user asked for.
- Create a scope (`.threads/`) the user did not ask for.
- Delete a thread file, overwrite a file in an archive, or reuse an id.
- Add fields, drop unknown fields, or rewrite earlier notes.
- Move a file to `.threads/history/` without a terminal status, or leave a
  terminal status in `.threads/`.
- Fix an anomaly silently.
