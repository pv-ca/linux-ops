---
description: Undo a change an agent made to this Linux machine, from the linux-ops journal.
disable-model-invocation: true
argument-hint: "[change id, what to undo, or a period such as today]"
allowed-tools: Bash(python3 *linux-ops/scripts/state.py* plan*)
---

Undo this change on the machine: $ARGUMENTS

The scripts are in `${CLAUDE_PLUGIN_ROOT}/skills/linux-ops/scripts/`. This is what the journal and the machine say right now:

!`python3 "${CLAUDE_PLUGIN_ROOT}/skills/linux-ops/scripts/state.py" plan 2>&1 || true`

1. Pick the changes from the list above. If the request names none, show the list and ask which one. If it asks for everything, or for a period ("today", "since Monday"), take every active change whose date falls in it, say which ones in one line each, and work from the newest to the oldest. Do not fetch the list again.
2. For each change, check that the machine is still in the state its entry describes. If it is not, say what differs and stop before running anything.
3. Run the undo command. Ask first when it falls under the linux-ops skill's confirmation boundary.
4. In one call, run `journal.py undone <id>` for each change undone and `state.py plan` again, and read what still differs.
5. Stop where the skill's section 3 says to: list what has no way back instead of chasing it, and never fetch a package from outside the enabled repositories.

Report in the skill's plain-language form (its section 5): first what is back to how it was, then how the person can check it, then what was left behind and why.
