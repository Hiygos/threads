# Reopen

Reopening brings a thread back from `.threads/history/` or
`.threads/history/expired/` into `.threads/`. It is deliberate, so a
reopened thread always comes back as `open`, never `proposed`, whichever
state it had.

1. Check `.threads/<id>.md` does not exist. If it does, stop and tell the
   user: two files would share one id.
2. Re-read the archived file, then edit it in place:
   - set `status: open` and `touched` to today;
   - remove the `merged_into` line, if any;
   - leave an `expired` line as it is: outside `.threads/history/expired/`
     it is ignored;
   - append a dated note saying why it is reopened.
3. Move it without overwriting, then verify:
   `mv -n .threads/history/<id>.md .threads/<id>.md` (or from
   `.threads/history/expired/<id>.md`), then check it is in `.threads/` and
   gone from the archive.
4. Run the script's `regen`, then tell the user in one line.

A retired proposal must come back as `open`: left `proposed`, it is more
than 3 days old and is retired again the next time the script runs.

If the reopened thread had been merged, its survivor may still be active:
append a dated note there too, saying the thread was split back out.
