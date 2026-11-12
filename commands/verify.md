---
description: Check that everything agents set up on this Linux machine still works, for example after a system update.
disable-model-invocation: true
---

Check that what was set up on this machine is still in effect. $ARGUMENTS

The scripts are in `${CLAUDE_PLUGIN_ROOT}/skills/linux-ops/scripts/`.

1. Run `journal.py list --active`.
2. For each change that has a `verify` command, read the command first: run it only if it reads and changes nothing. Then compare the result with what the entry says.
3. For a change with no `verify` command, check the outcome named in its description by the smallest read that proves it.
4. When something no longer holds, run `state.py diff` and `state.py history --days 14` and say which later change is the likeliest cause.

Report three lists: still working, broken, could not check. Change nothing.
