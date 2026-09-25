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

    def test_unknown_fields_preserved_in_order_with_body(self):
        text = "\ufeff---\r\nid: a\r\nz_mine: 1\r\nstatus: open\r\n---\r\n\r\n## 2026-01-01\r\n\r\nNote.\r\n"
        fields, body = core.split_thread(text)
        self.assertEqual(list(fields.items()), [("id", "a"), ("z_mine", "1"), ("status", "open")])
        self.assertEqual(body, "\r\n## 2026-01-01\r\n\r\nNote.\r\n")

    def test_quotes_protect_whitespace_and_colons(self):
        self.assertEqual(core.parse_frontmatter("---\nq: \" a: b \"\ne: ''\n---\n"),
                         {"q": " a: b ", "e": ""})

    def test_rejects_bad_keys_and_unclosed(self):
        for text in ("---\nId: a\n---\n", "---\n1x: a\n---\n", "---\nid: a\n",
                     "", "\n---\nid: a\n---\n"):
            with self.subTest(text=text):
                self.assertIsNone(core.split_thread(text))


class Ids(unittest.TestCase):
    def test_valid(self):
        for value in ("a", "cache-policy", "v2", "2026-review", "a-b-c"):
            with self.subTest(value=value):
                self.assertTrue(core.valid_id(value))

    def test_invalid(self):
        for value in ("", "A", "cache_policy", "-a", "a-", "a--b", "a b", "caché", "a.b",
                      "a\n"):
            with self.subTest(value=value):
                self.assertFalse(core.valid_id(value))


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

    def test_non_thread_entries_are_never_anomalies(self):
        self.put("notes.txt", "x")
        self.put(".contract", "not even a number")
        self.put(".hidden.md", "x")
        os.makedirs(os.path.join(self.root, ".threads", ".state", "notices"))
        self.put(os.path.join(".state", "notices", "a.md"), "x")
        os.mkdir(os.path.join(self.root, ".threads", "folder.md"))
        self.assertEqual(core.regenerate(self.scope).anomalies, [])
        self.assertIn("No active threads.", self.index())

    def test_terminal_state_in_active_folder_is_an_anomaly(self):
        self.put("a.md", thread_text(**dict(VALID, status="resolved")))
        result = core.regenerate(self.scope)
        self.assertEqual([(a.rel, a.reason) for a in result.anomalies],
                         [(".threads/a.md", "status `resolved` does not belong in `.threads/`")])
        self.assertIn("No active threads.", self.index())

    def test_all_missing_fields_listed(self):
        self.put("a.md", thread_text(id="a", status="merged", opened="2026-01-01"))
        reason = core.scan(self.scope).anomalies[0].reason
        self.assertEqual(reason, "missing required fields `touched`, `question`, `merged_into`")

    def test_conditional_fields_elsewhere_tolerated(self):
        # A reopened retired proposal keeps `expired`; a stray `merged_into` is ignored.
        self.put("a.md", thread_text(**dict(VALID, expired="2026-01-05", merged_into="b")))
        self.assertEqual([t.id for t in core.scan(self.scope).active], ["a"])

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root reads anything")
    def test_unreadable_file(self):
        self.put("a.md", thread_text(**VALID))
        path = os.path.join(self.root, ".threads", "a.md")
        os.chmod(path, 0)
        try:
            self.assertEqual(core.scan(self.scope).anomalies[0].reason, "cannot be read")
        finally:
            os.chmod(path, 0o644)

    def test_anomalous_files_untouched(self):
        self.put("Bad.md", "junk")
        path = os.path.join(self.root, ".threads", "Bad.md")
        os.utime(path, (0, 0))
        core.regenerate(self.scope)
        self.assertEqual(os.stat(path).st_mtime, 0)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "junk")
        self.assertIn("- `.threads/Bad.md` — frontmatter missing or not the flat subset\n",
                      self.index())

    def test_archive_indexes_only_where_folders_exist(self):
        core.regenerate(self.scope)
        self.assertEqual(os.listdir(os.path.join(self.root, ".threads")), [])
        os.mkdir(os.path.join(self.root, ".threads", "history"))
        core.regenerate(self.scope)
        self.assertEqual(os.listdir(os.path.join(self.root, ".threads", "history")), ["INDEX.md"])

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


class CreateScope(unittest.TestCase):
    """Edges the conformance cases leave out; the skeleton itself is covered there."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = os.path.realpath(tmp.name)
        self.env = {"HOME": os.path.join(self.root, "home")}

    def tree(self, top):
        return sorted(os.path.relpath(os.path.join(d, n), top)
                      for d, dirs, files in os.walk(top) for n in dirs + files)

    def test_skeleton_only(self):
        work = os.path.join(self.root, "work")
        os.mkdir(work)
        scope = core.create_scope(work, env=self.env)
        self.assertEqual(self.tree(work), sorted([
            ".threads", ".threads/.contract", ".threads/history",
            ".threads/history/INDEX.md", ".threads/history/expired",
            ".threads/history/expired/INDEX.md", "THREADS.md"]))
        with open(scope.contract_path, "rb") as f:
            self.assertEqual(f.read(), b"1\n")
        self.assertEqual(core.resolve_scope(work, self.env).root, work)

    def test_refusal_writes_nothing(self):
        work = os.path.join(self.root, "work")
        os.makedirs(os.path.join(work, ".threads"))
        before = self.tree(self.root)
        with self.assertRaises(core.ScopeExists) as refused:
            core.create_scope(work, env=self.env)
        self.assertEqual(refused.exception.scope.root, work)
        self.assertEqual(self.tree(self.root), before)
        created, text = core.run_init(work, env=self.env)
        self.assertFalse(created)
        self.assertIn(work, text)

    def test_user_scope_creates_missing_root(self):
        users = os.path.join(self.root, "a", "b")
        scope = core.create_scope(self.root, user=True, env=dict(self.env, THREADS_USER_ROOT=users))
        self.assertEqual((scope.kind, scope.root), ("user", users))
        self.assertTrue(os.path.isdir(os.path.join(users, ".threads", "history", "expired")))

    def test_user_notice_only_for_user_scope(self):
        work = os.path.join(self.root, "work")
        os.mkdir(work)
        _, project = core.run_init(work, env=self.env)
        _, user = core.run_init(work, user=True, env=self.env)
        self.assertNotIn("approval", project)
        self.assertEqual(user.count("approval"), 1)


class Today(unittest.TestCase):
    def test_forced_clock(self):
        os.environ["THREADS_TODAY"] = "2026-05-04"
        try:
            self.assertEqual(core.today().isoformat(), "2026-05-04")
        finally:
            del os.environ["THREADS_TODAY"]


if __name__ == "__main__":
    unittest.main()
