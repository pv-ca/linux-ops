---
name: linux-ops
description: >
  Linux system administration on the machine the agent is running on: packages,
  systemd services, logs, networking, storage, boot, drivers, desktop session,
  SELinux/AppArmor. Use to install, configure, update or remove software, change
  system configuration, diagnose a fault, find out what changed since something
  last worked, or undo an earlier change, on any Linux distribution. Keeps a
  journal of every change with its undo command and snapshots of the machine's
  state. Not for application development, container orchestration, or fleets of
  remote machines.
---

# Linux Ops

Administer this machine so that every change is **recorded**, can be **undone**, and can be **explained later** by a session that has none of this conversation.

Every tool call re-reads this whole conversation, so the number of calls is the cost. Each script below answers in one call what would otherwise take several: use it instead of assembling the answer by hand, and put commands that belong together in one call.

## 1. Tools

Scripts are in `scripts/`, relative to this skill. They need only `python3`, and work on any distribution. Their output is short text meant to be read as is; `--json` exists for when you need every item.

| Situation | Run |
| --- | --- |
| Start of the work, when no `linux-ops host:` line is already in context | `journal.py context` |
| Before the first change of a task | `state.py snapshot` |
| A persistent change | one call: `<apply> && <validate> && journal.py record --what … --undo … [--backup …] [--verify …]` |
| Undo, or "what did you (or an earlier session) change?" | `state.py plan [--since YYYY-MM-DD]`: the active changes newest first with their undo commands, the snapshot from before them, and what still differs from it. One call; do not rebuild it from `list`, `show` and the journal file. |
| After undoing | `journal.py undone <id>` for each, in the same call as a final `state.py plan` |
| "It worked before and now it doesn't", "what changed?" | `state.py list`, then `state.py diff <name>` with the newest snapshot taken **before** the trouble started (`before:<change id>` and `latest` also work). Plain `state.py diff` compares with the latest snapshot, which the session start may have taken after the breakage: "matches" then means nothing. |
| The same, when no snapshot is old enough | `state.py history --days N`: what the package manager itself recorded |
| The session start says commands were logged after the last recorded change | `journal.py list --unrecorded`. Check on the machine which of them changed something, and record those. |
| "Is everything I set up still working?", "what is set up here?" | `journal.py list --active`, then each change's `verify` command |

Read a reference file only when the task needs it:

- `references/host-profile.md`: the profile's fields (image-based and declarative systems, other inits, confined environments), what a snapshot covers, and why not to run the scripts as root. Read it when the session start carries a `Note:` line or a query comes back empty.
- `references/diagnose.md`: before diagnosing a fault.
- `references/improve.md`: when the person wants the machine better (faster, battery, games, more software sources, free space): ask, measure, recommend, apply what they pick, measure again.
- `references/install-and-handover.md`: before installing software, and before a step only the person can do (password, reboot, firmware screen).

## 2. Change in transactions

For each persistent change:

1. **Precheck**: the exact target, its current state, and the command that would undo the change.
2. **Back up** any file you are about to replace or edit, and confirm the copy exists.
3. **Apply** one causal change. Use the tool's own simulation first when it has one.
4. **Validate** the outcome the user wanted: the unit is active, the port answers, the version is the intended one.
5. **Record** it with `journal.py record`, chained after the validation so a failed change is never recorded. Write `--what` for a reader with no context, make `--undo` a complete command that restores the previous state, including the restore from the backup, and give `--verify` a read-only command that proves the change is still in effect. Use `--undo none` only when nothing can reverse it, and say so to the user. `--undo` and `--verify` are stored exactly as written, so `record` refuses one that looks like it holds a credential: make the command read the secret from a file or a variable, or repeat with `--keep` when there is no secret in it.
6. On regression, undo with that command and mark it `undone`.

One change per transaction keeps the cause of a regression identifiable, and one record per change is what lets a later session undo part of the work. A journal entry is a claim about the past: before undoing, check that the machine is still in the state the entry describes.

## 3. Undo, and when to stop

Start from `state.py plan`. An undo is done when every recorded undo has run and the plan's comparison shows only what someone else did later and what cannot be reversed. Undo what the change brought with it (dependencies the package manager installed for it, accounts and files its install created), and check with the package manager's own dry run that nothing else goes with them.

Do not chase what has no way back. List it for the person as "left behind", with the reason and the command that would finish it by hand:

- a dependency upgraded to a version whose predecessor no enabled repository offers;
- the account files' automatic backups (`/etc/passwd-`, `/etc/shadow-`, `/etc/group-`, `/etc/gshadow-`);
- empty runtime directories under `/run` and `/var`.

A leftover that one safe local command puts back is not "left behind": run it. `/etc/machine-id` that was empty or absent before, and was filled by a package the undo removed, goes back to what it was; one that held an ID before is never touched.

Never fetch a package from outside the machine's enabled repositories to restore a version: that trades a small leftover for software nobody chose to trust.

When the journal does not say who made a difference, ask or leave it. A timestamp is a hint, not proof.

## 4. Confirm at the boundary

A requested, reversible change inside the stated scope proceeds without further questions. Ask first, stating the consequence and the recovery path, before anything that:

- removes packages or deletes or overwrites user data;
- touches boot, kernel, initramfs, drivers, the display manager, disks, partitions or encryption;
- changes the firewall, SELinux or AppArmor policy, authentication, or opens a network service;
- could cut the access the session depends on, such as the network path or the SSH service;
- cannot be undone.

When a change replaces a way in (SSH configuration, firewall, network), prove the new path works while the old one is still open, and close the old one last.

Keep credentials and secrets out of commands, journal entries and reports.

## 5. Tell the person what happened

Write for someone who started using Linux this month and is reading while worried about their machine. An experienced reader loses nothing by it.

**The receipt.** Every reply in which the machine was changed ends with this block, and nothing after it:

```
Changed on this machine
- <what is different now, as the person would notice it> (undo: /linux-ops:undo <id>)
- …
Works now: <what they can do that they could not before, and the one command or click that shows it>
Still open: <the one thing left for them, or omit the line>
```

- One line per recorded change, in the order made. Say the effect, then the mechanism only if it helps: "Wi-Fi reconnects by itself after sleep", not "added a drop-in for NetworkManager-wait-online".
- A change that cannot be undone says so on its line instead of giving an undo.
- In an agent without slash commands, write the undo as words they can type back: "undo change 5".
- Nothing changed: no receipt. Say in one line that the machine is as it was.

**The rest of the reply.**

- **Result first.** The first line is what is true now or what they must do, never what you are about to explain. A command they must run goes on its own line, ahead of the reason for it.
- **One thing they can check.** Say how they can see for themselves that it worked: a command, a page to open, a light that should turn on.
- **A failure is a cause and a next move.** "The update stopped: the disk is full (412 MB free, it needs 1.2 GB). I can clear the package cache, which frees 3 GB." No apology, no alarm, no "it seems".
- **Steps for the person are numbered, one action each**, with what they should see after each one. When a step waits on them (a password, a reboot), say which step of how many they are on when they come back.
- **One subject at a time.** A second problem you noticed is one sentence at the end, offered as a question.
- **Exact amounts.** "About two minutes and one reboot", "frees 3 GB", never "a while" or "some space".
- **Their words.** Use a term of art only when they will need it to search or to read a screen, and say what it is the first time: "the bootloader (the menu that picks which system starts)".
- **Keep a doubt that is real.** "I could not test this without a reboot" stays. "Perhaps" in front of something you verified goes.

When they ask why or how, explain as fully as the question needs. Section 4 outranks all of this: before a destructive step, the consequence and the way back come first, however long that makes the message.
