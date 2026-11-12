---
description: Show what changed on this Linux machine since it last worked - packages, kernel, modules, enabled units, accounts, configuration files - and what agents recorded doing.
disable-model-invocation: true
argument-hint: "[since when, or what stopped working]"
allowed-tools: Bash(python3 *linux-ops/scripts/state.py* list*), Bash(python3 *linux-ops/scripts/journal.py* list*)
---

Tell me what changed on this machine. $ARGUMENTS

The scripts are in `${CLAUDE_PLUGIN_ROOT}/skills/linux-ops/scripts/`. The saved snapshots, oldest first:

!`python3 "${CLAUDE_PLUGIN_ROOT}/skills/linux-ops/scripts/state.py" list 2>&1 || true`

What agents recorded changing:

!`python3 "${CLAUDE_PLUGIN_ROOT}/skills/linux-ops/scripts/journal.py" list 2>&1 || true`

1. Pick from the list above the latest snapshot from before the moment in question, and run `state.py diff <that snapshot>`. With no moment given, use the oldest snapshot.
2. When no snapshot is old enough, run `state.py history --days N` for what the package manager recorded, and say that files and settings from before the first snapshot cannot be compared.
3. Lead with what the diff shows and no journal entry explains: those are the changes nobody announced. A change a person typed by hand may be in the shell history; ask before reading it, because it can hold secrets.

Answer with the changes grouped as packages, kernel and modules, units, accounts, and files. If something stopped working, say which change is the likeliest cause and why, and what you did not check. Change nothing.
