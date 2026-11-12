---
description: Check whether this Linux machine is ready for a system update or a distribution upgrade, before running it.
disable-model-invocation: true
argument-hint: "[update | upgrade to <release>]"
---

Check whether this machine is ready for: $ARGUMENTS (a regular system update when nothing is named).

The scripts are in `${CLAUDE_PLUGIN_ROOT}/skills/linux-ops/scripts/`.

Read, and change nothing except taking the snapshot:

1. Run `state.py snapshot`, so there is a "before" to compare with whatever happens.
2. Third-party and disabled repositories, and packages that come from none of the enabled ones.
3. Kernel modules built outside the kernel tree (DKMS, akmods) and whether Secure Boot is on: these are what an update most often leaves unloaded.
4. Free space on `/`, `/boot` and the package cache.
5. Held or pinned packages, an interrupted earlier transaction, a reboot already pending.
6. The way back: a second bootable kernel, filesystem snapshots if the system has them, a backup of the user's data. A snapshot is not a backup.
7. Simulate the transaction with the package manager's own dry run and read what it would remove.

Answer with a verdict first (ready, ready with cautions, not ready), then each finding with what to do about it. Do not start the update.
