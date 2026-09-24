# Agent Skills across harnesses

Research for [#3](https://github.com/Hiygos/threads/issues/3): how a **skill** that carries instructions plus bundled scripts gets packaged, discovered and run across **harnesses**, and which hook points each harness exposes that the skill could document as optional. Sources were checked on 2026-09-24.

**Legend:** **V** = verified in the harness's own docs or source (linked). **I** = inferred from those docs, not stated outright. **?** = could not be verified.

## 1. The format: Agent Skills open standard

Spec: <https://agentskills.io/specification> (V). A skill is a directory with a required `SKILL.md`: YAML frontmatter, then a Markdown body.

| Field | Req. | Constraint |
|---|---|---|
| `name` | yes | 1-64 chars, `a-z0-9-`, no leading, trailing or double hyphen, **must match the parent directory name** |
| `description` | yes | 1-1024 chars. Says what the skill does and when to use it |
| `license` | no | License name or a bundled license file |
| `compatibility` | no | ≤500 chars. Environment needs, e.g. "Requires Python 3.14+ and uv" |
| `metadata` | no | Map of string to string. Clients store their own extensions here |
| `allowed-tools` | no | Experimental. A space-separated list of pre-approved tools. Support varies |

- The spec suggests `scripts/`, `references/` and `assets/` directories. On scripts it says: "Supported languages depend on the agent implementation. Common options include Python, Bash, and JavaScript." (V)
- **Progressive disclosure.** At startup the agent loads only `name` and `description`. It loads the body when the skill is activated, and loads other files only when the body references them. The spec recommends keeping `SKILL.md` under 500 lines and under about 5000 tokens. (V)
- **Paths.** The body references files by paths relative to the skill root. The scripts guide says commands "are relative to the **skill directory root**, because the agent runs commands from there" ([using-scripts](https://agentskills.io/skill-creation/using-scripts)). The client guide tells harnesses to resolve those paths against the skill directory and pass absolute paths to tools ([adding-skills-support](https://agentskills.io/client-implementation/adding-skills-support)). (V) In practice the agent's working directory is usually the project, so the SKILL.md should tell the agent to build absolute paths itself. (I)
- **Script guidance** (V, same page):
  - no interactive prompts ("a hard requirement")
  - `--help` output
  - structured stdout, with diagnostics on stderr
  - idempotent
  - a `--dry-run` flag for stateful operations
  - meaningful exit codes
  - bounded output
- **Dependencies.** Python scripts can declare dependencies inline with PEP 723 and run under `uv run`. That needs uv installed. The standard does not require any runtime. (V)
- **Paths are not part of the spec.** The spec does not say where skills live. The client guide recommends that harnesses scan `<project>/.agents/skills/` and `~/.agents/skills/` next to their own directories, and says project scope overrides user scope on a name collision. It also suggests gating project skills on a trust check. (V)
- **Validation.** The `skills-ref validate ./my-skill` tool checks frontmatter ([repo](https://github.com/agentskills/agentskills/tree/main/skills-ref)). (V)
- **Adoption.** The [client showcase](https://agentskills.io/clients) lists more than 40 clients, including every harness below. (V)

## 2. Per-harness table

"Scripts" means the agent can run bundled scripts through its own shell tool. None of these harnesses ships a Python interpreter for skills, so `python3` has to be on the user's PATH. (I, because no doc promises a runtime.)

| Harness | Project path(s) | User path(s) | Reads `~/.agents/skills` by default? | Scripts | Session-start | Pre-prompt | End-of-turn |
|---|---|---|---|---|---|---|---|
| **Claude Code** (baseline) | `.claude/skills/` in cwd and every parent up to the repo root | `~/.claude/skills/`, plugins | **No** (V: not mentioned anywhere in the docs) | Yes, via the Bash tool. `${CLAUDE_SKILL_DIR}` expands to the skill directory (V) | `SessionStart` | `UserPromptSubmit` | `Stop` |
| **Codex CLI** | `.agents/skills` in cwd and every parent up to the repo root | `$HOME/.agents/skills`. Admin: `/etc/codex/skills` | **Yes** (V) | Yes, through the shell tool under the sandbox and approvals (I). Default workspace-write mode asks before writing outside the workspace (V) | `SessionStart` | `UserPromptSubmit` | `Stop` (V) |
| **Gemini CLI** | `.gemini/skills/`, `.agents/skills/` (the `.agents` alias wins) | `~/.gemini/skills/`, `~/.agents/skills/`, extensions | **Yes** (V) | Yes. On activation the skill directory joins the allowed paths, after a consent prompt (V) | `SessionStart` | `BeforeAgent` | `AfterAgent` (V) |
| **Antigravity** (IDE / 2.0 / CLI) | `.agents/skills/` (legacy `.agent/skills/`) | `~/.gemini/config/skills/` (IDE, 2.0). `~/.gemini/antigravity-cli/skills/` (CLI). Legacy: `~/.gemini/antigravity/skills/` | **No** (V: not in the documented list) | Yes. The docs say to treat scripts as black boxes and run `--help` first (V) | none documented | `PreInvocation` (per model call) | `Stop` ("when execution terminates") (V) |
| **Cursor** | `.agents/skills/`, `.cursor/skills/`. Also reads `.claude/skills/`, `.codex/skills/`. Scans nested directories | `~/.agents/skills/`, `~/.cursor/skills/`, `~/.claude/skills/`, `~/.codex/skills/` | **Yes** (V) | Yes, "any language" (V) | `sessionStart` (returns `additional_context`) | `beforeSubmitPrompt` | `stop` (`followup_message`, which can loop) (V) |
| **OpenClaw** | `<workspace>/skills`, `<workspace>/.agents/skills` | `~/.agents/skills`, `<state-dir>/skills`, `skills.load.extraDirs` | **Yes** (V) | Yes, via the `exec` tool. `{baseDir}` expands to the skill directory. `metadata.openclaw.requires.bins` can gate loading on e.g. `python3` (V) | `agent:bootstrap` (can add context files) | `message:received` / plugin `before_prompt_build` | `message:sent` / plugin `agent_end` (V) |
| **Hermes Agent** | `.hermes/skills/`, `.agents/skills/` (only after `hermes skills trust`) | `~/.hermes/skills/`. Other directories only through `skills.external_dirs` | **No**, opt-in via `external_dirs` (V) | Probably, through its terminal tool (I). Script execution is **not documented** (?) | plugin `on_session_start` | plugin `pre_llm_call` (can inject context) | plugin `post_llm_call` (observer only) (V) |
| **OpenCode** | `.opencode/skills/`, `.claude/skills/`, `.agents/skills/`, walking up to the git worktree root | `~/.config/opencode/skills/`, `~/.claude/skills/`, `~/.agents/skills/` | **Yes** (V) | Yes (I) | not researched | not researched | not researched |
| **GitHub Copilot** (CLI, cloud agent, VS Code, JetBrains) | `.github/skills`, `.claude/skills`, `.agents/skills` | `~/.copilot/skills`, `~/.agents/skills` | **Yes** (V) | Yes (I) | not researched | not researched | not researched |

### Sources per harness

- **Claude Code.** Skills: <https://code.claude.com/docs/en/skills>. The raw page has no mention of `.agents`.
- **Codex CLI.**
  - Skills: <https://learn.chatgpt.com/docs/build-skills> (redirected from `developers.openai.com/codex/skills`). Codex follows symlinked skill folders. A skill can carry an optional `agents/openai.yaml` with `policy.allow_implicit_invocation` and `dependencies.tools`. Duplicate names across scopes are not merged, so both copies appear.
  - Hooks: <https://learn.chatgpt.com/docs/hooks>. The docs say "Hooks are enabled by default" and `[features] hooks = false` turns them off. Hooks are read from `~/.codex/hooks.json` or `config.toml` and from `<repo>/.codex/…`. `SessionStart`, `UserPromptSubmit` and `Stop` can return `additionalContext`.
  - Sandbox: <https://developers.openai.com/codex/concepts/sandboxing>, <https://developers.openai.com/codex/agent-approvals-security>.
- **Gemini CLI.**
  - Skills: <https://geminicli.com/docs/cli/skills/>. Activation goes through the `activate_skill` tool and a consent prompt.
  - Hooks: <https://geminicli.com/docs/hooks/>. Hooks are read from `.gemini/settings.json`, `~/.gemini/settings.json` and extensions. They take JSON on stdin and must print only JSON on stdout.
- **Antigravity.** Skills: <https://antigravity.google/docs/skills>. Hooks: <https://antigravity.google/docs/hooks>, configured in `.agents/hooks.json` and `~/.gemini/config/hooks.json`. Only five hook events are listed: PreToolUse, PostToolUse, PreInvocation, PostInvocation, Stop.
- **Cursor.** Skills: <https://cursor.com/docs/context/skills>. Hooks: <https://cursor.com/docs/agent/hooks>, configured in `.cursor/hooks.json` and `~/.cursor/hooks.json`.
- **OpenClaw.**
  - Skills: <https://docs.openclaw.ai/tools/skills>.
  - Hooks: <https://docs.openclaw.ai/automation/hooks> and <https://docs.openclaw.ai/automation/hooks/event-types>. These are TS/JS handlers that run in the Gateway process. Workspace hooks need explicit enablement.
  - Plugin hooks: <https://docs.openclaw.ai/plugins/hooks>.
  - OpenClaw's "workspace" is the agent's workspace, not necessarily a code repository (I).
- **Hermes Agent.** Skills: <https://hermes-agent.nousresearch.com/docs/user-guide/features/skills>. Hooks: <https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks>. Hermes has four hook systems:
  - Gateway hooks: never loaded by the CLI.
  - Plugin hooks: Python `ctx.register_hook()`, run in both the CLI and the gateway.
  - Shell hooks: set in `config.yaml`.
  - The upstream tracker records bugs where plugin hooks never fired: [#2817](https://github.com/NousResearch/hermes-agent/issues/2817), [#102592](https://github.com/NousResearch/hermes-agent/issues/102592). Treat hook reliability as **?**.
- **OpenCode.** <https://opencode.ai/docs/skills/>.
- **GitHub Copilot.** <https://docs.github.com/en/copilot/concepts/agents/about-agent-skills>.

## 3. Notes

- **The format is portable. Placement is not.** Every harness here parses `SKILL.md` with `name` and `description`, and ignores or tolerates unknown frontmatter. Extensions are namespaced:
  - Claude Code: `disable-model-invocation`, `hooks`, `context`, `${CLAUDE_SKILL_DIR}`
  - Codex: `agents/openai.yaml`
  - OpenClaw: `metadata.openclaw`
  - Hermes: `metadata.hermes`, `platforms`
  - Cursor: `paths`, `disable-model-invocation`

  A skill that uses only the standard fields loads everywhere.
- **No shared variable points to the skill's own directory.** Claude Code has `${CLAUDE_SKILL_DIR}` and OpenClaw has `{baseDir}`. Gemini CLI injects the folder structure, and Codex and Cursor expose the location in the catalog. The spec's portable answer is "relative to the skill root". The agent must turn that into an absolute path before calling a shell tool.
- **Hooks are per harness and never part of a skill.** Several harnesses let a skill-carrying package ship hooks: Claude Code plugins, Gemini CLI extensions, Antigravity CLI plugins, OpenClaw plugins and Hermes plugins. A bare Agent Skills directory cannot register hooks in any of them. Claude Code's `hooks` frontmatter is the exception, and it applies only in Claude Code and only after the skill is invoked. (V for Claude Code and Gemini, I for the rest.)
- **Hook shapes line up well for command hooks.** Claude Code, Codex, Gemini CLI, Cursor and Antigravity all run a shell command, pass JSON on stdin and read JSON on stdout. Only the event names and the output keys differ, for example `additionalContext` in Codex versus `additional_context` in Cursor. OpenClaw and Hermes hooks are in-process code (TS/JS and Python), not shell commands.
- **Runtime.** No harness guarantees Python. Python ships with macOS only through the Command Line Tools and on Windows only as `py`/`python`, so this is a user prerequisite. (I)

## 4. Implications for the spec

- **Target the open standard only.** Use `name` (equal to the folder name, e.g. `threads`), `description`, `license`, and `compatibility: Requires Python 3 on PATH (stdlib only)`. Keep harness-specific extras out of the shared `SKILL.md`, or in namespaced `metadata` if they are needed at all.
- **Bundle scripts under `scripts/`.** Each script should be stdlib-only, non-interactive, idempotent and JSON-to-stdout, with `--help` and `--dry-run` on anything that moves or regenerates files. The SKILL.md tells the agent to resolve `scripts/…` against the skill directory and run `python3 <abs-path>`, with the `.threads/` location passed explicitly and never inferred from cwd.
- **Harness-neutral user-scope install path: `~/.agents/skills/threads/`.** Codex, Gemini CLI, Cursor, OpenClaw, OpenCode and Copilot read it by default. Three need an extra step:
  - Claude Code: symlink it into `~/.claude/skills/`.
  - Hermes: add `~/.agents/skills` to `skills.external_dirs`.
  - Antigravity: copy or symlink into `~/.gemini/config/skills/` (or `~/.gemini/antigravity-cli/skills/` for the CLI).

  Install docs should name exactly these three.
- **Project-scope install path: `.agents/skills/threads/`.** It is read by every harness here except Claude Code, which reads `.claude/skills/`. It is also project-shadowing: project scope overrides user scope everywhere this was documented. Hermes loads project skills only after `hermes skills trust`, and the client guide recommends trust gating generally, so the spec should not rely on project-scope skills loading silently.
- **Don't confuse the skill's install path with the threads' storage path.** `~/.agents/skills/` is where the skill's code lives, not where user-scope threads live. In Codex's default sandbox, a user-scope `.threads/` outside the workspace triggers an approval prompt on every write. The spec should document that behaviour, or have the skill add a writable root in its setup notes.
- **Upkeep must be agent-driven by default.** Only three hook points are common enough to document as optional accelerators, never as requirements:
  - *session-start*: every harness except Antigravity has one.
  - *pre-prompt*: Claude Code, Codex, Gemini, Cursor, Hermes and OpenClaw.
  - *end-of-turn*: Claude Code, Codex, Gemini, Cursor and Antigravity. Hermes and OpenClaw have only observer or message-level equivalents.

  The skill's scripts should be callable unchanged from a command hook (JSON on stdin is optional, output on stdout). Then a per-harness snippet, e.g. `.codex/hooks.json`, `.gemini/settings.json` or `.cursor/hooks.json`, becomes an optional appendix and not part of the contract.
- **Treat all agent-run upkeep as best effort.** This is the ADR 0001 split. Where no hooks are wired, TTL expiry and index regeneration happen only when the agent follows the SKILL.md. The contract must therefore tolerate stale generated files and late expiry. Readers should rebuild or re-check rather than trust the index.
- **Unverified items to re-check before the spec leans on them:**
  - How Hermes executes bundled scripts.
  - Whether Hermes plugin hooks are reliable.
  - Whether OpenClaw's workspace maps to a code repository.
  - OpenCode's and Copilot's hook surfaces, which were not researched.
