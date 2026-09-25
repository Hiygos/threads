"""Every conformance case, against every adapter."""
import unittest

from tests.conformance import harness


class Conformance(unittest.TestCase):
    maxDiff = None

    def test_cases(self):
        names = harness.case_names()
        self.assertTrue(names, "no conformance cases found")
        for name in names:
            for adapter in [harness.REFERENCE] + sorted(set(harness.ADAPTERS) - {harness.REFERENCE}):
                with self.subTest(case=name, adapter=adapter):
                    case, result, actual, expected = harness.run_case(name, adapter)
                    if case["refusal"] is None:
                        self.assertEqual(result.code, 0, result.stderr)
                    else:
                        self.assertNotEqual(result.code, 0)
                        self.assertIn(case["refusal"], (result.stdout or "") + result.stderr)
                    if result.stdout is not None:
                        self.assertEqual(result.stdout, case["stdout"])
                    self.assertEqual(sorted(actual), sorted(expected), "paths differ")
                    for path in expected:
                        self.assertEqual(actual[path], expected[path], path)


if __name__ == "__main__":
    unittest.main()
