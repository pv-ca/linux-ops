# Contract

What `linux-ops` promises, on which systems, and what it does when it meets a system outside that promise. Features are designed against this document; a change that breaks it needs this document changed first.

## Scope

The skill administers the single Linux machine the agent is running on, workstation or server: packages, services, logs, networking, storage, boot, drivers, desktop session and access control.

Outside scope: application development, container orchestration, configuration management across many machines.

## Axes

The skill branches on capabilities read from the host, never on the distribution's name alone. `scripts/detect_host.py` reads these axes and prints them as the host profile.

| Axis | Values | Read from |
| --- | --- | --- |
| Family | `fedora`, `debian`, `arch`, `suse`, or none | `ID` and `ID_LIKE` in `os-release` |
| Package manager | `dnf`, `apt`, `pacman`, `zypper`; outside those families `apk`, `xbps`, `portage`, `eopkg`, `swupd`, `slackpkg`, `nix` | the family, confirmed by the binary being installed; else the first of the others found |
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
| Untested | Every other system: Alpine, Void, Gentoo, NixOS and the rest | Works through the same axes, with a note in the profile. Detection and snapshots run in CI on Alpine. |

## Any distribution

The skill works on every Linux distribution, and no axis forbids a change. Where the usual commands would be wrong, the profile says so in `notes`, and the skill changes the system the way that system expects:

- **Image-based** (Fedora Silverblue, Kinoite, Bazzite, openSUSE MicroOS and Aeon): these report their parent's `ID`, so they are detected by change model. Packages are layered with the system's own tool, or installed as Flatpak or in a container.
- **Declarative** (NixOS): the configuration is edited and rebuilt; the previous generation is the undo.
- **No systemd**: the init's own service commands are used.
- **Unknown package manager**: the skill asks how software is installed there instead of guessing.

What keeps this safe is not a list of allowed systems. It is that every change is prechecked, backed up, recorded with its undo, and confirmed first when it is destructive.

## Method

The skill's value is the machine's memory, since models already know the commands:

- **Journal**: a persistent change is prechecked, backed up, applied alone, validated against the intended outcome and recorded with the command that undoes it. `journal.py` never runs an undo command; the agent does, after checking the machine still matches the entry.
- **Snapshots**: `state.py` saves system packages, Flatpak and Snap, the kernel and its command line, loaded modules, Secure Boot state, enabled units (system and user), user and group names, a hash of each readable file in `/etc` and in the user's `~/.config` (three levels deep, files up to 256 KB), and dconf, and compares two snapshots. A file it cannot read is counted, never reported as unchanged; a fact it cannot read is `null`, never a guess.
- **History**: `state.py history` reads the package manager's own record (rpm install times, `dpkg.log`, `pacman.log`), so the days before the first snapshot are not blank. On rpm systems it cannot see removals. On a system with another package manager it says it has no log to read, rather than print an empty list.
- **Any Linux**: the journal, snapshots and diff do not depend on the support level, and leave empty what the system does not have. Enabled services are read from systemd, OpenRC or runit.
- **Evidence**: claims about the host come from what was read on it in the current session.
- **Boundary**: destructive, irreversible, security-changing and access-interrupting actions are confirmed with the user first.

## State

The scripts write in one place only: `$LINUX_OPS_STATE`, or else `$XDG_STATE_HOME/linux-ops/<machine-id>/` (`~/.local/state` by default). Inside a container (distrobox, toolbox, Podman, Docker) the directory is `<machine-id>-<container>/`, because such a container may share the host's machine id and home while its packages are its own. It holds `journal.jsonl` and `snapshots/`, readable by the owner only. The journal is never trimmed; the newest 90 snapshots are kept. The scripts send nothing anywhere; what an agent reads from there goes to its model provider like any other tool output. Deleting the directory removes the skill's memory and nothing else.

Commands are masked before they are written: a value assigned to a credential-looking name (`password`, `token`, `secret`, `api key`, `access key`, `authorization`), quoted or not, the value of a flag with such a name, the password or token inside a URL, a private key, and the password arguments of common tools (`curl -u`, `sshpass`, `mysql`, `nmcli`, `chpasswd`, `docker login`, `redis-cli`, `htpasswd`, `smbclient`, `aws configure`, `sudo -S`). The mask is a courtesy, not a guarantee. A recorded undo or verify command is never masked, because a masked command no longer runs: `journal.py record` refuses one that looks like it holds a credential, unless `--keep` says it does not. A logged command longer than 4000 characters is cut. File edits are logged unless the file is inside a Git work tree.

## Agents

One folder serves three agents. `skills/linux-ops/` is the only place with behavior; each adapter is a manifest and a hook file that call its scripts.

| Agent | Manifest | Hooks | Extra |
| --- | --- | --- | --- |
| Claude Code | `.claude-plugin/plugin.json` | `hooks/hooks.json` | `commands/` |
| Codex | `.codex-plugin/plugin.json` | `hooks/hooks.json` (same file) | |
| Antigravity | `.antigravity-plugin/plugin.json` | `hooks.json` at the root | |

The hooks do two things: print the host, the latest changes and how many commands were logged without a recorded change, at session start and again after the context is cleared or compacted (and take a snapshot when the last one is older than a day), and append each command the agent ran to the journal. `journal.py hook` reads the payload of any of the three. A hook failure never blocks the session. The hooks are a record, not a security boundary: nothing here blocks a command.

`state.py plan` prints the active changes with their undo commands, the snapshot from before them and what still differs from it, as text; it runs nothing. `state.py diff` prints text, and JSON with `--json`. `state.py status` prints JSON for a program to show.

In Claude Code, `hooks/panel.tsx` draws a panel from `state.py status`, as a chip under the prompt (default), a bar above it, a side panel, or not at all (`/linux-ops-panel chip|bar|side|off`): it runs only that script (`status`, and `snapshot` when "Take one now" is pressed), `detect_host.py` and `uname -r` on the host, spends no model tokens, and never runs an undo. Its Undo buttons only fill the prompt. The chosen layout is remembered across sessions; `/linux-ops-panel` toggles it. Codex and Antigravity ignore it.

## Compatibility

- Scripts run on Python 3.6 or later with the standard library only, so they work wherever `python3` exists without installing anything else.
- `skills/linux-ops` follows the Agent Skills format (`SKILL.md` plus bundled files) and avoids features of any single agent in its instructions. Everything specific to one agent (manifests, hook files, Claude Code's `commands/`) only calls its scripts, and there is one copy of the skill.
- The host profile, journal entries and snapshots are versioned by `schema_version`; a field is removed or changes meaning only with a version bump.
