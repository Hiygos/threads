"""Run the conformance suite: `python3 -m tests.conformance [--update]`.

`--update` rewrites every case's `after/` and expected stdout from the
adapters' actual output; review the diff before committing it.
"""
import sys
import unittest

from tests.conformance import harness, test_conformance

if "--update" in sys.argv[1:]:
    harness.UPDATE = True

suite = unittest.defaultTestLoader.loadTestsFromModule(test_conformance)
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
