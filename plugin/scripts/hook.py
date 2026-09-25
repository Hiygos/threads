"""threads: the plugin's adapter, run by guard.sh.

A thin adapter over threads_core (packaged beside this file), with two kinds of
entry point. `hook.py <HookEventName>` reads the hook input JSON on stdin,
resolves the scope from its `cwd`, and is silent when no scope exists; hook
JSON output goes to stdout. `hook.py init [user]` is the body of the
`/threads:init` skill: it creates a scope from the current directory and
prints plain text for the model to report, always exiting 0 (a non-zero exit
would make Claude Code fail the skill instead of showing the outcome).
No state under the plugin root.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import threads_core  # noqa: E402


def session_start(scope, payload):
    # The injection is THREADS.md's text for now, anomalies included.
    listing = threads_core.render_index(threads_core.regenerate(scope))
    return {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": listing}}


HOOKS = {"SessionStart": session_start}


def init(args):
    if args not in ([], ["user"]):
        sys.stdout.write("usage: /threads:init [user]\n")
        return 0
    _, text = threads_core.run_init(os.getcwd(), user=bool(args))
    sys.stdout.write(text)
    return 0


def main(argv):
    if argv and argv[0] == "init":
        return init(argv[1:])
    handler = HOOKS.get(argv[0] if argv else "")
    if handler is None:
        return 0
    payload = json.load(sys.stdin)
    scope = threads_core.resolve_scope(payload.get("cwd") or os.getcwd())
    if scope is None:
        return 0
    sys.stdout.write(json.dumps(handler(scope, payload)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
