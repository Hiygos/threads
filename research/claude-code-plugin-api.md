# Claude Code plugin API: what hooks, skills and commands can do from inside a plugin

Research for [#2](https://github.com/Hiygos/threads/issues/2). Sources are the official
Claude Code docs as published at research time (September 2026, docs reference versions up to
v2.1.25x). **Verified** = stated in the cited doc. **Inference** = our reading, not stated.

Primary sources:

- Hooks reference — <https://code.claude.com/docs/en/hooks>
- Plugins reference — <https://code.claude.com/docs/en/plugins-reference>
- Plugins guide — <https://code.claude.com/docs/en/plugins>
- Plugin marketplaces — <https://code.claude.com/docs/en/plugin-marketplaces>
- Skills — <https://code.claude.com/docs/en/skills>
- Sessions (transcript storage) — <https://code.claude.com/docs/en/sessions>
- Setup (system requirements) — <https://code.claude.com/docs/en/setup>

## 1. How hooks are declared in a plugin; `${CLAUDE_PLUGIN_ROOT}` and project dir

Verified:

- Plugin hooks live in `hooks/hooks.json` at the plugin root, or inline under `hooks` in
  `plugin.json` (a manifest `hooks` path can also point elsewhere). Same shape as settings
  hooks: `{"hooks": {"<Event>": [{"matcher": ..., "hooks": [{"type": "command", ...}]}]}}`.
  They respond to the same lifecycle events as user hooks.
  [plugins-reference § Hooks](https://code.claude.com/docs/en/plugins-reference#hooks)
- Three path variables: `${CLAUDE_PLUGIN_ROOT}` (plugin install dir), `${CLAUDE_PLUGIN_DATA}`
  (persistent per-plugin dir that survives updates, created on first reference),
  `${CLAUDE_PROJECT_DIR}` (project root). In hook commands the placeholder is substituted
  anywhere it appears, **and** all three are exported as env vars to the hook process. They are
  **not** set for commands Claude runs through the Bash tool; in skill content, write the
  placeholder and Claude Code substitutes it inline at load.
  [plugins-reference § Environment variables](https://code.claude.com/docs/en/plugins-reference#environment-variables)
- `${CLAUDE_PROJECT_DIR}` is the root **where the session started** and stays put if Claude
  enters a worktree or `cd`s; the hook input's `cwd` field follows Claude instead.
  [hooks § Reference scripts by path](https://code.claude.com/docs/en/hooks#reference-scripts-by-path)
- Marketplace plugins are **copied** into `~/.claude/plugins/cache`, one directory per version,
  so `${CLAUDE_PLUGIN_ROOT}` changes on every update; never write state there. A plugin loaded
  in place from a local-directory marketplace (or `--plugin-dir`) points at the source dir.
  Files outside the plugin dir are not copied. Mid-session updates keep the old path until
  `/reload-plugins`.
  [plugins-reference § Plugin caching](https://code.claude.com/docs/en/plugins-reference#plugin-caching-and-file-resolution)
- Two command forms: **exec form** (`command` + `args`, no shell, placeholders substituted per
  argument — recommended when paths are involved) and **shell form** (no `args`; `shell`
  defaults to `bash`, or `powershell` on Windows without Git Bash; quote placeholders).
  [hooks § Exec form and shell form](https://code.claude.com/docs/en/hooks#exec-form-and-shell-form)
- All matching hooks for an event run **in parallel**; a plugin's copy of a handler is not
  deduplicated against the same handler in settings. `disableAllHooks` turns them all off.
  [hooks § Common fields](https://code.claude.com/docs/en/hooks#common-fields),
  [hooks § Disable or remove hooks](https://code.claude.com/docs/en/hooks#disable-or-remove-hooks)
- Default timeouts: 600 s for command hooks, but **30 s on UserPromptSubmit**; a timed-out
  UserPromptSubmit hook's output (including `additionalContext`) is discarded and the prompt
  goes through without it. [hooks § UserPromptSubmit](https://code.claude.com/docs/en/hooks#userpromptsubmit)

## 2. `additionalContext` on SessionStart and UserPromptSubmit: size and shape

Verified:

- Shape: `{"hookSpecificOutput": {"hookEventName": "<Event>", "additionalContext": "<string>"}}`
  on stdout, exit 0, stdout containing **only** the JSON object. Plain-text stdout is also added
  as context on exactly SessionStart, UserPromptSubmit, UserPromptExpansion and PostModelSwitch.
  Since v2.1.248, stdout that looks like JSON but fails to parse is **not** added as text.
  [hooks § Exit code output](https://code.claude.com/docs/en/hooks#exit-code-output),
  [hooks § Add context for Claude](https://code.claude.com/docs/en/hooks#add-context-for-claude)
- **Cap: 10,000 characters** per string (each JSON field measured separately; plain stdout
  measured whole; each hook measured on its own). Over the cap, the text is saved to a file in
  the session directory and Claude gets the path plus a **2,000-character preview**; Claude is
  not asked to read the file. No setting raises the cap.
  [hooks § JSON output](https://code.claude.com/docs/en/hooks#json-output)
- Delivery: wrapped in a system reminder (starting with the hook's name), not shown as a chat
  message. Several hooks' values for one event are all delivered.
  SessionStart context lands before the first prompt; UserPromptSubmit context lands alongside
  the submitted prompt. [hooks § Add context for Claude](https://code.claude.com/docs/en/hooks#add-context-for-claude)
- Injected text is saved in the transcript. On `--resume`/`--continue`, past UserPromptSubmit
  context is **replayed, not recomputed**; SessionStart **re-runs** with `source: "resume"`.
  SessionStart `source` values: `startup`, `resume`, `clear`, `compact`, `fork`.
  [hooks § SessionStart](https://code.claude.com/docs/en/hooks#sessionstart)
- Extra SessionStart outputs: `initialUserMessage` (headless only), `sessionTitle`,
  `watchPaths` (absolute paths that then fire `FileChanged`), `reloadSkills`. SessionStart
  cannot block. UserPromptSubmit can `decision: "block"` (erases the prompt; `reason` shown to
  the user, not to Claude) but **cannot rewrite** the prompt.
  [hooks § SessionStart decision control](https://code.claude.com/docs/en/hooks#sessionstart-decision-control),
  [hooks § UserPromptSubmit decision control](https://code.claude.com/docs/en/hooks#userpromptsubmit-decision-control)
- Interactive SessionStart hooks run in the background, but Claude's first response waits for
  them. [hooks § SessionStart](https://code.claude.com/docs/en/hooks#sessionstart)

## 3. Stop hook blocking semantics

Verified ([hooks § Stop](https://code.claude.com/docs/en/hooks#stop)):

- **When it fires:** every time the main agent finishes responding, i.e. at the end of each
  turn. Not on user interrupt. API errors fire `StopFailure` instead (output ignored).
  Subagents fire `SubagentStop`, not `Stop`.
- **Blocking:** `{"decision": "block", "reason": "..."}` prevents stopping; `reason` is
  required and is delivered to Claude as why it must continue. Exit 2 with stderr is equivalent.
- **Softer alternative:** `hookSpecificOutput.additionalContext` on Stop also continues the
  conversation, but the transcript labels it "Stop hook feedback" rather than a hook error.
- **Loop protection:** input field `stop_hook_active` is `true` when Claude is already
  continuing because of a Stop hook. Claude Code **overrides the hook and ends the turn after
  8 consecutive blocks**; the cap applies to the `additionalContext` path too.
- Input also carries `last_assistant_message` (the final text, so no transcript parsing is
  needed), `background_tasks` and `session_crons`.

## 4. How a plugin ships skills and slash commands; namespacing

Verified:

- Skills: `skills/<name>/SKILL.md` at the plugin root (supporting files alongside). Legacy
  commands: flat `commands/*.md`. **Custom commands have been merged into skills**: both create
  `/name`; `skills/` is recommended for new work. A plugin with no `skills/` dir may ship a
  single root `SKILL.md`.
  [plugins-reference § Skills](https://code.claude.com/docs/en/plugins-reference#skills),
  [skills](https://code.claude.com/docs/en/skills)
- **Always namespaced** as `/<plugin-name>:<skill-name>` (plugin `name` from `plugin.json`,
  or the marketplace entry name if different). A plugin skill never collides with a same-named
  user/project skill; both load.
  [plugins guide](https://code.claude.com/docs/en/plugins),
  [skills § Where skills live](https://code.claude.com/docs/en/skills)
- `disable-model-invocation: true` makes a skill user-invoked only (the "slash command"
  behaviour). The skill listing truncates `description` + `when_to_use` at **1,536 characters**.
  [skills § Frontmatter reference](https://code.claude.com/docs/en/skills)
- Manifest paths: `skills` **adds** to the default `skills/` scan; `commands` **replaces** the
  default `commands/` scan. Exception: for a marketplace entry whose `source` is the
  marketplace root (`"./"`, as in this repo), listing specific `skills` subdirectories
  **replaces** the default scan.
  [plugins-reference § Path behavior rules](https://code.claude.com/docs/en/plugins-reference#path-behavior-rules)
- A skill's frontmatter may itself declare hooks (with `once: true` honoured only there).
  [hooks § Hooks in skills and agents](https://code.claude.com/docs/en/hooks#hooks-in-skills-and-agents)

## 5. Can `python3` be assumed?

Verified:

- Claude Code's system requirements list OS, RAM, network and shell (Bash, Zsh, PowerShell or
  CMD) — **no Python, no Node**. Claude Code ships as a native binary; even the npm package
  does not use Node at runtime. Windows without Git for Windows has no Bash at all.
  [setup § System requirements](https://code.claude.com/docs/en/setup#system-requirements)
- The docs only auto-provision **Node.js** package deps for marketplace-installed plugins
  (when a `package.json` + lockfile are present). Python dependencies must be installed by a
  hook into `${CLAUDE_PLUGIN_DATA}`. They say nothing about a Python interpreter being present.
  [plugins-reference § Node.js package dependencies](https://code.claude.com/docs/en/plugins-reference#node-js-package-dependencies)
- On Windows, exec form needs a real executable; the doc recommends `node <script>` as a
  cross-platform pattern.
  [hooks § Exec form and shell form](https://code.claude.com/docs/en/hooks#exec-form-and-shell-form)

Inference: `python3` is **not guaranteed**. It is present on stock macOS only via the Xcode
Command Line Tools stub, on most Linux distros but not minimal ones (e.g. Alpine), and usually
not on Windows (where the name is `python`/`py`). Node is not guaranteed either. A POSIX shell
is guaranteed everywhere except native Windows without Git Bash.

## 6. Transcript JSONL format stability

Verified:

- Transcripts are JSONL at `~/.claude/projects/<project>/<session-id>.jsonl`; hooks receive
  the path as `transcript_path`. The docs state: *"The entry format is internal to Claude Code
  and changes between versions"*, so direct parsers can break on any release; supported
  alternatives are `/export`, `claude -p --output-format json|stream-json`, and hook inputs.
  [sessions § Where transcripts are stored](https://code.claude.com/docs/en/sessions#where-transcripts-are-stored)
- The transcript is written **asynchronously** and may not yet contain the current turn when a
  hook fires. For the last assistant text, use `last_assistant_message` on Stop.
  [hooks § Common input fields](https://code.claude.com/docs/en/hooks#common-input-fields)
- Transcripts are retained 30 days by default (`cleanupPeriodDays`).
  [sessions](https://code.claude.com/docs/en/sessions)

## Implications for the spec

- Declare the three hooks in `hooks/hooks.json`, exec form, script paths via
  `${CLAUDE_PLUGIN_ROOT}`; locate `.threads/` from the input `cwd` / `${CLAUDE_PROJECT_DIR}`,
  never from the plugin dir. Decide explicitly which of the two defines "project scope" when a
  session enters a worktree (they diverge).
- Keep every injected block under **10,000 chars** (target well under, since multiple hooks
  and plugins share the context); design the SessionStart digest to degrade to a summary plus
  file pointers rather than overflow into the 2,000-char preview.
- UserPromptSubmit must finish well within **30 s**, and its output is replayed stale on resume:
  keep it cheap and prefer SessionStart for state that must be fresh after resume.
- Stop enforcement: check `stop_hook_active` and block at most once per turn (the 8-block cap
  is a backstop, not a design); prefer Stop `additionalContext` over `decision: "block"` for
  routine reminders so they don't render as hook errors.
- Use `last_assistant_message` and the `prompt` field instead of reading the transcript;
  treat any transcript parsing as best-effort and fail open, since the format is explicitly
  unstable.
- Ship commands as `skills/<name>/SKILL.md` with `disable-model-invocation: true`; users will
  type `/threads:<name>`. Because this repo's marketplace entry uses `source: "./"`, the
  harness-agnostic skill must not sit in the plugin's default `skills/` scan unless the plugin
  should load it — list the plugin's skill directories explicitly in `plugin.json`.
- Runtime: `python3` cannot be assumed. Options to decide in the spec: (a) require Python 3
  and fail open with a clear one-time message when missing, (b) POSIX `sh` scripts (loses
  native Windows without Git Bash), or (c) Node (not guaranteed either). Keep hooks stdlib-only
  regardless, since only Node deps are auto-installed.
- Never write state under `${CLAUDE_PLUGIN_ROOT}` (replaced on update); anything plugin-owned
  and persistent goes in `${CLAUDE_PLUGIN_DATA}`, thread data in the project/user scope.
