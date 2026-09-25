#!/bin/sh
# Run a threads hook with the first Python >= 3.9 on PATH (python3, then python).
# Usage: sh guard.sh <HookEventName>, with the hook's JSON input on stdin, or
# sh guard.sh init [user], the body of the /threads:init skill.
# Without a suitable interpreter, SessionStart injects one "inactive" line,
# init prints it as plain text, and every other hook exits 0 silently. Shell builtins only: PATH may be bare.
# `-B`: no bytecode cache, so nothing is written under the plugin root.

dir=${0%/*}
[ "$dir" = "$0" ] && dir=.

for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1 &&
     "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    exec "$py" -B "$dir/hook.py" "$@"
  fi
done

if [ "$1" = "SessionStart" ]; then
  printf '%s\n' '{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "threads is inactive: Python ≥3.9 not found"}}'
elif [ "$1" = "init" ]; then
  printf '%s\n' 'threads is inactive: Python ≥3.9 not found'
fi
exit 0
