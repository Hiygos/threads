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
USER_ROOT_ENV = "THREADS_USER_ROOT"
DEFAULT_USER_ROOT = ".agents"  # relative to the home directory

ACTIVE_STATES = ("proposed", "open", "deferred")
REQUIRED_FIELDS = ("id", "status", "opened", "touched", "question")

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

_KEY_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


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


class ScopeExists(Exception):
    """Scope creation refused: `scope` already covers the start directory."""

    def __init__(self, scope):
        Exception.__init__(self, scope.root)
        self.scope = scope


class Thread:
    def __init__(self, path, fields):
        self.path = path
        self.fields = fields

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
    regenerate(scope)
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


def parse_frontmatter(text):
    """Parse the strict flat frontmatter subset; None when it is not one.

    Not YAML: one `key: value` per line, paired quotes stripped, nothing else.
    """
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        return None
    fields = {}
    for raw in lines[1:]:
        line = raw.rstrip("\r")
        if line == "---":
            return fields
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


def read_thread(path):
    """A Thread for a well-formed file, or None."""
    try:
        with open(path, "rb") as f:
            text = f.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    fields = parse_frontmatter(text)
    if fields is None or any(not fields.get(k) for k in REQUIRED_FIELDS):
        return None
    return Thread(path, fields)


def scan_active(scope):
    """Well-formed active threads in `.threads/`, sorted by id."""
    threads = []
    for name in sorted(os.listdir(scope.threads_dir)):
        path = os.path.join(scope.threads_dir, name)
        if not name.endswith(".md") or not os.path.isfile(path):
            continue
        thread = read_thread(path)
        if thread and thread.status in ACTIVE_STATES:
            threads.append(thread)
    threads.sort(key=lambda t: t.id)
    return threads


def render_index(threads):
    """The normative text of THREADS.md for `threads`."""
    out = [INDEX_HEADER]
    for state, label in INDEX_GROUPS:
        rows = [t for t in threads if t.status == state]
        if not rows:
            continue
        out.append("\n## %s\n\n" % label)
        for t in rows:
            out.append("- **[%s](%s/%s.md)** — %s\n" % (t.id, THREADS_DIR, t.id, t.question))
            if t.leaning:
                out.append("  - leaning: %s\n" % t.leaning)
    if not threads:
        out.append("\nNo active threads.\n")
    return "".join(out)


def render_contract():
    """The exact content of `.threads/.contract`."""
    return "%d\n" % CONTRACT_VERSION


def render_history_index():
    """The normative text of `.threads/history/INDEX.md` with no closed thread."""
    return HISTORY_INDEX_HEADER + "\nNo closed threads.\n"


def render_expired_index():
    """The normative text of `.threads/history/expired/INDEX.md` with no retired thread."""
    return EXPIRED_INDEX_HEADER + "\nNo expired threads.\n"


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


def regenerate(scope):
    """Rebuild the generated files of `scope` from its folders."""
    write_atomic(scope.index_path, render_index(scan_active(scope)))
