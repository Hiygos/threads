"""Shared core of threads: one source, packaged into the plugin and the skill.

Python >= 3.9, standard library only (ADR 0003). The adapters (the plugin's
hooks, the skill's `threads` script) stay thin and call the public functions
below; everything that must be byte-identical across implementations lives
here. Do not edit a packaged copy: edit this file and copy it over.
"""
import os
import re
import subprocess
from datetime import date

CONTRACT_VERSION = 1

THREADS_DIR = ".threads"
INDEX_FILE = "THREADS.md"
HISTORY_DIR = "history"  # inside `.threads/`
EXPIRED_DIR = "expired"  # inside `.threads/history/`
ARCHIVE_INDEX_FILE = "INDEX.md"
CONTRACT_FILE = ".contract"  # inside `.threads/`
NOTICES_DIR = os.path.join(".state", "notices")  # inside `.threads/`
USER_ROOT_ENV = "THREADS_USER_ROOT"
DEFAULT_USER_ROOT = ".agents"  # relative to the home directory

ACTIVE_STATES = ("proposed", "open", "deferred")
TERMINAL_STATES = ("resolved", "abandoned", "merged")
REQUIRED_FIELDS = ("id", "status", "opened", "touched", "question")

# A `proposed` thread retires when its age from `opened` exceeds this many
# calendar days (CONTRACT.md § Retirement). Fixed, not configurable.
PROPOSED_TTL_DAYS = 3

# Stale thresholds (CONTRACT.md § Briefing): idle days from `touched`,
# strictly greater. Fixed, not configurable.
STALE_DAYS = {"open": 14, "deferred": 45}

# A merge review is proposed when more active threads than this exist.
MERGE_REVIEW_OVER = 25

# The dated note retirement appends, under `## <date>` (normative).
RETIREMENT_NOTE = "Retired: unconfirmed for more than 3 days.\n"

INDEX_HEADER = (
    "# THREADS\n"
    "\n"
    "> Generated from `.threads/`. Do not edit by hand: edit the thread files,\n"
    "> and this index is rebuilt on the next upkeep.\n"
)

HISTORY_INDEX_HEADER = (
    "# History\n"
    "\n"
    "> Generated from `.threads/history/`. Do not edit by hand: edit the thread files,\n"
    "> and this index is rebuilt on the next upkeep.\n"
)

EXPIRED_INDEX_HEADER = (
    "# Expired\n"
    "\n"
    "> Generated from `.threads/history/expired/`. Do not edit by hand: edit the thread files,\n"
    "> and this index is rebuilt on the next upkeep.\n"
)

USER_SCOPE_NOTICE = (
    "The user scope is outside the project, so some harnesses ask for approval\n"
    "before writing to it; allow %s once in the harness's settings to avoid it.\n"
)

# Group order and labels of THREADS.md are normative (CONTRACT.md).
INDEX_GROUPS = (
    ("open", "Open"),
    ("deferred", "Deferred"),
    ("proposed", "Proposed (awaiting confirmation)"),
)

# Group order and labels of `.threads/history/INDEX.md` are normative too.
HISTORY_GROUPS = (
    ("resolved", "Resolved"),
    ("abandoned", "Abandoned"),
    ("merged", "Merged"),
)

ANOMALIES_HEADER = (
    "\n"
    "## Anomalies\n"
    "\n"
    "> These files are not read as threads and are left untouched: fix them by hand.\n"
    "\n"
)

# Fixed text of the briefing's data sections (normative, CONTRACT.md § Briefing).
BRIEFING_RETIREMENTS_HEADER = (
    "# Retired proposals\n"
    "\n"
    "These proposed threads went unconfirmed for more than 3 days and were moved\n"
    "to `.threads/history/expired/`. Tell the user about each one (moving the file\n"
    "back to `.threads/` restores it); only after telling them, acknowledge it by\n"
    "running the command shown, as is.\n"
    "\n"
)

BRIEFING_ANOMALIES_HEADER = (
    "# Anomalies\n"
    "\n"
    "These files are not read as threads and are never fixed automatically:\n"
    "tell the user, who fixes them by hand.\n"
    "\n"
)

