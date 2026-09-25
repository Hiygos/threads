"""Plugin adapter tests: the `sh` guard, SessionStart and Stop, through hook I/O only."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from tests.core_import import threads_core as core

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(REPO, "plugin")
INACTIVE = "threads is inactive: Python ≥3.9 not found"
TODAY = "2026-01-03"
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

    def hook(self, event="SessionStart", source="startup", session="s1", **extra):
        payload = dict(extra, hook_event_name=event, cwd=self.work)
        if session is not None:
            payload["session_id"] = session
        if event == "SessionStart":
            payload["source"] = source
        # An isolated HOME: a real user scope on the machine is never read.
        env = dict(os.environ, PATH=self.bin, HOME=os.path.join(self.tmp.name, "home"),
                   TZ="UTC", THREADS_TODAY=TODAY)
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

    def scope(self):
        return core.resolve_scope(self.work, {"HOME": os.path.join(self.tmp.name, "home")})

    def plugin_module(self):
        """The copied plugin's hook.py, for its constants and ack command line."""
        path = os.path.join(self.plugin, "scripts", "hook.py")
        spec = importlib.util.spec_from_file_location("threads_hook_under_test", path)
        module = importlib.util.module_from_spec(spec)
        saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
        try:
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = saved
            sys.path[:] = [p for p in sys.path if p != os.path.dirname(path)]
        return module

    def briefing(self, leaning_max=None):
        """The briefing's data sections for the scope as it is now (after upkeep)."""
        scope = self.scope()
        hook = self.plugin_module()
        with mock.patch.dict(os.environ, THREADS_TODAY=TODAY):
            return core.briefing(scope, core.scan(scope), lambda t: hook.ack_command(scope, t),
                                 leaning_max)

    def listing(self):
        return self.briefing().listing

    def write(self, name, text):
        with open(os.path.join(self.work, ".threads", name), "w", encoding="utf-8") as f:
            f.write(text)

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
        for rel in (".threads/Broken.md", ".threads/history/sample.md", ".threads/sample.md"):
            self.assertLess(context.index("- `%s` — " % rel), context.index(self.listing()))
        for path, data in broken.items():
            with open(path, "rb") as f:
                self.assertEqual(f.read(), data)

    def test_retirement_notices_first_with_a_working_ack_command(self):
        self.real("python3")
        self.add_scope()
        with open(os.path.join(self.work, ".threads", "old-idea.md"), "w", encoding="utf-8") as f:
            f.write("---\nid: old-idea\nstatus: proposed\nopened: 2025-12-01\n"
                    "touched: 2025-12-01\nquestion: Which log level?\n---\n")
        context = self.context(self.hook())
        self.assertLess(context.index("old-idea"), context.index(self.listing()))
        self.assertIn(self.listing(), context)
        commands = [line.split("`")[1] for line in context.splitlines()
                    if line.strip().startswith("ack: `")]
        self.assertEqual(len(commands), 1)
        env = dict(os.environ, PATH=self.bin + os.pathsep + "/usr/bin:/bin",
                   HOME=os.path.join(self.tmp.name, "home"))
        env.pop("THREADS_USER_ROOT", None)
        proc = subprocess.run(["/bin/sh", "-c", commands[0]], cwd=self.tmp.name, env=env,
                              capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(b"old-idea", proc.stdout)
        self.assertEqual(os.listdir(os.path.join(self.work, ".threads", ".state", "notices")), [])
        self.assertNotIn("ack: `", self.context(self.hook()))

    def test_briefing_order_rules_then_listing(self):
        self.real("python3")
        self.add_scope()
        hook = self.plugin_module()
        context = self.context(self.hook())
        self.assertEqual(context, self.briefing(hook.LEANING_MAX).text(hook.RULES))
        self.assertLess(context.index(hook.RULES), context.index(self.listing()))

    def test_urgent_parts_and_rules_survive_the_cap(self):
        self.real("python3")
        self.add_scope()
        hook = self.plugin_module()
        # One retirement, one anomaly, one stale thread, a merge review, and a
        # listing far longer than the cap.
        self.write("old-idea.md", "---\nid: old-idea\nstatus: proposed\nopened: 2025-12-01\n"
                   "touched: 2025-12-01\nquestion: Which log level?\n---\n")
        self.write("Broken.md", "no frontmatter\n")
        self.write("forgotten.md", THREAD.replace("sample", "forgotten").replace(
            "2026-01-02", "2025-11-01"))
        for n in range(200):
            self.write("topic-%03d.md" % n, THREAD.replace("sample", "topic-%03d" % n).replace(
                "Which cache?", "Which option for topic %d, given everything said so far? " % n * 2))
        context = self.context(self.hook())
        brief = self.briefing(hook.LEANING_MAX)
        self.assertLessEqual(len(context), hook.CONTEXT_CAP)
        self.assertEqual(len(brief.urgent), 4)  # Retirements, anomalies, merge review, stale.
        fixed = "\n".join(brief.urgent + [hook.RULES]) + "\n"
        self.assertTrue(context.startswith(fixed))
        listing = context[len(fixed):].splitlines(True)
        self.assertEqual(listing[-2], "\n")  # The marker line stands apart.
        self.assertIn("THREADS.md", listing[-1])
        self.assertNotIn(listing[-1], brief.listing)
        self.assertTrue(brief.listing.startswith("".join(listing[:-2])))
        self.assertGreater(len(listing), 10)

    def test_listing_not_truncated_below_the_cap(self):
        self.real("python3")
        self.add_scope()
        hook = self.plugin_module()
        context = self.context(self.hook())
        self.assertTrue(context.endswith(self.listing()))
        self.assertLess(len(context), hook.CONTEXT_CAP)

    def test_long_leaning_cut_in_the_listing_only(self):
        self.real("python3")
        self.add_scope()
        hook = self.plugin_module()
        leaning = "x" * (hook.LEANING_MAX * 2)
        self.write("sample.md", THREAD.replace("---\n", "leaning: %s\n---\n" % leaning, 2)
                   .replace("leaning: %s\n---\nid" % leaning, "---\nid"))
        context = self.context(self.hook())
        self.assertNotIn(leaning, context)
        self.assertIn("  - leaning: %s…\n" % ("x" * (hook.LEANING_MAX - 1)), context)
        with open(os.path.join(self.work, "THREADS.md"), encoding="utf-8") as f:
            self.assertIn(leaning, f.read())

    def test_ack_python_missing(self):
        env = dict(os.environ, PATH=self.bin, HOME=os.path.join(self.tmp.name, "home"))
        proc = subprocess.run(
            ["/bin/sh", os.path.join(self.plugin, "scripts", "guard.sh"), "ack", "all"],
            cwd=self.work, env=env, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual((proc.returncode, proc.stdout.decode("utf-8")), (0, INACTIVE + "\n"))

    def test_session_start_regenerates_index(self):
        self.real("python3")
        self.add_scope()
        self.hook()
        with open(os.path.join(self.work, "THREADS.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), core.render_index(core.scan(self.scope())))

    def test_no_scope_no_output(self):
        self.real("python3")
        self.assertEqual(self.hook(), "")
        self.assertEqual(os.listdir(self.work), [])

    def test_no_state_under_plugin_root(self):
        self.real("python3")
        self.add_scope()
        before = self.tree(self.plugin)
        self.hook()
        self.edit("sample")
        self.hook("Stop")
        self.assertEqual(self.tree(self.plugin), before)

    def test_newer_contract_writes_nothing_private_state_included(self):
        # Conformance ignores `.state/plugin/`; here the whole scope, mtimes too.
        self.real("python3")
        self.add_scope()
        self.write(".contract", "%d\n" % (core.CONTRACT_VERSION + 1))
        self.write("old-idea.md", "---\nid: old-idea\nstatus: proposed\nopened: 2025-12-01\n"
                   "touched: 2025-12-01\nquestion: Which log level?\n---\n")

        def state():
            return sorted((os.path.relpath(os.path.join(d, n), self.work),
                           os.lstat(os.path.join(d, n)).st_mtime_ns)
                          for d, dirs, files in os.walk(self.work) for n in dirs + files)

        before = state()
        context = self.context(self.hook())
        self.assertEqual(self.hook("Stop"), "")
        self.assertIn("uses contract %d; update threads" % (core.CONTRACT_VERSION + 1), context)
        env = dict(os.environ, PATH=self.bin, HOME=os.path.join(self.tmp.name, "home"))
        env.pop("THREADS_USER_ROOT", None)
        proc = subprocess.run(["/bin/sh", os.path.join(self.plugin, "scripts", "guard.sh"),
                               "ack", "all"], cwd=self.work, env=env, capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(state(), before)

    def edit(self, thread_id, note="More thinking."):
        """Append a dated note, leaving `touched` as it was: the thread now hangs."""
        with open(os.path.join(self.work, ".threads", thread_id + ".md"), "a",
                  encoding="utf-8") as f:
            f.write("\n## %s\n\n%s\n" % (TODAY, note))

    def blocked(self, out):
        """The ids listed by a Stop block (empty when the hook let the turn end)."""
        if not out:
            return []
        output = json.loads(out)
        self.assertEqual(output["decision"], "block")
        return [line.split("`")[1] for line in output["reason"].splitlines()
                if line.startswith("- `")]

    def test_stop_blocks_on_a_hanging_thread(self):
        self.real("python3")
        self.add_scope()
        self.write("quiet.md", THREAD.replace("sample", "quiet"))
        self.write("parked.md", THREAD.replace("sample", "parked")
                   .replace("status: open", "status: deferred"))
        self.write("settled.md", THREAD.replace("sample", "settled"))
        self.hook()
        self.edit("sample")
        self.edit("parked")
        self.edit("settled")
        with open(os.path.join(self.work, ".threads", "settled.md"), encoding="utf-8") as f:
            text = f.read().replace("touched: 2026-01-02", "touched: " + TODAY)
        self.write("settled.md", text)
        self.write("fresh.md", THREAD.replace("sample", "fresh")
                   .replace("status: open", "status: proposed"))
        out = self.hook("Stop")
        self.assertEqual(self.blocked(out), ["fresh", "sample"])
        self.assertIn(os.path.realpath(self.work), json.loads(out)["reason"])

    def test_stop_blocks_each_thread_once_per_session(self):
        self.real("python3")
        self.add_scope()
        self.write("other.md", THREAD.replace("sample", "other"))
        self.hook()
        self.edit("sample")
        self.assertEqual(self.blocked(self.hook("Stop")), ["sample"])
        self.assertEqual(self.hook("Stop"), "")
        self.edit("sample", "Still thinking.")
        self.edit("other")
        self.assertEqual(self.blocked(self.hook("Stop")), ["other"])
        self.assertEqual(self.hook("Stop"), "")
        # Another session has its own record.
        self.hook(session="s2")
        self.edit("sample", "Third note.")
        self.assertEqual(self.blocked(self.hook("Stop", session="s2")), ["sample"])

    def test_stop_respects_stop_hook_active(self):
        self.real("python3")
        self.add_scope()
        self.hook()
        self.edit("sample")
        self.assertEqual(self.hook("Stop", stop_hook_active=True), "")
        self.assertEqual(self.blocked(self.hook("Stop")), ["sample"])

    def test_stop_ignores_another_sessions_modification(self):
        # s2 changes the thread before s1 starts: s1's snapshot already holds it.
        self.real("python3")
        self.add_scope()
        self.hook(session="s2")
        self.edit("sample")
        self.hook(session="s1")
        self.assertEqual(self.hook("Stop", session="s1"), "")
        self.assertEqual(self.blocked(self.hook("Stop", session="s2")), ["sample"])

    def test_snapshot_kept_on_resume_and_compact_only(self):
        self.real("python3")
        self.add_scope()
        for source, kept in (("resume", True), ("compact", True),
                             ("startup", False), ("clear", False)):
            with self.subTest(source=source):
                session = "s-" + source
                self.hook(session=session)
                self.edit("sample", source)
                self.hook(source=source, session=session)
                self.assertEqual(self.blocked(self.hook("Stop", session=session)),
                                 ["sample"] if kept else [])

    def test_stop_without_session_id_or_scope_is_silent(self):
        self.real("python3")
        self.assertEqual(self.hook("Stop"), "")
        self.assertEqual(os.listdir(self.work), [])
        self.add_scope()
        self.hook()
        self.edit("sample")
        self.assertEqual(self.hook("Stop", session=None), "")
        self.assertEqual(self.hook("Stop", session="../escape"), "")
        self.assertEqual(self.blocked(self.hook("Stop")), ["sample"])

    def test_stop_without_a_snapshot_starts_one(self):
        # The scope was created mid-session: nothing to compare with yet.
        self.real("python3")
        self.add_scope()
        self.edit("sample")
        self.assertEqual(self.hook("Stop"), "")
        self.edit("sample", "Later.")
        self.assertEqual(self.blocked(self.hook("Stop")), ["sample"])

    def test_generated_files_regenerated_on_every_stop(self):
        self.real("python3")
        self.add_scope()
        self.hook()
        index = os.path.join(self.work, "THREADS.md")
        for extra in ({}, {"stop_hook_active": True}, {"session": None}):
            with self.subTest(extra=extra):
                with open(index, "w", encoding="utf-8") as f:
                    f.write("edited by hand\n")
                self.write("added.md", THREAD.replace("sample", "added"))
                self.hook("Stop", **extra)
                with open(index, encoding="utf-8") as f:
                    self.assertEqual(f.read(), core.render_index(core.scan(self.scope())))

    def test_old_session_markers_pruned(self):
        self.real("python3")
        self.add_scope()
        hook = self.plugin_module()
        self.hook(session="old")
        self.hook(session="recent")
        sessions = os.path.join(self.work, ".threads", hook.SESSIONS_DIR)
        old = os.path.join(sessions, "old.json")
        stamp = time.time() - (hook.MARKER_MAX_AGE_DAYS + 1) * 86400
        os.utime(old, (stamp, stamp))
        self.hook(session="new")
        self.assertEqual(sorted(os.listdir(sessions)), ["new.json", "recent.json"])

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
