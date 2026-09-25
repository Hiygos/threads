"""Skill adapter tests: the `threads` script (`start` snapshot and `check`, `init`'s
setup text, snippet insertion), the skill's files, and the skill copied alone."""
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(REPO, "skill")
SCRIPT = os.path.join(SKILL, "scripts", "threads")
BEGIN = "<!-- threads:begin -->"
END = "<!-- threads:end -->"
LIMITS = "# What this skill cannot guarantee"
TODAY = "2026-01-03"
THREAD = "---\nid: %s\nstatus: %s\nopened: 2026-01-01\ntouched: %s\nquestion: Which %s?\n---\n"


def can_symlink():
    """Whether this machine lets the tests create a symlink (Windows may not)."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.symlink("target", os.path.join(tmp, "link"))
        except (AttributeError, NotImplementedError, OSError):
            return False
    return True


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
                  encoding="utf-8", newline="\n") as f:
            f.write(THREAD % (thread_id, status, touched, thread_id))

    def edit(self, thread_id):
        with open(os.path.join(self.work, ".threads", thread_id + ".md"), "a",
                  encoding="utf-8", newline="\n") as f:
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
        with open(os.path.join(self.work, ".threads", ".contract"), "w", newline="\n") as f:
            f.write("99\n")
        self.run_script("start")
        self.assertFalse(os.path.exists(os.path.join(self.work, ".threads", ".state")))
        self.assertIn("read-only", self.run_script("check"))


def run(script, cwd, home, *args, code=0, test=None):
    """Run the script with an isolated HOME; return its stdout."""
    env = dict(os.environ, HOME=home, TZ="UTC", THREADS_TODAY=TODAY)
    env.pop("THREADS_USER_ROOT", None)
    proc = subprocess.run([sys.executable, "-B", script] + list(args), cwd=cwd, env=env,
                          capture_output=True)
    test.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
    return proc.stdout.decode("utf-8")


class SkillSetup(unittest.TestCase):
    """`init`'s skill-only text and `snippet`'s idempotent insertion between markers."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = os.path.realpath(tmp.name)
        self.home = os.path.join(self.root, "home")
        self.work = os.path.join(self.root, "work")
        os.makedirs(self.home)
        os.makedirs(self.work)

    def script(self, *args, code=0):
        return run(SCRIPT, self.work, self.home, *args, code=code, test=self)

    def read(self, path):
        with open(path, "rb") as f:
            return f.read().decode("utf-8")

    def write(self, path, text):
        with open(path, "wb") as f:
            f.write(text.encode("utf-8"))

    def snippet(self):
        return self.script("snippet")

    def test_init_prints_the_limits_once_and_the_snippet(self):
        out = self.script("init")
        self.assertTrue(out.startswith("Created the project scope at %s\n" % self.work))
        self.assertEqual(out.count(LIMITS), 1)
        self.assertEqual(out.count(BEGIN), 1)
        self.assertTrue(out.endswith(self.snippet()))
        # A refusal repeats it too, once: the scope may be another harness's.
        out = self.script("init", code=1)
        self.assertTrue(out.startswith("Not created: "))
        self.assertEqual(out.count(LIMITS), 1)

    def test_snippet_is_marker_delimited(self):
        lines = self.snippet().splitlines()
        self.assertEqual((lines[0], lines[-1]), (BEGIN, END))
        self.assertIn("start", self.snippet())
        self.assertIn("check", self.snippet())

    def test_insert_into_missing_file(self):
        path = os.path.join(self.work, "sub", "AGENTS.md")
        self.assertIn("Added", self.script("snippet", path))
        self.assertEqual(self.read(path), self.snippet())

    def test_insert_into_existing_file_then_repeat(self):
        path = os.path.join(self.work, "AGENTS.md")
        self.write(path, "# Project\n\nRules.")
        self.script("snippet", path)
        first = self.read(path)
        self.assertEqual(first, "# Project\n\nRules.\n\n" + self.snippet())
        self.assertIn("already up to date", self.script("snippet", path))
        self.assertEqual(self.read(path), first)

    def test_older_snippet_is_replaced_not_duplicated(self):
        path = os.path.join(self.work, "AGENTS.md")
        self.write(path, "# Project\n\n%s\nOld pointer.\n%s\n\n## After\n" % (BEGIN, END))
        self.assertIn("Updated", self.script("snippet", path))
        text = self.read(path)
        self.assertEqual(text, "# Project\n\n" + self.snippet() + "\n## After\n")
        self.assertEqual(text.count(BEGIN), 1)

    def test_duplicate_blocks_collapse_to_one(self):
        path = os.path.join(self.work, "AGENTS.md")
        old = "%s\nOld.\n%s\n" % (BEGIN, END)
        self.write(path, "A\n" + old + "B\n" + old + "C\n")
        self.script("snippet", path)
        self.assertEqual(self.read(path), "A\n" + self.snippet() + "B\nC\n")

    def test_crlf_file_keeps_its_line_endings(self):
        path = os.path.join(self.work, "AGENTS.md")
        self.write(path, "Rules.\r\n")
        self.script("snippet", path)
        self.assertEqual(self.read(path),
                         "Rules.\r\n\r\n" + self.snippet().replace("\n", "\r\n"))

    def test_unpaired_markers_are_refused(self):
        path = os.path.join(self.work, "AGENTS.md")
        self.write(path, "%s\nHalf a block.\n" % BEGIN)
        self.assertIn("Not written", self.script("snippet", path, code=1))
        self.assertEqual(self.read(path), "%s\nHalf a block.\n" % BEGIN)

    @unittest.skipUnless(can_symlink(), "cannot create symlinks here")
    def test_symlink_target_is_written(self):
        target = os.path.join(self.work, "AGENTS.md")
        self.write(target, "Rules.\n")
        link = os.path.join(self.work, "CLAUDE.md")
        os.symlink("AGENTS.md", link)
        self.script("snippet", link)
        self.assertTrue(os.path.islink(link))
        self.assertEqual(self.read(target).count(BEGIN), 1)


