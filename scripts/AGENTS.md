# AGENTS.md — scripts/

## Purpose

Maintainer tooling run from a clone, never shipped: `release.py`, used by
`.github/workflows/release.yml`.

## Ownership

- `release.py` — `check <tag>` exits 1 unless the tag is `v<version>` with
  the plugin manifest's `version` and `skill/VERSION` equal to it;
  `build <out dir>` writes `threads-skill-<version>.zip` and prints its path.

## Local Contracts

- Stdlib only, Python ≥3.9, runnable from the repo root on every CI platform.
- One product semver `X.Y.Z` in two places that always agree:
  `plugin/.claude-plugin/plugin.json` (`version`) and `skill/VERSION` (the
  version and one LF). Bump both in the same commit; the contract version
  (`CONTRACT.md` § Contract version) is separate and never follows it.
- The zip carries `skill/`'s contents at its root (it unpacks into
  `~/.agents/skills/threads/`), minus dotfiles, `__pycache__` and
  `skill/AGENTS.md`/`CLAUDE.md`; entries are sorted and fixed-dated, and a
  script keeps its executable bit.
- Release flow: work on `dev`, merge to `main`, push the tag `vX.Y.Z`. The
  release workflow checks versions, runs the suite, builds the zip and
  publishes the GitHub Release with it; any failure publishes nothing.

## Verification

- `python3 -m unittest`: `tests/test_packaging.py` covers the check and the
  zip, unpacked and run as a skill.