BRIEFING_MERGE_REVIEW = (
    "# Merge review\n"
    "\n"
    "%d threads are active, more than 25. Look for threads that overlap and\n"
    "propose merges to the user; merge only what the user approves.\n"
)

BRIEFING_STALE_HEADER = (
    "# Stale threads\n"
    "\n"
    "These threads have not been touched for a long time (`open` for more than\n"
    "14 days, `deferred` for more than 45). Ask the user whether each one still\n"
    "matters, then update or close it.\n"
    "\n"
)

BRIEFING_LISTING_HEADER = (
    "# Active threads\n"
    "\n"
    "%s scope at %s; paths are relative to it.\n"
)

_KEY_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_ID_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


class Scope:
    """A resolved scope: the folder holding `.threads/` and `THREADS.md`.

    `kind` is "project" or "user".
    """

    def __init__(self, root, kind="project"):
        self.root = os.path.abspath(root)
        self.kind = kind

    @property
    def threads_dir(self):
        return os.path.join(self.root, THREADS_DIR)

    @property
    def index_path(self):
        return os.path.join(self.root, INDEX_FILE)

    @property
    def history_dir(self):
        return os.path.join(self.threads_dir, HISTORY_DIR)

    @property
    def expired_dir(self):
        return os.path.join(self.history_dir, EXPIRED_DIR)

    @property
    def contract_path(self):
        return os.path.join(self.threads_dir, CONTRACT_FILE)

    @property
    def notices_dir(self):
        return os.path.join(self.threads_dir, NOTICES_DIR)


class ScopeExists(Exception):
    """Scope creation refused: `scope` already covers the start directory."""

    def __init__(self, scope):
        Exception.__init__(self, scope.root)
        self.scope = scope


class Thread:
    """A thread file with no anomaly: its fields (unknown ones kept) and body."""

    def __init__(self, path, fields, body=""):
        self.path = path
        self.fields = fields
        self.body = body

    @property
    def id(self):
        return self.fields["id"]

    @property
    def status(self):
        return self.fields["status"]

    @property
    def question(self):
        return self.fields["question"]

    @property
    def leaning(self):
        return self.fields.get("leaning", "")


class Anomaly:
    """A file in a threads folder the contract cannot read as a thread.

    `rel` is its path relative to the scope root (`/` separated); `reason`
    is the normative English text shown in THREADS.md.
    """

    def __init__(self, path, rel, reason):
        self.path = path
        self.rel = rel
        self.reason = reason


class ScopeScan:
    """A scope read whole: threads per folder, sorted by id, and anomalies by path."""

    def __init__(self, active, closed, expired, anomalies):
        self.active = active
        self.closed = closed
        self.expired = expired
        self.anomalies = anomalies


def today():
    """The local date, or THREADS_TODAY (test-only clock, outside the contract)."""
    forced = os.environ.get("THREADS_TODAY")
    if forced:
        return date.fromisoformat(forced)
    return date.today()


def _has_threads(folder):
    return os.path.isdir(os.path.join(folder, THREADS_DIR))


def _project_candidates(start, home):
    """Folders checked for `.threads/`, nearest first, and the git root or None.

    Up to the git root (checked, and the last one); outside git, up to just
    below `home` (never checked); outside both, the start directory only.
    """
    folders = []
    folder = start
    while True:
        folders.append(folder)
        if os.path.exists(os.path.join(folder, ".git")):
            return folders, folder
        parent = os.path.dirname(folder)
        if parent == folder:
            break
        folder = parent
    # Outside git: below home, every folder up to just below it; otherwise
    # the start directory only. Home itself is never checked.
    prefix = home.rstrip(os.sep) + os.sep if home else None
    if prefix and start.startswith(prefix):
        return [f for f in folders if f.startswith(prefix)], None
    return ([] if start == home else [start]), None


