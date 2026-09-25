#!/usr/bin/env python3
"""Release tooling: version agreement and the skill zip. Stdlib only.

    python3 scripts/release.py check <tag>      # exit 1 unless tag = manifest = VERSION
    python3 scripts/release.py build <out dir>  # write threads-skill-<version>.zip, print its path

The product version lives in two files that must agree: the plugin manifest
(`plugin/.claude-plugin/plugin.json`, `version`) and the skill's `VERSION`
(`skill/VERSION`, the version and one LF). A release tag is `v<version>`.

The zip holds `skill/`'s contents at its root, so it unpacks straight into
`~/.agents/skills/threads/`. Left out: dotfiles, `__pycache__`, and the
folder's `AGENTS.md`/`CLAUDE.md` (the repo's contract for contributors, not
part of the installed skill). Entries are sorted and dated 1980-01-01, so a
build is reproducible; a file keeps its executable bit.
"""
import json
import os
import re
import stat
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join("plugin", ".claude-plugin", "plugin.json")
VERSION_FILE = os.path.join("skill", "VERSION")
SKILL = "skill"
SEMVER = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
EXCLUDED = {"__pycache__", "AGENTS.md", "CLAUDE.md"}
EPOCH = (1980, 1, 1, 0, 0, 0)


class ReleaseError(Exception):
    pass


def manifest_version(root=REPO):
    with open(os.path.join(root, MANIFEST), encoding="utf-8") as f:
        version = json.load(f).get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise ReleaseError("%s: version %r is not X.Y.Z" % (MANIFEST, version))
    return version


def skill_version(root=REPO):
    with open(os.path.join(root, VERSION_FILE), "rb") as f:
        data = f.read()
    version = data[:-1].decode("utf-8", "replace") if data.endswith(b"\n") else None
    if version is None or not SEMVER.fullmatch(version):
        raise ReleaseError("%s: must hold X.Y.Z and one LF, found %r" % (VERSION_FILE, data))
    return version


def check(tag, root=REPO):
    """The version every source agrees on; ReleaseError on any disagreement."""
    if not tag.startswith("v") or not SEMVER.fullmatch(tag[1:]):
        raise ReleaseError("tag %r is not vX.Y.Z" % tag)
    manifest, skill = manifest_version(root), skill_version(root)
    if not tag[1:] == manifest == skill:
        raise ReleaseError("versions disagree: tag %s, %s %s, %s %s"
                           % (tag, MANIFEST, manifest, VERSION_FILE, skill))
    return manifest


def skill_files(root=REPO):
    """(archive name, absolute path) of every file the zip carries, sorted."""
    base = os.path.join(root, SKILL)
    found = []
    for folder, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in EXCLUDED]
        for name in files:
            if name.startswith(".") or name in EXCLUDED:
                continue
            path = os.path.join(folder, name)
            found.append((os.path.relpath(path, base).replace(os.sep, "/"), path))
    return sorted(found)


def executable(path):
    if os.name == "nt":
        # No executable bit on Windows: a shebang marks a script.
        with open(path, "rb") as f:
            return f.read(2) == b"#!"
    return bool(os.stat(path).st_mode & stat.S_IXUSR)


def build(out_dir, root=REPO):
    """Write `threads-skill-<version>.zip` into out_dir; return its path."""
    version = skill_version(root)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "threads-skill-%s.zip" % version)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, source in skill_files(root):
            info = zipfile.ZipInfo(name, EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if executable(source) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            with open(source, "rb") as f:
                archive.writestr(info, f.read())
    return path


def main(argv):
    try:
        if len(argv) == 2 and argv[0] == "check":
            print("versions agree: %s" % check(argv[1]))
            return 0
        if len(argv) == 2 and argv[0] == "build":
            print(build(argv[1]))
            return 0
    except (OSError, ReleaseError) as error:
        print("release: %s" % error, file=sys.stderr)
        return 1
    print("usage: release.py check <tag> | release.py build <out dir>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
