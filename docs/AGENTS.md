# AGENTS.md — docs/

## Purpose

Durable docs for agents working on the plugin: skill configuration, architecture decisions and the acceptance-check map.

## Ownership

- `agents/` — per-repo config read by the engineering skills (issue tracker, triage labels, domain-doc rules). Edit directly; re-run `setup-matt-pocock-skills` only to switch trackers.
- `adr/` — architecture decision records, added by `/domain-modeling` when a decision is hard to reverse, surprising and a real trade-off.
- `acceptance-checks.md` — the retired manual acceptance checks of the original setup, each mapped to the automated tests that replace it (or why it no longer applies). Renaming or removing a test it names updates it in the same commit.

## Local Contracts

- Public repo: no personal paths, names, or real thread content (root § Local Contracts).
