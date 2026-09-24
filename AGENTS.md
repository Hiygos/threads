# AGENTS.md — threads

## Purpose

Source repo of the `threads` Claude Code plugin (see `README.md` for the goal).
This file is the contract for agents working **on** the plugin, and the root of
this repo's DOX hierarchy (see § DOX framework below).

## Ownership

This repo is self-contained: everything needed to work on it is in this file
and the `AGENTS.md` files below it. Nothing outside the repo is part of the
contract.

## Local Contracts

- **Scope: Claude Code only.** Other agents/harnesses are out of scope until
  explicitly reopened.
- **Public repo.** Never commit real thread content, personal paths, names, or
  credentials. Examples and fixtures are synthetic.
- **English everywhere**: code, identifiers, comments, docs, and every string
  the plugin injects into a session.
- **Self-contained plugin.** Installing it must not require editing the user's
  `CLAUDE.md`; the plugin carries its own contract.

## Work Guidance

## Verification

## Child DOX Index

- [`docs/`](docs/AGENTS.md) — agent-facing config (`docs/agents/`) and ADRs (`docs/adr/`, created lazily).

## Agent skills

### Issue tracker

GitHub Issues on this repo, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

---

# DOX framework

- DOX is a high-performance `AGENTS.md` hierarchy, installed in this repo
- Agents must follow DOX instructions across any action, edits included

## Core Contract

- `AGENTS.md` files are binding work contracts for their subtrees
- Work products, source materials, instructions, records, assets, and durable docs must stay understandable from the nearest applicable `AGENTS.md` plus every parent `AGENTS.md` above it

## Read Before Acting

**This binds every action, not only edits** — a read, an `ls`, a `find`, a
`grep`, answering a question without touching anything. A read that starts from
the wrong map produces a wrong answer as easily as a bad edit produces a wrong
file, and it does it silently.

1. Read the root `AGENTS.md` (this file)
2. Identify every file or folder you expect to touch
3. Walk from the repository root to each target path
4. Read every `AGENTS.md` found along each route
5. If a parent `AGENTS.md` lists a child `AGENTS.md` whose scope contains the path, read that child and continue from there
6. Use the nearest `AGENTS.md` as the local contract and parent docs for repo-wide rules
7. If docs conflict, the closer doc controls local work details, but no child doc may weaken DOX

**Open the chain yourself — never wait to be handed it.** Auto-injection depends
on the harness and on the tool you reach with, so it is never a guarantee: step 4
is an action you perform, and it comes **before** the first `find`.

Do not rely on memory. Re-read the applicable DOX chain in the current session.

## Update After Editing

Every meaningful change requires a DOX pass before the task is done.

Update the closest owning `AGENTS.md` when a change affects:

- purpose, scope, ownership, or responsibilities
- durable structure, contracts, workflows, or operating rules
- required inputs, outputs, permissions, constraints, side effects, or artifacts
- user preferences about behavior, communication, process, organization, or quality
- `AGENTS.md` creation, deletion, move, rename, or index contents

Update parent docs when parent-level structure, ownership, workflow, or child index changes. Update child docs when parent changes alter local rules. Remove stale or contradictory text immediately. Small edits that do not change behavior or contracts may leave docs unchanged, but the DOX pass still must happen.

## Notify Every Routing-File Edit

A routing file — `AGENTS.md`, its `CLAUDE.md` symlink, and the index rows inside
them — changes how **every future session** behaves. An edit the maintainer did
not see is a rule they never agreed to, enforced from then on. So: every edit to
one is announced to the maintainer, in the same reply that makes it.

- **Say what changed, not that something changed.** Path, what was added, what
  was removed, why. A generic "DOX pass done" does not count as notification.
- **Volume scales with height.** The root `AGENTS.md` is the top: its edits get
  their own explicit statement, with the changed lines quoted, never folded into
  a list of other work. A top-level folder's `AGENTS.md` gets a named line of its
  own. A deeper child, a symlink, or a single index row gets a mention.
- **No exemptions for small.** A one-line index row, a typo fix, a reordering:
  still an edit to a routing file, still reported.

## Hierarchy

- The root `AGENTS.md` is the DOX rail: repo-wide instructions, global preferences, durable workflow rules, and the top-level Child DOX Index
- Child `AGENTS.md` files own folder-specific instructions and their own Child DOX Index
- Each parent explains what its direct children cover and what stays owned by the parent
- The closer a doc is to the work, the more specific and practical it must be

## Child Doc Shape

- **Every top-level folder carries an `AGENTS.md`, unconditionally.** A top-level
  folder is a domain by definition, so the contract is part of creating it, not a
  later step. Dot-folders (`.claude-plugin/`, `.git/`) are excluded: they hold
  manifests and tooling state, not work.
- **Below the top level**, create a child `AGENTS.md` when a folder becomes a durable boundary with its own purpose, rules, responsibilities, workflow, materials, or quality standards — and record it in the parent's Child DOX Index either way
- **A nested folder that is its own git repo is its own DOX root**: the chain stops at that boundary and its contract lives inside it
- **Every `AGENTS.md` carries a `CLAUDE.md` symlink beside it.** `AGENTS.md` is the cross-agent convention, but Claude Code reads `CLAUDE.md` and ignores `AGENTS.md`: without the symlink, that folder's contract is invisible to this harness
- Work Guidance must reflect the current standards of the project or user instructions; if there are no specific standards or instructions yet, leave it empty
- Verification must reflect an existing check; if no verification framework exists yet, leave it empty and update it when one exists

Default section order:
- Purpose
- Ownership
- Local Contracts
- Work Guidance
- Verification
- Child DOX Index

## Style

- Keep docs concise, current, and operational
- Document stable contracts, not diary entries
- Put broad rules in parent docs and concrete details in child docs
- Prefer direct bullets with explicit names
- Do not duplicate rules across many files unless each scope needs a local version
- Delete stale notes instead of explaining history
- Trim obvious statements, repeated rules, misplaced detail, and warnings for risks that no longer exist

## Closeout

1. Re-check changed paths against the DOX chain
2. Update nearest owning docs and any affected parents or children
3. Refresh every affected Child DOX Index
4. Remove stale or contradictory text
5. Run existing verification when relevant
6. Report any docs intentionally left unchanged and why
7. Notify every routing file you did change, at the volume its height calls for
   (§ Notify Every Routing-File Edit)

## User Preferences

When the maintainer requests a durable behavior change, record it here or in the relevant child `AGENTS.md`.
