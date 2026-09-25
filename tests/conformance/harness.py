"""Conformance harness: run each case against every adapter, compare to goldens.

A case is a folder under `cases/` holding `before/` (the scope as it starts),
`after/` (the scope as it must end) and `case.json`:

    {"date": "YYYY-MM-DD", "operation": ["regen"], "stdout": "", "refusal": null}

`operation` is the skill's subcommand line; each adapter maps it to its own
entry point. `refusal` is null when the operation must succeed, otherwise a
string the refusal output must contain. Empty folders in fixtures carry a
`.gitkeep`, ignored by the comparison. Goldens change only with `--update`.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CASES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases")
SKILL_SCRIPT = os.path.join(REPO, "skill", "scripts", "threads")

KEEP = ".gitkeep"
# Implementation-private state is not part of the contract.
IGNORED_DIRS = {".threads/.state/plugin", ".threads/.state/skill"}

UPDATE = False


class Result:
    def __init__(self, code, stdout, stderr):
        self.code = code
        self.stdout = stdout
        self.stderr = stderr


def base_env(case):
    env = dict(os.environ)
    env["TZ"] = "UTC"
    env["THREADS_TODAY"] = case["date"]
    env.pop("THREADS_USER_ROOT", None)
    return env


def run_skill(workdir, case):
    proc = subprocess.run(
        [sys.executable, SKILL_SCRIPT] + case["operation"],
        cwd=workdir, env=base_env(case), capture_output=True,
    )
    return Result(proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8"))


ADAPTERS = {"skill": run_skill}
# With --update, the reference adapter writes the goldens; the others are
# still compared against them, so a divergence cannot be baked in.
REFERENCE = "skill"


def case_names():
    return sorted(n for n in os.listdir(CASES) if os.path.isdir(os.path.join(CASES, n)))


def load_case(name):
    with open(os.path.join(CASES, name, "case.json"), encoding="utf-8") as f:
        return json.load(f)


def snapshot(root):
    """{relative posix path: bytes, or None for a folder} of a tree."""
    tree = {}
    for folder, dirs, files in os.walk(root):
        rel = os.path.relpath(folder, root)
        rel = "" if rel == "." else rel.replace(os.sep, "/") + "/"
        dirs[:] = sorted(d for d in dirs
                         if d != "__pycache__" and rel + d not in IGNORED_DIRS)
        if rel:
            tree[rel[:-1]] = None
        for name in files:
            if name == KEEP:
                continue
            path = os.path.join(folder, name)
            with open(path, "rb") as f:
                tree[os.path.relpath(path, root).replace(os.sep, "/")] = f.read()
    return tree


def copy_fixture(src, dst):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(KEEP))


def write_golden(tree, dst):
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    for rel, data in sorted(tree.items()):
        path = os.path.join(dst, *rel.split("/"))
        if data is None:
            os.makedirs(path, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
    for folder, dirs, files in os.walk(dst):
        if not dirs and not files:
            open(os.path.join(folder, KEEP), "wb").close()


def run_case(name, adapter):
    """Run one case; return (expected, actual) pairs to compare, or update goldens."""
    case = load_case(name)
    case_dir = os.path.join(CASES, name)
    with tempfile.TemporaryDirectory() as tmp:
        workdir = os.path.join(tmp, "scope")
        copy_fixture(os.path.join(case_dir, "before"), workdir)
        result = ADAPTERS[adapter](workdir, case)
        tree = snapshot(workdir)
    if UPDATE and adapter == REFERENCE:
        write_golden(tree, os.path.join(case_dir, "after"))
        case["stdout"] = result.stdout
        with open(os.path.join(case_dir, "case.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(case, f, indent=2, ensure_ascii=False)
            f.write("\n")
    return case, result, tree, snapshot(os.path.join(case_dir, "after"))
