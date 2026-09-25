---
name: init
description: Create a threads scope. With no argument, the project scope (at the git root inside a repository, at the current directory otherwise); with `user`, the user scope shared by projects that have none.
argument-hint: "[user]"
disable-model-invocation: true
allowed-tools: Bash(sh:*)
---

Scope creation already ran; its output:

!`sh "${CLAUDE_PLUGIN_ROOT}/scripts/guard.sh" init $ARGUMENTS`

Report this outcome to the user in plain words, keeping every path and
passing on any note about approval prompts. Do not run anything else and do
not create, edit or move any file: if a scope already covers this directory
and the user wants a nested one, they can ask for it with an explicit path.
