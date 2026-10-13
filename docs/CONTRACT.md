# Contract

What `linux-ops` promises, on which systems, and what it does when it meets a system outside that promise. Features are designed against this document; a change that breaks it needs this document changed first.

## Scope

The skill administers the single Linux machine the agent is running on, workstation or server: packages, services, logs, networking, storage, boot, drivers, desktop session and access control.

Outside scope: application development, container orchestration, configuration management across many machines.

## Axes

The skill branches on capabilities read from the host, never on the distribution's name alone. `scripts/detect_host.py` reads these axes and prints them as the host profile.

| Axis | Values | Read from |
| --- | --- | --- |
| Family | `fedora`, `debian`, `arch`, `suse` | `ID` and `ID_LIKE` in `os-release` |
| Package manager | `dnf`, `apt`, `pacman`, `zypper` | the family, confirmed by the binary being installed |
| Change model | `imperative`, `image`, `declarative` | `/run/ostree-booted`; `transactional-update` with a read-only root; `/etc/NIXOS` |
| Init | `systemd` or the name of PID 1 | `/run/systemd/system` |
| Access control | SELinux (enforcing, permissive), AppArmor, none | `/sys/fs/selinux`, `/sys/module/apparmor` |
| Session | `wayland`, `x11`, `none` | session environment variables |
| Environment | `physical`, `vm`, `container`, `sandbox`, `wsl` | `systemd-detect-virt`, container markers, kernel release |
| Privilege | `root`, `sudo`, `doas`, `none` | effective user and installed tools |

## Support levels

| Level | Systems | Guarantee |
| --- | --- | --- |
| Tier 1 | Fedora, Debian, Ubuntu, Arch Linux, openSUSE Tumbleweed, openSUSE Leap | Detection runs in CI on the distribution's official container image. |
| Derivative | Anything that resolves to a tier 1 family through `ID_LIKE`: Rocky, Alma, Linux Mint, Pop!_OS, Manjaro, EndeavourOS and others | Works through the same axes. Not tested; package and unit names can differ. |
| Unsupported | Every other system | Read-only mode. |

## Read-only mode

The skill makes changes only on a host where every one of these holds:

1. the family is one of the four above;
2. that family's package manager is installed;
3. the change model is `imperative`;
4. the init system is systemd.

When any of them fails, the profile reports `mode: read-only` with the reasons, and the skill inspects, diagnoses and explains but hands every change to the user as a command to review.

This rule is what makes the skill safe to install anywhere. It may be unable to help on a given system; it does not apply the wrong procedure to it.

Image-based variants of tier 1 families (Fedora Silverblue and Kinoite, openSUSE MicroOS and Aeon) report their parent's `ID`, so they are detected by change model and held in read-only mode until the skill implements their change model.

## Method

The skill's value is method and facts, since models already know the commands:

- **Evidence**: claims about the host come from what was read on it in the current session.
- **Transactions**: a persistent change is prechecked, backed up, applied alone, validated against the intended outcome and reported with its undo path.
- **Boundary**: destructive, irreversible, security-changing and access-interrupting actions are confirmed with the user first.

## Compatibility

- Scripts run on Python 3.6 or later with the standard library only, so they work on every tier 1 release without installing anything.
- The skill follows the Agent Skills format (`SKILL.md` plus bundled files) and avoids features of any single agent in its instructions.
- The host profile is versioned by `schema_version`; a field is removed or changes meaning only with a version bump.
