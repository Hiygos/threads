# Migrate

Moving a hand-rolled threads setup (your own hooks, scripts or instructions)
onto this plugin. Do it only when the user asks, one step at a time, telling
the user what each step changes. Never delete or rewrite the user's files
without their yes.

## 1. Retire the old mechanism

The plugin carries its own rules and upkeep. With the user, remove or
disable the old hooks, scripts and any threads section in their instruction
files, so that two mechanisms do not act on the same folder.

## 2. Put the scope where the plugin looks

- A project scope is the nearest `.threads/` from the session's directory,
  up to the git root.
- The user scope is `.threads/` under `$THREADS_USER_ROOT` when that is an
  absolute path, `~/.agents` otherwise. A user scope kept under a
  harness-specific folder is not read at all: move its `.threads/` there,
  after checking none exists yet (if one does, ask the user how to combine
  them).

## 3. Fix the files

The briefing and `THREADS.md` list every file the contract cannot read as
an anomaly. Go through them with the user; common cases from older setups:

- **Suffixed archive copies** (`<id>-2.md` and the like, with `id` naming
  another file): give each its own kebab-case id, in the file name and the
  `id` field together, unique across the three folders. If it is the same
  topic as the other file, ask the user whether to merge the histories
  instead.
- **Missing required fields** (`id`, `status`, `opened`, `touched`,
  `question`): nothing is defaulted. Propose values from the file's own
  notes or the project's history, and write them once the user agrees.
- **States in the wrong folder or unknown to the contract**: map each to
  `proposed`, `open`, `deferred`, `resolved`, `abandoned` or `merged` with
  the user, then move the file to the folder that state belongs in, never
  overwriting.

Unknown fields may stay: they are kept and ignored.

## 4. Carry over pending retirement notices

If the old setup kept unacknowledged retirement notices in a file such as
`.threads/.state/pending-notices.json`, create one empty file
`.threads/.state/notices/<id>` per id it lists (a valid id only), check they
are all there, then remove the old file with the user's yes. The briefing
will show them from then on.

## 5. Clear old private state

Anything else directly under `.threads/.state/` other than `notices/`
(files the old mechanism kept for itself) is no longer read. Remove it with
the user's yes; never touch `.threads/.state/plugin/` or
`.threads/.state/skill/`.

## 6. Check

Start a new session: the briefing should list the threads with no
anomalies. `THREADS.md` and the archive indexes are rebuilt by the upkeep;
if the old ones held text written by hand, tell the user it will be
replaced.
