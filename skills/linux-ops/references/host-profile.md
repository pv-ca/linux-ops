# Host profile

`detect_host.py` prints the profile; the session start shows its summary. Choose every command from the profile, not from the distribution's name.

| Field | Use |
| --- | --- |
| `notes` | What makes the usual commands wrong on this host: an image-based or declarative system, an init other than systemd, an unknown package manager. Read them before the first change and follow them. The skill works on every distribution; a note changes how you make a change, never whether you may. |
| `package_manager` | `dnf`, `apt`, `pacman`, `zypper`, `apk`, `xbps`, `portage` or another one found on the host; `null` when none was recognized. |
| `change_model` | `imperative`: change the system in place. `image` (Silverblue, Kinoite, Bazzite, MicroOS): the root is read-only, so layer with `rpm-ostree` or `transactional-update`, or use Flatpak or a container, and expect a reboot. `declarative` (NixOS): edit the configuration and rebuild; the undo is the previous generation. |
| `init` | `systemd`, or the name of PID 1. Without systemd, use that init's own commands (`rc-service` and `rc-update`, `sv`, `s6-rc`) and read logs where that system writes them. |
| `support` | `tier1` is tested. On `derivative` and `untested`, confirm a package or unit name on the host before relying on it. |
| `mac` | With SELinux or AppArmor active, check its denials before blaming permissions or the service. |
| `session` | `wayland`, `x11` or `none` decides which display tools exist. |
| `environment` | `sandbox` or `container` means your commands see a confined view: a failed or empty query may be the confinement, not the host. |
| `privilege` | How a privileged command would run: `root`, `sudo`, `doas`, `none`. |

## What the snapshot covers

`state.py diff` reads what is on disk, so it also shows changes nobody recorded: a package update, an edit made by hand, another tool. It covers system packages, Flatpak, Snap, kernel, kernel command line, loaded modules, Secure Boot, enabled units (system and user), user and group names, `/etc`, the user's `~/.config` and dconf. Prefer it to reconstructing history from logs.

Files only root can read are counted as unreadable and not compared. Do not run the scripts as root to reach them: root has its own state directory and would find no snapshots. When one of those files matters, read that file itself with the machine's privilege tool.

`state.py history` knows rpm, dpkg and pacman; on other systems it says so, and you read that system's own package log.
