"""Packaging checks: every packaged core copy is identical to the source."""
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(REPO, "core", "threads_core.py")
# Every place the core is packaged into; keep in sync with core/AGENTS.md.
COPIES = [os.path.join(REPO, "skill", "scripts", "threads_core.py")]


class CoreCopies(unittest.TestCase):
    def test_copies_identical(self):
        with open(SOURCE, "rb") as f:
            source = f.read()
        for copy in COPIES:
            with self.subTest(copy=os.path.relpath(copy, REPO)):
                with open(copy, "rb") as f:
                    self.assertTrue(f.read() == source,
                                    "stale core copy: copy core/threads_core.py over it")


if __name__ == "__main__":
    unittest.main()
