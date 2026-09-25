"""Packaging checks: core copies identical to the source, one product version,
the release check and the skill zip (`scripts/release.py`)."""
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(REPO, "core", "threads_core.py")
# Every place the core is packaged into; keep in sync with core/AGENTS.md.
COPIES = [
    os.path.join(REPO, "skill", "scripts", "threads_core.py"),
    os.path.join(REPO, "plugin", "scripts", "threads_core.py"),
]
RELEASE = os.path.join(REPO, "scripts", "release.py")
THREAD = ("---\nid: old\nstatus: proposed\nopened: 2025-12-01\ntouched: 2025-12-01\n"
          "question: Which old?\n---\n")


def load_release():
    spec = importlib.util.spec_from_file_location("threads_release_under_test", RELEASE)
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


release = load_release()


def run_release(*args):
    proc = subprocess.run([sys.executable, "-B", RELEASE] + list(args), cwd=REPO,
                          capture_output=True)
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


class CoreCopies(unittest.TestCase):
    def test_copies_identical(self):
        with open(SOURCE, "rb") as f:
            source = f.read()
        for copy in COPIES:
            with self.subTest(copy=os.path.relpath(copy, REPO)):
                with open(copy, "rb") as f:
                    self.assertTrue(f.read() == source,
                                    "stale core copy: copy core/threads_core.py over it")


class Versions(unittest.TestCase):
    def fake_repo(self, manifest, skill):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        os.makedirs(os.path.join(tmp.name, "plugin", ".claude-plugin"))
        os.makedirs(os.path.join(tmp.name, "skill"))
        with open(os.path.join(tmp.name, "plugin", ".claude-plugin", "plugin.json"), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump({"name": "threads", "version": manifest}, f)
        with open(os.path.join(tmp.name, "skill", "VERSION"), "wb") as f:
            f.write(skill)
        return tmp.name

    def test_manifest_agrees_with_skill_version(self):
        self.assertEqual(release.manifest_version(), release.skill_version())

    def test_matching_tag_passes(self):
        version = release.skill_version()
        self.assertEqual(run_release("check", "v" + version)[:2],
                         (0, "versions agree: %s\n" % version))

    def test_disagreeing_tag_fails(self):
        code, out, err = run_release("check", "v999.0.0")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("versions disagree", err)

    def test_any_disagreement_fails(self):
        cases = {
            "tag vs both": ("v1.2.4", "1.2.3", b"1.2.3\n"),
            "manifest": ("v1.2.3", "1.2.4", b"1.2.3\n"),
            "VERSION": ("v1.2.3", "1.2.3", b"1.2.4\n"),
        }
        for label, (tag, manifest, skill) in cases.items():
            with self.subTest(label):
                with self.assertRaisesRegex(release.ReleaseError, "versions disagree"):
                    release.check(tag, self.fake_repo(manifest, skill))
        self.assertEqual(release.check("v1.2.3", self.fake_repo("1.2.3", b"1.2.3\n")), "1.2.3")

    def test_malformed_versions_fail(self):
        root = self.fake_repo("1.2.3", b"1.2.3\n")
        for tag in ("1.2.3", "v1.2", "v01.2.3", "v1.2.3-rc.1", "release"):
            with self.subTest(tag=tag):
                with self.assertRaisesRegex(release.ReleaseError, "not vX.Y.Z"):
                    release.check(tag, root)
        for manifest, skill in (("1.2", b"1.2.3\n"), ("1.2.3", b"1.2.3"),
                                ("1.2.3", b"1.2.3\r\n"), ("1.2.3", b"v1.2.3\n")):
            with self.subTest(manifest=manifest, skill=skill):
                with self.assertRaises(release.ReleaseError):
                    release.check("v1.2.3", self.fake_repo(manifest, skill))


class SkillZip(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = os.path.realpath(tmp.name)
        code, out, err = run_release("build", os.path.join(self.tmp, "dist"))
        self.assertEqual(code, 0, err)
        self.zip = out.strip()

    def test_name_and_entries(self):
        self.assertEqual(os.path.basename(self.zip),
                         "threads-skill-%s.zip" % release.skill_version())
        with zipfile.ZipFile(self.zip) as archive:
            names = archive.namelist()
            modes = {i.filename: (i.external_attr >> 16) & 0o777 for i in archive.infolist()}
        self.assertIn("SKILL.md", names)
        self.assertIn("VERSION", names)
        self.assertIn("scripts/threads", names)
        self.assertIn("scripts/threads_core.py", names)
        for name in names:
            with self.subTest(name=name):
                parts = name.split("/")
                self.assertFalse(any(p.startswith(".") or p == "__pycache__" for p in parts))
                self.assertNotIn(parts[-1], ("AGENTS.md", "CLAUDE.md"))
        self.assertEqual(modes["scripts/threads"], 0o755)
        self.assertEqual(modes["SKILL.md"], 0o644)

    def test_unpacks_as_a_working_skill(self):
        skill = os.path.join(self.tmp, "home", ".agents", "skills", "threads")
        with zipfile.ZipFile(self.zip) as archive:
            archive.extractall(skill)
        work = os.path.join(self.tmp, "work")
        os.makedirs(os.path.join(work, ".threads"))
        with open(os.path.join(work, ".threads", "old.md"), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(THREAD)
        script = os.path.join(skill, "scripts", "threads")
        env = dict(os.environ, HOME=os.path.join(self.tmp, "home"), TZ="UTC",
                   THREADS_TODAY="2026-01-03")
        env.pop("THREADS_USER_ROOT", None)
        proc = subprocess.run([sys.executable, "-B", script, "start"], cwd=work, env=env,
                              capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout.decode("utf-8")
        self.assertIn("# Retired proposals", out)
        self.assertIn("cd %s && %s %s ack old" % (shlex.quote(work), shlex.quote(sys.executable),
                                                  shlex.quote(script)), out)
        self.assertTrue(os.path.isfile(os.path.join(work, ".threads", "history", "expired",
                                                    "old.md")))


if __name__ == "__main__":
    unittest.main()
