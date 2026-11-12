---
description: Show what linux-ops keeps about this machine and where, and erase it or turn the automatic command log off.
disable-model-invocation: true
argument-hint: "[show | erase | stop logging]"
---

Tell me what linux-ops keeps on this machine. $ARGUMENTS

The scripts are in `${CLAUDE_PLUGIN_ROOT}/skills/linux-ops/scripts/` (the `scripts/` folder of the linux-ops skill).

1. Run `journal.py where` and report the directory, the counts and the size. Say that nothing there leaves the machine and that only the owner can read it.
2. To show the content: `journal.py list` for recorded changes, `journal.py list --all` for every logged command.
3. To erase: say that the undo commands and the snapshots go with it and cannot be recovered, wait for a yes, then move that directory to the trash (`gio trash`) or delete it when there is no trash.
4. To stop the automatic log: `LINUX_OPS_NO_LOG=1` in the environment the agent starts from. Show the line and the shell profile it would go in, and add it only after a yes. Recorded changes and snapshots keep working.
