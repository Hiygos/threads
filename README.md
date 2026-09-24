# threads

> Status: **early setup** — nothing here runs yet.

A Claude Code plugin that gives an agent a memory for **open questions**.

A *thread* is an open question with a provisional position. It is not a
task (no position to hold), not a decision (nothing left open), and not a
fact (true regardless of the work in progress). Threads live as plain
Markdown files in the project (`.threads/`), and the plugin keeps them
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

## Origin

Extracted from a working setup used daily in a personal workspace, where
the mechanism was designed, reviewed, and hardened before being packaged.

## License

MIT — see [LICENSE](LICENSE).
