# threads

A memory layer for open questions that an AI agent carries across sessions, shipped as two implementations of one contract: a skill any agent can run, and a Claude Code plugin.

## Language

### The memory

**Thread**:
An open question with a provisional position, kept across sessions until an outcome is declared.
_Avoid_: issue, todo, note

**Task**:
Work with no position to hold; not a thread.

**Decision**:
A question with nothing left open; not a thread.

**Fact**:
Something true regardless of the work in progress; not a thread.

**Scope**:
The one place a session's threads live: the **project scope** or the **user scope**, never both at once.

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

**Enforcement**:
The part of the plugin that makes the contract self-enforcing instead of relying on the agent's discipline.

**Harness**:
The agent runtime a skill is loaded into (Claude Code, Codex, …).
_Avoid_: provider
