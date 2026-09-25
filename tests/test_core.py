"""Unit tests of the core, through its public interface."""
import os
import shutil
import subprocess
import tempfile
import unittest

from tests.core_import import threads_core as core


def thread_text(**fields):
    lines = ["---"] + ["%s: %s" % kv for kv in fields.items()] + ["---", ""]
    return "\n".join(lines)


VALID = dict(id="a", status="open", opened="2026-01-01", touched="2026-01-02", question="Q?")


class ParseFrontmatter(unittest.TestCase):
    def test_flat_fields(self):
        self.assertEqual(core.parse_frontmatter("---\nid: a\nquestion: Why: now?\n---\n"),
                         {"id": "a", "question": "Why: now?"})

    def test_bom_tolerated(self):
        self.assertEqual(core.parse_frontmatter("﻿---\nid: a\n---\n"), {"id": "a"})

    def test_paired_quotes_only(self):
        fields = core.parse_frontmatter("---\na: \"x\"\nb: 'y'\nc: it's'\nd: \"z'\n---\n")
        self.assertEqual(fields, {"a": "x", "b": "y", "c": "it's'", "d": "\"z'"})

    def test_rejects_non_subset(self):
        for text in ("id: a\n", "---\nid: a\n", "---\nnot a pair\n---\n",
                     "---\nid: a\nid: b\n---\n", "---\n  - item\n---\n"):
            with self.subTest(text=text):
                self.assertIsNone(core.parse_frontmatter(text))

    def test_unknown_fields_kept(self):
        self.assertEqual(core.parse_frontmatter("---\nmine: x\n---\n"), {"mine": "x"})


class Regenerate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.mkdir(os.path.join(self.root, ".threads"))
        self.scope = core.resolve_scope(self.root, {"HOME": os.path.join(self.root, "no-home")})

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name, text):
        with open(os.path.join(self.root, ".threads", name), "w", encoding="utf-8") as f:
            f.write(text)

    def index(self):
        with open(self.scope.index_path, encoding="utf-8") as f:
            return f.read()

    def test_inactive_without_threads_dir(self):
        with tempfile.TemporaryDirectory() as other:
            env = {"HOME": os.path.join(other, "home")}
            self.assertIsNone(core.resolve_scope(other, env))

    def test_missing_required_field_not_listed(self):
        fields = dict(VALID)
        del fields["touched"]
        self.put("a.md", thread_text(**fields))
        core.regenerate(self.scope)
        self.assertIn("No active threads.", self.index())

    def test_ignores_non_md_and_terminal_states(self):
        self.put("notes.txt", "x")
        self.put("a.md", thread_text(**dict(VALID, status="resolved")))
        core.regenerate(self.scope)
        self.assertIn("No active threads.", self.index())

    def test_unchanged_index_not_rewritten(self):
        self.put("a.md", thread_text(**VALID))
        core.regenerate(self.scope)
        os.utime(self.scope.index_path, (0, 0))
        core.regenerate(self.scope)
        self.assertEqual(os.stat(self.scope.index_path).st_mtime, 0)
        self.assertEqual(sorted(os.listdir(self.root)), [".threads", "THREADS.md"])

    def test_lf_and_utf8(self):
        self.put("a.md", thread_text(**dict(VALID, question="Perché?")))
        core.regenerate(self.scope)
        with open(self.scope.index_path, "rb") as f:
            data = f.read()
        self.assertNotIn(b"\r", data)
        self.assertIn("Perché?".encode("utf-8"), data)
        self.assertTrue(data.endswith(b"\n") and not data.endswith(b"\n\n"))


GIT = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
       "-c", "commit.gpgsign=false"]


class ResolveScope(unittest.TestCase):
    """Edges the conformance cases leave out; the rule itself is covered there."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = os.path.realpath(tmp.name)
        self.home = self.mkdir("home")
        self.env = {"HOME": self.home, "PATH": os.environ.get("PATH", "")}

    def mkdir(self, *parts):
        path = os.path.join(self.root, *parts)
        os.makedirs(path, exist_ok=True)
        return path

    def git(self, cwd, *args):
        subprocess.run(GIT + list(args), cwd=cwd, env=dict(self.env, GIT_CONFIG_NOSYSTEM="1"),
                       check=True, capture_output=True)

    def worktree(self):
        main = self.mkdir("main")
        self.git(main, "init", "-q")
        self.git(main, "commit", "-q", "--allow-empty", "-m", "x")
        wt = os.path.join(self.root, "wt")
        self.git(main, "worktree", "add", "-q", "--detach", wt)
        self.mkdir("main", ".threads")
        return wt

    def test_home_itself_never_checked(self):
        self.mkdir("home", ".threads")
        self.assertIsNone(core.resolve_scope(self.home, self.env))

    def test_scope_kinds(self):
        self.mkdir("home", ".agents", ".threads")
        self.mkdir("home", "p", ".threads")
        self.assertEqual(core.resolve_scope(self.mkdir("home", "q"), self.env).kind, "user")
        self.assertEqual(core.resolve_scope(self.mkdir("home", "p"), self.env).kind, "project")

    def test_moved_user_root_without_threads_is_inactive(self):
        self.mkdir("home", ".agents", ".threads")
        env = dict(self.env, THREADS_USER_ROOT=self.mkdir("moved"))
        self.assertIsNone(core.resolve_scope(self.mkdir("work"), env))

    @unittest.skipIf(shutil.which("git") is None, "git not found")
    def test_worktree_own_threads_wins(self):
        wt = self.worktree()
        os.mkdir(os.path.join(wt, ".threads"))
        self.assertEqual(core.resolve_scope(wt, self.env).root, wt)

    @unittest.skipIf(shutil.which("git") is None, "git not found")
    def test_worktree_without_git_binary(self):
        wt = self.worktree()
        self.assertEqual(core.resolve_scope(wt, self.env).root, os.path.join(self.root, "main"))
        self.assertIsNone(core.resolve_scope(wt, dict(self.env, PATH=self.mkdir("empty-bin"))))


class Today(unittest.TestCase):
    def test_forced_clock(self):
        os.environ["THREADS_TODAY"] = "2026-05-04"
        try:
            self.assertEqual(core.today().isoformat(), "2026-05-04")
        finally:
            del os.environ["THREADS_TODAY"]


if __name__ == "__main__":
    unittest.main()
