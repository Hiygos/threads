# Merge

Merging removes overlap between two active threads while keeping both
histories. The agent proposes, the user approves: never merge on your own.

## Propose

Name the thread that survives, the one it absorbs, and why they overlap, in
one or two lines. Wait for the user's yes. Several absorbed threads into one
survivor are fine; each one is a separate merge below.

## Apply

The survivor must be an active thread in `.threads/`; never merge into a
thread in an archive. Re-read both files right before editing them.

1. **Survivor** (`.threads/<survivor>.md`): append a dated note summarising
   what it takes over, e.g. `Merged in <absorbed>: <its question and
   position>.`; update `leaning` if the merge changes your position; set
   `touched` to today.
2. **Absorbed** (`.threads/<absorbed>.md`): set `status: merged`, add the
   field `merged_into: <survivor>`, set `touched` to today, and append a
   dated note `Merged into <survivor>.` with anything it added.
3. Move the absorbed thread without overwriting, then verify:
   `mkdir -p .threads/history && mv -n .threads/<absorbed>.md .threads/history/<absorbed>.md`,
   then check it is in `.threads/history/` and gone from `.threads/`. If the
   destination already exists, stop and tell the user.
4. Tell the user in one line per merge.

To undo a merge, reopen the absorbed thread (`reopen.md`).
