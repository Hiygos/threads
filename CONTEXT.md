# threads

A memory layer for open questions that an AI agent carries across sessions, shipped as two implementations of one contract: a skill any agent can run, and a Claude Code plugin.

## Language

### The memory

**Thread**:
An open question with a provisional position, kept across sessions until an outcome is declared.
_Avoid_: issue, todo, note

**Proposed thread**:
A thread the agent opened on its own initiative and the user has not confirmed yet; unconfirmed, it is retired once its TTL passes.
_Avoid_: draft, tentative thread

**Retirement**:
The automatic move of an expired proposed thread into the expired archive; unlike a closing, nobody decided it, so the user must be told.
_Avoid_: deletion, expiry (for the move itself)

**Anomaly**:
A file in a threads folder that the contract cannot read, or whose state does not belong in that folder; reported, never fixed automatically.
_Avoid_: corrupt thread, invalid thread

**Task**:
Work with no position to hold; not a thread.

**Decision**:
A question with nothing left open; not a thread.

**Fact**:
Something true regardless of the work in progress; not a thread.

**Scope**:
The one place a session's threads live: the **project scope** or the **user scope**, never both at once. A scope exists exactly when its `.threads/` folder exists, and only the user creates one.

**Project root**:
The nearest folder, from where the session starts upward, that holds a `.threads/`; the project scope lives there.
_Avoid_: working directory, cwd

**User scope**:
The scope shared by every project with no `.threads/` of its own, one per user and the same for every harness.
_Avoid_: global scope

### The product

**Contract**:
The rules that define threads, their file format and how an agent must treat them; the one thing the skill and the plugin share.
_Avoid_: policy, spec

**Skill**:
The implementation of the contract for any harness: instructions plus the scripts the agent runs itself, since no hooks do it for it.
_Avoid_: provider-agnostic version, portable version, standalone skill

**Plugin**:
The implementation of the contract for Claude Code, where hooks do the upkeep and the instructions shrink to what hooks cannot do.
_Avoid_: Claude Code version

**Instructions**:
The agent-facing text an implementation carries (what the plugin injects and its skill holds, or the skill's own text), written per implementation to conform to the contract, never copied from it.
_Avoid_: contract (for this text)

**Enforcement**:
The part of the plugin that makes the contract self-enforcing instead of relying on the agent's discipline.

**Harness**:
The agent runtime a skill is loaded into (Claude Code, Codex, …).
_Avoid_: provider
