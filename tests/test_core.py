"""Unit tests of the core, through its public interface."""
import os
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
        self.scope = core.resolve_scope(self.root)

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
            self.assertIsNone(core.resolve_scope(other))

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


class Today(unittest.TestCase):
    def test_forced_clock(self):
        os.environ["THREADS_TODAY"] = "2026-05-04"
        try:
            self.assertEqual(core.today().isoformat(), "2026-05-04")
        finally:
            del os.environ["THREADS_TODAY"]


if __name__ == "__main__":
    unittest.main()
