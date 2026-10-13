---
name: linux-ops
description: >
  Linux system administration on the machine the agent is running on: packages,
  systemd services, logs, networking, storage, boot, drivers, desktop session,
  SELinux/AppArmor. Use to diagnose a fault, change system configuration, or
  install, update or remove software on Fedora, Debian, Ubuntu, Arch or openSUSE
  and their derivatives. Not for application development, container
  orchestration, or fleets of remote machines.
---

# Linux Ops

Administer the host from its **profile** and from **evidence**: read what the machine says, make one **reversible** change at a time, and prove the result.

## 1. Profile the host

Run `python3 scripts/detect_host.py` (path relative to this skill) once per session, before the first diagnosis or change. It only reads. Its JSON is the profile; choose every command from it instead of from the distribution's name.

| Field | Use |
| --- | --- |
| `mode` | `read-write`: the whole skill applies. `read-only`: see below. |
| `package_manager` | `dnf`, `apt`, `pacman` or `zypper`. |
| `support` | `tier1` is tested. On `derivative`, confirm a package or unit name on the host before relying on it. |
| `mac` | With SELinux or AppArmor active, check its denials before blaming permissions or the service. |
| `session` | `wayland`, `x11` or `none` decides which display tools exist. |
| `environment` | `sandbox` or `container` means your commands see a confined view: a failed or empty query may be the confinement, so say so instead of reporting it as host state. |
| `privilege` | How a privileged command would run: `root`, `sudo`, `doas`, `none`. |

**Read-only mode.** When `mode` is `read-only`, `read_only_reasons` says why: an unsupported distribution, an image-based or declarative system, or no systemd. Inspect, diagnose and explain as usual, and give changes to the user as commands to review and run, naming the reason. The procedures here assume a mutable systemd host and are wrong elsewhere.

## 2. Ground every claim in evidence

State what you observed on this host in this session, and label the rest as expected or unknown. These pairs look alike and differ: installed and running; enabled and active; configured and in effect; a past log line and a present fault. Use the installed tool's `--help` or man page for syntax when a flag matters, because the installed version outranks memory. When evidence is missing, name the unknown and run the smallest read that settles it.

A diagnosis, review or plan ends in a report. A change needs a request for that change.

## 3. Change in transactions

For each persistent change:

1. **Precheck**: confirm the exact target, its current state, and how you would undo the change.
2. **Back up** what you are about to replace, next to the original or in a directory you name, and confirm the copy exists.
3. **Apply** one causal change.
4. **Validate** the outcome the user wanted: the unit is active, the device works, the package version is the one intended. Exit status alone is not the outcome.
5. **Decide**: on success continue; on regression undo with the path from step 1; when unsure, gather evidence before changing anything else.
6. **Report**: what changed, what you verified and how, what is still unknown, and the undo command.

One change per transaction keeps the cause of any regression identifiable.

## 4. Confirm at the boundary

A requested, reversible change inside the stated scope proceeds without further questions. Ask first, stating the consequence and the recovery path, before anything that:

- removes packages or deletes or overwrites user data;
- touches boot, kernel, initramfs, drivers, the display manager, disks, partitions or encryption;
- changes the firewall, SELinux or AppArmor policy, authentication, or opens a network service;
- could cut the access the session depends on, such as the network path or the SSH service;
- cannot be undone.

Keep credentials and secrets out of commands, output and reports.
