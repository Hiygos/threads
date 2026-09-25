"""threads: the plugin's adapter, run by guard.sh.

A thin adapter over threads_core (packaged beside this file), with three kinds
of entry point. `hook.py <HookEventName>` reads the hook input JSON on stdin,
resolves the scope from its `cwd`, and is silent when no scope exists; hook
JSON output goes to stdout. SessionStart injects the briefing and records the
session's snapshot (and prunes orphan stashes); Stop rebuilds the generated
files, stashes the questions ending the agent's last reply, and blocks, once
per thread and session, on the threads this session left hanging;
UserPromptSubmit consumes the stash and injects the skipped-question check.
`hook.py init [user]` is the body of the
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
import re
import shlex
import shutil
import sys
import time

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

# Session markers: `.threads/.state/plugin/sessions/<session_id>.json`, holding
# the snapshot taken at the session's start and the ids the Stop gate already
# blocked on. Removed once untouched for this many days.
SESSIONS_DIR = os.path.join(".state", "plugin", "sessions")
MARKER_MAX_AGE_DAYS = 7
SESSION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")

# Skipped-question stash: `${CLAUDE_PLUGIN_DATA}/<session_id>`, JSON
# `{"candidates": [...]}`, the questions ending the agent's last reply. Each
# Stop overwrites it (or removes it when there are none); the next
# UserPromptSubmit reads and removes it. Plugin-internal limits: how many
# candidates are kept (the first ones), how long each may be (longer lines
# keep their end, where the question is), and the age at which SessionStart
# prunes an orphan stash.
DATA_ENV = "CLAUDE_PLUGIN_DATA"
MAX_CANDIDATES = 10
CANDIDATE_MAX_CHARS = 300
STASH_MAX_AGE_DAYS = 7
QUESTION_MARKS = ("?", "\uff1f", "\u061f")
FENCE_RE = re.compile(r" {0,3}(`{3,}|~{3,})")
HEADING_RE = re.compile(r" {0,3}#{1,6}(\s|$)")
SETEXT_RE = re.compile(r" {0,3}(=+|-+)\s*$")
TABLE_DELIMITER_RE = re.compile(r"\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
TEMP_RE = re.compile(r"\..+\.tmp-\d+")

# The skipped-question check: the questions, the scope root, today's date.
CHECK = """# Questions left from your last reply

Your last reply put these questions to the user:

%s
For each one the user's new message leaves unanswered and that is still an
unresolved choice, open a `proposed` thread now, without asking (`opened` and
`touched`: %s). First look for its id in `.threads/`, `.threads/history/` and
`.threads/history/expired/` of the scope at %s, and reopen the existing thread
instead if there is one. Then tell the user in one line at the end of your reply.

Open nothing for a question already covered by a thread, for an offer to do
some work (a task, not a thread), or for a clarifying question that events have
overtaken. Otherwise answer the user's message as usual.
"""

# The Stop gate's reason: scope root, the hanging threads, today's date.
STOP_REASON = """These threads changed during this session and are still `open` or `proposed`
without today's `touched`. Settle each one before ending the turn.
Scope at %s; paths are relative to it.

%s
For each one, pick the most likely outcome yourself instead of asking the user,
apply it, and tell the user in one line per thread (the user corrects you if it
is wrong):

- resolved: set `status: resolved`, add a dated note with the outcome, and move
  the file to `.threads/history/`;
- abandoned: set `status: abandoned`, add a dated note with the reason, and move
  the file to `.threads/history/`;
- deferred: set `status: deferred` and add a dated note with the reason it waits;
- still open: keep the status, update `leaning` to your current position, and
  add a dated note.

In every case set `touched: %s`. Re-read each file right before editing it,
and never overwrite a file that already exists in `.threads/history/`.
"""

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


def marker_path(scope, payload):
    """The session marker's path, or None without a usable session id."""
    session = payload.get("session_id")
    if not isinstance(session, str) or not SESSION_ID_RE.fullmatch(session):
        return None
    return os.path.join(scope.threads_dir, SESSIONS_DIR, session + ".json")


def new_marker(scope):
    return {"snapshot": threads_core.take_snapshot(scope), "blocked": []}


def prune_markers(scope, keep):
    """Remove session markers (and leftovers) untouched for MARKER_MAX_AGE_DAYS."""
    folder = os.path.join(scope.threads_dir, SESSIONS_DIR)
    limit = time.time() - MARKER_MAX_AGE_DAYS * 86400
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        path = os.path.join(folder, name)
        if path == keep:
            continue
        try:
            if os.lstat(path).st_mtime >= limit:
                continue
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                os.unlink(path)
        except OSError:
            pass  # Removed meanwhile by another session.


def stash_path(payload):
    """The session's stash path, or None without a plugin data folder or a usable session id."""
    folder = os.environ.get(DATA_ENV, "")
    session = payload.get("session_id")
    if not os.path.isabs(folder) or not isinstance(session, str) \
            or not SESSION_ID_RE.fullmatch(session):
        return None
    return os.path.join(folder, session)


def table_lines(lines):
    """Indexes of `lines` that belong to a table."""
    rows = {i for i, line in enumerate(lines) if line.lstrip().startswith("|")}
    for i in range(len(lines) - 1):
        if "|" in lines[i] and "|" in lines[i + 1] and TABLE_DELIMITER_RE.fullmatch(lines[i + 1]):
            j = i
            while j < len(lines) and lines[j].strip() and "|" in lines[j]:
                rows.add(j)
                j += 1
    return rows


