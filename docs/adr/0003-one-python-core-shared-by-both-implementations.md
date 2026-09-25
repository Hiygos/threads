# One Python core shared by both implementations

The plugin and the skill must produce byte-identical generated files and apply the same thresholds, and neither Claude Code nor any other harness guarantees a runtime. So both are thin adapters (hooks on one side, the `threads` script on the other) over a single core module in Python ≥3.9, standard library only: parsing, expiry, rendering of generated files, and scope creation. The core has one source in this repo and is packaged into both the plugin and the skill, because the skill must install on its own; a check keeps the copies identical. "Two implementations" (ADR 0001) means two ways of delivering the contract, not two codebases; the conformance suite still covers the adapters.

Python is a documented prerequisite. The plugin's hooks run through a small `sh` guard that looks for `python3`, then `python`, and checks the version; without one, SessionStart injects a single "threads is inactive" line and the other hooks exit 0 silently. Supported platforms: macOS, Linux, Windows with Git Bash.

## Considered Options

- Compiled single binary (Go/Rust): runs everywhere, rejected for the cost of building, signing and shipping one binary per platform, on both sides.
- Node: rejected, not guaranteed either (Claude Code's native installer does not need it) and the existing mechanism is stdlib Python.
- POSIX shell: rejected, too fragile for frontmatter parsing and date arithmetic with byte-identical output, and absent on native Windows.
- Separate codebases per implementation: rejected, byte-identical output would rest on the conformance suite alone instead of holding by construction.
