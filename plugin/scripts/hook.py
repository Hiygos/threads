"""threads: the plugin's hook adapter, run by guard.sh as `hook.py <HookEventName>`.

A thin adapter over threads_core (packaged beside this file). It reads the hook
input JSON on stdin, resolves the scope from its `cwd`, and is silent when no
scope exists. Hook JSON output goes to stdout. No state under the plugin root.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import threads_core  # noqa: E402


def session_start(scope, payload):
    threads_core.regenerate(scope)
    listing = threads_core.render_index(threads_core.scan_active(scope))
    return {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": listing}}


HOOKS = {"SessionStart": session_start}


def main(argv):
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
