"""Unit tests of the core, through its public interface."""
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

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
        with open(os.path.join(self.root, ".threads", name), "w", encoding="utf-8", newline="\n") as f:
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
        core.upkeep(self.scope)
        self.assertIn("No active threads.", self.index())

    def test_non_thread_entries_are_never_anomalies(self):
        self.put("notes.txt", "x")
        self.put(".contract", "1\n")
        self.put(".hidden.md", "x")
        os.makedirs(os.path.join(self.root, ".threads", ".state", "notices"))
        self.put(os.path.join(".state", "notices", "a.md"), "x")
        os.mkdir(os.path.join(self.root, ".threads", "folder.md"))
        self.assertEqual(core.upkeep(self.scope).anomalies, [])
        self.assertIn("No active threads.", self.index())

    def test_terminal_state_in_active_folder_is_an_anomaly(self):
        self.put("a.md", thread_text(**dict(VALID, status="resolved")))
        result = core.upkeep(self.scope)
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
    @unittest.skipIf(os.name == "nt", "chmod cannot make a file unreadable on Windows")
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
        core.upkeep(self.scope)
        self.assertEqual(os.stat(path).st_mtime, 0)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "junk")
        self.assertIn("- `.threads/Bad.md` — frontmatter missing or not the flat subset\n",
                      self.index())

    def test_archive_indexes_only_where_folders_exist(self):
        core.upkeep(self.scope)
        self.assertEqual(os.listdir(os.path.join(self.root, ".threads")), [])
        os.mkdir(os.path.join(self.root, ".threads", "history"))
        core.upkeep(self.scope)
        self.assertEqual(os.listdir(os.path.join(self.root, ".threads", "history")), ["INDEX.md"])

    def test_unchanged_index_not_rewritten(self):
        self.put("a.md", thread_text(**VALID))
        core.upkeep(self.scope)
        os.utime(self.scope.index_path, (0, 0))
        core.upkeep(self.scope)
        self.assertEqual(os.stat(self.scope.index_path).st_mtime, 0)
        self.assertEqual(sorted(os.listdir(self.root)), [".threads", "THREADS.md"])

    def test_lf_and_utf8(self):
        self.put("a.md", thread_text(**dict(VALID, question="Perché?")))
        core.upkeep(self.scope)
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
    @unittest.skipIf(os.name == "nt", "Windows finds git on the parent's PATH: it cannot be hidden")
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
        return sorted(os.path.relpath(os.path.join(d, n), top).replace(os.sep, "/")
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


class Retirement(unittest.TestCase):
    """Edges the conformance cases leave out; the TTL rule itself is covered there."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = os.path.realpath(tmp.name)
        os.makedirs(os.path.join(self.root, ".threads", "history", "expired"))
        self.scope = core.resolve_scope(self.root, {"HOME": os.path.join(self.root, "no-home")})
        os.environ["THREADS_TODAY"] = "2026-03-10"
        self.addCleanup(os.environ.pop, "THREADS_TODAY", None)

    def path(self, *parts):
        return os.path.join(self.root, ".threads", *parts)

    def put(self, rel, data):
        with open(self.path(*rel.split("/")), "wb") as f:
            f.write(data if isinstance(data, bytes) else data.encode("utf-8"))

    def read(self, rel):
        with open(self.path(*rel.split("/")), "rb") as f:
            return f.read()

    def stale(self, **extra):
        fields = dict(VALID, id="p", status="proposed", opened="2026-03-01")
        fields.update(extra)
        return thread_text(**fields)

    def test_moved_back_reads_as_a_normal_thread(self):
        self.put("p.md", self.stale())
        core.upkeep(self.scope)
        self.assertEqual([t.id for t in core.scan(self.scope).expired], ["p"])
        os.rename(self.path("history", "expired", "p.md"), self.path("p.md"))
        result = core.scan(self.scope)
        self.assertEqual(([t.id for t in result.active], result.expired, result.anomalies),
                         (["p"], [], []))

    def test_vanished_source_is_done(self):
        self.put("p.md", self.stale())
        stale_scan = core.scan(self.scope)
        os.remove(self.path("p.md"))
        self.assertEqual(core.retire_expired(self.scope, stale_scan), [])
        self.assertEqual(core.pending_notices(self.scope), [])
        self.assertEqual(os.listdir(self.path("history", "expired")), [])

    def test_repeated_upkeep_after_ack_queues_nothing(self):
        self.put("p.md", self.stale())
        core.upkeep(self.scope)
        self.assertEqual(core.ack(self.scope, "p"), ["p"])
        before = self.read("history/expired/p.md")
        core.upkeep(self.scope)
        self.assertEqual(core.pending_notices(self.scope), [])
        self.assertEqual(self.read("history/expired/p.md"), before)
        self.assertEqual(core.ack(self.scope, "p"), [])

    def test_destination_not_a_thread_file_blocks_retirement(self):
        self.put("p.md", self.stale())
        os.mkdir(self.path("history", "expired", "p.md"))
        result = core.upkeep(self.scope)
        self.assertEqual([(a.rel, a.reason) for a in result.anomalies], [
            (".threads/p.md", "cannot be retired: `.threads/history/expired/p.md` already exists")])
        self.assertEqual(self.read("p.md"), self.stale().encode("utf-8"))
        self.assertEqual(core.pending_notices(self.scope), [])

    def test_bytes_kept_except_the_additions(self):
        original = ("\ufeff---\nid: p\nstatus: proposed\nexpired: 2025-01-01\nopened: 2026-03-01\n"
                    "touched: 2026-03-01\nquestion: Q?\nz_mine: 'kept'\n---\n\n## 2026-03-01\n\nNote.")
        self.put("p.md", original)
        core.upkeep(self.scope)
        expected = original.replace("expired: 2025-01-01", "expired: 2026-03-10") + (
            "\n\n## 2026-03-10\n\n" + core.RETIREMENT_NOTE)
        self.assertEqual(self.read("history/expired/p.md"), expected.encode("utf-8"))
        self.assertFalse(os.path.exists(self.path("p.md")))

    def test_crlf_kept_and_added_lines_lf(self):
        self.put("p.md", self.stale().replace("\n", "\r\n"))
        core.upkeep(self.scope)
        self.assertEqual(self.read("history/expired/p.md"), (
            self.stale().replace("\n", "\r\n")
            .replace("\r\n---\r\n", "\r\nexpired: 2026-03-10\n---\r\n")
            + "\n## 2026-03-10\n\n" + core.RETIREMENT_NOTE).encode("utf-8"))

    def test_creates_missing_folders(self):
        os.rmdir(self.path("history", "expired"))
        os.rmdir(self.path("history"))
        self.put("p.md", self.stale())
        core.upkeep(self.scope)
        self.assertTrue(os.path.isfile(self.path("history", "expired", "p.md")))
        self.assertEqual(core.pending_notices(self.scope), ["p"])

    def test_future_opened_stays(self):
        self.put("p.md", self.stale(opened="2026-04-01"))
        core.upkeep(self.scope)
        self.assertTrue(os.path.isfile(self.path("p.md")))

    def test_ack_rejects_a_non_id(self):
        with self.assertRaises(ValueError):
            core.ack(self.scope, "../p")


class Briefing(unittest.TestCase):
    """Edges the conformance cases leave out; the thresholds are covered there."""

    def thread(self, **extra):
        fields = dict(VALID)
        fields.update(extra)
        return core.Thread("x.md", fields)

    def test_stale_only_open_and_deferred(self):
        now = core.parse_date("2026-06-01")
        for status in ("proposed", "resolved", "abandoned", "merged"):
            with self.subTest(status=status):
                self.assertFalse(core.is_stale(self.thread(status=status), now))
        self.assertTrue(core.is_stale(self.thread(status="deferred"), now))

    def test_unreadable_touched_is_stale(self):
        for value in ("2026-02-30", "soon", "2026-1-1"):
            with self.subTest(touched=value):
                self.assertTrue(core.is_stale(self.thread(touched=value),
                                              core.parse_date("2026-01-03")))

    def test_leaning_cut_only_when_asked(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, ".threads"))
            with open(os.path.join(tmp, ".threads", "a.md"), "w", encoding="utf-8", newline="\n") as f:
                f.write(thread_text(**dict(VALID, leaning="abcdefghij")))
            scope = core.resolve_scope(tmp, {"HOME": os.path.join(tmp, "no-home")})
            result = core.scan(scope)
            self.assertIn("leaning: abcdefghij\n", core.briefing(scope, result, str).listing)
            self.assertIn("leaning: abcd…\n", core.briefing(scope, result, str, 5).listing)

    def test_text_joins_sections_with_one_blank_line(self):
        brief = core.Briefing(["# A\n", "# B\n"], "# L\n")
        self.assertEqual(brief.text(), "# A\n\n# B\n\n# L\n")
        self.assertEqual(brief.text("# R\n", listing="# M\n"), "# A\n\n# B\n\n# R\n\n# M\n")


class ContractVersion(unittest.TestCase):
    """How `.threads/.contract` is read; read-only behaviour is covered by conformance."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        os.mkdir(os.path.join(tmp.name, ".threads"))
        self.scope = core.resolve_scope(tmp.name, {"HOME": os.path.join(tmp.name, "no-home")})

    def put(self, data):
        with open(self.scope.contract_path, "wb") as f:
            f.write(data)

    def test_absent_is_contract_1(self):
        self.assertEqual(core.contract_version(self.scope), 1)
        self.assertEqual(core.contract_warning(self.scope), "")

    def test_tolerant_reader(self):
        for data, version in ((b"1\n", 1), (b"1", 1), (b"\xef\xbb\xbf1\r\n", 1), (b" 12 \n", 12)):
            with self.subTest(data=data):
                self.put(data)
                self.assertEqual(core.contract_version(self.scope), version)

    def test_garbled_is_unknown_and_read_only(self):
        for data in (b"", b"0\n", b"01\n", b"two\n", b"1\n2\n", b"-1\n", b"\xff\n"):
            with self.subTest(data=data):
                self.put(data)
                self.assertIsNone(core.contract_version(self.scope))
                self.assertNotEqual(core.contract_warning(self.scope), "")

    def test_unreadable_is_unknown(self):
        os.mkdir(self.scope.contract_path)
        self.assertIsNone(core.contract_version(self.scope))

    def test_newer_is_read_only(self):
        self.put(b"%d\n" % (core.CONTRACT_VERSION + 1))
        self.assertIn("contract %d;" % (core.CONTRACT_VERSION + 1),
                      core.contract_warning(self.scope))
        with self.assertRaises(core.ReadOnlyScope):
            core.ack(self.scope, "all")


class Hanging(unittest.TestCase):
    """The hanging set: modified since a snapshot, `open` or `proposed`, not touched today."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name
        os.mkdir(os.path.join(self.root, ".threads"))
        self.scope = core.resolve_scope(self.root, {"HOME": os.path.join(self.root, "no-home")})
        patcher = mock.patch.dict(os.environ, THREADS_TODAY="2026-01-03")
        patcher.start()
        self.addCleanup(patcher.stop)

    def put(self, thread_id, **extra):
        fields = dict(VALID, id=thread_id)
        fields.update(extra)
        with open(os.path.join(self.root, ".threads", thread_id + ".md"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(thread_text(**fields))

    def edit(self, thread_id):
        with open(os.path.join(self.root, ".threads", thread_id + ".md"), "a",
                  encoding="utf-8", newline="\n") as f:
            f.write("\n## 2026-01-03\n\nNote.\n")

    def ids(self, snapshot):
        return [t.id for t in core.hanging(self.scope, snapshot)]

    def test_modified_open_and_proposed_hang(self):
        self.put("b-open")
        self.put("a-proposed", status="proposed")
        self.put("c-deferred", status="deferred")
        self.put("d-today", touched="2026-01-03")
        self.put("e-untouched")
        snap = core.take_snapshot(self.scope)
        for thread_id in ("b-open", "a-proposed", "c-deferred", "d-today"):
            self.edit(thread_id)
        self.assertEqual(self.ids(snap), ["a-proposed", "b-open"])

    def test_new_file_counts_as_modified(self):
        snap = core.take_snapshot(self.scope)
        self.put("new")
        self.assertEqual(self.ids(snap), ["new"])

    def test_unmodified_and_anomalies_never_hang(self):
        self.put("a")
        snap = core.take_snapshot(self.scope)
        self.assertEqual(self.ids(snap), [])
        with open(os.path.join(self.root, ".threads", "broken.md"), "w", newline="\n") as f:
            f.write("no frontmatter\n")
        self.assertEqual(self.ids(snap), [])

    def test_moved_to_history_does_not_hang(self):
        self.put("a")
        snap = core.take_snapshot(self.scope)
        os.mkdir(self.scope.history_dir)
        os.rename(os.path.join(self.root, ".threads", "a.md"),
                  os.path.join(self.scope.history_dir, "a.md"))
        self.assertEqual(self.ids(snap), [])

    def test_state_round_trip_is_atomic_json(self):
        self.put("a")
        path = os.path.join(self.scope.threads_dir, ".state", "x", "snap.json")
        self.assertIsNone(core.read_state(path))
        core.write_state(path, {"snapshot": core.take_snapshot(self.scope)})
        self.assertEqual(os.listdir(os.path.dirname(path)), ["snap.json"])
        self.edit("a")
        self.assertEqual(self.ids(core.read_state(path)["snapshot"]), ["a"])
        with open(path, "w", newline="\n") as f:
            f.write("not json")
        self.assertIsNone(core.read_state(path))


class Today(unittest.TestCase):
    def test_forced_clock(self):
        os.environ["THREADS_TODAY"] = "2026-05-04"
        try:
            self.assertEqual(core.today().isoformat(), "2026-05-04")
        finally:
            del os.environ["THREADS_TODAY"]


if __name__ == "__main__":
    unittest.main()
