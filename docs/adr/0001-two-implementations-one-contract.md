# Two implementations, one contract

The skill (any harness) and the plugin (Claude Code) are built as two separate implementations in this one repo, not as one skill wrapped by hooks: inside the plugin, hooks already do the upkeep, so its instructions would only repeat them, while the skill must carry both the instructions and the scripts the agent runs by hand. What they share is the contract — thread file format, states, folder layout, expiry rules — kept in one normative document both must conform to, because both can operate on the same `.threads/` folder (e.g. Claude Code and Codex in one repo) and any divergence would corrupt the other's data.

## Considered Options

- One identical skill inside and outside the plugin, with hooks as thin adapters over the skill's scripts: rejected, it forces the plugin's instructions to cover work its hooks already do.
- Two fully independent projects, each with its own format: rejected, shared folders would break.
- Two repos: rejected, a format change and both sides' conformance should land in one commit.
