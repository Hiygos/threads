"""threads: the plugin's adapter, run by guard.sh.

A thin adapter over threads_core (packaged beside this file), with three kinds
of entry point. `hook.py <HookEventName>` reads the hook input JSON on stdin,
resolves the scope from its `cwd`, and is silent when no scope exists; hook
JSON output goes to stdout. `hook.py init [user]` is the body of the
`/threads:init` skill: it creates a scope from the current directory and
prints plain text for the model to report, always exiting 0 (a non-zero exit
would make Claude Code fail the skill instead of showing the outcome).
`hook.py ack <id>|all` is the command line SessionStart gives the agent for
each retirement notice; it acknowledges notices in the scope resolved from
the current directory. No state under the plugin root.
"""
import json
import os
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import threads_core  # noqa: E402


GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard.sh")

RETIREMENTS_HEADER = (
    "# Retired proposals\n"
    "\n"
    "These proposed threads went unconfirmed for more than 3 days and were moved\n"
    "to `.threads/history/expired/`. Tell the user about each one (moving the file\n"
    "back to `.threads/` restores it); only after telling them, acknowledge it by\n"
    "running the command shown, as is.\n"
    "\n"
)


def ack_command(scope, target):
    """The exact shell command line that acknowledges `target` in `scope`."""
    return "cd %s && sh %s ack %s" % (shlex.quote(scope.root), shlex.quote(GUARD), target)


def retirements(scope, result):
    """The retirement notices section of the briefing; empty with none queued."""
    ids = threads_core.pending_notices(scope)
    if not ids:
        return ""
    questions = {t.id: t.question for t in result.expired}
    out = [RETIREMENTS_HEADER]
    for thread_id in ids:
        question = questions.get(thread_id)
        out.append("- `%s`%s\n  ack: `%s`\n" % (
            thread_id, " — %s" % question if question else "", ack_command(scope, thread_id)))
    if len(ids) > 1:
        out.append("\nAll at once: `%s`\n" % ack_command(scope, "all"))
    return "".join(out) + "\n"


def session_start(scope, payload):
    # Retirement notices first, then THREADS.md's text (anomalies, listing).
    result = threads_core.upkeep(scope)
    context = retirements(scope, result) + threads_core.render_index(result)
    return {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": context}}


HOOKS = {"SessionStart": session_start}


def init(args):
    if args not in ([], ["user"]):
        sys.stdout.write("usage: /threads:init [user]\n")
        return 0
    _, text = threads_core.run_init(os.getcwd(), user=bool(args))
    sys.stdout.write(text)
    return 0


def ack(args):
    if len(args) != 1 or not (args[0] == "all" or threads_core.valid_id(args[0])):
        sys.stdout.write("usage: guard.sh ack <id>|all\n")
        return 2
    scope = threads_core.resolve_scope(os.getcwd())
    if scope is None:
        return 0
    done = threads_core.ack(scope, args[0])
    sys.stdout.write(threads_core.ack_text(done, args[0]))
    return 0


def main(argv):
    if argv and argv[0] == "init":
        return init(argv[1:])
    if argv and argv[0] == "ack":
        return ack(argv[1:])
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
