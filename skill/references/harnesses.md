# Harnesses

Where each harness finds this skill, and which instructions file it always
loads (where the setup snippet goes). Harnesses change: when a row does not
match what you see, or the harness is not listed, **ask the user** instead of
guessing. Check a file exists (or that its folder does) before proposing it.

## Installing the skill

The harness-neutral home is `~/.agents/skills/threads/` (user) or
`.agents/skills/threads/` (project). Codex, Gemini CLI, Cursor, OpenClaw,
OpenCode and GitHub Copilot read `~/.agents/skills/` by default. The others
need a link or a setting:

| Harness | Extra step |
| --- | --- |
| Claude Code | `ln -s ~/.agents/skills/threads ~/.claude/skills/threads` (project: `.claude/skills/`) |
| Hermes Agent | add `~/.agents/skills` to `skills.external_dirs`; project skills load only after `hermes skills trust` |
| Antigravity | link or copy into `~/.gemini/config/skills/` (the CLI: `~/.gemini/antigravity-cli/skills/`) |

On Claude Code, the `threads` plugin enforces the same contract with hooks;
recommend it over this skill there.

## Always-loaded instructions files

The snippet goes in the file for the scope that was created: the project's
file for a project scope, the user's file for the user scope. A project file
is committed with the repository: say so before writing to it.

| Harness | Project scope | User scope |
| --- | --- | --- |
| Codex | `AGENTS.md` at the repository root | `~/.codex/AGENTS.md` |
| Gemini CLI | `GEMINI.md` at the project root (or the name set in `context.fileName`) | `~/.gemini/GEMINI.md` |
| Cursor | `AGENTS.md` at the project root | none as a file (user rules live in the settings): ask |
| OpenCode | `AGENTS.md` at the project root | `~/.config/opencode/AGENTS.md` |
| GitHub Copilot | `.github/copilot-instructions.md`, or `AGENTS.md` | `~/.copilot/copilot-instructions.md` (CLI): ask if unsure |
| Claude Code (skill, no plugin) | `CLAUDE.md` at the project root | `~/.claude/CLAUDE.md` |
| OpenClaw | the workspace's `AGENTS.md` | the same file: its workspace is per user |
| Hermes Agent | `AGENTS.md` at the project root | not verified: ask |
| Antigravity | not verified: ask | `~/.gemini/GEMINI.md` (not verified: ask) |

- Several harnesses on one project often share `AGENTS.md`; one snippet
  there serves them all. When `CLAUDE.md` is a link to `AGENTS.md`, write the
  file it points to (`snippet` follows the link).
- Rerunning `snippet` on a file that already holds it updates it in place.
