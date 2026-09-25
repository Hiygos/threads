"""Conformance harness: run each case against every adapter, compare to goldens.

A case is a folder under `cases/` holding `before/` (the sandbox as it
starts), `after/` (the sandbox as it must end) and `case.json`:

    {"date": "YYYY-MM-DD", "operation": ["regen"], "stdout": "", "refusal": null}

`operation` is the skill's subcommand line; each adapter maps it to its own
entry point. `refusal` is null when the operation must succeed, otherwise a
string the refusal output must contain. Empty folders in fixtures carry a
`.gitkeep`, ignored by the comparison. Goldens change only with `--update`.

Optional keys, for scope resolution (paths are relative to the sandbox, `/`
separated):

- `cwd`: the start directory (default `.`, the sandbox itself).
- `git`: folders to `git init` (each gets one empty commit) before the run.
- `worktrees`: `{"<path>": "<repo>"}`, linked worktrees to add, each of a
  repo listed in `git`. The path must be absent or an empty folder.
- `env`: extra environment variables; `{sandbox}` in a value is replaced by
  the sandbox's absolute path. `HOME` defaults to an empty folder outside the
  sandbox (so the machine's real home is never read or written) and
  `THREADS_USER_ROOT` is unset unless given here.
- `silent`: true when every adapter must write nothing to stdout or stderr.

`.git` entries are left out of the comparison. Cases using `git` or
`worktrees` are skipped when the `git` binary is missing.

Adapters:

- `skill` runs `skill/scripts/threads <operation>` in the start directory;
  its stdout is compared with `stdout`.
- `plugin` runs the hook its operation maps to in `PLUGIN_HOOKS`, through the
  real `sh` guard, with the hook input JSON on stdin (`cwd` = the
  start directory). Each entry is `(hook event, output field)`: the field of
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
# Implementation-private state is not part of the contract, wherever the
# scope sits in the sandbox; git's own files are fixture plumbing.
IGNORED_SUFFIXES = (".threads/.state/plugin", ".threads/.state/skill")
IGNORED_NAMES = {"__pycache__", ".git"}
GIT = ["git", "-c", "user.name=Conformance", "-c", "user.email=conformance@example.invalid",
       "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"]

UPDATE = False


class Result:
    """An adapter run; `stdout` is None when it has no counterpart to compare.

    `raw` is everything the adapter wrote to stdout.
    """

    def __init__(self, code, stdout, stderr, raw):
        self.code = code
        self.stdout = stdout
        self.stderr = stderr
        self.raw = raw


def base_env(case, sandbox, home):
    env = dict(os.environ)
    env["TZ"] = "UTC"
    env["THREADS_TODAY"] = case["date"]
    env.pop("THREADS_USER_ROOT", None)
    env.pop("XDG_CONFIG_HOME", None)
    env["HOME"] = home
    # Some Pythons (Apple's) cache bytecode under $HOME, which may sit in the sandbox.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # The guard picks python3 from PATH: make it the interpreter running the tests.
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    for key, value in case.get("env", {}).items():
        env[key] = value.replace("{sandbox}", sandbox)
    return env


def run_skill(start, env, case):
    proc = subprocess.run(
        [sys.executable, SKILL_SCRIPT] + case["operation"],
        cwd=start, env=env, capture_output=True,
    )
    out = proc.stdout.decode("utf-8")
    return Result(proc.returncode, out, proc.stderr.decode("utf-8"), out)


def run_plugin(start, env, case):
    event, field = PLUGIN_HOOKS[case["operation"][0]]
    payload = {"session_id": "conformance", "hook_event_name": event, "cwd": start}
    if event == "SessionStart":
        payload["source"] = "startup"
    proc = subprocess.run(
        ["sh", PLUGIN_GUARD, event], input=json.dumps(payload).encode("utf-8"),
        cwd=start, env=env, capture_output=True,
    )
    out = proc.stdout.decode("utf-8")
    stdout = None
    if field is not None:
        stdout = json.loads(out)["hookSpecificOutput"].get(field, "") if out.strip() else ""
    return Result(proc.returncode, stdout, proc.stderr.decode("utf-8"), out)


ADAPTERS = {"skill": run_skill, "plugin": run_plugin}
# With --update, the reference adapter writes the goldens; the others are
# still compared against them, so a divergence cannot be baked in.
REFERENCE = "skill"


def needs_git(case):
    return bool(case.get("git") or case.get("worktrees"))


def git_available():
    return shutil.which("git") is not None


def setup_git(sandbox, case, env):
    """Create the case's repositories and linked worktrees inside the sandbox."""
    def git(cwd, *args):
        subprocess.run(GIT + list(args), cwd=cwd, env=env, check=True, capture_output=True)

    for rel in case.get("git", []):
        repo = os.path.join(sandbox, *rel.split("/"))
        git(repo, "init", "-q")
        git(repo, "commit", "-q", "--allow-empty", "-m", "fixture")
    for rel, repo in sorted(case.get("worktrees", {}).items()):
        path = os.path.join(sandbox, *rel.split("/"))
        git(os.path.join(sandbox, *repo.split("/")), "worktree", "add", "-q", "--detach", path)


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
                         if d not in IGNORED_NAMES and not (rel + d).endswith(IGNORED_SUFFIXES))
        if rel:
            tree[rel[:-1]] = None
        for name in files:
            if name == KEEP or name in IGNORED_NAMES:
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
        tmp = os.path.realpath(tmp)
        sandbox = os.path.join(tmp, "sandbox")
        home = os.path.join(tmp, "home")
        os.mkdir(home)
        copy_fixture(os.path.join(case_dir, "before"), sandbox)
        env = base_env(case, sandbox, home)
        if needs_git(case):
            setup_git(sandbox, case, env)
        start = os.path.join(sandbox, *case.get("cwd", ".").split("/"))
        result = ADAPTERS[adapter](start, env, case)
        tree = snapshot(sandbox)
    if UPDATE and adapter == REFERENCE:
        write_golden(tree, os.path.join(case_dir, "after"))
        case["stdout"] = result.stdout
        with open(os.path.join(case_dir, "case.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(case, f, indent=2, ensure_ascii=False)
            f.write("\n")
    return case, result, tree, snapshot(os.path.join(case_dir, "after"))
