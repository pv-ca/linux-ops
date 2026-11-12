---
description: Set up linux-ops on this machine - first snapshot, and permission rules so read-only inspection stops asking for approval.
disable-model-invocation: true
---

Set up linux-ops on this machine. $ARGUMENTS

The scripts are in `${CLAUDE_PLUGIN_ROOT}/skills/linux-ops/scripts/`.

1. Run `detect_host.py`, `state.py snapshot` and `journal.py where`, and say in two lines what the host is and where the state is kept.
2. Run `state.py history --days 14` and show what changed on this machine in the last two weeks, grouped by day, kernel and drivers first. This is what linux-ops can already answer today; say that files and settings are compared from this first snapshot on.
3. Propose permission rules for the user's Claude Code settings that allow, without asking, only commands that read: the three linux-ops scripts, and this host's own inspection commands (unit status and logs, package queries, device, mount and network listings). Write each rule for the exact command form; never propose a rule that covers `sudo`, a package transaction, a file deletion, or a shell that runs arbitrary text.
4. Show the exact rules and the file they would go in. Apply them only after the user says yes, and keep a copy of the file as it was.

Everything that changes the machine keeps asking, as the linux-ops skill's confirmation boundary says.
