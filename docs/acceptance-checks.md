# Acceptance checks

The setup this project was extracted from was verified by ten manual
acceptance checks. They are retired: each one is replaced by the automated
tests below, or no longer applies under `CONTRACT.md`. Conformance cases are
under `tests/conformance/cases/` and run against both implementations; the
other names are test methods in `tests/test_plugin.py` (plugin),
`tests/test_skill.py` (skill) and `tests/test_core.py` (core).

| # | Manual check | Replaced by |
| --- | --- | --- |
| 1 | An `open` thread whose `touched` is today does not block the end of the session. | `test_stop_blocks_on_a_hanging_thread` (the `settled` thread); core `test_modified_open_and_proposed_hang` (`d-today`). |
| 2 | An `open` thread with an old `touched`, modified during the session, blocks the end of the session once. | `test_stop_blocks_on_a_hanging_thread`; `test_stop_blocks_each_thread_once_per_session`. |
| 3 | A second stop attempt in the same session does not block again. | `test_stop_blocks_each_thread_once_per_session`; `test_stop_respects_stop_hook_active`. |
| 4 | A `proposed` thread opened more than 3 days ago is retired to `.threads/history/expired/` with `expired:` and a dated note; if the move fails, the file stays active. | `expire-ttl-boundary`, `start-merge-review-26-full`; `expire-move-collision`; core `test_destination_not_a_thread_file_blocks_retirement`, `test_bytes_kept_except_the_additions`. Retirement now runs at every upkeep (every hook; the skill's `start`, `check`, `regen`, `ack`), not only at session start. |
| 5 | A `proposed` thread with a missing or unreadable `opened` retires immediately. | Unreadable: `expire-unreadable-opened`. Missing: retired as a check — a missing required field makes the file an anomaly, never defaulted and never retired (an anomalous proposal stays put: the same case's `missing-touched`; `regen-anomalies`). |
| 6 | A file moved by hand into or out of `.threads/history/` is mirrored by both `INDEX.md` at the next hook. | `regen-archive-indexes` (a stale hand-written index rebuilt from the folder), `regen-replaces-edited-index`; `test_session_start_regenerates_index`, `test_generated_files_regenerated_on_every_stop`; core `test_moved_back_reads_as_a_normal_thread`. |
| 7 | More than 25 active threads add the merge-review notice; a `merged` thread appears in `history/INDEX.md` with its `merged_into`. | `start-merge-review-25`, `start-merge-review-26-full`; `regen-archive-indexes` (`index-rebuild`). |
| 8 | A retirement notice reappears at every session start until acknowledged. | `start-notice-repeats`; `ack-across-adapters`, `expire-repeated-upkeep`; `test_retirement_notices_first_with_a_working_ack_command`. The old queue file format is retired: the queue is now one empty file per notice (`CONTRACT.md` § Retirement notices). |
| 9 | A file with broken frontmatter or a state that does not belong in its folder is reported as an anomaly in `THREADS.md` and in the start notice, instead of disappearing. | `regen-anomalies`, `start-merge-review-25`, `start-merge-review-26-full`; `test_anomalies_injected_and_files_untouched`. |
| 10 | The start injection stays under the context cap. | `test_urgent_parts_and_rules_survive_the_cap`, `test_listing_not_truncated_below_the_cap`. Plugin only (the skill's `start` has no cap), and only the listing is cut: urgent sections and rules alone may exceed it (`plugin/AGENTS.md`). |

End to end, `scripts/smoke_claude.py` checks by hand that the plugin's
briefing reaches the model in a real Claude Code session.
