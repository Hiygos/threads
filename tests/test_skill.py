"""Skill adapter tests: the `threads` script's `start` snapshot and `check`, through stdout."""
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "skill", "scripts", "threads")
TODAY = "2026-01-03"
THREAD = "---\nid: %s\nstatus: %s\nopened: 2026-01-01\ntouched: %s\nquestion: Which %s?\n---\n"


class SkillCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = os.path.join(self.tmp.name, "work")
        os.makedirs(os.path.join(self.work, ".threads"))
        for thread_id, status in (("cache", "open"), ("queue", "open"), ("later", "deferred")):
            self.write(thread_id, status)

    def write(self, thread_id, status="open", touched="2026-01-02"):
        with open(os.path.join(self.work, ".threads", thread_id + ".md"), "w",
                  encoding="utf-8") as f:
            f.write(THREAD % (thread_id, status, touched, thread_id))

    def edit(self, thread_id):
        with open(os.path.join(self.work, ".threads", thread_id + ".md"), "a",
                  encoding="utf-8") as f:
            f.write("\n## %s\n\nMore thinking.\n" % TODAY)

    def run_script(self, *args, code=0):
        # An isolated HOME: a real user scope on the machine is never read.
        env = dict(os.environ, HOME=os.path.join(self.tmp.name, "home"), TZ="UTC",
                   THREADS_TODAY=TODAY)
        env.pop("THREADS_USER_ROOT", None)
        proc = subprocess.run([sys.executable, "-B", SCRIPT] + list(args), cwd=self.work,
                              env=env, capture_output=True)
        self.assertEqual(proc.returncode, code, proc.stderr)
        return proc.stdout.decode("utf-8")

    def listed(self, out):
        return [line.split("`")[1] for line in out.splitlines() if line.startswith("- `")]

    def test_start_edit_check_lists_exactly_the_hanging_thread(self):
        self.run_script("start")
        self.assertEqual(self.run_script("check"), "")
        self.edit("cache")
        self.edit("later")  # Deferred: not hanging.
        self.write("queue", touched=TODAY)  # Touched today: settled.
        out = self.run_script("check")
        self.assertEqual(self.listed(out), ["cache"])
        self.assertIn("- `cache` (open, touched 2026-01-02) — Which cache?\n", out)

    def test_new_thread_counts_as_modified(self):
        self.run_script("start")
        self.write("fresh", status="proposed")
        self.assertEqual(self.listed(self.run_script("check")), ["fresh"])

    def test_start_retakes_the_snapshot(self):
        self.run_script("start")
        self.edit("cache")
        self.run_script("start")
        self.assertEqual(self.run_script("check"), "")

    def test_check_without_snapshot(self):
        self.assertIn("threads start", self.run_script("check", code=1))

    def test_check_in_a_read_only_scope(self):
        with open(os.path.join(self.work, ".threads", ".contract"), "w") as f:
            f.write("99\n")
        self.run_script("start")
        self.assertFalse(os.path.exists(os.path.join(self.work, ".threads", ".state")))
        self.assertIn("read-only", self.run_script("check"))


if __name__ == "__main__":
    unittest.main()