def candidates(message):
    """The lines of `message` ending in a question mark, outside code, quotes, tables and headings.

    Capped at MAX_CANDIDATES lines of at most CANDIDATE_MAX_CHARS characters.
    """
    lines = message.splitlines() if isinstance(message, str) else []
    tables = table_lines(lines)
    found, fence = [], None
    for i, line in enumerate(lines):
        opening = FENCE_RE.match(line)
        if fence is not None:
            # A fence closes on the same character, at least as long, alone on its line.
            if opening and opening.group(1)[0] == fence[0] and len(opening.group(1)) >= len(fence) \
                    and not line[opening.end():].strip():
                fence = None
            continue
        if opening:
            fence = opening.group(1)
            continue
        text = line.strip()
        if (len(text) < 2 or not text.endswith(QUESTION_MARKS) or i in tables
                or text.startswith(">") or HEADING_RE.match(line)
                or (i + 1 < len(lines) and SETEXT_RE.fullmatch(lines[i + 1]))):
            continue
        if len(text) > CANDIDATE_MAX_CHARS:
            text = "\u2026" + text[-(CANDIDATE_MAX_CHARS - 1):]
        found.append(text)
        if len(found) == MAX_CANDIDATES:
            break
    return found


def stash(scope, payload):
    """Overwrite the session's stash with the last reply's candidates; none removes it."""
    path = stash_path(payload)
    if path is None:
        return
    found = [] if threads_core.contract_warning(scope) else \
        candidates(payload.get("last_assistant_message"))
    try:
        if found:
            threads_core.write_state(path, {"candidates": found})
        else:
            os.unlink(path)
    except OSError:
        pass  # Nothing to remove, or the data folder is unwritable.


def prune_stashes(keep):
    """Remove stashes (and write leftovers) untouched for STASH_MAX_AGE_DAYS."""
    folder = os.environ.get(DATA_ENV, "")
    if not os.path.isabs(folder):
        return
    limit = time.time() - STASH_MAX_AGE_DAYS * 86400
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        path = os.path.join(folder, name)
        if path == keep or not (SESSION_ID_RE.fullmatch(name) or TEMP_RE.fullmatch(name)):
            continue
        try:
            if os.path.isfile(path) and not os.path.islink(path) \
                    and os.lstat(path).st_mtime < limit:
                os.unlink(path)
        except OSError:
            pass  # Removed meanwhile by another session.


def session_start(scope, payload):
    # Urgent sections first, then the rules, then the listing: the only part
    # cut to stay within the cap.
    result = threads_core.upkeep(scope)
    marker = marker_path(scope, payload)
    if marker is not None and not threads_core.contract_warning(scope):
        # The same session goes on after resume/compact: keep its snapshot.
        kept = (payload.get("source") in ("resume", "compact")
                and threads_core.read_state(marker) is not None)
        if kept:
            os.utime(marker)
        else:
            threads_core.write_state(marker, new_marker(scope))
        prune_markers(scope, marker)
    prune_stashes(stash_path(payload))
    brief = threads_core.briefing(scope, result, lambda t: ack_command(scope, t), LEANING_MAX)
    fixed = len(brief.text(RULES, listing=""))
    context = brief.text(RULES, listing=fit_listing(brief.listing, CONTEXT_CAP - fixed))
    return {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": context}}


def stop_reason(scope, threads):
    return STOP_REASON % (scope.root, threads_core.render_hanging(threads),
                          threads_core.today().isoformat())


def stop(scope, payload):
    # Generated files are rebuilt and the stash overwritten on every Stop,
    # continuations included; a read-only scope gets no write.
    result = threads_core.upkeep(scope)
    stash(scope, payload)
    marker = marker_path(scope, payload)
    if marker is None or threads_core.contract_warning(scope):
        return None
    if payload.get("stop_hook_active"):
        return None
    state = threads_core.read_state(marker)
    if state is None or not isinstance(state.get("snapshot"), dict):
        # No snapshot for this session (the scope was created mid-session, or
        # the marker was pruned): start one now, nothing to compare yet.
        threads_core.write_state(marker, new_marker(scope))
        return None
    blocked = [b for b in state.get("blocked", []) if isinstance(b, str)]
    threads = [t for t in threads_core.hanging(scope, state["snapshot"], result)
               if t.id not in blocked]
    if not threads:
        return None
    state["blocked"] = sorted(set(blocked) | {t.id for t in threads})
    threads_core.write_state(marker, state)
    return {"decision": "block", "reason": stop_reason(scope, threads)}


def user_prompt_submit(scope, payload):
    # Consume the stash: it is shown at most once, and never in a read-only scope.
    path = stash_path(payload)
    if path is None:
        return None
    state = threads_core.read_state(path)
    try:
        os.unlink(path)
    except OSError:
        pass  # No stash: the last turn ended without questions, or was interrupted.
    found = state.get("candidates") if state is not None else None
    if not isinstance(found, list) or threads_core.contract_warning(scope):
        return None
    found = [c for c in found if isinstance(c, str) and c][:MAX_CANDIDATES]
    if not found:
        return None
    listed = "".join("- %s\n" % c for c in found)
    context = CHECK % (listed, threads_core.today().isoformat(), scope.root)
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                   "additionalContext": context}}


HOOKS = {"SessionStart": session_start, "Stop": stop, "UserPromptSubmit": user_prompt_submit}


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
    output = handler(scope, payload)
    if output is not None:
        sys.stdout.write(json.dumps(output) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
