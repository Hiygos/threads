"""Plugin adapter tests: the `sh` guard and SessionStart, through hook I/O only."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.core_import import threads_core as core

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(REPO, "plugin")
INACTIVE = "threads is inactive: Python ≥3.9 not found"
SOURCES = ("startup", "resume", "compact", "clear")
THREAD = "---\nid: sample\nstatus: open\nopened: 2026-01-01\ntouched: 2026-01-02\nquestion: Which cache?\n---\n"


class PluginHooks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # A private copy of the plugin, to check nothing is written under it.
        self.plugin = os.path.join(self.tmp.name, "plugin")
        shutil.copytree(PLUGIN, self.plugin, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.work = os.path.join(self.tmp.name, "work")
        os.mkdir(self.work)
        self.bin = os.path.join(self.tmp.name, "bin")
        os.mkdir(self.bin)

    def fake(self, name, body):
        path = os.path.join(self.bin, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\n" + body + "\n")
        os.chmod(path, 0o755)

    def real(self, name):
        self.fake(name, 'exec "%s" "$@"' % sys.executable)

    def too_old(self, name):
        # Fails the version check like an interpreter older than 3.9 would.
        self.fake(name, "exit 1")

    def add_scope(self):
        os.mkdir(os.path.join(self.work, ".threads"))
        with open(os.path.join(self.work, ".threads", "sample.md"), "w", encoding="utf-8") as f:
            f.write(THREAD)

    def hook(self, event="SessionStart", source="startup"):
        payload = {"session_id": "s1", "hook_event_name": event, "cwd": self.work}
        if event == "SessionStart":
            payload["source"] = source
        # An isolated HOME: a real user scope on the machine is never read.
        env = dict(os.environ, PATH=self.bin, HOME=os.path.join(self.tmp.name, "home"),
                   TZ="UTC", THREADS_TODAY="2026-01-03")
        env.pop("THREADS_USER_ROOT", None)
        proc = subprocess.run(
            ["/bin/sh", os.path.join(self.plugin, "scripts", "guard.sh"), event],
            input=json.dumps(payload).encode("utf-8"),
            cwd=self.work, env=env, capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.decode("utf-8")

    def init(self, *args):
        """Run `/threads:init`'s command the way its `!` injection does."""
        env = dict(os.environ, PATH=self.bin, HOME=os.path.join(self.tmp.name, "home"))
        env.pop("THREADS_USER_ROOT", None)
        proc = subprocess.run(
            ["/bin/sh", os.path.join(self.plugin, "scripts", "guard.sh"), "init"] + list(args),
            cwd=self.work, env=env, capture_output=True, stdin=subprocess.DEVNULL,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.decode("utf-8")

    def context(self, out):
        output = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SessionStart")
        return output["additionalContext"]

    def listing(self):
        return core.render_index(core.scan(core.resolve_scope(self.work, {"HOME": os.path.join(self.tmp.name, "home")})))

    def tree(self, root):
        return sorted(os.path.relpath(os.path.join(d, n), root)
                      for d, dirs, files in os.walk(root) for n in dirs + files)

    def test_listing_injected_on_every_source(self):
        self.real("python3")
        self.add_scope()
        for source in SOURCES:
            with self.subTest(source=source):
                context = self.context(self.hook(source=source))
                self.assertIn(self.listing(), context)
                self.assertIn("sample", context)

    def test_anomalies_injected_and_files_untouched(self):
        self.real("python3")
        self.add_scope()
        history = os.path.join(self.work, ".threads", "history")
        os.mkdir(history)
        broken = {
            os.path.join(self.work, ".threads", "Broken.md"): b"no frontmatter\n",
            os.path.join(history, "sample.md"): THREAD.replace("open", "resolved").encode(),
        }
        for path, data in broken.items():
            with open(path, "wb") as f:
                f.write(data)
        context = self.context(self.hook())
        self.assertIn("\n## Anomalies\n", context)
        for rel in (".threads/Broken.md", ".threads/history/sample.md", ".threads/sample.md"):
            self.assertIn("- `%s` — " % rel, context)
        self.assertIn(self.listing(), context)
        for path, data in broken.items():
            with open(path, "rb") as f:
                self.assertEqual(f.read(), data)

    def test_session_start_regenerates_index(self):
        self.real("python3")
        self.add_scope()
        self.hook()
        with open(os.path.join(self.work, "THREADS.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), self.listing())

    def test_no_scope_no_output(self):
        self.real("python3")
        self.assertEqual(self.hook(), "")
        self.assertEqual(os.listdir(self.work), [])

    def test_no_state_under_plugin_root(self):
        self.real("python3")
        self.add_scope()
        before = self.tree(self.plugin)
        self.hook()
        self.assertEqual(self.tree(self.plugin), before)

    def test_init_creates_and_refuses_with_exit_0(self):
        self.real("python3")
        before = self.tree(self.plugin)
        self.assertIn(os.path.realpath(self.work), self.init())
        self.assertTrue(os.path.isfile(os.path.join(self.work, ".threads", ".contract")))
        self.assertIn(os.path.realpath(self.work), self.init())
        self.assertEqual(self.tree(self.plugin), before)

    def test_init_bad_argument_writes_nothing(self):
        self.real("python3")
        self.assertIn("usage", self.init("nope"))
        self.assertEqual(os.listdir(self.work), [])

    def test_init_skill_runs_the_guard(self):
        with open(os.path.join(self.plugin, "skills", "init", "SKILL.md"), encoding="utf-8") as f:
            body = f.read()
        self.assertIn('!`sh "${CLAUDE_PLUGIN_ROOT}/scripts/guard.sh" init $ARGUMENTS`', body)
        self.assertIn("disable-model-invocation: true", body)

    def test_init_python_missing(self):
        self.assertEqual(self.init(), INACTIVE + "\n")
        self.assertEqual(os.listdir(self.work), [])

    def test_python_missing(self):
        self.add_scope()
        self.assertEqual(self.context(self.hook()), INACTIVE)
        self.assertEqual(self.hook("Stop"), "")

    def test_python_too_old(self):
        self.too_old("python3")
        self.too_old("python")
        self.add_scope()
        self.assertEqual(self.context(self.hook()), INACTIVE)
        self.assertEqual(self.hook("Stop"), "")
        self.assertFalse(os.path.exists(os.path.join(self.work, "THREADS.md")))

    def test_only_python(self):
        self.real("python")
        self.add_scope()
        self.assertIn(self.listing(), self.context(self.hook()))

    def test_python3_too_old_falls_back_to_python(self):
        self.too_old("python3")
        self.real("python")
        self.add_scope()
        self.assertIn(self.listing(), self.context(self.hook()))


if __name__ == "__main__":
    unittest.main()
