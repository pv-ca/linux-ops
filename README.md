# linux-ops

An agent skill for administering the Linux machine the agent runs on. It gives the agent a profile of the host, a method for changing it safely, and a rule for staying out of the way on systems it does not support.

> Early draft, version 0.1.0. The host profile and the method exist; the inventory, change journal and evals listed under Planned do not yet. No license has been chosen, so all rights are reserved for now.

Models already know `apt` and `systemctl`. What they lack is the state of this particular machine and the discipline to change it reversibly, so that is what the skill supplies.

## Supported systems

| Level | Systems |
| --- | --- |
| Tier 1, tested in CI | Fedora, Debian, Ubuntu, Arch Linux, openSUSE Tumbleweed, openSUSE Leap |
| Derivative, untested | Distributions that declare one of those families in `ID_LIKE`, such as Rocky, Linux Mint or Manjaro |
| Everything else | Read-only mode: the skill inspects and advises, and makes no changes |

Image-based systems (Fedora Silverblue and Kinoite, openSUSE MicroOS and Aeon), NixOS and hosts without systemd are held in read-only mode. [docs/CONTRACT.md](docs/CONTRACT.md) states the rules.

## What is in this version

- `skills/linux-ops/SKILL.md`: the method, covering evidence, change transactions and the confirmation boundary.
- `skills/linux-ops/scripts/detect_host.py`: prints the host profile as JSON. It reads the host and changes nothing. Python 3.6+, standard library only.

```console
$ python3 skills/linux-ops/scripts/detect_host.py --compact
{"change_model": "imperative", "environment": "physical", "family": "fedora", "init": "systemd", "mode": "read-write", "package_manager": "dnf", ...}
```

## Install

Copy `skills/linux-ops` into your agent's skills directory, for example `~/.claude/skills/linux-ops` for Claude Code or `~/.agents/skills/linux-ops` for Codex.

## Planned

In order: a read-only inventory with sensitive values redacted, a change journal with backups and undo commands, a handoff file for resuming work, a hook that blocks destructive commands outside a transaction, a comparison of two inventories, and proposed permission rules.

## Development

```console
$ python3 -m pytest -q tests     # unit tests against fake host trees
$ tests/containers.sh            # the detector inside each tier 1 container image
```

`tests/containers.sh` needs Docker or Podman and network access; set `ENGINE` to choose between them.
