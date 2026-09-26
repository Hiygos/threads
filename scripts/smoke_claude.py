"""Manual end-to-end smoke test: the plugin loaded into a real Claude Code.

    python3 scripts/smoke_claude.py [extra claude arguments...]

Creates a temporary project holding a `.threads/` with one synthetic open
thread under a random id, runs `claude -p` there with this repo's `plugin/`
loaded through `--plugin-dir` and every tool disabled, and asks the model
for the id of the open thread. The id can only come from the briefing
SessionStart injected, so a reply naming it shows the plugin reached the
model. Exits 0 on success, 1 on a wrong reply, 2 when `claude` is missing
or fails.

It calls the model, so it spends usage on the account `claude` is signed in
with. It is never run by CI nor found by `python3 -m unittest` discovery.
Extra arguments go to `claude` as is (e.g. `--model haiku`).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import uuid

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(REPO, "plugin")
TIMEOUT = 300
PROMPT = ("Your session context lists the active threads of this project. "
          "Reply with only the id of the one open thread listed there, nothing else. "
          "If no thread is listed, reply NONE.")


def main(extra):
    claude = shutil.which("claude")
    if claude is None:
        print("smoke: `claude` not found on PATH", file=sys.stderr)
        return 2
    thread_id = "smoke-" + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory() as tmp:
        project = os.path.join(os.path.realpath(tmp), "project")
        os.makedirs(os.path.join(project, ".threads"))
        with open(os.path.join(project, ".threads", thread_id + ".md"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write("---\nid: %s\nstatus: open\nopened: 2026-01-01\ntouched: 2026-01-01\n"
                    "question: Does the smoke test reach the model?\n---\n" % thread_id)
        command = [claude, "-p", PROMPT, "--plugin-dir", PLUGIN, "--tools", "",
                   "--no-session-persistence", "--output-format", "text"] + extra
        try:
            proc = subprocess.run(command, cwd=project, capture_output=True, text=True,
                                  timeout=TIMEOUT, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            print("smoke: `claude -p` timed out after %d s" % TIMEOUT, file=sys.stderr)
            return 2
    reply = proc.stdout.strip()
    if proc.returncode != 0:
        print("smoke: `claude -p` exited %d\n%s" % (proc.returncode, proc.stderr), file=sys.stderr)
        return 2
    if thread_id in reply:
        print("smoke: ok, the model saw %s" % thread_id)
        return 0
    print("smoke: FAILED, expected %s, got:\n%s" % (thread_id, reply), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
