"""Shared core of threads: one source, packaged into the plugin and the skill.

Python >= 3.9, standard library only (ADR 0003). The adapters (the plugin's
hooks, the skill's `threads` script) stay thin and call the public functions
below; everything that must be byte-identical across implementations lives
here. Do not edit a packaged copy: edit this file and copy it over.
"""
import os
import re
from datetime import date

CONTRACT_VERSION = 1

THREADS_DIR = ".threads"
INDEX_FILE = "THREADS.md"

ACTIVE_STATES = ("proposed", "open", "deferred")
REQUIRED_FIELDS = ("id", "status", "opened", "touched", "question")

INDEX_HEADER = (
    "# THREADS\n"
    "\n"
    "> Generated from `.threads/`. Do not edit by hand: edit the thread files,\n"
    "> and this index is rebuilt on the next upkeep.\n"
)

# Group order and labels of THREADS.md are normative (CONTRACT.md).
INDEX_GROUPS = (
    ("open", "Open"),
    ("deferred", "Deferred"),
    ("proposed", "Proposed (awaiting confirmation)"),
)

_KEY_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


class Scope:
    """A resolved scope: the folder holding `.threads/` and `THREADS.md`."""

    def __init__(self, root):
        self.root = os.path.abspath(root)

    @property
    def threads_dir(self):
        return os.path.join(self.root, THREADS_DIR)

    @property
    def index_path(self):
        return os.path.join(self.root, INDEX_FILE)


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


def resolve_scope(start):
    """The scope for a session started in `start`, or None when inactive."""
    if os.path.isdir(os.path.join(start, THREADS_DIR)):
        return Scope(start)
    return None


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
