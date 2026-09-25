# User scope in `~/.agents/`, project root found by walking up

The plugin and the skill must resolve the same folder on every harness, or two agents on one machine keep two memories without noticing. So the user scope lives at `~/.agents/.threads/` with `~/.agents/THREADS.md` (movable with `THREADS_USER_ROOT`): `~/.agents/` is the one directory most harnesses already treat as neutral, and the implementations open it explicitly, so no harness has to discover it the way it discovers `~/.agents/skills/`. The project root is the nearest folder holding `.threads/`, walking up from the start directory to the git root (or to just below `$HOME` outside git), so harnesses opened at different depths of one repo land on the same `.threads/`. In a linked git worktree with no `.threads/` of its own, the walk-up continues to the main worktree's root (via `git rev-parse --git-common-dir`), so a worktree shares its project's threads instead of falling back to the user scope.

## Considered Options

- `~/.claude/.threads/`: rejected, a Claude Code path no other harness has reason to look in.
- `~/.threads/`: rejected, the walk-up would find it from any project under `$HOME` and mistake it for a project scope.
- `${XDG_DATA_HOME:-~/.local/share}/threads/`: rejected, unfamiliar on macOS and used by no agent convention.
- Project root = the start directory only: rejected, a session opened in a subfolder would silently fall back to the user scope while another harness at the repo root uses the project scope.
