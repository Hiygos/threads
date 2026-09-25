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
the current directory. No state under the plugin root, and nothing written
in a read-only scope (newer or unreadable contract): `ack` refuses there.
"""
import json
import os
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import threads_core  # noqa: E402


GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard.sh")

# Plugin-internal limits: Claude Code's cap on `additionalContext`, and the
# length a `leaning` is cut to in the injected listing.
CONTEXT_CAP = 10000
LEANING_MAX = 200

# The listing's heading, blank line and scope line: never cut.
LISTING_HEADER_LINES = 3

TRUNCATED = (
    "\n[Listing truncated to fit the session context: %d more lines. "
    "The full list is in THREADS.md at the scope root.]\n"
)

# The always-on rules, injected between the urgent sections and the listing.
RULES = """# Working with threads

A thread is an open question with a provisional position, kept in `.threads/`
across sessions until an outcome is declared. It is not a task (work with no
position to hold), not a decision (nothing left open) and not a fact (true
regardless of the work in progress): those belong elsewhere.

- Open a thread when a choice stays unresolved beyond the current exchange and
  there is a position worth keeping on it.
- The initial state records who decided it is a thread: `proposed` when you
  open it on your own initiative (tell the user in one line), `open` when the
  user asked for it. Before creating one, look for its id in `.threads/`,
  `.threads/history/` and `.threads/history/expired/`, and reopen an existing
  thread instead.
- When your position changes, update `leaning` and `touched` and append a
  dated note; never rewrite earlier notes. Re-read a thread file right before
  editing it. Write a thread's content in the language of the conversation.
- Never edit `THREADS.md` or an archive's `INDEX.md`: they are rebuilt from
  the thread files.
- A state change is an edit of `status` and `touched`. For anything beyond it
  (closing, deferring, rejecting, merging, reopening, fixing an anomaly), load
  the threads skill first.
- Phrase every open choice you put to the user as a question, so that it can
  be kept.
"""


def ack_command(scope, target):
    """The exact shell command line that acknowledges `target` in `scope`."""
    return "cd %s && sh %s ack %s" % (shlex.quote(scope.root), shlex.quote(GUARD), target)


def fit_listing(listing, room):
    """`listing` cut at a line boundary, with the marker line, to fit `room` characters.

    Its header (heading and scope line) is always kept.
    """
    if len(listing) <= room:
        return listing
    lines = listing.splitlines(True)
    keep = min(LISTING_HEADER_LINES, len(lines))
    for n in range(len(lines) - 1, keep - 1, -1):
        marker = TRUNCATED % (len(lines) - n)
        if n == keep or len("".join(lines[:n])) + len(marker) <= room:
            return "".join(lines[:n]) + marker
    return listing


def session_start(scope, payload):
    # Urgent sections first, then the rules, then the listing: the only part
    # cut to stay within the cap.
    result = threads_core.upkeep(scope)
    brief = threads_core.briefing(scope, result, lambda t: ack_command(scope, t), LEANING_MAX)
    fixed = len(brief.text(RULES, listing=""))
    context = brief.text(RULES, listing=fit_listing(brief.listing, CONTEXT_CAP - fixed))
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
    try:
        done = threads_core.ack(scope, args[0])
    except threads_core.ReadOnlyScope as refused:
        sys.stdout.write(str(refused))
        return 1
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
