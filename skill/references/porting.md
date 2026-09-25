# Porting: running the script from hooks

Optional. Nothing here is installed by this skill, and the skill works
without it. In a harness that runs command hooks, `start` and `check` can be
wired to its session-start and end-of-turn events, so the upkeep no longer
depends on the agent remembering. Set it up only when the user asks, in the
harness's own hook configuration, with their yes for each file you change.

## What to wire

- **Session start** → `start`. Its stdout is the briefing: pass it to the
  model as added context. Run it with the session's working directory as the
  current directory (most harnesses give it as `cwd` in the hook input).
- **End of turn** → `check`. Empty stdout: nothing hangs, let the turn end.
  Otherwise its stdout lists the threads left hanging: pass it back to the
  model (as a block reason or follow-up message) so it declares their
  outcome. Pass it back at most once per turn, or the hook can loop.
- The script reads no stdin and prints plain text: wrap it in the few lines
  of shell the harness needs to turn text into its JSON output. It exits 0
  with no output when there is no scope, and never uses the network.

Use absolute paths to the interpreter and to `scripts/threads`: hooks run
with a minimal environment.

## Where hooks live

| Harness | Session start | End of turn | Configuration |
| --- | --- | --- | --- |
| Codex | `SessionStart` | `Stop` | `~/.codex/hooks.json` or the project's `.codex/` |
| Gemini CLI | `SessionStart` | `AfterAgent` | `.gemini/settings.json`, `~/.gemini/settings.json` |
| Cursor | `sessionStart` (`additional_context`) | `stop` (`followup_message`) | `.cursor/hooks.json`, `~/.cursor/hooks.json` |
| Antigravity | none | `Stop` | `.agents/hooks.json`, `~/.gemini/config/hooks.json` |
| OpenClaw, Hermes | in-process plugin hooks (TS/JS, Python), not shell commands | | their plugin docs |

Each harness names its output keys differently; read its hook documentation
before writing the configuration, and test it once with a throwaway thread.

## What hooks still do not give

Even wired, `check` only lists: it cannot tell which thread this session
changed if another session changed it too, and nothing detects proposals the
user skipped. Retirement notices still wait for the next `start`.