def _main_worktree_root(git_root, env):
    """The main worktree's root when `git_root` is a linked worktree, else None.

    Asks git for the common dir; any failure (git absent, not a repo, bare
    main repository) means no main worktree to continue to.
    """
    if not os.path.isfile(os.path.join(git_root, ".git")):
        return None  # A `.git` folder: this is a main worktree.
    env = {k: v for k, v in env.items()
           if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")}
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--git-dir", "--git-common-dir"],
            cwd=git_root, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = proc.stdout.decode("utf-8", "replace").splitlines()
    if proc.returncode != 0 or len(lines) != 2:
        return None
    git_dir, common_dir = (os.path.realpath(os.path.join(git_root, p)) for p in lines)
    if git_dir == common_dir or os.path.basename(common_dir) != ".git":
        return None
    return os.path.dirname(common_dir)


def _user_root(env):
    """The user scope's root: `$THREADS_USER_ROOT` when absolute, else `~/.agents`."""
    moved = env.get(USER_ROOT_ENV, "")
    if moved and os.path.isabs(moved):
        return moved
    home = env.get("HOME") or os.path.expanduser("~")
    return os.path.join(home, DEFAULT_USER_ROOT)


def _context(start, env):
    """The environment, the real start directory and the real home (or None)."""
    env = os.environ if env is None else env
    home = env.get("HOME") or os.path.expanduser("~")
    home = os.path.realpath(home) if os.path.isabs(home) else None
    return env, os.path.realpath(start), home


def _project_scope(start, home, env):
    """The project scope covering `start` (or None), and the git root (or None)."""
    folders, git_root = _project_candidates(start, home)
    for folder in folders:
        if _has_threads(folder):
            return Scope(folder), git_root
    if git_root is not None:
        main = _main_worktree_root(git_root, env)
        if main is not None and _has_threads(main):
            return Scope(main), git_root
    return None, git_root


def resolve_scope(start, env=None):
    """The scope for a session started in `start`, or None when inactive.

    The nearest project scope (walk-up, then the main worktree's root for a
    linked worktree), else the user scope, else None. Never both. `env`
    (default `os.environ`) supplies HOME and THREADS_USER_ROOT.
    """
    env, start, home = _context(start, env)
    scope, _ = _project_scope(start, home, env)
    if scope is not None:
        return scope
    root = _user_root(env)
    if _has_threads(root):
        return Scope(root, kind="user")
    return None


def create_scope(start, user=False, env=None):
    """Create a scope's skeleton and return the new Scope.

    The project scope goes at the git root inside a repository, at `start`
    otherwise; with `user`, the user scope goes under the user root. Raises
    ScopeExists, writing nothing, when a project scope already covers `start`
    (or, with `user`, when the user scope exists).
    """
    env, start, home = _context(start, env)
    if user:
        scope = Scope(_user_root(env), kind="user")
        if _has_threads(scope.root):
            raise ScopeExists(scope)
    else:
        found, git_root = _project_scope(start, home, env)
        if found is not None:
            raise ScopeExists(found)
        scope = Scope(git_root or start)
    os.makedirs(scope.root, exist_ok=True)
    try:
        os.mkdir(scope.threads_dir)
    except FileExistsError:
        raise ScopeExists(scope)  # Created meanwhile by someone else.
    os.makedirs(scope.expired_dir, exist_ok=True)
    write_atomic(scope.contract_path, render_contract())
    write_atomic(os.path.join(scope.history_dir, ARCHIVE_INDEX_FILE), render_history_index())
    write_atomic(os.path.join(scope.expired_dir, ARCHIVE_INDEX_FILE), render_expired_index())
    _write_generated(scope, scan(scope))
    return scope


def run_init(start, user=False, env=None):
    """Create a scope for an adapter: (created, text to show the user)."""
    try:
        scope = create_scope(start, user, env)
    except ScopeExists as refused:
        found = refused.scope
        if found.kind == "user":
            return False, "Not created: the user scope already exists at %s\n" % found.root
        return False, "Not created: this directory is already covered by the scope at %s\n" % found.root
    text = "Created the %s scope at %s\n" % (scope.kind, scope.root)
    if scope.kind == "user":
        text += USER_SCOPE_NOTICE % scope.root
    return True, text


def split_thread(text):
    """Split a thread file's text into (fields, body); None when not the subset.

    The strict flat frontmatter subset, not YAML: a leading BOM is dropped,
    then a line `---`, one `key: value` per non-blank line (paired quotes
    stripped, nothing else interpreted), and a closing `---`. The body is
    everything after the closing line. Unknown fields are kept, in order.
    """
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.split("\n")
    if lines[0].rstrip("\r") != "---":
        return None
    fields = {}
    for n, raw in enumerate(lines[1:], 1):
        line = raw.rstrip("\r")
        if line == "---":
            return fields, "\n".join(lines[n + 1:])
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        key = key.strip()
        if not sep or not _KEY_RE.match(key) or key in fields:
            return None
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[key] = value
    return None


def parse_frontmatter(text):
    """The fields of the frontmatter subset (see split_thread), or None."""
    parsed = split_thread(text)
    return None if parsed is None else parsed[0]


def valid_id(value):
    """True when `value` is a kebab-case id: `[a-z0-9]+(-[a-z0-9]+)*`."""
    return _ID_RE.fullmatch(value) is not None


def _thread_files(folder, archive):
    """The thread files of one folder: regular `*.md` files not starting with `.`.

    An archive's own INDEX.md is excluded. Everything else (dot entries such
    as `.contract` and `.state/`, other files, subfolders) is not a thread
    file and never an anomaly.
    """
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return [n for n in sorted(names)
            if n.endswith(".md") and not n.startswith(".")
            and not (archive and n == ARCHIVE_INDEX_FILE)
            and os.path.isfile(os.path.join(folder, n))]


def _check(path, rel_folder, folder_states, expired_folder):
    """(Thread, None) for a readable file, or (None, reason)."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None, "cannot be read"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, "not UTF-8 text"
    parsed = split_thread(text)
    if parsed is None:
        return None, "frontmatter missing or not the flat subset"
    fields, body = parsed
    missing = [k for k in REQUIRED_FIELDS if not fields.get(k)]
    # Conditionally required: `merged_into` when merged, `expired` in the expired archive.
    status = fields.get("status")
    if status == "merged" and not fields.get("merged_into"):
        missing.append("merged_into")
    if expired_folder and status == "proposed" and not fields.get("expired"):
        missing.append("expired")
    if missing:
        return None, "missing required field%s %s" % (
            "s" if len(missing) > 1 else "", ", ".join("`%s`" % k for k in missing))
    stem = os.path.basename(path)[:-len(".md")]
    if not valid_id(fields["id"]):
        return None, "invalid id `%s`" % fields["id"]
    if fields["id"] != stem:
        return None, "id `%s` does not match the file name" % fields["id"]
    if fields["status"] not in folder_states:
        return None, "status `%s` does not belong in `%s`" % (fields["status"], rel_folder)
    return Thread(path, fields, body), None


def scan(scope):
    """Read the three folders of `scope` into threads and anomalies.

    `.threads/` holds the active states, `history/` the terminal ones and
    `history/expired/` retired proposals (`proposed` with `expired`). A file
    that breaks a rule is an anomaly: reported, never moved or rewritten.
    """
    folders = (
        (scope.threads_dir, ACTIVE_STATES, False),
        (scope.history_dir, TERMINAL_STATES, False),
        (scope.expired_dir, ("proposed",), True),
    )
    found = []  # (folder index, path, rel, Thread or None, reason)
    by_stem = {}
    for index, (folder, states, expired_folder) in enumerate(folders):
        rel_folder = os.path.relpath(folder, scope.root).replace(os.sep, "/") + "/"
        for name in _thread_files(folder, archive=index > 0):
            path = os.path.join(folder, name)
            rel = rel_folder + name
            thread, reason = _check(path, rel_folder, states, expired_folder)
            found.append((index, path, rel, thread, reason))
            by_stem.setdefault(name, []).append(rel)
    groups = ([], [], [])
    anomalies = []
    now = today()
    for index, path, rel, thread, reason in found:
        others = [r for r in by_stem[os.path.basename(path)] if r != rel]
        if thread is not None and others:
            thread, reason = None, "id `%s` also used by %s" % (
                thread.id, ", ".join("`%s`" % r for r in others))
        if thread is not None and index == 0 and is_expired(thread, now):
            # A destination taken by something that is not a thread file.
            dest = os.path.join(scope.expired_dir, os.path.basename(path))
            if os.path.lexists(dest):
                thread, reason = None, "cannot be retired: `%s` already exists" % (
                    os.path.relpath(dest, scope.root).replace(os.sep, "/"))
        if thread is None:
            anomalies.append(Anomaly(path, rel, reason))
        else:
            groups[index].append(thread)
    for threads in groups:
        threads.sort(key=lambda t: t.id)
    anomalies.sort(key=lambda a: a.rel)
    return ScopeScan(groups[0], groups[1], groups[2], anomalies)


def _entry(thread, link):
    return "- **[%s](%s)** — %s\n" % (thread.id, link, thread.question)


def render_anomalies(anomalies):
    """The normative anomalies section of THREADS.md; empty with no anomaly."""
    if not anomalies:
        return ""
    return ANOMALIES_HEADER + "".join(
        "- `%s` — %s\n" % (a.rel, a.reason) for a in anomalies)


def _active_groups(threads, leaning_max=None):
    """The state groups of THREADS.md, or its "no active threads" line.

    `leaning_max` (adapter-internal, never for generated files) shortens a
    longer `leaning` to that many characters, ending in `…`.
    """
    out = []
    for state, label in INDEX_GROUPS:
        rows = [t for t in threads if t.status == state]
        if not rows:
            continue
        out.append("\n## %s\n\n" % label)
        for t in rows:
            out.append(_entry(t, "%s/%s.md" % (THREADS_DIR, t.id)))
            leaning = t.leaning
            if leaning_max is not None and len(leaning) > leaning_max:
                leaning = leaning[:max(leaning_max - 1, 0)] + "…"
            if leaning:
                out.append("  - leaning: %s\n" % leaning)
    if not threads:
        out.append("\nNo active threads.\n")
    return "".join(out)


def render_index(scan):
    """The normative text of THREADS.md for a ScopeScan: anomalies, then active threads."""
    return INDEX_HEADER + render_anomalies(scan.anomalies) + _active_groups(scan.active)


def render_contract():
    """The exact content of `.threads/.contract`."""
    return "%d\n" % CONTRACT_VERSION


def render_history_index(scan=None):
    """The normative text of `.threads/history/INDEX.md`."""
    threads = scan.closed if scan is not None else []
    out = [HISTORY_INDEX_HEADER]
    for state, label in HISTORY_GROUPS:
        rows = [t for t in threads if t.status == state]
        if not rows:
            continue
        out.append("\n## %s\n\n" % label)
        for t in rows:
            out.append(_entry(t, "%s.md" % t.id))
            if t.leaning:
                out.append("  - leaning: %s\n" % t.leaning)
            if state == "merged":
                out.append("  - merged into: %s\n" % t.fields["merged_into"])
    if not threads:
        out.append("\nNo closed threads.\n")
    return "".join(out)


def render_expired_index(scan=None):
    """The normative text of `.threads/history/expired/INDEX.md`."""
    threads = scan.expired if scan is not None else []
    out = [EXPIRED_INDEX_HEADER]
    if threads:
        out.append("\n")
    for t in threads:
        out.append(_entry(t, "%s.md" % t.id))
        if t.leaning:
            out.append("  - leaning: %s\n" % t.leaning)
        out.append("  - expired: %s\n" % t.fields["expired"])
    if not threads:
        out.append("\nNo expired threads.\n")
    return "".join(out)


def write_atomic(path, text):
    """Write through a temp file in the same folder, then rename.

    Returns False without touching the file when its content is already `text`.
    """
    data = text.encode("utf-8")
    try:
        with open(path, "rb") as f:
            if f.read() == data:
                return False
    except OSError:
        pass
    folder, name = os.path.split(path)
    tmp = os.path.join(folder, ".%s.tmp-%d" % (name, os.getpid()))
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    return True


def _write_generated(scope, result):
    """Write the generated files for `result`; never creates a folder."""
    write_atomic(scope.index_path, render_index(result))
    if os.path.isdir(scope.history_dir):
        write_atomic(os.path.join(scope.history_dir, ARCHIVE_INDEX_FILE),
                     render_history_index(result))
    if os.path.isdir(scope.expired_dir):
        write_atomic(os.path.join(scope.expired_dir, ARCHIVE_INDEX_FILE),
                     render_expired_index(result))


def parse_date(value):
    """A `YYYY-MM-DD` value as a date, or None when it is not a valid one."""
    if not _DATE_RE.fullmatch(value or ""):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def is_expired(thread, now=None):
    """True for a `proposed` thread whose age from `opened` exceeds the TTL.

    Calendar days on the local date, strictly greater; an unreadable
    `opened` counts as expired.
    """
    if thread.status != "proposed":
        return False
    opened = parse_date(thread.fields.get("opened"))
    if opened is None:
        return True
    return ((now or today()) - opened).days > PROPOSED_TTL_DAYS


def retired_text(text, when):
    """The text of a retired thread: `text` with `expired` set and the note appended.

    Everything else is kept byte for byte: an existing `expired` line is
    replaced in place, otherwise `expired: <when>` is inserted just before
    the closing `---`; then the dated note is appended at the end.
    """
    lines = text.split("\n")
    stamp = "expired: %s" % when.isoformat()
    for n, raw in enumerate(lines[1:], 1):
        line = raw.rstrip("\r")
        if line == "---":
            lines.insert(n, stamp)
            break
        if line.partition(":")[0].strip() == "expired":
            lines[n] = stamp
            break
    out = "\n".join(lines)
    if not out.endswith("\n"):
        out += "\n"
    return out + "\n## %s\n\n%s" % (when.isoformat(), RETIREMENT_NOTE)


def _link_new(src, dest):
    """Give `src` the name `dest` without ever replacing an existing entry.

    False when `dest` exists. Uses a hard link; where the file system has
    none, falls back to a checked rename (a narrow race, same folder).
    """
    try:
        os.link(src, dest)
    except FileExistsError:
        return False
    except OSError:
        if os.path.lexists(dest):
            return False
        os.replace(src, dest)
        return True
    os.unlink(src)
    return True


def _retire(scope, thread, when):
    """Move one expired proposal into the expired archive; True when this call did it.

    A vanished source is done already (False, no notice); an existing
    destination is refused (False, nothing written: scan reports it).
    """
    try:
        with open(thread.path, "rb") as f:
            text = f.read().decode("utf-8")
    except FileNotFoundError:
        return False
    name = os.path.basename(thread.path)
    dest = os.path.join(scope.expired_dir, name)
    if os.path.lexists(dest):
        return False
    os.makedirs(scope.expired_dir, exist_ok=True)
    tmp = os.path.join(scope.expired_dir, ".%s.tmp-%d" % (name, os.getpid()))
    with open(tmp, "wb") as f:
        f.write(retired_text(text, when).encode("utf-8"))
    if not _link_new(tmp, dest):
        os.unlink(tmp)
        return False
    queue_notice(scope, thread.id)
    try:
        os.unlink(thread.path)
    except FileNotFoundError:
        pass  # Retired meanwhile by another session: done already.
    return True


def retire_expired(scope, result=None):
    """Retire every expired proposal of `.threads/`; return the retired ids.

    Anomalies are never retired. `result` is a scan to act on (default: a
    fresh one); a stale scan is safe, since moves are idempotent.
    """
    now = today()
    result = scan(scope) if result is None else result
    return [t.id for t in result.active if is_expired(t, now) and _retire(scope, t, now)]


def queue_notice(scope, thread_id):
    """Queue the retirement notice of `thread_id`: an empty file in the queue."""
    os.makedirs(scope.notices_dir, exist_ok=True)
    write_atomic(os.path.join(scope.notices_dir, thread_id), "")


def pending_notices(scope):
    """The ids with a queued retirement notice, sorted; other entries are ignored."""
    try:
        names = os.listdir(scope.notices_dir)
    except OSError:
        return []
    return sorted(n for n in names
                  if valid_id(n) and os.path.isfile(os.path.join(scope.notices_dir, n)))


def upkeep(scope):
    """The idempotent upkeep every operation runs first; return the final scan.

    Retires expired proposals (queueing their notices), then rebuilds the
    generated files from the folders.
    """
    retire_expired(scope)
    result = scan(scope)
    _write_generated(scope, result)
    return result


def ack(scope, target):
    """Acknowledge retirement notices after upkeep: `target` is an id or "all".

    Returns the ids whose notice this call deleted (empty when none was
    queued). Raises ValueError for a target that is neither.
    """
    if target != "all" and not valid_id(target):
        raise ValueError(target)
    upkeep(scope)
    done = []
    for thread_id in pending_notices(scope) if target == "all" else [target]:
        try:
            os.unlink(os.path.join(scope.notices_dir, thread_id))
        except FileNotFoundError:
            continue
        done.append(thread_id)
    return done


def ack_text(done, target):
    """What an adapter prints for an ack of `target` that deleted `done`."""
    if done:
        return "".join("Acknowledged the retirement notice of %s\n" % i for i in done)
    if target == "all":
        return "No retirement notice is queued\n"
    return "No retirement notice is queued for %s\n" % target


def is_stale(thread, now=None):
    """True for an `open` or `deferred` thread idle longer than its threshold.

    Idle days count from `touched`, strictly greater; an unreadable
    `touched` counts as stale, one in the future does not.
    """
    limit = STALE_DAYS.get(thread.status)
    if limit is None:
        return False
    touched = parse_date(thread.fields.get("touched"))
    if touched is None:
        return True
    return ((now or today()) - touched).days > limit


def _contract_warning(scope):
    """The contract-version warning section: its slot in the briefing, empty for now."""
    return ""


class Briefing:
    """The briefing's data sections for one scope, as adapters compose them.

    `urgent` is the list of urgent sections, in order (retirements,
    anomalies, contract-version warning, merge review, stale threads), each
    present only when it has something to say; `listing` is the active
    threads. Each section is text ending in LF; sections are joined by one
    blank line. Adapters insert their own text (the rules) between the
    urgent sections and the listing, and may truncate the listing only.
    """

    def __init__(self, urgent, listing):
        self.urgent = urgent
        self.listing = listing

    def text(self, rules="", listing=None):
        """The whole briefing: urgent sections, `rules` when given, the listing."""
        parts = self.urgent + ([rules] if rules else [])
        parts.append(self.listing if listing is None else listing)
        return "\n".join(parts)


def _retirements(scope, result, ack_command):
    ids = pending_notices(scope)
    if not ids:
        return ""
    questions = {t.id: t.question for t in result.expired}
    out = [BRIEFING_RETIREMENTS_HEADER]
    for thread_id in ids:
        question = questions.get(thread_id)
        out.append("- `%s`%s\n  ack: `%s`\n" % (
            thread_id, " — %s" % question if question else "", ack_command(thread_id)))
    if len(ids) > 1:
        out.append("\nAll at once: `%s`\n" % ack_command("all"))
    return "".join(out)


def briefing(scope, result, ack_command, leaning_max=None):
    """The Briefing of `scope` from `result`, the scan its upkeep returned.

    `ack_command(target)` is the adapter's exact command line that
    acknowledges `target` (an id or "all"); `leaning_max` is the adapter's
    own `leaning` truncation for the listing (None: none).
    """
    now = today()
    urgent = [_retirements(scope, result, ack_command)]
    if result.anomalies:
        urgent.append(BRIEFING_ANOMALIES_HEADER + "".join(
            "- `%s` — %s\n" % (a.rel, a.reason) for a in result.anomalies))
    urgent.append(_contract_warning(scope))
    if len(result.active) > MERGE_REVIEW_OVER:
        urgent.append(BRIEFING_MERGE_REVIEW % len(result.active))
    stale = [t for t in result.active if is_stale(t, now)]
    if stale:
        urgent.append(BRIEFING_STALE_HEADER + "".join(
            "- `%s` (%s, touched %s) — %s\n" % (t.id, t.status, t.fields["touched"], t.question)
            for t in stale))
    listing = (BRIEFING_LISTING_HEADER % (scope.kind.capitalize(), scope.root)
               + _active_groups(result.active, leaning_max))
    return Briefing([u for u in urgent if u], listing)
