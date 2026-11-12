---
description: Write a rescue sheet for this Linux machine while it works - what to do when it will not boot, has no network or no screen, and no agent can help.
disable-model-invocation: true
argument-hint: "[output file]"
---

Write a one-page rescue sheet for this machine, for the moment it cannot reach you. $ARGUMENTS

The scripts are in `${CLAUDE_PLUGIN_ROOT}/skills/linux-ops/scripts/`.

Read the machine and write only what is true here, with the exact names and keys:

1. How to boot the previous kernel or a previous snapshot on this bootloader, and the key that shows the menu.
2. How to reach a text console when the graphical session fails, and how to log in there.
3. How to get the network back from that console on this machine's network stack, including Wi-Fi.
4. Where the linux-ops journal and snapshots are (`journal.py context` prints the host; the state directory is under `~/.local/state/linux-ops/`), and the two commands that show what changed and how to undo the last change.
5. The last changes recorded (`journal.py list --active`), newest first, each with its undo command.
6. Where the user's backup is, if one exists, and what is on no backup.

Save it as Markdown to the file named above, or to `~/linux-rescue.md`, and tell the user to print it or copy it to a phone: a file on the machine that will not boot helps nobody. Leave out passwords and keys.
