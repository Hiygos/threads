"""Conformance harness: run each case against every adapter, compare to goldens.

A case is a folder under `cases/` holding `before/` (the scope as it starts),
`after/` (the scope as it must end) and `case.json`:

    {"date": "YYYY-MM-DD", "operation": ["regen"], "stdout": "", "refusal": null}

`operation` is the skill's subcommand line; each adapter maps it to its own
entry point. `refusal` is null when the operation must succeed, otherwise a
string the refusal output must contain. Empty folders in fixtures carry a
`.gitkeep`, ignored by the comparison. Goldens change only with `--update`.

Adapters:

- `skill` runs `skill/scripts/threads <operation>` in the scope folder; its
  stdout is compared with `stdout`.
- `plugin` runs the hook its operation maps to in `PLUGIN_HOOKS`, through the
  real `sh` guard, with the hook input JSON on stdin (`cwd` = the scope
  folder). Each entry is `(hook event, output field)`: the field of
  `hookSpecificOutput` compared with `stdout`, or None when the hook's output
  has no counterpart of the skill's stdout, in which case only the exit code
  and the files on disk are compared. `regen` maps to SessionStart, which
  regenerates the generated files before injecting the listing; the listing
  itself is not the skill's `regen` output, so it is not compared here.
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
PLUGIN_GUARD = os.path.join(REPO, "plugin", "scripts", "guard.sh")

# Skill operation -> (plugin hook event, hookSpecificOutput field compared
# with the case's stdout, or None when not comparable).
PLUGIN_HOOKS = {"regen": ("SessionStart", None)}

KEEP = ".gitkeep"
# Implementation-private state is not part of the contract.
IGNORED_DIRS = {".threads/.state/plugin", ".threads/.state/skill"}

UPDATE = False


class Result:
    """An adapter run; `stdout` is None when it has no counterpart to compare."""

    def __init__(self, code, stdout, stderr):
        self.code = code
        self.stdout = stdout
        self.stderr = stderr


def base_env(case):
    env = dict(os.environ)
    env["TZ"] = "UTC"
    env["THREADS_TODAY"] = case["date"]
    env.pop("THREADS_USER_ROOT", None)
    # The guard picks python3 from PATH: make it the interpreter running the tests.
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    return env


def run_skill(workdir, case):
    proc = subprocess.run(
        [sys.executable, SKILL_SCRIPT] + case["operation"],
        cwd=workdir, env=base_env(case), capture_output=True,
    )
    return Result(proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8"))


def run_plugin(workdir, case):
    event, field = PLUGIN_HOOKS[case["operation"][0]]
    payload = {"session_id": "conformance", "hook_event_name": event, "cwd": workdir}
    if event == "SessionStart":
        payload["source"] = "startup"
    proc = subprocess.run(
        ["sh", PLUGIN_GUARD, event], input=json.dumps(payload).encode("utf-8"),
        cwd=workdir, env=base_env(case), capture_output=True,
    )
    out = proc.stdout.decode("utf-8")
    stdout = None
    if field is not None:
        stdout = json.loads(out)["hookSpecificOutput"].get(field, "") if out.strip() else ""
    return Result(proc.returncode, stdout, proc.stderr.decode("utf-8"))


ADAPTERS = {"skill": run_skill, "plugin": run_plugin}
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