class SkillFiles(unittest.TestCase):
    """SKILL.md's frontmatter and links, and the skill working when copied alone."""

    def read(self, path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_frontmatter(self):
        lines = self.read(os.path.join(SKILL, "SKILL.md")).split("\n")
        self.assertEqual(lines[0], "---")
        end = lines.index("---", 1)
        fields = {}
        for line in lines[1:end]:
            key, sep, value = line.partition(":")
            self.assertTrue(sep, line)
            self.assertNotIn(key.strip(), fields)
            fields[key.strip()] = value.strip()
        self.assertEqual(set(fields), {"name", "description", "license", "compatibility"})
        self.assertEqual(fields["name"], "threads")
        self.assertTrue(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fields["name"]))
        self.assertTrue(0 < len(fields["description"]) <= 1024)
        self.assertEqual(fields["license"], "MIT")
        self.assertEqual(fields["compatibility"], "Requires Python 3 on PATH (stdlib only)")

    def test_every_linked_reference_exists(self):
        refs = os.path.join(SKILL, "references")
        docs = [os.path.join(SKILL, "SKILL.md")]
        docs += [os.path.join(refs, n) for n in sorted(os.listdir(refs)) if n.endswith(".md")]
        seen = set()
        for doc in docs:
            for link in re.findall(r"\]\(([^)#:]+\.md)\)", self.read(doc)):
                path = os.path.normpath(os.path.join(os.path.dirname(doc), link))
                seen.add(os.path.relpath(path, SKILL))
                self.assertTrue(os.path.isfile(path), "%s in %s" % (link, doc))
        for name in ("harnesses", "porting", "merge", "reopen", "migrate"):
            self.assertIn(os.path.join("references", name + ".md"), seen)

    def test_works_copied_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = os.path.realpath(tmp)
            copy = os.path.join(tmp, "skills", "threads")
            shutil.copytree(SKILL, copy, symlinks=True,
                            ignore=shutil.ignore_patterns("__pycache__"))
            work = os.path.join(tmp, "work")
            os.makedirs(os.path.join(work, ".threads", "history", "expired"))
            with open(os.path.join(work, ".threads", "old.md"), "w", encoding="utf-8", newline="\n") as f:
                f.write(THREAD.replace("2026-01-01", "2025-12-01")
                        % ("old", "proposed", "2025-12-01", "old"))
            script = os.path.join(copy, "scripts", "threads")
            out = run(script, work, os.path.join(tmp, "home"), "start", test=self)
            self.assertIn("# Retired proposals", out)
            self.assertIn("# Active threads", out)
            # The ack line names the copy and the interpreter that ran it.
            ack = "cd %s && %s %s ack old" % (shlex.quote(work), shlex.quote(sys.executable),
                                              shlex.quote(script))
            self.assertIn(ack, out)
            self.assertTrue(os.path.isfile(os.path.join(work, ".threads", "history",
                                                        "expired", "old.md")))


if __name__ == "__main__":
    unittest.main()
