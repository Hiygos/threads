# AGENTS.md — scripts/

## Purpose

Maintainer tooling run from a clone, never shipped: `release.py`, used by
`.github/workflows/release.yml`, and the manual smoke test `smoke_claude.py`.

## Ownership

- `release.py` — `check <tag>` exits 1 unless the tag is `v<version>` with
  the plugin manifest's `version` and `skill/VERSION` equal to it;
  `build <out dir>` writes `threads-skill-<version>.zip` and prints its path.
- `smoke_claude.py` — manual end-to-end smoke test: runs `claude -p` with
  `--plugin-dir plugin` and no tools in a temp project holding one synthetic
  thread, and checks the reply names its id (the briefing reached the model).

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
- `smoke_claude.py` is run by hand only (`python3 scripts/smoke_claude.py
  [claude args]`): it needs a signed-in `claude` and spends model usage, so
  CI never runs it and its name keeps it out of `unittest` discovery.
- Release flow: work on `dev`, merge to `main`, push the tag `vX.Y.Z`. The
  release workflow checks versions, runs the suite, builds the zip and
  publishes the GitHub Release with it; any failure publishes nothing.

## Verification

- `python3 -m unittest`: `tests/test_packaging.py` covers the check and the
  zip, unpacked and run as a skill.
